# Curl Examples

Bash scripts demonstrating Zapier Triggers API usage with curl.

## Prerequisites

- **curl** - HTTP client (usually pre-installed)
- **jq** - JSON processor
  ```bash
  # macOS
  brew install jq

  # Ubuntu/Debian
  sudo apt-get install jq

  # CentOS/RHEL
  sudo yum install jq
  ```
- **API Key** - From AWS Secrets Manager

## Setup

1. **Make scripts executable:**
   ```bash
   chmod +x *.sh
   ```

2. **Set your API key:**
   ```bash
   export API_KEY="your-api-key-here"
   ```

3. **Optional: Set custom API URL:**
   ```bash
   export API_URL="https://your-custom-url.lambda-url.us-east-2.on.aws"
   ```

## Scripts

### basic-flow.sh

Complete API workflow demonstrating all endpoints.

**What it does:**
1. Authenticates and gets JWT token
2. Creates an event
3. Retrieves inbox
4. Acknowledges event delivery
5. Verifies event removed from inbox

**Usage:**
```bash
export API_KEY="your-key"
./basic-flow.sh
```

**Example output:**
```
==========================================
  Zapier Triggers API - Basic Flow
==========================================

==> Step 1: Authenticating with API...
  URL: https://...lambda-url.us-east-2.on.aws/token
  Username: api

✓ Authentication successful
  Token: eyJhbGciOiJIUzI1N...

==> Step 2: Creating event...
  Event data:
  {
    "type": "user.signup",
    "source": "basic-flow-example",
    "payload": {...}
  }

✓ Event created successfully
  Event ID: 550e8400-e29b-41d4-a716-446655440000
  Status: pending

...
```

### bulk-events.sh

Sends multiple events with rate limiting.

**What it does:**
- Creates multiple events in succession
- Implements rate limiting (10 events/second)
- Tracks success/failure counts
- Shows performance metrics

**Usage:**
```bash
export API_KEY="your-key"
./bulk-events.sh 10  # Send 10 events
```

**Example output:**
```
==========================================
  Sending 10 events
  Rate: ~10 events/second
==========================================

[1/10] Created user.signup: 550e8400-...
[2/10] Created user.login: 660f9511-...
[3/10] Created order.placed: 770a0622-...
...

==========================================
  Summary
==========================================

  Total events: 10
  Successful: 10
  Failed: 0
  Time elapsed: 2s
  Average rate: 5.00 events/second
```

### polling-consumer.sh

Continuous polling loop to consume events (like Zapier).

**What it does:**
- Polls inbox every 10 seconds
- Processes events (simulated)
- Acknowledges successful delivery
- Runs until stopped with Ctrl+C

**Usage:**
```bash
export API_KEY="your-key"
./polling-consumer.sh
```

**Example output:**
```
==========================================
  Zapier Triggers API - Polling Consumer
==========================================

  API URL: https://...lambda-url.us-east-2.on.aws
  Poll interval: 10s

  Press Ctrl+C to stop
==========================================

[2024-01-15 10:30:00] Polling inbox...
✓ Found 2 pending event(s)

==> Processing event: 550e8400-e29b-41d4-a716-446655440000
  Type: user.signup
  Source: web-app
  Payload:
  {
    "user_id": "12345",
    "email": "user@example.com"
  }
  Processing... (1.2s)
✓ Event acknowledged: 550e8400-...

...

[2024-01-15 10:30:15] Polling inbox...
  No pending events
  Waiting 10s for next poll...
```

Press Ctrl+C to stop:
```
==========================================
  Polling stopped (Ctrl+C)
==========================================

  Total events processed: 5
  Total errors: 0
```

## Common Workflows

### Test the complete flow

```bash
# 1. Run basic flow to understand the API
./basic-flow.sh

# 2. Create some test events
./bulk-events.sh 5

# 3. Start polling consumer to process them
./polling-consumer.sh
```

### Simulate production load

```bash
# Terminal 1: Start consumer
./polling-consumer.sh

# Terminal 2: Generate events
while true; do
    ./bulk-events.sh 10
    sleep 30
done
```

## Troubleshooting

### Script shows "command not found"

Make scripts executable:
```bash
chmod +x *.sh
```

### jq not found

Install jq:
```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq
```

### Authentication fails

1. Verify API key:
   ```bash
   echo $API_KEY
   ```

2. Get API key from Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id zapier-api-credentials-{stackName} \
     --region us-east-2 \
     --query SecretString --output text | jq -r '.zapier_api_key'
   ```

3. Set API key:
   ```bash
   export API_KEY="actual-key-here"
   ```

### Connection timeout

1. Verify API URL:
   ```bash
   echo $API_URL
   ```

2. Test connectivity:
   ```bash
   curl -v $API_URL/health
   ```

3. Check Lambda is running in AWS Console

## Environment Variables

All scripts support these environment variables:

- `API_URL` - API base URL (default: production URL)
- `API_KEY` - Your API key (required)

**Example:**
```bash
export API_URL="https://dev-api.lambda-url.us-east-2.on.aws"
export API_KEY="dev-api-key"
./basic-flow.sh
```

## Next Steps

- **Python/Node.js examples:** See [Developer Guide](../../docs/DEVELOPER_GUIDE.md)
- **Integration patterns:** See [workflows/](../workflows/)
- **API documentation:** https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws/docs
