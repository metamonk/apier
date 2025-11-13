# Integration Workflow Patterns

Common integration patterns for the Zapier Triggers API with detailed implementation guides.

## Available Patterns

### 1. Webhook Bridge
**Forward webhooks from external services to Zapier**

[Read the full guide →](./webhook-bridge.md)

**Use Cases:**
- Stripe payment notifications
- Shopify order updates
- GitHub repository events
- Twilio SMS/call events
- SendGrid email events

**Quick Example:**
```python
@app.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    # Verify signature
    verify_stripe_signature(request.data, signature, secret)

    # Forward to Zapier API
    requests.post(
        f"{ZAPIER_API_URL}/events",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "type": f"stripe.{event['type']}",
            "source": "stripe-webhook",
            "payload": event['data']
        }
    )
```

### 2. Database Sync
**Track database changes and trigger workflows**

[Read the full guide →](./database-sync.md)

**Use Cases:**
- User registration/updates
- Order status changes
- Inventory updates
- Payment confirmations
- Document approvals

**Quick Example:**
```python
@receiver(post_save, sender=User)
def user_saved_handler(sender, instance, created, **kwargs):
    if created:
        send_zapier_event.delay(
            event_type="user.created",
            source="django-app",
            payload={
                "user_id": str(instance.id),
                "email": instance.email
            }
        )
```

### 3. Scheduled Events
**Generate events on a schedule for periodic tasks**

[Read the full guide →](./scheduled-events.md)

**Use Cases:**
- Daily/weekly reports
- Monthly billing reminders
- Periodic data exports
- Scheduled notifications
- Batch processing triggers

**Quick Example:**
```python
# daily_report.py - Run via cron: 0 9 * * *
def generate_daily_report():
    report_data = {
        "date": yesterday.strftime("%Y-%m-%d"),
        "metrics": {
            "total_sales": 12543.99,
            "total_orders": 87
        }
    }

    send_event(
        event_type="report.daily",
        source="scheduled-job",
        payload=report_data
    )
```

## Pattern Selection Guide

| Pattern | Best For | Complexity | Reliability |
|---------|----------|------------|-------------|
| Webhook Bridge | External service events | Medium | High |
| Database Sync | Internal data changes | Low | High |
| Scheduled Events | Periodic tasks | Low | High |

## Quick Start

### 1. Choose Your Pattern

Determine which pattern fits your use case:

- **Receiving webhooks?** → Use **Webhook Bridge**
- **Tracking database changes?** → Use **Database Sync**
- **Need scheduled reports?** → Use **Scheduled Events**

### 2. Set Up Authentication

All patterns require JWT authentication:

```bash
# Get API key from Secrets Manager
export API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id zapier-api-credentials-{stackName} \
  --query SecretString --output text | jq -r '.zapier_api_key')

# Get JWT token
export TOKEN=$(curl -s -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=api&password=$API_KEY" | jq -r '.access_token')
```

### 3. Implement Your Pattern

Follow the detailed guide for your chosen pattern:

