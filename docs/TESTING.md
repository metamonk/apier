# Testing Guide

This document covers testing for the Zapier Triggers API.

## Overview

The API uses **pytest** for unit testing with mocked AWS services (DynamoDB and Secrets Manager) using **moto**.

## Test Coverage

### Endpoints Tested

✅ **Health Check Endpoints**
- `GET /` - Service information
- `GET /health` - Health status

✅ **Configuration Endpoint**
- `GET /config` - Non-sensitive configuration retrieval

✅ **Core API Endpoints**
- `POST /events` - Event ingestion
- `GET /inbox` - Retrieve pending events
- `POST /inbox/{event_id}/ack` - Acknowledge event delivery

### Test Categories

1. **Health Endpoints** (`TestHealthEndpoints`)
   - Root endpoint returns service information
   - Health endpoint returns healthy status

2. **Configuration** (`TestConfigEndpoint`)
   - Configuration retrieval with mocked secrets

3. **Event Creation** (`TestEventsEndpoint`)
   - Successful event creation
   - Validation of required fields
   - Invalid JSON handling
   - Multiple event creation
   - UUID validation

4. **Inbox Retrieval** (`TestInboxEndpoint`)
   - Empty inbox handling
   - Pending events retrieval
   - Event ordering (newest first)
   - Event structure validation

5. **Event Acknowledgment** (`TestAcknowledgeEndpoint`)
   - Successful acknowledgment
   - Non-existent event handling
   - Acknowledged events removed from inbox
   - Idempotent acknowledgment

6. **End-to-End Workflows** (`TestEndToEndWorkflow`)
   - Complete event lifecycle
   - Multiple events handling

## Running Tests

### Prerequisites

1. **Install dependencies:**

```bash
cd amplify/functions/api
pip install -r requirements-dev.txt
```

Or using pnpm (from project root):

```bash
pnpm test:install
```

### Run All Tests

```bash
# From the API directory
cd amplify/functions/api
pytest

# Or from project root
pnpm test
```

### Run with Coverage

```bash
# Detailed coverage report
pytest --cov=. --cov-report=term-missing

# HTML coverage report
pytest --cov=. --cov-report=html
# Open htmlcov/index.html in browser
```

### Run Specific Tests

```bash
# Run a specific test class
pytest tests/test_api.py::TestEventsEndpoint

# Run a specific test
pytest tests/test_api.py::TestEventsEndpoint::test_create_event_success

# Run tests matching a pattern
pytest -k "event"
```

### Verbose Output

```bash
# Show all test details
pytest -v

# Show print statements
pytest -s

# Both verbose and prints
pytest -vs
```

## Test Configuration

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
asyncio_mode = auto

addopts =
    --verbose
    --cov=.
    --cov-report=term-missing
    --cov-fail-under=80
```

**Coverage threshold:** 80% minimum

### Environment Variables

Tests automatically set these environment variables:

```python
DYNAMODB_TABLE_NAME = 'test-zapier-triggers-events'
SECRET_ARN = 'arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret'
AWS_REGION = 'us-east-1'
```

## Test Architecture

### Mocked AWS Services

Tests use **moto** to mock AWS services locally:

1. **DynamoDB:**
   - Mock table created with same schema as production
   - Includes `status-index` GSI for queries
   - Auto-cleaned between tests

2. **Secrets Manager:**
   - Mock secret with test credentials
   - Secret cache cleared between tests

### Fixtures

**`aws_credentials`** - Mock AWS credentials

**`dynamodb_table`** - Creates and tears down mock DynamoDB table

**`secrets_manager`** - Creates mock Secrets Manager secret

**`client`** - FastAPI TestClient with all mocks configured

### Test Isolation

Each test:
- Gets fresh mock AWS resources
- Has isolated database state
- Clears secrets cache
- Runs independently

## CI/CD Integration

### GitHub Actions (Example)

```yaml
name: Run Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          cd amplify/functions/api
          pip install -r requirements-dev.txt

      - name: Run tests
        run: |
          cd amplify/functions/api
          pytest --cov=. --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./amplify/functions/api/coverage.xml
