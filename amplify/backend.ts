import { defineBackend } from '@aws-amplify/backend';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cloudwatch_actions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as cdk from 'aws-cdk-lib';
import { RemovalPolicy } from 'aws-cdk-lib';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Zapier Triggers API Backend
 * - FastAPI REST API on Lambda
 * - DynamoDB for event storage
 * - Lambda Function URL for HTTP endpoints
 */
const backend = defineBackend({});

// Get the CDK stack
const stack = backend.createStack('api-stack');

// Create DynamoDB table for events
const eventsTable = new dynamodb.Table(stack, 'EventsTable', {
  tableName: `zapier-triggers-events-${stack.stackName}`,
  partitionKey: {
    name: 'id',
    type: dynamodb.AttributeType.STRING,
  },
  sortKey: {
    name: 'created_at',
    type: dynamodb.AttributeType.STRING,
  },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
  removalPolicy: RemovalPolicy.RETAIN,
  pointInTimeRecovery: true,
  // GDPR/CCPA Compliance: Automatic data deletion after 90 days
  timeToLiveAttribute: 'ttl',
});

// Add GSI for status queries
eventsTable.addGlobalSecondaryIndex({
  indexName: 'status-index',
  partitionKey: {
    name: 'status',
    type: dynamodb.AttributeType.STRING,
  },
  sortKey: {
    name: 'created_at',
    type: dynamodb.AttributeType.STRING,
  },
});

// Create Secrets Manager secret for API credentials
const apiSecret = new secretsmanager.Secret(stack, 'ApiCredentials', {
  secretName: `zapier-api-credentials-${stack.stackName}`,
  description: 'API keys and webhook URLs for Zapier Triggers API',
  generateSecretString: {
    secretStringTemplate: JSON.stringify({
      zapier_api_key: 'PLACEHOLDER_KEY',
      zapier_webhook_url: 'https://hooks.zapier.com/placeholder',
      environment: 'development',
    }),
    generateStringKey: 'jwt_secret', // Auto-generate JWT secret
    excludeCharacters: '/@"\\', // Exclude problematic characters
  },
  removalPolicy: RemovalPolicy.RETAIN, // Keep secrets when stack is deleted
});

// Create Lambda function with Python runtime (FastAPI + Mangum)
// Dependencies are pre-installed in amplify.yml, so we just package the directory
const triggersApiFunction = new lambda.Function(stack, 'TriggersApiFunction', {
  runtime: lambda.Runtime.PYTHON_3_12,
  handler: 'main.handler',
  code: lambda.Code.fromAsset(join(__dirname, 'functions/api')),
  architecture: lambda.Architecture.X86_64,
  memorySize: 512,
  timeout: cdk.Duration.seconds(30),
  // Enable AWS X-Ray tracing for distributed tracing
  tracing: lambda.Tracing.ACTIVE,
  environment: {
    DYNAMODB_TABLE_NAME: eventsTable.tableName,
    SECRET_ARN: apiSecret.secretArn,
    // AWS_REGION is automatically provided by Lambda runtime
  },
});

// Grant Lambda permissions to access DynamoDB
eventsTable.grantReadWriteData(triggersApiFunction);

// Grant Lambda permissions to read secrets
apiSecret.grantRead(triggersApiFunction);

// Create Function URL for the Lambda (simpler than API Gateway for this use case)
const functionUrl = triggersApiFunction.addFunctionUrl({
  authType: lambda.FunctionUrlAuthType.NONE, // TODO: Add authentication in production
  cors: {
    allowedOrigins: ['*'],
    allowedMethods: [lambda.HttpMethod.ALL],
    allowedHeaders: ['*'],
  },
});

// Output the Function URL
new cdk.CfnOutput(stack, 'TriggersApiUrl', {
  value: functionUrl.url,
  description: 'Triggers API endpoint URL',
});

// Output the Secret ARN for reference
new cdk.CfnOutput(stack, 'ApiSecretArn', {
  value: apiSecret.secretArn,
  description: 'ARN of the API credentials secret in Secrets Manager',
});

// ========================================
// MONITORING AND ALERTING RESOURCES
// ========================================

// Create SNS topic for alerts
const alertsTopic = new sns.Topic(stack, 'AlertsTopic', {
  topicName: `zapier-api-alerts-${stack.stackName}`,
  displayName: 'Zapier Triggers API Alerts',
});

// Email subscriptions should be added after deployment via AWS Console or CLI
// This avoids hardcoding emails in infrastructure code and handles confirmation flow properly
// See docs/SNS_ALERTS.md for subscription instructions

// Output SNS topic ARN
new cdk.CfnOutput(stack, 'AlertsTopicArn', {
  value: alertsTopic.topicArn,
  description: 'SNS Topic ARN for CloudWatch Alarms',
});

// Create CloudWatch Alarms
// 1. High Error Rate Alarm
const errorAlarm = new cloudwatch.Alarm(stack, 'HighErrorRateAlarm', {
  alarmName: `zapier-api-high-errors-${stack.stackName}`,
  alarmDescription: 'Alert when Lambda error rate exceeds threshold',
  metric: triggersApiFunction.metricErrors({
    period: cdk.Duration.minutes(5),
    statistic: 'Sum',
  }),
  threshold: 10,
  evaluationPeriods: 2,
  comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
  treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
});

