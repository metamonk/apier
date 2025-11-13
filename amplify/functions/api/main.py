"""
Zapier Triggers API - FastAPI Backend
Endpoints: POST /events, GET /inbox, POST /inbox/{id}/ack
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import os
import uuid
import boto3
from boto3.dynamodb.conditions import Key

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'zapier-triggers-events')
table = dynamodb.Table(table_name)

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
