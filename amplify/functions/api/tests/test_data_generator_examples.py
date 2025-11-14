"""
Examples demonstrating how to use the EventDataGenerator (Task 23.4)

This file provides practical examples of using the test data generation
utilities in your test files. These examples show common patterns and
use cases for generating test data.

Run these tests to verify the data generator works correctly:
    pytest tests/test_data_generator_examples.py -v
"""
import json
import os
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from moto import mock_aws
import boto3

# Import the data generator
from tests.generate_test_data import (
    EventDataGenerator,
    quick_realistic_data,
    quick_high_failure_data,
    quick_latency_data,
    quick_throughput_data,
)


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
    from main import app
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


# ============================================================================
# Example 1: Basic Realistic Dataset
# ============================================================================

def test_example_realistic_dataset(client, auth_token, dynamodb_table):
    """
    Example: Generate a realistic dataset for comprehensive metrics testing.

    This is the most common use case - generates events with typical
    distribution (85% delivered, 10% pending, 5% failed).
    """
    # Generate 500 events with realistic distribution
    generator = EventDataGenerator(dynamodb_table)
    events = generator.generate_realistic_dataset(count=500)

    assert len(events) == 500

    # Test metrics with this data
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/metrics/summary", headers=headers)

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 500
    assert data["delivered"] > data["failed"]  # Should have more successes
    assert data["pending"] >= 0


# ============================================================================
# Example 2: Quick Helper Functions
# ============================================================================

def test_example_quick_helpers(client, auth_token, dynamodb_table):
    """
    Example: Use quick helper functions for rapid test data creation.

    These are convenience functions for common scenarios.
    """
    # Quick high failure scenario (clear table first)
    quick_high_failure_data(dynamodb_table, delivered=20, failed=80)

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/metrics/errors", headers=headers)

    data = response.json()
    # Error rate = 80/(20+80) = 80%
    assert data["failed_deliveries"] == 80
    assert data["error_rate"] == 80.0  # Exact value


# ============================================================================
# Example 3: Latency Testing
# ============================================================================

def test_example_latency_percentiles(client, auth_token, dynamodb_table):
    """
    Example: Generate events with specific latencies for percentile testing.

    This is useful when you need to verify percentile calculations.
    """
    generator = EventDataGenerator(dynamodb_table)

    # Create events with known latencies: 1s, 2s, 3s, ..., 100s
    latencies = list(range(1, 101))
    events = generator.generate_latency_test_dataset(latencies=latencies)

    assert len(events) == 100

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/metrics/latency", headers=headers)

    data = response.json()
    assert data["sample_size"] == 100

    # P50 should be around 50s (median)
    assert 45 <= data["p50"] <= 55

    # P95 should be around 95s
    assert 90 <= data["p95"] <= 100


# ============================================================================
# Example 4: Throughput Testing
# ============================================================================

def test_example_throughput_distribution(client, auth_token, dynamodb_table):
    """
    Example: Generate time-distributed events for throughput testing.

    Creates events evenly distributed over time to test throughput calculations.
    """
    generator = EventDataGenerator(dynamodb_table)

    # Generate 10 events per hour for 24 hours (240 total)
    events = generator.generate_throughput_dataset(
        events_per_hour=10,
        hours=24,
        include_old_events=False
    )

    assert len(events) == 240

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/metrics/throughput", headers=headers)

    data = response.json()
    assert data["total_events_24h"] == 240
    assert data["events_per_hour"] == 10.0


# ============================================================================
# Example 5: High Failure Scenario
# ============================================================================

def test_example_high_failure_rate(client, auth_token, dynamodb_table):
    """
    Example: Generate high-failure scenario for error testing.

    Useful for testing dashboard behavior under poor conditions.
    """
    generator = EventDataGenerator(dynamodb_table)

    events = generator.generate_high_failure_scenario(
        delivered=10,
        failed=90,
        pending=5
    )

    assert len(events) == 105

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/metrics/errors", headers=headers)

    data = response.json()
    assert data["failed_deliveries"] == 90
    assert data["error_rate"] == 90.0  # 90% error rate