errorAlarm.addAlarmAction(new cloudwatch_actions.SnsAction(alertsTopic));

// 2. High Duration Alarm
const durationAlarm = new cloudwatch.Alarm(stack, 'HighDurationAlarm', {
  alarmName: `zapier-api-high-duration-${stack.stackName}`,
  alarmDescription: 'Alert when Lambda execution time exceeds 10 seconds',
  metric: triggersApiFunction.metricDuration({
    period: cdk.Duration.minutes(5),
    statistic: 'Average',
  }),
  threshold: 10000, // 10 seconds in milliseconds
  evaluationPeriods: 2,
  comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
  treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
});

durationAlarm.addAlarmAction(new cloudwatch_actions.SnsAction(alertsTopic));

// 3. Throttle Alarm
const throttleAlarm = new cloudwatch.Alarm(stack, 'ThrottleAlarm', {
  alarmName: `zapier-api-throttling-${stack.stackName}`,
  alarmDescription: 'Alert when Lambda is being throttled',
  metric: triggersApiFunction.metricThrottles({
    period: cdk.Duration.minutes(1),
    statistic: 'Sum',
  }),
  threshold: 1,
  evaluationPeriods: 1,
  comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
  treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
});

throttleAlarm.addAlarmAction(new cloudwatch_actions.SnsAction(alertsTopic));

// 4. DynamoDB Read Throttle Alarm
const dynamoReadThrottleAlarm = new cloudwatch.Alarm(stack, 'DynamoReadThrottleAlarm', {
  alarmName: `zapier-api-dynamo-read-throttle-${stack.stackName}`,
  alarmDescription: 'Alert when DynamoDB reads are throttled',
  metric: eventsTable.metricUserErrors({
    period: cdk.Duration.minutes(5),
    statistic: 'Sum',
  }),
  threshold: 5,
  evaluationPeriods: 1,
  comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
  treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
});

dynamoReadThrottleAlarm.addAlarmAction(new cloudwatch_actions.SnsAction(alertsTopic));

// Create CloudWatch Dashboard
const dashboard = new cloudwatch.Dashboard(stack, 'ApiDashboard', {
  dashboardName: `ZapierTriggersAPI-${stack.stackName}`,
});

// Add Lambda metrics widget
dashboard.addWidgets(
  new cloudwatch.GraphWidget({
    title: 'Lambda Invocations & Errors',
    left: [
      triggersApiFunction.metricInvocations({
        label: 'Invocations',
        color: cloudwatch.Color.BLUE,
        statistic: 'Sum',
      }),
      triggersApiFunction.metricErrors({
        label: 'Errors',
        color: cloudwatch.Color.RED,
        statistic: 'Sum',
      }),
    ],
    width: 12,
  }),
  new cloudwatch.GraphWidget({
    title: 'Lambda Duration & Throttles',
    left: [
      triggersApiFunction.metricDuration({
        label: 'Duration (ms)',
        color: cloudwatch.Color.GREEN,
        statistic: 'Average',
      }),
    ],
    right: [
      triggersApiFunction.metricThrottles({
        label: 'Throttles',
        color: cloudwatch.Color.ORANGE,
        statistic: 'Sum',
      }),
    ],
    width: 12,
  })
);

// Add DynamoDB metrics widget
dashboard.addWidgets(
  new cloudwatch.GraphWidget({
    title: 'DynamoDB Operations',
    left: [
      eventsTable.metricConsumedReadCapacityUnits({
        label: 'Read Capacity',
        color: cloudwatch.Color.BLUE,
        statistic: 'Sum',
      }),
      eventsTable.metricConsumedWriteCapacityUnits({
        label: 'Write Capacity',
        color: cloudwatch.Color.GREEN,
        statistic: 'Sum',
      }),
    ],
    width: 12,
  }),
  new cloudwatch.GraphWidget({
    title: 'DynamoDB User Errors',
    left: [
      eventsTable.metricUserErrors({
        label: 'User Errors',
        color: cloudwatch.Color.RED,
        statistic: 'Sum',
      }),
    ],
    width: 12,
  })
);

// Add custom metrics widget for API-specific metrics
dashboard.addWidgets(
  new cloudwatch.SingleValueWidget({
    title: 'Current Status',
    metrics: [
      triggersApiFunction.metricInvocations({
        label: 'Total Invocations (5m)',
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      triggersApiFunction.metricErrors({
        label: 'Errors (5m)',
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
    ],
    width: 12,
  }),
  new cloudwatch.SingleValueWidget({
    title: 'Performance',
    metrics: [
      triggersApiFunction.metricDuration({
        label: 'Avg Duration (ms)',
        statistic: 'Average',
        period: cdk.Duration.minutes(5),
      }),
      triggersApiFunction.metricDuration({
        label: 'P99 Duration (ms)',
        statistic: 'p99',
        period: cdk.Duration.minutes(5),
      }),
    ],
    width: 12,
  })
);

// Output Dashboard URL
new cdk.CfnOutput(stack, 'DashboardUrl', {
  value: `https://console.aws.amazon.com/cloudwatch/home?region=${stack.region}#dashboards:name=${dashboard.dashboardName}`,
  description: 'CloudWatch Dashboard URL',
});
