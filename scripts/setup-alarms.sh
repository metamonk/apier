#!/bin/bash
# setup-alarms.sh - Create all CloudWatch alarms for Zapier Triggers API
# Run this after deploying the API to set up monitoring alerts

set -e

REGION="us-east-2"
LAMBDA_FUNCTION="amplify-dmmfqlsr845yz-mai-TriggersApiFunction53F37-11nL053fQfsL"

echo "🔔 Creating CloudWatch alarms for Zapier Triggers API..."
echo ""

# 1. High Ingestion Latency
echo "Creating alarm: High Ingestion Latency..."
aws cloudwatch put-metric-alarm \
  --alarm-name zapier-api-high-ingestion-latency \
  --alarm-description "Alert when POST /events ingestion latency exceeds 1 second" \
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

# 2. High 5xx Errors
echo "Creating alarm: High 5xx Errors..."
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

# 3. Lambda High Error Rate
echo "Creating alarm: Lambda High Error Rate..."
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

# 4. Lambda Throttling
echo "Creating alarm: Lambda Throttling..."
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

echo ""
echo "✓ All alarms created successfully!"
echo ""
echo "📧 Next Steps: Configure SNS Notifications"
echo "1. Create an SNS topic:"
echo "   aws sns create-topic --name zapier-api-alerts --region $REGION"
echo ""
echo "2. Subscribe your email to the topic:"
echo "   aws sns subscribe --topic-arn arn:aws:sns:$REGION:971422717446:zapier-api-alerts \\"
echo "     --protocol email --notification-endpoint your-email@example.com --region $REGION"
echo ""
echo "3. Add the SNS topic to alarms (example):"
echo "   aws cloudwatch put-metric-alarm --alarm-name zapier-api-high-ingestion-latency \\"
echo "     --alarm-actions arn:aws:sns:$REGION:971422717446:zapier-api-alerts \\"
echo "     --region $REGION"
echo ""
echo "📊 View alarms in AWS Console:"
echo "   https://console.aws.amazon.com/cloudwatch/home?region=$REGION#alarmsV2:"
