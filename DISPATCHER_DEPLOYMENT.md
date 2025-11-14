# Dispatcher Service Deployment Guide

## Overview

The Event Dispatcher Service has been successfully implemented and is ready for deployment. This document provides deployment instructions and a summary of what was created.

## What Was Created

### 1. Lambda Function Code
**Location**: `/Users/zeno/Projects/zapier/apier/amplify/functions/dispatcher/`

- **main.py**: Core Lambda handler with async event processing
  - JWT authentication with API
  - Event fetching from /inbox endpoint
  - Webhook delivery with httpx AsyncClient
  - Exponential backoff retry logic (3 attempts, 1s → 2s → 4s → 60s max)
  - Event acknowledgment via /inbox/{id}/ack
  - CloudWatch metrics publishing
  - AWS X-Ray tracing

- **requirements.txt**: Production dependencies
  - httpx==0.27.2 (async HTTP client)
  - boto3==1.35.76 (AWS SDK)
  - aws-xray-sdk==2.14.0 (tracing)

- **requirements-dev.txt**: Development dependencies
  - pytest==8.3.4
  - pytest-asyncio==0.24.0
  - pytest-mock==3.14.0
  - moto[dynamodb]==5.0.20

- **tests/test_dispatcher.py**: Comprehensive unit tests (18+ test cases)
  - Tests for secret retrieval, authentication, event fetching
  - Tests for retry logic, timeout handling, error scenarios
  - Tests for acknowledgment and metrics publishing
  - Mock-based testing for AWS services

- **README.md**: Complete service documentation
  - Architecture overview
  - Configuration guide
  - Workflow documentation
  - Monitoring and troubleshooting guides

### 2. CDK Infrastructure
**Location**: `/Users/zeno/Projects/zapier/apier/amplify/backend.ts`

Added the following resources:

- **DispatcherFunction**: Lambda function
  - Python 3.12 runtime
  - 256MB memory, 5-minute timeout
  - Environment variables configured
  - IAM permissions for DynamoDB, Secrets Manager, CloudWatch

- **DispatcherScheduleRule**: EventBridge rule
  - Triggers every 5 minutes
  - Rate schedule: `rate(5 minutes)`
  - Retry attempts: 2

- **DispatcherErrorAlarm**: CloudWatch alarm
  - Triggers on >3 errors in 5 minutes
  - Sends notifications to SNS topic

- **Dashboard Widgets**: Two new widgets
  - Event Processing metrics (processed, successful, failed)
  - Performance metrics (latency, retries)

### 3. Configuration Requirements

The following must be configured in AWS Secrets Manager:

```json
{
  "zapier_api_key": "your-api-key",
  "zapier_webhook_url": "https://hooks.zapier.com/...",
  "jwt_secret": "auto-generated-secret"
}
```

## Deployment Steps

### Step 1: Install Dependencies Locally (Optional - for testing)

```bash
cd amplify/functions/dispatcher
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/test_dispatcher.py -v
```

### Step 2: Update Secrets Manager

Before deploying, update the secret with your webhook URL:

```bash
# Get the secret ARN from previous deployment
SECRET_ARN=$(aws cloudformation describe-stacks \
  --stack-name amplify-apier-main \
  --query "Stacks[0].Outputs[?OutputKey=='ApiSecretArn'].OutputValue" \
  --output text)

# Update the secret with your webhook URL
aws secretsmanager update-secret \
  --secret-id "$SECRET_ARN" \
  --secret-string '{
    "zapier_api_key": "your-actual-api-key",
    "zapier_webhook_url": "https://hooks.zapier.com/your-webhook-url",
    "jwt_secret": "your-jwt-secret"
  }'
```

### Step 3: Deploy the Stack

Using AWS Amplify:

```bash
# For sandbox deployment
npm run build
npx ampx sandbox

# For production deployment
npx ampx pipeline-deploy --branch main --appId <your-app-id>
```

### Step 4: Verify Deployment

After deployment, check the outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name amplify-apier-main \
  --query "Stacks[0].Outputs" \
  --output table
```

Look for:
- **DispatcherFunctionArn**: ARN of the dispatcher Lambda
- **DispatcherScheduleRuleName**: Name of the EventBridge rule

### Step 5: Test the Dispatcher

1. **Create a test event**:
```bash
API_URL="<your-api-url-from-outputs>"
API_KEY="<your-api-key>"

