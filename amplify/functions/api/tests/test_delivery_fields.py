"""
Unit tests for delivery tracking fields (Task 22.1).
Tests that new fields (delivery_attempts, last_delivery_attempt,
delivery_latency_ms, error_message) are properly created and returned.
"""
import json
import os
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
import boto3
from datetime import datetime


# Set environment variables before importing the app
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
    """Create a mock DynamoDB table for testing."""
    with mock_aws():
        # Create DynamoDB resource
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

        # Create table
        table = dynamodb.create_table(
            TableName='test-zapier-triggers-events',
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'},
                {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'},
                {'AttributeName': 'created_at', 'AttributeType': 'S'},
                {'AttributeName': 'status', 'AttributeType': 'S'}
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


@pytest.fixture(scope='function')
def secrets_manager(aws_credentials):
    """Create a mock Secrets Manager secret for testing."""
    with mock_aws():
        client = boto3.client('secretsmanager', region_name='us-east-1')

        # Create secret
        client.create_secret(
            Name='test-secret',
            SecretString=json.dumps({
                'environment': 'test',
                'jwt_secret': 'test-jwt-secret-12345678901234',
                'zapier_api_key': 'test-api-key',
                'zapier_webhook_url': 'https://hooks.zapier.com/test'
            })
        )

        yield client


@pytest.fixture(scope='function')
def client(dynamodb_table, secrets_manager):
    """Create a test client with mocked AWS services."""
    # Import app after mocking is set up
    from main import app

    # Reset the secrets cache to force fresh retrieval
    import main
    main._secrets_cache.clear()

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope='function')
def auth_token(client):
    """Get an authentication token for protected endpoints."""
    response = client.post(
        "/token",
        data={"username": "api", "password": "test-api-key"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


class TestDeliveryTrackingFields:
    """Tests for new delivery tracking fields (Task 22.1)."""

    def test_event_creation_includes_delivery_fields(self, client, auth_token, dynamodb_table):
        """Test that newly created events include delivery tracking fields with default values."""
        event_data = {
            "type": "user.signup",
            "source": "web-app",
            "payload": {
                "user_id": "123",
                "email": "test@example.com"
            }
        }

        response = client.post(
            "/events",
            json=event_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 201
        data = response.json()
        event_id = data["id"]

        # Verify the event was stored in DynamoDB with the new fields
        from boto3.dynamodb.conditions import Key
        response = dynamodb_table.query(
            KeyConditionExpression=Key('id').eq(event_id),
            Limit=1
        )

        assert len(response['Items']) == 1
        item = response['Items'][0]

        # Verify new delivery tracking fields exist with default values
        assert 'delivery_attempts' in item
        assert item['delivery_attempts'] == 0
        assert 'last_delivery_attempt' in item
        assert item['last_delivery_attempt'] is None
        assert 'delivery_latency_ms' in item
        assert item['delivery_latency_ms'] is None
        assert 'error_message' in item
        assert item['error_message'] is None

    def test_inbox_returns_delivery_fields(self, client, auth_token):
        """Test that GET /inbox includes delivery tracking fields in response."""
        # Create a test event
        event_data = {
            "type": "test.event",
            "source": "test",
            "payload": {"test": "data"}
        }

        create_response = client.post(
            "/events",
            json=event_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert create_response.status_code == 201

        # Retrieve inbox
        inbox_response = client.get(
            "/inbox",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert inbox_response.status_code == 200
        events = inbox_response.json()
        assert len(events) > 0

        # Verify first event has delivery tracking fields
        event = events[0]
        assert 'delivery_attempts' in event
        assert event['delivery_attempts'] == 0
        assert 'last_delivery_attempt' in event
        assert event['last_delivery_attempt'] is None
        assert 'delivery_latency_ms' in event
        assert event['delivery_latency_ms'] is None
        assert 'error_message' in event
        assert event['error_message'] is None

    def test_delivery_fields_are_optional(self, client, auth_token, dynamodb_table):
        """Test that delivery fields are optional and handle missing values gracefully."""
        # Manually create an event without the new fields (simulating old data)
        from datetime import datetime, timedelta
        timestamp = datetime.utcnow().isoformat() + "Z"
        ttl_timestamp = int((datetime.utcnow() + timedelta(days=90)).timestamp())

        old_event = {
            "id": "test-old-event-123",
            "type": "legacy.event",
            "source": "legacy-system",
            "payload": {"legacy": "data"},
            "status": "pending",
            "created_at": timestamp,
            "updated_at": timestamp,
            "ttl": ttl_timestamp
            # Note: No delivery tracking fields
        }

        dynamodb_table.put_item(Item=old_event)

        # Retrieve inbox (should handle missing fields gracefully)
        inbox_response = client.get(
            "/inbox",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert inbox_response.status_code == 200
        events = inbox_response.json()

        # Find our legacy event
        legacy_event = next((e for e in events if e['id'] == 'test-old-event-123'), None)
        assert legacy_event is not None

        # Verify fields default to appropriate values when missing
        assert legacy_event['delivery_attempts'] == 0  # Default to 0
        assert legacy_event['last_delivery_attempt'] is None
        assert legacy_event['delivery_latency_ms'] is None
        assert legacy_event['error_message'] is None

    def test_multiple_events_all_have_delivery_fields(self, client, auth_token):
        """Test that multiple events all include delivery tracking fields."""
        # Create multiple events
        event_ids = []
        for i in range(5):
            event_data = {
                "type": f"test.event{i}",
                "source": "test",
                "payload": {"index": i}
            }

            response = client.post(
                "/events",
                json=event_data,
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            assert response.status_code == 201
            event_ids.append(response.json()["id"])

        # Retrieve inbox
        inbox_response = client.get(
            "/inbox",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert inbox_response.status_code == 200
        events = inbox_response.json()
        assert len(events) == 5

        # Verify all events have delivery tracking fields
        for event in events:
            assert 'delivery_attempts' in event
            assert event['delivery_attempts'] == 0
            assert 'last_delivery_attempt' in event
            assert 'delivery_latency_ms' in event
            assert 'error_message' in event
