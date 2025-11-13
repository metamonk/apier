# Zapier Triggers API - Node.js Client

Production-ready Node.js client for the Zapier Triggers API with automatic token management and comprehensive error handling.

## Installation

```bash
npm install
```

Or manually install dependencies:

```bash
npm install node-fetch
```

## Configuration

1. Copy the example environment file:
   ```bash
   cp ../.env.example .env
   ```

2. Edit `.env` and add your API key:
   ```bash
   ZAPIER_API_KEY=your-api-key-here
   ```

3. Get your API key from AWS Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id zapier-api-credentials-{stackName} \
     --query SecretString --output text | jq -r .zapier_api_key
   ```

## Usage

### Quick Start

```bash
# Run the example client
ZAPIER_API_KEY=your-key-here node client.js
```

### As a Module

```javascript
import ZapierTriggersClient from './client.js';

const client = new ZapierTriggersClient(process.env.ZAPIER_API_KEY);

// Create an event
const event = await client.createEvent('user.created', 'web-app', {
  user_id: '12345',
  email: 'user@example.com'
});

// Get pending events
const events = await client.getInbox();

// Process all events
await client.processInbox(async (event) => {
  console.log('Processing:', event.id);
  // Your processing logic here
});
```

## API Reference

### Constructor

```javascript
const client = new ZapierTriggersClient(apiKey, baseUrl?)
```

- `apiKey` (required): Your Zapier API key
- `baseUrl` (optional): API base URL (default: production endpoint)

### Methods

#### `createEvent(type, source, payload)`

Create a new event.

**Parameters:**
- `type` (string): Event type (e.g., 'user.created')
- `source` (string): Event source (e.g., 'web-app')
- `payload` (object): Event data

**Returns:** Promise<object> - Created event with id, status, timestamp

#### `getInbox()`

Retrieve pending events.

**Returns:** Promise<Array> - List of pending events

#### `acknowledgeEvent(eventId)`

Acknowledge event delivery.

**Parameters:**
- `eventId` (string): Event ID to acknowledge

**Returns:** Promise<object> - Acknowledgment response

#### `processInbox(callback)`

Process all pending events with a callback.

**Parameters:**
- `callback` (async function): Function to process each event

**Returns:** Promise<Array> - Processing results

#### `healthCheck()`

Check API health status.

**Returns:** Promise<object> - Health status

## Error Handling

The client includes comprehensive error handling:

```javascript
try {
  await client.createEvent('user.created', 'web-app', {});
} catch (error) {
  if (error.message.includes('401')) {
    console.error('Invalid API key');
  } else if (error.message.includes('404')) {
    console.error('Event not found');
  } else {
    console.error('Unexpected error:', error);
  }
}
```

## Features

- Automatic JWT token management and refresh
- Token caching for 23 hours (refreshes 1 hour before expiry)
- Comprehensive error handling
- Batch event processing
- TypeScript-ready with JSDoc comments

## Requirements

- Node.js 16+ (or 18+ for native fetch support)
- Active Zapier API key from AWS Secrets Manager

## Documentation

See the main [SDK Snippets documentation](../../docs/SDK_SNIPPETS.md) for more examples and best practices.
