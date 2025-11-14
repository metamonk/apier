"""
Unit tests for DELETE /events/{event_id} endpoint.
Tests GDPR/CCPA compliance event deletion functionality.
"""
import json
import os
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
import boto3


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
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

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

        table.meta.client.get_waiter('table_exists').wait(TableName='test-zapier-triggers-events')
        yield table


@pytest.fixture(scope='function')
def cloudwatch_client(aws_credentials):
    """Create a mock CloudWatch client for testing."""
    with mock_aws():
        client = boto3.client('cloudwatch', region_name='us-east-1')
        yield client


@pytest.fixture(scope='function')
def secrets_manager(aws_credentials):
    """Create a mock Secrets Manager secret for testing."""
    with mock_aws():
        client = boto3.client('secretsmanager', region_name='us-east-1')

        # Create secret with test API key
        client.create_secret(
            Name='test-secret',
            SecretString=json.dumps({
                'environment': 'test',
                'jwt_secret': 'test-jwt-secret-12345678901234567890123456789012',
                'zapier_api_key': 'test-api-key-12345',
                'zapier_webhook_url': 'https://hooks.zapier.com/test'
            })
        )

        yield client


@pytest.fixture(scope='function')
def client(dynamodb_table, secrets_manager, cloudwatch_client):
    """Create a test client with mocked AWS services."""
    from main import app
    import main
    main._secrets_cache.clear()

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope='function')
def auth_token(client):
    """Get a valid JWT token for authenticated requests."""
    response = client.post(
        "/token",
        data={
            "username": "api",
            "password": "test-api-key-12345"
        }
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope='function')
def auth_headers(auth_token):
    """Create authorization headers with JWT token."""
    return {"Authorization": f"Bearer {auth_token}"}


