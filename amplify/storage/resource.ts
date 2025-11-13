import { defineBackend } from '@aws-amplify/backend';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { RemovalPolicy } from 'aws-cdk-lib';

export function createEventsTable(stack: any) {
  const eventsTable = new dynamodb.Table(stack, 'EventsTable', {
    tableName: 'zapier-triggers-events',
    partitionKey: {
      name: 'id',
      type: dynamodb.AttributeType.STRING,
    },
    sortKey: {
      name: 'created_at',
      type: dynamodb.AttributeType.STRING,
    },
    billingMode: dynamodb.BillingMode.PAY_PER_REQUEST, // Auto-scaling
    removalPolicy: RemovalPolicy.RETAIN, // Keep data on stack deletion
    pointInTimeRecovery: true, // Enable backups
  });

  // GSI for querying by status
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

  return eventsTable;
}