# Get JWT token
TOKEN=$(curl -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=api&password=$API_KEY" | jq -r '.access_token')

# Create a test event
curl -X POST "$API_URL/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "test.event",
    "source": "manual",
    "payload": {"message": "Test dispatcher"}
  }'
```

2. **Manually invoke the dispatcher** (optional):
```bash
FUNCTION_NAME=$(aws cloudformation describe-stacks \
  --stack-name amplify-apier-main \
  --query "Stacks[0].Outputs[?OutputKey=='DispatcherFunctionArn'].OutputValue" \
  --output text | cut -d: -f7)

aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload '{}' \
  response.json

cat response.json
```

3. **Wait 5 minutes** for the EventBridge schedule to trigger, or manually invoke as shown above.

4. **Check CloudWatch Logs**:
```bash
aws logs tail /aws/lambda/<function-name> --follow
```

5. **Verify the event was delivered**:
```bash
# Check if event status changed to "delivered"
curl -X GET "$API_URL/inbox" \
  -H "Authorization: Bearer $TOKEN"
```

### Step 6: Monitor with CloudWatch

1. **Open CloudWatch Dashboard**:
```bash
aws cloudformation describe-stacks \
  --stack-name amplify-apier-main \
  --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" \
  --output text
```

2. **Check Custom Metrics**:
   - Navigate to CloudWatch > Metrics
   - Select "ZapierTriggersAPI/Dispatcher" namespace
   - View:
     - EventsProcessed
     - SuccessfulDeliveries
     - FailedDeliveries
     - DeliveryLatency
     - RetryAttempts

3. **Check Alarms**:
   - Navigate to CloudWatch > Alarms
   - Verify "zapier-dispatcher-errors-..." alarm exists

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    EventBridge Schedule                      │
│                     (Every 5 minutes)                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Dispatcher Lambda Function                  │
│                                                              │
│  1. Authenticate with API (JWT)                             │
│  2. Fetch pending events from /inbox                        │
│  3. Deliver to webhook (with retry)                         │
│  4. Acknowledge delivered events                            │
│  5. Publish metrics to CloudWatch                           │
└────────┬──────────────────────┬────────────────────┬────────┘
         │                      │                    │
         ▼                      ▼                    ▼
┌────────────────┐    ┌──────────────────┐  ┌──────────────┐
│  Triggers API  │    │  Webhook URL     │  │  CloudWatch  │
│  (/inbox, /ack)│    │  (Zapier Hooks)  │  │  (Metrics)   │
└────────────────┘    └──────────────────┘  └──────────────┘
         │
         ▼
┌────────────────┐
│   DynamoDB     │
│ (Events Table) │
└────────────────┘
```

## Configuration

### Environment Variables (Auto-configured by CDK)

| Variable | Value | Description |
|----------|-------|-------------|
| API_BASE_URL | `https://xxx.lambda-url.us-east-2.on.aws` | Triggers API endpoint |
| DYNAMODB_TABLE_NAME | `zapier-triggers-events-api-stack` | DynamoDB table name |
| SECRET_ARN | `arn:aws:secretsmanager:...` | Secrets Manager ARN |
| AWS_REGION | `us-east-2` | AWS region |
| MAX_EVENTS_PER_RUN | `100` | Max events per execution |

### Retry Configuration (In code, can be modified)

| Setting | Value | Location |
|---------|-------|----------|
| MAX_RETRIES | 3 | main.py |
| INITIAL_BACKOFF_SECONDS | 1 | main.py |
| MAX_BACKOFF_SECONDS | 60 | main.py |

### Schedule Configuration

- **Frequency**: Every 5 minutes
- **Location**: amplify/backend.ts line 371
- **To change**: Modify `events.Schedule.rate(cdk.Duration.minutes(5))`

## Monitoring & Alerts

### CloudWatch Metrics

All metrics are published to `ZapierTriggersAPI/Dispatcher` namespace:

| Metric | Description | Unit |
|--------|-------------|------|
| EventsProcessed | Total events processed | Count |
| SuccessfulDeliveries | Successfully delivered events | Count |
| FailedDeliveries | Failed delivery attempts | Count |
| DeliveryLatency | Average delivery time | Milliseconds |
| RetryAttempts | Total retry attempts | Count |

### CloudWatch Alarms

| Alarm | Threshold | Action |
|-------|-----------|--------|
| High Error Rate | >3 errors in 5 min | SNS notification |

### Logs

View logs:
```bash
aws logs tail /aws/lambda/<function-name> --follow
```

Filter for specific event:
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/<function-name> \
  --filter-pattern "event_id"