class TestDeleteEventEndpoint:
    """Tests for DELETE /events/{event_id} endpoint."""

    def test_delete_event_success(self, client, auth_headers):
        """Test successful event deletion."""
        # Create an event first
        event_data = {
            "type": "user.signup",
            "source": "web-app",
            "payload": {
                "user_id": "123",
                "email": "test@example.com"
            }
        }

        create_response = client.post("/events", json=event_data, headers=auth_headers)
        assert create_response.status_code == 201
        event_id = create_response.json()["id"]

        # Delete the event
        delete_response = client.delete(f"/events/{event_id}", headers=auth_headers)

        assert delete_response.status_code == 200
        delete_data = delete_response.json()

        # Verify response structure
        assert delete_data["id"] == event_id
        assert delete_data["message"] == "Event deleted successfully"
        assert "deleted_at" in delete_data

    def test_delete_event_not_found(self, client, auth_headers):
        """Test deleting a non-existent event returns 404."""
        fake_event_id = "00000000-0000-0000-0000-000000000000"

        response = client.delete(f"/events/{fake_event_id}", headers=auth_headers)

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_delete_event_without_auth(self, client):
        """Test DELETE /events/{id} without authentication fails."""
        fake_event_id = "00000000-0000-0000-0000-000000000000"

        response = client.delete(f"/events/{fake_event_id}")

        assert response.status_code == 401

    def test_delete_event_with_invalid_token(self, client):
        """Test DELETE /events/{id} with invalid token fails."""
        fake_event_id = "00000000-0000-0000-0000-000000000000"
        headers = {"Authorization": "Bearer invalid-token"}

        response = client.delete(f"/events/{fake_event_id}", headers=headers)

        assert response.status_code == 401

    def test_deleted_event_not_in_inbox(self, client, auth_headers):
        """Test that deleted events don't appear in inbox."""
        # Create an event
        event_data = {
            "type": "test.event",
            "source": "test",
            "payload": {"test": "data"}
        }

        create_response = client.post("/events", json=event_data, headers=auth_headers)
        event_id = create_response.json()["id"]

        # Verify it's in the inbox
        inbox_response = client.get("/inbox", headers=auth_headers)
        assert len(inbox_response.json()) == 1

        # Delete the event
        delete_response = client.delete(f"/events/{event_id}", headers=auth_headers)
        assert delete_response.status_code == 200

        # Verify it's no longer in the inbox
        inbox_response = client.get("/inbox", headers=auth_headers)
        assert len(inbox_response.json()) == 0

    def test_delete_already_deleted_event(self, client, auth_headers):
        """Test deleting an event that was already deleted."""
        # Create an event
        event_data = {
            "type": "test.event",
            "source": "test",
            "payload": {"test": "data"}
        }

        create_response = client.post("/events", json=event_data, headers=auth_headers)
        event_id = create_response.json()["id"]

        # Delete once
        first_delete = client.delete(f"/events/{event_id}", headers=auth_headers)
        assert first_delete.status_code == 200

        # Try to delete again - should return 404
        second_delete = client.delete(f"/events/{event_id}", headers=auth_headers)
        assert second_delete.status_code == 404
        data = second_delete.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_delete_delivered_event(self, client, auth_headers):
        """Test deleting an event that has been delivered."""
        # Create an event
        event_data = {
            "type": "test.event",
            "source": "test",
            "payload": {"test": "data"}
        }

        create_response = client.post("/events", json=event_data, headers=auth_headers)
        event_id = create_response.json()["id"]

        # Acknowledge the event (mark as delivered)
        ack_response = client.post(f"/inbox/{event_id}/ack", headers=auth_headers)
        assert ack_response.status_code == 200

        # Delete the delivered event
        delete_response = client.delete(f"/events/{event_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        assert delete_response.json()["id"] == event_id

    def test_delete_multiple_events(self, client, auth_headers):
        """Test deleting multiple events."""
        # Create 3 events
        event_ids = []
        for i in range(3):
            event_data = {
                "type": f"test.event{i}",
                "source": "test",
                "payload": {"index": i}
            }
            response = client.post("/events", json=event_data, headers=auth_headers)
            event_ids.append(response.json()["id"])

        # Verify all 3 are in inbox
        inbox_response = client.get("/inbox", headers=auth_headers)
        assert len(inbox_response.json()) == 3

        # Delete 2 of them
        for event_id in event_ids[:2]:
            delete_response = client.delete(f"/events/{event_id}", headers=auth_headers)
            assert delete_response.status_code == 200

        # Verify only 1 remains in inbox
        inbox_response = client.get("/inbox", headers=auth_headers)
        remaining_events = inbox_response.json()
        assert len(remaining_events) == 1
        assert remaining_events[0]["id"] == event_ids[2]


class TestDeleteEventAuditLogging:
    """Tests for audit logging and compliance features."""

    def test_delete_event_audit_log(self, client, auth_headers, capfd):
        """Test that deletion is logged for audit purposes."""
        # Create an event
        event_data = {
            "type": "user.data",
            "source": "gdpr-request",
            "payload": {"user_id": "123", "email": "user@example.com"}
        }

        create_response = client.post("/events", json=event_data, headers=auth_headers)
        event_id = create_response.json()["id"]

        # Delete the event
        delete_response = client.delete(f"/events/{event_id}", headers=auth_headers)
        assert delete_response.status_code == 200

        # Check that audit log was written (captured output)
        captured = capfd.readouterr()
        assert "[AUDIT]" in captured.out
        assert event_id in captured.out
        assert "user.data" in captured.out
        assert "gdpr-request" in captured.out

    def test_delete_event_with_special_characters(self, client, auth_headers):
        """Test deleting an event with special characters in payload."""
        # Create an event with special characters
        event_data = {
            "type": "user.message",
            "source": "chat-app",
            "payload": {
                "message": "Test <script>alert('xss')</script>",
                "user": "user@example.com"
            }
        }

        create_response = client.post("/events", json=event_data, headers=auth_headers)
        event_id = create_response.json()["id"]

        # Delete should work normally
        delete_response = client.delete(f"/events/{event_id}", headers=auth_headers)
        assert delete_response.status_code == 200


class TestGDPRComplianceWorkflow:
    """End-to-end tests for GDPR/CCPA compliance scenarios."""

    def test_gdpr_right_to_erasure_workflow(self, client, auth_headers):
        """Test complete GDPR right to erasure workflow."""
        # Step 1: Create user data event
        user_event = {
            "type": "user.created",
            "source": "registration-service",
            "payload": {
                "user_id": "user-123",
                "email": "user@example.com",
                "name": "John Doe",
                "created_at": "2024-01-15T10:00:00Z"
            }
        }

        create_response = client.post("/events", json=user_event, headers=auth_headers)
        assert create_response.status_code == 201
        event_id = create_response.json()["id"]

        # Step 2: Verify event exists in inbox
        inbox_response = client.get("/inbox", headers=auth_headers)
        assert len(inbox_response.json()) == 1
        assert inbox_response.json()[0]["id"] == event_id

        # Step 3: User requests data deletion (GDPR Article 17)
        delete_response = client.delete(f"/events/{event_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Event deleted successfully"

        # Step 4: Verify event is permanently deleted
        inbox_response = client.get("/inbox", headers=auth_headers)
        assert len(inbox_response.json()) == 0

        # Step 5: Verify deletion is idempotent (second delete returns 404)
        second_delete = client.delete(f"/events/{event_id}", headers=auth_headers)
        assert second_delete.status_code == 404
        data = second_delete.json()
        assert "detail" in data

    def test_ccpa_data_deletion_workflow(self, client, auth_headers):
        """Test CCPA consumer data deletion workflow."""
        # Create multiple events for a consumer
        event_ids = []

        # Create first event
        event1 = {
            "type": "purchase.completed",
            "source": "ecommerce",
            "payload": {"consumer_id": "ca-user-456", "amount": "99.99"}
        }
        response1 = client.post("/events", json=event1, headers=auth_headers)
        assert response1.status_code == 201
        event_ids.append(response1.json()["id"])

        # Create second event
        event2 = {
            "type": "profile.updated",
            "source": "profile-service",
            "payload": {"consumer_id": "ca-user-456", "state": "CA"}
        }
        response2 = client.post("/events", json=event2, headers=auth_headers)
        assert response2.status_code == 201
        event_ids.append(response2.json()["id"])

        # Verify all events exist
        inbox_response = client.get("/inbox", headers=auth_headers)
        assert len(inbox_response.json()) == 2

        # Delete all consumer events (CCPA data deletion request)
        for event_id in event_ids:
            delete_response = client.delete(f"/events/{event_id}", headers=auth_headers)
            assert delete_response.status_code == 200

        # Verify all events are deleted
        inbox_response = client.get("/inbox", headers=auth_headers)
        assert len(inbox_response.json()) == 0

    def test_partial_deletion_scenario(self, client, auth_headers):
        """Test scenario where only specific events are deleted."""
        # Create events for two different users
        user1_event = {
            "type": "user.activity",
            "source": "app",
            "payload": {"user_id": "user-1", "action": "login"}
        }
        user2_event = {
            "type": "user.activity",
            "source": "app",
            "payload": {"user_id": "user-2", "action": "login"}
        }

        user1_response = client.post("/events", json=user1_event, headers=auth_headers)
        user1_id = user1_response.json()["id"]

        user2_response = client.post("/events", json=user2_event, headers=auth_headers)
        user2_id = user2_response.json()["id"]

        # Delete only user1's event
        delete_response = client.delete(f"/events/{user1_id}", headers=auth_headers)
        assert delete_response.status_code == 200

        # Verify user2's event still exists
        inbox_response = client.get("/inbox", headers=auth_headers)
        remaining_events = inbox_response.json()
        assert len(remaining_events) == 1
        assert remaining_events[0]["id"] == user2_id
        assert remaining_events[0]["payload"]["user_id"] == "user-2"
