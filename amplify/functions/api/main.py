"""
Zapier Triggers API - FastAPI Backend
Endpoints: POST /events, GET /inbox, POST /inbox/{id}/ack
Includes JWT Bearer token authentication for API security.
"""
from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import os
import uuid
import json
import time
import hmac
import hashlib
import csv
import io
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

# AWS X-Ray instrumentation
from aws_xray_sdk.core import xray_recorder, patch_all

# Patch all AWS SDK calls for automatic tracing
patch_all()

# Utility function to convert floats to Decimals for DynamoDB
def convert_floats_to_decimal(obj):
    """
    Recursively convert all float values to Decimal for DynamoDB compatibility.

    DynamoDB does not support Python's float type - it requires Decimal instead.
    This function walks through dictionaries, lists, and nested structures to
    convert all float values while preserving the structure.

    Args:
        obj: Object to convert (dict, list, or primitive)

    Returns:
        Object with all floats converted to Decimal
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj

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
    {
        "name": "Webhooks",
        "description": "Webhook receiver endpoints for receiving events from the dispatcher service. "
                      "Includes HMAC signature validation for security and comprehensive event logging.",
    },
    {
        "name": "Compliance",
        "description": "Data export and compliance endpoints for GDPR/CCPA data portability requirements. "
                      "Allows authenticated users to export their event data in various formats.",
    },
    {
        "name": "Metrics",
        "description": "Real-time metrics endpoints for monitoring dashboard. "
                      "Provides event counts, latency statistics, throughput data, and error rates. "
                      "All metrics endpoints require JWT authentication.",
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

class WebhookEvent(BaseModel):
    """Webhook event model for receiving events from dispatcher"""
    event_type: str
    payload: dict
    timestamp: Optional[str] = None
    event_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "user.created",
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "payload": {
                    "user_id": "12345",
                    "email": "user@example.com"
                },
                "timestamp": "2024-01-15T10:30:00Z"
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
    delivery_attempts: Optional[int] = 0
    last_delivery_attempt: Optional[str] = None
    delivery_latency_ms: Optional[float] = None
    error_message: Optional[str] = None

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
                "updated_at": "2024-01-15T10:30:00Z",
                "delivery_attempts": 0,
                "last_delivery_attempt": None,
                "delivery_latency_ms": None,
                "error_message": None
            }
        }


class EventSummary(BaseModel):
    """Summary metrics for event monitoring dashboard"""
    total: int
    pending: int
    delivered: int
    failed: int
    success_rate: float

    class Config:
        json_schema_extra = {
            "example": {
                "total": 1247,
                "pending": 23,
                "delivered": 1198,
                "failed": 26,
                "success_rate": 97.91
            }
        }


class LatencyMetrics(BaseModel):
    """Latency metrics for event processing times"""
    p50: float
    p95: float
    p99: float
    sample_size: int

    class Config:
        json_schema_extra = {
            "example": {
                "p50": 1.23,
                "p95": 3.45,
                "p99": 5.67,
                "sample_size": 1150
            }
        }


class ThroughputMetrics(BaseModel):
    """Throughput metrics for events per time interval"""
    events_per_minute: float
    events_per_hour: float
    total_events_24h: int
    time_range: str

    class Config:
        json_schema_extra = {
            "example": {
                "events_per_minute": 2.5,
                "events_per_hour": 150.0,
                "total_events_24h": 3600,
                "time_range": "last_24_hours"
            }
        }


class ErrorMetrics(BaseModel):
    """Error metrics for failed deliveries and retries"""
    total_errors: int
    error_rate: float
    failed_deliveries: int
    pending_retries: int

    class Config:
        json_schema_extra = {
            "example": {
                "total_errors": 26,
                "error_rate": 2.09,
                "failed_deliveries": 26,
                "pending_retries": 5
            }
        }


class WebhookLog(BaseModel):
    """Webhook log entry for receiver UI"""
    id: str
    event_type: str
    payload: dict
    source_ip: str
    timestamp: str
    status: str
    request_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_type": "user.created",
                "payload": {"user_id": "12345", "email": "user@example.com"},
                "source_ip": "203.0.113.42",
                "timestamp": "2024-01-15T10:30:00Z",
                "status": "received",
                "request_id": "req_abc123"
            }
        }


# In-memory cache for metrics with TTL
metrics_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 30  # Cache metrics for 30 seconds

# In-memory cache for webhook logs (simulating CloudWatch logs for MVP)
# In production, query CloudWatch Logs or store in DynamoDB
webhook_logs_cache: List[Dict[str, Any]] = []
WEBHOOK_LOGS_MAX_SIZE = 1000  # Keep last 1000 webhook deliveries


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
    # Convert floats to Decimals for DynamoDB compatibility
    event_data = {
        "id": event_id,
        "type": event.type,
        "source": event.source,
        "payload": convert_floats_to_decimal(event.payload),
        "status": "pending",
        "created_at": timestamp,
        "updated_at": timestamp,
        "ttl": ttl_timestamp,  # GDPR/CCPA: Auto-delete after 90 days
        # Delivery tracking fields (Task 22.1)
        # Note: last_delivery_attempt is omitted for pending events (sparse GSI)
        # It will be added when the event is first delivered/attempted
        "delivery_attempts": 0
    }

    try:
        table.put_item(Item=event_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store event: {str(e)}"
        )

    # Publish EventsCreated metric to CloudWatch (Task 22.3)
    try:
        cloudwatch_client.put_metric_data(
            Namespace=CLOUDWATCH_NAMESPACE,
            MetricData=[
                {
                    'MetricName': 'EventsCreated',
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {'Name': 'EventType', 'Value': event.type},
                        {'Name': 'Source', 'Value': event.source}
                    ]
                }
            ]
        )
    except Exception as metric_error:
        # Don't fail the request if metrics fail (best effort)
        print(f"[WARNING] Failed to publish EventsCreated metric: {str(metric_error)}")

    return EventResponse(
        id=event_id,
        status="pending",
        timestamp=timestamp
    )

# GET /metrics/summary - Get event summary metrics (protected endpoint)
@app.get("/metrics/summary", response_model=EventSummary,
         tags=["Metrics"],
         summary="Get Event Summary Metrics",
         response_description="Summary of event counts and success rate")
async def get_metrics_summary(current_user: User = Depends(get_authenticated_user)):
    """
    ## Get Event Summary Metrics

    Returns aggregate metrics for monitoring dashboard:
    - **total**: Total number of events across all statuses
    - **pending**: Number of events waiting for delivery
    - **delivered**: Number of successfully delivered events
    - **failed**: Number of failed delivery attempts
    - **success_rate**: Percentage of successful deliveries (delivered / (delivered + failed))

    ### Caching
    Results are cached for 30 seconds to reduce database load.

    ### Example
    ```bash
    curl -X GET "https://your-api-url/metrics/summary" \\
      -H "Authorization: Bearer YOUR_JWT_TOKEN"
    ```

    ### Response
    ```json
    {
      "total": 1247,
      "pending": 23,
      "delivered": 1198,
      "failed": 26,
      "success_rate": 97.91
    }
    ```
    """
    # Check cache first
    cache_key = "summary"
    now = time.time()

    if cache_key in metrics_cache:
        cached_data = metrics_cache[cache_key]
        if now - cached_data["timestamp"] < CACHE_TTL_SECONDS:
            return cached_data["data"]

    try:
        # Scan table to count events by status
        # Note: This is a full table scan which is acceptable for MVP
        # For production at scale, consider using DynamoDB Streams + Lambda aggregator
        response = table.scan(
            ProjectionExpression="id, #status",
            ExpressionAttributeNames={"#status": "status"}
        )

        events = response.get("Items", [])

        # Handle pagination if more than 1MB of data
        while "LastEvaluatedKey" in response:
            response = table.scan(
                ProjectionExpression="id, #status",
                ExpressionAttributeNames={"#status": "status"},
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            events.extend(response.get("Items", []))

        # Count events by status
        total = len(events)
        pending = sum(1 for e in events if e.get("status") == "pending")
        delivered = sum(1 for e in events if e.get("status") == "delivered")
        failed = sum(1 for e in events if e.get("status") == "failed")

        # Calculate success rate
        completed = delivered + failed
        success_rate = (delivered / completed * 100) if completed > 0 else 0.0

        result = EventSummary(
            total=total,
            pending=pending,
            delivered=delivered,
            failed=failed,
            success_rate=round(success_rate, 2)
        )

        # Update cache
        metrics_cache[cache_key] = {
            "data": result,
            "timestamp": now
        }

        return result

    except ClientError as e:
        print(f"DynamoDB error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )


# GET /metrics/latency - Get latency percentiles (protected endpoint)
@app.get("/metrics/latency", response_model=LatencyMetrics,
         tags=["Metrics"],
         summary="Get Event Processing Latency Metrics",
         response_description="Latency percentiles (P50, P95, P99) for completed events")
async def get_metrics_latency(current_user: User = Depends(get_authenticated_user)):
    """
    ## Get Event Processing Latency Metrics

    Returns latency percentiles for event processing:
    - **p50**: 50th percentile latency in seconds (median)
    - **p95**: 95th percentile latency in seconds
    - **p99**: 99th percentile latency in seconds
    - **sample_size**: Number of events included in calculation

    Latency is calculated as the time between event creation (`created_at`)
    and final status update (`updated_at`) for delivered and failed events.

    ### Caching
    Results are cached for 30 seconds to reduce database load.

    ### Example
    ```bash
    curl -X GET "https://your-api-url/metrics/latency" \\
      -H "Authorization: Bearer YOUR_JWT_TOKEN"
    ```

    ### Response
    ```json
    {
      "p50": 1.23,
      "p95": 3.45,
      "p99": 5.67,
      "sample_size": 1150
    }
    ```
    """
    # Check cache first
    cache_key = "latency"
    now = time.time()

    if cache_key in metrics_cache:
        cached_data = metrics_cache[cache_key]
        if now - cached_data["timestamp"] < CACHE_TTL_SECONDS:
            return cached_data["data"]

    try:
        # Scan for completed events (delivered or failed) with timestamps
        response = table.scan(
            ProjectionExpression="id, #status, created_at, updated_at",
            FilterExpression=Attr("status").is_in(["delivered", "failed"]),
            ExpressionAttributeNames={"#status": "status"}
        )

        events = response.get("Items", [])

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(
                ProjectionExpression="id, #status, created_at, updated_at",
                FilterExpression=Attr("status").is_in(["delivered", "failed"]),
                ExpressionAttributeNames={"#status": "status"},
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            events.extend(response.get("Items", []))

        # Calculate latencies in seconds
        latencies = []
        for event in events:
            try:
                created = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
                updated = datetime.fromisoformat(event["updated_at"].replace("Z", "+00:00"))
                latency = (updated - created).total_seconds()
                latencies.append(latency)
            except (KeyError, ValueError):
                # Skip events with missing or invalid timestamps
                continue

        # Calculate percentiles
        if latencies:
            latencies.sort()
            n = len(latencies)
            p50_idx = int(n * 0.50)
            p95_idx = int(n * 0.95)
            p99_idx = int(n * 0.99)

            result = LatencyMetrics(
                p50=round(latencies[p50_idx] if p50_idx < n else latencies[-1], 2),
                p95=round(latencies[p95_idx] if p95_idx < n else latencies[-1], 2),
                p99=round(latencies[p99_idx] if p99_idx < n else latencies[-1], 2),
                sample_size=n
            )
        else:
            # No completed events yet
            result = LatencyMetrics(p50=0.0, p95=0.0, p99=0.0, sample_size=0)

        # Update cache
        metrics_cache[cache_key] = {
            "data": result,
            "timestamp": now
        }

        return result

    except ClientError as e:
        print(f"DynamoDB error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve latency metrics: {str(e)}"
        )


# GET /metrics/throughput - Get event throughput metrics (protected endpoint)
@app.get("/metrics/throughput", response_model=ThroughputMetrics,
         tags=["Metrics"],
         summary="Get Event Throughput Metrics",
         response_description="Event throughput rates over the last 24 hours")
async def get_metrics_throughput(current_user: User = Depends(get_authenticated_user)):
    """
    ## Get Event Throughput Metrics

    Returns event throughput rates for the last 24 hours:
    - **events_per_minute**: Average events per minute
    - **events_per_hour**: Average events per hour
    - **total_events_24h**: Total events in the last 24 hours
    - **time_range**: Time range description

    ### Caching
    Results are cached for 30 seconds to reduce database load.

    ### Example
    ```bash
    curl -X GET "https://your-api-url/metrics/throughput" \\
      -H "Authorization: Bearer YOUR_JWT_TOKEN"
    ```

    ### Response
    ```json
    {
      "events_per_minute": 2.5,
      "events_per_hour": 150.0,
      "total_events_24h": 3600,
      "time_range": "last_24_hours"
    }
    ```
    """
    # Check cache first
    cache_key = "throughput"
    now_time = time.time()

    if cache_key in metrics_cache:
        cached_data = metrics_cache[cache_key]
        if now_time - cached_data["timestamp"] < CACHE_TTL_SECONDS:
            return cached_data["data"]

    try:
        # Calculate 24 hours ago timestamp
        now = datetime.utcnow()
        hours_24_ago = now - timedelta(hours=24)
        cutoff_iso = hours_24_ago.isoformat() + "Z"

        # Scan for events created in the last 24 hours
        response = table.scan(
            ProjectionExpression="id, created_at",
            FilterExpression=Attr("created_at").gte(cutoff_iso)
        )

        events = response.get("Items", [])

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(
                ProjectionExpression="id, created_at",
                FilterExpression=Attr("created_at").gte(cutoff_iso),
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            events.extend(response.get("Items", []))

        total_events = len(events)

        # Calculate rates
        # 24 hours = 1440 minutes
        events_per_minute = round(total_events / 1440.0, 2) if total_events > 0 else 0.0
        events_per_hour = round(total_events / 24.0, 2) if total_events > 0 else 0.0

        result = ThroughputMetrics(
            events_per_minute=events_per_minute,
            events_per_hour=events_per_hour,
            total_events_24h=total_events,
            time_range="last_24_hours"
        )

        # Update cache
        metrics_cache[cache_key] = {
            "data": result,
            "timestamp": now_time
        }

        return result

    except ClientError as e:
        print(f"DynamoDB error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve throughput metrics: {str(e)}"
        )


# GET /metrics/errors - Get error metrics (protected endpoint)
@app.get("/metrics/errors", response_model=ErrorMetrics,
         tags=["Metrics"],
         summary="Get Error Metrics",
         response_description="Error rates and failed delivery statistics")
async def get_metrics_errors(current_user: User = Depends(get_authenticated_user)):
    """
    ## Get Error Metrics

    Returns error and failure statistics:
    - **total_errors**: Total number of failed events
    - **error_rate**: Percentage of failed deliveries
    - **failed_deliveries**: Number of events with failed status
    - **pending_retries**: Number of pending events (potential retries)

    Error rate is calculated as: (failed / (delivered + failed)) * 100

    ### Caching
    Results are cached for 30 seconds to reduce database load.

    ### Example
    ```bash
    curl -X GET "https://your-api-url/metrics/errors" \\
      -H "Authorization: Bearer YOUR_JWT_TOKEN"
    ```

    ### Response
    ```json
    {
      "total_errors": 26,
      "error_rate": 2.09,
      "failed_deliveries": 26,
      "pending_retries": 5
    }
    ```
    """
    # Check cache first
    cache_key = "errors"
    now = time.time()

    if cache_key in metrics_cache:
        cached_data = metrics_cache[cache_key]
        if now - cached_data["timestamp"] < CACHE_TTL_SECONDS:
            return cached_data["data"]

    try:
        # Scan table to count events by status
        response = table.scan(
            ProjectionExpression="id, #status",
            ExpressionAttributeNames={"#status": "status"}
        )

        events = response.get("Items", [])

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(
                ProjectionExpression="id, #status",
                ExpressionAttributeNames={"#status": "status"},
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            events.extend(response.get("Items", []))

        # Count by status
        failed = sum(1 for e in events if e.get("status") == "failed")
        delivered = sum(1 for e in events if e.get("status") == "delivered")
        pending = sum(1 for e in events if e.get("status") == "pending")

        # Calculate error rate
        completed = delivered + failed
        error_rate = (failed / completed * 100) if completed > 0 else 0.0

        result = ErrorMetrics(
            total_errors=failed,
            error_rate=round(error_rate, 2),
            failed_deliveries=failed,
            pending_retries=pending
        )

        # Update cache
        metrics_cache[cache_key] = {
            "data": result,
            "timestamp": now
        }

        return result

    except ClientError as e:
        print(f"DynamoDB error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve error metrics: {str(e)}"
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
                updated_at=item['updated_at'],
                delivery_attempts=item.get('delivery_attempts', 0),
                last_delivery_attempt=item.get('last_delivery_attempt'),
                delivery_latency_ms=item.get('delivery_latency_ms'),
                error_message=item.get('error_message')
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

        # Calculate delivery latency (Task 22.3)
        created_at = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
        delivered_at = datetime.utcnow().replace(tzinfo=created_at.tzinfo)
        delivery_latency_ms = int((delivered_at - created_at).total_seconds() * 1000)

        # Update the event status with delivery tracking fields
        table.update_item(
            Key={
                'id': event_id,
                'created_at': item['created_at']
            },
            UpdateExpression="SET #status = :status, updated_at = :timestamp, last_delivery_attempt = :last_attempt, delivery_latency_ms = :latency, delivery_attempts = :attempts",
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':status': 'delivered',
                ':timestamp': timestamp,
                ':last_attempt': timestamp,
                ':latency': delivery_latency_ms,
                ':attempts': item.get('delivery_attempts', 0) + 1
            }
        )

        # Publish EventsDelivered and DeliveryLatency metrics to CloudWatch (Task 22.3)
        try:
            cloudwatch_client.put_metric_data(
                Namespace=CLOUDWATCH_NAMESPACE,
                MetricData=[
                    {
                        'MetricName': 'EventsDelivered',
                        'Value': 1,
                        'Unit': 'Count',
                        'Timestamp': datetime.utcnow(),
                        'Dimensions': [
                            {'Name': 'EventType', 'Value': item.get('type', 'unknown')},
                            {'Name': 'Source', 'Value': item.get('source', 'unknown')}
                        ]
                    },
                    {
                        'MetricName': 'DeliveryLatency',
                        'Value': delivery_latency_ms,
                        'Unit': 'Milliseconds',
                        'Timestamp': datetime.utcnow(),
                        'Dimensions': [
                            {'Name': 'EventType', 'Value': item.get('type', 'unknown')},
                            {'Name': 'Source', 'Value': item.get('source', 'unknown')}
                        ]
                    }
                ]
            )
        except Exception as metric_error:
            # Don't fail the request if metrics fail (best effort)
            print(f"[WARNING] Failed to publish delivery metrics: {str(metric_error)}")

        return {
            "id": event_id,
            "status": "delivered",
            "message": "Event acknowledged successfully",
            "updated_at": timestamp,
            "delivery_latency_ms": delivery_latency_ms
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to acknowledge event: {str(e)}"
        )


# DELETE /events/{event_id} - Delete event for GDPR/CCPA compliance (protected endpoint)
@app.delete("/events/{event_id}",
           tags=["Events"],
           summary="Delete Event",
           response_description="Event deleted successfully")
async def delete_event(
    event_id: str,
    current_user: User = Depends(get_authenticated_user)
):
    """
    ## Delete Event

    Permanently deletes an event from the system for GDPR/CCPA compliance.

    ### Authentication

    Requires JWT bearer token in Authorization header.

    ### Path Parameters

    - **event_id**: The unique identifier (UUID) of the event to delete

    ### Response

    Returns confirmation with:
    - **id**: The deleted event ID
    - **message**: Confirmation message
    - **deleted_at**: Timestamp of deletion

    ### Use Cases

    This endpoint supports:
    - **GDPR Right to Erasure**: Delete personal data upon user request
    - **CCPA Data Deletion**: Remove consumer data as required by California law
    - **Data Minimization**: Remove events that are no longer needed

    ### Audit Logging

    All deletions are logged to CloudWatch for compliance audit trails with:
    - Event ID
    - Deletion timestamp
    - Authenticated user performing the deletion

    ### Error Handling

    - Returns 404 if event ID is not found
    - Returns 401 if authentication fails
    - Returns 500 for internal server errors

    ### Example

    ```bash
    curl -X DELETE "https://your-api.com/events/{event_id}" \\
         -H "Authorization: Bearer {your_token}"
    ```
    """
    timestamp = datetime.utcnow().isoformat() + "Z"

    try:
        # First, query to get the item and verify it exists
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

        # Delete the event from DynamoDB
        table.delete_item(
            Key={
                'id': event_id,
                'created_at': item['created_at']
            }
        )

        # Log deletion for audit purposes
        print(f"[AUDIT] Event deleted: id={event_id}, "
              f"user={current_user.username}, timestamp={timestamp}, "
              f"event_type={item.get('type', 'unknown')}, "
              f"source={item.get('source', 'unknown')}")

        # Publish deletion metric to CloudWatch
        try:
            cloudwatch_client.put_metric_data(
                Namespace=CLOUDWATCH_NAMESPACE,
                MetricData=[
                    {
                        'MetricName': 'EventDeletion',
                        'Value': 1,
                        'Unit': 'Count',
                        'Timestamp': datetime.utcnow(),
                        'Dimensions': [
                            {'Name': 'EventType', 'Value': item.get('type', 'unknown')},
                            {'Name': 'Reason', 'Value': 'manual_deletion'}
                        ]
                    }
                ]
            )
        except Exception as metric_error:
            # Don't fail the request if metrics fail
            print(f"[WARNING] Failed to publish deletion metric: {str(metric_error)}")

        return {
            "id": event_id,
            "message": "Event deleted successfully",
            "deleted_at": timestamp
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete event: {str(e)}"
        )

# Helper function for HMAC signature validation
def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify HMAC signature of webhook payload.

    Args:
        payload: Raw request body bytes
        signature: Signature from X-Webhook-Signature header
        secret: Webhook secret from Secrets Manager

    Returns:
        True if signature is valid, False otherwise
    """
    if not signature or not secret:
        return False

    # Compute HMAC-SHA256 signature
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(signature, expected_signature)


