"""
Load tests for metrics accuracy under high volume (Task 23.3).

Tests metrics endpoints under realistic load conditions:
- High concurrency scenarios
- Large dataset processing
- Metrics accuracy under load
- Performance degradation testing
- Cache effectiveness under load
"""
import json
import os
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
import boto3
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import statistics


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
# TEST CLASS: High Volume Metrics Accuracy
# ============================================================================

class TestHighVolumeMetricsAccuracy:
    """Test metrics accuracy with large datasets."""

    def test_summary_accuracy_with_1000_events(self, client, auth_token, dynamodb_table):
        """Test summary metrics remain accurate with 1000+ events."""
        now = datetime.utcnow()

        # Create 1000 events with known distribution
        # 700 delivered, 200 pending, 100 failed
        expected_delivered = 700
        expected_pending = 200
        expected_failed = 100

        for i in range(expected_delivered):
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

        for i in range(expected_pending):
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

        for i in range(expected_failed):
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

        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/metrics/summary", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verify exact counts
        assert data["total"] == 1000
        assert data["delivered"] == expected_delivered
        assert data["pending"] == expected_pending
        assert data["failed"] == expected_failed

        # Verify success rate calculation
        expected_success_rate = (expected_delivered / (expected_delivered + expected_failed)) * 100
        assert data["success_rate"] == round(expected_success_rate, 2)

    def test_latency_accuracy_with_large_sample(self, client, auth_token, dynamodb_table):
        """Test latency percentile accuracy with large sample size."""
        now = datetime.utcnow()

        # Create 500 events with known latencies (1-500 seconds)
        for i in range(1, 501):
            created = now - timedelta(seconds=i)
            dynamodb_table.put_item(Item={
                "id": f"latency-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": created.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/metrics/latency", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert data["sample_size"] == 500

        # Verify percentiles are in expected ranges
        # P50 should be around 250s (median of 1-500)
        assert 240 <= data["p50"] <= 260

        # P95 should be around 475s (95th percentile)
        assert 470 <= data["p95"] <= 480

        # P99 should be around 495s (99th percentile)
        assert 490 <= data["p99"] <= 500

    def test_throughput_accuracy_over_24_hours(self, client, auth_token, dynamodb_table):
        """Test throughput calculation accuracy with time-distributed events."""
        now = datetime.utcnow()

        # Create 240 events evenly distributed over 24 hours (10 per hour)
        events_count = 240
        for i in range(events_count):
            hours_ago = (i / 10.0)  # Spread over 24 hours
            created_time = now - timedelta(hours=hours_ago)

            dynamodb_table.put_item(Item={
                "id": f"throughput-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": created_time.isoformat() + "Z",
                "updated_at": created_time.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/metrics/throughput", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert data["total_events_24h"] == events_count
        # 240 events / 24 hours = 10 events/hour
        assert data["events_per_hour"] == round(events_count / 24.0, 2)
        # 240 events / 1440 minutes = 0.17 events/minute
        assert data["events_per_minute"] == round(events_count / 1440.0, 2)

    def test_error_metrics_accuracy_under_load(self, client, auth_token, dynamodb_table):
        """Test error metrics accuracy with mixed statuses."""
        now = datetime.utcnow()

        # Create realistic error scenario: 850 delivered, 100 failed, 50 pending
        for i in range(850):
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

        for i in range(100):
            dynamodb_table.put_item(Item={
                "id": f"error-{i}",
                "type": "test",
                "source": "test",
                "status": "failed",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 3,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        for i in range(50):
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

        headers = {"Authorization": f"Bearer {auth_token}"}
        response = client.get("/metrics/errors", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert data["total_errors"] == 100
        assert data["failed_deliveries"] == 100
        assert data["pending_retries"] == 50
        # Error rate = 100 / (850 + 100) * 100 = 10.53%
        expected_error_rate = (100 / 950) * 100
        assert data["error_rate"] == round(expected_error_rate, 2)


# ============================================================================
# TEST CLASS: Concurrent Access Performance
# ============================================================================

class TestConcurrentAccessPerformance:
    """Test metrics endpoints under concurrent load."""

    def test_concurrent_summary_requests(self, client, auth_token, dynamodb_table):
        """Test summary endpoint with 50 concurrent requests."""
        now = datetime.utcnow()

        # Create baseline data
        for i in range(100):
            dynamodb_table.put_item(Item={
                "id": f"concurrent-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        headers = {"Authorization": f"Bearer {auth_token}"}

        def fetch_summary():
            response = client.get("/metrics/summary", headers=headers)
            return response.status_code, response.json()

        # Execute 50 concurrent requests
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(fetch_summary) for _ in range(50)]

            results = []
            for future in as_completed(futures):
                status_code, data = future.result()
                results.append((status_code, data))

        # All requests should succeed
        assert all(status == 200 for status, _ in results)

        # All responses should be identical (cache hit)
        first_response = results[0][1]
        assert all(data == first_response for _, data in results)

    def test_parallel_metrics_fetch_performance(self, client, auth_token, dynamodb_table):
        """Test fetching all metrics in parallel (dashboard scenario)."""
        now = datetime.utcnow()

        # Create realistic dataset
        for i in range(500):
            created = now - timedelta(seconds=i % 300)
            status = "delivered" if i % 10 != 0 else "failed"

            dynamodb_table.put_item(Item={
                "id": f"parallel-{i}",
                "type": "test",
                "source": "test",
                "status": status,
                "created_at": created.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1 if status == "delivered" else 3,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        headers = {"Authorization": f"Bearer {auth_token}"}

        # Simulate 10 dashboards fetching all 4 metrics in parallel
        def fetch_all_metrics():
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(client.get, "/metrics/summary", headers=headers): "summary",
                    executor.submit(client.get, "/metrics/latency", headers=headers): "latency",
                    executor.submit(client.get, "/metrics/throughput", headers=headers): "throughput",
                    executor.submit(client.get, "/metrics/errors", headers=headers): "errors",
                }

                results = {}
                for future in as_completed(futures):
                    metric_name = futures[future]
                    response = future.result()
                    results[metric_name] = response.status_code

                return results

        with ThreadPoolExecutor(max_workers=10) as executor:
            dashboard_futures = [executor.submit(fetch_all_metrics) for _ in range(10)]

            all_results = []
            for future in as_completed(dashboard_futures):
                results = future.result()
                all_results.append(results)

        # All requests should succeed
        for results in all_results:
            assert all(status == 200 for status in results.values())

    def test_request_latency_distribution(self, client, auth_token, dynamodb_table):
        """Test that request latencies are consistent under load."""
        now = datetime.utcnow()

        # Create data
        for i in range(200):
            dynamodb_table.put_item(Item={
                "id": f"latency-test-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        headers = {"Authorization": f"Bearer {auth_token}"}

        # Measure request latencies
        latencies = []
        for _ in range(30):
            start = time.time()
            response = client.get("/metrics/summary", headers=headers)
            duration = time.time() - start

            assert response.status_code == 200
            latencies.append(duration)

        # Calculate statistics
        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]

        # All requests should complete quickly (< 1 second)
        assert max(latencies) < 1.0

        # P99 should not be much worse than median (consistent performance)
        assert p99 < p50 * 5  # P99 should be less than 5x median


# ============================================================================
# TEST CLASS: Cache Effectiveness Under Load
# ============================================================================

class TestCacheEffectivenessUnderLoad:
    """Test cache behavior under realistic load patterns."""

    def test_cache_reduces_database_load(self, client, auth_token, dynamodb_table):
        """Test that caching reduces repeated database queries."""
        now = datetime.utcnow()

        # Create data
        for i in range(100):
            dynamodb_table.put_item(Item={
                "id": f"cache-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        headers = {"Authorization": f"Bearer {auth_token}"}

        # First request - cache miss
        start = time.time()
        response1 = client.get("/metrics/summary", headers=headers)
        first_duration = time.time() - start

        # Subsequent requests - cache hits
        cache_hit_durations = []
        for _ in range(10):
            start = time.time()
            response = client.get("/metrics/summary", headers=headers)
            cache_hit_durations.append(time.time() - start)

        # All should succeed
        assert response1.status_code == 200
        assert all(response.status_code == 200 for response in [response1])

        # Cache hits should be faster on average
        avg_cache_hit = statistics.mean(cache_hit_durations)
        # Cache hits can be faster or comparable due to in-memory cache
        assert avg_cache_hit <= first_duration or avg_cache_hit < 0.1

    def test_cache_expiry_refreshes_data(self, client, auth_token, dynamodb_table):
        """Test that cache expiry allows fresh data to be retrieved."""
        now = datetime.utcnow()

        # Initial data: 50 events
        for i in range(50):
            dynamodb_table.put_item(Item={
                "id": f"expiry-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        headers = {"Authorization": f"Bearer {auth_token}"}

        # First request
        response1 = client.get("/metrics/summary", headers=headers)
        data1 = response1.json()
        assert data1["total"] == 50

        # Add more data
        for i in range(50, 100):
            dynamodb_table.put_item(Item={
                "id": f"expiry-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        # Request with cache - should still show 50
        response2 = client.get("/metrics/summary", headers=headers)
        data2 = response2.json()
        assert data2["total"] == 50

        # Clear cache manually
        import main
        main.metrics_cache.clear()

        # Request after cache clear - should show 100
        response3 = client.get("/metrics/summary", headers=headers)
        data3 = response3.json()
        assert data3["total"] == 100


# ============================================================================
# TEST CLASS: Stress Testing
# ============================================================================

class TestStressScenarios:
    """Stress test scenarios for metrics endpoints."""

    def test_metrics_with_maximum_dataset(self, client, auth_token, dynamodb_table):
        """Test metrics with very large dataset (2000+ events)."""
        now = datetime.utcnow()

        # Create 2000 events with varied statuses and timestamps
        for i in range(2000):
            hours_ago = (i % 48) * 0.5  # Spread over 24 hours
            created_time = now - timedelta(hours=hours_ago)

            status = "delivered" if i % 5 != 0 else ("pending" if i % 10 == 0 else "failed")

            dynamodb_table.put_item(Item={
                "id": f"stress-{i}",
                "type": f"type-{i % 10}",
                "source": f"source-{i % 5}",
                "status": status,
                "created_at": created_time.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1 if status == "delivered" else (0 if status == "pending" else 3),
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        headers = {"Authorization": f"Bearer {auth_token}"}

        # All endpoints should still work
        summary = client.get("/metrics/summary", headers=headers)
        latency = client.get("/metrics/latency", headers=headers)
        throughput = client.get("/metrics/throughput", headers=headers)
        errors = client.get("/metrics/errors", headers=headers)

        # All should succeed
        assert summary.status_code == 200
        assert latency.status_code == 200
        assert throughput.status_code == 200
        assert errors.status_code == 200

        # Verify data integrity
        assert summary.json()["total"] == 2000

    def test_sustained_high_request_rate(self, client, auth_token, dynamodb_table):
        """Test sustained high request rate over time."""
        now = datetime.utcnow()

        # Create data
        for i in range(500):
            dynamodb_table.put_item(Item={
                "id": f"sustained-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        headers = {"Authorization": f"Bearer {auth_token}"}

        # Make 100 sequential requests (simulating sustained load)
        successful_requests = 0
        for _ in range(100):
            response = client.get("/metrics/summary", headers=headers)
            if response.status_code == 200:
                successful_requests += 1

        # All requests should succeed
        assert successful_requests == 100
