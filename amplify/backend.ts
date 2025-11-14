import { defineBackend } from '@aws-amplify/backend';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cloudwatch_actions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cdk from 'aws-cdk-lib';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as apigatewayv2 from 'aws-cdk-lib/aws-apigatewayv2';
import * as apigatewayv2_integrations from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import * as lambdaEventSources from 'aws-cdk-lib/aws-lambda-event-sources';
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
  // Enable DynamoDB Streams for real-time updates (Task 27.3)
  stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
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

// Add GSI for delivery attempt queries (Task 22.2)
// Sparse index - only indexes events with non-null last_delivery_attempt
// Use cases: retry logic, delivery-time-based metrics, stale event detection
eventsTable.addGlobalSecondaryIndex({
  indexName: 'last-attempt-index',
  partitionKey: {
    name: 'status',
    type: dynamodb.AttributeType.STRING,
  },
  sortKey: {
    name: 'last_delivery_attempt',
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

// Grant Lambda permissions to publish CloudWatch custom metrics
triggersApiFunction.addToRolePolicy(new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  actions: ['cloudwatch:PutMetricData'],
  resources: ['*'],
}));

// Create Function URL for the Lambda (simpler than API Gateway for this use case)
// Note: Using NONE for AWS-level auth - security is handled at application level via JWT tokens
const functionUrl = triggersApiFunction.addFunctionUrl({
  authType: lambda.FunctionUrlAuthType.NONE,
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

// ========================================
// DISPATCHER SERVICE RESOURCES
// ========================================

// Create Lambda function for event dispatcher
const dispatcherFunction = new lambda.Function(stack, 'DispatcherFunction', {
  runtime: lambda.Runtime.PYTHON_3_12,
  handler: 'main.handler',
  code: lambda.Code.fromAsset(join(__dirname, 'functions/dispatcher')),
  architecture: lambda.Architecture.X86_64,
  memorySize: 256,
  timeout: cdk.Duration.seconds(300), // 5 minutes for processing multiple events
  tracing: lambda.Tracing.ACTIVE,
  environment: {
    API_BASE_URL: functionUrl.url.replace(/\/$/, ''), // Remove trailing slash
    DYNAMODB_TABLE_NAME: eventsTable.tableName,
    SECRET_ARN: apiSecret.secretArn,
    MAX_EVENTS_PER_RUN: '100',
  },
});

// Grant dispatcher permissions to read/write DynamoDB
eventsTable.grantReadWriteData(dispatcherFunction);

// Grant dispatcher permissions to read secrets
apiSecret.grantRead(dispatcherFunction);

// Grant dispatcher permissions to publish CloudWatch metrics
dispatcherFunction.addToRolePolicy(new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  actions: ['cloudwatch:PutMetricData'],
  resources: ['*'],
}));

// Create EventBridge rule to trigger dispatcher every 5 minutes
// Note: ruleName auto-generated by CDK to avoid exceeding 64-char EventBridge limit
const dispatcherRule = new events.Rule(stack, 'DispatcherScheduleRule', {
  description: 'Triggers dispatcher Lambda every 5 minutes to process pending events',
  schedule: events.Schedule.rate(cdk.Duration.minutes(5)),
  enabled: true,
});

// Add dispatcher Lambda as target
dispatcherRule.addTarget(new targets.LambdaFunction(dispatcherFunction, {
  retryAttempts: 2,
}));

// Create CloudWatch alarms for dispatcher
const dispatcherErrorAlarm = new cloudwatch.Alarm(stack, 'DispatcherErrorAlarm', {
  alarmName: `zapier-dispatcher-errors-${stack.stackName}`,
  alarmDescription: 'Alert when dispatcher Lambda encounters errors',
  metric: dispatcherFunction.metricErrors({
    period: cdk.Duration.minutes(5),
    statistic: 'Sum',
  }),
  threshold: 3,
  evaluationPeriods: 1,
  comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
  treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
});

dispatcherErrorAlarm.addAlarmAction(new cloudwatch_actions.SnsAction(alertsTopic));

// Add dispatcher metrics to dashboard
dashboard.addWidgets(
  new cloudwatch.GraphWidget({
    title: 'Dispatcher - Event Processing',
    left: [
      new cloudwatch.Metric({
        namespace: 'ZapierTriggersAPI/Dispatcher',
        metricName: 'EventsProcessed',
        statistic: 'Sum',
        label: 'Events Processed',
        color: cloudwatch.Color.BLUE,
        period: cdk.Duration.minutes(5),
      }),
      new cloudwatch.Metric({
        namespace: 'ZapierTriggersAPI/Dispatcher',
        metricName: 'SuccessfulDeliveries',
        statistic: 'Sum',
        label: 'Successful',
        color: cloudwatch.Color.GREEN,
        period: cdk.Duration.minutes(5),
      }),
      new cloudwatch.Metric({
        namespace: 'ZapierTriggersAPI/Dispatcher',
        metricName: 'FailedDeliveries',
        statistic: 'Sum',
        label: 'Failed',
        color: cloudwatch.Color.RED,
        period: cdk.Duration.minutes(5),
      }),
    ],
    width: 12,
  }),
  new cloudwatch.GraphWidget({
    title: 'Dispatcher - Performance',
    left: [
      new cloudwatch.Metric({
        namespace: 'ZapierTriggersAPI/Dispatcher',
        metricName: 'DeliveryLatency',
        statistic: 'Average',
        label: 'Avg Delivery Time (ms)',
        color: cloudwatch.Color.PURPLE,
        period: cdk.Duration.minutes(5),
      }),
    ],
    right: [
      new cloudwatch.Metric({
        namespace: 'ZapierTriggersAPI/Dispatcher',
        metricName: 'RetryAttempts',
        statistic: 'Sum',
        label: 'Retry Attempts',
        color: cloudwatch.Color.ORANGE,
        period: cdk.Duration.minutes(5),
      }),
    ],
    width: 12,
  })
);

// Output Dispatcher Function details
new cdk.CfnOutput(stack, 'DispatcherFunctionArn', {
  value: dispatcherFunction.functionArn,
  description: 'ARN of the Dispatcher Lambda function',
});

new cdk.CfnOutput(stack, 'DispatcherScheduleRuleName', {
  value: dispatcherRule.ruleName,
  description: 'Name of the EventBridge rule that triggers the dispatcher',
});

// ========================================
// WEBSOCKET REAL-TIME UPDATES (TASK 27)
// ========================================

// Create DynamoDB table for WebSocket connections (Task 27.2)
const connectionsTable = new dynamodb.Table(stack, 'ConnectionsTable', {
  tableName: `zapier-websocket-connections-${stack.stackName}`,
  partitionKey: {
    name: 'connectionId',
    type: dynamodb.AttributeType.STRING,
  },
  billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
  removalPolicy: RemovalPolicy.DESTROY, // Clean up on stack deletion
  // Auto-expire stale connections after 24 hours
  timeToLiveAttribute: 'ttl',
});

// Create Lambda function for WebSocket $connect route (Task 27.2)
const wsConnectFunction = new lambda.Function(stack, 'WebSocketConnectFunction', {
  runtime: lambda.Runtime.PYTHON_3_12,
  handler: 'main.handler',
  code: lambda.Code.fromAsset(join(__dirname, 'functions/websocket-connect')),
  architecture: lambda.Architecture.X86_64,
  memorySize: 256,
  timeout: cdk.Duration.seconds(10),
  tracing: lambda.Tracing.ACTIVE,
  environment: {
    CONNECTIONS_TABLE_NAME: connectionsTable.tableName,
  },
});

// Grant permissions to write to connections table
connectionsTable.grantWriteData(wsConnectFunction);

// Create Lambda function for WebSocket $disconnect route (Task 27.2)
const wsDisconnectFunction = new lambda.Function(stack, 'WebSocketDisconnectFunction', {
  runtime: lambda.Runtime.PYTHON_3_12,
  handler: 'main.handler',
  code: lambda.Code.fromAsset(join(__dirname, 'functions/websocket-disconnect')),
  architecture: lambda.Architecture.X86_64,
  memorySize: 256,
  timeout: cdk.Duration.seconds(10),
  tracing: lambda.Tracing.ACTIVE,
  environment: {
    CONNECTIONS_TABLE_NAME: connectionsTable.tableName,
  },
});

// Grant permissions to delete from connections table
connectionsTable.grantWriteData(wsDisconnectFunction);

// Create Lambda function for WebSocket message handler (Task 27.2)
const wsMessageFunction = new lambda.Function(stack, 'WebSocketMessageFunction', {
  runtime: lambda.Runtime.PYTHON_3_12,
  handler: 'main.handler',
  code: lambda.Code.fromAsset(join(__dirname, 'functions/websocket-message')),
  architecture: lambda.Architecture.X86_64,
  memorySize: 256,
  timeout: cdk.Duration.seconds(10),
  tracing: lambda.Tracing.ACTIVE,
  environment: {
    // WEBSOCKET_API_ENDPOINT will be set after WebSocket API is created
  },
});

// Create Lambda function for WebSocket broadcaster (Task 27.4)
const wsBroadcasterFunction = new lambda.Function(stack, 'WebSocketBroadcasterFunction', {
  runtime: lambda.Runtime.PYTHON_3_12,
  handler: 'main.handler',
  code: lambda.Code.fromAsset(join(__dirname, 'functions/websocket-broadcaster')),
  architecture: lambda.Architecture.X86_64,
  memorySize: 512,
  timeout: cdk.Duration.seconds(60),
  tracing: lambda.Tracing.ACTIVE,
  environment: {
    CONNECTIONS_TABLE_NAME: connectionsTable.tableName,
    // WEBSOCKET_API_ENDPOINT will be set after WebSocket API is created
  },
});

// Grant permissions to read connections and read/write events
connectionsTable.grantReadData(wsBroadcasterFunction);
connectionsTable.grantWriteData(wsBroadcasterFunction); // For cleaning up stale connections

// Create WebSocket API (Task 27.1)
const webSocketApi = new apigatewayv2.WebSocketApi(stack, 'WebSocketApi', {
  apiName: `zapier-triggers-websocket-${stack.stackName}`,
  description: 'WebSocket API for real-time event updates',
  // Route selection based on action field in message body
  routeSelectionExpression: '$request.body.action',
});

// Create WebSocket stage with auto-deployment (Task 27.1)
const webSocketStage = new apigatewayv2.WebSocketStage(stack, 'WebSocketStage', {
  webSocketApi: webSocketApi,
  stageName: 'production',
  autoDeploy: true,
});

// Add $connect route (Task 27.1)
webSocketApi.addRoute('$connect', {
  integration: new apigatewayv2_integrations.WebSocketLambdaIntegration(
    'ConnectIntegration',
    wsConnectFunction
  ),
});

// Add $disconnect route (Task 27.1)
webSocketApi.addRoute('$disconnect', {
  integration: new apigatewayv2_integrations.WebSocketLambdaIntegration(
    'DisconnectIntegration',
    wsDisconnectFunction
  ),
});

// Add $default route for unmatched messages (Task 27.1)
webSocketApi.addRoute('$default', {
  integration: new apigatewayv2_integrations.WebSocketLambdaIntegration(
    'DefaultIntegration',
    wsMessageFunction // Use message handler for PING/PONG and other messages
  ),
});

// Grant message handler permission to post messages to WebSocket API
wsMessageFunction.addToRolePolicy(new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  actions: ['execute-api:ManageConnections'],
  resources: [
    `arn:aws:execute-api:${stack.region}:${stack.account}:${webSocketApi.apiId}/${webSocketStage.stageName}/*`,
  ],
}));

