/**
 * Zapier Triggers API - Node.js Client
 *
 * A production-ready client for interacting with the Zapier Triggers API.
 *
 * Features:
 * - Automatic JWT token management and refresh
 * - Comprehensive error handling
 * - Event creation, retrieval, and acknowledgment
 * - Batch event processing
 *
 * Usage:
 *   import ZapierTriggersClient from './client.js';
 *   const client = new ZapierTriggersClient(process.env.ZAPIER_API_KEY);
 *   await client.createEvent('user.created', 'web-app', { user_id: '123' });
 */

import fetch from 'node-fetch';

class ZapierTriggersClient {
  /**
   * Initialize the Zapier Triggers API client
   * @param {string} apiKey - Your Zapier API key from AWS Secrets Manager
   * @param {string} baseUrl - API base URL (default: production endpoint)
   */
  constructor(
    apiKey,
    baseUrl = 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws'
  ) {
    if (!apiKey) {
      throw new Error('API key is required');
    }

    this.apiKey = apiKey;
    this.baseUrl = baseUrl;
    this.token = null;
    this.tokenExpiry = null;
  }

  /**
   * Ensure we have a valid token, refreshing if needed
   * @private
   */
  async ensureAuthenticated() {
    if (!this.token || this.tokenExpiry < Date.now()) {
      await this.authenticate();
    }
  }

  /**
   * Authenticate with the API and obtain JWT token
   * Token is valid for 24 hours
   * @private
   */
  async authenticate() {
    try {
      const response = await fetch(`${this.baseUrl}/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          username: 'api',
          password: this.apiKey,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          `Authentication failed: ${response.status} ${response.statusText} - ${errorText}`
        );
      }

      const data = await response.json();
      this.token = data.access_token;

      // Token is valid for 24 hours, refresh 1 hour before expiry
      this.tokenExpiry = Date.now() + 23 * 60 * 60 * 1000;

      console.log('Successfully authenticated with Zapier Triggers API');
    } catch (error) {
      console.error('Authentication error:', error.message);
      throw error;
    }
  }

  /**
   * Create a new event in the Zapier Triggers API
   *
   * @param {string} type - Event type identifier (e.g., 'user.created', 'order.placed')
   * @param {string} source - Event source system (e.g., 'web-app', 'shopify')
   * @param {object} payload - Event data as JSON object
   * @returns {Promise<object>} Created event with id, status, and timestamp
   *
   * @example
   * const event = await client.createEvent('user.created', 'web-app', {
   *   user_id: '12345',
   *   email: 'user@example.com'
   * });
   * console.log('Event created:', event.id);
   */
  async createEvent(type, source, payload) {
    await this.ensureAuthenticated();

    try {
      const response = await fetch(`${this.baseUrl}/events`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ type, source, payload }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          `Failed to create event: ${response.status} - ${JSON.stringify(errorData)}`
        );
      }

      return await response.json();
    } catch (error) {
      console.error('Event creation error:', error.message);
      throw error;
    }
  }

  /**
   * Retrieve all pending events from the inbox
   *
   * @returns {Promise<Array>} Array of pending events (max 100)
   *
   * @example
   * const events = await client.getInbox();
   * console.log(`Found ${events.length} pending events`);
   */
  async getInbox() {
    await this.ensureAuthenticated();

    try {
      const response = await fetch(`${this.baseUrl}/inbox`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${this.token}`,
        },
      });

