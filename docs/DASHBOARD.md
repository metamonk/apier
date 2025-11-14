# API/er Monitoring Dashboard

Real-time monitoring dashboard for the Zapier Triggers API, providing comprehensive visibility into event processing, delivery performance, and system health.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Dashboard Features](#dashboard-features)
- [Metrics Explained](#metrics-explained)
- [Setup Instructions](#setup-instructions)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

## Quick Start

### Accessing the Dashboard

The dashboard is deployed via AWS Amplify and is accessible at:

**Production**: `https://{amplify-app-id}.amplifyapp.com`
**Development**: `https://dev.{amplify-app-id}.amplifyapp.com`
**Sandbox**: `https://sandbox.{amplify-app-id}.amplifyapp.com`

Find your specific URL in the AWS Amplify Console after deployment.

### First-Time Setup

1. **Configure Environment Variables**: Create a `.env` file in the `frontend/` directory:
   ```bash
   VITE_API_URL=https://your-lambda-url.lambda-url.us-east-2.on.aws
   VITE_API_KEY=your_api_key_here
   ```

2. **Obtain API Key**: Retrieve from AWS Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id zapier-api-credentials-{stackName} \
     --query SecretString --output text | jq -r '.zapier_api_key'
   ```

3. **Access Dashboard**: Open the dashboard URL in your browser. Authentication is automatic using the configured API key.

## Architecture Overview

### Technology Stack

```
┌─────────────────────────────────────────────────────────┐
│                    React Frontend                        │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────┐     │
│  │ Dashboard  │  │ Events Page  │  │ Webhooks    │     │
│  │ (Landing)  │  │ (Management) │  │ (Receiver)  │     │
│  └─────┬──────┘  └──────┬───────┘  └──────┬──────┘     │
│        │                │                  │            │
│        └────────────────┴──────────────────┘            │
│                         │                               │
│                    JWT Auth Layer                       │
│                         │                               │
└─────────────────────────┼───────────────────────────────┘
                          │
                     HTTPS/TLS
                          │
┌─────────────────────────┼───────────────────────────────┐
│               FastAPI Backend (Lambda)                   │
│  ┌──────────────────────────────────────────────┐       │
│  │  Metrics Endpoints                            │       │
│  │  • GET /metrics/summary                       │       │
│  │  • GET /metrics/latency                       │       │
│  │  • GET /metrics/throughput                    │       │
│  │  • GET /metrics/errors                        │       │
│  └──────────────────────────────────────────────┘       │
│                         │                               │
│                    Query Logic                          │
│                         │                               │
└─────────────────────────┼───────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────┐
│                   DynamoDB Table                         │
│  ┌──────────────────────────────────────────────┐       │
│  │  Events Table                                 │       │
│  │  • Primary Key: id + created_at               │       │
│  │  • GSI: status-index                          │       │
│  │  • GSI: last-attempt-index                    │       │
│  │  • TTL: 90 days (GDPR/CCPA compliance)        │       │
│  └──────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

### Component Architecture

**Frontend Components** (`frontend/src/`):
- **DashboardPage**: Landing page with real-time metrics visualization
  - EventCountCards: Summary statistics (total, pending, delivered, failed)
  - LifecycleFlow: Visual flow diagram of event lifecycle
  - MetricsCharts: Latency and throughput visualizations
  - SendEventSheet: Quick event submission interface
- **EventsPage**: Full event management with filtering and export
- **WebhooksPage**: Webhook receiver monitoring

**Backend API** (`amplify/functions/api/main.py`):
- FastAPI application running on AWS Lambda
- JWT authentication for all protected endpoints
- CloudWatch custom metrics for monitoring
- DynamoDB for event storage and querying

**Infrastructure** (`amplify/backend.ts`):
- AWS Amplify Gen 2 with CDK
- Lambda Function URL (HTTPS-only)
- DynamoDB with GSIs for efficient querying
- Secrets Manager for credential storage
- CloudWatch alarms and dashboards

## Dashboard Features

### 1. Event Summary Cards

Real-time overview of event statistics:
- **Total Events**: Cumulative count of all events in the system
- **Pending**: Events awaiting delivery to webhooks
- **Delivered**: Successfully delivered events
- **Failed**: Events that exceeded retry limits
- **Success Rate**: Percentage of successful deliveries (delivered / (delivered + failed))

**Auto-refresh**: Updates every 10 seconds (configurable via Pause/Resume)

### 2. Event Lifecycle Flow

Visual representation of the event journey:
```
Created → Pending → Delivered ✓
                 → Failed ✗
```

Shows the current distribution of events across lifecycle states with:
- Event counts per stage
- Visual flow with arrows
- Color-coded status indicators

### 3. Performance Metrics

#### Latency Chart
Displays event delivery latency percentiles:
- **P50 (Median)**: 50% of events delivered faster than this
- **P95**: 95% of events delivered faster than this
- **P99**: 99% of events delivered faster than this

**Interpretation**:
- P50 < 500ms: Excellent performance
- P95 < 2s: Good performance
- P99 > 5s: Investigate slow events

#### Throughput Chart
Shows events processed per time interval:
- **Events per minute**: Current processing rate
- **Time-series view**: 24-hour rolling window
- **Trend analysis**: Identify peak usage periods

### 4. Quick Actions

- **Send Event**: Submit test events directly from the dashboard
- **Refresh**: Manual metrics refresh
- **Pause/Resume**: Control auto-refresh behavior
- **Navigate**: Quick links to Events and Webhooks pages

## Metrics Explained

### Event Summary Metrics

**Endpoint**: `GET /metrics/summary`

```json
{
  "total": 1247,
  "pending": 23,
  "delivered": 1198,
  "failed": 26,
  "success_rate": 97.91
}
```

**Fields**:
- `total`: Total event count across all statuses
- `pending`: Events with status="pending" (awaiting delivery)
- `delivered`: Events with status="delivered" (successfully sent to webhook)
- `failed`: Events with status="failed" (exceeded max retry attempts)
- `success_rate`: (delivered / (delivered + failed)) * 100

**Business Insights**:
- Monitor `success_rate` for service health (target: >95%)
- High `pending` count indicates delivery backlog
- Rising `failed` count suggests webhook or network issues

### Latency Metrics

**Endpoint**: `GET /metrics/latency`

```json
{
  "p50": 1.23,
  "p95": 3.45,
  "p99": 5.67,
  "sample_size": 1150
}
```

**Fields** (all values in seconds):
- `p50`: Median delivery time (50th percentile)
- `p95`: 95th percentile delivery time
- `p99`: 99th percentile delivery time
- `sample_size`: Number of delivered events in the measurement

**How Percentiles Work**:
- **P50 (Median)**: Half of all events deliver faster, half slower
- **P95**: Only 5% of events are slower than this value
- **P99**: Only 1% of events are slower than this value

**Calculation**:
Percentiles are calculated from the `delivery_latency_ms` field, which is set when an event transitions to "delivered" status. The latency measures the time from event creation (`created_at`) to successful delivery.

**Example Interpretation**:
```
P50: 1.2s → Typical event delivers in 1.2 seconds
P95: 3.4s → 95% of events deliver within 3.4 seconds
P99: 8.5s → 1% of events take longer than 8.5 seconds
```

**When to Investigate**:
- P50 > 2s: Check webhook endpoint performance
- P95 > 10s: Network latency or webhook timeout issues
- Large gap between P95 and P99: Outliers affecting performance

### Throughput Metrics

**Endpoint**: `GET /metrics/throughput`

```json
{
  "events_per_minute": 12.5,
  "events_per_hour": 750,
  "events_per_day": 18000,
  "measurement_period": "last_24_hours"
}
```

**Fields**:
- `events_per_minute`: Average event ingestion rate (per minute)
- `events_per_hour`: Average event ingestion rate (per hour)
- `events_per_day`: Total events in the last 24 hours
- `measurement_period`: Time window for calculations

**Calculation**:
Throughput is calculated by counting events created within the last 24 hours and dividing by the time period.

**Business Insights**:
- Identify peak usage hours
- Capacity planning for scaling
- Detect anomalies (sudden spikes or drops)

**Example Scenarios**:
- **Normal**: 10-15 events/min during business hours
- **Peak**: 50+ events/min during marketing campaigns
- **Alert**: < 1 event/min unexpectedly (possible integration issue)

### Error Metrics

**Endpoint**: `GET /metrics/errors`

```json
{
  "total_failed": 26,
  "error_rate": 2.09,
  "top_errors": [
    {
      "error_message": "Connection timeout",
      "count": 15
    },
    {
      "error_message": "404 Not Found",
      "count": 8
    }
  ]
}
```

**Fields**:
- `total_failed`: Total count of failed events
- `error_rate`: (failed / (delivered + failed)) * 100
- `top_errors`: Most common error messages with counts

**Root Cause Analysis**:
- **Connection timeout**: Webhook endpoint slow or unreachable
- **404 Not Found**: Webhook URL changed or incorrect
- **401 Unauthorized**: Webhook signature validation failing
- **500 Internal Server Error**: Webhook endpoint bug

## Setup Instructions

### Prerequisites

- Node.js 18+ and pnpm
- AWS CLI configured with appropriate credentials
- Access to the deployed Lambda Function URL
- API key from AWS Secrets Manager

### Local Development

1. **Clone Repository**:
   ```bash
   git clone https://github.com/your-org/apier.git
   cd apier/frontend
   ```

2. **Install Dependencies**:
   ```bash
   pnpm install
   ```

3. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API URL and key
   ```

4. **Run Development Server**:
   ```bash
   pnpm dev
   ```

   Dashboard will be available at `http://localhost:5173`

### Production Deployment

The dashboard is automatically deployed via AWS Amplify when you push to Git branches:

1. **Development Environment** (`dev` branch):
   ```bash
   git checkout dev
   git add .
   git commit -m "feat: dashboard updates"
   git push origin dev
   ```

2. **Production Environment** (`main` branch):
   ```bash
   git checkout main
   git merge dev
   git push origin main
   ```

Amplify will automatically:
- Build the frontend (`pnpm build`)
- Deploy to CloudFront CDN
- Update the environment-specific URL

### Environment Variables

**Frontend** (`.env`):
```bash
# API Configuration
VITE_API_URL=https://your-lambda-url.lambda-url.us-east-2.on.aws
VITE_API_KEY=your_api_key_here
```

**Backend** (automatically set by CDK):
- `DYNAMODB_TABLE_NAME`: DynamoDB table name
- `SECRET_ARN`: Secrets Manager ARN
- `AWS_REGION`: AWS region

## Troubleshooting

### Common Issues

#### Dashboard Shows "Authentication Error"

**Symptoms**: Red error banner on dashboard load

**Causes**:
1. Missing or incorrect `VITE_API_KEY` in `.env`
2. API key expired or rotated in Secrets Manager
3. JWT token generation failing

**Solutions**:
```bash
# 1. Verify API key in Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id zapier-api-credentials-{stackName} \
  --query SecretString --output text | jq

# 2. Update .env with correct API key
echo "VITE_API_KEY=your_correct_key" >> frontend/.env

# 3. Clear browser cache and reload
```

#### Metrics Not Loading

**Symptoms**: Spinner never completes, or "Failed to load metrics" error

**Causes**:
1. Lambda function cold start timeout
2. DynamoDB throttling
3. Network connectivity issues
4. CORS configuration problem

**Solutions**:
```bash
# 1. Check Lambda logs
aws logs tail /aws/lambda/{functionName} --follow

# 2. Verify API endpoint is reachable
curl -H "Authorization: Bearer $TOKEN" \
  https://your-api-url/metrics/summary

# 3. Check CloudWatch metrics for errors
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value={functionName} \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

#### Slow Dashboard Performance

**Symptoms**: Dashboard takes >5 seconds to load or refresh

**Causes**:
1. Large dataset (millions of events)
2. Lambda cold start
3. DynamoDB scan (missing GSI usage)

**Solutions**:
1. **Reduce Query Scope**: Metrics endpoints use efficient GSI queries, but verify in CloudWatch logs
2. **Warm Lambda**: Configure reserved concurrency or use CloudWatch Events to ping every 5 minutes
3. **Optimize Frontend**: Use React.memo and useCallback to prevent unnecessary re-renders

#### Stale Data

**Symptoms**: Dashboard shows outdated information

**Causes**:
1. Auto-refresh paused
2. Clock skew between client and server
3. DynamoDB eventually consistent reads

**Solutions**:
1. Click "Resume" if auto-refresh is paused
2. Click "Refresh" to force immediate update
3. Verify `lastUpdated` timestamp in UI

### Health Checks

#### Verify Dashboard Health

```bash
# 1. Check if frontend is deployed
curl -I https://your-amplify-url.amplifyapp.com

# 2. Verify API authentication
TOKEN=$(curl -s -X POST "https://your-api-url/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=api&password=YOUR_API_KEY" | jq -r '.access_token')

echo "Token: $TOKEN"

# 3. Test metrics endpoints
curl -H "Authorization: Bearer $TOKEN" https://your-api-url/metrics/summary | jq
curl -H "Authorization: Bearer $TOKEN" https://your-api-url/metrics/latency | jq
curl -H "Authorization: Bearer $TOKEN" https://your-api-url/metrics/throughput | jq
```

#### Monitor System Health

```bash
# Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value={functionName} \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# DynamoDB metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=zapier-triggers-events-{stackName} \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

## API Reference

### Authentication

All metrics endpoints require JWT authentication:

```bash
# 1. Obtain token
curl -X POST "https://your-api-url/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=api&password=YOUR_API_KEY"

# Response:
# {
#   "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
#   "token_type": "bearer"
# }

# 2. Use token in Authorization header
curl -H "Authorization: Bearer $TOKEN" https://your-api-url/metrics/summary
```

### Metrics Endpoints

#### GET /metrics/summary

Returns event summary statistics.

**Request**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://your-api-url/metrics/summary
```

**Response**:
```json
{
  "total": 1247,
  "pending": 23,
  "delivered": 1198,
  "failed": 26,
  "success_rate": 97.91
}
```

**Status Codes**:
- `200 OK`: Success
- `401 Unauthorized`: Missing or invalid token
- `500 Internal Server Error`: Database error

#### GET /metrics/latency

Returns latency percentiles for delivered events.

**Request**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://your-api-url/metrics/latency
```

**Response**:
```json
{
  "p50": 1.23,
  "p95": 3.45,
  "p99": 5.67,
  "sample_size": 1150
}
```

**Notes**:
- Only includes events with status="delivered"
- Values in seconds
- Returns `null` percentiles if sample_size < 1

#### GET /metrics/throughput

Returns event throughput metrics for the last 24 hours.

**Request**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://your-api-url/metrics/throughput
```

**Response**:
```json
{
  "events_per_minute": 12.5,
  "events_per_hour": 750,
  "events_per_day": 18000,
  "measurement_period": "last_24_hours"
}
```

**Notes**:
- Counts all events created in the last 24 hours
- Rates are averages across the time period

#### GET /metrics/errors

Returns error metrics and top error messages.

**Request**:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://your-api-url/metrics/errors
```

**Response**:
```json
{
  "total_failed": 26,
  "error_rate": 2.09,
  "top_errors": [
    {
      "error_message": "Connection timeout",
      "count": 15
    }
  ]
}
```

**Notes**:
- `error_rate` = (failed / (delivered + failed)) * 100
- `top_errors` limited to 10 most common errors

## Additional Resources

- **[Main README](../README.md)**: Project overview and getting started
- **[Deployment Guide](./DEPLOYMENT.md)**: CI/CD and multi-environment setup
- **[Monitoring Guide](./MONITORING.md)**: CloudWatch metrics and alerting
- **[Security Documentation](./SECURITY.md)**: Authentication and security best practices
- **[Developer Guide](./DEVELOPER_GUIDE.md)**: API integration examples

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review CloudWatch logs for errors
3. Consult the [Developer Guide](./DEVELOPER_GUIDE.md)
4. Open an issue on GitHub

---

**Last Updated**: 2025-11-13
**Version**: 1.0.0