// Update message handler environment with WebSocket API endpoint
wsMessageFunction.addEnvironment(
  'WEBSOCKET_API_ENDPOINT',
  `${webSocketApi.apiEndpoint}/${webSocketStage.stageName}`
);

// Grant broadcaster permission to post messages to WebSocket API (Task 27.4)
wsBroadcasterFunction.addToRolePolicy(new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  actions: ['execute-api:ManageConnections'],
  resources: [
    `arn:aws:execute-api:${stack.region}:${stack.account}:${webSocketApi.apiId}/${webSocketStage.stageName}/*`,
  ],
}));

// Update broadcaster environment with WebSocket API endpoint (Task 27.4)
wsBroadcasterFunction.addEnvironment(
  'WEBSOCKET_API_ENDPOINT',
  `${webSocketApi.apiEndpoint}/${webSocketStage.stageName}`
);

// Add DynamoDB Stream event source to broadcaster (Task 27.3)
wsBroadcasterFunction.addEventSource(new lambdaEventSources.DynamoEventSource(eventsTable, {
  startingPosition: lambda.StartingPosition.LATEST,
  batchSize: 10,
  maxBatchingWindow: cdk.Duration.seconds(1),
  retryAttempts: 3,
  bisectBatchOnError: true,
  // Only trigger on INSERT and MODIFY events
  filters: [
    lambda.FilterCriteria.filter({
      eventName: lambda.FilterRule.isEqual('INSERT'),
    }),
    lambda.FilterCriteria.filter({
      eventName: lambda.FilterRule.isEqual('MODIFY'),
    }),
  ],
}));