# Dependency to validate webhook signature
async def validate_webhook_signature(request: Request) -> None:
    """
    Dependency to validate webhook HMAC signature before processing request body.
    This must run before FastAPI parses the request body.
    """
    # Get webhook secret from Secrets Manager
    if not secret_arn:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SECRET_ARN environment variable not configured"
        )

    secrets = get_secret(secret_arn)
    webhook_secret = secrets.get("zapier_webhook_secret")

    # If webhook secret is configured, validate signature
    if webhook_secret:
        # Get signature from header
        signature = request.headers.get("X-Webhook-Signature", "")

        # Get raw request body for signature verification
        # We need to cache this for later use by Pydantic
        body = await request.body()

        # Cache the body so it can be read again by FastAPI
        async def receive():
            return {"type": "http.request", "body": body}
        request._receive = receive

        # Verify signature
        if not verify_webhook_signature(body, signature, webhook_secret):
            client_host = request.client.host if request.client else "unknown"
            print(f"[WEBHOOK] Invalid signature from {client_host}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )


# POST /webhook - Receive events from dispatcher (security validated)
@app.post("/webhook",
          tags=["Webhooks"],
          summary="Receive Webhook Events",
          response_description="Webhook event received and logged successfully",
          dependencies=[Depends(validate_webhook_signature)])
async def receive_webhook(
    webhook_event: WebhookEvent,
    request: Request
):
    """
    ## Webhook Receiver Endpoint

    Receives events from the dispatcher service and logs them for debugging and monitoring.

    ### Security

    This endpoint validates HMAC signatures to ensure events are from authenticated sources.
    Include the `X-Webhook-Signature` header with an HMAC-SHA256 signature of the request body.

    ### Request Headers

    - **X-Webhook-Signature**: HMAC-SHA256 signature of the request body (hex encoded)
    - **X-Request-ID**: Optional request ID for tracking (will be logged)

    ### Request Body

    - **event_type**: Type of event being delivered
    - **event_id**: Optional unique event identifier
    - **payload**: Event data as JSON object
    - **timestamp**: Optional ISO 8601 timestamp of event creation

    ### Response

    Returns 200 OK with acknowledgment message if successful.
    Returns 401 Unauthorized if signature validation fails.

    ### Logging

    All received events are logged to CloudWatch with:
    - Event type and ID
    - Payload data
    - Source IP address
    - Timestamp
    - Request headers

    ### Idempotency

    This endpoint is idempotent and can safely handle duplicate deliveries.
    Duplicate events (same event_id) will be logged but acknowledged successfully.

    ### Example

    ```bash
    # Generate signature
    WEBHOOK_SECRET="your-webhook-secret"
    PAYLOAD='{"event_type":"user.created","payload":{"user_id":"123"}}'
    SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | cut -d' ' -f2)

    # Send webhook
    curl -X POST https://your-api.com/webhook \\
         -H "Content-Type: application/json" \\
         -H "X-Webhook-Signature: $SIGNATURE" \\
         -d "$PAYLOAD"
    ```
    """
    # Extract metadata
    timestamp = webhook_event.timestamp or datetime.utcnow().isoformat() + "Z"
    event_id = webhook_event.event_id or "unknown"
    request_id = request.headers.get("X-Request-ID", "none")
    source_ip = request.client.host if request.client else "unknown"

    # Log event to CloudWatch (via print/Lambda logs)
    print(f"[WEBHOOK] Received event: type={webhook_event.event_type}, "
          f"id={event_id}, source_ip={source_ip}, request_id={request_id}")
    print(f"[WEBHOOK] Event payload: {json.dumps(webhook_event.payload)}")
    print(f"[WEBHOOK] Event timestamp: {timestamp}")

    # Log all headers for debugging (excluding sensitive auth headers)
    headers_log = {k: v for k, v in request.headers.items()
                   if k.lower() not in ['authorization', 'x-webhook-signature']}
    print(f"[WEBHOOK] Request headers: {json.dumps(headers_log)}")

    # Store webhook log in memory cache for UI display
    log_entry = {
        "id": event_id if event_id != "unknown" else str(uuid.uuid4()),
        "event_type": webhook_event.event_type,
        "payload": webhook_event.payload,
        "source_ip": source_ip,
        "timestamp": timestamp,
        "status": "received",
        "request_id": request_id
    }

    # Add to beginning of list (newest first) and maintain max size
    webhook_logs_cache.insert(0, log_entry)
    if len(webhook_logs_cache) > WEBHOOK_LOGS_MAX_SIZE:
        webhook_logs_cache.pop()

    # Publish custom CloudWatch metric
    try:
        cloudwatch_client.put_metric_data(
            Namespace=CLOUDWATCH_NAMESPACE,
            MetricData=[
                {
                    'MetricName': 'WebhookReceived',
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {'Name': 'EventType', 'Value': webhook_event.event_type}
                    ]
                }
            ]
        )
    except Exception as e:
        # Don't fail the request if metrics fail
        print(f"[WEBHOOK] Failed to publish metric: {str(e)}")

    # Return 200 OK acknowledgment
    return {
        "status": "received",
        "message": "Webhook event received and logged successfully",
        "event_id": event_id,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


# GET /webhooks/logs - Get webhook delivery logs for receiver UI (protected endpoint)
@app.get("/webhooks/logs", response_model=List[WebhookLog],
         tags=["Webhooks"],
         summary="Get Webhook Delivery Logs",
         response_description="List of webhook deliveries with filtering support")
async def get_webhook_logs(
    event_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_authenticated_user)
):
    """
    ## Get Webhook Delivery Logs

    Retrieves webhook delivery logs for the receiver UI with filtering capabilities.

    ### Authentication

    Requires JWT bearer token in Authorization header.

    ### Query Parameters

    - **event_type** (optional): Filter by specific event type (e.g., "user.created")
    - **start_date** (optional): ISO 8601 timestamp - Filter logs from this date onwards
    - **end_date** (optional): ISO 8601 timestamp - Filter logs up to this date
    - **search** (optional): Search term to filter by payload content or event_id
    - **limit** (optional): Maximum number of logs to return (default: 100, max: 1000)

    ### Response

    Returns an array of webhook log entries sorted by timestamp (newest first).
    Each log includes:
    - **id**: Unique webhook delivery identifier
    - **event_type**: Type of event delivered
    - **payload**: Event data
    - **source_ip**: IP address of the sender
    - **timestamp**: Delivery timestamp (ISO 8601)
    - **status**: Delivery status (always "received" for successful deliveries)
    - **request_id**: Optional request tracking ID

    ### Example Requests

    ```bash
    # Get all webhook logs
    curl -H "Authorization: Bearer {token}" "https://api.example.com/webhooks/logs"

    # Filter by event type
    curl -H "Authorization: Bearer {token}" "https://api.example.com/webhooks/logs?event_type=user.created"

    # Filter by date range
    curl -H "Authorization: Bearer {token}" \\
         "https://api.example.com/webhooks/logs?start_date=2024-01-01T00:00:00Z&end_date=2024-12-31T23:59:59Z"

    # Search in payload
    curl -H "Authorization: Bearer {token}" "https://api.example.com/webhooks/logs?search=user@example.com"
    ```
    """
    # Validate limit
    if limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 1000"
        )

    # Start with all logs
    filtered_logs = webhook_logs_cache.copy()

    # Apply event_type filter
    if event_type:
        filtered_logs = [log for log in filtered_logs if log.get("event_type") == event_type]

    # Apply date range filters
    if start_date:
        try:
            datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            filtered_logs = [log for log in filtered_logs if log.get("timestamp", "") >= start_date]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
            )

    if end_date:
        try:
            datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            filtered_logs = [log for log in filtered_logs if log.get("timestamp", "") <= end_date]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO 8601 format (e.g., 2024-12-31T23:59:59Z)"
            )

    # Apply search filter (search in payload JSON string and event_id)
    if search:
        search_lower = search.lower()
        filtered_logs = [
            log for log in filtered_logs
            if search_lower in json.dumps(log.get("payload", {})).lower()
            or search_lower in log.get("id", "").lower()
            or search_lower in log.get("event_type", "").lower()
        ]

    # Apply limit
    filtered_logs = filtered_logs[:limit]

    # Convert to WebhookLog models
    result = [WebhookLog(**log) for log in filtered_logs]

    return result


