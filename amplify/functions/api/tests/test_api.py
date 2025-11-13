"""
Unit tests for Zapier Triggers API endpoints.
Tests POST /events, GET /inbox, and POST /inbox/{id}/ack.
"""
import json
import os
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
import boto3
from datetime import datetime
from decimal import Decimal


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


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_root_endpoint(self, client):
        """Test GET / returns service information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Zapier Triggers API"
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_endpoint(self, client):
        """Test GET /health returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestConfigEndpoint:
    """Tests for configuration endpoint."""

    def test_get_config(self, client):
        """Test GET /config returns non-sensitive configuration."""
        response = client.get("/config")

        assert response.status_code == 200
        data = response.json()

        # Verify configuration fields
        assert data["environment"] == "test"
        assert data["zapier_configured"] is True
        assert data["webhook_configured"] is True
        assert data["jwt_configured"] is True
        assert "cache_hit" in data


class TestEventsEndpoint:
    """Tests for POST /events endpoint."""

    def test_create_event_success(self, client):
        """Test successful event creation."""
        event_data = {
            "type": "user.signup",
            "source": "web-app",
            "payload": {
                "user_id": "123",
                "email": "test@example.com"
            }
        }

        response = client.post("/events", json=event_data)

        assert response.status_code == 201
        data = response.json()

        # Verify response structure
        assert "id" in data
        assert data["status"] == "pending"
        assert "timestamp" in data

        # Verify ID is a valid UUID format
        import uuid
        try:
            uuid.UUID(data["id"])
        except ValueError:
            pytest.fail("Invalid UUID format for event ID")

    def test_create_event_missing_field(self, client):
        """Test event creation with missing required field."""
        incomplete_data = {
            "type": "user.signup",
            "source": "web-app"
            # Missing 'payload' field
        }

        response = client.post("/events", json=incomplete_data)

        assert response.status_code == 422  # Validation error

    def test_create_event_invalid_json(self, client):
        """Test event creation with invalid JSON."""
        response = client.post(
            "/events",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_create_multiple_events(self, client):
        """Test creating multiple events."""
        event_ids = []

        for i in range(3):
            event_data = {
                "type": f"test.event{i}",
                "source": "test",
                "payload": {"index": i}
            }

            response = client.post("/events", json=event_data)
            assert response.status_code == 201

            event_ids.append(response.json()["id"])

        # Verify all IDs are unique
        assert len(event_ids) == len(set(event_ids))


class TestInboxEndpoint:
    """Tests for GET /inbox endpoint."""

    def test_get_inbox_empty(self, client):
        """Test inbox retrieval when no events exist."""
        response = client.get("/inbox")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_inbox_with_pending_events(self, client):
        """Test inbox retrieval with pending events."""
        # Create some test events
        event_data = {
            "type": "test.event",
            "source": "test",
            "payload": {"test": "data"}
        }

        # Create 3 events
        event_ids = []
        for i in range(3):
            response = client.post("/events", json=event_data)
            assert response.status_code == 201
            event_ids.append(response.json()["id"])

        # Retrieve inbox
        response = client.get("/inbox")

        assert response.status_code == 200
        events = response.json()

        # Verify we got all 3 events
        assert len(events) == 3

        # Verify event structure
        for event in events:
            assert "id" in event
            assert event["status"] == "pending"
            assert event["type"] == "test.event"
            assert event["source"] == "test"
            assert "payload" in event
            assert "created_at" in event
            assert "updated_at" in event

    def test_inbox_ordering(self, client):
        """Test that inbox returns events in descending created_at order."""
        # Create events with slight delays to ensure different timestamps
        import time

        event_ids = []
        for i in range(3):
            response = client.post("/events", json={
                "type": f"test.event{i}",
                "source": "test",
                "payload": {"index": i}
            })
            event_ids.append(response.json()["id"])
            time.sleep(0.1)  # Small delay to ensure different timestamps

        # Get inbox
        response = client.get("/inbox")
        events = response.json()

        # Verify events are in descending order (newest first)
        # The most recently created event should be first
        timestamps = [event["created_at"] for event in events]
        assert timestamps == sorted(timestamps, reverse=True)


class TestAcknowledgeEndpoint:
    """Tests for POST /inbox/{event_id}/ack endpoint."""

    def test_acknowledge_event_success(self, client):
        """Test successful event acknowledgment."""
        # Create an event first
        event_data = {
            "type": "test.event",
            "source": "test",
            "payload": {"test": "data"}
        }

        create_response = client.post("/events", json=event_data)
        event_id = create_response.json()["id"]

        # Acknowledge the event
        ack_response = client.post(f"/inbox/{event_id}/ack")

        assert ack_response.status_code == 200
        ack_data = ack_response.json()

        # Verify response structure
        assert ack_data["id"] == event_id
        assert ack_data["status"] == "delivered"
        assert ack_data["message"] == "Event acknowledged successfully"
        assert "updated_at" in ack_data

    def test_acknowledge_nonexistent_event(self, client):
        """Test acknowledging an event that doesn't exist."""
        fake_event_id = "00000000-0000-0000-0000-000000000000"

        response = client.post(f"/inbox/{fake_event_id}/ack")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_acknowledged_event_not_in_inbox(self, client):
        """Test that acknowledged events don't appear in inbox."""
        # Create an event
        event_data = {
            "type": "test.event",
            "source": "test",
            "payload": {"test": "data"}
        }

        create_response = client.post("/events", json=event_data)
        event_id = create_response.json()["id"]

        # Verify it's in the inbox
        inbox_response = client.get("/inbox")
        assert len(inbox_response.json()) == 1

        # Acknowledge the event
        client.post(f"/inbox/{event_id}/ack")

        # Verify it's no longer in the inbox
        inbox_response = client.get("/inbox")
        assert len(inbox_response.json()) == 0

    def test_acknowledge_event_twice(self, client):
        """Test acknowledging the same event twice."""
        # Create an event
        event_data = {
            "type": "test.event",
            "source": "test",
            "payload": {"test": "data"}
        }

        create_response = client.post("/events", json=event_data)
        event_id = create_response.json()["id"]

        # Acknowledge once
        first_ack = client.post(f"/inbox/{event_id}/ack")
        assert first_ack.status_code == 200

        # Acknowledge again - should still succeed (idempotent)
        second_ack = client.post(f"/inbox/{event_id}/ack")
        assert second_ack.status_code == 200


class TestEndToEndWorkflow:
    """End-to-end integration tests."""

    def test_complete_event_lifecycle(self, client):
        """Test the complete event lifecycle: create → inbox → acknowledge."""
        # Step 1: Create an event
        event_data = {
            "type": "user.signup",
            "source": "web-app",
            "payload": {
                "user_id": "test-user-123",
                "email": "test@example.com",
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        create_response = client.post("/events", json=event_data)
        assert create_response.status_code == 201
        event_id = create_response.json()["id"]

        # Step 2: Verify event appears in inbox
        inbox_response = client.get("/inbox")
        assert inbox_response.status_code == 200

        inbox_events = inbox_response.json()
        assert len(inbox_events) == 1
        assert inbox_events[0]["id"] == event_id
        assert inbox_events[0]["status"] == "pending"

        # Step 3: Acknowledge the event
        ack_response = client.post(f"/inbox/{event_id}/ack")
        assert ack_response.status_code == 200
        assert ack_response.json()["status"] == "delivered"

        # Step 4: Verify event no longer in inbox
        final_inbox_response = client.get("/inbox")
        assert len(final_inbox_response.json()) == 0

    def test_multiple_events_workflow(self, client):
        """Test handling multiple events through the workflow."""
        # Create 5 events
        event_ids = []
        for i in range(5):
            event_data = {
                "type": f"test.event{i}",
                "source": "test",
                "payload": {"index": i}
            }

            response = client.post("/events", json=event_data)
            event_ids.append(response.json()["id"])

        # Verify all 5 are in inbox
        inbox_response = client.get("/inbox")
        assert len(inbox_response.json()) == 5

        # Acknowledge 3 of them
        for event_id in event_ids[:3]:
            client.post(f"/inbox/{event_id}/ack")

        # Verify only 2 remain in inbox
        inbox_response = client.get("/inbox")
        remaining_events = inbox_response.json()
        assert len(remaining_events) == 2

        # Verify the remaining event IDs are correct
        remaining_ids = {event["id"] for event in remaining_events}
        expected_ids = set(event_ids[3:])
        assert remaining_ids == expected_ids
