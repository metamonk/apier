"""
WebSocket Connect Handler
Handles WebSocket $connect events by storing connection IDs in DynamoDB
"""
import os
import json
import time
from typing import Dict, Any
from datetime import datetime, timedelta

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
    Lambda handler for WebSocket $connect route

    Args:
        event: API Gateway WebSocket event containing connectionId
        context: Lambda context object

    Returns:
        Response dict with statusCode and body
    """
    try:
        # Extract connection ID from event context
        connection_id = event['requestContext']['connectionId']

        print(f"New WebSocket connection: {connection_id}")

        # Calculate TTL (24 hours from now)
        ttl = int((datetime.now() + timedelta(hours=24)).timestamp())

        # Store connection in DynamoDB
        connections_table.put_item(
            Item={
                'connectionId': connection_id,
                'connectedAt': datetime.utcnow().isoformat(),
                'ttl': ttl,
            }
        )

        print(f"Successfully stored connection: {connection_id}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Connected successfully',
                'connectionId': connection_id
            })
        }

    except ClientError as e:
        print(f"DynamoDB error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Failed to store connection',
                'error': str(e)
            })
        }

    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Internal server error',
                'error': str(e)
            })
        }
