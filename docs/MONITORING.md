# Monitoring and Logging Guide

This document covers monitoring, logging, and alerting for the Zapier Triggers API.

## Overview

The API uses **AWS CloudWatch** for:
- Log aggregation and analysis
- Performance metrics
- Error tracking
- Custom alarms

## CloudWatch Log Groups

### Lambda Function Logs

**Main API Function:**
```
Log Group: /aws/lambda/amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL
Retention: 7 days
Region: us-east-2
```

**Infrastructure Functions:**
```
/aws/lambda/amplify-dmmfqlsr845yz-mai-AmplifyBranchLinkerCusto-*
(Amplify deployment helpers)
```

### Accessing Logs

#### Via AWS Console

1. Go to **CloudWatch** → **Log groups**
2. Search for: `amplify-dmmfqlsr845yz-mai-TriggersApiFunction`
3. Click on the log group
4. View log streams (each Lambda execution creates a stream)

#### Via AWS CLI

```bash
# Tail live logs
aws logs tail /aws/lambda/amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL \
  --region us-east-2 \
  --follow

# View last hour of logs
aws logs tail /aws/lambda/amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL \
  --region us-east-2 \
  --since 1h

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL \
  --region us-east-2 \
  --filter-pattern "ERROR"
```

## Log Retention

**Current Settings:**
- **Development/Staging**: 7 days
- **Production**: Should be 30 days (update when deploying to main)

**Update Retention:**
```bash
# Set to 30 days for production
aws logs put-retention-policy \
  --log-group-name /aws/lambda/amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL \
  --retention-in-days 30 \
  --region us-east-2
```

**Available Retention Periods:**
1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653 days, or infinite (null)

## Lambda Metrics

### Built-in Metrics

AWS Lambda automatically publishes these metrics to CloudWatch:

**Performance Metrics:**
- **Invocations**: Number of times function is invoked
- **Duration**: Execution time in milliseconds
- **Errors**: Number of invocations that result in errors
- **Throttles**: Number of throttled invocations
- **ConcurrentExecutions**: Concurrent executions at a point in time
- **UnreservedConcurrentExecutions**: Concurrent executions for unreserved function

**View Metrics:**
```bash
# Get invocation count (last hour)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region us-east-2
```

### Custom Metrics

The API automatically publishes custom metrics to CloudWatch through a FastAPI middleware. All metrics are published to the `ZapierTriggersAPI` namespace.

#### Available Custom Metrics

**1. ApiLatency** (Milliseconds)
- **Description**: Request duration from receipt to response
- **Use Case**: Monitor ingestion latency for POST /events endpoint
- **Dimensions**: Endpoint, Method, StatusCode
- **Target**: P95 < 500ms, Alert if > 1000ms

**2. ApiRequests** (Count)
- **Description**: Total number of API requests
- **Dimensions**: Endpoint, Method, StatusCode
- **Use Case**: Track throughput and usage patterns

**3. ApiErrors** (Count)
- **Description**: Total error count (4xx + 5xx responses)
- **Dimensions**: Endpoint, Method, StatusCode
- **Use Case**: Monitor overall API health
- **Target**: < 1% error rate

**4. Api4xxErrors** (Count)
- **Description**: Client error count (400-499 status codes)
- **Dimensions**: Endpoint, Method, StatusCode
- **Use Case**: Track authentication failures, invalid requests
- **Common Causes**: Invalid JWT tokens, malformed requests

**5. Api5xxErrors** (Count)
- **Description**: Server error count (500-599 status codes)
- **Dimensions**: Endpoint, Method, StatusCode
- **Use Case**: Track infrastructure issues, bugs
- **Target**: Should be 0 - alert immediately

**6. ApiAvailability** (Count)
- **Description**: Success/failure indicator (1 for success, 0 for failure)
- **Dimensions**: Endpoint
- **Use Case**: Calculate uptime percentage
- **Target**: > 99.9% availability

#### Viewing Custom Metrics

**Via AWS Console:**
1. Go to CloudWatch → Metrics
2. Select "Custom namespaces" → "ZapierTriggersAPI"
3. Choose metric and dimensions to visualize

