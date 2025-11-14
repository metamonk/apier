# Test Data Generator Guide

## Overview

The Test Data Generator (`generate_test_data.py`) provides comprehensive utilities for creating realistic test data for metrics endpoint testing. It simplifies the creation of DynamoDB event items with various characteristics for testing different scenarios.

## Quick Start

### Basic Usage

```python
from tests.generate_test_data import EventDataGenerator

# Initialize with your DynamoDB table
generator = EventDataGenerator(dynamodb_table)

# Generate 500 realistic events
events = generator.generate_realistic_dataset(count=500)
```

### Quick Helper Functions

For rapid prototyping, use the convenience functions:

```python
from tests.generate_test_data import (
    quick_realistic_data,
    quick_high_failure_data,
    quick_latency_data,
    quick_throughput_data,
)

# Generate realistic data
events = quick_realistic_data(dynamodb_table, count=500)

# Generate high-failure scenario
events = quick_high_failure_data(dynamodb_table, delivered=20, failed=80)

# Generate specific latencies
events = quick_latency_data(dynamodb_table, latencies=[1, 5, 10, 30, 60])

# Generate throughput test data
events = quick_throughput_data(dynamodb_table, events_per_hour=10, hours=24)
```

## Available Generators

### 1. Realistic Dataset

Generates events with typical production distribution (85% delivered, 10% pending, 5% failed).

```python
events = generator.generate_realistic_dataset(
    count=500,              # Total number of events
    hours_ago_range=12,     # Spread events across 12 hours
)
```

**Use Cases:**
- General metrics testing
- Dashboard integration tests
- Baseline performance testing

### 2. High Failure Scenario

Creates a dataset with elevated failure rates for error testing.

```python
events = generator.generate_high_failure_scenario(
    delivered=20,   # Successful deliveries
    failed=80,      # Failed deliveries
    pending=10,     # Pending events
)
```

**Use Cases:**
- Error metrics testing
- Dashboard behavior under poor conditions
- Alert threshold testing

### 3. Latency Test Dataset

Generates events with specific latency values for percentile accuracy testing.

```python
events = generator.generate_latency_test_dataset(
    latencies=[1, 2, 5, 10, 30, 60, 120],  # Specific latencies in seconds
    status="delivered",                     # Can be "delivered" or "failed"
)
```

**Use Cases:**
- Percentile calculation verification (P50, P95, P99)
- Latency distribution testing
- Performance benchmarking

### 4. Throughput Dataset

Creates time-distributed events for throughput calculation testing.

```python
events = generator.generate_throughput_dataset(
    events_per_hour=10,       # Events per hour
    hours=24,                 # Time range
    include_old_events=False, # Include events >24h old
)
```

**Use Cases:**
- Throughput metrics testing
- Time-based filtering verification
- Rate calculation testing

### 5. Large Dataset

Generates very large datasets for load and stress testing.

```python
generator.generate_large_dataset(
    count=2000,           # Total events
    delivered_pct=0.80,   # 80% delivered
    pending_pct=0.10,     # 10% pending
    failed_pct=0.10,      # 10% failed
)
```

**Use Cases:**
- Load testing
- Performance degradation testing
- Cache effectiveness testing
- DynamoDB pagination testing

### 6. Percentile Test Dataset

Creates uniformly distributed latencies for percentile math verification.

```python
events = generator.generate_percentile_test_dataset(
    count=100,           # Number of events
    min_latency=1.0,     # Minimum latency (seconds)
    max_latency=100.0,   # Maximum latency (seconds)
)
```

**Use Cases:**
- Percentile accuracy testing
- Statistical calculation verification
- Algorithm validation

### 7. GSI Test Dataset

Generates events optimized for Global Secondary Index testing.

```python
events = generator.generate_gsi_test_dataset(
    count_per_status=50,  # Events per status type
)
```

**Use Cases:**
- GSI query testing (status-lastAttemptAt-index)
- Index performance testing
- Query optimization testing

### 8. Single Event

Creates minimal dataset for edge case testing.

```python
events = generator.generate_single_event(
    status="delivered",
    latency_seconds=5.0,
)
```

**Use Cases:**
- Edge case testing (n=1)
- Minimal data scenarios
- Specific event testing

### 9. Empty State

Returns empty dataset for null/zero testing.

```python
events = generator.generate_empty_state()
```

**Use Cases:**
- Empty database testing
- Zero-state UI testing
- Error handling verification

## Custom Event Creation

For maximum control, create individual events with specific properties:

