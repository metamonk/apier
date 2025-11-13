# Monitoring and Logging Guide

This document covers monitoring, logging, and alerting for the Zapier Triggers API.

## Overview

The API uses comprehensive AWS monitoring services:

- **AWS CloudWatch**: Log aggregation, performance metrics, and custom dashboards
- **AWS X-Ray**: Distributed tracing for request analysis and debugging
- **Amazon SNS**: Real-time alerting and incident notifications
- **CloudWatch Alarms**: Automated threshold monitoring with SNS integration

### Key Monitoring Features

- Real-time performance dashboards with Lambda and DynamoDB metrics
- Distributed tracing with X-Ray for debugging and latency analysis
- Automated alerting for errors, performance degradation, and throttling
- Email notifications via SNS for critical incidents
- Custom metrics for API-specific monitoring

## AWS X-Ray Distributed Tracing

### Overview

AWS X-Ray provides end-to-end tracing of requests through your Lambda function, automatically tracking:
- Lambda invocation details
- AWS SDK calls (DynamoDB, Secrets Manager)
- HTTP requests and responses
- Service latency and errors

### Accessing X-Ray Traces

#### Via AWS Console

1. Go to **X-Ray** → **Traces**
2. Filter by time range and response codes
3. Click on individual traces to see detailed service map
4. View subsegments for each AWS service call

#### Via AWS CLI

```bash
# Get recent traces
aws xray get-trace-summaries \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --region us-east-2

# Get specific trace details
aws xray batch-get-traces \
  --trace-ids {trace-id} \
  --region us-east-2
```

### X-Ray Service Map

The service map visualizes your application architecture:

1. **Lambda Function**: Your FastAPI application
2. **DynamoDB**: Event storage operations
3. **Secrets Manager**: Credential retrieval
4. **AWS SDK**: All boto3 calls are automatically traced

**View Service Map:**
- X-Ray Console → Service map
- Shows latency, error rates, and traffic flow
- Identify performance bottlenecks

### Instrumentation

The Lambda function is instrumented with X-Ray SDK:

```python
# Already configured in main.py
from aws_xray_sdk.core import xray_recorder, patch_all

# Automatically instruments boto3 and other AWS SDK calls
patch_all()
```

**What gets traced:**
- All DynamoDB queries (Query, PutItem, UpdateItem)
- Secrets Manager GetSecretValue calls
- FastAPI endpoint execution
- Cold start vs warm start performance

### Analyzing Traces

#### Identify Slow Requests

```bash
# Find traces with duration > 1 second
aws xray get-trace-summaries \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --filter-expression 'duration > 1' \
  --region us-east-2
```

#### Find Error Traces

```bash
# Get traces with errors
aws xray get-trace-summaries \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --filter-expression 'error = true OR fault = true' \
  --region us-east-2
```

#### Analyze Cold Starts

```bash
# Filter for initialization subsegments
# Look for traces with "Initialization" in segments
# Cold starts typically show >1s duration for first invocation
```

### Custom Annotations (Optional)

Add custom annotations for more detailed tracing:

```python
from aws_xray_sdk.core import xray_recorder

@app.post("/events")
async def create_event(event: Event):
    # Add custom annotation
    xray_recorder.put_annotation('event_type', event.type)
    xray_recorder.put_annotation('event_source', event.source)

    # Add metadata
    xray_recorder.put_metadata('event_payload_size', len(str(event.payload)))

    # Your existing code...
```

## CloudWatch Dashboards

### Automated Dashboard

A comprehensive CloudWatch dashboard is automatically created during deployment:

**Dashboard Name**: `ZapierTriggersAPI-{stack-name}`

**Widgets included:**

1. **Lambda Invocations & Errors** (Graph)
   - Total invocations
   - Error count
   - 5-minute intervals

2. **Lambda Duration & Throttles** (Graph)
   - Average execution time
   - Throttle events

3. **DynamoDB Operations** (Graph)
   - Read capacity consumed
   - Write capacity consumed

4. **DynamoDB Latency & Errors** (Graph)
   - Request latency
   - User errors (4xx)
   - System errors (5xx)

5. **Current Status** (Single Value)
   - Total invocations (5m window)
   - Current errors

6. **Performance** (Single Value)
   - Average duration
   - P99 duration

### Accessing the Dashboard

The dashboard URL is output after deployment:

```bash
# Get dashboard URL from CloudFormation outputs
aws cloudformation describe-stacks \
  --stack-name {stack-name} \
  --query 'Stacks[0].Outputs[?OutputKey==`DashboardUrl`].OutputValue' \
  --output text \
  --region us-east-2
```

Or access via AWS Console:
1. Go to **CloudWatch** → **Dashboards**
2. Select `ZapierTriggersAPI-{stack-name}`

### Custom Dashboard Widgets

Add your own widgets via AWS Console or CLI:

```bash
# Export current dashboard
aws cloudwatch get-dashboard \
  --dashboard-name ZapierTriggersAPI-{stack-name} \
  --region us-east-2 > dashboard.json

# Modify dashboard.json with custom widgets

# Update dashboard
aws cloudwatch put-dashboard \
  --dashboard-name ZapierTriggersAPI-{stack-name} \
  --dashboard-body file://dashboard.json \
  --region us-east-2
```

