# Quickstart Guide

Get up and running with the Zapier Triggers API in 5 minutes.

## What is the Zapier Triggers API?

The Zapier Triggers API is a serverless event ingestion and delivery system that enables external systems to send events that can be consumed by Zapier automation workflows. It acts as a bridge between your applications and Zapier, providing a reliable polling-based event delivery mechanism.

**Key Use Cases:**
- Send webhook events to Zapier without exposing your infrastructure
- Buffer and queue events for reliable delivery
- Trigger Zapier workflows from any application or service
- Build custom integrations with automatic retry and acknowledgment

## Prerequisites

Before you begin, ensure you have:

1. **AWS Account** - For accessing the deployed API
2. **API Key** - Your Zapier API key (stored in AWS Secrets Manager)
3. **curl** or any HTTP client - For making API requests

## Step 1: Get Your API URL

The API is deployed on AWS Lambda with a unique Function URL. Find your API URL:

**Production API:**
```
https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws
```

**Test the API is running:**
```bash
curl https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws/health
```

**Expected response:**
```json
{
  "status": "healthy"
}
```

## Step 2: Get Your API Key

Your API key is stored securely in AWS Secrets Manager. Retrieve it using the AWS CLI:

```bash
# For production environment
aws secretsmanager get-secret-value \
  --secret-id zapier-api-credentials-{stackName} \
  --region us-east-2 \
  --query SecretString --output text | jq -r '.zapier_api_key'
```

Replace `{stackName}` with your actual stack name from AWS Amplify Console.

**Don't have AWS CLI access?** Ask your system administrator for the API key.

## Step 3: Obtain a JWT Token

All protected API endpoints require JWT authentication. Get your token:

```bash
# Store your API key
export API_KEY="your-api-key-here"
export API_URL="https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws"

# Get JWT token
curl -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=api&password=$API_KEY"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Store the token for convenience:**
```bash
export TOKEN=$(curl -s -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=api&password=$API_KEY" | jq -r '.access_token')

echo "Token: $TOKEN"
```

**Token expires in 24 hours.** You'll need to request a new one after expiration.

## Step 4: Send Your First Event

Post an event to the API:

```bash
curl -X POST "$API_URL/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "user.created",
    "source": "my-app",
    "payload": {
      "user_id": "12345",
      "email": "user@example.com",
      "name": "John Doe"
    }
  }'
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Congratulations!** You've created your first event. The event is now stored and ready for Zapier to consume.

## Step 5: Retrieve Pending Events (Inbox)

Zapier polls the inbox endpoint to retrieve events. You can test this:

```bash
curl -X GET "$API_URL/inbox" \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "user.created",
    "source": "my-app",
    "payload": {
      "user_id": "12345",
      "email": "user@example.com",
      "name": "John Doe"
    },
    "status": "pending",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
]
```

## Step 6: Acknowledge Event Delivery

After Zapier processes an event, it acknowledges delivery to mark the event as "delivered":

```bash
# Replace with your actual event ID from Step 4
EVENT_ID="550e8400-e29b-41d4-a716-446655440000"

curl -X POST "$API_URL/inbox/$EVENT_ID/ack" \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "delivered",
  "message": "Event acknowledged successfully",
  "updated_at": "2024-01-15T10:31:00Z"
}
```

The event will no longer appear in the inbox after acknowledgment.

## Complete Example Script

Here's a complete script that demonstrates the full workflow:

```bash
#!/bin/bash
# Save as: quickstart.sh

# Configuration
API_URL="https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws"
API_KEY="your-api-key-here"

echo "1. Getting JWT token..."
TOKEN=$(curl -s -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=api&password=$API_KEY" | jq -r '.access_token')

echo "   Token: ${TOKEN:0:20}..."

echo -e "\n2. Creating event..."
EVENT=$(curl -s -X POST "$API_URL/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "user.created",
    "source": "quickstart",
    "payload": {
      "user_id": "12345",
      "email": "user@example.com"
    }
  }')

echo "$EVENT" | jq

EVENT_ID=$(echo "$EVENT" | jq -r '.id')

echo -e "\n3. Retrieving inbox..."
curl -s -X GET "$API_URL/inbox" \
  -H "Authorization: Bearer $TOKEN" | jq

echo -e "\n4. Acknowledging event $EVENT_ID..."
curl -s -X POST "$API_URL/inbox/$EVENT_ID/ack" \
  -H "Authorization: Bearer $TOKEN" | jq

echo -e "\n5. Verifying inbox (should be empty)..."
curl -s -X GET "$API_URL/inbox" \
  -H "Authorization: Bearer $TOKEN" | jq
```

**Run it:**
```bash
chmod +x quickstart.sh
./quickstart.sh
```

## Common Use Cases

### 1. Webhook to Zapier Bridge

Use the API as a bridge for webhooks:

