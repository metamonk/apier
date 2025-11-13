"""
Zapier Triggers API - FastAPI Backend
Endpoints: POST /events, GET /inbox, POST /inbox/{id}/ack
Includes JWT Bearer token authentication for API security.
"""
from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import os
import uuid
import json
import time
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# AWS X-Ray instrumentation
from aws_xray_sdk.core import xray_recorder, patch_all

# Patch all AWS SDK calls for automatic tracing
patch_all()

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

# Initialize CloudWatch client for custom metrics
cloudwatch_client = boto3.client('cloudwatch', region_name=os.environ.get('AWS_REGION', 'us-east-2'))
CLOUDWATCH_NAMESPACE = 'ZapierTriggersAPI'

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

# OpenAPI Tags Metadata
tags_metadata = [
    {
        "name": "Authentication",
        "description": "OAuth2 authentication endpoints for obtaining JWT bearer tokens. "
                      "Use the `/token` endpoint to authenticate with your API key and receive a token for accessing protected endpoints.",
    },
    {
        "name": "Events",
        "description": "Event ingestion endpoints for receiving and storing events from external sources. "
                      "All event endpoints require JWT authentication.",
    },
    {
        "name": "Inbox",
        "description": "Event delivery endpoints for retrieving pending events and acknowledging successful delivery. "
                      "These endpoints enable the polling pattern for Zapier integrations.",
    },
    {
        "name": "Health",
        "description": "Service health check and status endpoints. These are publicly accessible without authentication.",
    },
    {
        "name": "Configuration",
        "description": "Configuration endpoints for retrieving non-sensitive system configuration. "
                      "Demonstrates secure secret retrieval from AWS Secrets Manager.",
    },
]

app = FastAPI(
    title="Zapier Triggers API",
    summary="Event ingestion and delivery API for Zapier automation workflows",
    description="""
## Overview

The **Zapier Triggers API** provides a robust event ingestion and delivery system designed for Zapier automation workflows.
This API enables external systems to send events that can be consumed by Zapier triggers using a polling pattern.

## Key Features

* **Event Ingestion**: POST events from any source with automatic storage and TTL management
* **Event Delivery**: Retrieve pending events via polling with acknowledgment support
* **JWT Authentication**: Secure OAuth2-based authentication using JWT bearer tokens
* **AWS Integration**: Leverages DynamoDB for storage and Secrets Manager for credential management
* **GDPR/CCPA Compliant**: Automatic data retention policies with 90-day TTL
* **Observability**: AWS X-Ray tracing and CloudWatch metrics for monitoring

## Authentication Flow

1. **Obtain Token**: POST credentials to `/token` endpoint (username: "api", password: your API key)
2. **Receive JWT**: Get a JWT bearer token valid for 24 hours
3. **Access Protected Endpoints**: Include token in Authorization header: `Bearer {token}`

## Typical Workflow

1. External system POSTs event data to `/events`
2. Event is stored with "pending" status in DynamoDB
3. Zapier polls `/inbox` to retrieve undelivered events
4. After successful processing, Zapier POSTs to `/inbox/{id}/ack`
5. Event status updates to "delivered"

## Data Retention

All events automatically expire after 90 days (TTL) for GDPR/CCPA compliance.
    """,
    version="1.0.0",
    terms_of_service="https://example.com/terms/",
    contact={
        "name": "API Support",
        "url": "https://example.com/support",
        "email": "support@example.com"
    },
    license_info={
        "name": "MIT",
        "identifier": "MIT",
    },
    openapi_tags=tags_metadata,
)

# CloudWatch Metrics Middleware
@app.middleware("http")
async def cloudwatch_metrics_middleware(request: Request, call_next):
    """
    Middleware to track API performance metrics and publish to CloudWatch.
    Tracks: ingestion latency, error rates, and request counts.
    """
    start_time = time.perf_counter()
    endpoint = request.url.path
    method = request.method

    # Process the request
    response = None
    error_occurred = False
    status_code = 500  # Default to error if something goes wrong

    try:
        response = await call_next(request)
        status_code = response.status_code

        # Check if this is an error response
        if status_code >= 400:
            error_occurred = True

    except Exception as e:
        error_occurred = True
        # Re-raise the exception after recording metrics
        raise
    finally:
        # Calculate request duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Add processing time header
        if response:
            response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"

        # Publish metrics to CloudWatch asynchronously (fire and forget)
        # We don't await this to avoid slowing down the response
        try:
            publish_request_metrics(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
                error_occurred=error_occurred
            )
        except Exception as metric_error:
            # Log error but don't fail the request
            print(f"Failed to publish CloudWatch metrics: {str(metric_error)}")

    return response


