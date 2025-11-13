# Webhook Bridge Pattern

Forward webhooks from external services (Stripe, Shopify, GitHub, etc.) to Zapier via the Triggers API.

## Overview

```
External Service → Webhook → Your Server → Zapier Triggers API → Zapier Workflows
   (Stripe)                    (Bridge)
```

## Why Use This Pattern?

**Benefits:**
- **Buffering** - Events are stored even if Zapier is temporarily unavailable
- **Retry Logic** - Undelivered events remain in inbox until acknowledged
- **Centralized Management** - All webhooks go through one API
- **Zapier Compatibility** - Use Zapier's polling trigger pattern
- **Observability** - CloudWatch logs all webhook activity

**Use Cases:**
- Stripe payment notifications
- Shopify order updates
- GitHub repository events
- Twilio SMS/call events
- SendGrid email events

## Implementation

### 1. Flask (Python)

```python
from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import os

app = Flask(__name__)

# Configuration
ZAPIER_API_URL = os.environ["ZAPIER_API_URL"]
ZAPIER_API_TOKEN = os.environ["ZAPIER_API_TOKEN"]
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

def verify_stripe_signature(payload, signature, secret):
    """Verify Stripe webhook signature"""
    expected_sig = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    # Stripe sends signature as "t=timestamp,v1=signature"
    sig_parts = dict(part.split('=') for part in signature.split(','))
    received_sig = sig_parts.get('v1', '')

    return hmac.compare_digest(expected_sig, received_sig)

@app.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """
    Stripe webhook endpoint
    Receives Stripe webhooks and forwards to Zapier Triggers API
    """
    # Get signature from header
    signature = request.headers.get('Stripe-Signature')

    if not signature:
        return jsonify({"error": "Missing signature"}), 400

    # Verify signature
    try:
        if not verify_stripe_signature(request.data, signature, STRIPE_WEBHOOK_SECRET):
            return jsonify({"error": "Invalid signature"}), 401
    except Exception as e:
        return jsonify({"error": f"Signature verification failed: {str(e)}"}), 401

    # Parse webhook payload
    try:
        event = request.json
    except Exception as e:
        return jsonify({"error": "Invalid JSON"}), 400

    # Forward to Zapier Triggers API
    try:
        response = requests.post(
            f"{ZAPIER_API_URL}/events",
            headers={
                "Authorization": f"Bearer {ZAPIER_API_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "type": f"stripe.{event['type']}",  # e.g., "stripe.payment_intent.succeeded"
                "source": "stripe-webhook",
                "payload": {
                    "id": event['id'],
                    "type": event['type'],
                    "data": event['data']['object'],
                    "created": event['created']
                }
            },
            timeout=5
        )

        if response.status_code == 201:
            return jsonify({
                "status": "forwarded",
                "event_id": response.json()["id"]
            }), 200
        else:
            # Log error but return 200 to Stripe (we received it)
            app.logger.error(f"Failed to forward to Zapier: {response.text}")
            return jsonify({"status": "received"}), 200

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error forwarding to Zapier: {str(e)}")
        # Return 200 to Stripe so they don't retry
        return jsonify({"status": "received"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

**Requirements:**
```txt
flask==3.0.0
requests==2.31.0
```

**Run:**
```bash
export ZAPIER_API_URL="https://your-api-url.lambda-url.us-east-2.on.aws"
export ZAPIER_API_TOKEN="your-jwt-token"
export STRIPE_WEBHOOK_SECRET="whsec_..."

python webhook_bridge.py
```

### 2. Express (Node.js)

```javascript
const express = require('express');
const axios = require('axios');
const crypto = require('crypto');
const bodyParser = require('body-parser');

const app = express();

// Configuration
const ZAPIER_API_URL = process.env.ZAPIER_API_URL;
const ZAPIER_API_TOKEN = process.env.ZAPIER_API_TOKEN;
const STRIPE_WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET;

// Verify Stripe signature
function verifyStripeSignature(payload, signature, secret) {
  const expectedSig = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('hex');

  // Parse signature header
  const sigParts = signature.split(',').reduce((acc, part) => {
    const [key, value] = part.split('=');
    acc[key] = value;
    return acc;
  }, {});

  return crypto.timingSafeEqual(
    Buffer.from(expectedSig),
    Buffer.from(sigParts.v1 || '')
  );
}

// Stripe webhook endpoint
app.post('/webhooks/stripe',
  bodyParser.raw({ type: 'application/json' }),
  async (req, res) => {
    const signature = req.headers['stripe-signature'];

    if (!signature) {
      return res.status(400).json({ error: 'Missing signature' });
    }

    // Verify signature
    try {
      const isValid = verifyStripeSignature(
        req.body,
        signature,
        STRIPE_WEBHOOK_SECRET
      );

      if (!isValid) {
        return res.status(401).json({ error: 'Invalid signature' });
      }
    } catch (err) {
      return res.status(401).json({ error: 'Signature verification failed' });
    }

    // Parse event
    const event = JSON.parse(req.body.toString());

    // Forward to Zapier Triggers API
    try {
      const response = await axios.post(
        `${ZAPIER_API_URL}/events`,
        {
          type: `stripe.${event.type}`,
          source: 'stripe-webhook',
          payload: {
            id: event.id,
            type: event.type,
            data: event.data.object,
            created: event.created
          }
        },
        {
          headers: {
            'Authorization': `Bearer ${ZAPIER_API_TOKEN}`,
            'Content-Type': 'application/json'
          },
          timeout: 5000
        }
      );

      res.json({
        status: 'forwarded',
        event_id: response.data.id
      });
    } catch (err) {
      console.error('Error forwarding to Zapier:', err);
      // Return 200 to Stripe (we received it)
      res.json({ status: 'received' });
    }
  }
);

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`Webhook bridge listening on port ${PORT}`);
});
```

**Requirements:**
```json
{
  "dependencies": {
    "express": "^4.18.2",
    "axios": "^1.6.0",
    "body-parser": "^1.20.2"
  }
}
```

**Run:**
```bash
export ZAPIER_API_URL="https://your-api-url.lambda-url.us-east-2.on.aws"
export ZAPIER_API_TOKEN="your-jwt-token"
export STRIPE_WEBHOOK_SECRET="whsec_..."