# ============================================================================
# Example 6: Custom Event Creation
# ============================================================================

def test_example_custom_events(client, auth_token, dynamodb_table):
    """
    Example: Create events with custom properties.

    Shows how to create specific events for edge case testing.
    """
    generator = EventDataGenerator(dynamodb_table)
    now = datetime.utcnow()

    # Create a specific delivered event with 5 second latency
    event1 = generator.create_event(
        status="delivered",
        created_at=now - timedelta(seconds=5),
        updated_at=now,
        latency_seconds=5.0,
        event_type="user.signup",
        event_source="web",
    )

    # Create a failed event with error message
    event2 = generator.create_event(
        status="failed",
        created_at=now - timedelta(minutes=10),
        error_message="Webhook endpoint returned 500",
        event_type="payment.failed",
        delivery_attempts=3,
    )

    # Create a pending event
    event3 = generator.create_event(
        status="pending",
        created_at=now - timedelta(minutes=2),
        event_type="data.sync",
    )

    events = generator.bulk_insert_events([event1, event2, event3])
    assert len(events) == 3

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/metrics/summary", headers=headers)

    data = response.json()
    assert data["total"] == 3
    assert data["pending"] == 1
    assert data["delivered"] == 1
    assert data["failed"] == 1


# ============================================================================
# Example 7: Large Dataset for Load Testing
# ============================================================================

def test_example_large_dataset(client, auth_token, dynamodb_table):
    """
    Example: Generate large dataset for load/stress testing.

    Creates 1000+ events for testing system behavior under load.
    """
    generator = EventDataGenerator(dynamodb_table)

    # Generate 1000 events (batched internally for efficiency)
    generator.generate_large_dataset(
        count=1000,
        delivered_pct=0.80,
        pending_pct=0.10,
        failed_pct=0.10,
    )

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/metrics/summary", headers=headers)

    data = response.json()
    assert data["total"] == 1000
    assert 700 <= data["delivered"] <= 900  # Around 80%
    assert data["pending"] >= 50  # Around 10%
    assert data["failed"] >= 50  # Around 10%


# ============================================================================
# Example 8: Empty State Testing
# ============================================================================

def test_example_empty_state(client, auth_token, dynamodb_table):
    """
    Example: Test metrics with no data (empty state).

    Ensures all endpoints handle empty databases gracefully.
    """
    generator = EventDataGenerator(dynamodb_table)
    events = generator.generate_empty_state()

    assert len(events) == 0

    headers = {"Authorization": f"Bearer {auth_token}"}

    # All metrics should return zero values
    summary = client.get("/metrics/summary", headers=headers).json()
    latency = client.get("/metrics/latency", headers=headers).json()
    throughput = client.get("/metrics/throughput", headers=headers).json()
    errors = client.get("/metrics/errors", headers=headers).json()

    assert summary["total"] == 0
    assert latency["sample_size"] == 0
    assert throughput["total_events_24h"] == 0
    assert errors["total_errors"] == 0


# ============================================================================
# Example 9: Single Event Testing
# ============================================================================

def test_example_single_event(client, auth_token, dynamodb_table):
    """
    Example: Test metrics with minimal data (single event).

    Useful for testing edge cases and calculations with n=1.
    """
    generator = EventDataGenerator(dynamodb_table)

    events = generator.generate_single_event(
        status="delivered",
        latency_seconds=10.0
    )

    assert len(events) == 1

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/metrics/latency", headers=headers)

    data = response.json()
    assert data["sample_size"] == 1
    # All percentiles should be the same with n=1
    assert data["p50"] == data["p95"] == data["p99"]


# ============================================================================
# Example 10: Percentile Distribution Testing
# ============================================================================

