"""
WebSocket Disconnect Handler
Handles WebSocket $disconnect events by removing connection IDs from DynamoDB
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
CONNECTIONS_TABLE_NAME = os.environ.get('CONNECTIONS_TABLE_NAME')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-2')

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
connections_table = dynamodb.Table(CONNECTIONS_TABLE_NAME)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for WebSocket $disconnect route

    Args:
        event: API Gateway WebSocket event containing connectionId
        context: Lambda context object

    Returns:
        Response dict with statusCode and body
    """
    try:
        # Extract connection ID from event context
        connection_id = event['requestContext']['connectionId']

        print(f"WebSocket disconnection: {connection_id}")

        # Delete connection from DynamoDB
        connections_table.delete_item(
            Key={
                'connectionId': connection_id
            }
        )

        print(f"Successfully removed connection: {connection_id}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Disconnected successfully',
                'connectionId': connection_id
            })
        }

    except ClientError as e:
        print(f"DynamoDB error: {e}")
        # Return success even if delete fails (idempotent operation)
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Disconnection processed',
                'error': str(e)
            })
        }

    except Exception as e:
        print(f"Unexpected error: {e}")
        # Return success to avoid blocking disconnection
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Disconnection processed',
                'error': str(e)
            })
        }
