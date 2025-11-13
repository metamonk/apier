# SNS Alerts Configuration Guide

This guide explains how to configure CloudWatch alarm notifications via Amazon SNS (Simple Notification Service).

## Overview

The Zapier Triggers API automatically creates:
- **SNS Topic**: `zapier-api-alerts-{stackName}`
- **4 CloudWatch Alarms**: Error rate, duration, throttling, DynamoDB errors
- **CloudWatch Dashboard**: Real-time metrics visualization

All alarms are automatically connected to the SNS topic. You just need to subscribe to receive notifications.

## Quick Start

### 1. Get the SNS Topic ARN

After deployment, the SNS Topic ARN is available in CloudFormation outputs:

```bash
# Get the SNS Topic ARN
aws cloudformation describe-stacks \
  --stack-name amplify-apier-{your-branch}-{stack-id} \
  --region us-east-2 \
  --query "Stacks[0].Outputs[?OutputKey=='AlertsTopicArn'].OutputValue" \
  --output text
```

Or check the Amplify Console:
- AWS Amplify Console → Your App → Backend Resources → CloudFormation Stack → Outputs → `AlertsTopicArn`

### 2. Subscribe to Email Notifications

```bash
# Subscribe to email notifications
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-2:ACCOUNT_ID:zapier-api-alerts-{stackName} \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-2
```

**Important**: You must confirm the subscription by clicking the link in the confirmation email sent by AWS.

### 3. Verify Subscription

```bash
# List all subscriptions for the topic
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:us-east-2:ACCOUNT_ID:zapier-api-alerts-{stackName} \
  --region us-east-2
```

## Notification Channels

### Email Notifications

**Pros**: Free, detailed alarm information, good for non-urgent alerts
**Cons**: Delay (minutes), email filtering issues

```bash
aws sns subscribe \
  --topic-arn <TOPIC_ARN> \
  --protocol email \
  --notification-endpoint your-email@example.com
```

### SMS Notifications

**Pros**: Fast, reliable for critical alerts
**Cons**: Costs $0.50-$1.00 per month + $0.00645 per SMS (US)

```bash
aws sns subscribe \
  --topic-arn <TOPIC_ARN> \
  --protocol sms \
  --notification-endpoint +1234567890
```

### HTTPS Webhook

**Pros**: Integrate with Slack, PagerDuty, custom systems
**Cons**: Requires public HTTPS endpoint

```bash
aws sns subscribe \
  --topic-arn <TOPIC_ARN> \
  --protocol https \
  --notification-endpoint https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Lambda Function

**Pros**: Custom logic, filtering, enrichment
**Cons**: Requires Lambda development

```bash
aws sns subscribe \
  --topic-arn <TOPIC_ARN> \
  --protocol lambda \
  --notification-endpoint arn:aws:lambda:us-east-2:ACCOUNT_ID:function:alert-handler
```

## Configured CloudWatch Alarms

### 1. High Error Rate Alarm

**Alarm Name**: `zapier-api-high-errors-{stackName}`
**Threshold**: More than 10 errors in 10 minutes (2 consecutive periods of 5 minutes)
**Metric**: Lambda Errors (Sum)

**Triggered by**:
- Unhandled exceptions in Lambda function
- DynamoDB throttling errors
- Secrets Manager access failures
- Invalid JWT tokens (excessive authentication failures)

**Actions**:
1. Check CloudWatch Logs for Lambda function
2. Review recent code deployments
3. Check DynamoDB throttling metrics
4. Verify Secrets Manager configuration

### 2. High Duration Alarm

**Alarm Name**: `zapier-api-high-duration-{stackName}`
**Threshold**: Average duration > 10 seconds for 10 minutes (2 consecutive periods)
**Metric**: Lambda Duration (Average)

**Triggered by**:
- DynamoDB performance issues
- Slow Secrets Manager responses
- Network latency
- Cold start issues (rare with provisioned concurrency)

**Actions**:
1. Check DynamoDB read/write capacity metrics
2. Review Lambda memory configuration
3. Investigate external API calls
4. Consider increasing Lambda memory/timeout

### 3. Throttling Alarm

**Alarm Name**: `zapier-api-throttling-{stackName}`
**Threshold**: Any throttling events in 1 minute
**Metric**: Lambda Throttles (Sum)

**Triggered by**:
- Concurrent execution limit reached (default: 1000)
- Reserved concurrency limit reached
- Account-level limits

**Actions**:
1. Check Lambda concurrency metrics
2. Request AWS limit increase if needed
3. Implement request queuing
4. Review traffic patterns for spikes

### 4. DynamoDB Errors Alarm

**Alarm Name**: `zapier-api-dynamo-read-throttle-{stackName}`
**Threshold**: More than 5 DynamoDB errors in 5 minutes
**Metric**: DynamoDB UserErrors (Sum)

**Triggered by**:
- Read/write capacity exceeded (unlikely with on-demand billing)
- Item size exceeds 400KB limit
- Invalid queries or scans
- Conditional check failures

**Actions**:
1. Check DynamoDB metrics in CloudWatch
2. Review query patterns for optimization
3. Consider using DynamoDB DAX for caching
4. Verify billing mode is on-demand

## Testing the Alerting System

### Prerequisites

1. Subscribe to SNS topic (see above)
2. Confirm subscription via email/SMS
3. Have AWS CLI configured

### Test 1: Trigger High Error Rate Alarm

Simulate errors by invoking the Lambda with invalid payloads:

```bash
# Run the test script
./scripts/test-alerts.sh error-rate
```

Or manually:

```bash
# Get Lambda function name
FUNCTION_URL="https://YOUR_FUNCTION_URL"