// Output WebSocket API URL (Task 27.1)
new cdk.CfnOutput(stack, 'WebSocketApiUrl', {
  value: webSocketStage.url,
  description: 'WebSocket API endpoint URL (wss://...)',
});

new cdk.CfnOutput(stack, 'WebSocketApiId', {
  value: webSocketApi.apiId,
  description: 'WebSocket API ID',
});

// Create CloudWatch alarms for WebSocket operations
const wsConnectErrorAlarm = new cloudwatch.Alarm(stack, 'WebSocketConnectErrorAlarm', {
  alarmName: `zapier-websocket-connect-errors-${stack.stackName}`,
  alarmDescription: 'Alert when WebSocket connect Lambda encounters errors',
  metric: wsConnectFunction.metricErrors({
    period: cdk.Duration.minutes(5),
    statistic: 'Sum',
  }),
  threshold: 5,
  evaluationPeriods: 1,
  comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
  treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
});

wsConnectErrorAlarm.addAlarmAction(new cloudwatch_actions.SnsAction(alertsTopic));

const wsBroadcasterErrorAlarm = new cloudwatch.Alarm(stack, 'WebSocketBroadcasterErrorAlarm', {
  alarmName: `zapier-websocket-broadcaster-errors-${stack.stackName}`,
  alarmDescription: 'Alert when WebSocket broadcaster Lambda encounters errors',
  metric: wsBroadcasterFunction.metricErrors({
    period: cdk.Duration.minutes(5),
    statistic: 'Sum',
  }),
  threshold: 10,
  evaluationPeriods: 2,
  comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
  treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
});

