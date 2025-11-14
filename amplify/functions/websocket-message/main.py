"""
WebSocket Message Handler
Handles incoming WebSocket messages including PING/PONG
"""
import os
import json
from typing import Dict, Any

import boto3
from botocore.exceptions import ClientError

# AWS X-Ray instrumentation
from aws_xray_sdk.core import xray_recorder, patch_all

# Patch all AWS SDK calls for automatic tracing
patch_all()

# Environment configuration
WEBSOCKET_API_ENDPOINT = os.environ.get('WEBSOCKET_API_ENDPOINT')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-2')

# API Gateway Management API client (for posting to WebSocket connections)
apigw_management_client = None


def get_management_client():
    """Lazy initialization of API Gateway Management client"""
    global apigw_management_client
    if apigw_management_client is None:
        endpoint = WEBSOCKET_API_ENDPOINT.replace('wss://', 'https://')
        apigw_management_client = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=endpoint,
            region_name=AWS_REGION
        )
    return apigw_management_client


def send_message(connection_id: str, message: Dict[str, Any]) -> bool:
    """
    Send message to a WebSocket connection

    Args:
        connection_id: WebSocket connection ID
        message: Message data to send

    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_management_client()
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message).encode('utf-8')
        )
        return True

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'GoneException':
            print(f"Connection {connection_id} is gone (410)")
        else:
            print(f"Error sending message: {e}")
        return False

    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for WebSocket messages

    Args:
        event: API Gateway WebSocket event
        context: Lambda context object

    Returns:
        Response dict with statusCode
    """
    try:
        connection_id = event['requestContext']['connectionId']
        route_key = event['requestContext'].get('routeKey', '$default')

        print(f"Message from {connection_id} on route {route_key}")

        # Parse message body if present
        body = event.get('body')
        if body:
            try:
                message = json.loads(body)
                message_type = message.get('type')

                print(f"Message type: {message_type}")

                # Handle PING messages
                if message_type == 'ping':
                    print(f"Responding to PING from {connection_id}")
                    send_message(connection_id, {
                        'type': 'pong',
                        'timestamp': message.get('timestamp')
                    })

                # Handle other message types as needed
                elif message_type in ['subscribe', 'unsubscribe']:
                    # Future: Handle subscription management
                    print(f"Subscription request: {message_type}")
                    send_message(connection_id, {
                        'type': 'ack',
                        'action': message_type
                    })

            except json.JSONDecodeError:
                print(f"Invalid JSON in message body: {body}")

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Message received'})
        }

    except Exception as e:
        print(f"Error handling message: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