def test_example_percentile_distribution(client, auth_token, dynamodb_table):
    """
    Example: Generate evenly distributed latencies for percentile accuracy.

    Creates a uniform distribution to verify percentile math.
    """
    generator = EventDataGenerator(dynamodb_table)

    # Generate 100 events with latencies from 1 to 100 seconds
    events = generator.generate_percentile_test_dataset(
        count=100,
        min_latency=1.0,
        max_latency=100.0
    )

    assert len(events) == 100

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/metrics/latency", headers=headers)

    data = response.json()

    # With uniform distribution:
    # P50 ≈ 50, P95 ≈ 95, P99 ≈ 99
    assert 45 <= data["p50"] <= 55
    assert 90 <= data["p95"] <= 100
    assert 95 <= data["p99"] <= 100


# ============================================================================
# Example 11: GSI Testing (Status Index)
# ============================================================================

def test_example_gsi_dataset(dynamodb_table):
    """
    Example: Generate data for GSI (Global Secondary Index) testing.

    Creates events with proper last_attempt_at values for GSI queries.
    """
    generator = EventDataGenerator(dynamodb_table)

    events = generator.generate_gsi_test_dataset(count_per_status=50)

    assert len(events) == 150  # 50 per status (pending, delivered, failed)

    # Verify GSI fields are populated
    delivered_count = sum(1 for e in events if e["status"] == "delivered")
    failed_count = sum(1 for e in events if e["status"] == "failed")

    assert delivered_count == 50
    assert failed_count == 50

    # All delivered/failed should have last_attempt_at
    for event in events:
        if event["status"] in ["delivered", "failed"]:
            assert "last_attempt_at" in event
            assert event["last_attempt_at"] is not None


# ============================================================================
# Example 12: Time-Based Filtering
# ============================================================================

def test_example_time_filtering(client, auth_token, dynamodb_table):
    """
    Example: Test time-based filtering with old and recent events.

    Generates events both inside and outside the 24-hour window.
    """
    generator = EventDataGenerator(dynamodb_table)

    # Generate throughput data with old events
    events = generator.generate_throughput_dataset(
        events_per_hour=10,
        hours=24,
        include_old_events=True  # Also creates events >24h old
    )

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/metrics/throughput", headers=headers)

    data = response.json()

    # Should only count events from last 24 hours
    assert data["total_events_24h"] == 240  # 10/hour * 24 hours
    # Old events should not be counted


# ============================================================================
# Example 13: Reusable Fixture Pattern
# ============================================================================

@pytest.fixture
def realistic_events(dynamodb_table):
    """
    Reusable fixture for realistic event data.

    This pattern allows you to create fixtures for common datasets.
    """
    generator = EventDataGenerator(dynamodb_table)
    return generator.generate_realistic_dataset(count=100)


def test_example_using_fixture(client, auth_token, realistic_events):
    """
    Example: Use a fixture for cleaner test code.

    The realistic_events fixture provides data automatically.
    """
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/metrics/summary", headers=headers)

    data = response.json()
    assert data["total"] == 100


# ============================================================================
# Documentation Test - Verify All Generator Methods Work
# ============================================================================

def test_all_generator_methods_work(dynamodb_table):
    """
    Comprehensive test to verify all generator methods execute successfully.
    """
    generator = EventDataGenerator(dynamodb_table)

    # Test each method
    methods_to_test = [
        lambda: generator.generate_realistic_dataset(count=10),
        lambda: generator.generate_high_failure_scenario(delivered=5, failed=5),
        lambda: generator.generate_latency_test_dataset([1, 2, 3, 4, 5]),
        lambda: generator.generate_throughput_dataset(events_per_hour=2, hours=2),
        lambda: generator.generate_empty_state(),
        lambda: generator.generate_single_event(),
        lambda: generator.generate_percentile_test_dataset(count=10),
        lambda: generator.generate_gsi_test_dataset(count_per_status=5),
    ]

    for method in methods_to_test:
        result = method()
        assert result is not None  # All methods should return something
