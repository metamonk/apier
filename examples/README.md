# Code Examples

This directory contains practical code examples and integration patterns for the Zapier Triggers API.

## Directory Structure

```
examples/
├── curl/                    # Bash scripts with curl commands
│   ├── basic-flow.sh       # Complete authentication and event workflow
│   ├── bulk-events.sh      # Send multiple events
│   └── polling-consumer.sh # Event polling and acknowledgment loop
└── workflows/              # Common integration patterns
    ├── webhook-bridge.md   # Forward webhooks to Zapier
    ├── database-sync.md    # Track database changes
    └── scheduled-events.md # Generate events on schedule
```

## Quick Start

### curl Examples

The curl examples are standalone bash scripts that demonstrate API usage:

```bash
# Make scripts executable
chmod +x examples/curl/*.sh

# Set your API key
export API_KEY="your-api-key-here"

# Run basic flow example
./examples/curl/basic-flow.sh
```

**Prerequisites:**
- `curl` - HTTP client
- `jq` - JSON processor (install: `brew install jq` or `apt-get install jq`)
- API key from AWS Secrets Manager

### Workflows

The workflows directory contains detailed guides for common integration patterns:

- **[webhook-bridge.md](./workflows/webhook-bridge.md)** - Forward webhooks from external services (Stripe, Shopify) to Zapier
- **[database-sync.md](./workflows/database-sync.md)** - Trigger Zapier workflows on database changes
- **[scheduled-events.md](./workflows/scheduled-events.md)** - Generate events on a schedule (cron jobs, reports)

## Getting Your API Key

Retrieve your API key from AWS Secrets Manager:

```bash
aws secretsmanager get-secret-value \
  --secret-id zapier-api-credentials-{stackName} \
  --region us-east-2 \
  --query SecretString --output text | jq -r '.zapier_api_key'
```

Replace `{stackName}` with your actual Amplify stack name.

## Setting Environment Variables

For convenience, set these environment variables:

```bash
export API_URL="https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws"
export API_KEY="your-api-key-here"
```

## Example Scripts

### Basic Flow (`curl/basic-flow.sh`)

Demonstrates the complete API workflow:
1. Authenticate and get JWT token
2. Create an event
3. Retrieve inbox
4. Acknowledge event

**Usage:**
```bash
export API_KEY="your-key"
./examples/curl/basic-flow.sh
```

### Bulk Events (`curl/bulk-events.sh`)

Sends multiple events in succession:
- Demonstrates batch event creation
- Shows rate limiting best practices
- Includes error handling

**Usage:**
```bash
export API_KEY="your-key"
./examples/curl/bulk-events.sh 10  # Send 10 events
```

### Polling Consumer (`curl/polling-consumer.sh`)

Implements a polling loop to consume events:
- Polls inbox every 10 seconds
- Processes events (simulated)
- Acknowledges successful delivery
- Handles errors gracefully

**Usage:**
```bash
export API_KEY="your-key"
./examples/curl/polling-consumer.sh
```

Press Ctrl+C to stop.

## Language-Specific Examples

For language-specific client implementations, see the **[Developer Guide](../docs/DEVELOPER_GUIDE.md)**:

- **Python** - Full client with requests library
- **Node.js** - Async/await client with axios
- **Go** - Idiomatic Go client

## Integration Patterns

### Pattern 1: Webhook Bridge

Forward webhooks from external services to Zapier via the API.

**Use Case:** You receive webhooks from Stripe, Shopify, or other services but want to process them in Zapier.

**See:** [workflows/webhook-bridge.md](./workflows/webhook-bridge.md)

### Pattern 2: Database Sync

Track database changes and trigger Zapier workflows.

**Use Case:** User signup, order status changes, inventory updates.

**See:** [workflows/database-sync.md](./workflows/database-sync.md)

### Pattern 3: Scheduled Events

Generate events on a schedule for periodic tasks.

**Use Case:** Daily reports, weekly summaries, monthly billing.

**See:** [workflows/scheduled-events.md](./workflows/scheduled-events.md)

## Testing Examples

All examples can be tested against your development environment:

```bash
# Use development API URL
export API_URL="https://dev-api-url.lambda-url.us-east-2.on.aws"
export API_KEY="dev-api-key"

# Run examples
./examples/curl/basic-flow.sh
```

## Troubleshooting

### jq Not Found

**Error:** `jq: command not found`

**Solution:**
```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq

# CentOS/RHEL
sudo yum install jq
```

### API Key Invalid

**Error:** `401 Unauthorized` or `Incorrect username or password`

**Solution:**
1. Verify API key from Secrets Manager
2. Ensure no trailing whitespace in API_KEY variable
3. Check you're using the correct environment (dev/prod)

### Connection Timeout

**Error:** `curl: (7) Failed to connect`

**Solution:**
1. Verify API URL is correct
2. Check internet connectivity
3. Verify Lambda is deployed and running

## Additional Resources

- **[Quickstart Guide](../docs/QUICKSTART.md)** - Get started in 5 minutes
- **[Developer Guide](../docs/DEVELOPER_GUIDE.md)** - Comprehensive integration guide
- **[API Documentation](https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws/docs)** - Interactive Swagger UI

## Contributing Examples

Have a useful integration pattern? Contribute it:

1. Create a new file in the appropriate directory
2. Include clear documentation and comments
3. Test the example end-to-end
4. Submit a pull request

---

**Need help?** Check the [Developer Guide](../docs/DEVELOPER_GUIDE.md) or open an issue on GitHub.