# Send 15 invalid requests to trigger alarm (threshold: 10 errors in 10 minutes)
for i in {1..15}; do
  curl -X POST "$FUNCTION_URL/events" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer invalid_token" \
    -d '{"invalid": "payload"}' &
done
wait

echo "Error rate alarm should trigger in 5-10 minutes. Check your email/SMS."
```

### Test 2: Trigger High Duration Alarm

Simulate slow requests (requires code modification):

```bash
# This requires temporarily adding a sleep to the Lambda code
# Not recommended for production testing
```

**Better approach**: Monitor real performance over time.

### Test 3: Trigger Throttling Alarm

Simulate high load:

```bash
# Run the test script
./scripts/test-alerts.sh throttling
```

Or manually:

```bash
# Send 2000 concurrent requests to exceed Lambda concurrency limit
FUNCTION_URL="https://YOUR_FUNCTION_URL"

for i in {1..2000}; do
  curl "$FUNCTION_URL/health" &
done
wait

echo "Throttling alarm should trigger within 1-2 minutes."
```

### Test 4: Manual Alarm Trigger (Safest)

Use AWS CLI to set alarm state:

```bash
# Set alarm to ALARM state manually
aws cloudwatch set-alarm-state \
  --alarm-name zapier-api-high-errors-{stackName} \
  --state-value ALARM \
  --state-reason "Testing alert notification system" \
  --region us-east-2

echo "Check your email/SMS for the test notification."
echo "Alarm will auto-recover when actual metrics are OK."
```

## Notification Format

### Email Notification Example

```
Subject: ALARM: "zapier-api-high-errors-main" in US East (Ohio)

You are receiving this email because your Amazon CloudWatch Alarm
"zapier-api-high-errors-main" in the US East (Ohio) region has entered
the ALARM state, because "Threshold Crossed: 2 consecutive datapoints
[15.0 (13/11/24 07:15:00), 12.0 (13/11/24 07:10:00)] were greater than
the threshold (10.0)." at "Wednesday 13 November, 2024 07:18:23 UTC".

View this alarm in the AWS Management Console:
https://console.aws.amazon.com/cloudwatch/home?region=us-east-2#...

Alarm Details:
- Name: zapier-api-high-errors-main
- Description: Alert when Lambda error rate exceeds threshold
- State Change: OK -> ALARM
- Reason for State Change: Threshold Crossed
- Timestamp: Wednesday 13 November, 2024 07:18:23 UTC
- AWS Account: 123456789012
```

### SMS Notification Example

```
ALARM: "zapier-api-high-errors-main" in US East (Ohio) -
Threshold Crossed: 2 datapoints [15.0, 12.0] greater than 10.0
```

## Managing Subscriptions

### List All Subscriptions

```bash
aws sns list-subscriptions-by-topic \
  --topic-arn <TOPIC_ARN> \
  --region us-east-2
```

### Unsubscribe

```bash
# Get subscription ARN from list-subscriptions
aws sns unsubscribe \
  --subscription-arn <SUBSCRIPTION_ARN> \
  --region us-east-2
