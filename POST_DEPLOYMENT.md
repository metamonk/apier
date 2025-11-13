# Post-Deployment Setup Guide

This guide covers the steps to complete after deploying the enhanced monitoring and observability features.

## Overview

You've successfully deployed:
- AWS X-Ray distributed tracing
- CloudWatch dashboards with comprehensive metrics
- Automated CloudWatch alarms
- SNS topic for alert notifications

## Required Post-Deployment Steps

### 1. Update SNS Email Subscription

The SNS topic is created with a placeholder email. You must update it with your actual email address.

```bash
# Get your stack name from Amplify Console or CloudFormation
STACK_NAME="your-stack-name"  # e.g., amplify-dmmfqlsr845yz-main-branch-6ca37098e7-apistack7B433BC7-MMMAWD4LJ6AL

# Get SNS topic ARN
TOPIC_ARN=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`AlertsTopicArn`].OutputValue' \
  --output text \
  --region us-east-2)

echo "SNS Topic ARN: $TOPIC_ARN"

# Subscribe your email
aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-2

# Check your email and confirm the subscription by clicking the link
```

**Important**: You must confirm the email subscription by clicking the confirmation link sent to your inbox.

### 2. Access Your CloudWatch Dashboard

```bash
# Get dashboard URL
DASHBOARD_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`DashboardUrl`].OutputValue' \
  --output text \
  --region us-east-2)

echo "Dashboard URL: $DASHBOARD_URL"

# Open in browser (macOS)
open "$DASHBOARD_URL"

# Or manually navigate to:
# CloudWatch Console → Dashboards → ZapierTriggersAPI-{stack-name}
```

### 3. Verify X-Ray Tracing

After making some API requests:

```bash
# Get recent traces
aws xray get-trace-summaries \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --region us-east-2

# Or view in console
# X-Ray Console → Traces → Service map
```

### 4. Test Alert System

Manually trigger an alarm to verify notifications work:

```bash
# Trigger high error alarm
aws cloudwatch set-alarm-state \
  --alarm-name "zapier-api-high-errors-${STACK_NAME}" \
  --state-value ALARM \
  --state-reason "Testing alert system" \
  --region us-east-2

# You should receive an email notification within 1-2 minutes

# Reset alarm to OK
aws cloudwatch set-alarm-state \
  --alarm-name "zapier-api-high-errors-${STACK_NAME}" \
  --state-value OK \
  --state-reason "Test complete" \
  --region us-east-2
```

### 5. Update backend.ts Email (Optional)

Edit `/Users/zeno/Projects/zapier/apier/amplify/backend.ts`:

```typescript
// Find this line (around line 135):
alertsTopic.addSubscription(
  new subscriptions.EmailSubscription('REPLACE_WITH_YOUR_EMAIL@example.com')
);

// Change to your actual email:
alertsTopic.addSubscription(
  new subscriptions.EmailSubscription('your-actual-email@example.com')
);
```

Then redeploy:
```bash
git add amplify/backend.ts
git commit -m "fix: update SNS email subscription"
git push origin main  # or dev branch
```

## Verification Checklist

- [ ] SNS email subscription confirmed (check inbox for confirmation email)
- [ ] CloudWatch dashboard accessible and showing metrics
- [ ] X-Ray traces appearing in console after API requests
- [ ] Test alarm successfully sent email notification
- [ ] All 4 CloudWatch alarms are in "OK" or "INSUFFICIENT_DATA" state

## View All Resources

```bash
# List all CloudWatch alarms
aws cloudwatch describe-alarms \
  --query 'MetricAlarms[?contains(AlarmName, `zapier-api`)].{Name:AlarmName,State:StateValue}' \
  --output table \
  --region us-east-2

# List SNS subscriptions
aws sns list-subscriptions-by-topic \
  --topic-arn $TOPIC_ARN \
  --region us-east-2

# View CloudWatch dashboard
aws cloudwatch list-dashboards \
  --query 'DashboardEntries[?contains(DashboardName, `ZapierTriggersAPI`)]' \
  --region us-east-2
```

## Common Issues

### Issue: Email confirmation not received

**Solution**:
1. Check spam/junk folder
2. Verify email address is correct
3. Try subscribing again with correct email

### Issue: Dashboard not showing metrics

**Solution**:
1. Wait 5-10 minutes for metrics to populate
2. Make some API requests to generate metrics
3. Refresh the dashboard

### Issue: X-Ray traces not appearing

**Solution**:
1. Verify Lambda has X-Ray tracing enabled (check Lambda console)
2. Make API requests to generate traces
3. Wait 1-2 minutes for traces to appear
4. Check IAM permissions for X-Ray

## Optional Enhancements

### Add SMS Notifications

```bash
aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol sms \
  --notification-endpoint +1234567890 \
  --region us-east-2
```

### Add Slack/Webhook Notifications

```bash
aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol https \
  --notification-endpoint https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
  --region us-east-2
```

### Update Log Retention for Production

```bash
# Set to 30 days for production
aws logs put-retention-policy \
  --log-group-name /aws/lambda/YOUR-LAMBDA-FUNCTION-NAME \
  --retention-in-days 30 \
  --region us-east-2
```

## Documentation

For detailed information, see:
- [MONITORING.md](/Users/zeno/Projects/zapier/apier/docs/MONITORING.md) - Complete monitoring guide
- [DEPLOYMENT.md](/Users/zeno/Projects/zapier/apier/docs/DEPLOYMENT.md) - Deployment strategies and blue-green deployments

## Support

If you encounter issues:
1. Check CloudWatch logs for Lambda errors
2. Review X-Ray traces for request failures
3. Verify IAM permissions for Lambda execution role
4. Check CloudFormation stack events for deployment issues

---

**Last Updated:** 2025-11-13
