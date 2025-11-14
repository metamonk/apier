"""
Unit tests for metrics endpoints (Task 23.1).
Tests all /metrics/* endpoints: summary, latency, throughput, errors.

Coverage Goals:
- Test all success paths with various data scenarios
- Test edge cases (empty data, single events, large datasets)
- Test caching behavior (30-second TTL)
- Test pagination handling for large datasets
- Test error handling and DynamoDB failures
- Test authentication requirements
- Aim for >90% code coverage on metrics code
"""
import json
import os
import pytest
import time
from fastapi.testclient import TestClient
from moto import mock_aws
import boto3
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch


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

    # Reset the secrets cache and metrics cache to force fresh retrieval
    import main
    main._secrets_cache.clear()
    main.metrics_cache.clear()

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


@pytest.fixture
def sample_events(dynamodb_table):
    """Create a diverse set of sample events for testing."""
    now = datetime.utcnow()

    events = [
        # Recent delivered events (for latency calculation)
        {
            "id": "delivered-1",
            "type": "user.signup",
            "source": "web",
            "status": "delivered",
            "created_at": (now - timedelta(seconds=10)).isoformat() + "Z",
            "updated_at": (now - timedelta(seconds=5)).isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        },
        {
            "id": "delivered-2",
            "type": "user.login",
            "source": "mobile",
            "status": "delivered",
            "created_at": (now - timedelta(seconds=30)).isoformat() + "Z",
            "updated_at": (now - timedelta(seconds=20)).isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        },
        # Older delivered events
        {
            "id": "delivered-old",
            "type": "order.placed",
            "source": "api",
            "status": "delivered",
            "created_at": (now - timedelta(hours=25)).isoformat() + "Z",
            "updated_at": (now - timedelta(hours=25)).isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        },
        # Failed events
        {
            "id": "failed-1",
            "type": "webhook.error",
            "source": "web",
            "status": "failed",
            "created_at": (now - timedelta(minutes=5)).isoformat() + "Z",
            "updated_at": (now - timedelta(minutes=2)).isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 3,
            "ttl": int((now + timedelta(days=90)).timestamp())
        },
        {
            "id": "failed-2",
            "type": "payment.failed",
            "source": "stripe",
            "status": "failed",
            "created_at": (now - timedelta(minutes=15)).isoformat() + "Z",
            "updated_at": (now - timedelta(minutes=10)).isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 3,
            "ttl": int((now + timedelta(days=90)).timestamp())
        },
        # Pending events
        {
            "id": "pending-1",
            "type": "data.sync",
            "source": "cron",
            "status": "pending",
            "created_at": (now - timedelta(seconds=45)).isoformat() + "Z",
            "updated_at": (now - timedelta(seconds=45)).isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 0,
            "ttl": int((now + timedelta(days=90)).timestamp())
        },
        {
            "id": "pending-2",
            "type": "email.queue",
            "source": "mailer",
            "status": "pending",
            "created_at": (now - timedelta(hours=1)).isoformat() + "Z",
            "updated_at": (now - timedelta(hours=1)).isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 0,
            "ttl": int((now + timedelta(days=90)).timestamp())
        },
        # Recent events for throughput testing (last 24h)
        {
            "id": "recent-1",
            "type": "analytics.track",
            "source": "web",
            "status": "delivered",
            "created_at": (now - timedelta(hours=2)).isoformat() + "Z",
            "updated_at": (now - timedelta(hours=2)).isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        },
        {
            "id": "recent-2",
            "type": "analytics.track",
            "source": "web",
            "status": "delivered",
            "created_at": (now - timedelta(hours=5)).isoformat() + "Z",
            "updated_at": (now - timedelta(hours=5)).isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        },
        {
            "id": "recent-3",
            "type": "analytics.track",
            "source": "web",
            "status": "pending",
            "created_at": (now - timedelta(hours=10)).isoformat() + "Z",
            "updated_at": (now - timedelta(hours=10)).isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 0,
            "ttl": int((now + timedelta(days=90)).timestamp())
        },
    ]

    # Insert all events
    for event in events:
        dynamodb_table.put_item(Item=event)

    return events


# ============================================================================
# TEST CLASS: /metrics/summary
# ============================================================================