**Via AWS CLI:**
```bash
# Get API latency statistics (last hour)
aws cloudwatch get-metric-statistics \
  --namespace ZapierTriggersAPI \
  --metric-name ApiLatency \
  --dimensions Name=Endpoint,Value=/events Name=Method,Value=POST \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum,Minimum \
  --region us-east-2

# Get error rate (last hour)
aws cloudwatch get-metric-statistics \
  --namespace ZapierTriggersAPI \
  --metric-name ApiErrors \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region us-east-2

# Get API request count by endpoint
aws cloudwatch get-metric-statistics \
  --namespace ZapierTriggersAPI \
  --metric-name ApiRequests \
  --dimensions Name=Endpoint,Value=/events \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region us-east-2
```

#### Metric Implementation Details

Custom metrics are published via FastAPI middleware that:
- Measures request duration using `time.perf_counter()`
- Captures endpoint path, HTTP method, and status code
- Publishes metrics asynchronously to avoid impacting response time
- Uses "fire and forget" pattern - metric failures don't affect API responses
- Adds `X-Process-Time` header to all responses

**Source Code:** `amplify/functions/api/main.py` - See `cloudwatch_metrics_middleware()` and `publish_request_metrics()`

## DynamoDB Metrics

**Available Metrics:**
- **ConsumedReadCapacityUnits**: Read capacity consumed
- **ConsumedWriteCapacityUnits**: Write capacity consumed
- **UserErrors**: 4xx errors
- **SystemErrors**: 5xx errors
- **SuccessfulRequestLatency**: Request latency
- **ThrottledRequests**: Throttled requests

**View DynamoDB Metrics:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedWriteCapacityUnits \
  --dimensions Name=TableName,Value=zapier-triggers-events-amplify-dmmfqlsr845yz-main-branch-6ca37098e7-apistack7B433BC7-MMMAWD4LJ6AL \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region us-east-2
```

## CloudWatch Alarms

### Setting Up Alarms

CloudWatch alarms monitor metrics and trigger notifications when thresholds are breached. Configure alarms for both built-in Lambda metrics and custom API metrics.

#### Custom API Metrics Alarms

##### 1. High Ingestion Latency Alarm

Alert when POST /events response time exceeds 1 second:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-high-ingestion-latency \
  --alarm-description "Alert when ingestion latency exceeds 1 second" \
  --metric-name ApiLatency \
  --namespace ZapierTriggersAPI \
  --statistic Average \
  --period 300 \
  --threshold 1000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=Endpoint,Value=/events Name=Method,Value=POST \
  --treat-missing-data notBreaching \
  --region us-east-2
```

##### 2. High API Error Rate Alarm

Alert when API error rate exceeds 1%:

```bash
# First, create a metric math alarm that calculates error rate
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-high-error-rate \
  --alarm-description "Alert when API error rate exceeds 1%" \
  --evaluation-periods 2 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --treat-missing-data notBreaching \
  --metrics '[
    {
      "Id": "errors",
      "ReturnData": false,
      "MetricStat": {
        "Metric": {
          "Namespace": "ZapierTriggersAPI",
          "MetricName": "ApiErrors"
        },
        "Period": 300,
        "Stat": "Sum"
      }
    },
    {
      "Id": "requests",
      "ReturnData": false,
      "MetricStat": {
        "Metric": {
          "Namespace": "ZapierTriggersAPI",
          "MetricName": "ApiRequests"
        },
        "Period": 300,
        "Stat": "Sum"
      }
    },
    {
      "Id": "error_rate",
      "Expression": "(errors / requests) * 100",
      "Label": "Error Rate (%)",
      "ReturnData": true
    }
  ]' \
  --region us-east-2
```

##### 3. High 5xx Error Alarm

Alert immediately on any 5xx server errors:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-5xx-errors \
  --alarm-description "Alert on any 5xx server errors" \
  --metric-name Api5xxErrors \
  --namespace ZapierTriggersAPI \
  --statistic Sum \
  --period 60 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --treat-missing-data notBreaching \
  --region us-east-2