```python
from datetime import datetime, timedelta

now = datetime.utcnow()

event = generator.create_event(
    status="delivered",                      # pending, delivered, or failed
    created_at=now - timedelta(seconds=10),  # Creation time
    updated_at=now,                          # Last update time
    latency_seconds=10.0,                    # Time to complete
    event_type="user.signup",                # Event type
    event_source="web",                      # Event source
    delivery_attempts=1,                     # Number of attempts
    error_message="Error details",           # For failed events
    event_id="custom-id-123",                # Custom ID
    last_attempt_at="2024-01-15T10:30:00Z", # For GSI testing
)

# Insert single event or batch
events = generator.bulk_insert_events([event])
```

## Common Test Patterns

### Pattern 1: Reusable Fixtures

Create fixtures for common datasets:

```python
import pytest
from tests.generate_test_data import EventDataGenerator

@pytest.fixture
def realistic_events(dynamodb_table):
    """Fixture providing realistic event data."""
    generator = EventDataGenerator(dynamodb_table)
    return generator.generate_realistic_dataset(count=500)

def test_metrics_summary(client, auth_token, realistic_events):
    """Test using the fixture."""
    response = client.get("/metrics/summary", headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 200
```

### Pattern 2: Scenario-Based Testing

Test specific scenarios with targeted data:

```python
def test_high_error_rate_scenario(client, auth_token, dynamodb_table):
    """Test dashboard behavior during high errors."""
    generator = EventDataGenerator(dynamodb_table)

    # Generate high-failure scenario
    generator.generate_high_failure_scenario(delivered=10, failed=90)

    # Verify error metrics
    response = client.get("/metrics/errors", headers={"Authorization": f"Bearer {auth_token}"})
    data = response.json()

    assert data["error_rate"] == 90.0
    assert data["failed_deliveries"] == 90
```

### Pattern 3: Progressive Load Testing

Test system behavior as data volume increases:

```python
def test_metrics_scale(client, auth_token, dynamodb_table):
    """Test metrics accuracy as dataset grows."""
    generator = EventDataGenerator(dynamodb_table)
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Test with 100 events
    generator.generate_realistic_dataset(count=100)
    response1 = client.get("/metrics/summary", headers=headers)
    assert response1.json()["total"] == 100

    # Add 400 more (total 500)
    generator.generate_realistic_dataset(count=400)

    # Clear cache to get fresh data
    import main
    main.metrics_cache.clear()

    response2 = client.get("/metrics/summary", headers=headers)
    assert response2.json()["total"] == 500
```

### Pattern 4: Time Window Testing

Test time-based filtering with events inside/outside windows:

```python
def test_24h_filtering(client, auth_token, dynamodb_table):
    """Verify only last 24h events are counted."""
    generator = EventDataGenerator(dynamodb_table)

    # Generate recent and old events
    generator.generate_throughput_dataset(
        events_per_hour=10,
        hours=24,
        include_old_events=True  # Adds events >24h old
    )

    response = client.get(
        "/metrics/throughput",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    # Only recent events should be counted
    data = response.json()
    assert data["total_events_24h"] == 240  # 10/hour * 24 hours
```

## Event Field Reference

### Required Fields

All generated events include these fields:

```python
{
    "id": str,                  # Unique event identifier
    "type": str,                # Event type (e.g., "user.signup")
    "source": str,              # Event source (e.g., "web", "mobile")
    "status": str,              # "pending", "delivered", or "failed"
    "created_at": str,          # ISO 8601 timestamp with Z
    "updated_at": str,          # ISO 8601 timestamp with Z
    "payload": dict,            # Event payload data
    "delivery_attempts": int,   # Number of delivery attempts
    "ttl": int,                 # Unix timestamp for TTL (90 days)
}
```

### Optional Fields

Fields added based on event status or configuration:

```python
{
    "error_message": str,       # Error description (failed events)
    "last_attempt_at": str,     # Last delivery attempt time (for GSI)
}
```

### Default Event Types

```python
EVENT_TYPES = [
    "user.signup", "user.login", "user.logout",
    "order.placed", "order.completed", "order.cancelled",
    "payment.success", "payment.failed",
    "webhook.error", "data.sync", "email.queue",
    "analytics.track", "notification.sent",
]
```

### Default Event Sources

```python
EVENT_SOURCES = ["web", "mobile", "api", "cron", "stripe", "mailer", "admin"]
```

## Best Practices

### 1. Use Appropriate Dataset Sizes

- **Unit tests**: 10-100 events
- **Integration tests**: 100-500 events
- **Load tests**: 1000+ events

### 2. Clear Caches Between Tests

When testing cache behavior, explicitly clear caches:

