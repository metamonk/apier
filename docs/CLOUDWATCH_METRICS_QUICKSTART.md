# CloudWatch Metrics Quick Start Guide

This guide helps you verify that CloudWatch custom metrics are working after deployment.

## What Was Implemented

CloudWatch metrics integration has been added to the FastAPI backend to track:
- **Ingestion Latency**: How long POST /events takes to respond
- **API Uptime**: Success/failure rate for availability tracking
- **Error Rates**: Separate tracking for 4xx and 5xx errors
- **Request Counts**: Total API usage by endpoint

## Deployment Steps

### 1. Deploy the API

The metrics middleware is already integrated into `amplify/functions/api/main.py`.

```bash
# Deploy using Amplify
npx ampx sandbox

# Or if already deployed, the next deployment will include metrics
```

### 2. Generate Test Traffic

Make some API calls to generate metrics:

```bash
# Get your API URL from Amplify outputs
API_URL="https://your-function-url.lambda-url.us-east-2.on.aws"

# Test health endpoint (should succeed - 200)
curl -i "$API_URL/health"

# Test events endpoint without auth (should fail - 401)
curl -i -X POST "$API_URL/events" \
  -H "Content-Type: application/json" \
  -d '{"type":"test","source":"curl","payload":{"test":true}}'

# Get a JWT token
TOKEN=$(curl -s -X POST "$API_URL/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=api&password=YOUR_API_KEY" | jq -r '.access_token')

# Test authenticated request (should succeed - 201)
curl -i -X POST "$API_URL/events" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"type":"test","source":"curl","payload":{"test":true}}'
```

### 3. Wait for Metrics

CloudWatch metrics have a delay (typically 1-5 minutes). After making requests, wait a few minutes before checking.

### 4. Verify Metrics in AWS Console

**Option A: AWS Console**

1. Go to [CloudWatch Console](https://console.aws.amazon.com/cloudwatch/home?region=us-east-2)
2. Click "Metrics" → "All metrics"
3. Look for "ZapierTriggersAPI" under "Custom namespaces"
4. Click on it to see available metrics
5. Select metrics to visualize:
   - ApiLatency
   - ApiRequests
   - ApiErrors
   - Api4xxErrors
   - Api5xxErrors
   - ApiAvailability

**Option B: AWS CLI**

```bash
# List available metrics
aws cloudwatch list-metrics \
  --namespace ZapierTriggersAPI \
  --region us-east-2

# Get ApiLatency for POST /events (last 15 minutes)
aws cloudwatch get-metric-statistics \
  --namespace ZapierTriggersAPI \
  --metric-name ApiLatency \
  --dimensions Name=Endpoint,Value=/events Name=Method,Value=POST \
  --start-time $(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum,Minimum,SampleCount \
  --region us-east-2

# Get total API request count (last hour)
aws cloudwatch get-metric-statistics \
  --namespace ZapierTriggersAPI \
  --metric-name ApiRequests \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region us-east-2

# Get error count (last hour)
aws cloudwatch get-metric-statistics \
  --namespace ZapierTriggersAPI \
  --metric-name ApiErrors \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region us-east-2
```

### 5. Set Up Alarms

Once metrics are flowing, configure CloudWatch alarms:

```bash
# Run the automated setup script
./scripts/setup-alarms.sh

# Or manually create alarms (see docs/MONITORING.md for full details)
```

## Expected Results

After generating traffic and waiting a few minutes, you should see:

1. **Metrics Appear**: "ZapierTriggersAPI" namespace in CloudWatch
2. **Response Headers**: `X-Process-Time` header in API responses
3. **Dimensions**: Metrics grouped by Endpoint, Method, StatusCode
4. **Data Points**:
   - ApiLatency: Average ~50-200ms (depends on cold start)
   - ApiRequests: Sum equals number of requests made
   - ApiErrors: Sum equals number of failed requests
   - Api4xxErrors: Counts authentication failures (401s)
   - Api5xxErrors: Should be 0 (no server errors)
   - ApiAvailability: 1 for success, 0 for failure

## Troubleshooting

### Metrics Not Appearing

**Check Lambda logs:**
```bash
# Get your function name from Amplify outputs
FUNCTION_NAME="amplify-...-TriggersApiFunction-..."

# Tail logs to see metric publishing
aws logs tail /aws/lambda/$FUNCTION_NAME \
  --region us-east-2 \
  --follow \
  --format short
```

**Look for:**
- `"Failed to publish CloudWatch metrics:"` - Indicates metric publishing errors
- CloudWatch API errors in logs
- IAM permission issues

**Fix IAM permissions (if needed):**

The Lambda function needs `cloudwatch:PutMetricData` permission. This should be automatically granted, but if not:

```bash
# Add CloudWatch metrics permission to Lambda role
# (Replace ROLE_NAME with your Lambda execution role)
aws iam attach-role-policy \
  --role-name YOUR_LAMBDA_ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchFullAccess \
  --region us-east-2
```

### X-Process-Time Header Not Appearing

- Middleware should add this header automatically
- Check that middleware is registered before CORS middleware
- Verify no exceptions in Lambda logs

### High Latency Values

- First request (cold start) is typically 1-3 seconds
- Subsequent requests should be < 500ms
- Check Lambda memory allocation (currently 512MB)
- Review DynamoDB query performance
- Check Secrets Manager caching (should be cached after first call)

## Monitoring Best Practices

1. **Create CloudWatch Dashboard**
   - Add widgets for ApiLatency, ApiErrors, ApiRequests
   - Monitor trends over time
   - Share with team

2. **Set Up SNS Notifications**
   - Create SNS topic for alerts
   - Subscribe team email addresses
   - Attach to CloudWatch alarms

3. **Regular Review**
   - Daily: Check error logs
   - Weekly: Review latency trends
   - Monthly: Optimize based on patterns

4. **Cost Optimization**
   - Custom metrics: ~$0.30 per metric per month
   - API calls: $0.01 per 1,000 requests
   - Total estimated cost: < $5/month for moderate usage

## Next Steps

- [ ] Verify metrics are flowing
- [ ] Create CloudWatch dashboard
- [ ] Set up alarms using `./scripts/setup-alarms.sh`
- [ ] Configure SNS notifications
- [ ] Document metric baseline values
- [ ] Set up automated monitoring reports

## References

- [Full Monitoring Guide](./MONITORING.md)
- [CloudWatch Custom Metrics Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/publishingMetrics.html)
- [FastAPI Middleware](https://fastapi.tiangolo.com/tutorial/middleware/)

---

**Last Updated**: 2025-11-13
**Maintained By**: Development Team