def publish_request_metrics(endpoint: str, method: str, status_code: int, duration_ms: float, error_occurred: bool):
    """
    Publish custom metrics to CloudWatch.

    Metrics published:
    - ApiLatency: Request duration in milliseconds
    - ApiRequests: Request count
    - ApiErrors: Error count (4xx and 5xx)
    - Api4xxErrors: Client error count
    - Api5xxErrors: Server error count
    """
    try:
        metric_data = []
        timestamp = datetime.utcnow()

        # Common dimensions for all metrics
        dimensions = [
            {'Name': 'Endpoint', 'Value': endpoint},
            {'Name': 'Method', 'Value': method},
            {'Name': 'StatusCode', 'Value': str(status_code)}
        ]

        # 1. API Latency Metric (for POST /events - ingestion latency)
        metric_data.append({
            'MetricName': 'ApiLatency',
            'Dimensions': dimensions,
            'Value': duration_ms,
            'Unit': 'Milliseconds',
            'Timestamp': timestamp,
            'StorageResolution': 60  # Standard resolution (60 seconds)
        })

        # 2. API Request Count
        metric_data.append({
            'MetricName': 'ApiRequests',
            'Dimensions': dimensions,
            'Value': 1,
            'Unit': 'Count',
            'Timestamp': timestamp,
            'StorageResolution': 60
        })

        # 3. Error Metrics
        if error_occurred:
            # Total errors
            metric_data.append({
                'MetricName': 'ApiErrors',
                'Dimensions': dimensions,
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': timestamp,
                'StorageResolution': 60
            })

            # 4xx errors (client errors)
            if 400 <= status_code < 500:
                metric_data.append({
                    'MetricName': 'Api4xxErrors',
                    'Dimensions': dimensions,
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': timestamp,
                    'StorageResolution': 60
                })

            # 5xx errors (server errors)
            elif status_code >= 500:
                metric_data.append({
                    'MetricName': 'Api5xxErrors',
                    'Dimensions': dimensions,
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': timestamp,
                    'StorageResolution': 60
                })

        # 4. API Availability (success rate)
        metric_data.append({
            'MetricName': 'ApiAvailability',
            'Dimensions': [{'Name': 'Endpoint', 'Value': endpoint}],
            'Value': 1 if not error_occurred else 0,
            'Unit': 'Count',
            'Timestamp': timestamp,
            'StorageResolution': 60
        })

        # Publish all metrics in a single API call
        cloudwatch_client.put_metric_data(
            Namespace=CLOUDWATCH_NAMESPACE,
            MetricData=metric_data
        )

    except Exception as e:
        # Log but don't fail - metrics are best effort
        print(f"Error publishing metrics to CloudWatch: {str(e)}")


# CORS configuration handled by Lambda Function URL
# Commenting out FastAPI CORS middleware to avoid duplicate headers
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=False,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# Request/Response Models
class Event(BaseModel):
    """Event ingestion request model"""
    type: str
    source: str
    payload: dict

    class Config:
        json_schema_extra = {
            "example": {
                "type": "user.created",
                "source": "web-app",
                "payload": {
                    "user_id": "12345",
                    "email": "user@example.com",
                    "name": "John Doe"
                }
            }
        }

class EventResponse(BaseModel):
    """Event creation response model"""
    id: str
    status: str
    timestamp: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }

class InboxEvent(BaseModel):
    """Inbox event model with full details"""
    id: str
    type: str
    source: str
    payload: dict
    status: str
    created_at: str
    updated_at: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "type": "user.created",
                "source": "web-app",
                "payload": {
                    "user_id": "12345",
                    "email": "user@example.com"
                },
                "status": "pending",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z"
            }
        }


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
@app.post("/token", response_model=Token, tags=["Authentication"],
          summary="Obtain JWT Access Token",
          response_description="JWT bearer token for API authentication")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    jwt_secret: str = Depends(get_jwt_secret)
):
    """
    ## OAuth2 Token Endpoint

    Authenticate with your API credentials and receive a JWT bearer token for accessing protected endpoints.

    ### Credentials

    - **username**: Must be "api"
    - **password**: Your Zapier API key

    ### Response

    Returns a JWT access token valid for 24 hours that must be included in the Authorization header
    for all protected endpoint requests.

    ### Example Usage

    ```bash
    curl -X POST "https://your-api.com/token" \\
         -H "Content-Type: application/x-www-form-urlencoded" \\
         -d "username=api&password=your-api-key-here"
    ```
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


# Health check endpoints (public - no authentication required)
@app.get("/", tags=["Health"],
         summary="Root Endpoint",
         response_description="API service information and status")
def read_root():
    """
    ## Root API Endpoint

    Returns basic information about the API service including name, status, and version.
    This endpoint is publicly accessible and does not require authentication.
    """
    return {
        "service": "Zapier Triggers API",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/health", tags=["Health"],
         summary="Health Check",
         response_description="Service health status")
def health_check():
    """
    ## Health Check Endpoint

    Simple health check endpoint that returns the service status.
    Used by load balancers and monitoring systems to verify service availability.
    This endpoint is publicly accessible and does not require authentication.
    """
    return {"status": "healthy"}

# GET /config - Retrieve non-sensitive configuration (demonstrates secret access)
@app.get("/config", tags=["Configuration"],
         summary="Get Configuration Status",
         response_description="Non-sensitive configuration information")
async def get_config():
    """
    ## Configuration Status Endpoint

    Retrieves non-sensitive configuration information from AWS Secrets Manager.
    This endpoint demonstrates secure secret retrieval at runtime without exposing sensitive values.

    ### Response

    Returns boolean flags indicating which secrets are configured and whether the secret cache was hit.

    **Note**: This endpoint does NOT expose actual API keys or secret values for security reasons.
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
@app.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED,
          tags=["Events"],
          summary="Create New Event",
          response_description="Event created successfully with ID and timestamp")
async def create_event(
    event: Event,
    current_user: User = Depends(get_authenticated_user)
):
    """
    ## Create Event Endpoint

    Ingests a new event into the system for processing by Zapier workflows.

    ### Authentication

    Requires JWT bearer token in Authorization header.

    ### Request Body

    - **type**: Event type identifier (e.g., "user.created", "order.placed")
    - **source**: Event source system (e.g., "shopify", "salesforce")
    - **payload**: Event data as JSON object

    ### Response

    Returns the created event with:
    - **id**: Unique event identifier (UUID)
    - **status**: Always "pending" for new events
    - **timestamp**: ISO 8601 timestamp of event creation

    ### Data Retention

    Events automatically expire after 90 days (GDPR/CCPA compliance).

    ### Example

    ```json
    {
      "type": "user.created",
      "source": "web-app",
      "payload": {
        "user_id": "12345",
        "email": "user@example.com"
      }
    }
    ```
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
@app.get("/inbox", response_model=List[InboxEvent],
         tags=["Inbox"],
         summary="Get Pending Events",
         response_description="List of pending events awaiting delivery")
async def get_inbox(current_user: User = Depends(get_authenticated_user)):
    """
    ## Get Inbox Events

    Retrieves all undelivered (pending) events from the inbox for Zapier polling.

    ### Authentication

    Requires JWT bearer token in Authorization header.

    ### Response

    Returns an array of pending events (max 100), sorted by creation time (newest first).
    Each event includes:
    - **id**: Unique event identifier
    - **type**: Event type
    - **source**: Event source system
    - **payload**: Event data
    - **status**: Event status (will be "pending")
    - **created_at**: Event creation timestamp
    - **updated_at**: Last update timestamp

    ### Polling Pattern

    This endpoint is designed for Zapier's polling trigger pattern:
    1. Zapier polls this endpoint periodically
    2. Retrieves pending events
    3. Processes events in Zapier workflows
    4. Acknowledges each event via `/inbox/{id}/ack`
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
@app.post("/inbox/{event_id}/ack",
          tags=["Inbox"],
          summary="Acknowledge Event Delivery",
          response_description="Event acknowledged and marked as delivered")
async def acknowledge_event(
    event_id: str,
    current_user: User = Depends(get_authenticated_user)
):
    """
    ## Acknowledge Event

    Marks an event as successfully delivered after Zapier has processed it.

    ### Authentication

    Requires JWT bearer token in Authorization header.

    ### Path Parameters

    - **event_id**: The unique identifier (UUID) of the event to acknowledge

    ### Response

    Returns confirmation with:
    - **id**: The acknowledged event ID
    - **status**: New status ("delivered")
    - **message**: Confirmation message
    - **updated_at**: Timestamp of acknowledgment

    ### Workflow

    After Zapier successfully processes an event from `/inbox`:
    1. Call this endpoint with the event ID
    2. Event status updates from "pending" to "delivered"
    3. Event will no longer appear in future `/inbox` requests

    ### Error Handling

    Returns 404 if event ID is not found.
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
