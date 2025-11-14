"""
Zapier Triggers API - Event Dispatcher Service
Polls events from /inbox and dispatches them to configured webhook URLs
Implements retry logic with exponential backoff
"""
import os
import json
import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal

import httpx
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# AWS X-Ray instrumentation
from aws_xray_sdk.core import xray_recorder, patch_all

# Patch all AWS SDK calls for automatic tracing
patch_all()

# Environment configuration
API_BASE_URL = os.environ.get('API_BASE_URL')
SECRET_ARN = os.environ.get('SECRET_ARN')
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-2')
MAX_EVENTS_PER_RUN = int(os.environ.get('MAX_EVENTS_PER_RUN', '100'))

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1
MAX_BACKOFF_SECONDS = 60

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE_NAME)
secrets_client = boto3.client('secretsmanager', region_name=AWS_REGION)
cloudwatch_client = boto3.client('cloudwatch', region_name=AWS_REGION)

# CloudWatch namespace
CLOUDWATCH_NAMESPACE = 'ZapierTriggersAPI/Dispatcher'

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
        Exception: If secret retrieval fails
    """
    if secret_id in _secrets_cache:
        return _secrets_cache[secret_id]

    try:
        response = secrets_client.get_secret_value(SecretId=secret_id)

        if 'SecretString' in response:
            secret_data = json.loads(response['SecretString'])
        else:
            secret_data = response['SecretBinary']

        _secrets_cache[secret_id] = secret_data
        return secret_data

    except ClientError as e:
        error_code = e.response['Error']['Code']
        raise Exception(f"Failed to retrieve secret {secret_id}: {error_code}")
    except Exception as e:
        raise Exception(f"Unexpected error retrieving secret: {str(e)}")


def get_jwt_token() -> str:
    """
    Authenticate with the API and get a JWT token.

    Returns:
        JWT access token

    Raises:
        Exception: If authentication fails
    """
    secrets = get_secret(SECRET_ARN)
    api_key = secrets.get('zapier_api_key')

    if not api_key:
        raise Exception("API key not found in secrets")

    # Authenticate to get JWT token
    token_url = f"{API_BASE_URL}/token"

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            token_url,
            data={
                'username': 'api',
                'password': api_key
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        if response.status_code != 200:
            raise Exception(f"Authentication failed: {response.status_code} - {response.text}")

        token_data = response.json()
        return token_data['access_token']


async def fetch_pending_events(token: str) -> List[Dict[str, Any]]:
    """
    Fetch pending events from the /inbox endpoint.

    Args:
        token: JWT access token

    Returns:
        List of pending events

    Raises:
        Exception: If fetching events fails
    """
    inbox_url = f"{API_BASE_URL}/inbox"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            inbox_url,
            headers={'Authorization': f'Bearer {token}'}
        )

        if response.status_code != 200:
            raise Exception(f"Failed to fetch inbox: {response.status_code} - {response.text}")

        return response.json()


async def deliver_event_with_retry(
    event: Dict[str, Any],
    webhook_url: str,
    max_retries: int = MAX_RETRIES
) -> Dict[str, Any]:
    """
    Deliver an event to a webhook URL with exponential backoff retry logic.

    Args:
        event: The event data to deliver
        webhook_url: The destination webhook URL
        max_retries: Maximum number of retry attempts

    Returns:
        Dict with delivery status and metadata
    """
    event_id = event['id']
    attempt = 0
    backoff = INITIAL_BACKOFF_SECONDS
    last_error = None

    async with httpx.AsyncClient(timeout=30.0) as client:
        while attempt < max_retries:
            attempt += 1

            try:
                print(f"Delivering event {event_id} to {webhook_url} (attempt {attempt}/{max_retries})")

                # Send event to webhook
                response = await client.post(
                    webhook_url,
                    json=event,
                    headers={'Content-Type': 'application/json'}
                )

                # Check if delivery was successful
                if response.status_code in (200, 201, 202, 204):
                    print(f"Successfully delivered event {event_id} on attempt {attempt}")

                    return {
                        'success': True,
                        'event_id': event_id,
                        'attempts': attempt,
                        'status_code': response.status_code,
                        'response_time_ms': response.elapsed.total_seconds() * 1000
                    }

                # Non-retryable error (4xx except 429)
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    print(f"Non-retryable error for event {event_id}: {response.status_code}")

                    return {
                        'success': False,
                        'event_id': event_id,
                        'attempts': attempt,
                        'error': f"HTTP {response.status_code}",
                        'retryable': False
                    }

                # Retryable error (5xx or 429)
                last_error = f"HTTP {response.status_code}"
                print(f"Retryable error for event {event_id}: {response.status_code}")

            except httpx.TimeoutException as e:
                last_error = f"Timeout: {str(e)}"
                print(f"Timeout delivering event {event_id}: {str(e)}")

            except httpx.RequestError as e:
                last_error = f"Request error: {str(e)}"
                print(f"Request error delivering event {event_id}: {str(e)}")

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                print(f"Unexpected error delivering event {event_id}: {str(e)}")

            # If we haven't returned yet, we need to retry
            if attempt < max_retries:
                # Calculate exponential backoff with jitter
                sleep_time = min(backoff, MAX_BACKOFF_SECONDS)
                print(f"Retrying event {event_id} in {sleep_time}s...")
                await asyncio.sleep(sleep_time)
                backoff *= 2  # Exponential backoff

    # All retries exhausted
    print(f"Failed to deliver event {event_id} after {max_retries} attempts")

    return {
        'success': False,
        'event_id': event_id,
        'attempts': max_retries,
        'error': last_error,
        'retryable': True
    }


async def update_event_delivery_status(
    event_id: str,
    created_at: str,
    attempts: int,
    success: bool,
    error_message: Optional[str] = None
):
    """
    Update event delivery tracking fields in DynamoDB (Task 22.4).

    Args:
        event_id: The event ID
        created_at: The event creation timestamp (sort key)
        attempts: Number of delivery attempts
        success: Whether delivery was successful
        error_message: Error message if delivery failed
    """
    try:
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Build update expression based on success/failure
        if success:
            # On success, these fields are updated by the API's ack endpoint
            # We just update the attempt counter here
            table.update_item(
                Key={
                    'id': event_id,
                    'created_at': created_at
                },
                UpdateExpression="SET delivery_attempts = :attempts, last_delivery_attempt = :last_attempt",
                ExpressionAttributeValues={
                    ':attempts': attempts,
                    ':last_attempt': timestamp
                }
            )
        else:
            # On failure, update all tracking fields including error message
            table.update_item(
                Key={
                    'id': event_id,
                    'created_at': created_at
                },
                UpdateExpression="SET delivery_attempts = :attempts, last_delivery_attempt = :last_attempt, error_message = :error, #status = :status",
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':attempts': attempts,
                    ':last_attempt': timestamp,
                    ':error': error_message or 'Unknown error',
                    ':status': 'failed'
                }
            )

        print(f"Updated delivery status for event {event_id}: attempts={attempts}, success={success}")

    except Exception as e:
        print(f"Failed to update delivery status for event {event_id}: {str(e)}")


async def acknowledge_event(event_id: str, token: str) -> bool:
    """
    Acknowledge successful event delivery via the /inbox/{id}/ack endpoint.

    Args:
        event_id: The event ID to acknowledge
        token: JWT access token

    Returns:
        True if acknowledgment was successful, False otherwise
    """
    ack_url = f"{API_BASE_URL}/inbox/{event_id}/ack"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                ack_url,
                headers={'Authorization': f'Bearer {token}'}
            )

            if response.status_code in (200, 201, 204):
                print(f"Successfully acknowledged event {event_id}")
                return True
            else:
                print(f"Failed to acknowledge event {event_id}: {response.status_code} - {response.text}")
                return False

    except Exception as e:
        print(f"Error acknowledging event {event_id}: {str(e)}")
        return False


def publish_metrics(metrics: Dict[str, Any]):
    """
    Publish custom metrics to CloudWatch.

    Args:
        metrics: Dictionary containing metric data
    """
    try:
        metric_data = []
        timestamp = datetime.utcnow()

        # Total events processed
        if 'total_events' in metrics:
            metric_data.append({
                'MetricName': 'EventsProcessed',
                'Value': metrics['total_events'],
                'Unit': 'Count',
                'Timestamp': timestamp
            })

        # Successful deliveries
        if 'successful_deliveries' in metrics:
            metric_data.append({
                'MetricName': 'SuccessfulDeliveries',
                'Value': metrics['successful_deliveries'],
                'Unit': 'Count',
                'Timestamp': timestamp
            })

        # Failed deliveries (Task 22.4)
        if 'failed_deliveries' in metrics:
            metric_data.append({
                'MetricName': 'DeliveryFailures',
                'Value': metrics['failed_deliveries'],
                'Unit': 'Count',
                'Timestamp': timestamp
            })

        # Average delivery time
        if 'avg_delivery_time_ms' in metrics:
            metric_data.append({
                'MetricName': 'DispatcherDeliveryLatency',
                'Value': metrics['avg_delivery_time_ms'],
                'Unit': 'Milliseconds',
                'Timestamp': timestamp
            })

        # Total retry attempts (Task 22.4)
        if 'total_retries' in metrics:
            metric_data.append({
                'MetricName': 'RetryCount',
                'Value': metrics['total_retries'],
                'Unit': 'Count',
                'Timestamp': timestamp
            })

        if metric_data:
            cloudwatch_client.put_metric_data(
                Namespace=CLOUDWATCH_NAMESPACE,
                MetricData=metric_data
            )
            print(f"Published {len(metric_data)} metrics to CloudWatch")

    except Exception as e:
        print(f"Failed to publish metrics: {str(e)}")


async def process_events():
    """
    Main event processing loop.
    Fetches pending events, delivers them to webhooks, and acknowledges successful deliveries.

    Returns:
        Dict with processing statistics
    """
    start_time = time.time()

    # Get secrets for webhook URL
    secrets = get_secret(SECRET_ARN)
    webhook_url = secrets.get('zapier_webhook_url')

    if not webhook_url:
        raise Exception("Webhook URL not configured in secrets")

    # Authenticate and get JWT token
    token = get_jwt_token()

    # Fetch pending events
    events = await fetch_pending_events(token)

    if not events:
        print("No pending events to process")
        return {
            'total_events': 0,
            'successful_deliveries': 0,
            'failed_deliveries': 0,
            'processing_time_seconds': time.time() - start_time
        }

    # Limit the number of events per run
    events_to_process = events[:MAX_EVENTS_PER_RUN]
    print(f"Processing {len(events_to_process)} events")

    # Process events concurrently
    delivery_tasks = [
        deliver_event_with_retry(event, webhook_url)
        for event in events_to_process
    ]

    delivery_results = await asyncio.gather(*delivery_tasks)

    # Update DynamoDB delivery status for all events (Task 22.4)
    update_tasks = []
    for i, result in enumerate(delivery_results):
        event = events_to_process[i]
        update_tasks.append(
            update_event_delivery_status(
                event_id=result['event_id'],
                created_at=event['created_at'],
                attempts=result['attempts'],
                success=result['success'],
                error_message=result.get('error')
            )
        )

    await asyncio.gather(*update_tasks)

    # Acknowledge successful deliveries
    successful_events = [
        result for result in delivery_results
        if result['success']
    ]

    ack_tasks = [
        acknowledge_event(result['event_id'], token)
        for result in successful_events
    ]

    ack_results = await asyncio.gather(*ack_tasks)

    # Calculate statistics
    total_events = len(events_to_process)
    successful_deliveries = len(successful_events)
    failed_deliveries = total_events - successful_deliveries
    total_retries = sum(result['attempts'] - 1 for result in delivery_results)

    # Calculate average delivery time for successful deliveries
    delivery_times = [
        result['response_time_ms']
        for result in delivery_results
        if result['success'] and 'response_time_ms' in result
    ]
    avg_delivery_time_ms = sum(delivery_times) / len(delivery_times) if delivery_times else 0

    processing_time_seconds = time.time() - start_time

    # Prepare metrics
    metrics = {
        'total_events': total_events,
        'successful_deliveries': successful_deliveries,
        'failed_deliveries': failed_deliveries,
        'total_retries': total_retries,
        'avg_delivery_time_ms': avg_delivery_time_ms
    }

    # Publish metrics to CloudWatch
    publish_metrics(metrics)

    # Log summary
    print(f"Processed {total_events} events in {processing_time_seconds:.2f}s")
    print(f"Successful: {successful_deliveries}, Failed: {failed_deliveries}, Retries: {total_retries}")

    return {
        **metrics,
        'processing_time_seconds': processing_time_seconds,
        'acknowledged_count': sum(ack_results)
    }


def handler(event, context):
    """
    Lambda handler function.
    Triggered by EventBridge scheduler to process pending events.

    Args:
        event: Lambda event (from EventBridge)
        context: Lambda context

    Returns:
        Dict with processing results
    """
    print(f"Dispatcher Lambda invoked at {datetime.utcnow().isoformat()}")
    print(f"Event: {json.dumps(event)}")

    try:
        # Run async event processing
        result = asyncio.run(process_events())

        print(f"Dispatcher completed successfully")

        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }

    except Exception as e:
        error_message = f"Dispatcher failed: {str(e)}"
        print(error_message)

        # Publish error metric
        publish_metrics({'failed_deliveries': 1})

        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_message
            })
        }


# For local testing
if __name__ == "__main__":
    # Mock event and context for testing
    test_event = {}

    class MockContext:
        request_id = "test-request-id"
        function_name = "dispatcher-test"

    result = handler(test_event, MockContext())
    print(json.dumps(result, indent=2))
