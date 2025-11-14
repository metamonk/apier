"""
Unit tests for last-attempt-index GSI (Task 22.2).
Tests time-based queries using the new Global Secondary Index.
"""
import json
import os
import pytest
from moto import mock_aws
import boto3
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key


# Set environment variables
os.environ['DYNAMODB_TABLE_NAME'] = 'test-zapier-triggers-events'
os.environ['SECRET_ARN'] = 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret'
os.environ['AWS_REGION'] = 'us-east-1'


@pytest.fixture(scope='function')
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture(scope='function')
def dynamodb_table(aws_credentials):
    """Create a mock DynamoDB table with both GSIs."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

        # Create table with both GSIs
        table = dynamodb.create_table(
            TableName='test-zapier-triggers-events',
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'},
                {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'},
                {'AttributeName': 'created_at', 'AttributeType': 'S'},
                {'AttributeName': 'status', 'AttributeType': 'S'},
                {'AttributeName': 'last_delivery_attempt', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'status-index',
                    'KeySchema': [
                        {'AttributeName': 'status', 'KeyType': 'HASH'},
                        {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
                {
                    'IndexName': 'last-attempt-index',
                    'KeySchema': [
                        {'AttributeName': 'status', 'KeyType': 'HASH'},
                        {'AttributeName': 'last_delivery_attempt', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )

        # Wait for table to be created
        table.meta.client.get_waiter('table_exists').wait(TableName='test-zapier-triggers-events')

        yield table


class TestLastAttemptGSI:
    """Tests for last-attempt-index GSI functionality."""

    def test_gsi_sparse_index_behavior(self, dynamodb_table):
        """Test that GSI is sparse - only indexes events with last_delivery_attempt set."""
        # Create events: some with last_delivery_attempt, some without
        base_time = datetime.utcnow()

        # Event 1: Delivered (has last_delivery_attempt)
        event1 = {
            "id": "event-1",
            "type": "test.event",
            "source": "test",
            "payload": {"data": "test1"},
            "status": "delivered",
            "created_at": base_time.isoformat() + "Z",
            "updated_at": base_time.isoformat() + "Z",
            "last_delivery_attempt": (base_time + timedelta(seconds=10)).isoformat() + "Z",
            "delivery_attempts": 1,
            "ttl": int((base_time + timedelta(days=90)).timestamp())
        }

        # Event 2: Pending (no last_delivery_attempt)
        event2 = {
            "id": "event-2",
            "type": "test.event",
            "source": "test",
            "payload": {"data": "test2"},
            "status": "pending",
            "created_at": (base_time + timedelta(seconds=5)).isoformat() + "Z",
            "updated_at": (base_time + timedelta(seconds=5)).isoformat() + "Z",
            "delivery_attempts": 0,
            "ttl": int((base_time + timedelta(days=90)).timestamp())
        }

        # Event 3: Failed (has last_delivery_attempt)
        event3 = {
            "id": "event-3",
            "type": "test.event",
            "source": "test",
            "payload": {"data": "test3"},
            "status": "failed",
            "created_at": (base_time + timedelta(seconds=15)).isoformat() + "Z",
            "updated_at": (base_time + timedelta(seconds=15)).isoformat() + "Z",
            "last_delivery_attempt": (base_time + timedelta(seconds=20)).isoformat() + "Z",
            "delivery_attempts": 3,
            "error_message": "Connection timeout",
            "ttl": int((base_time + timedelta(days=90)).timestamp())
        }

        dynamodb_table.put_item(Item=event1)
        dynamodb_table.put_item(Item=event2)
        dynamodb_table.put_item(Item=event3)

        # Query last-attempt-index for delivered events
        response = dynamodb_table.query(
            IndexName='last-attempt-index',
            KeyConditionExpression=Key('status').eq('delivered')
        )

        # Should only return event1 (has last_delivery_attempt)
        assert len(response['Items']) == 1
        assert response['Items'][0]['id'] == 'event-1'

        # Query for failed events
        response = dynamodb_table.query(
            IndexName='last-attempt-index',
            KeyConditionExpression=Key('status').eq('failed')
        )

        # Should only return event3
        assert len(response['Items']) == 1
        assert response['Items'][0]['id'] == 'event-3'

        # Query for pending events - should return nothing (pending has no last_delivery_attempt)
        response = dynamodb_table.query(
            IndexName='last-attempt-index',
            KeyConditionExpression=Key('status').eq('pending')
        )

        assert len(response['Items']) == 0

    def test_gsi_time_range_queries(self, dynamodb_table):
        """Test time-range queries using last_delivery_attempt."""
        base_time = datetime.utcnow()

        # Create multiple delivered events across different times
        events = []
        for i in range(5):
            event_time = base_time + timedelta(minutes=i*10)
            delivery_time = event_time + timedelta(seconds=30)

            event = {
                "id": f"event-{i}",
                "type": "test.event",
                "source": "test",
                "payload": {"index": i},
                "status": "delivered",
                "created_at": event_time.isoformat() + "Z",
                "updated_at": delivery_time.isoformat() + "Z",
                "last_delivery_attempt": delivery_time.isoformat() + "Z",
                "delivery_attempts": 1,
                "delivery_latency_ms": 30000,
                "ttl": int((base_time + timedelta(days=90)).timestamp())
            }
            events.append(event)
            dynamodb_table.put_item(Item=event)

        # Query for delivered events in a specific time range
        # Events 1, 2, 3 should fall in this range (10-31 minutes from base_time)
        # Note: Event 3 is delivered at 30min + 30sec, so range_end must be after that
        range_start = (base_time + timedelta(minutes=10)).isoformat() + "Z"
        range_end = (base_time + timedelta(minutes=31)).isoformat() + "Z"

        response = dynamodb_table.query(
            IndexName='last-attempt-index',
            KeyConditionExpression=Key('status').eq('delivered') &
                                   Key('last_delivery_attempt').between(range_start, range_end)
        )

        # Should return 3 events (indices 1, 2, 3)
        assert len(response['Items']) == 3
        returned_indices = sorted([item['payload']['index'] for item in response['Items']])
        assert returned_indices == [1, 2, 3]

    def test_gsi_retry_logic_query(self, dynamodb_table):
        """Test querying failed events for retry logic."""
        base_time = datetime.utcnow()

        # Create failed events with different last attempt times
        failed_events = []
        for i in range(4):
            # Events failed at different times (oldest to newest)
            attempt_time = base_time - timedelta(hours=4-i)

            event = {
                "id": f"failed-event-{i}",
                "type": "test.event",
                "source": "test",
                "payload": {"index": i},
                "status": "failed",
                "created_at": (attempt_time - timedelta(minutes=5)).isoformat() + "Z",
                "updated_at": attempt_time.isoformat() + "Z",
                "last_delivery_attempt": attempt_time.isoformat() + "Z",
                "delivery_attempts": i + 1,
                "error_message": f"Error {i}",
                "ttl": int((base_time + timedelta(days=90)).timestamp())
            }
            failed_events.append(event)
            dynamodb_table.put_item(Item=event)

        # Query failed events sorted by last attempt time (ascending - oldest first)
        response = dynamodb_table.query(
            IndexName='last-attempt-index',
            KeyConditionExpression=Key('status').eq('failed'),
            ScanIndexForward=True  # Ascending order
        )

        assert len(response['Items']) == 4

        # Verify events are ordered by last_delivery_attempt (oldest first)
        for i in range(4):
            assert response['Items'][i]['id'] == f'failed-event-{i}'

        # Now query for events that haven't been attempted in the last 2 hours (for retry)
        cutoff_time = base_time - timedelta(hours=2)
        cutoff_iso = cutoff_time.isoformat() + "Z"

        response = dynamodb_table.query(
            IndexName='last-attempt-index',
            KeyConditionExpression=Key('status').eq('failed') &
                                   Key('last_delivery_attempt').lt(cutoff_iso)
        )

        # Should return first 2 events (attempted 4 and 3 hours ago)
        assert len(response['Items']) == 2
        assert response['Items'][0]['id'] == 'failed-event-0'
        assert response['Items'][1]['id'] == 'failed-event-1'

    def test_gsi_delivery_throughput_metrics(self, dynamodb_table):
        """Test calculating delivery throughput using the GSI."""
        base_time = datetime.utcnow()

        # Create events delivered in the last hour
        events_last_hour = 5
        for i in range(events_last_hour):
            delivery_time = base_time - timedelta(minutes=i*10)
            event = {
                "id": f"recent-{i}",
                "type": "test.event",
                "source": "test",
                "payload": {},
                "status": "delivered",
                "created_at": (delivery_time - timedelta(seconds=30)).isoformat() + "Z",
                "updated_at": delivery_time.isoformat() + "Z",
                "last_delivery_attempt": delivery_time.isoformat() + "Z",
                "delivery_attempts": 1,
                "ttl": int((base_time + timedelta(days=90)).timestamp())
            }
            dynamodb_table.put_item(Item=event)

        # Create events delivered more than an hour ago
        events_older = 3
        for i in range(events_older):
            delivery_time = base_time - timedelta(hours=2+i)
            event = {
                "id": f"old-{i}",
                "type": "test.event",
                "source": "test",
                "payload": {},
                "status": "delivered",
                "created_at": (delivery_time - timedelta(seconds=30)).isoformat() + "Z",
                "updated_at": delivery_time.isoformat() + "Z",
                "last_delivery_attempt": delivery_time.isoformat() + "Z",
                "delivery_attempts": 1,
                "ttl": int((base_time + timedelta(days=90)).timestamp())
            }
            dynamodb_table.put_item(Item=event)

        # Query for events delivered in the last hour
        one_hour_ago = (base_time - timedelta(hours=1)).isoformat() + "Z"

        response = dynamodb_table.query(
            IndexName='last-attempt-index',
            KeyConditionExpression=Key('status').eq('delivered') &
                                   Key('last_delivery_attempt').gte(one_hour_ago)
        )

        # Should return only the 5 recent events
        assert len(response['Items']) == events_last_hour

        # Calculate throughput (events per hour)
        events_delivered = len(response['Items'])
        throughput_per_hour = events_delivered  # Since we're looking at 1 hour

        assert throughput_per_hour == 5

    def test_gsi_supports_both_ascending_and_descending(self, dynamodb_table):
        """Test that GSI supports both sort orders."""
        base_time = datetime.utcnow()

        # Create 3 delivered events at different times
        for i in range(3):
            delivery_time = base_time + timedelta(minutes=i*5)
            event = {
                "id": f"sorted-{i}",
                "type": "test.event",
                "source": "test",
                "payload": {"order": i},
                "status": "delivered",
                "created_at": delivery_time.isoformat() + "Z",
                "updated_at": delivery_time.isoformat() + "Z",
                "last_delivery_attempt": delivery_time.isoformat() + "Z",
                "delivery_attempts": 1,
                "ttl": int((base_time + timedelta(days=90)).timestamp())
            }
            dynamodb_table.put_item(Item=event)

        # Query ascending (oldest first)
        response_asc = dynamodb_table.query(
            IndexName='last-attempt-index',
            KeyConditionExpression=Key('status').eq('delivered'),
            ScanIndexForward=True
        )

        assert len(response_asc['Items']) == 3
        assert [item['id'] for item in response_asc['Items']] == ['sorted-0', 'sorted-1', 'sorted-2']

        # Query descending (newest first)
        response_desc = dynamodb_table.query(
            IndexName='last-attempt-index',
            KeyConditionExpression=Key('status').eq('delivered'),
            ScanIndexForward=False
        )

        assert len(response_desc['Items']) == 3
        assert [item['id'] for item in response_desc['Items']] == ['sorted-2', 'sorted-1', 'sorted-0']
