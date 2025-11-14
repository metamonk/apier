# WebSocket Real-Time Updates - Context7 Research Summary

**Date:** 2025-11-14
**Task:** Task 27 - Implement Real-Time Updates with AWS API Gateway WebSocket API
**Research Source:** Context7 MCP Documentation

---

## Executive Summary

Comprehensive research completed for implementing WebSocket real-time updates using:
1. **AWS API Gateway WebSocket API** - For bidirectional client-server communication
2. **DynamoDB Streams** - For triggering on database changes
3. **AWS API Gateway Management API (boto3)** - For posting messages to connections

All documentation sourced from Context7 (latest AWS docs) to ensure current best practices and avoid deprecated patterns.

---

## 1. AWS API Gateway WebSocket API

### CDK Setup Pattern (Python)

```python
from aws_cdk.aws_apigatewayv2_integrations import WebSocketLambdaIntegration
import aws_cdk.aws_apigatewayv2 as apigwv2

# Create WebSocket API with lifecycle route handlers
web_socket_api = apigwv2.WebSocketApi(self, "EventsWebSocketApi",
    connect_route_options=apigwv2.WebSocketRouteOptions(
        integration=WebSocketLambdaIntegration("ConnectIntegration", connect_handler)
    ),
    disconnect_route_options=apigwv2.WebSocketRouteOptions(
        integration=WebSocketLambdaIntegration("DisconnectIntegration", disconnect_handler)
    ),
    default_route_options=apigwv2.WebSocketRouteOptions(
        integration=WebSocketLambdaIntegration("DefaultIntegration", default_handler)
    )
)

# Deploy to production stage with auto-deploy
apigwv2.WebSocketStage(self, "prod",
    web_socket_api=web_socket_api,
    stage_name="prod",
    auto_deploy=True
)
```

### Required Routes

| Route | Purpose | When Invoked |
|-------|---------|--------------|
| `$connect` | Connection lifecycle | Client initiates WebSocket upgrade |
| `$disconnect` | Cleanup | Client disconnects or connection times out |
| `$default` | Fallback | Messages that don't match custom routes |

### Connection Event Structure

```python
# $connect event payload
{
    "requestContext": {
        "connectionId": "AAAA1234=",           # Unique connection identifier
        "routeKey": "$connect",
        "domainName": "abcd1234.execute-api.us-east-1.amazonaws.com",
        "stage": "prod",
        "apiId": "abcd1234"
    },
    "queryStringParameters": {
        "user_id": "123",    # Optional: pass via query params
        "api_key": "xyz"     # For authentication
    }
}
```

### Lambda Handler Pattern ($connect)

```python
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
connections_table = dynamodb.Table('websocket-connections')

def lambda_handler(event, context):
    connection_id = event['requestContext']['connectionId']

    # Store connection in DynamoDB
    connections_table.put_item(
        Item={
            'connectionId': connection_id,
            'connectedAt': datetime.utcnow().isoformat(),
            'ttl': int(datetime.utcnow().timestamp()) + 86400  # 24 hour TTL
        }
    )

    return {'statusCode': 200}
```

---

## 2. DynamoDB Streams Configuration

### Enable Streams on Table (CDK)

```python
from aws_cdk import aws_dynamodb as dynamodb

events_table = dynamodb.Table(self, "EventsTable",
    partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
    sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
    stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,  # ← CRITICAL
    removal_policy=cdk.RemovalPolicy.DESTROY
)
```

### Stream View Types

| Type | Description | Use Case |
|------|-------------|----------|
| `NEW_AND_OLD_IMAGES` | Both new and old item | Audit trails, update detection |
| `NEW_IMAGE` | Only new item | Create/update notifications |
| `OLD_IMAGE` | Only old item | Delete notifications |
| `KEYS_ONLY` | Only key attributes | Minimal overhead |

### Lambda Event Source Mapping (CDK)