```

### Confirm Pending Subscription

If you missed the confirmation email:

```bash
# Request new confirmation email
aws sns confirm-subscription \
  --topic-arn <TOPIC_ARN> \
  --token <TOKEN_FROM_EMAIL>
```

Or unsubscribe and re-subscribe to get a new confirmation email.

## Alarm Thresholds Customization

To modify alarm thresholds, update `amplify/backend.ts`:

```typescript
const errorAlarm = new cloudwatch.Alarm(stack, 'HighErrorRateAlarm', {
  // ... other config
  threshold: 20, // Change from 10 to 20 errors
  evaluationPeriods: 3, // Require 3 consecutive periods instead of 2
});
```

Then redeploy:

```bash
git add amplify/backend.ts
git commit -m "chore: adjust CloudWatch alarm thresholds"
git push origin main
```

## Integration with Third-Party Services

### Slack Integration

1. Create Slack Incoming Webhook: https://api.slack.com/messaging/webhooks
2. Subscribe to SNS with the webhook URL:

```bash
aws sns subscribe \
  --topic-arn <TOPIC_ARN> \
  --protocol https \
  --notification-endpoint https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

3. Slack will receive JSON payloads. Consider using a Lambda function for better formatting.

### PagerDuty Integration

1. Get PagerDuty integration email address
2. Subscribe to SNS with the email:

```bash
aws sns subscribe \
  --topic-arn <TOPIC_ARN> \
  --protocol email \
  --notification-endpoint your-service@your-account.pagerduty.com
```

### Opsgenie Integration

Opsgenie provides SNS integration out-of-the-box:

1. Create Opsgenie SNS Integration
2. Get the HTTPS endpoint
3. Subscribe to SNS:

```bash
aws sns subscribe \
  --topic-arn <TOPIC_ARN> \
  --protocol https \
  --notification-endpoint https://api.opsgenie.com/v1/json/amazonsns?apiKey=YOUR_KEY
```

## Monitoring Costs

SNS pricing (US East):
- Email: **Free**
- SMS: ~$0.00645 per message (US)
- HTTPS: $0.60 per million notifications
- Lambda: $0.20 per million requests + Lambda execution cost

CloudWatch pricing:
- Alarms: $0.10 per alarm per month (first 10 free)
- Dashboard: $3 per month

**Estimated monthly cost for this setup**:
- 4 alarms: $0.00 (covered by free tier)
- 1 dashboard: $3.00
- 100 alert notifications via email: $0.00
- **Total: ~$3/month**

## Troubleshooting

### Not Receiving Notifications

1. **Check subscription status**:
   ```bash
   aws sns list-subscriptions-by-topic --topic-arn <TOPIC_ARN>
   ```
   Status should be "Confirmed", not "PendingConfirmation"

2. **Check spam/junk folder** for AWS emails

3. **Verify alarm is actually triggered**:
   ```bash
   aws cloudwatch describe-alarms \
     --alarm-names zapier-api-high-errors-{stackName} \
     --region us-east-2
   ```
   Check StateValue: should be "ALARM" when triggered

4. **Test with manual alarm trigger** (see above)

### Too Many Notifications

1. **Adjust alarm thresholds** in backend.ts
2. **Add alarm actions filtering** using Lambda
3. **Use composite alarms** to require multiple alarms before notifying

### Delayed Notifications

- CloudWatch evaluates alarms every 1-5 minutes
- SNS email delivery can take 1-5 minutes
- Total delay: 2-10 minutes is normal
- Use SMS for faster notifications (30-60 seconds)

## Best Practices

1. **Subscribe multiple channels**: Email for details, SMS for critical
2. **Use filtering**: Lambda function to filter/enrich notifications
3. **Test regularly**: Run test alerts monthly to verify delivery
4. **Document on-call**: Maintain runbook for each alarm type
5. **Set up escalation**: Use PagerDuty/Opsgenie for on-call rotation
6. **Monitor alarm health**: Set up alarms for missing metrics
7. **Regular review**: Adjust thresholds based on actual traffic patterns

## Resources

- [CloudWatch Alarms Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html)
- [SNS Documentation](https://docs.aws.amazon.com/sns/latest/dg/welcome.html)
- [CloudWatch Alarm Best Practices](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html)
- [Project Monitoring Documentation](./MONITORING.md)

---

**Last Updated:** 2025-11-13
**Maintained By:** Development Team