class TestMetricsSummary:
    """Tests for GET /metrics/summary endpoint."""

    def test_summary_requires_authentication(self, client):
        """Test that /metrics/summary requires authentication."""
        response = client.get("/metrics/summary")
        assert response.status_code == 401

    def test_summary_with_no_events(self, client, auth_token):
        """Test summary metrics when database is empty."""
        response = client.get(
            "/metrics/summary",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "total" in data
        assert "pending" in data
        assert "delivered" in data
        assert "failed" in data
        assert "success_rate" in data

        # All should be zero
        assert data["total"] == 0
        assert data["pending"] == 0
        assert data["delivered"] == 0
        assert data["failed"] == 0
        assert data["success_rate"] == 0.0

    def test_summary_with_sample_events(self, client, auth_token, sample_events):
        """Test summary metrics with diverse sample data."""
        response = client.get(
            "/metrics/summary",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Count expected values from sample_events
        expected_total = len(sample_events)
        expected_pending = sum(1 for e in sample_events if e["status"] == "pending")
        expected_delivered = sum(1 for e in sample_events if e["status"] == "delivered")
        expected_failed = sum(1 for e in sample_events if e["status"] == "failed")
        expected_success_rate = (expected_delivered / (expected_delivered + expected_failed) * 100) if (expected_delivered + expected_failed) > 0 else 0.0

        assert data["total"] == expected_total
        assert data["pending"] == expected_pending
        assert data["delivered"] == expected_delivered
        assert data["failed"] == expected_failed
        assert data["success_rate"] == round(expected_success_rate, 2)

    def test_summary_success_rate_100_percent(self, client, auth_token, dynamodb_table):
        """Test success rate calculation when all events are delivered."""
        now = datetime.utcnow()

        # Create only delivered events
        for i in range(5):
            dynamodb_table.put_item(Item={
                "id": f"success-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        response = client.get(
            "/metrics/summary",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success_rate"] == 100.0

    def test_summary_success_rate_0_percent(self, client, auth_token, dynamodb_table):
        """Test success rate calculation when all completed events failed."""
        now = datetime.utcnow()

        # Create only failed events
        for i in range(3):
            dynamodb_table.put_item(Item={
                "id": f"fail-{i}",
                "type": "test",
                "source": "test",
                "status": "failed",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 3,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        response = client.get(
            "/metrics/summary",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success_rate"] == 0.0

    def test_summary_caching_behavior(self, client, auth_token, dynamodb_table):
        """Test that summary results are cached for 30 seconds."""
        now = datetime.utcnow()

        # Create initial event
        dynamodb_table.put_item(Item={
            "id": "cache-test-1",
            "type": "test",
            "source": "test",
            "status": "delivered",
            "created_at": now.isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        # First request - should hit database
        response1 = client.get(
            "/metrics/summary",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["total"] == 1

        # Add another event
        dynamodb_table.put_item(Item={
            "id": "cache-test-2",
            "type": "test",
            "source": "test",
            "status": "delivered",
            "created_at": now.isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        # Second request immediately - should return cached data
        response2 = client.get(
            "/metrics/summary",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["total"] == 1  # Still cached value

        # Clear cache and try again - should see new data
        import main
        main.metrics_cache.clear()

        response3 = client.get(
            "/metrics/summary",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response3.status_code == 200
        data3 = response3.json()
        assert data3["total"] == 2  # Fresh data

    def test_summary_with_large_dataset(self, client, auth_token, dynamodb_table):
        """Test summary with large dataset to verify pagination handling."""
        now = datetime.utcnow()

        # Create 150 events across different statuses
        for i in range(150):
            status = "delivered" if i < 100 else ("failed" if i < 130 else "pending")
            dynamodb_table.put_item(Item={
                "id": f"large-{i}",
                "type": "test",
                "source": "test",
                "status": status,
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1 if status != "pending" else 0,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        response = client.get(
            "/metrics/summary",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 150
        assert data["delivered"] == 100
        assert data["failed"] == 30
        assert data["pending"] == 20


# ============================================================================
# TEST CLASS: /metrics/latency
# ============================================================================

class TestMetricsLatency:
    """Tests for GET /metrics/latency endpoint."""

    def test_latency_requires_authentication(self, client):
        """Test that /metrics/latency requires authentication."""
        response = client.get("/metrics/latency")
        assert response.status_code == 401

    def test_latency_with_no_completed_events(self, client, auth_token, dynamodb_table):
        """Test latency metrics when no completed events exist."""
        now = datetime.utcnow()

        # Create only pending events
        dynamodb_table.put_item(Item={
            "id": "pending-only",
            "type": "test",
            "source": "test",
            "status": "pending",
            "created_at": now.isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 0,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        response = client.get(
            "/metrics/latency",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # All latencies should be 0 with no sample
        assert data["p50"] == 0.0
        assert data["p95"] == 0.0
        assert data["p99"] == 0.0
        assert data["sample_size"] == 0

    def test_latency_with_single_event(self, client, auth_token, dynamodb_table):
        """Test latency calculation with a single completed event."""
        now = datetime.utcnow()
        created = now - timedelta(seconds=5)
        updated = now

        dynamodb_table.put_item(Item={
            "id": "single-event",
            "type": "test",
            "source": "test",
            "status": "delivered",
            "created_at": created.isoformat() + "Z",
            "updated_at": updated.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        response = client.get(
            "/metrics/latency",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # All percentiles should be the same with 1 sample
        assert data["sample_size"] == 1
        assert data["p50"] == data["p95"] == data["p99"]
        assert data["p50"] >= 5.0  # At least 5 seconds

    def test_latency_percentiles_calculation(self, client, auth_token, dynamodb_table):
        """Test accurate percentile calculation with diverse latencies."""
        now = datetime.utcnow()

        # Create events with known latencies: 1s, 2s, 3s, ..., 10s
        for i in range(1, 11):
            created = now - timedelta(seconds=i)
            updated = now

            dynamodb_table.put_item(Item={
                "id": f"percentile-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": created.isoformat() + "Z",
                "updated_at": updated.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        response = client.get(
            "/metrics/latency",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["sample_size"] == 10
        # P50 should be around 5s (median)
        assert 4.0 <= data["p50"] <= 6.0
        # P95 should be around 9.5s
        assert 8.0 <= data["p95"] <= 10.0
        # P99 should be around 9.9s (close to max)
        assert 9.0 <= data["p99"] <= 10.0

    def test_latency_includes_failed_events(self, client, auth_token, dynamodb_table):
        """Test that latency includes both delivered and failed events."""
        now = datetime.utcnow()

        # Create delivered event
        dynamodb_table.put_item(Item={
            "id": "delivered-lat",
            "type": "test",
            "source": "test",
            "status": "delivered",
            "created_at": (now - timedelta(seconds=3)).isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        # Create failed event
        dynamodb_table.put_item(Item={
            "id": "failed-lat",
            "type": "test",
            "source": "test",
            "status": "failed",
            "created_at": (now - timedelta(seconds=7)).isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 3,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        response = client.get(
            "/metrics/latency",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sample_size"] == 2  # Both events counted

    def test_latency_handles_invalid_timestamps(self, client, auth_token, dynamodb_table):
        """Test that events with invalid timestamps are skipped gracefully."""
        now = datetime.utcnow()

        # Create event with valid timestamps
        dynamodb_table.put_item(Item={
            "id": "valid-ts",
            "type": "test",
            "source": "test",
            "status": "delivered",
            "created_at": (now - timedelta(seconds=5)).isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        # Create event with invalid created_at
        dynamodb_table.put_item(Item={
            "id": "invalid-ts",
            "type": "test",
            "source": "test",
            "status": "delivered",
            "created_at": "invalid-timestamp",
            "updated_at": now.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        response = client.get(
            "/metrics/latency",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sample_size"] == 1  # Only valid event counted

    def test_latency_caching(self, client, auth_token, dynamodb_table):
        """Test that latency results are cached."""
        now = datetime.utcnow()

        dynamodb_table.put_item(Item={
            "id": "cache-lat-1",
            "type": "test",
            "source": "test",
            "status": "delivered",
            "created_at": (now - timedelta(seconds=5)).isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        # First request
        response1 = client.get(
            "/metrics/latency",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response1.status_code == 200
        data1 = response1.json()

        # Add another event
        dynamodb_table.put_item(Item={
            "id": "cache-lat-2",
            "type": "test",
            "source": "test",
            "status": "delivered",
            "created_at": (now - timedelta(seconds=10)).isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        # Second request - should be cached
        response2 = client.get(
            "/metrics/latency",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        data2 = response2.json()
        assert data2["sample_size"] == data1["sample_size"]  # Still 1, from cache


# ============================================================================
# TEST CLASS: /metrics/throughput
# ============================================================================

class TestMetricsThroughput:
    """Tests for GET /metrics/throughput endpoint."""

    def test_throughput_requires_authentication(self, client):
        """Test that /metrics/throughput requires authentication."""
        response = client.get("/metrics/throughput")
        assert response.status_code == 401

    def test_throughput_with_no_recent_events(self, client, auth_token, dynamodb_table):
        """Test throughput when no events in last 24 hours."""
        now = datetime.utcnow()

        # Create old event (>24h ago)
        old_time = now - timedelta(hours=25)
        dynamodb_table.put_item(Item={
            "id": "old-event",
            "type": "test",
            "source": "test",
            "status": "delivered",
            "created_at": old_time.isoformat() + "Z",
            "updated_at": old_time.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        response = client.get(
            "/metrics/throughput",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_events_24h"] == 0
        assert data["events_per_minute"] == 0.0
        assert data["events_per_hour"] == 0.0
        assert data["time_range"] == "last_24_hours"

    def test_throughput_with_recent_events(self, client, auth_token, dynamodb_table):
        """Test throughput calculation with events in last 24 hours."""
        now = datetime.utcnow()

        # Create 100 events in the last 24 hours
        for i in range(100):
            created_time = now - timedelta(hours=i % 24)
            dynamodb_table.put_item(Item={
                "id": f"recent-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": created_time.isoformat() + "Z",
                "updated_at": created_time.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        response = client.get(
            "/metrics/throughput",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_events_24h"] == 100
        # 100 events / 1440 minutes = ~0.07 events/min
        assert data["events_per_minute"] == round(100 / 1440.0, 2)
        # 100 events / 24 hours = ~4.17 events/hour
        assert data["events_per_hour"] == round(100 / 24.0, 2)

    def test_throughput_excludes_old_events(self, client, auth_token, dynamodb_table):
        """Test that throughput only counts events from last 24 hours."""
        now = datetime.utcnow()

        # Create recent event (2 hours ago)
        recent_time = now - timedelta(hours=2)
        dynamodb_table.put_item(Item={
            "id": "recent",
            "type": "test",
            "source": "test",
            "status": "delivered",
            "created_at": recent_time.isoformat() + "Z",
            "updated_at": recent_time.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        # Create old event (26 hours ago)
        old_time = now - timedelta(hours=26)
        dynamodb_table.put_item(Item={
            "id": "old",
            "type": "test",
            "source": "test",
            "status": "delivered",
            "created_at": old_time.isoformat() + "Z",
            "updated_at": old_time.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        response = client.get(
            "/metrics/throughput",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_events_24h"] == 1  # Only recent event

    def test_throughput_includes_all_statuses(self, client, auth_token, dynamodb_table):
        """Test that throughput counts events regardless of status."""
        now = datetime.utcnow()

        # Create events with different statuses
        for i, status in enumerate(["pending", "delivered", "failed"]):
            dynamodb_table.put_item(Item={
                "id": f"status-{i}",
                "type": "test",
                "source": "test",
                "status": status,
                "created_at": (now - timedelta(hours=1)).isoformat() + "Z",
                "updated_at": (now - timedelta(hours=1)).isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 0 if status == "pending" else 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        response = client.get(
            "/metrics/throughput",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_events_24h"] == 3  # All statuses counted

    def test_throughput_caching(self, client, auth_token, dynamodb_table):
        """Test that throughput results are cached."""
        now = datetime.utcnow()

        dynamodb_table.put_item(Item={
            "id": "cache-tp-1",
            "type": "test",
            "source": "test",
            "status": "delivered",
            "created_at": (now - timedelta(hours=1)).isoformat() + "Z",
            "updated_at": (now - timedelta(hours=1)).isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        response1 = client.get(
            "/metrics/throughput",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        data1 = response1.json()
        assert data1["total_events_24h"] == 1

        # Add another event
        dynamodb_table.put_item(Item={
            "id": "cache-tp-2",
            "type": "test",
            "source": "test",
            "status": "delivered",
            "created_at": (now - timedelta(hours=2)).isoformat() + "Z",
            "updated_at": (now - timedelta(hours=2)).isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 1,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        # Should return cached result
        response2 = client.get(
            "/metrics/throughput",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        data2 = response2.json()
        assert data2["total_events_24h"] == 1  # Still cached


# ============================================================================
# TEST CLASS: /metrics/errors
# ============================================================================

class TestMetricsErrors:
    """Tests for GET /metrics/errors endpoint."""

    def test_errors_requires_authentication(self, client):
        """Test that /metrics/errors requires authentication."""
        response = client.get("/metrics/errors")
        assert response.status_code == 401

    def test_errors_with_no_events(self, client, auth_token):
        """Test error metrics when database is empty."""
        response = client.get(
            "/metrics/errors",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_errors"] == 0
        assert data["error_rate"] == 0.0
        assert data["failed_deliveries"] == 0
        assert data["pending_retries"] == 0

    def test_errors_with_only_successful_events(self, client, auth_token, dynamodb_table):
        """Test error metrics when all events are successful."""
        now = datetime.utcnow()

        for i in range(5):
            dynamodb_table.put_item(Item={
                "id": f"success-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        response = client.get(
            "/metrics/errors",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_errors"] == 0
        assert data["error_rate"] == 0.0
        assert data["failed_deliveries"] == 0
        assert data["pending_retries"] == 0

    def test_errors_with_failures(self, client, auth_token, dynamodb_table):
        """Test error metrics calculation with failures."""
        now = datetime.utcnow()

        # 8 delivered, 2 failed
        for i in range(8):
            dynamodb_table.put_item(Item={
                "id": f"delivered-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        for i in range(2):
            dynamodb_table.put_item(Item={
                "id": f"failed-{i}",
                "type": "test",
                "source": "test",
                "status": "failed",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 3,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        response = client.get(
            "/metrics/errors",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_errors"] == 2
        assert data["failed_deliveries"] == 2
        # Error rate = 2 / (8 + 2) * 100 = 20%
        assert data["error_rate"] == 20.0

    def test_errors_with_pending_retries(self, client, auth_token, dynamodb_table):
        """Test that pending events are counted as potential retries."""
        now = datetime.utcnow()

        # Create pending events
        for i in range(3):
            dynamodb_table.put_item(Item={
                "id": f"pending-{i}",
                "type": "test",
                "source": "test",
                "status": "pending",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 0,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        response = client.get(
            "/metrics/errors",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pending_retries"] == 3

    def test_errors_100_percent_failure_rate(self, client, auth_token, dynamodb_table):
        """Test error rate when all completed events failed."""
        now = datetime.utcnow()

        for i in range(5):
            dynamodb_table.put_item(Item={
                "id": f"fail-all-{i}",
                "type": "test",
                "source": "test",
                "status": "failed",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 3,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        response = client.get(
            "/metrics/errors",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error_rate"] == 100.0

    def test_errors_caching(self, client, auth_token, dynamodb_table):
        """Test that error metrics are cached."""
        now = datetime.utcnow()

        dynamodb_table.put_item(Item={
            "id": "cache-err-1",
            "type": "test",
            "source": "test",
            "status": "failed",
            "created_at": now.isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 3,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        response1 = client.get(
            "/metrics/errors",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        data1 = response1.json()

        # Add another failed event
        dynamodb_table.put_item(Item={
            "id": "cache-err-2",
            "type": "test",
            "source": "test",
            "status": "failed",
            "created_at": now.isoformat() + "Z",
            "updated_at": now.isoformat() + "Z",
            "payload": {},
            "delivery_attempts": 3,
            "ttl": int((now + timedelta(days=90)).timestamp())
        })

        # Should return cached result
        response2 = client.get(
            "/metrics/errors",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        data2 = response2.json()
        assert data2["total_errors"] == data1["total_errors"]


# ============================================================================
# TEST CLASS: Error Handling
# ============================================================================

class TestMetricsErrorHandling:
    """Tests for error handling in metrics endpoints."""

    @patch('main.table')
    def test_summary_handles_dynamodb_errors(self, mock_table, client, auth_token):
        """Test that DynamoDB errors are handled gracefully."""
        from botocore.exceptions import ClientError

        # Make table.scan raise a ClientError
        mock_table.scan.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "Service temporarily unavailable"}},
            "Scan"
        )

        response = client.get(
            "/metrics/summary",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 500
        assert "Failed to retrieve metrics" in response.json()["detail"]

    @patch('main.table')
    def test_latency_handles_dynamodb_errors(self, mock_table, client, auth_token):
        """Test latency endpoint error handling."""
        from botocore.exceptions import ClientError

        mock_table.scan.side_effect = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Throughput exceeded"}},
            "Scan"
        )

        response = client.get(
            "/metrics/latency",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 500

    @patch('main.table')
    def test_throughput_handles_dynamodb_errors(self, mock_table, client, auth_token):
        """Test throughput endpoint error handling."""
        from botocore.exceptions import ClientError

        mock_table.scan.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Internal error"}},
            "Scan"
        )

        response = client.get(
            "/metrics/throughput",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 500

    @patch('main.table')
    def test_errors_handles_dynamodb_errors(self, mock_table, client, auth_token):
        """Test errors endpoint error handling."""
        from botocore.exceptions import ClientError

        mock_table.scan.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}},
            "Scan"
        )

        response = client.get(
            "/metrics/errors",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 500
