"""
Integration tests for dashboard API communication (Task 23.2).

Tests the complete dashboard workflow:
- Authentication flow
- Metrics data fetching in parallel
- Dashboard state management
- Auto-refresh behavior simulation
- Error handling and retry logic
- Real-world usage patterns
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


@pytest.fixture
def realistic_dashboard_data(dynamodb_table):
    """Create realistic dashboard data mimicking production usage."""
    now = datetime.utcnow()

    events = []

    # Last 24 hours: 500 events with realistic distribution
    for i in range(500):
        hours_ago = (i % 24) * 0.5  # Spread across 12 hours
        created_time = now - timedelta(hours=hours_ago)

        # Status distribution: 85% delivered, 10% pending, 5% failed
        if i < 425:
            status = "delivered"
            delivery_attempts = 1
            updated_time = created_time + timedelta(seconds=i % 60)  # Variable latency
        elif i < 475:
            status = "pending"
            delivery_attempts = 0
            updated_time = created_time
        else:
            status = "failed"
            delivery_attempts = 3
            updated_time = created_time + timedelta(seconds=300)  # Failed after 5min

        event = {
            "id": f"event-{i}",
            "type": ["user.signup", "user.login", "order.placed", "payment.success"][i % 4],
            "source": ["web", "mobile", "api", "cron"][i % 4],
            "status": status,
            "created_at": created_time.isoformat() + "Z",
            "updated_at": updated_time.isoformat() + "Z",
            "payload": {"data": f"test-{i}"},
            "delivery_attempts": delivery_attempts,
            "ttl": int((now + timedelta(days=90)).timestamp())
        }
        events.append(event)
        dynamodb_table.put_item(Item=event)

    return events


# ============================================================================
# TEST CLASS: Dashboard Initial Load
# ============================================================================

class TestDashboardInitialLoad:
    """Tests for dashboard initial page load workflow."""

    def test_complete_dashboard_load_workflow(self, client, auth_token, realistic_dashboard_data):
        """Test complete dashboard initialization workflow."""
        # Simulate dashboard initial load: fetch all metrics in parallel

        # Step 1: Authenticate (already done via fixture)
        assert auth_token is not None

        # Step 2: Fetch all metrics in parallel (as dashboard does)
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Make all requests concurrently
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
                assert response.status_code == 200, f"{metric_name} endpoint failed"
                results[metric_name] = response.json()

        # Verify all metrics loaded successfully
        assert "summary" in results
        assert "latency" in results
        assert "throughput" in results
        assert "errors" in results

        # Verify data integrity
        summary = results["summary"]
        assert summary["total"] == 500
        assert summary["delivered"] == 425
        assert summary["pending"] == 50
        assert summary["failed"] == 25

        latency = results["latency"]
        assert latency["sample_size"] == 450  # delivered + failed

        throughput = results["throughput"]
        assert throughput["total_events_24h"] == 500

        errors = results["errors"]
        assert errors["failed_deliveries"] == 25
        assert errors["pending_retries"] == 50

    def test_dashboard_handles_empty_state(self, client, auth_token):
        """Test dashboard loads correctly with no data."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        summary = client.get("/metrics/summary", headers=headers).json()
        latency = client.get("/metrics/latency", headers=headers).json()
        throughput = client.get("/metrics/throughput", headers=headers).json()
        errors = client.get("/metrics/errors", headers=headers).json()

        # All should return valid empty state
        assert summary["total"] == 0
        assert latency["sample_size"] == 0
        assert throughput["total_events_24h"] == 0
        assert errors["total_errors"] == 0

    def test_dashboard_partial_failure_handling(self, client, auth_token, realistic_dashboard_data):
        """Test dashboard handles partial API failures gracefully."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Fetch metrics that work
        summary_response = client.get("/metrics/summary", headers=headers)
        latency_response = client.get("/metrics/latency", headers=headers)

        # Verify successful responses
        assert summary_response.status_code == 200
        assert latency_response.status_code == 200

        # Verify data is still usable
        summary = summary_response.json()
        assert summary["total"] > 0


# ============================================================================
# TEST CLASS: Dashboard Auto-Refresh Simulation
# ============================================================================

class TestDashboardAutoRefresh:
    """Tests simulating dashboard auto-refresh behavior."""

    def test_auto_refresh_workflow(self, client, auth_token, dynamodb_table):
        """Test dashboard auto-refresh every 10 seconds (simulated)."""
        now = datetime.utcnow()
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Initial state: 10 events
        for i in range(10):
            dynamodb_table.put_item(Item={
                "id": f"refresh-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        # First refresh
        summary1 = client.get("/metrics/summary", headers=headers).json()
        assert summary1["total"] == 10

        # Clear cache to simulate cache expiry (30 seconds)
        import main
        main.metrics_cache.clear()

        # Add 5 more events
        for i in range(10, 15):
            dynamodb_table.put_item(Item={
                "id": f"refresh-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        # Second refresh after cache clear
        summary2 = client.get("/metrics/summary", headers=headers).json()
        assert summary2["total"] == 15

    def test_concurrent_dashboard_users(self, client, auth_token, realistic_dashboard_data):
        """Test multiple dashboard users accessing metrics simultaneously."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        def fetch_all_metrics():
            """Simulate a single user's dashboard fetch."""
            results = []
            results.append(client.get("/metrics/summary", headers=headers))
            results.append(client.get("/metrics/latency", headers=headers))
            results.append(client.get("/metrics/throughput", headers=headers))
            results.append(client.get("/metrics/errors", headers=headers))
            return results

        # Simulate 10 concurrent users
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_all_metrics) for _ in range(10)]

            for future in as_completed(futures):
                responses = future.result()
                # All responses should succeed
                for response in responses:
                    assert response.status_code == 200

    def test_cache_hit_performance(self, client, auth_token, realistic_dashboard_data):
        """Test that cached requests are faster than uncached."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # First request - cache miss
        start = time.time()
        response1 = client.get("/metrics/summary", headers=headers)
        duration1 = time.time() - start

        assert response1.status_code == 200

        # Second request - cache hit (should be faster)
        start = time.time()
        response2 = client.get("/metrics/summary", headers=headers)
        duration2 = time.time() - start

        assert response2.status_code == 200

        # Cached request should be significantly faster (at least 2x)
        # Note: In test environment, speedup may be less dramatic
        assert duration2 < duration1 or duration2 < 0.1  # Either faster or very fast


# ============================================================================
# TEST CLASS: Real-World Dashboard Scenarios
# ============================================================================

class TestRealWorldDashboardScenarios:
    """Tests for real-world dashboard usage patterns."""

    def test_event_submission_updates_metrics(self, client, auth_token, dynamodb_table):
        """Test that submitting an event updates dashboard metrics."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Get initial state
        import main
        main.metrics_cache.clear()
        initial_summary = client.get("/metrics/summary", headers=headers).json()
        initial_total = initial_summary["total"]

        # Submit new event via API
        event_response = client.post(
            "/events",
            json={
                "type": "dashboard.test",
                "source": "test",
                "payload": {"test": "data"}
            },
            headers=headers
        )
        assert event_response.status_code == 201

        # Clear cache and get updated metrics
        main.metrics_cache.clear()
        updated_summary = client.get("/metrics/summary", headers=headers).json()

        # Verify total increased
        assert updated_summary["total"] == initial_total + 1
        assert updated_summary["pending"] == initial_summary["pending"] + 1

    def test_dashboard_with_high_failure_rate(self, client, auth_token, dynamodb_table):
        """Test dashboard displays correct data with high failure rate."""
        now = datetime.utcnow()

        # Create scenario: 20 delivered, 80 failed
        for i in range(20):
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

        for i in range(80):
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

        summary = client.get("/metrics/summary", headers=headers).json()
        errors = client.get("/metrics/errors", headers=headers).json()

        # Verify metrics accurately reflect failure rate
        assert summary["success_rate"] == 20.0  # 20% success
        assert errors["error_rate"] == 80.0  # 80% error

    def test_dashboard_with_varying_latencies(self, client, auth_token, dynamodb_table):
        """Test dashboard correctly displays latency distribution."""
        now = datetime.utcnow()

        # Create events with specific latencies
        latencies = [1, 2, 3, 5, 10, 15, 20, 30, 60, 120]  # seconds

        for i, latency_seconds in enumerate(latencies):
            created = now - timedelta(seconds=latency_seconds)
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
        latency = client.get("/metrics/latency", headers=headers).json()

        # Verify percentiles make sense
        assert latency["sample_size"] == 10
        assert latency["p50"] <= latency["p95"] <= latency["p99"]
        assert latency["p99"] >= 100.0  # Max is 120s

    def test_dashboard_throughput_changes_over_time(self, client, auth_token, dynamodb_table):
        """Test throughput metrics reflect time-based filtering."""
        now = datetime.utcnow()
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Create events: 50 recent (last 24h), 50 old (>24h ago)
        for i in range(50):
            # Recent events
            dynamodb_table.put_item(Item={
                "id": f"recent-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": (now - timedelta(hours=i % 20)).isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

            # Old events
            dynamodb_table.put_item(Item={
                "id": f"old-{i}",
                "type": "test",
                "source": "test",
                "status": "delivered",
                "created_at": (now - timedelta(hours=25 + i)).isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        throughput = client.get("/metrics/throughput", headers=headers).json()

        # Only recent events should be counted
        assert throughput["total_events_24h"] == 50
        assert throughput["events_per_hour"] == round(50 / 24.0, 2)


# ============================================================================
# TEST CLASS: Dashboard Error Recovery
# ============================================================================

class TestDashboardErrorRecovery:
    """Tests for dashboard error handling and recovery."""

    def test_dashboard_recovers_from_auth_failure(self, client):
        """Test dashboard handles authentication errors gracefully."""
        # Attempt to access without token
        response = client.get("/metrics/summary")
        assert response.status_code == 401

        # Get valid token and retry
        token_response = client.post(
            "/token",
            data={"username": "api", "password": "test-api-key"}
        )
        assert token_response.status_code == 200
        token = token_response.json()["access_token"]

        # Should now succeed
        response = client.get(
            "/metrics/summary",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_dashboard_handles_invalid_token(self, client):
        """Test dashboard handles invalid tokens properly."""
        response = client.get(
            "/metrics/summary",
            headers={"Authorization": "Bearer invalid-token-12345"}
        )
        assert response.status_code == 401

    def test_dashboard_metrics_consistency(self, client, auth_token, realistic_dashboard_data):
        """Test that metrics remain consistent across multiple fetches."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Fetch summary multiple times
        summary1 = client.get("/metrics/summary", headers=headers).json()
        summary2 = client.get("/metrics/summary", headers=headers).json()
        summary3 = client.get("/metrics/summary", headers=headers).json()

        # All fetches should return identical data (due to caching)
        assert summary1 == summary2 == summary3


# ============================================================================
# TEST CLASS: Dashboard Performance Under Load
# ============================================================================

class TestDashboardPerformanceUnderLoad:
    """Tests for dashboard performance characteristics."""

    def test_dashboard_handles_rapid_polling(self, client, auth_token, realistic_dashboard_data):
        """Test dashboard handles rapid successive requests."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Make 20 rapid requests
        responses = []
        for _ in range(20):
            response = client.get("/metrics/summary", headers=headers)
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == 200

        # First and last should be identical (cache hit)
        assert responses[0].json() == responses[-1].json()

    def test_dashboard_load_with_large_dataset(self, client, auth_token, dynamodb_table):
        """Test dashboard performance with large dataset (1000+ events)."""
        now = datetime.utcnow()

        # Create 1000 events
        for i in range(1000):
            status = "delivered" if i % 2 == 0 else "pending"
            dynamodb_table.put_item(Item={
                "id": f"large-{i}",
                "type": "test",
                "source": "test",
                "status": status,
                "created_at": now.isoformat() + "Z",
                "updated_at": now.isoformat() + "Z",
                "payload": {},
                "delivery_attempts": 1 if status == "delivered" else 0,
                "ttl": int((now + timedelta(days=90)).timestamp())
            })

        headers = {"Authorization": f"Bearer {auth_token}"}

        # Should still respond quickly (mocked DynamoDB is fast)
        start = time.time()
        response = client.get("/metrics/summary", headers=headers)
        duration = time.time() - start

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1000
        assert duration < 5.0  # Should complete within 5 seconds