wsBroadcasterErrorAlarm.addAlarmAction(new cloudwatch_actions.SnsAction(alertsTopic));

// Add WebSocket metrics to dashboard
dashboard.addWidgets(
  new cloudwatch.GraphWidget({
    title: 'WebSocket - Connections',
    left: [
      wsConnectFunction.metricInvocations({
        label: 'Connections',
        color: cloudwatch.Color.BLUE,
        statistic: 'Sum',
      }),
      wsDisconnectFunction.metricInvocations({
        label: 'Disconnections',
        color: cloudwatch.Color.ORANGE,
        statistic: 'Sum',
      }),
    ],
    right: [
      wsConnectFunction.metricErrors({
        label: 'Connect Errors',
        color: cloudwatch.Color.RED,
        statistic: 'Sum',
      }),
    ],
    width: 12,
  }),
  new cloudwatch.GraphWidget({
    title: 'WebSocket - Broadcasting',
    left: [
      wsBroadcasterFunction.metricInvocations({
        label: 'Broadcast Invocations',
        color: cloudwatch.Color.GREEN,
        statistic: 'Sum',
      }),
      wsBroadcasterFunction.metricErrors({
        label: 'Broadcast Errors',
        color: cloudwatch.Color.RED,
        statistic: 'Sum',
      }),
    ],
    right: [
      wsBroadcasterFunction.metricDuration({
        label: 'Broadcast Duration (ms)',
        color: cloudwatch.Color.PURPLE,
        statistic: 'Average',
      }),
    ],
    width: 12,
  })
);