node webhook_bridge.js
```

## Webhook Verification

Always verify webhook signatures to prevent malicious requests.

### Stripe

```python
def verify_stripe_signature(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    sig_parts = dict(p.split('=') for p in signature.split(','))
    return hmac.compare_digest(expected, sig_parts.get('v1', ''))
```

### Shopify

```python
def verify_shopify_signature(data, hmac_header, secret):
    hash = hmac.new(
        secret.encode('utf-8'),
        data,
        hashlib.sha256
    )
    return hmac.compare_digest(
        hash.hexdigest(),
        hmac_header
    )
```

### GitHub

```python
def verify_github_signature(payload, signature, secret):
    expected = 'sha256=' + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
```

## Deployment

### AWS Lambda + API Gateway

Deploy as serverless function for automatic scaling:

```python
# lambda_handler.py
import json
import os
import requests

def lambda_handler(event, context):
    # Parse webhook from API Gateway event
    body = json.loads(event['body'])
    headers = event['headers']

    # Verify signature (implementation depends on webhook provider)
    # ... signature verification ...

    # Forward to Zapier Triggers API
    zapier_api_url = os.environ['ZAPIER_API_URL']
    zapier_token = os.environ['ZAPIER_API_TOKEN']

    response = requests.post(
        f"{zapier_api_url}/events",
        headers={
            "Authorization": f"Bearer {zapier_token}",
            "Content-Type": "application/json"
        },
        json={
            "type": f"webhook.{body['type']}",
            "source": "lambda-bridge",
            "payload": body
        }
    )

    return {
        'statusCode': 200,
        'body': json.dumps({'status': 'forwarded'})
    }
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY webhook_bridge.py .

EXPOSE 5000

CMD ["python", "webhook_bridge.py"]
```

**Run:**
```bash
docker build -t webhook-bridge .
docker run -p 5000:5000 \
  -e ZAPIER_API_URL="..." \
  -e ZAPIER_API_TOKEN="..." \
  -e STRIPE_WEBHOOK_SECRET="..." \
  webhook-bridge
```

## Error Handling

### Retry Logic

```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session():
    """Create session with automatic retries"""
    session = requests.Session()

    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)

    return session

# Use session for Zapier API calls
session = create_session()
response = session.post(f"{ZAPIER_API_URL}/events", ...)
```

### Dead Letter Queue

Store failed forwards for manual review:

```python
import boto3

sqs = boto3.client('sqs')
DLQ_URL = os.environ['DLQ_URL']

def forward_to_zapier(event_data):
    try:
        response = requests.post(f"{ZAPIER_API_URL}/events", json=event_data)
        response.raise_for_status()
    except Exception as e:
        # Add to dead letter queue
        sqs.send_message(
            QueueUrl=DLQ_URL,
            MessageBody=json.dumps({
                'event': event_data,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        )
        raise
```

## Testing

### Test with curl

```bash
# Simulate webhook (without signature)
curl -X POST http://localhost:5000/webhooks/stripe \
  -H "Content-Type: application/json" \
  -d '{
    "id": "evt_test_123",
    "type": "payment_intent.succeeded",
    "data": {
      "object": {
        "id": "pi_test_123",
        "amount": 2000,
        "currency": "usd"
      }
    },
    "created": 1234567890
  }'
```

### Test with Stripe CLI

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Forward webhooks to local server
stripe listen --forward-to localhost:5000/webhooks/stripe

# Trigger test event
stripe trigger payment_intent.succeeded
```

## Monitoring

### CloudWatch Logs

```python
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

@app.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    logger.info(f"Received webhook: {request.json.get('type')}")

    try:
        # ... forward to Zapier ...
        logger.info(f"Forwarded event {event_id} to Zapier")
    except Exception as e:
        logger.error(f"Failed to forward webhook: {str(e)}")
```

### Metrics

Track webhook processing:

```python
from prometheus_client import Counter, Histogram

webhooks_received = Counter('webhooks_received_total', 'Total webhooks received')
webhooks_forwarded = Counter('webhooks_forwarded_total', 'Total webhooks forwarded')
webhook_latency = Histogram('webhook_latency_seconds', 'Webhook processing latency')

@app.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    webhooks_received.inc()

    with webhook_latency.time():
        # ... process webhook ...
        webhooks_forwarded.inc()
```

## Best Practices

1. **Always verify signatures** - Prevent malicious requests
2. **Return 200 quickly** - Acknowledge receipt before processing
3. **Process asynchronously** - Use background jobs for forwarding
4. **Implement retries** - Handle transient failures
5. **Log everything** - Essential for debugging
6. **Use dead letter queues** - Don't lose failed webhooks
7. **Monitor latency** - Keep webhook processing fast
8. **Test thoroughly** - Use webhook provider's testing tools

## Next Steps

- See [database-sync.md](./database-sync.md) for database change tracking
- See [scheduled-events.md](./scheduled-events.md) for periodic event generation
- Read [Developer Guide](../../docs/DEVELOPER_GUIDE.md) for more patterns