```python
from aws_cdk import aws_lambda_event_sources as event_sources

stream_handler = _lambda.Function(...)

stream_handler.add_event_source(
    event_sources.DynamoEventSource(events_table,
        starting_position=_lambda.StartingPosition.LATEST,  # Don't process historical
        batch_size=1,          # Process one at a time for real-time
        retry_attempts=3,
        filters=[              # Optional: filter specific events
            _lambda.FilterCriteria.filter({
                "eventName": _lambda.FilterRule.is_equal("INSERT")
            })
        ]
    )
)

# Grant read permissions
events_table.grant_stream_read(stream_handler)
```

### DynamoDB Stream Event Structure

```python
{
    "Records": [
        {
            "eventID": "c9fbe7d0261a5163fcb6940593e41797",
            "eventName": "INSERT",  # INSERT, MODIFY, or REMOVE
            "eventVersion": "1.1",
            "eventSource": "aws:dynamodb",
            "awsRegion": "us-east-1",
            "dynamodb": {
                "Keys": {
                    "PK": {"S": "EVENT#123"},
                    "SK": {"S": "METADATA"}
                },
                "NewImage": {
                    "event_id": {"S": "123"},
                    "name": {"S": "User Signup"},
                    "status": {"S": "active"}
                },
                "OldImage": {...},  # Only if NEW_AND_OLD_IMAGES
                "SequenceNumber": "700000000000888747038",
                "SizeBytes": 174,
                "StreamViewType": "NEW_AND_OLD_IMAGES"
            },
            "eventSourceARN": "arn:aws:dynamodb:us-east-1:111122223333:table/EventsTable/stream/..."
        }
    ]
}
```

### Processing Stream Records (Lambda Handler)

```python
import json

def lambda_handler(event, context):
    for record in event['Records']:
        event_name = record['eventName']  # INSERT, MODIFY, REMOVE

        if event_name in ['INSERT', 'MODIFY']:
            new_image = record['dynamodb']['NewImage']
            # Convert DynamoDB format to regular dict
            event_data = deserialize_dynamodb_item(new_image)
            # Broadcast to WebSocket connections
            broadcast_update(event_data)

        elif event_name == 'REMOVE':
            old_image = record['dynamodb']['OldImage']
            # Handle deletion notification

    return {'statusCode': 200}
```

---

## 3. API Gateway Management API (boto3)

### Client Initialization

**CRITICAL:** Endpoint URL must be constructed from event context, never hardcoded.

```python
import boto3

def get_management_api_client(event):
    """
    Construct API Gateway Management API client from event context.
    This is the ONLY correct way to initialize the client.
    """
    domain = event['requestContext']['domainName']
    stage = event['requestContext']['stage']
    endpoint_url = f"https://{domain}/{stage}"

    return boto3.client(
        'apigatewaymanagementapi',
        endpoint_url=endpoint_url
    )
```

### Posting Messages to Connections

```python
import json
from botocore.exceptions import ClientError

def send_to_connection(client, connection_id, message_data):
    """
    Send message to a single WebSocket connection.

    Returns:
        True if successful, False if connection is stale
    """
    try:
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message_data).encode('utf-8')  # Must be UTF-8 encoded
        )
        return True

    except ClientError as e:
        if e.response['Error']['Code'] == 'GoneException':
            # Connection is stale (410 Gone) - MUST clean up database
            print(f"Connection {connection_id} is stale, cleaning up...")
            delete_connection(connection_id)
            return False
        else:
            # Other errors (throttling, etc.)
            raise
```

### Broadcasting to All Connections

```python
import boto3
from boto3.dynamodb.conditions import Attr

def broadcast_message(domain, stage, connections_table_name, message_data):
    """
    Broadcast message to all active WebSocket connections.

    Args:
        domain: API Gateway domain from event context
        stage: API Gateway stage from event context
        connections_table_name: DynamoDB table with connection IDs
        message_data: Dictionary to send (will be JSON serialized)

    Returns:
        Dict with sent/failed counts
    """
    # Initialize API Gateway Management API client
    endpoint_url = f"https://{domain}/{stage}"
    apigw_client = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)

    # Get all active connections from DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(connections_table_name)
    response = table.scan()
    connections = response.get('Items', [])

    sent_count = 0
    stale_connections = []

    # Send to each connection
    for connection in connections:
        connection_id = connection['connectionId']

        try:
            apigw_client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(message_data).encode('utf-8')
            )
            sent_count += 1

        except ClientError as e:
            if e.response['Error']['Code'] == 'GoneException':
                # Mark stale connection for deletion
                stale_connections.append(connection_id)
            else:
                print(f"Error sending to {connection_id}: {e}")

    # Clean up stale connections
    for stale_id in stale_connections:
        table.delete_item(Key={'connectionId': stale_id})

    return {
        'sent': sent_count,
        'failed': len(stale_connections)
    }
```

