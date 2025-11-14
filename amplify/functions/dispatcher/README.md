# Event Dispatcher Service

The Event Dispatcher is a serverless Lambda function that automatically polls pending events from the Zapier Triggers API and delivers them to configured webhook URLs.

## Architecture

- **Runtime**: Python 3.12
- **Trigger**: EventBridge scheduled rule (every 5 minutes)
- **Timeout**: 5 minutes (300 seconds)
- **Memory**: 256 MB

## Features

### Event Processing
- Polls `/inbox` endpoint for pending events
- Processes up to 100 events per run
- Concurrent event delivery using asyncio

### Retry Logic
- Maximum 3 retry attempts per event
- Exponential backoff (1s → 2s → 4s, max 60s)
- Distinguishes between retryable (5xx, 429) and non-retryable (4xx) errors

### Webhook Delivery
- Uses httpx AsyncClient for HTTP requests
- 30-second timeout per request
- JWT authentication with the API
- Automatic event acknowledgment on success

### Monitoring & Logging
- CloudWatch Logs for detailed execution logs
- Custom CloudWatch metrics:
  - `EventsProcessed`: Total events processed
  - `SuccessfulDeliveries`: Successfully delivered events
  - `FailedDeliveries`: Failed delivery attempts
  - `DeliveryLatency`: Average delivery time in milliseconds
  - `RetryAttempts`: Total retry attempts
- CloudWatch alarms for error detection
- AWS X-Ray tracing enabled

## Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `API_BASE_URL` | Base URL of the Triggers API | `https://xxx.lambda-url.us-east-2.on.aws` |
| `DYNAMODB_TABLE_NAME` | DynamoDB table name | `zapier-triggers-events-api-stack` |
| `SECRET_ARN` | ARN of Secrets Manager secret | `arn:aws:secretsmanager:...` |
| `AWS_REGION` | AWS region | `us-east-2` |
| `MAX_EVENTS_PER_RUN` | Maximum events per execution | `100` |

### Required Secrets (AWS Secrets Manager)

The secret referenced by `SECRET_ARN` must contain:

```json
{
  "zapier_api_key": "your-api-key",
  "zapier_webhook_url": "https://hooks.zapier.com/...",
  "jwt_secret": "auto-generated-secret"
}
```

## IAM Permissions

The Lambda function requires:

- **DynamoDB**: `dynamodb:Query`, `dynamodb:UpdateItem` on the events table
- **Secrets Manager**: `secretsmanager:GetSecretValue` on the API secret
- **CloudWatch**: `cloudwatch:PutMetricData` for custom metrics
- **CloudWatch Logs**: `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
- **X-Ray**: `xray:PutTraceSegments`, `xray:PutTelemetryRecords`

## Workflow

1. **Authentication**: Authenticates with the API using the stored API key to obtain a JWT token
2. **Fetch Events**: Retrieves pending events from `/inbox` endpoint
3. **Concurrent Delivery**: Delivers events to webhook URL(s) concurrently
4. **Retry Logic**: Retries failed deliveries with exponential backoff
5. **Acknowledgment**: Marks successfully delivered events as "delivered" via `/inbox/{id}/ack`
6. **Metrics**: Publishes execution metrics to CloudWatch

## Testing

### Unit Tests

Run the test suite:

```bash
cd amplify/functions/dispatcher
pip install -r requirements-dev.txt
pytest tests/test_dispatcher.py -v
```

### Test Coverage

- Secret retrieval and caching
- JWT authentication
- Event fetching from inbox
- Webhook delivery with retry logic
- Event acknowledgment
- Metrics publishing
- Lambda handler execution

### Manual Testing

Invoke the Lambda function manually:

```bash
aws lambda invoke \
  --function-name <dispatcher-function-name> \
  --payload '{}' \
  response.json

cat response.json
```

## Monitoring

### CloudWatch Dashboard

The CDK stack creates a dashboard with:
- Event processing metrics (processed, successful, failed)
- Performance metrics (latency, retries)
- Lambda function metrics (invocations, errors, duration)

### CloudWatch Alarms

- **High Error Rate**: Triggers when >3 errors occur in 5 minutes
- Notifications sent to SNS topic

### CloudWatch Logs

View logs:

```bash
aws logs tail /aws/lambda/<function-name> --follow
```

### X-Ray Traces

View distributed traces in AWS X-Ray console to analyze:
- API call latency
- DynamoDB query performance
- Webhook delivery times
- Retry patterns

## Error Handling

### Non-Retryable Errors (4xx)
- Bad Request (400)
- Unauthorized (401)
- Forbidden (403)
- Not Found (404)

Events with non-retryable errors are **not** acknowledged and remain in "pending" status for manual review.

### Retryable Errors (5xx, 429)
- Internal Server Error (500)
- Bad Gateway (502)
- Service Unavailable (503)
- Gateway Timeout (504)
- Too Many Requests (429)

Events with retryable errors are retried with exponential backoff up to 3 attempts.

## Deployment

The dispatcher is deployed as part of the main CDK stack:

```bash
npm run build
npx ampx sandbox
```

Or for production:

```bash
npx ampx pipeline-deploy --branch main --appId <app-id>
```

## Scaling Considerations

### Current Limits
- **Events per run**: 100 (configurable via `MAX_EVENTS_PER_RUN`)
- **Execution frequency**: Every 5 minutes
- **Theoretical throughput**: ~1,200 events/hour (assuming all succeed on first attempt)

### Scaling Options

1. **Increase frequency**: Change EventBridge schedule to every 1-2 minutes
2. **Increase batch size**: Raise `MAX_EVENTS_PER_RUN` to 200-500
3. **Add concurrency**: Deploy multiple dispatchers with different webhook URLs
4. **Event-driven**: Replace scheduled trigger with DynamoDB Streams for real-time processing

## Troubleshooting

### Dispatcher not running
- Check EventBridge rule is enabled
- Verify Lambda function has correct permissions
- Check CloudWatch Logs for errors

### Events not being delivered
- Verify webhook URL in Secrets Manager
- Check webhook endpoint is accessible
- Review CloudWatch metrics for failed deliveries
- Check X-Ray traces for network issues

### High retry rates
- Investigate webhook endpoint performance
- Check for rate limiting (429 errors)
- Consider increasing backoff times or reducing batch size

## Development

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt -r requirements-dev.txt
```

2. Set environment variables:
```bash
export API_BASE_URL="https://..."
export DYNAMODB_TABLE_NAME="..."
export SECRET_ARN="arn:aws:secretsmanager:..."
```

3. Run locally:
```bash
python main.py
```

### Code Structure

- `main.py`: Main Lambda handler and event processing logic
- `tests/test_dispatcher.py`: Comprehensive unit tests
- `requirements.txt`: Production dependencies
- `requirements-dev.txt`: Development and testing dependencies

## Security

- API credentials stored in AWS Secrets Manager
- JWT authentication for API access
- Secrets cached per Lambda container (not per invocation)
- IAM least-privilege permissions
- HTTPS-only webhook delivery
- AWS X-Ray for security audit trails

## Cost Optimization

- Uses Lambda Function URL instead of API Gateway
- On-demand DynamoDB billing
- Secrets cached to minimize Secrets Manager API calls
- EventBridge scheduled rule (no polling infrastructure needed)
- X-Ray sampling reduces trace storage costs
