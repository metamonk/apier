import { defineBackend } from '@aws-amplify/backend';
import { auth } from './auth/resource';
import { data } from './data/resource';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as cdk from 'aws-cdk-lib';
import { RemovalPolicy } from 'aws-cdk-lib';
import path from 'path';

/**
 * Zapier Triggers API Backend
 * - FastAPI REST API on Lambda
 * - DynamoDB for event storage
 * - API Gateway for HTTP endpoints
 */
const backend = defineBackend({
  auth,
  data,
});

// Get the CDK stack
const { stack } = backend.auth.resources.userPool;

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

// Create Lambda function with Docker (FastAPI + Lambda Web Adapter)
const triggersApiFunction = new lambda.DockerImageFunction(stack, 'TriggersApiFunction', {
  functionName: `triggers-api-${stack.stackName}`,
  code: lambda.DockerImageCode.fromImageAsset(path.join(__dirname, 'functions/api')),
  memorySize: 512,
  timeout: cdk.Duration.seconds(30),
  environment: {
    DYNAMODB_TABLE_NAME: eventsTable.tableName,
    AWS_REGION: stack.region,
  },
});

// Grant Lambda permissions to access DynamoDB
eventsTable.grantReadWriteData(triggersApiFunction);

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