## CloudWatch Alarms and SNS Notifications

### Automated Alarms

The following CloudWatch alarms are automatically configured:

#### 1. High Error Rate Alarm

**Trigger**: More than 10 errors in 10 minutes (2 evaluation periods of 5 minutes)

```bash
# View alarm status
aws cloudwatch describe-alarms \
  --alarm-names zapier-api-high-errors-{stack-name} \
  --region us-east-2
```

**What triggers it:**
- Lambda function exceptions
- HTTP 500 errors
- Unhandled exceptions

**Action**: Sends email notification via SNS

#### 2. High Duration Alarm

**Trigger**: Average execution time > 10 seconds for 10 minutes

```bash
# View alarm status
aws cloudwatch describe-alarms \
  --alarm-names zapier-api-high-duration-{stack-name} \
  --region us-east-2
```

**What triggers it:**
- Slow DynamoDB queries
- Secrets Manager timeout
- Cold starts
- Heavy payload processing

**Action**: Sends email notification via SNS

#### 3. Throttle Alarm

**Trigger**: Any throttling event

```bash
# View alarm status
aws cloudwatch describe-alarms \
  --alarm-names zapier-api-throttling-{stack-name} \
  --region us-east-2
```

**What triggers it:**
- Lambda concurrent execution limit reached
- Account-level throttling

**Action**: Sends email notification via SNS

#### 4. DynamoDB Throttle Alarm

**Trigger**: More than 5 DynamoDB user errors in 5 minutes

```bash
# View alarm status
aws cloudwatch describe-alarms \
  --alarm-names zapier-api-dynamo-read-throttle-{stack-name} \
  --region us-east-2
```

**What triggers it:**
- DynamoDB throttling (exceeds capacity)
- Query syntax errors

**Action**: Sends email notification via SNS

### SNS Topic Configuration

An SNS topic is automatically created for alerts:

**Topic Name**: `zapier-api-alerts-{stack-name}`

#### Subscribe to Alerts

**IMPORTANT**: Update the email subscription after deployment:

```bash
# Get SNS topic ARN
TOPIC_ARN=$(aws cloudformation describe-stacks \
  --stack-name {stack-name} \
  --query 'Stacks[0].Outputs[?OutputKey==`AlertsTopicArn`].OutputValue' \
  --output text \
  --region us-east-2)

# Subscribe your email
aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-2

# Confirm subscription by clicking link in email
```

#### Add Multiple Subscriptions

```bash
# Add SMS notification
aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol sms \
  --notification-endpoint +1234567890 \
  --region us-east-2

# Add webhook notification
aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol https \
  --notification-endpoint https://your-webhook.com/alerts \
  --region us-east-2
```

#### Test Alerts

```bash
# Manually trigger an alarm to test notifications
aws cloudwatch set-alarm-state \
  --alarm-name zapier-api-high-errors-{stack-name} \
  --state-value ALARM \
  --state-reason "Testing alert system" \
  --region us-east-2

# Reset alarm
aws cloudwatch set-alarm-state \
  --alarm-name zapier-api-high-errors-{stack-name} \
  --state-value OK \
  --state-reason "Test complete" \
  --region us-east-2
```

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

You can add custom metrics using CloudWatch SDK in your Lambda code:

```python
import boto3

cloudwatch = boto3.client('cloudwatch', region_name='us-east-2')

# Publish custom metric
cloudwatch.put_metric_data(
    Namespace='ZapierTriggersAPI',
    MetricData=[
        {
            'MetricName': 'EventsProcessed',
            'Value': 1,
            'Unit': 'Count',
            'Timestamp': datetime.utcnow()
        }
    ]
)
```

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

#### 5. X-Ray Trace IDs

```sql
fields @timestamp, @message
| filter @message like /X-Amzn-Trace-Id/
| parse @message /X-Amzn-Trace-Id: Root=(?<traceId>[^;]+)/
| display @timestamp, traceId
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
- Monitor cold start duration via X-Ray
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
- X-Ray: $5 per 1M traces recorded, $0.50 per 1M traces retrieved

## Troubleshooting

### Common Issues

#### High Error Rate

1. Check CloudWatch logs for error messages
2. Review X-Ray traces for failed requests
3. Check recent code changes
4. Verify DynamoDB table status
5. Verify Secrets Manager access
6. Check Lambda timeout settings

#### High Latency

1. Use X-Ray to identify slow subsegments
2. Check Lambda memory allocation
3. Review DynamoDB query patterns
4. Check for cold starts in X-Ray
5. Verify network issues
6. Profile slow code paths

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
- Check alarm status

### Weekly
- Review performance metrics and X-Ray traces
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
- [AWS X-Ray Documentation](https://docs.aws.amazon.com/xray/latest/devguide/)
- [X-Ray SDK for Python](https://docs.aws.amazon.com/xray/latest/devguide/xray-sdk-python.html)

---

**Last Updated:** 2025-11-13
**Maintained By:** Development Team
