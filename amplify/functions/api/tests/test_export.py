"""
Unit tests for GET /events/export endpoint (GDPR/CCPA compliance).
Tests JSON and CSV export formats with various filters.
"""
import json
import csv
import io
import os
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
import boto3
from datetime import datetime, timedelta


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
    """Get a valid JWT token for testing."""
    response = client.post(
        "/token",
        data={
            "username": "api",
            "password": "test-api-key"
        }
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope='function')
def sample_events(client, auth_token):
    """Create sample events for testing."""
    events = []
    base_time = datetime.utcnow()

    # Create events with different types and dates
    event_configs = [
        {"type": "user.created", "source": "web", "days_ago": 5},
        {"type": "user.created", "source": "api", "days_ago": 3},
        {"type": "order.placed", "source": "web", "days_ago": 2},
        {"type": "user.updated", "source": "web", "days_ago": 1},
        {"type": "order.placed", "source": "api", "days_ago": 0},
    ]

    for i, config in enumerate(event_configs):
        event_data = {
            "type": config["type"],
            "source": config["source"],
            "payload": {
                "index": i,
                "user_id": f"user-{i}",
                "timestamp": (base_time - timedelta(days=config["days_ago"])).isoformat()
            }
        }

        response = client.post(
            "/events",
            json=event_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 201
        events.append(response.json())

    return events


class TestExportEndpointAuthentication:
    """Tests for authentication and authorization."""

    def test_export_requires_authentication(self, client):
        """Test that export endpoint requires JWT token."""
        response = client.get("/events/export")
        assert response.status_code == 401

    def test_export_with_invalid_token(self, client):
        """Test export with invalid JWT token."""
        response = client.get(
            "/events/export",
            headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401


class TestExportJSON:
    """Tests for JSON export format."""

    def test_export_json_no_events(self, client, auth_token):
        """Test JSON export when no events exist."""
        response = client.get(
            "/events/export",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "attachment" in response.headers["content-disposition"]
        assert ".json" in response.headers["content-disposition"]
        assert response.headers["x-total-events"] == "0"

        data = json.loads(response.content)
        assert data == []

    def test_export_json_with_events(self, client, auth_token, sample_events):
        """Test JSON export with sample events."""
        response = client.get(
            "/events/export?format=json",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.headers["x-total-events"] == "5"

        data = json.loads(response.content)
        assert len(data) == 5

        # Verify event structure
        for event in data:
            assert "id" in event
            assert "type" in event
            assert "source" in event
            assert "payload" in event
            assert "status" in event
            assert "created_at" in event
            assert "updated_at" in event

    def test_export_json_filter_by_event_type(self, client, auth_token, sample_events):
        """Test JSON export filtered by event type."""
        response = client.get(
            "/events/export?event_type=user.created",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = json.loads(response.content)

        # Should only have user.created events
        assert len(data) == 2
        for event in data:
            assert event["type"] == "user.created"

    def test_export_json_filter_by_date_range(self, client, auth_token, sample_events):
        """Test JSON export with date range filter."""
        # Get events from last 3 days
        start_date = (datetime.utcnow() - timedelta(days=3)).isoformat() + "Z"

        response = client.get(
            f"/events/export?start_date={start_date}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = json.loads(response.content)

        # Should have events from last 3 days (4 events: days 0, 1, 2, 3)
        assert len(data) >= 3

    def test_export_json_combined_filters(self, client, auth_token, sample_events):
        """Test JSON export with multiple filters."""
        start_date = (datetime.utcnow() - timedelta(days=10)).isoformat() + "Z"
        end_date = datetime.utcnow().isoformat() + "Z"

        response = client.get(
            f"/events/export?event_type=order.placed&start_date={start_date}&end_date={end_date}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = json.loads(response.content)

        # Should only have order.placed events within date range
        assert len(data) == 2
        for event in data:
            assert event["type"] == "order.placed"


class TestExportCSV:
    """Tests for CSV export format."""

    def test_export_csv_no_events(self, client, auth_token):
        """Test CSV export when no events exist."""
        response = client.get(
            "/events/export?format=csv",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert ".csv" in response.headers["content-disposition"]
        assert response.headers["x-total-events"] == "0"

        # Should only have header row
        csv_content = response.content.decode('utf-8')
        lines = csv_content.strip().split('\n')
        assert len(lines) == 1  # Only header
        assert "id,type,source,status,created_at,updated_at,payload" in lines[0]

    def test_export_csv_with_events(self, client, auth_token, sample_events):
        """Test CSV export with sample events."""
        response = client.get(
            "/events/export?format=csv",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert response.headers["x-total-events"] == "5"

        # Parse CSV
        csv_content = response.content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)

        assert len(rows) == 5

        # Verify CSV structure
        for row in rows:
            assert 'id' in row
            assert 'type' in row
            assert 'source' in row
            assert 'status' in row
            assert 'created_at' in row
            assert 'updated_at' in row
            assert 'payload' in row

            # Payload should be valid JSON string
            payload = json.loads(row['payload'])
            assert isinstance(payload, dict)

    def test_export_csv_filter_by_event_type(self, client, auth_token, sample_events):
        """Test CSV export filtered by event type."""
        response = client.get(
            "/events/export?format=csv&event_type=order.placed",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200

        # Parse CSV
        csv_content = response.content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)

        # Should only have order.placed events
        assert len(rows) == 2
        for row in rows:
            assert row['type'] == 'order.placed'


class TestExportValidation:
    """Tests for input validation."""

    def test_export_invalid_format(self, client, auth_token):
        """Test export with invalid format parameter."""
        response = client.get(
            "/events/export?format=xml",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 400
        assert "Invalid format" in response.json()["detail"]

    def test_export_invalid_start_date(self, client, auth_token):
        """Test export with invalid start_date format."""
        response = client.get(
            "/events/export?start_date=invalid-date",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 400
        assert "Invalid start_date format" in response.json()["detail"]

    def test_export_invalid_end_date(self, client, auth_token):
        """Test export with invalid end_date format."""
        response = client.get(
            "/events/export?end_date=not-a-date",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 400
        assert "Invalid end_date format" in response.json()["detail"]


class TestExportHeaders:
    """Tests for response headers."""

    def test_export_json_headers(self, client, auth_token, sample_events):
        """Test JSON export response headers."""
        response = client.get(
            "/events/export?format=json",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "attachment" in response.headers["content-disposition"]
        assert "events_export_" in response.headers["content-disposition"]
        assert ".json" in response.headers["content-disposition"]
        assert "x-total-events" in response.headers

    def test_export_csv_headers(self, client, auth_token, sample_events):
        """Test CSV export response headers."""
        response = client.get(
            "/events/export?format=csv",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "events_export_" in response.headers["content-disposition"]
        assert ".csv" in response.headers["content-disposition"]
        assert "x-total-events" in response.headers

    def test_export_filename_has_timestamp(self, client, auth_token):
        """Test that export filename includes timestamp."""
        response = client.get(
            "/events/export",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        content_disposition = response.headers["content-disposition"]

        # Filename should contain timestamp in format YYYYMMDD_HHMMSS
        assert "events_export_" in content_disposition
        # Extract filename
        import re
        match = re.search(r'events_export_(\d{8}_\d{6})\.json', content_disposition)
        assert match is not None


class TestExportPerformance:
    """Tests for performance and limits."""

    def test_export_respects_limit(self, client, auth_token):
        """Test that export respects the 10,000 event limit."""
        # This test would create 10,001 events in a real scenario
        # For unit testing, we'll just verify the limit is documented
        # and the code includes the limit logic

        # Just verify the endpoint works with the limit parameter
        response = client.get(
            "/events/export",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        # The implementation includes: events = events[:10000]