- [Webhook Bridge Implementation →](./webhook-bridge.md#implementation)
- [Database Sync Implementation →](./database-sync.md#implementation)
- [Scheduled Events Implementation →](./scheduled-events.md#implementation)

## Common Components

### Event Payload Structure

All patterns use the same event structure:

```json
{
  "type": "event.type",       // Event type (noun.verb pattern)
  "source": "event-source",   // Source system identifier
  "payload": {                // Event-specific data
    "key": "value"
  }
}
```

### Error Handling

All patterns should implement retry logic:

```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry)
session.mount("https://", adapter)
```

### Logging

All patterns should log events:

```python
import logging

logger = logging.getLogger(__name__)

def send_event(event_data):
    try:
        logger.info(f"Sending event: {event_data['type']}")
        response = requests.post(...)
        logger.info(f"Event sent: {response.json()['id']}")
    except Exception as e:
        logger.error(f"Failed to send event: {str(e)}")
        raise
```

## Testing

### Unit Tests

Mock API calls in tests:

```python
from unittest.mock import patch, Mock

@patch('requests.post')
def test_send_event(mock_post):
    mock_post.return_value = Mock(
        status_code=201,
        json=lambda: {
            "id": "test-event-id",
            "status": "pending"
        }
    )

    result = send_event({
        "type": "test.event",
        "source": "test",
        "payload": {}
    })

    assert result["id"] == "test-event-id"
    mock_post.assert_called_once()
```

### Integration Tests

Test against development environment:

```bash
# Use dev environment
export API_URL="https://dev-api-url.lambda-url.us-east-2.on.aws"
export API_KEY="dev-api-key"

# Run integration tests
pytest tests/integration/
```

## Monitoring

### CloudWatch Metrics

Track events sent from each pattern:

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

cloudwatch.put_metric_data(
    Namespace='ZapierIntegration',
    MetricData=[
        {
            'MetricName': 'EventsSent',
            'Value': 1,
            'Unit': 'Count',
            'Dimensions': [
                {'Name': 'Pattern', 'Value': 'WebhookBridge'},
                {'Name': 'EventType', 'Value': event_type}
            ]
        }
    ]
)
```

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram

events_sent = Counter(
    'zapier_events_sent_total',
    'Total events sent to Zapier',
    ['pattern', 'event_type']
)

event_latency = Histogram(
    'zapier_event_latency_seconds',
    'Event send latency',
    ['pattern']
)

# Track metrics
events_sent.labels(pattern='webhook-bridge', event_type='stripe.payment').inc()
```

## Best Practices

### 1. Event Naming

Use consistent naming conventions:

```
✅ Good:
  - user.created
  - order.shipped
  - payment.succeeded

❌ Bad:
  - new_user
  - OrderShipped
  - payment-success
```

### 2. Payload Design

Include relevant context:

```python
# ✅ Good payload
{
    "type": "order.placed",
    "source": "web-app",
    "payload": {
        "order_id": "ORD-123",
        "user_id": "USER-456",
        "total": 99.99,
        "items": [...],
        "timestamp": "2024-01-15T10:30:00Z"
    }
}

# ❌ Bad payload (missing context)
{
    "type": "order",
    "source": "app",
    "payload": {
        "id": "123",
        "amount": 99.99
    }
}
```

### 3. Error Handling

Always implement retries:

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_zapier_event(self, event_data):
    try:
        response = requests.post(...)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        raise self.retry(exc=exc)
```

### 4. Monitoring

Track success and failure rates:

```python
def send_event_with_tracking(event_data):
    start_time = time.time()

    try:
        response = send_event(event_data)
        track_success(event_data['type'], time.time() - start_time)
        return response
    except Exception as e:
        track_failure(event_data['type'], str(e))
        raise
```

## Troubleshooting

### Issue: Events Not Appearing in Inbox

**Check:**
1. Verify event was created successfully (201 response)
2. Check event status is "pending"
3. Verify inbox query is working: `GET /inbox`
4. Check CloudWatch logs for errors

**Debug:**
```bash
# Create event and check inbox
EVENT_ID=$(curl -s -X POST "$API_URL/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"type":"test","source":"debug","payload":{}}' | jq -r '.id')

curl -X GET "$API_URL/inbox" \
  -H "Authorization: Bearer $TOKEN" | jq ".[] | select(.id == \"$EVENT_ID\")"
```

### Issue: High Latency

**Causes:**
- Lambda cold starts
- DynamoDB throttling
- Network issues

**Solutions:**
1. Use provisioned concurrency for Lambda
2. Increase DynamoDB capacity
3. Implement connection pooling
4. Add caching where appropriate

### Issue: Duplicate Events

**Prevention:**
```python
# Use idempotency key
import hashlib

def generate_idempotency_key(event_data):
    """Generate unique key for event"""
    content = f"{event_data['type']}:{event_data['source']}:{event_data['payload']}"
    return hashlib.sha256(content.encode()).hexdigest()

# Store sent events in cache/database
if idempotency_key in sent_events_cache:
    logger.warning(f"Duplicate event detected: {idempotency_key}")
    return

# Send event and cache key
send_event(event_data)
sent_events_cache.add(idempotency_key)
```

## Next Steps

1. **Choose a pattern** from the guides above
2. **Review the implementation** section in the pattern guide
3. **Test locally** with development environment
4. **Deploy to production** following best practices
5. **Monitor** with CloudWatch and alerts

## Additional Resources

- [Quickstart Guide](../../docs/QUICKSTART.md) - Get started in 5 minutes
- [Developer Guide](../../docs/DEVELOPER_GUIDE.md) - Comprehensive integration guide
- [Code Examples](../curl/) - Bash/curl examples
- [API Documentation](https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws/docs) - Interactive Swagger UI

## Contributing

Have a useful pattern? Contribute it:

1. Create a new markdown file in this directory
2. Follow the pattern guide template
3. Include code examples for multiple languages
4. Test all examples end-to-end
5. Submit a pull request

---

**Questions?** Open an issue on GitHub or consult the [Developer Guide](../../docs/DEVELOPER_GUIDE.md).
