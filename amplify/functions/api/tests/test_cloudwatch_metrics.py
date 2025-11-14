"""
Unit tests for CloudWatch custom metrics (Task 22.3).
Tests EventsCreated, EventsDelivered, and DeliveryLatency metrics.
"""
import json
import os
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
import boto3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, call


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


class TestCloudWatchMetrics:
    """Tests for CloudWatch custom metrics."""

    @patch('main.cloudwatch_client')
    def test_events_created_metric_published(self, mock_cloudwatch, client, auth_token):
        """Test that EventsCreated metric is published when creating an event."""
        event_data = {
            "type": "user.signup",
            "source": "web-app",
            "payload": {"user_id": "123"}
        }

        response = client.post(
            "/events",
            json=event_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 201

        # Verify CloudWatch metric was published
        mock_cloudwatch.put_metric_data.assert_called()

        # Find the EventsCreated metric among all calls
        events_created_found = False
        for call_obj in mock_cloudwatch.put_metric_data.call_args_list:
            metric_data = call_obj[1]['MetricData']
            for metric in metric_data:
                if metric['MetricName'] == 'EventsCreated':
                    events_created_found = True
                    assert metric['Value'] == 1
                    assert metric['Unit'] == 'Count'

                    # Verify dimensions
                    dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
                    assert dimensions['EventType'] == 'user.signup'
                    assert dimensions['Source'] == 'web-app'
                    break

        assert events_created_found, "EventsCreated metric was not published"

    @patch('main.cloudwatch_client')
    def test_events_delivered_metric_published(self, mock_cloudwatch, client, auth_token, dynamodb_table):
        """Test that EventsDelivered and DeliveryLatency metrics are published on acknowledgment."""
        # Create a test event first
        base_time = datetime.utcnow() - timedelta(seconds=30)
        created_at = base_time.isoformat() + "Z"

        event = {
            "id": "test-event-123",
            "type": "test.event",
            "source": "test",
            "payload": {"data": "test"},
            "status": "pending",
            "created_at": created_at,
            "updated_at": created_at,
            "delivery_attempts": 0,
            "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
        }

        dynamodb_table.put_item(Item=event)

        # Reset mock to clear the EventsCreated call
        mock_cloudwatch.reset_mock()

        # Acknowledge the event
        response = client.post(
            "/inbox/test-event-123/ack",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'delivered'
        assert 'delivery_latency_ms' in data
        assert data['delivery_latency_ms'] > 0

        # Verify CloudWatch metrics were published
        mock_cloudwatch.put_metric_data.assert_called()

        # Find EventsDelivered and DeliveryLatency metrics among all calls
        events_delivered_found = False
        delivery_latency_found = False

        for call_obj in mock_cloudwatch.put_metric_data.call_args_list:
            metric_data = call_obj[1]['MetricData']
            for metric in metric_data:
                if metric['MetricName'] == 'EventsDelivered':
                    events_delivered_found = True
                    assert metric['Value'] == 1
                    assert metric['Unit'] == 'Count'
                    dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
                    assert dimensions['EventType'] == 'test.event'
                    assert dimensions['Source'] == 'test'

                elif metric['MetricName'] == 'DeliveryLatency':
                    delivery_latency_found = True
                    assert metric['Value'] >= 30000  # At least 30 seconds
                    assert metric['Unit'] == 'Milliseconds'
                    dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
                    assert dimensions['EventType'] == 'test.event'
                    assert dimensions['Source'] == 'test'

        assert events_delivered_found, "EventsDelivered metric was not published"
        assert delivery_latency_found, "DeliveryLatency metric was not published"

    @patch('main.cloudwatch_client')
    def test_delivery_latency_calculated_correctly(self, mock_cloudwatch, client, auth_token, dynamodb_table):
        """Test that delivery latency is calculated correctly."""
        # Create event 2 minutes ago
        base_time = datetime.utcnow() - timedelta(minutes=2)
        created_at = base_time.isoformat() + "Z"

        event = {
            "id": "latency-test-456",
            "type": "latency.test",
            "source": "test",
            "payload": {},
            "status": "pending",
            "created_at": created_at,
            "updated_at": created_at,
            "delivery_attempts": 0,
            "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
        }

        dynamodb_table.put_item(Item=event)

        # Reset mock
        mock_cloudwatch.reset_mock()

        # Acknowledge the event
        response = client.post(
            "/inbox/latency-test-456/ack",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Latency should be approximately 2 minutes (120,000 ms)
        # Allow some tolerance for test execution time
        assert data['delivery_latency_ms'] >= 120000  # At least 2 minutes
        assert data['delivery_latency_ms'] <= 125000  # No more than 2m5s

        # Find the DeliveryLatency metric and verify the value matches
        latency_metric_found = False
        for call_obj in mock_cloudwatch.put_metric_data.call_args_list:
            metric_data = call_obj[1]['MetricData']
            for metric in metric_data:
                if metric['MetricName'] == 'DeliveryLatency':
                    latency_metric_found = True
                    assert metric['Value'] == data['delivery_latency_ms']
                    break

        assert latency_metric_found, "DeliveryLatency metric was not published"

    @patch('main.cloudwatch_client')
    def test_metrics_failure_does_not_break_request(self, mock_cloudwatch, client, auth_token):
        """Test that CloudWatch metric failures don't break the API request."""
        # Make CloudWatch client throw an exception
        mock_cloudwatch.put_metric_data.side_effect = Exception("CloudWatch unavailable")

        event_data = {
            "type": "resilience.test",
            "source": "test",
            "payload": {}
        }

        # Request should still succeed even though metrics fail
        response = client.post(
            "/events",
            json=event_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 201
        assert 'id' in response.json()

    @patch('main.cloudwatch_client')
    def test_multiple_events_publish_separate_metrics(self, mock_cloudwatch, client, auth_token):
        """Test that multiple events publish separate metric data points."""
        # Create 3 events
        for i in range(3):
            event_data = {
                "type": f"batch.test{i}",
                "source": "batch-test",
                "payload": {"index": i}
            }

            response = client.post(
                "/events",
                json=event_data,
                headers={"Authorization": f"Bearer {auth_token}"}
            )

            assert response.status_code == 201

        # Find all EventsCreated metrics
        events_created_metrics = []
        for call_obj in mock_cloudwatch.put_metric_data.call_args_list:
            metric_data = call_obj[1]['MetricData']
            for metric in metric_data:
                if metric['MetricName'] == 'EventsCreated':
                    events_created_metrics.append(metric)

        # Verify we have 3 EventsCreated metrics
        assert len(events_created_metrics) == 3

        # Verify each has the correct event type
        event_types_found = set()
        for metric in events_created_metrics:
            dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
            event_types_found.add(dimensions['EventType'])

        expected_types = {'batch.test0', 'batch.test1', 'batch.test2'}
        assert event_types_found == expected_types