### Required IAM Permissions

```python
from aws_cdk import aws_iam as iam

# For Lambda that posts to WebSocket connections
stream_handler.add_to_role_policy(
    iam.PolicyStatement(
        actions=['execute-api:ManageConnections'],
        resources=[
            f"arn:aws:execute-api:{region}:{account}:{api_id}/{stage}/POST/@connections/*"
        ]
    )
)
```

---

## 4. Best Practices & Common Pitfalls

### Connection Management

✅ **DO:**
- Store `connectionId` in DynamoDB on `$connect`
- Include `user_id` or filters for targeted broadcasts
- Clean up on `$disconnect`
- **Always** handle `GoneException` (410) for stale connections
- Use TTL on connections table for automatic cleanup

❌ **DON'T:**
- Hardcode WebSocket API endpoint URL
- Ignore `GoneException` - leads to stale connection accumulation
- Store sensitive data in connection table without encryption
- Skip IAM permission for `ManageConnections`

### DynamoDB Stream Processing

✅ **DO:**
- Use `LATEST` starting position for new deployments
- Set `batch_size=1` for real-time updates (or 10-100 for cost optimization)
- Filter events to reduce Lambda invocations
- Handle `MODIFY` events separately from `INSERT` if needed
- Monitor iterator age in CloudWatch

❌ **DON'T:**
- Use `TRIM_HORIZON` on large tables (high costs)
- Process all event types if you only need specific ones
- Forget to grant stream read permissions

### API Gateway Management API

✅ **DO:**
- Construct endpoint URL from `event.requestContext`
- JSON serialize and UTF-8 encode all messages
- Handle `GoneException` immediately and clean database
- Implement retry logic with exponential backoff
- Monitor CloudWatch for error rates

❌ **DON'T:**
- Exceed 128 KB message size (causes silent failures)
- Send raw bytes (must be UTF-8 encoded)
- Ignore rate limits (600 requests/second per connection)
- Skip error handling for individual connections

### Error Handling Patterns

```python
# Good: Graceful error handling
try:
    apigw_client.post_to_connection(
        ConnectionId=connection_id,
        Data=message_data
    )
except ClientError as e:
    if e.response['Error']['Code'] == 'GoneException':
        cleanup_stale_connection(connection_id)
    else:
        log_error_and_continue(e)

# Bad: Blocking error propagation
apigw_client.post_to_connection(...)  # Unhandled exceptions break the loop
```

---

## 5. Testing Strategies

### WebSocket Client Testing with wscat

```bash
# Install wscat
npm install -g wscat

# Connect to WebSocket API
wscat -c wss://abcd1234.execute-api.us-east-1.amazonaws.com/prod

# Test with query parameters (auth)
wscat -c 'wss://api.example.com/prod?user_id=123&api_key=xyz'

# Send test message
> {"action": "sendmessage", "message": "Hello"}

# Disconnect
[Ctrl+C]
```

### Integration Testing Checklist

- [ ] Test `$connect` route stores connectionId
- [ ] Test `$disconnect` route removes connectionId
- [ ] Trigger DynamoDB change and verify Lambda invocation
- [ ] Verify message delivery to connected client
- [ ] Test stale connection cleanup (disconnect client, trigger update)
- [ ] Test multiple simultaneous connections
- [ ] Monitor CloudWatch Logs for errors
- [ ] Check DynamoDB connections table for correct data

### Load Testing Considerations

- Test with 100+ concurrent connections
- Measure Lambda cold start impact
- Monitor API Gateway throttling
- Track DynamoDB read/write capacity usage
- Measure end-to-end latency (DynamoDB change → client notification)