```python
import main
main.metrics_cache.clear()
```

### 3. Use Realistic Distributions

Match production patterns for meaningful tests:
- 85% delivered
- 10% pending
- 5% failed

### 4. Test Edge Cases

Always include tests for:
- Empty datasets
- Single event (n=1)
- Very large datasets
- Time boundary conditions

### 5. Document Test Scenarios

Use descriptive test names and docstrings:

```python
def test_summary_with_high_failure_rate(client, auth_token, dynamodb_table):
    """
    Test dashboard summary displays correct metrics during high failure rate.

    Scenario: 20% success, 80% failure
    Expected: Error rate = 80%, success rate = 20%
    """
    # Test implementation
```

## Troubleshooting

### Issue: Events not appearing in metrics

**Solution**: Clear the metrics cache after inserting data:

```python
import main
main.metrics_cache.clear()

response = client.get("/metrics/summary", headers=headers)
```

### Issue: Incorrect event counts

**Possible causes**:
1. Events outside time windows (e.g., >24h old for throughput)
2. Cache returning stale data
3. Status mismatch in test expectations

**Solution**: Verify event timestamps and clear cache.

### Issue: Percentile calculations unexpected

**Solution**: Use `generate_percentile_test_dataset()` for uniform distribution or `generate_latency_test_dataset()` with known values.

### Issue: Memory issues with large datasets

**Solution**: Use `generate_large_dataset()` which batches insertions:

```python
# Good - batched insertion
generator.generate_large_dataset(count=5000)

# Avoid - all at once
events = [generator.create_event(...) for _ in range(5000)]
generator.bulk_insert_events(events)  # May cause memory issues
```

## Performance Tips

### 1. Batch Operations

Use `bulk_insert_events()` for multiple events:

```python
events = [generator.create_event(status="delivered") for _ in range(100)]
generator.bulk_insert_events(events)  # Single batch
```

### 2. Reuse Generator Instances

Create one generator per test, not per event:

```python
# Good
generator = EventDataGenerator(dynamodb_table)
generator.generate_realistic_dataset(100)
generator.generate_high_failure_scenario(10, 20)

# Avoid
EventDataGenerator(dynamodb_table).generate_realistic_dataset(100)
EventDataGenerator(dynamodb_table).generate_high_failure_scenario(10, 20)
```

### 3. Use Fixtures for Common Data

Define fixtures once, reuse across tests:

```python
@pytest.fixture(scope="module")  # Module scope for reuse
def large_dataset(dynamodb_table):
    generator = EventDataGenerator(dynamodb_table)
    generator.generate_large_dataset(count=1000)
```

## Examples

See `test_data_generator_examples.py` for 13 comprehensive examples covering:

1. Basic realistic dataset
2. Quick helper functions
3. Latency percentile testing
4. Throughput distribution
5. High failure scenarios
6. Custom event creation
7. Large dataset load testing
8. Empty state testing
9. Single event testing
10. Percentile distribution
11. GSI testing
12. Time-based filtering
13. Reusable fixture patterns

## API Reference

### EventDataGenerator Class

```python
class EventDataGenerator:
    def __init__(self, dynamodb_table)

    def create_event(...) -> Dict[str, Any]
    def bulk_insert_events(events: List[Dict]) -> List[Dict]

    # Preset generators
    def generate_realistic_dataset(...) -> List[Dict]
    def generate_high_failure_scenario(...) -> List[Dict]
    def generate_latency_test_dataset(...) -> List[Dict]
    def generate_throughput_dataset(...) -> List[Dict]
    def generate_large_dataset(...) -> List[Dict]
    def generate_percentile_test_dataset(...) -> List[Dict]
    def generate_gsi_test_dataset(...) -> List[Dict]
    def generate_single_event(...) -> List[Dict]
    def generate_empty_state() -> List[Dict]
```

### Quick Functions

```python
def quick_realistic_data(dynamodb_table, count: int = 500)
def quick_high_failure_data(dynamodb_table, delivered: int = 20, failed: int = 80)
def quick_latency_data(dynamodb_table, latencies: List[float])
def quick_throughput_data(dynamodb_table, events_per_hour: int = 10, hours: int = 24)
```

## Contributing

When adding new generators:

1. Follow the existing naming pattern: `generate_*_dataset()`
2. Document parameters and use cases
3. Add example usage to `test_data_generator_examples.py`
4. Update this guide with the new generator

## Support

For questions or issues with the test data generator:
1. Check the examples in `test_data_generator_examples.py`
2. Review this guide's troubleshooting section
3. Examine existing test files for patterns
