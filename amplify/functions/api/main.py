"""
Zapier Triggers API - FastAPI Backend
Endpoints: POST /events, GET /inbox, POST /inbox/{id}/ack
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
import os
import uuid
import json
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-2'))
table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'zapier-triggers-events')
table = dynamodb.Table(table_name)

# Initialize Secrets Manager client
secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-2'))
secret_arn = os.environ.get('SECRET_ARN')

# Global cache for secrets (Lambda container reuse optimization)
_secrets_cache: Dict[str, Any] = {}

def get_secret(secret_id: str) -> Dict[str, Any]:
    """
    Retrieve a secret from AWS Secrets Manager with caching.

    Args:
        secret_id: The ARN or name of the secret

    Returns:
        Dict containing the secret values

    Raises:
        HTTPException: If secret retrieval fails
    """
    # Return cached value if available
    if secret_id in _secrets_cache:
        return _secrets_cache[secret_id]

    try:
        response = secrets_client.get_secret_value(SecretId=secret_id)

        # Parse the secret string (it's JSON)
        if 'SecretString' in response:
            secret_data = json.loads(response['SecretString'])
        else:
            # Handle binary secrets (though we're using string secrets)
            secret_data = response['SecretBinary']

        # Cache the secret for future requests in this Lambda container
        _secrets_cache[secret_id] = secret_data
        return secret_data

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ResourceNotFoundException':
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Secret {secret_id} not found"
            )
        elif error_code == 'InvalidRequestException':
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid request for secret: {str(e)}"
            )
        elif error_code == 'DecryptionFailure':
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to decrypt secret using KMS key"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve secret: {str(e)}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error retrieving secret: {str(e)}"
        )

app = FastAPI(
    title="Zapier Triggers API",
    description="Event ingestion and delivery API for Zapier automation",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class Event(BaseModel):
    type: str
    source: str
    payload: dict

class EventResponse(BaseModel):
    id: str
    status: str
    timestamp: str

class InboxEvent(BaseModel):
    id: str
    type: str
    source: str
    payload: dict
    status: str
    created_at: str
    updated_at: str

# Health check endpoint
@app.get("/")
def read_root():
    return {
        "service": "Zapier Triggers API",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# GET /config - Retrieve non-sensitive configuration (demonstrates secret access)
@app.get("/config")
async def get_config():
    """
    Retrieve non-sensitive configuration values from Secrets Manager.
    This demonstrates secure secret retrieval at runtime.
    """
    if not secret_arn:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SECRET_ARN environment variable not configured"
        )

    try:
        secrets = get_secret(secret_arn)

        # Return only non-sensitive configuration
        # NEVER expose actual API keys or secrets in responses
        return {
            "environment": secrets.get("environment", "unknown"),
            "zapier_configured": "zapier_api_key" in secrets,
            "webhook_configured": "zapier_webhook_url" in secrets,
            "jwt_configured": "jwt_secret" in secrets,
            "cache_hit": secret_arn in _secrets_cache,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve configuration: {str(e)}"
        )

# POST /events - Ingest new event
@app.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(event: Event):
    """
    Ingest a new event into the system.
    Returns event ID, status, and timestamp.
    """
    # Generate unique event ID
    event_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Store event in DynamoDB
    event_data = {
        "id": event_id,
        "type": event.type,
        "source": event.source,
        "payload": event.payload,
        "status": "pending",
        "created_at": timestamp,
        "updated_at": timestamp
    }

    try:
        table.put_item(Item=event_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store event: {str(e)}"
        )

    return EventResponse(
        id=event_id,
        status="pending",
        timestamp=timestamp
    )

# GET /inbox - Retrieve undelivered events
@app.get("/inbox", response_model=List[InboxEvent])
async def get_inbox():
    """
    Retrieve all undelivered events from the inbox.
    """
    try:
        # Query GSI for pending events
        response = table.query(
            IndexName='status-index',
            KeyConditionExpression=Key('status').eq('pending'),
            ScanIndexForward=False,  # Sort by created_at descending
            Limit=100  # Limit to 100 events
        )

        events = []
        for item in response.get('Items', []):
            events.append(InboxEvent(
                id=item['id'],
                type=item['type'],
                source=item['source'],
                payload=item['payload'],
                status=item['status'],
                created_at=item['created_at'],
                updated_at=item['updated_at']
            ))

        return events
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve inbox: {str(e)}"
        )

# POST /inbox/{event_id}/ack - Acknowledge event delivery
@app.post("/inbox/{event_id}/ack")
async def acknowledge_event(event_id: str):
    """
    Acknowledge successful delivery of an event.
    Updates event status to 'delivered'.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"

    try:
        # First, get the item to find its created_at (sort key)
        response = table.query(
            KeyConditionExpression=Key('id').eq(event_id),
            Limit=1
        )

        if not response.get('Items'):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with ID {event_id} not found"
            )

        item = response['Items'][0]

        # Update the event status
        table.update_item(
            Key={
                'id': event_id,
                'created_at': item['created_at']
            },
            UpdateExpression="SET #status = :status, updated_at = :timestamp",
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':status': 'delivered',
                ':timestamp': timestamp
            }
        )

        return {
            "id": event_id,
            "status": "delivered",
            "message": "Event acknowledged successfully",
            "updated_at": timestamp
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to acknowledge event: {str(e)}"
        )

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {"error": "Not found", "path": str(request.url)}

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return {"error": "Internal server error"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