      if (!response.ok) {
        throw new Error(
          `Failed to retrieve inbox: ${response.status} ${response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      console.error('Inbox retrieval error:', error.message);
      throw error;
    }
  }

  /**
   * Acknowledge successful event processing
   *
   * @param {string} eventId - Event ID to acknowledge
   * @returns {Promise<object>} Acknowledgment response with updated status
   *
   * @example
   * const result = await client.acknowledgeEvent('550e8400-e29b-41d4-a716-446655440000');
   * console.log('Event acknowledged:', result.status); // 'delivered'
   */
  async acknowledgeEvent(eventId) {
    await this.ensureAuthenticated();

    try {
      const response = await fetch(`${this.baseUrl}/inbox/${eventId}/ack`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error(`Event not found: ${eventId}`);
        }
        throw new Error(
          `Failed to acknowledge event: ${response.status} ${response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      console.error('Event acknowledgment error:', error.message);
      throw error;
    }
  }

  /**
   * Process all pending events with a callback function
   * Automatically acknowledges events after successful processing
   *
   * @param {Function} callback - Async function to process each event
   * @returns {Promise<Array>} Array of processing results
   *
   * @example
   * const results = await client.processInbox(async (event) => {
   *   console.log(`Processing ${event.type}:`, event.payload);
   *   // Your processing logic here
   * });
   * console.log('Processed:', results.filter(r => r.status === 'success').length);
   */
  async processInbox(callback) {
    const events = await this.getInbox();
    console.log(`Processing ${events.length} pending events...`);

    const results = [];

    for (const event of events) {
      try {
        // Process event with callback
        await callback(event);

        // Acknowledge successful processing
        await this.acknowledgeEvent(event.id);

        results.push({ eventId: event.id, status: 'success' });
        console.log(`✓ Processed and acknowledged event ${event.id}`);
      } catch (error) {
        results.push({
          eventId: event.id,
          status: 'failed',
          error: error.message,
        });
        console.error(`✗ Failed to process event ${event.id}:`, error.message);
      }
    }

    return results;
  }

  /**
   * Check API health status
   * @returns {Promise<object>} Health status
   */
  async healthCheck() {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return await response.json();
    } catch (error) {
      console.error('Health check error:', error.message);
      throw error;
    }
  }
}

// Example usage
async function main() {
  // Initialize client with API key from environment variable
  const apiKey = process.env.ZAPIER_API_KEY;

  if (!apiKey) {
    console.error('Error: ZAPIER_API_KEY environment variable not set');
    console.log('Usage: ZAPIER_API_KEY=your-key-here node client.js');
    process.exit(1);
  }

  const client = new ZapierTriggersClient(apiKey);

  try {
    // 1. Health check
    console.log('\n1. Checking API health...');
    const health = await client.healthCheck();
    console.log('API status:', health);

    // 2. Create a sample event
    console.log('\n2. Creating sample event...');
    const event = await client.createEvent('user.created', 'web-app', {
      user_id: '12345',
      email: 'john.doe@example.com',
      name: 'John Doe',
      created_at: new Date().toISOString(),
      metadata: {
        signup_source: 'web',
        plan: 'premium',
      },
    });
    console.log('Event created:', {
      id: event.id,
      status: event.status,
      timestamp: event.timestamp,
    });

    // 3. Retrieve pending events
    console.log('\n3. Retrieving pending events...');
    const pendingEvents = await client.getInbox();
    console.log(`Found ${pendingEvents.length} pending events`);

    if (pendingEvents.length > 0) {
      console.log('\nPending events:');
      pendingEvents.slice(0, 5).forEach((evt, idx) => {
        console.log(
          `  ${idx + 1}. ${evt.id} - ${evt.type} (${evt.source}) - ${evt.created_at}`
        );
      });

      if (pendingEvents.length > 5) {
        console.log(`  ... and ${pendingEvents.length - 5} more`);
      }
    }

    // 4. Process events with custom handler
    console.log('\n4. Processing events...');
    const results = await client.processInbox(async (event) => {
      console.log(`  Processing event ${event.id}: ${event.type}`);
      console.log(`    Source: ${event.source}`);
      console.log(`    Payload:`, JSON.stringify(event.payload, null, 2));

      // Simulate processing time
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Your custom event processing logic here
      // For example: send to webhook, store in database, trigger workflow, etc.
    });

    // 5. Display results
    console.log('\n5. Processing complete!');
    const successful = results.filter((r) => r.status === 'success').length;
    const failed = results.filter((r) => r.status === 'failed').length;

    console.log(`  ✓ Successful: ${successful}`);
    console.log(`  ✗ Failed: ${failed}`);

    if (failed > 0) {
      console.log('\nFailed events:');
      results
        .filter((r) => r.status === 'failed')
        .forEach((r) => {
          console.log(`  - ${r.eventId}: ${r.error}`);
        });
    }
  } catch (error) {
    console.error('\n❌ Error:', error.message);
    process.exit(1);
  }
}

// Export client class as default
export default ZapierTriggersClient;

// Run example if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
