# Load Testing Documentation

## Overview

This document provides comprehensive information about load testing the Zapier Triggers API. Load tests are implemented using [k6](https://k6.io/), a modern, developer-friendly load testing tool with excellent scripting capabilities and detailed metrics.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Test Scenarios](#test-scenarios)
- [Running Tests](#running-tests)
- [Understanding Results](#understanding-results)
- [Performance Metrics](#performance-metrics)
- [Optimization Recommendations](#optimization-recommendations)

## Prerequisites

### Install k6

**macOS:**
```bash
brew install k6
```

**Linux:**
```bash
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

**Windows:**
```bash
winget install k6
```

Or download from [k6 releases](https://github.com/grafana/k6/releases).

### Environment Setup

Set your API key before running tests:

```bash
export API_KEY="your-zapier-api-key-here"
```

For custom API endpoint (optional):

```bash
export BASE_URL="https://your-custom-endpoint.amazonaws.com"
```

## Quick Start

Run all load tests sequentially:

```bash
npm run load-test:all
```

Or run individual tests:

```bash
npm run load-test:baseline   # 10 concurrent users
npm run load-test:moderate   # 50 concurrent users
npm run load-test:high       # 100-150 concurrent users
npm run load-test:spike      # Sudden traffic surge
```

## Test Scenarios

### 1. Baseline Test (`baseline.js`)

**Purpose:** Establish baseline performance metrics under normal load.

**Configuration:**
- Virtual Users: 10
- Duration: 2 minutes
- Think Time: 1 second between requests
- Endpoints Tested: All (auth, events, inbox, ack)

**Success Criteria:**
- Error rate < 1%
- p95 response time < 1000ms
- p99 response time < 2000ms
- Auth failures < 5

**Command:**
```bash
k6 run --env API_KEY=$API_KEY tests/load/baseline.js
```

### 2. Moderate Load Test (`moderate.js`)

**Purpose:** Evaluate performance under typical production load.

**Configuration:**
- Virtual Users: Ramps from 10 to 50
- Duration: 5 minutes
- Stages:
  - 30s warm-up to 10 users
  - 1m ramp to 50 users
  - 3m sustain 50 users
  - 30s ramp down

**Success Criteria:**
- Error rate < 2%
- p95 response time < 1500ms
- p99 response time < 3000ms
- DynamoDB throttles < 5

**Command:**
```bash
k6 run --env API_KEY=$API_KEY tests/load/moderate.js
```

### 3. High Load Test (`high-load.js`)

**Purpose:** Push system to capacity limits and identify bottlenecks.

**Configuration:**
- Virtual Users: Ramps from 20 to 150
- Duration: 12 minutes
- Stages:
  - 1m warm-up to 20 users
  - 2m ramp to 50 users
  - 2m ramp to 100 users
  - 3m sustain 100 users
  - 1m push to 150 users
  - 2m hold peak
  - 1m ramp down

**Success Criteria:**
- Error rate < 5%
- p95 response time < 3000ms
- p99 response time < 5000ms
- DynamoDB throttles < 100

**Command:**
```bash
k6 run --env API_KEY=$API_KEY tests/load/high-load.js
```

### 4. Spike Test (`spike.js`)

**Purpose:** Test system resilience during sudden traffic surges.

**Configuration:**
- Virtual Users: 10 → 200 (20x spike) → 10
- Duration: 3.5 minutes
- Stages:
  - 30s normal load (10 users)
  - 10s SPIKE to 200 users
  - 1m hold spike
  - 30s back to normal
  - 1m recovery observation

**Success Criteria:**
- Error rate < 10%
- System recovers after spike
- No cascading failures

**Command:**
```bash
k6 run --env API_KEY=$API_KEY tests/load/spike.js
```

## Running Tests

### Single Test

```bash
# Basic run
k6 run --env API_KEY=$API_KEY tests/load/baseline.js

# With custom endpoint
k6 run --env API_KEY=$API_KEY --env BASE_URL=https://your-api.com tests/load/baseline.js

# Save results to file
k6 run --env API_KEY=$API_KEY tests/load/baseline.js --out json=results/baseline-results.json
```

### All Tests (Sequential)

```bash
npm run load-test:all
```

This runs all four tests in sequence and generates comprehensive reports.

### Results Directory

Test results are saved to `results/` directory:

```
results/
├── baseline-summary.json
├── moderate-summary.json
├── high-load-summary.json
└── spike-summary.json
```

## Understanding Results

### k6 Output

k6 provides detailed metrics during and after test execution:

```
running (2m00.0s), 00/10 VUs, 1200 complete and 0 interrupted iterations

    ✓ auth: status is 200
    ✓ auth: has access token
    ✓ create event: status is 201
    ✓ create event: has event id
    ✓ inbox: status is 200
    ✓ ack: status is 200

    checks........................: 100.00% ✓ 7200     ✗ 0
    data_received.................: 2.4 MB  20 kB/s
    data_sent.....................: 1.2 MB  10 kB/s
    http_req_blocked..............: avg=1.2ms    min=2µs     med=14µs    max=250ms   p(90)=25µs    p(95)=46µs
    http_req_connecting...........: avg=450µs    min=0s      med=0s      max=112ms   p(90)=0s      p(95)=0s
  ✓ http_req_duration.............: avg=245ms    min=120ms   med=230ms   max=1200ms  p(90)=350ms   p(95)=450ms
      { expected_response:true }...: avg=245ms    min=120ms   med=230ms   max=1200ms  p(90)=350ms   p(95)=450ms
  ✓ http_req_failed...............: 0.00%   ✓ 0        ✗ 3600
    http_req_receiving............: avg=150µs    min=17µs    med=120µs   max=4ms     p(90)=264µs   p(95)=341µs
    http_req_sending..............: avg=80µs     min=11µs    med=63µs    max=5ms     p(90)=98µs    p(95)=133µs
    http_req_tls_handshaking......: avg=0s       min=0s      med=0s      max=0s      p(90)=0s      p(95)=0s
    http_req_waiting..............: avg=244ms    min=119ms   med=229ms   max=1199ms  p(90)=349ms   p(95)=449ms
    http_reqs.....................: 3600    30/s
    iteration_duration............: avg=2.5s     min=2.2s    med=2.4s    max=4.5s    p(90)=2.8s    p(95)=3.1s
    iterations....................: 1200    10/s
    vus...........................: 10      min=10     max=10
    vus_max.......................: 10      min=10     max=10
```

### Key Metrics

| Metric | Description | Good | Warning | Critical |
|--------|-------------|------|---------|----------|
| `http_req_failed` | Error rate | < 1% | 1-5% | > 5% |
| `http_req_duration` (p50) | Median response time | < 500ms | 500-1000ms | > 1000ms |
| `http_req_duration` (p95) | 95th percentile | < 1000ms | 1000-2000ms | > 2000ms |
| `http_req_duration` (p99) | 99th percentile | < 2000ms | 2000-5000ms | > 5000ms |
| `cold_start_rate` | Lambda cold starts | < 5% | 5-15% | > 15% |
| `dynamodb_throttles` | DynamoDB throttling | 0 | 1-10 | > 10 |
| `lambda_concurrency_errors` | Concurrency limit errors | 0 | 1-5 | > 5 |

### Custom Metrics

Our tests track additional custom metrics:

- **`event_creation_duration`**: Time to create events (POST /events)
- **`inbox_retrieval_duration`**: Time to fetch inbox (GET /inbox)
- **`ack_duration`**: Time to acknowledge events (POST /inbox/{id}/ack)
- **`auth_failures`**: Number of authentication failures
- **`cold_start_rate`**: Percentage of requests hitting cold Lambda containers
- **`dynamodb_throttles`**: DynamoDB throttling events
- **`timeout_errors`**: Request timeout count
- **`lambda_concurrency_errors`**: Lambda concurrency limit hits

## Performance Metrics

### Current Infrastructure

**AWS Lambda:**
- Memory: 512 MB (configurable)
- Timeout: 30 seconds
- Reserved Concurrency: Not set (uses account limits)
- Provisioned Concurrency: Not configured

**DynamoDB:**
- Table: `zapier-triggers-events`
- Billing Mode: On-demand (auto-scaling)
- GSI: `status-index` for querying pending events

**Expected Performance:**

| Test Type | RPS (avg) | p50 Latency | p95 Latency | Error Rate |
|-----------|-----------|-------------|-------------|------------|
| Baseline (10 VUs) | 10-15 | 200-300ms | 400-600ms | < 1% |
| Moderate (50 VUs) | 50-70 | 300-500ms | 700-1200ms | < 2% |
| High Load (100-150 VUs) | 80-120 | 500-800ms | 1500-2500ms | 2-5% |
| Spike (200 VUs) | 100-150 | 800-1500ms | 2000-4000ms | 5-10% |

### Bottleneck Analysis

Common performance bottlenecks observed during load testing:

#### 1. Lambda Cold Starts

**Symptoms:**
- First request to new Lambda container takes 1-3 seconds
- Cold start rate increases with rapid scaling
- p99 latency spikes

**Impact:**
- Affects ~5-15% of requests during scaling events
- More pronounced during spike tests

**Mitigation:**
- Enable Provisioned Concurrency for predictable traffic
- Reduce Lambda package size
- Use Lambda SnapStart (for Java/Python)
- Keep Lambda warm with scheduled pings

#### 2. DynamoDB Throttling

**Symptoms:**
- 503 errors with "Throttling" message
- Increased latency on write operations
- Failed event creation requests

**Impact:**
- Occurs when write capacity exceeded
- On-demand mode has burst capacity limits

**Mitigation:**
- Switch to provisioned capacity for predictable workloads
- Enable DynamoDB auto-scaling
- Implement exponential backoff retry logic
- Use DynamoDB Accelerator (DAX) for reads

#### 3. Lambda Concurrency Limits

**Symptoms:**
- 429 or 503 errors
- "Rate exceeded" or "Service unavailable" messages
- Requests queued or rejected

**Impact:**
- Default account limit: 1000 concurrent executions
- Unreserved concurrency shared across account

**Mitigation:**
- Request AWS quota increase
- Set reserved concurrency for critical functions
- Implement request queueing (SQS)
- Use throttling at API Gateway level

#### 4. JWT Token Operations

**Symptoms:**
- Slow /token endpoint responses
- High CPU usage during token verification
- Auth failures under load

**Impact:**
- Token generation/verification is CPU-intensive
- Secrets Manager calls add latency

**Mitigation:**
- Cache tokens aggressively (24h expiry)
- Cache Secrets Manager values in Lambda
- Use lighter JWT algorithms (HS256 vs RS256)
- Implement token refresh before expiry

## Optimization Recommendations

### Priority 1: Critical (Do Now)

#### 1. Enable Lambda Reserved Concurrency

```bash
aws lambda put-function-concurrency \
  --function-name zapier-triggers-api \
  --reserved-concurrent-executions 500
```

**Expected Impact:**
- Prevents other functions from consuming all concurrency
- Guarantees capacity for API
- Reduces 429 errors

#### 2. Increase Lambda Memory

```bash
aws lambda update-function-configuration \
  --function-name zapier-triggers-api \
  --memory-size 1024
```

**Expected Impact:**
- More CPU power (proportional to memory)
- Faster JWT operations
- Lower response times (20-30% improvement)

**Trade-off:** Higher cost (~2x), but better performance/$ ratio

#### 3. DynamoDB Capacity Planning

For predictable workloads, switch to provisioned capacity:

```bash
aws dynamodb update-table \
  --table-name zapier-triggers-events \
  --billing-mode PROVISIONED \
  --provisioned-throughput ReadCapacityUnits=100,WriteCapacityUnits=100
```

Enable auto-scaling:

```bash
aws application-autoscaling register-scalable-target \
  --service-namespace dynamodb \
  --resource-id table/zapier-triggers-events \
  --scalable-dimension dynamodb:table:WriteCapacityUnits \
  --min-capacity 10 \
  --max-capacity 500
```

**Expected Impact:**
- Eliminates throttling
- Predictable performance
- Lower costs for sustained traffic

### Priority 2: High Impact

#### 4. Enable Provisioned Concurrency

For production with consistent traffic:

```bash
aws lambda put-provisioned-concurrency-config \
  --function-name zapier-triggers-api \
  --provisioned-concurrent-executions 10 \
  --qualifier $LATEST
```

**Expected Impact:**
- Eliminates cold starts for first 10 concurrent users
- Improves p95/p99 latencies
- Consistent sub-500ms responses

**Cost:** $0.000004167 per GB-second + invocation costs

#### 5. Implement Request Caching

Add API Gateway caching for GET /inbox:

```bash
aws apigatewayv2 update-stage \
  --api-id your-api-id \
  --stage-name $default \
  --route-settings '*/GET/inbox={CachingEnabled=true,CacheTtlInSeconds=30}'
```

**Expected Impact:**
- Reduces DynamoDB reads by 80%
- Faster inbox retrieval
- Lower costs

#### 6. Add CloudFront Distribution

Place CloudFront in front of Lambda Function URL:

**Expected Impact:**
- Geographic distribution
- DDoS protection
- Lower latency for global users
- SSL termination at edge

### Priority 3: Nice to Have

#### 7. Optimize Lambda Package Size

- Remove unused dependencies
- Use Lambda layers for common libraries
- Minify code

**Expected Impact:**
- Faster cold starts (10-30% improvement)
- Reduced initialization time

#### 8. Implement Connection Pooling

Reuse DynamoDB client connections:

```python
# Initialize outside handler
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(table_name)

def handler(event, context):
    # Reuse connection
    table.put_item(...)
```

**Expected Impact:**
- Reduced connection overhead
- Lower latency (5-10% improvement)

#### 9. Add Request Queuing (SQS)

For event ingestion, decouple with SQS:

```
POST /events → SQS → Lambda → DynamoDB
```

**Expected Impact:**
- Better handling of traffic bursts
- Graceful degradation
- No lost events

#### 10. Use DynamoDB Streams

For event processing and delivery:

```
DynamoDB → Streams → Lambda → Zapier Webhook
```

**Expected Impact:**
- Real-time event delivery
- No polling needed
- Lower latency for Zapier

## Infrastructure Recommendations

### For < 100 RPS

**Current Setup (Adequate):**
- Lambda: 512 MB, on-demand
- DynamoDB: On-demand mode
- No provisioned concurrency

**Recommended:**
- Increase Lambda memory to 1024 MB
- Set reserved concurrency to 100

**Monthly Cost:** ~$50-100

### For 100-500 RPS

**Recommended:**
- Lambda: 1024 MB, 10 provisioned concurrency
- DynamoDB: Provisioned mode with auto-scaling
  - Base: 50 RCU / 50 WCU
  - Max: 200 RCU / 200 WCU
- CloudWatch alarms for throttling

**Monthly Cost:** ~$200-400

### For > 500 RPS

**Recommended:**
- Lambda: 1536 MB, 50 provisioned concurrency
- DynamoDB: Provisioned mode with auto-scaling
  - Base: 100 RCU / 100 WCU
  - Max: 1000 RCU / 1000 WCU
- API Gateway caching (30s TTL)
- CloudFront distribution
- SQS queue for event ingestion

**Monthly Cost:** ~$800-1500

## Troubleshooting

### High Error Rates

**Check:**
1. CloudWatch Logs for specific errors
2. DynamoDB metrics for throttling
3. Lambda concurrency metrics
4. X-Ray traces for slow operations

**Common Causes:**
- DynamoDB throttling → Increase capacity
- Lambda concurrency limits → Increase quota
- Cold starts → Enable provisioned concurrency
- API key issues → Verify credentials

### Slow Response Times

**Check:**
1. Lambda duration metrics
2. DynamoDB query performance
3. Cold start frequency
4. Network latency

**Common Causes:**
- Cold starts → Use provisioned concurrency
- Large payloads → Optimize payload size
- Secrets Manager calls → Cache secrets
- JWT verification → Cache tokens

### Timeouts

**Check:**
1. Lambda timeout settings (current: 30s)
2. HTTP client timeouts in tests
3. DynamoDB query complexity
4. Network issues

**Common Causes:**
- Lambda timeout too short → Increase to 60s
- DynamoDB scan operations → Use queries instead
- Network congestion → Add retries

## Continuous Monitoring

### CloudWatch Alarms

Set up alarms for:

1. **High Error Rate**
   - Metric: `Errors` / `Invocations` > 5%
   - Action: SNS notification

2. **High Latency**
   - Metric: p99 Duration > 3000ms
   - Action: SNS notification

3. **DynamoDB Throttling**
   - Metric: `UserErrors` > 10
   - Action: Auto-scale or alert

4. **Lambda Concurrency**
   - Metric: `ConcurrentExecutions` > 80% of reserved
   - Action: Alert for capacity planning

### Regular Load Testing

**Schedule:**
- Weekly: Baseline test (automated)
- Monthly: Full suite (all tests)
- Before releases: Regression testing
- Quarterly: Capacity planning tests

**Integration:**
```bash
# Add to CI/CD pipeline
- name: Load Testing
  run: npm run load-test:baseline
  env:
    API_KEY: ${{ secrets.API_KEY }}
```

## Additional Resources

- [k6 Documentation](https://k6.io/docs/)
- [AWS Lambda Performance](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [API Performance Testing Guide](https://k6.io/docs/testing-guides/api-load-testing/)

## Support

For issues or questions about load testing:

1. Check [CloudWatch Metrics Dashboard](docs/MONITORING.md)
2. Review [Deployment Documentation](docs/DEPLOYMENT.md)
3. Contact DevOps team
4. Open GitHub issue

---

**Last Updated:** 2024-11-13
**Version:** 1.0.0
**Maintainer:** DevOps Team