---

## 6. Implementation Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client (Browser)                         │
│                      WebSocket Connection                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│              AWS API Gateway WebSocket API                       │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ $connect │  │ $disconnect  │  │   $default   │              │
│  └────┬─────┘  └──────┬───────┘  └──────┬───────┘              │
└───────┼────────────────┼──────────────────┼──────────────────────┘
        │                │                  │
        ↓                ↓                  ↓
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ Connect Lambda│ │Disconnect     │ │Default Lambda │
│  - Store ID   │ │Lambda         │ │  - Heartbeat  │
│  in DynamoDB  │ │  - Remove ID  │ │  - Responses  │
└───────────────┘ └───────────────┘ └───────────────┘
        │                │
        ↓                ↓
┌─────────────────────────────────────────────────┐
│         DynamoDB Connections Table              │
│  PK: connectionId                               │
│  Attributes: userId, connectedAt, ttl           │
└─────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────┐
│         DynamoDB Events Table                   │
│  PK: EVENT#{id}                                 │
│  Stream: NEW_AND_OLD_IMAGES                     │
└────────────────┬────────────────────────────────┘
                 │ (Triggers on INSERT/MODIFY/REMOVE)
                 ↓
┌─────────────────────────────────────────────────┐
│       Broadcaster Lambda Function               │
│  1. Parse stream record                         │
│  2. Query connections table                     │
│  3. Post to each connectionId                   │
│  4. Handle GoneException → cleanup              │
└────────────────┬────────────────────────────────┘
                 │
                 └──→ API Gateway Management API
                        post_to_connection()
```

### Connections Table Schema

```python
{
    "connectionId": "AAAA1234=",    # Partition key (String)
    "user_id": "user123",           # Optional: for filtered broadcasts
    "connected_at": "2025-11-14T10:30:00Z",  # ISO timestamp
    "ttl": 1731590400              # Unix timestamp for auto-cleanup
}
```

### Message Format (Client → Server → Client)

```json
{
    "type": "event_update",
    "action": "created",
    "data": {
        "id": "event-123",
        "type": "user.signup",
        "status": "pending",
        "timestamp": "2025-11-14T10:30:00Z"
    }
}
```

---

## 7. Key Takeaways from Context7 Research

1. **Endpoint URL Construction:** CRITICAL - Must use `event.requestContext` to build `https://{domain}/{stage}`. Hardcoding will fail.

2. **GoneException Handling:** ESSENTIAL - Always catch 410 errors and clean up the database. Ignoring leads to stale connection accumulation.

3. **Stream Configuration:** Use `NEW_AND_OLD_IMAGES` for audit/update detection. Set `batch_size=1` for real-time, use `LATEST` starting position.

4. **Message Encoding:** Must be JSON serialized AND UTF-8 encoded. Max size 128 KB.

5. **IAM Permissions:** `execute-api:ManageConnections` is required for posting to connections.

6. **Testing Tool:** `wscat` is the standard tool for WebSocket testing.

7. **Rate Limits:** 600 requests/second per connection. Implement batching for large broadcasts.

8. **Connection Lifecycle:** Store on $connect, remove on $disconnect, clean up stale on GoneException.

9. **CDK Patterns:** Use `WebSocketLambdaIntegration` for Lambda handlers, `WebSocketStage` with `auto_deploy=True` for production.

10. **Monitoring:** Track iterator age, error rates, and GoneException rates in CloudWatch.

---

## Resources

- Context7 Documentation:
  - AWS API Gateway WebSocket API Developer Guide
  - AWS DynamoDB Developer Guide (Streams)
  - Boto3 Documentation (apigatewaymanagementapi)
  - AWS CDK API Reference (Python)

- Testing Tools:
  - wscat: `npm install -g wscat`
  - AWS CLI: `aws apigatewayv2` commands
  - AWS Console: API Gateway, DynamoDB, Lambda, CloudWatch

---

**Research completed:** 2025-11-14
**Updated Task 27:** All subtasks updated with detailed implementation notes
**Ready for implementation:** Yes, comprehensive patterns and examples provided
