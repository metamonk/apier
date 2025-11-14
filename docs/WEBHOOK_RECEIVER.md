# Webhook Receiver Documentation

## Overview

The webhook receiver endpoint (`POST /webhook`) receives events from the dispatcher service and logs them to CloudWatch for debugging and monitoring. This endpoint is part of the Zapier Triggers API and enables external systems to push events for processing.

## Endpoint Details

- **URL**: `/webhook`
- **Method**: POST
- **Authentication**: HMAC-SHA256 signature validation
- **Content-Type**: application/json

## Security

### HMAC Signature Validation

All webhook requests must include a valid HMAC-SHA256 signature in the `X-Webhook-Signature` header. The signature is computed over the raw request body using the webhook secret stored in AWS Secrets Manager.

#### Signature Generation

```bash
# Generate HMAC-SHA256 signature
WEBHOOK_SECRET="your-webhook-secret-from-secrets-manager"
PAYLOAD='{"event_type":"user.created","payload":{"user_id":"123"}}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | cut -d' ' -f2)

# Send webhook request
curl -X POST https://your-api-url.amazonaws.com/webhook \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Signature: $SIGNATURE" \
     -d "$PAYLOAD"
```

#### Python Example

```python
import hmac
import hashlib
import json
import requests

def send_webhook(webhook_url, webhook_secret, event_data):
    """
    Send a webhook with HMAC signature validation.

    Args:
        webhook_url: Full URL to the webhook endpoint
        webhook_secret: Secret key from AWS Secrets Manager
        event_data: Dictionary containing event data

    Returns:
        Response from the webhook endpoint
    """
    # Serialize payload to JSON
    payload = json.dumps(event_data)

    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        webhook_secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # Send request with signature header
    response = requests.post(
        webhook_url,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'X-Webhook-Signature': signature
        }
    )

    return response

# Example usage
webhook_url = "https://your-api-url.amazonaws.com/webhook"
webhook_secret = "your-webhook-secret"

event_data = {
    "event_type": "user.created",
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {
        "user_id": "12345",
        "email": "user@example.com",
        "name": "John Doe"
    },
    "timestamp": "2024-01-15T10:30:00Z"
}

response = send_webhook(webhook_url, webhook_secret, event_data)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

#### Node.js Example

```javascript
const crypto = require('crypto');
const https = require('https');

function sendWebhook(webhookUrl, webhookSecret, eventData) {
    // Serialize payload to JSON
    const payload = JSON.stringify(eventData);

    // Generate HMAC-SHA256 signature
    const signature = crypto
        .createHmac('sha256', webhookSecret)
        .update(payload)
        .digest('hex');

    // Parse URL
    const url = new URL(webhookUrl);

    // Configure request
    const options = {
        hostname: url.hostname,
        port: 443,
        path: url.pathname,
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload),
            'X-Webhook-Signature': signature
        }
    };

    // Send request
    return new Promise((resolve, reject) => {
        const req = https.request(options, (res) => {
            let data = '';

            res.on('data', (chunk) => {
                data += chunk;
            });

            res.on('end', () => {
                resolve({
                    statusCode: res.statusCode,
                    body: JSON.parse(data)
                });
            });
        });

        req.on('error', reject);
        req.write(payload);
        req.end();
    });
}

// Example usage
const webhookUrl = 'https://your-api-url.amazonaws.com/webhook';
const webhookSecret = 'your-webhook-secret';

const eventData = {
    event_type: 'user.created',
    event_id: '550e8400-e29b-41d4-a716-446655440000',
    payload: {
        user_id: '12345',
        email: 'user@example.com',
        name: 'John Doe'
    },
    timestamp: '2024-01-15T10:30:00Z'
};

sendWebhook(webhookUrl, webhookSecret, eventData)
    .then(response => {
        console.log(`Status: ${response.statusCode}`);
        console.log(`Response: ${JSON.stringify(response.body)}`);
    })
    .catch(error => {
        console.error(`Error: ${error.message}`);
    });
```

## Request Format

### Required Headers

| Header | Description |
|--------|-------------|
| `Content-Type` | Must be `application/json` |
| `X-Webhook-Signature` | HMAC-SHA256 signature of request body (hex encoded) |

### Optional Headers

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Request tracking ID (will be logged) |

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_type` | string | Yes | Type of event (e.g., "user.created", "order.completed") |
| `payload` | object | Yes | Event data as JSON object |
| `event_id` | string | No | Unique event identifier (defaults to "unknown" if not provided) |
| `timestamp` | string | No | ISO 8601 timestamp (defaults to current time if not provided) |

### Example Request Body

```json
{
  "event_type": "user.created",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "user_id": "12345",
    "email": "user@example.com",
    "name": "John Doe",
    "created_at": "2024-01-15T10:30:00Z"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Response Format

### Success Response (200 OK)

```json
{
  "status": "received",
  "message": "Webhook event received and logged successfully",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:05.123Z"
}
```

### Error Responses

#### 401 Unauthorized - Invalid Signature

```json
{
  "detail": "Invalid webhook signature"
}
```

#### 422 Unprocessable Entity - Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "event_type"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

#### 500 Internal Server Error

```json
{
  "detail": "SECRET_ARN environment variable not configured"
}
```

## Event Logging

All received webhook events are logged to CloudWatch with the following information:

- **Event Type**: The type of event received
- **Event ID**: Unique identifier for the event
- **Payload**: Full event data
- **Source IP**: IP address of the sender
- **Request ID**: Optional tracking ID from `X-Request-ID` header
- **Timestamp**: Time the event was received
- **Headers**: Non-sensitive request headers (excludes Authorization and X-Webhook-Signature)

### CloudWatch Log Format

```
[WEBHOOK] Received event: type=user.created, id=550e8400-e29b-41d4-a716-446655440000, source_ip=1.2.3.4, request_id=abc123
[WEBHOOK] Event payload: {"user_id": "12345", "email": "user@example.com"}
[WEBHOOK] Event timestamp: 2024-01-15T10:30:00Z
[WEBHOOK] Request headers: {"host": "api.example.com", "user-agent": "Python/3.11"}
```

### Viewing Logs

```bash
# View recent webhook logs
aws logs tail /aws/lambda/your-function-name --follow --filter-pattern "[WEBHOOK]"