```

##### 4. API Availability Alarm

Alert when API availability drops below 99%:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-low-availability \
  --alarm-description "Alert when API availability drops below 99%" \
  --evaluation-periods 2 \
  --threshold 99 \
  --comparison-operator LessThanThreshold \
  --treat-missing-data notBreaching \
  --metrics '[
    {
      "Id": "success",
      "ReturnData": false,
      "MetricStat": {
        "Metric": {
          "Namespace": "ZapierTriggersAPI",
          "MetricName": "ApiAvailability"
        },
        "Period": 300,
        "Stat": "Sum"
      }
    },
    {
      "Id": "total",
      "ReturnData": false,
      "MetricStat": {
        "Metric": {
          "Namespace": "ZapierTriggersAPI",
          "MetricName": "ApiRequests"
        },
        "Period": 300,
        "Stat": "Sum"
      }
    },
    {
      "Id": "availability",
      "Expression": "(success / total) * 100",
      "Label": "Availability (%)",
      "ReturnData": true
    }
  ]' \
  --region us-east-2
```

#### Lambda Metrics Alarms

##### 5. High Lambda Error Rate Alarm

Alert when Lambda errors exceed threshold:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-lambda-high-error-rate \
  --alarm-description "Alert when Lambda error rate is high" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=FunctionName,Value=amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL \
  --treat-missing-data notBreaching \
  --region us-east-2
```

##### 6. High Lambda Duration Alarm

Alert when Lambda execution time is too long:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-lambda-high-duration \
  --alarm-description "Alert when Lambda execution time exceeds 10 seconds" \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --threshold 10000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=FunctionName,Value=amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL \
  --treat-missing-data notBreaching \
  --region us-east-2
```

##### 7. Lambda Throttling Alarm

Alert when Lambda is being throttled:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-lambda-throttling \
  --alarm-description "Alert when Lambda is being throttled" \
  --metric-name Throttles \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 60 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=FunctionName,Value=amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL \
  --treat-missing-data notBreaching \
  --region us-east-2
```

#### Quick Setup: Create All Alarms

Create a script to set up all alarms at once:

```bash
#!/bin/bash
# setup-alarms.sh - Create all CloudWatch alarms for Zapier Triggers API

REGION="us-east-2"
LAMBDA_FUNCTION="amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL"

echo "Creating CloudWatch alarms..."

# 1. High Ingestion Latency
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-high-ingestion-latency \
  --alarm-description "Alert when ingestion latency exceeds 1 second" \
  --metric-name ApiLatency \
  --namespace ZapierTriggersAPI \
  --statistic Average \
  --period 300 \
  --threshold 1000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=Endpoint,Value=/events Name=Method,Value=POST \
  --treat-missing-data notBreaching \
  --region $REGION

# 3. High 5xx Errors
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-5xx-errors \
  --alarm-description "Alert on any 5xx server errors" \
  --metric-name Api5xxErrors \
  --namespace ZapierTriggersAPI \
  --statistic Sum \
  --period 60 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --treat-missing-data notBreaching \
  --region $REGION

# 5. Lambda High Error Rate
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-lambda-high-error-rate \
  --alarm-description "Alert when Lambda error rate is high" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=FunctionName,Value=$LAMBDA_FUNCTION \
  --treat-missing-data notBreaching \
  --region $REGION

# 7. Lambda Throttling
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-lambda-throttling \
  --alarm-description "Alert when Lambda is being throttled" \
  --metric-name Throttles \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 60 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=FunctionName,Value=$LAMBDA_FUNCTION \
  --treat-missing-data notBreaching \
  --region $REGION

echo "✓ All alarms created successfully!"
echo "Note: Configure SNS notifications separately using the instructions below."
```

Save this as `scripts/setup-alarms.sh` and run:
```bash
chmod +x scripts/setup-alarms.sh
./scripts/setup-alarms.sh
```

### Alarm Actions

To receive notifications, configure SNS topics:

```bash
# Create SNS topic
aws sns create-topic --name zapier-api-alerts --region us-east-2

# Subscribe email to topic
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-2:971422717446:zapier-api-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-2

# Add alarm action
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-high-error-rate \
  --alarm-actions arn:aws:sns:us-east-2:971422717446:zapier-api-alerts \
  ...other parameters...
