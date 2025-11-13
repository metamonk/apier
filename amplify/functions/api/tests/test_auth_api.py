"""
Unit tests for Zapier Triggers API with JWT authentication.
Tests authentication and protected endpoints.
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
def client(dynamodb_table, secrets_manager):
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


class TestAuthentication:
    """Tests for JWT authentication."""

    def test_get_token_success(self, client):
        """Test successful token generation."""
        response = client.post(
            "/token",
            data={
                "username": "api",
                "password": "test-api-key-12345"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_get_token_invalid_username(self, client):
        """Test token generation with invalid username."""
        response = client.post(
            "/token",
            data={
                "username": "wrong",
                "password": "test-api-key-12345"
            }
        )

        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    def test_get_token_invalid_password(self, client):
        """Test token generation with invalid API key."""
        response = client.post(
            "/token",
            data={
                "username": "api",
                "password": "wrong-key"
            }
        )

        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]


class TestPublicEndpoints:
    """Tests for public endpoints (no authentication required)."""

    def test_root_endpoint(self, client):
        """Test GET / returns service information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Zapier Triggers API"
        assert data["status"] == "healthy"

    def test_health_endpoint(self, client):
        """Test GET /health returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_config_endpoint(self, client):
        """Test GET /config returns non-sensitive configuration."""
        response = client.get("/config")

        assert response.status_code == 200
        data = response.json()
        assert data["environment"] == "test"
        assert data["zapier_configured"] is True


class TestProtectedEndpoints:
    """Tests for protected endpoints requiring authentication."""

    def test_create_event_without_auth(self, client):
        """Test POST /events without authentication fails."""
        event_data = {
            "type": "test.event",
            "source": "test",
            "payload": {"test": "data"}
        }

        response = client.post("/events", json=event_data)
        assert response.status_code == 401

    def test_create_event_with_invalid_token(self, client):
        """Test POST /events with invalid token fails."""
        event_data = {
            "type": "test.event",
            "source": "test",
            "payload": {"test": "data"}
        }

        headers = {"Authorization": "Bearer invalid-token"}
        response = client.post("/events", json=event_data, headers=headers)
        assert response.status_code == 401

    def test_create_event_with_auth(self, client, auth_headers):
        """Test POST /events with valid authentication."""
        event_data = {
            "type": "test.event",
            "source": "test",
            "payload": {"test": "data"}
        }

        response = client.post("/events", json=event_data, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"

    def test_get_inbox_without_auth(self, client):
        """Test GET /inbox without authentication fails."""
        response = client.get("/inbox")
        assert response.status_code == 401

    def test_get_inbox_with_auth(self, client, auth_headers):
        """Test GET /inbox with valid authentication."""
        response = client.get("/inbox", headers=auth_headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_acknowledge_event_without_auth(self, client):
        """Test POST /inbox/{id}/ack without authentication fails."""
        response = client.post("/inbox/test-id/ack")
        assert response.status_code == 401

    def test_acknowledge_event_with_auth(self, client, auth_headers):
        """Test POST /inbox/{id}/ack with valid authentication."""
        # Create an event first
        event_data = {
            "type": "test.event",
            "source": "test",
            "payload": {"test": "data"}
        }
        create_response = client.post("/events", json=event_data, headers=auth_headers)
        event_id = create_response.json()["id"]

        # Acknowledge it
        ack_response = client.post(f"/inbox/{event_id}/ack", headers=auth_headers)

        assert ack_response.status_code == 200
        assert ack_response.json()["status"] == "delivered"


class TestEndToEndWithAuth:
    """End-to-end tests with authentication."""

    def test_complete_authenticated_workflow(self, client, auth_headers):
        """Test complete workflow: login → create event → retrieve → acknowledge."""
        # Create event
        event_data = {
            "type": "user.signup",
            "source": "web-app",
            "payload": {"user_id": "123", "email": "test@example.com"}
        }

        create_response = client.post("/events", json=event_data, headers=auth_headers)
        assert create_response.status_code == 201
        event_id = create_response.json()["id"]

        # Check inbox
        inbox_response = client.get("/inbox", headers=auth_headers)
        assert inbox_response.status_code == 200
        assert len(inbox_response.json()) == 1

        # Acknowledge event
        ack_response = client.post(f"/inbox/{event_id}/ack", headers=auth_headers)
        assert ack_response.status_code == 200

        # Verify inbox is empty
        final_inbox_response = client.get("/inbox", headers=auth_headers)
        assert len(final_inbox_response.json()) == 0

    def test_token_reuse(self, client, auth_token):
        """Test that a single token can be used for multiple requests."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Make multiple requests with the same token
        for i in range(3):
            event_data = {
                "type": f"test.event{i}",
                "source": "test",
                "payload": {"index": i}
            }

            response = client.post("/events", json=event_data, headers=headers)
            assert response.status_code == 201