# GET /events/export - Export event data for GDPR/CCPA compliance (protected endpoint)
@app.get("/events/export",
         tags=["Compliance"],
         summary="Export Event Data",
         response_description="Event data exported in requested format")
async def export_events(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    event_type: Optional[str] = None,
    format: str = "json",
    current_user: User = Depends(get_authenticated_user)
):
    """
    ## Export Event Data

    Exports all event data for the authenticated user in the requested format.
    This endpoint supports GDPR Article 20 (Right to Data Portability) and CCPA data access requirements.

    ### Authentication

    Requires JWT bearer token in Authorization header.

    ### Query Parameters

    - **start_date** (optional): ISO 8601 timestamp - Filter events created on or after this date
    - **end_date** (optional): ISO 8601 timestamp - Filter events created on or before this date
    - **event_type** (optional): Filter events by specific type (e.g., "user.created")
    - **format** (optional): Export format - "json" (default) or "csv"

    ### Response

    Returns a file download with appropriate Content-Type and Content-Disposition headers.

    ### Formats

    **JSON Format**: Returns an array of event objects with all fields
    **CSV Format**: Returns tabular data with columns: id, type, source, status, created_at, updated_at, payload (JSON string)

    ### Rate Limiting

    This endpoint is resource-intensive. For large datasets, consider:
    - Using date range filters to limit the scope
    - Requesting exports during off-peak hours
    - Implementing client-side retry logic with exponential backoff

    ### Performance Considerations

    - Large exports may take several seconds to complete
    - Results are streamed to minimize memory usage
    - Maximum 10,000 events per export (pagination recommended for larger datasets)

    ### Example Requests

    ```bash
    # Export all events as JSON
    curl -H "Authorization: Bearer {token}" "https://api.example.com/events/export"

    # Export events from specific date range as CSV
    curl -H "Authorization: Bearer {token}" \\
         "https://api.example.com/events/export?start_date=2024-01-01T00:00:00Z&end_date=2024-12-31T23:59:59Z&format=csv"

    # Export specific event type
    curl -H "Authorization: Bearer {token}" \\
         "https://api.example.com/events/export?event_type=user.created"
    ```
    """
    # Validate format parameter
    if format not in ["json", "csv"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid format. Supported formats: json, csv"
        )

    # Validate and parse date parameters
    filter_expression = None

    if start_date:
        try:
            datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if filter_expression is None:
                filter_expression = Attr('created_at').gte(start_date)
            else:
                filter_expression = filter_expression & Attr('created_at').gte(start_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO 8601 format (e.g., 2024-01-01T00:00:00Z)"
            )

    if end_date:
        try:
            datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            if filter_expression is None:
                filter_expression = Attr('created_at').lte(end_date)
            else:
                filter_expression = filter_expression & Attr('created_at').lte(end_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO 8601 format (e.g., 2024-12-31T23:59:59Z)"
            )

    if event_type:
        if filter_expression is None:
            filter_expression = Attr('type').eq(event_type)
        else:
            filter_expression = filter_expression & Attr('type').eq(event_type)

    try:
        # Scan DynamoDB table with filters and pagination
        # Note: Using scan() instead of query() since we're filtering across all events
        # For production with large datasets, consider using query() with GSI on user_id
        events = []
        scan_kwargs = {
            'Limit': 10000  # Maximum events per export
        }

        if filter_expression is not None:
            scan_kwargs['FilterExpression'] = filter_expression

        # Paginate through results
        last_evaluated_key = None
        while True:
            if last_evaluated_key:
                scan_kwargs['ExclusiveStartKey'] = last_evaluated_key

            response = table.scan(**scan_kwargs)
            events.extend(response.get('Items', []))

            # Check if we've hit the limit or no more results
            if len(events) >= 10000 or 'LastEvaluatedKey' not in response:
                break

            last_evaluated_key = response['LastEvaluatedKey']

        # Sort events by created_at (descending)
        events.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        # Limit to 10,000 events
        events = events[:10000]

        # Generate appropriate response based on format
        if format == "json":
            # JSON export
            # Convert Decimal types to float for JSON serialization
            def decimal_default(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                raise TypeError

            json_data = json.dumps(events, default=decimal_default, indent=2)

            # Create streaming response
            return StreamingResponse(
                iter([json_data]),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=events_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
                    "X-Total-Events": str(len(events))
                }
            )

        elif format == "csv":
            # CSV export
            output = io.StringIO()

            # Define CSV columns
            fieldnames = ['id', 'type', 'source', 'status', 'created_at', 'updated_at', 'payload']
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')

            # Always write header
            writer.writeheader()

            # Write data rows if events exist
            if events:
                # Helper function to convert Decimal to float
                def decimal_default(obj):
                    if isinstance(obj, Decimal):
                        return float(obj)
                    raise TypeError

                for event in events:
                    # Convert payload dict to JSON string for CSV
                    row = {
                        'id': event.get('id', ''),
                        'type': event.get('type', ''),
                        'source': event.get('source', ''),
                        'status': event.get('status', ''),
                        'created_at': event.get('created_at', ''),
                        'updated_at': event.get('updated_at', ''),
                        'payload': json.dumps(event.get('payload', {}), default=decimal_default)
                    }
                    writer.writerow(row)

            csv_data = output.getvalue()
            output.close()

            # Create streaming response
            return StreamingResponse(
                iter([csv_data]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=events_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
                    "X-Total-Events": str(len(events))
                }
            )

    except Exception as e:
        print(f"[EXPORT] Error exporting events: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export events: {str(e)}"
        )


# Error handlers (optional custom error handling)
# Note: FastAPI handles HTTPException correctly by default
# These handlers only catch non-HTTPException errors
# @app.exception_handler(404)
# async def not_found_handler(request, exc):
#     return JSONResponse(
#         status_code=404,
#         content={"error": "Not found", "path": str(request.url)}
#     )

# @app.exception_handler(500)
# async def internal_error_handler(request, exc):
#     return JSONResponse(
#         status_code=500,
#         content={"error": "Internal server error"}
#     )

# Lambda handler using Mangum
from mangum import Mangum
handler = Mangum(app, lifespan="off")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