```bash
# Receive webhook from external service
# Forward to Zapier Triggers API

curl -X POST "$API_URL/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "order.placed",
    "source": "shopify",
    "payload": {
      "order_id": "ORD-2024-001",
      "customer_email": "customer@example.com",
      "total": 99.99,
      "items": [...]
    }
  }'
```

### 2. Scheduled Event Publishing

Generate events on a schedule:

```bash
# In your cron job or scheduled task
EVENT_TYPE="daily.report"
EVENT_SOURCE="reporting-system"

curl -X POST "$API_URL/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"$EVENT_TYPE\",
    \"source\": \"$EVENT_SOURCE\",
    \"payload\": {
      \"date\": \"$(date -I)\",
      \"metrics\": {...}
    }
  }"
```

### 3. Application Event Streaming

Stream application events in real-time:

```python
import requests

API_URL = "https://your-api-url.lambda-url.us-east-2.on.aws"
TOKEN = "your-jwt-token"

def send_event(event_type, source, payload):
    response = requests.post(
        f"{API_URL}/events",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "type": event_type,
            "source": source,
            "payload": payload
        }
    )
    return response.json()

# Example: User signup event
send_event(
    event_type="user.signup",
    source="web-app",
    payload={"user_id": "123", "email": "user@example.com"}
)
```

## Troubleshooting

### Issue: 401 Unauthorized

**Symptoms:**
```json
{
  "detail": "Could not validate credentials"
}
```

**Solutions:**
1. **Token expired** - Request a new token (tokens expire after 24 hours)
2. **Wrong API key** - Verify API key from Secrets Manager
3. **Missing Authorization header** - Ensure header is `Authorization: Bearer {token}`

**Debug:**
```bash
# Check if token is valid (decode JWT)
echo $TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | jq

# Request new token
TOKEN=$(curl -s -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=api&password=$API_KEY" | jq -r '.access_token')
```

### Issue: Connection Refused / Timeout

**Symptoms:**
```
curl: (7) Failed to connect to host
```

**Solutions:**
1. **Wrong URL** - Verify API URL is correct
2. **Network issue** - Check internet connectivity
3. **API down** - Check AWS Lambda status in CloudWatch

**Debug:**
```bash
# Test connectivity
curl -v $API_URL/health

# Check DNS resolution
nslookup your-api-url.lambda-url.us-east-2.on.aws
```

### Issue: 500 Internal Server Error

**Symptoms:**
```json
{
  "detail": "Internal server error"
}
```

**Solutions:**
1. **Check CloudWatch Logs** - Lambda logs will show the error
2. **Verify Secrets** - Ensure secrets are configured in Secrets Manager
3. **DynamoDB access** - Verify Lambda has permissions to DynamoDB

**Debug:**
```bash
# View Lambda logs
aws logs tail /aws/lambda/{function-name} --follow
```

### Issue: Empty Inbox

**Symptoms:**
Inbox returns `[]` even after creating events.

**Possible Causes:**
1. **Events already acknowledged** - Events disappear after acknowledgment
2. **Wrong environment** - Check you're using the correct API URL
3. **Events expired** - Events auto-delete after 90 days

**Debug:**
```bash
# Create a new event and immediately check inbox
curl -X POST "$API_URL/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"type": "test", "source": "debug", "payload": {}}' && \
curl -X GET "$API_URL/inbox" \
  -H "Authorization: Bearer $TOKEN" | jq
```

## API Rate Limits

The API currently has no enforced rate limits, but follow these guidelines:

- **Event creation:** Max 100 events/second recommended
- **Inbox polling:** Poll every 5-15 seconds (Zapier default)
- **Token requests:** Reuse tokens (24-hour validity)

Exceeding these guidelines may result in throttling or increased costs.

## Data Retention

**Important:** All events automatically expire after **90 days** (GDPR/CCPA compliance).

- Events are marked with a TTL (Time To Live) timestamp
- DynamoDB automatically deletes expired events
- No action required on your part

## Next Steps

Now that you're up and running:

1. **Read the Developer Guide** - [docs/DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md) for advanced patterns
2. **Explore the API** - Visit the interactive docs at `$API_URL/docs`
3. **Set up Monitoring** - See [docs/MONITORING.md](./MONITORING.md)
4. **Review Security** - Read [docs/SECURITY.md](./SECURITY.md)
5. **Check Examples** - Browse [examples/](../examples/) for more code samples

## Get Help

- **Interactive API Docs:** https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws/docs
- **GitHub Issues:** Report bugs or request features
- **AWS Documentation:** [AWS Amplify](https://docs.amplify.aws), [Lambda](https://docs.aws.amazon.com/lambda/), [DynamoDB](https://docs.aws.amazon.com/dynamodb/)

## Additional Resources

- [API Documentation (Swagger UI)](https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws/docs)
- [OpenAPI Specification](https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws/openapi.json)
- [ReDoc Alternative Docs](https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws/redoc)

---

**Happy building!** You're now ready to integrate the Zapier Triggers API into your applications.
