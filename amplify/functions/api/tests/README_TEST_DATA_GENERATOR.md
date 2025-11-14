# Test Data Generator for Metrics Endpoints

## Quick Start

Generate realistic test data for metrics endpoint testing:

```python
from tests.generate_test_data import EventDataGenerator

# Initialize
generator = EventDataGenerator(dynamodb_table)

# Generate 500 realistic events
events = generator.generate_realistic_dataset(count=500)
```

## Files

- **`generate_test_data.py`** - Main data generator module with `EventDataGenerator` class
- **`test_data_generator_examples.py`** - 13 comprehensive examples demonstrating usage patterns
- **`TEST_DATA_GENERATOR_GUIDE.md`** - Complete documentation with all methods and best practices

## Common Patterns

### 1. Realistic Dataset (Default Distribution)

```python
# 85% delivered, 10% pending, 5% failed
events = generator.generate_realistic_dataset(count=500)
```

### 2. High Failure Scenario

```python
events = generator.generate_high_failure_scenario(
    delivered=20,
    failed=80,
    pending=10
)
```

### 3. Latency Testing

```python
# Test with specific latencies for percentile accuracy
events = generator.generate_latency_test_dataset(
    latencies=[1, 5, 10, 30, 60, 120]
)
```

### 4. Throughput Testing

```python
# Generate time-distributed events
events = generator.generate_throughput_dataset(
    events_per_hour=10,
    hours=24
)
```

## Quick Functions

For rapid prototyping:

```python
from tests.generate_test_data import (
    quick_realistic_data,
    quick_high_failure_data,
    quick_latency_data,
    quick_throughput_data,
)

# One-liner data generation
events = quick_realistic_data(dynamodb_table, count=500)
```

## Running Examples

```bash
# Run all examples
pytest tests/test_data_generator_examples.py -v

# Run specific example
pytest tests/test_data_generator_examples.py::test_example_realistic_dataset -v

# Run examples with output
pytest tests/test_data_generator_examples.py -v -s
```

## Key Features

- **Realistic Distributions**: Matches production patterns (85/10/5 split)
- **Time Control**: Generate events at specific timestamps for time-window testing
- **Latency Control**: Create events with precise latencies for percentile testing
- **Error Scenarios**: High/low failure rates with realistic error messages
- **Large Datasets**: Efficient batched insertion for load testing (2000+ events)
- **GSI Support**: Proper `last_attempt_at` values for index testing
- **Flexible**: Custom event creation with full control over all fields

## Documentation

See **`TEST_DATA_GENERATOR_GUIDE.md`** for:
- Complete API reference
- All available generators
- Best practices
- Troubleshooting
- Performance tips
- 13 example use cases

## Architecture

```
EventDataGenerator
├── Core Methods
│   ├── create_event()         - Create single custom event
│   └── bulk_insert_events()   - Batch insert multiple events
│
├── Preset Generators
│   ├── generate_realistic_dataset()       - Default 85/10/5 distribution
│   ├── generate_high_failure_scenario()   - Elevated error rates
│   ├── generate_latency_test_dataset()    - Specific latencies
│   ├── generate_throughput_dataset()      - Time-distributed events
│   ├── generate_large_dataset()           - Load testing (2000+)
│   ├── generate_percentile_test_dataset() - Uniform distribution
│   ├── generate_gsi_test_dataset()        - GSI-optimized
│   ├── generate_single_event()            - Minimal (n=1)
│   └── generate_empty_state()             - Empty dataset
│
└── Quick Helpers
    ├── quick_realistic_data()
    ├── quick_high_failure_data()
    ├── quick_latency_data()
    └── quick_throughput_data()
```

## Event Structure

All generated events include:

```python
{
    "id": str,                  # Unique identifier
    "type": str,                # Event type (e.g., "user.signup")
    "source": str,              # Source (e.g., "web", "mobile")
    "status": str,              # "pending", "delivered", "failed"
    "created_at": str,          # ISO 8601 timestamp
    "updated_at": str,          # ISO 8601 timestamp
    "payload": dict,            # Realistic payload based on type
    "delivery_attempts": int,   # Number of attempts
    "ttl": int,                 # TTL timestamp (90 days)
}
```

Optional fields:
- `error_message` (failed events)
- `last_attempt_at` (for GSI testing)

## Testing Workflow

1. **Import**: `from tests.generate_test_data import EventDataGenerator`
2. **Initialize**: `generator = EventDataGenerator(dynamodb_table)`
3. **Generate**: `events = generator.generate_realistic_dataset(500)`
4. **Test**: Run your metrics endpoint tests
5. **Clear Cache**: `main.metrics_cache.clear()` between tests if needed

## Examples in Action

See `test_data_generator_examples.py` for complete working examples:

1. ✅ Basic realistic dataset
2. ✅ Quick helper functions
3. ✅ Latency percentile testing
4. ✅ Throughput distribution
5. ✅ High failure scenarios
6. ✅ Custom event creation
7. ✅ Large dataset load testing
8. ✅ Empty state testing
9. ✅ Single event edge cases
10. ✅ Percentile distribution
11. ✅ GSI testing
12. ✅ Time-based filtering
13. ✅ Reusable fixture patterns

All examples are fully tested and pass validation.

## Benefits

- **Reduces Boilerplate**: No more manually creating test events
- **Consistent**: All tests use the same realistic patterns
- **Flexible**: Easy to create custom scenarios
- **Fast**: Efficient batch insertion for large datasets
- **Comprehensive**: Covers all test scenarios from empty to 2000+ events
- **Well-Documented**: Examples and guide for every use case

## Support

For detailed documentation, see **`TEST_DATA_GENERATOR_GUIDE.md`**.

For examples, see **`test_data_generator_examples.py`**.