```

## Log Insights Queries

### Common Queries

#### 1. Error Analysis

```sql
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 20
```

#### 2. Slow Requests

```sql
fields @timestamp, @duration
| filter @type = "REPORT"
| sort @duration desc
| limit 20
```

#### 3. Request Count by Endpoint

```sql
fields @timestamp, @message
| filter @message like /INFO/
| stats count() by bin(5m)
```

#### 4. Memory Usage

```sql
fields @timestamp, @maxMemoryUsed / 1024 / 1024 as memoryUsedMB
| filter @type = "REPORT"
| sort @timestamp desc
| limit 20
```

### Run Query via CLI

```bash
# Start query
QUERY_ID=$(aws logs start-query \
  --log-group-name /aws/lambda/amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20' \
  --region us-east-2 \
  --query 'queryId' --output text)

# Get results
aws logs get-query-results --query-id $QUERY_ID --region us-east-2
```

## Monitoring Dashboard

### Create CloudWatch Dashboard

```bash
aws cloudwatch put-dashboard \
  --dashboard-name ZapierTriggersAPI \
  --region us-east-2 \
  --dashboard-body '{
    "widgets": [
      {
        "type": "metric",
        "properties": {
          "metrics": [
            ["AWS/Lambda", "Invocations", {"stat": "Sum"}],
            [".", "Errors", {"stat": "Sum"}],
            [".", "Duration", {"stat": "Average"}]
          ],
          "period": 300,
          "stat": "Average",
          "region": "us-east-2",
          "title": "Lambda Metrics",
          "dimensions": {
            "FunctionName": "amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL"
          }
        }
      }
    ]
  }'
```

View dashboard: https://console.aws.amazon.com/cloudwatch/home?region=us-east-2#dashboards:name=ZapierTriggersAPI

## Performance Monitoring

### Key Metrics to Monitor

1. **Latency (P50, P95, P99)**:
   - Target: < 500ms for P95
   - Alert if > 1000ms

2. **Error Rate**:
   - Target: < 0.1%
   - Alert if > 1%

3. **Throughput**:
   - Monitor requests per second
   - Plan capacity based on trends

4. **DynamoDB Throttling**:
   - Should be 0
   - Alert immediately if throttled

5. **Lambda Concurrent Executions**:
   - Monitor against account limits
   - Default limit: 1000 concurrent executions

### Performance Best Practices

- Keep Lambda warm with provisioned concurrency if needed
- Monitor cold start duration
- Optimize DynamoDB queries (use GSI effectively)
- Cache Secrets Manager calls (already implemented)
- Monitor Lambda memory usage and right-size

## Cost Monitoring

### Track Costs

```bash
# Get Lambda invocations (for cost estimation)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL \
  --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum \
  --region us-east-2
```

**Cost Factors:**
- Lambda invocations: $0.20 per 1M requests
- Lambda duration: $0.0000166667 per GB-second
- DynamoDB: Pay per request (on-demand)
- CloudWatch Logs: $0.50 per GB ingested
- Secrets Manager: $0.40 per secret per month

## Troubleshooting

### Common Issues

#### High Error Rate

1. Check CloudWatch logs for error messages
2. Review recent code changes
3. Check DynamoDB table status
4. Verify Secrets Manager access
5. Check Lambda timeout settings

#### High Latency

1. Check Lambda memory allocation
2. Review DynamoDB query patterns
3. Check for cold starts
4. Verify network issues
5. Profile slow code paths

#### Throttling

1. Check Lambda concurrent execution limits
2. Review DynamoDB capacity settings
3. Implement exponential backoff
4. Consider provisioned concurrency

## Security Monitoring

### Audit Logs

Enable CloudTrail for API activity:

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL \
  --region us-east-2
```

### Monitoring Access

- Monitor Secrets Manager access via CloudTrail
- Track Lambda invocation patterns
- Alert on unusual API call patterns
- Monitor IAM role changes

## Maintenance Tasks

### Daily
- Check for errors in CloudWatch logs
- Review Lambda invocation counts

### Weekly
- Review performance metrics
- Check alarm status
- Analyze slow queries

### Monthly
- Review and optimize costs
- Update retention policies if needed
- Review and update alarms
- Analyze trends and capacity planning

## References

- [CloudWatch Logs Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/)
- [Lambda Monitoring](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-functions.html)
- [DynamoDB Monitoring](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/monitoring-cloudwatch.html)
- [CloudWatch Alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html)

---

**Last Updated:** 2025-11-13
**Maintained By:** Development Team