```

## Troubleshooting

### Issue: Events not being delivered

**Check:**
1. Webhook URL is correct in Secrets Manager
2. Webhook endpoint is accessible (test with curl)
3. API authentication is working (check logs for "Authentication failed")
4. DynamoDB table has pending events

**Debug:**
```bash
# Check pending events
curl -X GET "$API_URL/inbox" -H "Authorization: Bearer $TOKEN"

# Check webhook URL
aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ARN" \
  --query SecretString \
  --output text | jq -r '.zapier_webhook_url'

# Test webhook manually
curl -X POST "https://hooks.zapier.com/your-webhook" \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### Issue: High retry rates

**Possible causes:**
1. Webhook endpoint is slow or timing out
2. Rate limiting (429 errors)
3. Network issues

**Solutions:**
1. Increase webhook timeout on receiving end
2. Reduce MAX_EVENTS_PER_RUN to avoid overwhelming webhook
3. Increase backoff times

### Issue: Dispatcher not running

**Check:**
1. EventBridge rule is enabled
2. Lambda function has correct permissions
3. No errors in CloudWatch Logs

**Debug:**
```bash
# Check EventBridge rule
aws events describe-rule \
  --name "zapier-dispatcher-schedule-api-stack"

# Check Lambda function
aws lambda get-function \
  --function-name "$FUNCTION_NAME"

# Manually invoke
aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload '{}' \
  response.json
```

## Scaling Considerations

### Current Capacity
- **Events per run**: 100
- **Runs per hour**: 12 (every 5 minutes)
- **Theoretical throughput**: ~1,200 events/hour

### To Scale Up

1. **Increase frequency**:
   - Change schedule to every 1 minute: `rate(1 minute)`
   - Throughput: ~6,000 events/hour

2. **Increase batch size**:
   - Change MAX_EVENTS_PER_RUN to 500
   - Throughput: ~6,000 events/hour (at 5-minute intervals)

3. **Add concurrency**:
   - Deploy multiple dispatchers with different webhook URLs
   - Use DynamoDB conditions to avoid duplicate processing

4. **Event-driven architecture**:
   - Replace scheduled trigger with DynamoDB Streams
   - Near real-time processing

## Cost Estimation

### Lambda
- **Invocations**: 12/hour × 24 hours × 30 days = 8,640/month
- **Duration**: ~2 seconds per invocation (avg)
- **Memory**: 256 MB
- **Estimated cost**: ~$0.10/month (within free tier)

### EventBridge
- **Rules**: 1 rule
- **Invocations**: 8,640/month
- **Estimated cost**: Free (well under 3M events)

### CloudWatch
- **Metrics**: 5 custom metrics
- **Logs**: ~10 MB/month
- **Estimated cost**: ~$0.50/month

### Total Estimated Cost: ~$0.60/month

## Next Steps

1. **Deploy to production** using the steps above
2. **Configure webhook URL** in Secrets Manager
3. **Monitor the first few runs** in CloudWatch
4. **Set up SNS email subscription** for alarm notifications
5. **Consider Task 9**: Develop Receiver UI for webhook endpoint

## Related Tasks

- **Task 8**: ✅ Develop Dispatcher Service (COMPLETED)
  - Subtask 8.1: ✅ Create Lambda function code
  - Subtask 8.2: ✅ Implement retry logic
  - Subtask 8.3: ✅ Add CDK infrastructure
  - Subtask 8.4: ✅ Implement event polling
  - Subtask 8.5: ✅ Add logging and metrics
  - Subtask 8.6: ✅ Create unit tests

- **Task 9**: ⏳ Develop Receiver UI (NEXT)
  - Create webhook receiver endpoint
  - Implement event logging
  - Add signature validation

## Files Created

```
amplify/functions/dispatcher/
├── main.py                      # Lambda handler (600 lines)
├── requirements.txt             # Production dependencies
├── requirements-dev.txt         # Development dependencies
├── README.md                    # Service documentation
└── tests/
    ├── __init__.py
    └── test_dispatcher.py       # Unit tests (550+ lines)

amplify/backend.ts               # Updated with dispatcher resources

DISPATCHER_DEPLOYMENT.md         # This file
```

## Support

For issues or questions:
1. Check CloudWatch Logs for error messages
2. Review the README.md in amplify/functions/dispatcher/
3. Run unit tests: `pytest tests/test_dispatcher.py -v`
4. Check AWS X-Ray traces for distributed tracing
