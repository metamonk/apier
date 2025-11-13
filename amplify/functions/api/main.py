"""
Zapier Triggers API - FastAPI Backend
Endpoints: POST /events, GET /inbox, POST /inbox/{id}/ack
Includes JWT Bearer token authentication for API security.
"""
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import os
import uuid
import json
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# Import authentication utilities
import auth
from auth import (
    Token,
    User,
    create_access_token,
    authenticate_api_key
)

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


# Dependency to inject JWT secret from AWS Secrets Manager
def get_jwt_secret() -> str:
    """Get JWT secret from AWS Secrets Manager."""
    if not secret_arn:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SECRET_ARN environment variable not configured"
        )
    secrets = get_secret(secret_arn)
    jwt_secret = secrets.get("jwt_secret")
    if not jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret not found in secrets manager"
        )
    return jwt_secret


# Dependency to get current authenticated user with JWT secret injection
async def get_authenticated_user(
    token: str = Depends(auth.oauth2_scheme),
    jwt_secret: str = Depends(get_jwt_secret)
) -> User:
    """Get the current authenticated user by validating the JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = auth.decode_access_token(token, jwt_secret)
        username: str = payload.get("sub")

        if username is None:
            raise credentials_exception

        # Return user from token claims
        user = User(username=username, disabled=False)
        return user
    except Exception:
        raise credentials_exception


# Authentication endpoint
@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    jwt_secret: str = Depends(get_jwt_secret)
):
    """
    OAuth2 compatible token endpoint.
    Authenticate with API key and receive a JWT bearer token.

    The username should be "api" and the password should be the Zapier API key.
    """
    # Get stored API key from secrets
    secrets = get_secret(secret_arn)
    stored_api_key = secrets.get("zapier_api_key")

    if not stored_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured in secrets manager"
        )

    # Validate credentials
    if form_data.username != "api" or not authenticate_api_key(form_data.password, stored_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create JWT token
    access_token_expires = timedelta(hours=24)
    access_token = create_access_token(
        data={"sub": form_data.username, "api_key": stored_api_key[:8] + "..."},
        secret_key=jwt_secret,
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


# Health check endpoint (public - no authentication required)
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

# POST /events - Ingest new event (protected endpoint)
@app.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event: Event,
    current_user: User = Depends(get_authenticated_user)
):
    """
    Ingest a new event into the system.
    Returns event ID, status, and timestamp.

    Requires authentication via JWT bearer token.
    """
    # Generate unique event ID
    event_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Calculate TTL for GDPR/CCPA compliance (90 days from now)
    ttl_timestamp = int((datetime.utcnow() + timedelta(days=90)).timestamp())

    # Store event in DynamoDB
    event_data = {
        "id": event_id,
        "type": event.type,
        "source": event.source,
        "payload": event.payload,
        "status": "pending",
        "created_at": timestamp,
        "updated_at": timestamp,
        "ttl": ttl_timestamp  # GDPR/CCPA: Auto-delete after 90 days
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

# GET /inbox - Retrieve undelivered events (protected endpoint)
@app.get("/inbox", response_model=List[InboxEvent])
async def get_inbox(current_user: User = Depends(get_authenticated_user)):
    """
    Retrieve all undelivered events from the inbox.

    Requires authentication via JWT bearer token.
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

# POST /inbox/{event_id}/ack - Acknowledge event delivery (protected endpoint)
@app.post("/inbox/{event_id}/ack")
async def acknowledge_event(
    event_id: str,
    current_user: User = Depends(get_authenticated_user)
):
    """
    Acknowledge successful delivery of an event.
    Updates event status to 'delivered'.

    Requires authentication via JWT bearer token.
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

# Lambda handler using Mangum
from mangum import Mangum
handler = Mangum(app, lifespan="off")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
