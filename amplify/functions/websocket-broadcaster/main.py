"""
WebSocket Broadcaster Lambda
Processes DynamoDB Stream events and broadcasts updates to all connected WebSocket clients
"""
import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError

# AWS X-Ray instrumentation
from aws_xray_sdk.core import xray_recorder, patch_all

# Patch all AWS SDK calls for automatic tracing
patch_all()

# Environment configuration
CONNECTIONS_TABLE_NAME = os.environ.get('CONNECTIONS_TABLE_NAME')
WEBSOCKET_API_ENDPOINT = os.environ.get('WEBSOCKET_API_ENDPOINT')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-2')

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
connections_table = dynamodb.Table(CONNECTIONS_TABLE_NAME)

# API Gateway Management API client (for posting to WebSocket connections)
# Extract the endpoint properly (format: https://api-id.execute-api.region.amazonaws.com/stage)
apigw_management_client = boto3.client(
    'apigatewaymanagementapi',
    endpoint_url=WEBSOCKET_API_ENDPOINT.replace('wss://', 'https://'),
    region_name=AWS_REGION
)

# DynamoDB deserializer for Stream records
deserializer = TypeDeserializer()


def deserialize_dynamodb_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deserialize DynamoDB item from Stream format to Python dict

    Args:
        item: DynamoDB item in Stream format

    Returns:
        Deserialized Python dict
    """
    return {k: deserializer.deserialize(v) for k, v in item.items()}


def convert_decimals(obj: Any) -> Any:
    """
    Convert Decimal objects to float for JSON serialization

    Args:
        obj: Object to convert

    Returns:
        Converted object
    """
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    return obj


def extract_event_data(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract relevant event data from DynamoDB Stream record

    Args:
        record: DynamoDB Stream record

    Returns:
        Event data dict or None if extraction fails
    """
    try:
        event_name = record['eventName']  # INSERT, MODIFY, REMOVE
        dynamodb_data = record.get('dynamodb', {})

        # Get new image (for INSERT and MODIFY)
        new_image = dynamodb_data.get('NewImage')
        old_image = dynamodb_data.get('OldImage')

        if event_name == 'INSERT' and new_image:
            event_data = deserialize_dynamodb_item(new_image)
            return {
                'type': 'event_update',
                'action': 'created',
                'data': convert_decimals(event_data)
            }

        elif event_name == 'MODIFY' and new_image and old_image:
            event_data = deserialize_dynamodb_item(new_image)
            old_data = deserialize_dynamodb_item(old_image)

            # Check if status changed
            if event_data.get('status') != old_data.get('status'):
                return {
                    'type': 'event_update',
                    'action': 'updated',
                    'data': convert_decimals(event_data),
                    'previous_status': old_data.get('status')
                }

        elif event_name == 'REMOVE' and old_image:
            event_data = deserialize_dynamodb_item(old_image)
            return {
                'type': 'event_update',
                'action': 'deleted',
                'data': convert_decimals({
                    'id': event_data.get('id'),
                    'type': event_data.get('type')
                })
            }

        return None

    except Exception as e:
        print(f"Error extracting event data: {e}")
        return None


def get_all_connections() -> List[str]:
    """
    Retrieve all active connection IDs from DynamoDB

    Returns:
        List of connection IDs
    """
    try:
        response = connections_table.scan()
        connections = [item['connectionId'] for item in response.get('Items', [])]

        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = connections_table.scan(
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            connections.extend([item['connectionId'] for item in response.get('Items', [])])

        print(f"Found {len(connections)} active connections")
        return connections

    except ClientError as e:
        print(f"Error fetching connections: {e}")
        return []


def post_to_connection(connection_id: str, message: Dict[str, Any]) -> bool:
    """
    Post message to a specific WebSocket connection

    Args:
        connection_id: WebSocket connection ID
        message: Message data to send

    Returns:
        True if successful, False otherwise
    """
    try:
        apigw_management_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message).encode('utf-8')
        )
        return True

    except ClientError as e:
        error_code = e.response['Error']['Code']

        # Handle stale connections (410 Gone)
        if error_code == 'GoneException':
            print(f"Connection {connection_id} is stale (410 Gone), cleaning up")
            try:
                connections_table.delete_item(
                    Key={'connectionId': connection_id}
                )
            except Exception as cleanup_error:
                print(f"Error cleaning up stale connection: {cleanup_error}")
            return False

        else:
            print(f"Error posting to connection {connection_id}: {e}")
            return False

    except Exception as e:
        print(f"Unexpected error posting to connection {connection_id}: {e}")
        return False


async def broadcast_to_connections_async(connections: List[str], message: Dict[str, Any]) -> Dict[str, int]:
    """
    Broadcast message to all connections asynchronously

    Args:
        connections: List of connection IDs
        message: Message to broadcast

    Returns:
        Dict with success and failure counts
    """
    successful = 0
    failed = 0

    # Process connections in batches to avoid overwhelming the API
    batch_size = 10
    for i in range(0, len(connections), batch_size):
        batch = connections[i:i + batch_size]

        # Use ThreadPoolExecutor for concurrent posts (since boto3 is synchronous)
        loop = asyncio.get_event_loop()
        tasks = []

        for connection_id in batch:
            task = loop.run_in_executor(None, post_to_connection, connection_id, message)
            tasks.append(task)

        # Wait for all tasks in batch to complete
        results = await asyncio.gather(*tasks)

        successful += sum(1 for r in results if r)
        failed += sum(1 for r in results if not r)

    return {'successful': successful, 'failed': failed}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for DynamoDB Stream events

    Args:
        event: DynamoDB Stream event with records
        context: Lambda context object

    Returns:
        Response dict with processing summary
    """
    print(f"Processing {len(event.get('Records', []))} DynamoDB Stream records")

    processed_count = 0
    broadcast_count = 0

    for record in event.get('Records', []):
        try:
            # Extract event data from Stream record
            event_data = extract_event_data(record)

            if not event_data:
                print(f"Skipping record (no relevant data): {record['eventName']}")
                continue

            processed_count += 1

            # Get all active connections
            connections = get_all_connections()

            if not connections:
                print("No active connections, skipping broadcast")
                continue

            # Broadcast message to all connections
            print(f"Broadcasting {event_data['action']} event to {len(connections)} connections")

            # Use asyncio for concurrent broadcasting
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    broadcast_to_connections_async(connections, event_data)
                )
                print(f"Broadcast result: {result['successful']} successful, {result['failed']} failed")
                broadcast_count += result['successful']
            finally:
                loop.close()

        except Exception as e:
            print(f"Error processing record: {e}")
            continue

    print(f"Processed {processed_count} events, broadcasted to {broadcast_count} connections")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': processed_count,
            'broadcasted': broadcast_count
        })
    }
