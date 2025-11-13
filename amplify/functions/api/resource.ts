import { defineFunction } from '@aws-amplify/backend';

export const triggersApi = defineFunction({
  name: 'triggers-api',
  entry: './main.py',
  runtime: 'python3.12' as any,
  memoryMB: 512,
  timeoutSeconds: 30,
});