```

### Pre-commit Hook (Optional)

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
cd amplify/functions/api
pytest --cov-fail-under=80
if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

## Writing New Tests

### Test Structure

```python
class TestNewFeature:
    """Tests for new feature."""

    def test_feature_success(self, client):
        """Test successful operation."""
        response = client.post("/new-endpoint", json={...})

        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "expected_value"

    def test_feature_error_handling(self, client):
        """Test error case."""
        response = client.post("/new-endpoint", json={...})

        assert response.status_code == 400
        assert "error" in response.json()["detail"]
```

### Best Practices

✅ **Do:**
- Use descriptive test names
- Test both success and error cases
- Verify response status codes
- Validate response structure
- Test edge cases
- Keep tests independent
- Use fixtures for setup
- Mock external dependencies

❌ **Don't:**
- Make real AWS API calls
- Depend on test execution order
- Use hardcoded IDs (except for error cases)
- Test implementation details
- Ignore assertion messages

### Naming Conventions

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`
- Use descriptive names: `test_create_event_with_invalid_payload`

## Debugging Tests

### Print Debugging

```python
def test_something(self, client):
    response = client.get("/endpoint")
    print(f"Response: {response.json()}")  # Run with pytest -s
    assert ...
```

### Debugger

```python
def test_something(self, client):
    import pdb; pdb.set_trace()
    response = client.get("/endpoint")
    assert ...
```

### Verbose Errors

```bash
# Show full diff on assertion errors
pytest -vv

# Show local variables on failure
pytest -l

# Drop into debugger on failure
pytest --pdb
```

## Test Maintenance

### When to Update Tests

- Adding new endpoints
- Modifying existing endpoints
- Changing response formats
- Adding new error handling
- Updating business logic
- Changing validation rules

### Coverage Goals

- **Minimum:** 80% overall coverage
- **Target:** 90%+ for critical paths
- **Focus areas:**
  - All endpoint handlers
  - Error handling
  - Input validation
  - Business logic

### Regular Tasks

**Daily:**
- Run tests before committing code
- Fix any failing tests immediately

**Weekly:**
- Review coverage reports
- Add tests for uncovered code
- Update tests for new features

**Monthly:**
- Review and refactor test code
- Update dependencies in requirements-dev.txt
- Clean up obsolete tests

## Troubleshooting

### Common Issues

#### Import Errors

**Error:** `ModuleNotFoundError: No module named 'moto'`

**Solution:**
```bash
cd amplify/functions/api
pip install -r requirements-dev.txt
```

#### Mock Not Working

**Error:** Tests hitting real AWS services

**Solution:**
- Ensure `@mock_aws` decorator is used
- Check `aws_credentials` fixture is applied
- Verify environment variables are set before app import

#### Async Warnings

**Error:** `RuntimeWarning: coroutine was never awaited`

**Solution:**
- Add `@pytest.mark.asyncio` to async tests
- Or use `asyncio_mode = auto` in pytest.ini (already configured)

#### Coverage Too Low

**Error:** `FAIL Required test coverage of 80% not reached`

**Solution:**
1. Run `pytest --cov=. --cov-report=html`
2. Open `htmlcov/index.html`
3. Identify uncovered lines
4. Add tests for uncovered code

## Performance

### Test Speed

Current test suite runs in ~5-10 seconds for all tests.

**Optimization tips:**
- Use function-scoped fixtures (already configured)
- Avoid unnecessary sleeps
- Mock external services
- Parallel execution with `pytest-xdist` (optional)

```bash
# Run tests in parallel
pip install pytest-xdist
pytest -n auto
```

## References

- [pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [moto Documentation](https://docs.getmoto.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)

---

**Last Updated:** 2025-11-13
**Maintained By:** Development Team