# Search for specific event ID
aws logs filter-log-events \
  --log-group-name /aws/lambda/your-function-name \
  --filter-pattern "550e8400-e29b-41d4-a716-446655440000"
```

## CloudWatch Metrics

The webhook endpoint publishes custom CloudWatch metrics:

- **Metric Name**: `WebhookReceived`
- **Namespace**: `ZapierTriggersAPI`
- **Dimensions**: `EventType`
- **Unit**: Count

### Viewing Metrics

```bash
# Get webhook received count by event type
aws cloudwatch get-metric-statistics \
  --namespace ZapierTriggersAPI \
  --metric-name WebhookReceived \
  --dimensions Name=EventType,Value=user.created \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-15T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

## Idempotency

The webhook endpoint is idempotent and safely handles duplicate deliveries. If the same event (identified by `event_id`) is sent multiple times:

1. Each delivery will be logged separately in CloudWatch
2. Each delivery will return a 200 OK response
3. No duplicate processing occurs (events are only logged, not stored)

This design allows for safe retries without side effects.

## Configuration

### AWS Secrets Manager

The webhook secret must be stored in AWS Secrets Manager. Add the `zapier_webhook_secret` key to your secrets:

```bash
# Update secrets with webhook secret
aws secretsmanager update-secret \
  --secret-id your-secret-arn \
  --secret-string '{
    "environment": "production",
    "jwt_secret": "your-jwt-secret",
    "zapier_api_key": "your-api-key",
    "zapier_webhook_url": "https://hooks.zapier.com/hooks/catch/...",
    "zapier_webhook_secret": "your-webhook-secret-key"
  }'
```

### Optional: Disable Signature Validation

If the `zapier_webhook_secret` key is not present in Secrets Manager, signature validation is skipped and all requests are accepted. This is **not recommended** for production use.

## Testing

### Manual Testing with curl

```bash
# Set variables
WEBHOOK_URL="https://your-api-url.amazonaws.com/webhook"
WEBHOOK_SECRET="your-webhook-secret"

# Create payload
PAYLOAD='{"event_type":"test.event","payload":{"test":"data"}}'

# Generate signature
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | cut -d' ' -f2)

# Send request
curl -X POST "$WEBHOOK_URL" \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Signature: $SIGNATURE" \
     -d "$PAYLOAD"
```

### Testing Invalid Signature

```bash
# Send request with invalid signature
curl -X POST "$WEBHOOK_URL" \
     -H "Content-Type: application/json" \
     -H "X-Webhook-Signature: invalid-signature-here" \
     -d "$PAYLOAD"

# Expected response: 401 Unauthorized
```

### Testing Without Signature

```bash
# Send request without signature header
curl -X POST "$WEBHOOK_URL" \
     -H "Content-Type: application/json" \
     -d "$PAYLOAD"

# Expected response: 401 Unauthorized (if webhook secret is configured)
```

## Troubleshooting

### Signature Validation Failures

If you're receiving 401 Unauthorized errors:

1. **Verify the webhook secret**: Ensure you're using the correct secret from AWS Secrets Manager
2. **Check JSON formatting**: The signature must be computed over the exact bytes sent in the request body
3. **Inspect the payload**: Use a tool like `xxd` to examine the exact bytes being signed
4. **Review CloudWatch logs**: Check for `[WEBHOOK] Invalid signature` messages

```bash
# View recent signature validation failures
aws logs tail /aws/lambda/your-function-name --follow \
  --filter-pattern "[WEBHOOK] Invalid signature"
```

### Debugging Signature Generation

```bash
# Generate signature and inspect payload
PAYLOAD='{"event_type":"test","payload":{"test":"data"}}'
echo -n "$PAYLOAD" | xxd  # View exact bytes
echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET"  # Generate signature
```

### Common Issues

1. **Whitespace differences**: Ensure no extra spaces or newlines in the JSON payload
2. **JSON key ordering**: Use the same key order when generating the signature
3. **Character encoding**: Ensure UTF-8 encoding for both payload and secret
4. **Cached secrets**: Lambda may cache the webhook secret; redeploy if you update it

## API Documentation

Interactive API documentation is available at:

- **Swagger UI**: `https://your-api-url.amazonaws.com/docs`
- **ReDoc**: `https://your-api-url.amazonaws.com/redoc`
- **OpenAPI JSON**: `https://your-api-url.amazonaws.com/openapi.json`

## Related Documentation

- [Main README](../README.md)
- [API Documentation](API_DOCUMENTATION.md)
- [Secrets Management](SECRETS.md)
- [Monitoring](MONITORING.md)
- [Deployment Guide](DEPLOYMENT.md)

## Support

For issues or questions:

- Check CloudWatch logs for detailed error messages
- Review the OpenAPI documentation at `/docs`
- Consult the [troubleshooting section](#troubleshooting) above
- Contact API support at support@example.com
