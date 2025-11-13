# Developer Guide

A comprehensive technical guide for integrating with the Zapier Triggers API.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [API Concepts](#api-concepts)
3. [Authentication Deep Dive](#authentication-deep-dive)
4. [Best Practices](#best-practices)
5. [Integration Patterns](#integration-patterns)
6. [Code Examples](#code-examples)
7. [Performance Optimization](#performance-optimization)
8. [Security Considerations](#security-considerations)
9. [Testing Your Integration](#testing-your-integration)
10. [Troubleshooting](#troubleshooting)

## Architecture Overview

### System Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│                 │         │                  │         │                  │
│  Your App/      │ Events  │  Zapier Triggers │ Polling │     Zapier       │
│  Webhook Source │────────>│       API        │<────────│   Workflows      │
│                 │         │   (Lambda+DDB)   │         │                  │
└─────────────────┘         └──────────────────┘         └──────────────────┘
                                     │                            │
                                     │                            │
                                     v                            v
                            ┌──────────────────┐        ┌──────────────┐
                            │  AWS Secrets     │        │ Your Actions │
                            │    Manager       │        │  (Email, DB, │
                            │  (Credentials)   │        │   Slack...)  │
                            └──────────────────┘        └──────────────┘
```

### Component Breakdown

**1. FastAPI Application (Lambda)**
- Runs on AWS Lambda with Lambda Web Adapter
- Handles HTTP requests via Lambda Function URLs
- Stateless, auto-scaling architecture
- Cold start: ~1-2 seconds, warm: <100ms

**2. DynamoDB Storage**
- Primary table: `zapier-triggers-events-{stackName}`
- Partition key: `id` (event UUID)
- Sort key: `created_at` (ISO timestamp)
- GSI: `status-index` for efficient pending event queries
- TTL: Auto-deletes events after 90 days

**3. AWS Secrets Manager**
- Stores: API keys, JWT secrets, webhook URLs
- Secret ID: `zapier-api-credentials-{stackName}`
- Cached in Lambda containers for performance
- Rotated on-demand (no automatic rotation)

**4. Authentication Layer**
- JWT-based (HS256 algorithm)
- Token expiry: 24 hours
- Password hashing: Argon2id
- OAuth2 password flow compatible

### Data Flow

**Event Ingestion Flow:**
```
1. Client → POST /token (get JWT)
2. Client → POST /events (with JWT) → Lambda
3. Lambda → Validates JWT using secret from Secrets Manager
4. Lambda → Writes event to DynamoDB with "pending" status
5. Lambda → Returns event ID and timestamp
```

**Event Delivery Flow:**
```
1. Zapier → GET /inbox (with JWT) → Lambda
2. Lambda → Queries DynamoDB GSI for "pending" events
3. Lambda → Returns events to Zapier
4. Zapier → Processes events in workflows
5. Zapier → POST /inbox/{id}/ack (with JWT) → Lambda
6. Lambda → Updates event status to "delivered"
```

## API Concepts

### Events

Events are the core data structure representing something that happened in your system.

**Event Structure:**
```json
{
  "type": "user.created",           // Event type (noun.verb pattern)
  "source": "web-app",              // Source system identifier
  "payload": {                      // Event-specific data (any JSON)
    "user_id": "12345",
    "email": "user@example.com",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

**Event Naming Conventions:**

Use **noun.verb** pattern for event types:
- `user.created`, `user.updated`, `user.deleted`
- `order.placed`, `order.shipped`, `order.cancelled`
- `payment.succeeded`, `payment.failed`
- `document.uploaded`, `document.approved`

**Why?** This pattern:
- Makes events self-documenting
- Groups related events naturally
- Enables easy filtering in Zapier

### Inbox

The inbox is a queue of undelivered events awaiting Zapier consumption.

**Inbox Characteristics:**
- Only returns events with `status: "pending"`
- Ordered by `created_at` descending (newest first)
- Limited to 100 events per request
- Events remain in inbox until acknowledged

**Inbox Query (DynamoDB):**
```python
# Behind the scenes, the API queries:
table.query(
    IndexName='status-index',          # GSI on status attribute
    KeyConditionExpression='status = :pending',
    ScanIndexForward=False,           # Descending order
    Limit=100
)
```

### Acknowledgment Flow

After Zapier successfully processes an event, it acknowledges delivery.

**Why Acknowledgment?**
- **Prevents duplicate processing** - Events don't reappear in inbox
- **Confirms successful delivery** - You know Zapier received the event
- **Enables retry logic** - Unacknowledged events can be retried

**Acknowledgment Updates:**
- Changes `status` from `"pending"` to `"delivered"`
- Updates `updated_at` timestamp
- Event no longer appears in inbox queries

## Authentication Deep Dive

### JWT Token Lifecycle

```
┌──────────────┐
│  Token       │  POST /token with API key
│  Request     │  ────────────────────────────>  ┌──────────────┐
└──────────────┘                                  │              │
                                                  │   Lambda     │
                                                  │   Function   │
┌──────────────┐                                  │              │
│  JWT Token   │  <────────────────────────────  └──────────────┘
│  (24h TTL)   │  Returns JWT
└──────────────┘
       │
       │  Include in Authorization header
       │  for all protected endpoints
       v
┌──────────────┐
│  Protected   │  Authorization: Bearer {token}
│  Requests    │  ────────────────────────────>  ┌──────────────┐
└──────────────┘                                  │   Validates  │
                                                  │   JWT & makes│
                                                  │   request    │
                                                  └──────────────┘
```

### Token Structure

**JWT Header:**
```json
{
  "alg": "HS256",    // HMAC SHA-256
  "typ": "JWT"       // Token type
}
```

**JWT Payload:**
```json
{
  "sub": "api",                    // Subject (username)
  "api_key": "test-api...",        // Truncated API key (for logging)
  "iat": 1705315200,              // Issued at (Unix timestamp)
  "exp": 1705401600               // Expires at (Unix timestamp)
}
```

**JWT Signature:**
```
HMACSHA256(
  base64UrlEncode(header) + "." +
  base64UrlEncode(payload),
  secret_from_secrets_manager
)
```

### Token Validation Process

When you make a request to a protected endpoint:

```python
# 1. Extract token from header
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# 2. Verify signature
jwt.decode(
    token,
    jwt_secret,          # From AWS Secrets Manager
    algorithms=["HS256"]
)

# 3. Check expiration
if token.exp < current_time:
    raise HTTPException(401, "Token expired")

# 4. Extract user from claims
user = User(username=token.sub)

# 5. Allow request to proceed
```

### Security Implications

**Token Security:**
- Tokens are signed, not encrypted (don't include sensitive data)
- Signature prevents tampering
- Short expiry (24h) limits exposure from token leaks
- HTTPS ensures tokens aren't intercepted in transit

**API Key Security:**
- Stored in AWS Secrets Manager (encrypted at rest)
- Hashed using Argon2id when compared
- Never logged or exposed in responses
- Rotated on-demand

## Best Practices

### Event Payload Design

**DO:**
```json
{
  "type": "order.placed",
  "source": "shopify-store",
  "payload": {
    "order_id": "ORD-2024-001",
    "customer_id": "CUST-12345",
    "total": 99.99,
    "currency": "USD",
    "items": [
      {
        "sku": "PROD-001",
        "quantity": 2,
        "price": 49.99
      }
    ],
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

**Benefits:**
- Self-contained (all data needed for processing)
- Includes IDs for reference
- Has timestamps for ordering
- Uses consistent naming (snake_case)

**DON'T:**
```json
{
  "type": "event",                 // Too generic
  "source": "app",                 // Not specific
  "payload": {
    "data": "some data",           // Vague field names
    "stuff": [...]                 // Unclear structure
  }
}
```

**Problems:**
- Hard to understand what happened
- No clear identifiers
- Difficult to filter/route in Zapier

### Payload Size Limits

DynamoDB has a 400KB item size limit. Keep payloads reasonable:

**Guidelines:**
- **Ideal:** < 10KB per event
- **Maximum:** < 100KB per event
- **For large data:** Store externally (S3) and include URL

**Example (large file):**
```json
{
  "type": "document.uploaded",
  "source": "document-processor",
  "payload": {
    "document_id": "DOC-789",
    "file_url": "https://s3.amazonaws.com/bucket/files/document.pdf",
    "file_size": 5242880,
    "metadata": {
      "name": "report.pdf",
      "uploaded_at": "2024-01-15T10:30:00Z"
    }
  }
}
```

### Polling Strategies

**Zapier Default Polling:**
- Polls every 5-15 minutes (based on plan)
- Retrieves up to 100 events per poll
- Processes events in order (newest first)

**Optimize for Zapier:**

1. **Batch Events:** Group related events to reduce API calls
2. **Consistent Timing:** Generate events at consistent intervals
3. **Acknowledgment:** Always acknowledge after processing

**Custom Polling (if building your own consumer):**

```python
import time
import requests

API_URL = "https://your-api-url.lambda-url.us-east-2.on.aws"
TOKEN = "your-jwt-token"

def poll_inbox():
    """Poll inbox every 10 seconds"""
    while True:
        # Fetch pending events
        response = requests.get(
            f"{API_URL}/inbox",
            headers={"Authorization": f"Bearer {TOKEN}"}
        )

        events = response.json()

        # Process each event
        for event in events:
            process_event(event)

            # Acknowledge after successful processing
            ack_response = requests.post(
                f"{API_URL}/inbox/{event['id']}/ack",
                headers={"Authorization": f"Bearer {TOKEN}"}
            )

            if ack_response.status_code == 200:
                print(f"Acknowledged event {event['id']}")

        # Wait before next poll
        time.sleep(10)

def process_event(event):
    """Process a single event"""
    print(f"Processing {event['type']}: {event['id']}")
    # Your processing logic here
```

### Error Handling

**Handle Transient Errors:**

```python
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def create_session():
    """Create session with automatic retries"""
    session = requests.Session()

    retry = Retry(
        total=3,                          # Retry 3 times
        backoff_factor=0.5,              # Wait 0.5, 1, 2 seconds
        status_forcelist=[500, 502, 503, 504],  # Retry on server errors
        method_whitelist=["GET", "POST"]
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)

    return session

# Use the session
session = create_session()
response = session.post(f"{API_URL}/events", json=event_data)
```

**Handle Authentication Errors:**

```python
class APIClient:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self.token = None
        self.token_expires = 0

    def get_token(self):
        """Get or refresh JWT token"""
        import time

        # Refresh if expired or about to expire (with 1-hour buffer)
        if time.time() >= (self.token_expires - 3600):
            response = requests.post(
                f"{self.api_url}/token",
                data={"username": "api", "password": self.api_key}
            )
            response.raise_for_status()

            self.token = response.json()["access_token"]
            self.token_expires = time.time() + (24 * 3600)  # 24 hours

        return self.token

    def send_event(self, event_type, source, payload):
        """Send event with automatic token refresh"""
        token = self.get_token()

        response = requests.post(
            f"{self.api_url}/events",
            headers={"Authorization": f"Bearer {token}"},
            json={"type": event_type, "source": source, "payload": payload}
        )

        # Handle 401 (token might have expired between refresh check)
        if response.status_code == 401:
            self.token_expires = 0  # Force refresh
            token = self.get_token()

            # Retry with new token
            response = requests.post(
                f"{self.api_url}/events",
                headers={"Authorization": f"Bearer {token}"},
                json={"type": event_type, "source": source, "payload": payload}
            )

        response.raise_for_status()
        return response.json()
```

### Rate Limiting Considerations

The API doesn't enforce hard rate limits, but consider these factors:

**Lambda Limits:**
- **Concurrency:** Default 1000 concurrent executions
- **Burst:** 3000 requests/second burst capacity
- **Sustained:** 500-1000 requests/second

**DynamoDB Limits:**
- **Write capacity:** Auto-scales, but has minimum provisioning time
- **Read capacity:** GSI queries consume read units
- **Throttling:** Requests may be throttled if capacity is exceeded

**Best Practices:**
```python
import time
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests_per_second=100):
        self.max_rps = max_requests_per_second
        self.interval = 1.0 / max_rps
        self.last_request = 0

    def wait_if_needed(self):
        """Wait if necessary to respect rate limit"""
        now = time.time()
        time_since_last = now - self.last_request

        if time_since_last < self.interval:
            time.sleep(self.interval - time_since_last)

        self.last_request = time.time()

# Usage
limiter = RateLimiter(max_requests_per_second=50)

for event in events_to_send:
    limiter.wait_if_needed()
    send_event(event)
```

## Integration Patterns

### Pattern 1: Webhook Bridge

Forward webhooks from external services to Zapier via the API.

**Use Case:** You receive webhooks from Stripe, Shopify, or other services, but want to process them in Zapier.

**Architecture:**
```
Stripe Webhook → Your Server → Zapier Triggers API → Zapier
```

**Implementation (Flask):**
```python
from flask import Flask, request, jsonify
import requests
import hmac
import hashlib

app = Flask(__name__)

API_URL = "https://your-api-url.lambda-url.us-east-2.on.aws"
API_TOKEN = "your-jwt-token"
STRIPE_WEBHOOK_SECRET = "whsec_..."

@app.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    # Verify Stripe signature
    signature = request.headers.get('Stripe-Signature')

    try:
        verify_stripe_signature(request.data, signature, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        return jsonify({"error": "Invalid signature"}), 400

    # Parse webhook payload
    event = request.json

    # Forward to Zapier Triggers API
    response = requests.post(
        f"{API_URL}/events",
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        json={
            "type": f"stripe.{event['type']}",
            "source": "stripe-webhook",
            "payload": event['data']['object']
        }
    )

    if response.status_code == 201:
        return jsonify({"status": "forwarded"}), 200
    else:
        return jsonify({"error": "Failed to forward"}), 500

def verify_stripe_signature(payload, signature, secret):
    """Verify Stripe webhook signature"""
    expected_sig = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, f"sha256={expected_sig}"):
        raise ValueError("Invalid signature")
```

**Benefits:**
- Centralized webhook handling
- Buffering (events stored even if Zapier is down)
- Retry logic (events remain in inbox until acknowledged)

### Pattern 2: Scheduled Event Generation

Generate events on a schedule for periodic tasks.

**Use Case:** Daily reports, weekly summaries, monthly billing.

**Implementation (Cron Job):**
```python
#!/usr/bin/env python3
"""
Daily report generator
Run via cron: 0 9 * * * /path/to/daily_report.py
"""

import requests
from datetime import datetime, timedelta

API_URL = "https://your-api-url.lambda-url.us-east-2.on.aws"
API_KEY = "your-api-key"

def get_token():
    response = requests.post(
        f"{API_URL}/token",
        data={"username": "api", "password": API_KEY}
    )
    return response.json()["access_token"]

def generate_report():
    """Generate daily report data"""
    # Your report generation logic
    return {
        "date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        "total_sales": 12543.99,
        "total_orders": 87,
        "new_customers": 23
    }

def send_report_event(token, report_data):
    response = requests.post(
        f"{API_URL}/events",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "type": "report.daily",
            "source": "reporting-system",
            "payload": report_data
        }
    )
    return response.json()

if __name__ == "__main__":
    token = get_token()
    report = generate_report()
    result = send_report_event(token, report)
    print(f"Report event created: {result['id']}")
```

### Pattern 3: Database Change Tracking

Track database changes and trigger Zapier workflows.

**Use Case:** User signup, order status changes, inventory updates.

**Implementation (Django Signal):**
```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from myapp.models import User
import requests

API_URL = "https://your-api-url.lambda-url.us-east-2.on.aws"
API_TOKEN = "your-jwt-token"

@receiver(post_save, sender=User)
def user_created_handler(sender, instance, created, **kwargs):
    """Send event when user is created"""
    if created:  # Only on creation, not updates
        event_data = {
            "type": "user.created",
            "source": "django-app",
            "payload": {
                "user_id": str(instance.id),
                "email": instance.email,
                "username": instance.username,
                "created_at": instance.created_at.isoformat()
            }
        }

        # Send event asynchronously (using Celery task)
        send_zapier_event.delay(event_data)

@shared_task
def send_zapier_event(event_data):
    """Celery task to send event to Zapier API"""
    try:
        response = requests.post(
            f"{API_URL}/events",
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            json=event_data,
            timeout=5
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Log error and retry
        raise self.retry(exc=e, countdown=60, max_retries=3)
```

### Pattern 4: Event Aggregation

Batch multiple events before sending to reduce API calls.

**Use Case:** High-volume events (clicks, page views, logs).

**Implementation:**
```python
import threading
import time
import requests
from queue import Queue

class EventAggregator:
    def __init__(self, api_url, api_token, batch_size=50, flush_interval=10):
        self.api_url = api_url
        self.api_token = api_token
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self.queue = Queue()
        self.running = True

        # Start background thread
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def add_event(self, event_type, source, payload):
        """Add event to batch"""
        self.queue.put({
            "type": event_type,
            "source": source,
            "payload": payload
        })

    def _worker(self):
        """Background worker to flush batches"""
        batch = []
        last_flush = time.time()

        while self.running:
            try:
                # Get event with timeout
                event = self.queue.get(timeout=1)
                batch.append(event)

                # Flush if batch is full
                if len(batch) >= self.batch_size:
                    self._flush_batch(batch)
                    batch = []
                    last_flush = time.time()

            except:
                # Timeout - check if we should flush based on time
                if batch and (time.time() - last_flush) >= self.flush_interval:
                    self._flush_batch(batch)
                    batch = []
                    last_flush = time.time()

    def _flush_batch(self, batch):
        """Send batch of events"""
        for event in batch:
            try:
                requests.post(
                    f"{self.api_url}/events",
                    headers={"Authorization": f"Bearer {self.api_token}"},
                    json=event,
                    timeout=5
                )
            except Exception as e:
                print(f"Failed to send event: {e}")

    def close(self):
        """Flush remaining events and stop"""
        self.running = False
        self.thread.join()

# Usage
aggregator = EventAggregator(API_URL, API_TOKEN)

# Add events (non-blocking)
for i in range(100):
    aggregator.add_event(
        event_type="user.click",
        source="web-app",
        payload={"button_id": f"btn-{i}", "timestamp": time.time()}
    )

# Flush and close when done
aggregator.close()
```

## Code Examples

### Python (requests)

```python
import requests
from datetime import datetime

class ZapierTriggersClient:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self.token = None

    def authenticate(self):
        """Get JWT token"""
        response = requests.post(
            f"{self.api_url}/token",
            data={"username": "api", "password": self.api_key}
        )
        response.raise_for_status()
        self.token = response.json()["access_token"]
        return self.token

    def create_event(self, event_type, source, payload):
        """Create a new event"""
        if not self.token:
            self.authenticate()

        response = requests.post(
            f"{self.api_url}/events",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            },
            json={
                "type": event_type,
                "source": source,
                "payload": payload
            }
        )
        response.raise_for_status()
        return response.json()

    def get_inbox(self):
        """Get pending events"""
        if not self.token:
            self.authenticate()

        response = requests.get(
            f"{self.api_url}/inbox",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        response.raise_for_status()
        return response.json()

    def acknowledge_event(self, event_id):
        """Acknowledge event delivery"""
        if not self.token:
            self.authenticate()

        response = requests.post(
            f"{self.api_url}/inbox/{event_id}/ack",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        response.raise_for_status()
        return response.json()

# Example usage
client = ZapierTriggersClient(
    api_url="https://your-api-url.lambda-url.us-east-2.on.aws",
    api_key="your-api-key"
)

# Send event
result = client.create_event(
    event_type="user.signup",
    source="web-app",
    payload={
        "user_id": "12345",
        "email": "user@example.com",
        "plan": "premium"
    }
)
print(f"Event created: {result['id']}")

# Get inbox
events = client.get_inbox()
print(f"Pending events: {len(events)}")

# Acknowledge first event
if events:
    ack = client.acknowledge_event(events[0]["id"])
    print(f"Acknowledged: {ack['id']}")
```

### Node.js (axios)

```javascript
const axios = require('axios');

class ZapierTriggersClient {
  constructor(apiUrl, apiKey) {
    this.apiUrl = apiUrl;
    this.apiKey = apiKey;
    this.token = null;
  }

  async authenticate() {
    const response = await axios.post(
      `${this.apiUrl}/token`,
      new URLSearchParams({
        username: 'api',
        password: this.apiKey
      })
    );
    this.token = response.data.access_token;
    return this.token;
  }

  async createEvent(eventType, source, payload) {
    if (!this.token) await this.authenticate();

    const response = await axios.post(
      `${this.apiUrl}/events`,
      {
        type: eventType,
        source: source,
        payload: payload
      },
      {
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        }
      }
    );
    return response.data;
  }

  async getInbox() {
    if (!this.token) await this.authenticate();

    const response = await axios.get(
      `${this.apiUrl}/inbox`,
      {
        headers: {
          'Authorization': `Bearer ${this.token}`
        }
      }
    );
    return response.data;
  }

  async acknowledgeEvent(eventId) {
    if (!this.token) await this.authenticate();

    const response = await axios.post(
      `${this.apiUrl}/inbox/${eventId}/ack`,
      {},
      {
        headers: {
          'Authorization': `Bearer ${this.token}`
        }
      }
    );
    return response.data;
  }
}

// Example usage
(async () => {
  const client = new ZapierTriggersClient(
    'https://your-api-url.lambda-url.us-east-2.on.aws',
    'your-api-key'
  );

  // Send event
  const result = await client.createEvent(
    'user.signup',
    'web-app',
    {
      user_id: '12345',
      email: 'user@example.com',
      plan: 'premium'
    }
  );
  console.log(`Event created: ${result.id}`);

  // Get inbox
  const events = await client.getInbox();
  console.log(`Pending events: ${events.length}`);

  // Acknowledge first event
  if (events.length > 0) {
    const ack = await client.acknowledgeEvent(events[0].id);
    console.log(`Acknowledged: ${ack.id}`);
  }
})();
```

### Go

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io/ioutil"
    "net/http"
    "net/url"
)

type ZapierTriggersClient struct {
    APIURL string
    APIKey string
    Token  string
}

type Event struct {
    Type    string                 `json:"type"`
    Source  string                 `json:"source"`
    Payload map[string]interface{} `json:"payload"`
}

type EventResponse struct {
    ID        string `json:"id"`
    Status    string `json:"status"`
    Timestamp string `json:"timestamp"`
}

type InboxEvent struct {
    ID        string                 `json:"id"`
    Type      string                 `json:"type"`
    Source    string                 `json:"source"`
    Payload   map[string]interface{} `json:"payload"`
    Status    string                 `json:"status"`
    CreatedAt string                 `json:"created_at"`
    UpdatedAt string                 `json:"updated_at"`
}

func (c *ZapierTriggersClient) Authenticate() error {
    data := url.Values{}
    data.Set("username", "api")
    data.Set("password", c.APIKey)

    resp, err := http.PostForm(c.APIURL+"/token", data)
    if err != nil {
        return err
    }
    defer resp.Body.Close()

    var result map[string]string
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return err
    }

    c.Token = result["access_token"]
    return nil
}

func (c *ZapierTriggersClient) CreateEvent(eventType, source string, payload map[string]interface{}) (*EventResponse, error) {
    if c.Token == "" {
        if err := c.Authenticate(); err != nil {
            return nil, err
        }
    }

    event := Event{
        Type:    eventType,
        Source:  source,
        Payload: payload,
    }

    jsonData, err := json.Marshal(event)
    if err != nil {
        return nil, err
    }

    req, err := http.NewRequest("POST", c.APIURL+"/events", bytes.NewBuffer(jsonData))
    if err != nil {
        return nil, err
    }

    req.Header.Set("Authorization", "Bearer "+c.Token)
    req.Header.Set("Content-Type", "application/json")

    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var eventResponse EventResponse
    if err := json.NewDecoder(resp.Body).Decode(&eventResponse); err != nil {
        return nil, err
    }

    return &eventResponse, nil
}

func (c *ZapierTriggersClient) GetInbox() ([]InboxEvent, error) {
    if c.Token == "" {
        if err := c.Authenticate(); err != nil {
            return nil, err
        }
    }

    req, err := http.NewRequest("GET", c.APIURL+"/inbox", nil)
    if err != nil {
        return nil, err
    }

    req.Header.Set("Authorization", "Bearer "+c.Token)

    client := &http.Client{}
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var events []InboxEvent
    if err := json.NewDecoder(resp.Body).Decode(&events); err != nil {
        return nil, err
    }

    return events, nil
}

func main() {
    client := &ZapierTriggersClient{
        APIURL: "https://your-api-url.lambda-url.us-east-2.on.aws",
        APIKey: "your-api-key",
    }

    // Create event
    payload := map[string]interface{}{
        "user_id": "12345",
        "email":   "user@example.com",
        "plan":    "premium",
    }

    result, err := client.CreateEvent("user.signup", "web-app", payload)
    if err != nil {
        panic(err)
    }
    fmt.Printf("Event created: %s\n", result.ID)

    // Get inbox
    events, err := client.GetInbox()
    if err != nil {
        panic(err)
    }
    fmt.Printf("Pending events: %d\n", len(events))
}
```

## Performance Optimization

### Lambda Cold Starts

**Understanding Cold Starts:**
- First request after idle: 1-2 seconds
- Subsequent requests (warm): <100ms
- Container reuse: ~5-15 minutes

**Optimization Strategies:**

1. **Keep Lambda Warm (Provisioned Concurrency):**
```typescript
// In backend.ts (CDK)
const triggersApiFunction = lambda.addFunction({
  // ... other config
  reservedConcurrentExecutions: 2,  // Reserve instances
});
```

2. **Reduce Package Size:**
```bash
# Use Lambda layers for large dependencies
# Keep deployment package small
```

3. **Pre-warm Connections:**
```python
# In Lambda handler, reuse connections
import boto3

# Global (outside handler) - reused across invocations
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('events-table')

def handler(event, context):
    # Connection already established
    table.put_item(Item=item)
```

### DynamoDB Performance

**Read Optimization:**

```python
# Use projection to reduce data transfer
response = table.query(
    IndexName='status-index',
    KeyConditionExpression=Key('status').eq('pending'),
    ProjectionExpression='id, #type, payload, created_at',  # Only fields needed
    ExpressionAttributeNames={'#type': 'type'}
)
```

**Write Optimization:**

```python
# Batch writes for multiple events
with table.batch_writer() as batch:
    for event in events:
        batch.put_item(Item=event)
```

**Query Optimization:**

```python
# Use GSI for status queries (much faster than scan)
# GSI: status-index with partition key 'status'
response = table.query(
    IndexName='status-index',
    KeyConditionExpression=Key('status').eq('pending'),
    ScanIndexForward=False,  # Descending order
    Limit=100
)
```

### Caching Strategies

**Secret Caching (Already Implemented):**

```python
# Cache secrets in Lambda container memory
_secrets_cache = {}

def get_secret(secret_id):
    if secret_id in _secrets_cache:
        return _secrets_cache[secret_id]

    # Fetch from Secrets Manager
    secret = fetch_secret(secret_id)
    _secrets_cache[secret_id] = secret
    return secret
```

**Response Caching (Client-Side):**

```python
from functools import lru_cache
from datetime import datetime, timedelta

class CachedClient:
    def __init__(self):
        self.token_cache = None
        self.token_expiry = None

    def get_token(self):
        """Cache token until expiry"""
        if self.token_cache and datetime.now() < self.token_expiry:
            return self.token_cache

        # Fetch new token
        response = requests.post(f"{API_URL}/token", ...)
        self.token_cache = response.json()["access_token"]
        self.token_expiry = datetime.now() + timedelta(hours=23)  # Buffer

        return self.token_cache
```

## Security Considerations

### Transport Security

**HTTPS Only:**
- Lambda Function URLs enforce HTTPS
- TLS 1.2+ required
- Certificates managed by AWS

**Verify in Client:**
```python
import requests

# Don't disable SSL verification in production!
response = requests.get(API_URL, verify=True)  # verify=True is default
```

### Token Security

**Storage:**
- **Never** store tokens in localStorage (web apps)
- **Never** commit tokens to Git
- **Never** log token values
- Use secure storage (keychain, environment variables)

**Best Practices:**
```python
import os
from keyring import set_password, get_password

# Store securely (not in code)
TOKEN = os.environ.get("ZAPIER_API_TOKEN")  # From environment
# or
TOKEN = get_password("zapier-api", "token")  # From keychain
```

### API Key Rotation

**Process:**

1. **Generate new API key** in your credential management system
2. **Update Secrets Manager:**
```bash
aws secretsmanager update-secret \
  --secret-id zapier-api-credentials-{stackName} \
  --secret-string "$(jq -n \
    --arg key "$NEW_API_KEY" \
    --arg jwt "$JWT_SECRET" \
    '{zapier_api_key: $key, jwt_secret: $jwt}')"
```

3. **Wait for Lambda container refresh** (5-15 minutes)
4. **Test with new key**
5. **Revoke old key**

### Input Validation

**Server-Side (API):**
- FastAPI automatically validates request bodies via Pydantic
- Type checking for `type`, `source`, `payload`
- Maximum payload size enforced by Lambda (6MB)

**Client-Side:**
```python
def validate_event(event_type, source, payload):
    """Validate event before sending"""
    if not event_type or not isinstance(event_type, str):
        raise ValueError("event_type must be non-empty string")

    if not source or not isinstance(source, str):
        raise ValueError("source must be non-empty string")

    if not isinstance(payload, dict):
        raise ValueError("payload must be dict")

    # Check payload size (DynamoDB 400KB limit)
    import json
    if len(json.dumps(payload)) > 350_000:  # Buffer for metadata
        raise ValueError("payload too large (max 350KB)")
```

## Testing Your Integration

### Unit Testing

**Mock the API:**

```python
import unittest
from unittest.mock import patch, Mock

class TestZapierIntegration(unittest.TestCase):
    @patch('requests.post')
    def test_create_event(self, mock_post):
        # Mock response
        mock_post.return_value = Mock(
            status_code=201,
            json=lambda: {
                "id": "test-id-123",
                "status": "pending",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        )

        # Test client
        client = ZapierTriggersClient(API_URL, API_KEY)
        result = client.create_event("test.event", "test", {})

        # Assertions
        self.assertEqual(result["id"], "test-id-123")
        self.assertEqual(result["status"], "pending")
        mock_post.assert_called_once()
```

### Integration Testing

**Test Against Sandbox:**

```python
import pytest
import requests

@pytest.fixture
def api_client():
    return ZapierTriggersClient(
        api_url=os.environ["TEST_API_URL"],
        api_key=os.environ["TEST_API_KEY"]
    )

def test_full_workflow(api_client):
    # Create event
    result = api_client.create_event(
        "test.event",
        "integration-test",
        {"test": True, "timestamp": datetime.now().isoformat()}
    )
    event_id = result["id"]

    # Verify in inbox
    inbox = api_client.get_inbox()
    assert any(e["id"] == event_id for e in inbox)

    # Acknowledge
    ack = api_client.acknowledge_event(event_id)
    assert ack["status"] == "delivered"

    # Verify removed from inbox
    inbox_after = api_client.get_inbox()
    assert not any(e["id"] == event_id for e in inbox_after)
```

### Load Testing

**Using Locust:**

```python
from locust import HttpUser, task, between

class ZapierAPIUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Authenticate once per user
        response = self.client.post("/token", data={
            "username": "api",
            "password": "your-api-key"
        })
        self.token = response.json()["access_token"]

    @task(3)
    def create_event(self):
        self.client.post(
            "/events",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "type": "load.test",
                "source": "locust",
                "payload": {"test": True}
            }
        )

    @task(1)
    def get_inbox(self):
        self.client.get(
            "/inbox",
            headers={"Authorization": f"Bearer {self.token}"}
        )
```

**Run load test:**
```bash
locust -f load_test.py --host https://your-api-url.lambda-url.us-east-2.on.aws
```

## Troubleshooting

### Debug Checklist

When encountering issues:

1. **Check API Health:**
```bash
curl https://your-api-url.lambda-url.us-east-2.on.aws/health
```

2. **Verify Token:**
```bash
# Decode JWT (header.payload.signature)
echo $TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | jq
```

3. **Check CloudWatch Logs:**
```bash
aws logs tail /aws/lambda/{function-name} --follow
```

4. **Test DynamoDB Access:**
```bash
aws dynamodb describe-table --table-name zapier-triggers-events-{stackName}
```

5. **Verify Secrets:**
```bash
aws secretsmanager get-secret-value \
  --secret-id zapier-api-credentials-{stackName} | jq
```

### Common Issues

#### Issue: CORS Errors (Web Browser)

**Symptoms:**
```
Access to fetch at '...' from origin '...' has been blocked by CORS policy
```

**Solution:**

The API allows all origins (`allow_origins=["*"]`). If you still see CORS errors:

1. Check browser console for actual error
2. Verify request includes `Authorization` header
3. Ensure using HTTPS (not HTTP)

**Production Fix (restrict origins):**
```python
# In main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific domain
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
```

#### Issue: Lambda Timeout

**Symptoms:**
```json
{
  "message": "Task timed out after 30.00 seconds"
}
```

**Causes:**
- DynamoDB throttling
- Network issues
- Cold start + slow dependencies

**Solutions:**

1. **Increase Lambda timeout** (in backend.ts):
```typescript
lambda.addFunction({
  timeout: Duration.seconds(60),  // Increase from 30
});
```

2. **Monitor DynamoDB throttling:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name UserErrors \
  --dimensions Name=TableName,Value=zapier-triggers-events-{stackName} \
  --statistics Sum \
  --start-time 2024-01-15T00:00:00Z \
  --end-time 2024-01-15T23:59:59Z \
  --period 3600
```

#### Issue: Token Not Found in Secrets Manager

**Symptoms:**
```json
{
  "detail": "JWT secret not found in secrets manager"
}
```

**Solution:**

Generate and store JWT secret:

```bash
# Generate secret
JWT_SECRET=$(openssl rand -hex 32)

# Update Secrets Manager
aws secretsmanager update-secret \
  --secret-id zapier-api-credentials-{stackName} \
  --secret-string "$(jq -n \
    --arg jwt "$JWT_SECRET" \
    --arg key "your-api-key" \
    '{jwt_secret: $jwt, zapier_api_key: $key}')"
```

## Migration Guide

### Migrating from Webhook-Based Zapier Integration

**Current Setup:**
- Zapier → Receives webhooks directly from your app
- Your app → Sends HTTP POST to Zapier webhook URL

**New Setup:**
- Your app → Sends events to Zapier Triggers API
- Zapier → Polls API for new events

**Migration Steps:**

1. **Deploy Zapier Triggers API** (if not already done)

2. **Update Your Application:**
```python
# Before (direct webhook)
import requests

zapier_webhook_url = "https://hooks.zapier.com/hooks/catch/..."
requests.post(zapier_webhook_url, json=event_data)

# After (via API)
from zapier_triggers_client import ZapierTriggersClient

client = ZapierTriggersClient(API_URL, API_KEY)
client.create_event(
    event_type="user.signup",
    source="web-app",
    payload=event_data
)
```

3. **Update Zapier Zap:**
   - Change trigger from "Webhooks by Zapier" to custom polling trigger
   - Point to your API's `/inbox` endpoint
   - Configure authentication (API key)

4. **Test in Parallel:**
   - Run both integrations simultaneously
   - Compare results
   - Verify all events are received

5. **Cut Over:**
   - Disable old webhook-based integration
   - Monitor new integration for issues

**Benefits of Migration:**
- Buffering (events stored even if Zapier is down)
- Retry logic (events remain until acknowledged)
- Centralized event management
- Better observability (CloudWatch logs)

---

## Next Steps

You now have a comprehensive understanding of the Zapier Triggers API. Here's what to do next:

1. **Start Small:** Test with the quickstart guide ([QUICKSTART.md](./QUICKSTART.md))
2. **Read Examples:** Browse [examples/](../examples/) for code samples
3. **Set Up Monitoring:** Configure CloudWatch alerts ([MONITORING.md](./MONITORING.md))
4. **Review Security:** Implement security best practices ([SECURITY.md](./SECURITY.md))
5. **Plan Deployment:** Understand CI/CD process ([DEPLOYMENT.md](./DEPLOYMENT.md))

**Questions or Issues?**
- Check the [API documentation](https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws/docs)
- Review CloudWatch logs for errors
- Consult AWS documentation for Lambda, DynamoDB, and Secrets Manager

**Happy integrating!**
