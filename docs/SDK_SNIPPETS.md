# Zapier Triggers API - SDK Snippets

Comprehensive code examples for integrating with the Zapier Triggers API in Node.js and Python.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Authentication](#authentication)
- [Creating Events](#creating-events)
- [Retrieving Events (Inbox)](#retrieving-events-inbox)
- [Acknowledging Events](#acknowledging-events)
- [Complete End-to-End Examples](#complete-end-to-end-examples)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)

---

## Quick Start

### Base URL

```
https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws
```

### Authentication Flow

1. Obtain JWT token from `/token` endpoint
2. Include token in `Authorization: Bearer {token}` header for all protected endpoints
3. Token is valid for 24 hours

---

## Installation

### Node.js Dependencies

```bash
npm install node-fetch
# or using yarn
yarn add node-fetch

# For TypeScript support
npm install --save-dev @types/node-fetch
```

**Minimum Node.js version:** 18+ (native fetch support) or 16+ with node-fetch

### Python Dependencies

```bash
pip install requests
# or using poetry
poetry add requests
```

**Minimum Python version:** 3.8+

---

## Authentication

### Node.js - Obtain JWT Token

```javascript
/**
 * Authenticate with the API and obtain a JWT token
 * @param {string} apiKey - Your Zapier API key
 * @returns {Promise<string>} JWT access token
 */
async function getAccessToken(apiKey) {
  const baseUrl = 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws';

  try {
    const response = await fetch(`${baseUrl}/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        username: 'api',
        password: apiKey,
      }),
    });

    if (!response.ok) {
      throw new Error(`Authentication failed: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return data.access_token;
  } catch (error) {
    console.error('Authentication error:', error.message);
    throw error;
  }
}

// Usage
const token = await getAccessToken(process.env.ZAPIER_API_KEY);
console.log('Token obtained:', token.substring(0, 20) + '...');
```

### Python - Obtain JWT Token

```python
import requests
from typing import Optional


def get_access_token(api_key: str) -> str:
    """
    Authenticate with the API and obtain a JWT token.

    Args:
        api_key: Your Zapier API key

    Returns:
        JWT access token valid for 24 hours

    Raises:
        requests.HTTPError: If authentication fails
    """
    base_url = 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws'

    try:
        response = requests.post(
            f'{base_url}/token',
            data={
                'username': 'api',
                'password': api_key,
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
            }
        )
        response.raise_for_status()

        data = response.json()
        return data['access_token']

    except requests.HTTPError as e:
        print(f'Authentication failed: {e.response.status_code} {e.response.reason}')
        raise


# Usage
import os
token = get_access_token(os.getenv('ZAPIER_API_KEY'))
print(f'Token obtained: {token[:20]}...')
```

---

## Creating Events

### Node.js - POST /events

```javascript
/**
 * Create a new event in the Zapier Triggers API
 * @param {string} token - JWT access token
 * @param {object} event - Event data
 * @returns {Promise<object>} Created event response
 */
async function createEvent(token, event) {
  const baseUrl = 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws';

  try {
    const response = await fetch(`${baseUrl}/events`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(event),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`Failed to create event: ${response.status} - ${JSON.stringify(errorData)}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Event creation error:', error.message);
    throw error;
  }
}

// Usage
const event = {
  type: 'user.created',
  source: 'web-app',
  payload: {
    user_id: '12345',
    email: 'user@example.com',
    name: 'John Doe',
    created_at: new Date().toISOString(),
  },
};

const result = await createEvent(token, event);
console.log('Event created:', result);
// Output: { id: '550e8400-e29b-41d4-a716-446655440000', status: 'pending', timestamp: '2024-01-15T10:30:00Z' }
```

### Python - POST /events

```python
from typing import Dict, Any
from datetime import datetime


def create_event(token: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new event in the Zapier Triggers API.

    Args:
        token: JWT access token
        event: Event data with type, source, and payload

    Returns:
        Created event response with id, status, and timestamp

    Raises:
        requests.HTTPError: If event creation fails
    """
    base_url = 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws'

    try:
        response = requests.post(
            f'{base_url}/events',
            json=event,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            }
        )
        response.raise_for_status()

        return response.json()

    except requests.HTTPError as e:
        print(f'Event creation failed: {e.response.status_code} - {e.response.text}')
        raise


# Usage
event = {
    'type': 'user.created',
    'source': 'web-app',
    'payload': {
        'user_id': '12345',
        'email': 'user@example.com',
        'name': 'John Doe',
        'created_at': datetime.utcnow().isoformat(),
    }
}

result = create_event(token, event)
print(f'Event created: {result}')
# Output: {'id': '550e8400-e29b-41d4-a716-446655440000', 'status': 'pending', 'timestamp': '2024-01-15T10:30:00Z'}
```

---

## Retrieving Events (Inbox)

### Node.js - GET /inbox

```javascript
/**
 * Retrieve pending events from the inbox
 * @param {string} token - JWT access token
 * @returns {Promise<Array>} Array of pending events
 */
async function getInbox(token) {
  const baseUrl = 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws';

  try {
    const response = await fetch(`${baseUrl}/inbox`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to retrieve inbox: ${response.status} ${response.statusText}`);
    }

    const events = await response.json();
    return events;
  } catch (error) {
    console.error('Inbox retrieval error:', error.message);
    throw error;
  }
}

// Usage
const pendingEvents = await getInbox(token);
console.log(`Found ${pendingEvents.length} pending events`);

pendingEvents.forEach(event => {
  console.log(`- Event ${event.id}: ${event.type} from ${event.source}`);
});

// Example output:
// Found 3 pending events
// - Event 550e8400-e29b-41d4-a716-446655440000: user.created from web-app
// - Event 550e8400-e29b-41d4-a716-446655440001: order.placed from shopify
// - Event 550e8400-e29b-41d4-a716-446655440002: lead.captured from salesforce
```

### Python - GET /inbox

```python
from typing import List


def get_inbox(token: str) -> List[Dict[str, Any]]:
    """
    Retrieve pending events from the inbox.

    Args:
        token: JWT access token

    Returns:
        List of pending events (max 100)

    Raises:
        requests.HTTPError: If retrieval fails
    """
    base_url = 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws'

    try:
        response = requests.get(
            f'{base_url}/inbox',
            headers={
                'Authorization': f'Bearer {token}',
            }
        )
        response.raise_for_status()

        return response.json()

    except requests.HTTPError as e:
        print(f'Inbox retrieval failed: {e.response.status_code} {e.response.reason}')
        raise


# Usage
pending_events = get_inbox(token)
print(f'Found {len(pending_events)} pending events')

for event in pending_events:
    print(f'- Event {event["id"]}: {event["type"]} from {event["source"]}')

# Example output:
# Found 3 pending events
# - Event 550e8400-e29b-41d4-a716-446655440000: user.created from web-app
# - Event 550e8400-e29b-41d4-a716-446655440001: order.placed from shopify
# - Event 550e8400-e29b-41d4-a716-446655440002: lead.captured from salesforce
```

---

## Acknowledging Events

### Node.js - POST /inbox/{id}/ack

```javascript
/**
 * Acknowledge successful event processing
 * @param {string} token - JWT access token
 * @param {string} eventId - Event ID to acknowledge
 * @returns {Promise<object>} Acknowledgment response
 */
async function acknowledgeEvent(token, eventId) {
  const baseUrl = 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws';

  try {
    const response = await fetch(`${baseUrl}/inbox/${eventId}/ack`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Event not found: ${eventId}`);
      }
      throw new Error(`Failed to acknowledge event: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Event acknowledgment error:', error.message);
    throw error;
  }
}

// Usage
const eventId = '550e8400-e29b-41d4-a716-446655440000';
const ackResult = await acknowledgeEvent(token, eventId);
console.log('Event acknowledged:', ackResult);
// Output: { id: '550e8400-e29b-41d4-a716-446655440000', status: 'delivered', message: 'Event acknowledged successfully', updated_at: '2024-01-15T10:35:00Z' }
```

### Python - POST /inbox/{id}/ack

```python
def acknowledge_event(token: str, event_id: str) -> Dict[str, Any]:
    """
    Acknowledge successful event processing.

    Args:
        token: JWT access token
        event_id: Event ID to acknowledge

    Returns:
        Acknowledgment response with updated status

    Raises:
        requests.HTTPError: If acknowledgment fails
    """
    base_url = 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws'

    try:
        response = requests.post(
            f'{base_url}/inbox/{event_id}/ack',
            headers={
                'Authorization': f'Bearer {token}',
            }
        )
        response.raise_for_status()

        return response.json()

    except requests.HTTPError as e:
        if e.response.status_code == 404:
            print(f'Event not found: {event_id}')
        else:
            print(f'Acknowledgment failed: {e.response.status_code} {e.response.reason}')
        raise


# Usage
event_id = '550e8400-e29b-41d4-a716-446655440000'
ack_result = acknowledge_event(token, event_id)
print(f'Event acknowledged: {ack_result}')
# Output: {'id': '550e8400-e29b-41d4-a716-446655440000', 'status': 'delivered', 'message': 'Event acknowledged successfully', 'updated_at': '2024-01-15T10:35:00Z'}
```

---

## Complete End-to-End Examples

### Node.js - Complete Workflow

```javascript
import fetch from 'node-fetch';

class ZapierTriggersClient {
  constructor(apiKey, baseUrl = 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws') {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl;
    this.token = null;
    this.tokenExpiry = null;
  }

  /**
   * Ensure we have a valid token, refreshing if needed
   */
  async ensureAuthenticated() {
    if (!this.token || this.tokenExpiry < Date.now()) {
      await this.authenticate();
    }
  }

  /**
   * Authenticate and obtain JWT token
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
        throw new Error(`Authentication failed: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      this.token = data.access_token;
      // Token is valid for 24 hours, refresh 1 hour before expiry
      this.tokenExpiry = Date.now() + (23 * 60 * 60 * 1000);
    } catch (error) {
      console.error('Authentication error:', error.message);
      throw error;
    }
  }

  /**
   * Create a new event
   */
  async createEvent(type, source, payload) {
    await this.ensureAuthenticated();

    try {
      const response = await fetch(`${this.baseUrl}/events`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ type, source, payload }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`Failed to create event: ${response.status} - ${JSON.stringify(errorData)}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Event creation error:', error.message);
      throw error;
    }
  }

  /**
   * Get pending events from inbox
   */
  async getInbox() {
    await this.ensureAuthenticated();

    try {
      const response = await fetch(`${this.baseUrl}/inbox`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to retrieve inbox: ${response.status} ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Inbox retrieval error:', error.message);
      throw error;
    }
  }

  /**
   * Acknowledge event delivery
   */
  async acknowledgeEvent(eventId) {
    await this.ensureAuthenticated();

    try {
      const response = await fetch(`${this.baseUrl}/inbox/${eventId}/ack`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error(`Event not found: ${eventId}`);
        }
        throw new Error(`Failed to acknowledge event: ${response.status} ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Event acknowledgment error:', error.message);
      throw error;
    }
  }

  /**
   * Process all pending events with a callback function
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
        results.push({ eventId: event.id, status: 'failed', error: error.message });
        console.error(`✗ Failed to process event ${event.id}:`, error.message);
      }
    }

    return results;
  }
}

// Usage Example
async function main() {
  const client = new ZapierTriggersClient(process.env.ZAPIER_API_KEY);

  try {
    // 1. Create an event
    console.log('Creating event...');
    const event = await client.createEvent(
      'user.created',
      'web-app',
      {
        user_id: '12345',
        email: 'john.doe@example.com',
        name: 'John Doe',
        created_at: new Date().toISOString(),
      }
    );
    console.log('Event created:', event);

    // 2. Retrieve pending events
    console.log('\nRetrieving pending events...');
    const pendingEvents = await client.getInbox();
    console.log(`Found ${pendingEvents.length} pending events`);

    // 3. Process events
    console.log('\nProcessing events...');
    const results = await client.processInbox(async (event) => {
      // Your event processing logic here
      console.log(`Processing event ${event.id}: ${event.type}`);
      // Simulate processing
      await new Promise(resolve => setTimeout(resolve, 100));
    });

    console.log('\nProcessing results:', results);
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

// Run if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export default ZapierTriggersClient;
```

### Python - Complete Workflow

```python
import os
import time
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime, timedelta
import requests


class ZapierTriggersClient:
    """
    Client for interacting with the Zapier Triggers API.

    Features:
    - Automatic token management and refresh
    - Comprehensive error handling
    - Event creation, retrieval, and acknowledgment
    - Batch event processing

    Example:
        client = ZapierTriggersClient(api_key=os.getenv('ZAPIER_API_KEY'))

        # Create an event
        event = client.create_event(
            type='user.created',
            source='web-app',
            payload={'user_id': '12345', 'email': 'user@example.com'}
        )

        # Process pending events
        client.process_inbox(lambda e: print(f"Processing {e['id']}"))
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws'
    ):
        """
        Initialize the Zapier Triggers API client.

        Args:
            api_key: Your Zapier API key
            base_url: API base URL (default: production endpoint)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None

    def _ensure_authenticated(self) -> None:
        """Ensure we have a valid token, refreshing if needed."""
        if not self.token or not self.token_expiry or self.token_expiry < datetime.utcnow():
            self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate and obtain JWT token."""
        try:
            response = requests.post(
                f'{self.base_url}/token',
                data={
                    'username': 'api',
                    'password': self.api_key,
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            )
            response.raise_for_status()

            data = response.json()
            self.token = data['access_token']
            # Token is valid for 24 hours, refresh 1 hour before expiry
            self.token_expiry = datetime.utcnow() + timedelta(hours=23)

        except requests.HTTPError as e:
            print(f'Authentication failed: {e.response.status_code} {e.response.reason}')
            raise

    def create_event(self, type: str, source: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new event in the system.

        Args:
            type: Event type identifier (e.g., 'user.created', 'order.placed')
            source: Event source system (e.g., 'web-app', 'shopify')
            payload: Event data as dictionary

        Returns:
            Created event response with id, status, and timestamp

        Raises:
            requests.HTTPError: If event creation fails
        """
        self._ensure_authenticated()

        try:
            response = requests.post(
                f'{self.base_url}/events',
                json={
                    'type': type,
                    'source': source,
                    'payload': payload,
                },
                headers={
                    'Authorization': f'Bearer {self.token}',
                    'Content-Type': 'application/json',
                }
            )
            response.raise_for_status()

            return response.json()

        except requests.HTTPError as e:
            print(f'Event creation failed: {e.response.status_code} - {e.response.text}')
            raise

    def get_inbox(self) -> List[Dict[str, Any]]:
        """
        Retrieve pending events from the inbox.

        Returns:
            List of pending events (max 100)

        Raises:
            requests.HTTPError: If retrieval fails
        """
        self._ensure_authenticated()

        try:
            response = requests.get(
                f'{self.base_url}/inbox',
                headers={
                    'Authorization': f'Bearer {self.token}',
                }
            )
            response.raise_for_status()

            return response.json()

        except requests.HTTPError as e:
            print(f'Inbox retrieval failed: {e.response.status_code} {e.response.reason}')
            raise

    def acknowledge_event(self, event_id: str) -> Dict[str, Any]:
        """
        Acknowledge successful event processing.

        Args:
            event_id: Event ID to acknowledge

        Returns:
            Acknowledgment response with updated status

        Raises:
            requests.HTTPError: If acknowledgment fails
        """
        self._ensure_authenticated()

        try:
            response = requests.post(
                f'{self.base_url}/inbox/{event_id}/ack',
                headers={
                    'Authorization': f'Bearer {self.token}',
                }
            )
            response.raise_for_status()

            return response.json()

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                print(f'Event not found: {event_id}')
            else:
                print(f'Acknowledgment failed: {e.response.status_code} {e.response.reason}')
            raise

    def process_inbox(self, callback: Callable[[Dict[str, Any]], None]) -> List[Dict[str, Any]]:
        """
        Process all pending events with a callback function.

        Args:
            callback: Function to process each event. Should raise exception on failure.

        Returns:
            List of processing results with eventId and status

        Example:
            def process_event(event):
                print(f"Processing {event['id']}: {event['type']}")
                # Your processing logic here

            results = client.process_inbox(process_event)
        """
        events = self.get_inbox()
        print(f'Processing {len(events)} pending events...')

        results = []
        for event in events:
            try:
                # Process event with callback
                callback(event)

                # Acknowledge successful processing
                self.acknowledge_event(event['id'])
                results.append({'event_id': event['id'], 'status': 'success'})
                print(f"✓ Processed and acknowledged event {event['id']}")

            except Exception as e:
                results.append({
                    'event_id': event['id'],
                    'status': 'failed',
                    'error': str(e)
                })
                print(f"✗ Failed to process event {event['id']}: {e}")

        return results


# Usage Example
def main():
    """Example usage of the Zapier Triggers API client."""
    client = ZapierTriggersClient(api_key=os.getenv('ZAPIER_API_KEY'))

    try:
        # 1. Create an event
        print('Creating event...')
        event = client.create_event(
            type='user.created',
            source='web-app',
            payload={
                'user_id': '12345',
                'email': 'john.doe@example.com',
                'name': 'John Doe',
                'created_at': datetime.utcnow().isoformat(),
            }
        )
        print(f'Event created: {event}')

        # 2. Retrieve pending events
        print('\nRetrieving pending events...')
        pending_events = client.get_inbox()
        print(f'Found {len(pending_events)} pending events')

        # 3. Process events
        print('\nProcessing events...')
        def process_event(event: Dict[str, Any]) -> None:
            """Process a single event."""
            print(f"Processing event {event['id']}: {event['type']}")
            # Simulate processing
            time.sleep(0.1)
            # Your processing logic here

        results = client.process_inbox(process_event)

        print('\nProcessing results:', results)

    except Exception as e:
        print(f'Error: {e}')
        exit(1)


if __name__ == '__main__':
    main()
```

---

## Error Handling

### Common Error Scenarios

#### 1. Authentication Errors (401)

**Node.js:**
```javascript
try {
  const token = await getAccessToken(apiKey);
} catch (error) {
  if (error.message.includes('401')) {
    console.error('Invalid API key. Please check your credentials.');
  }
  throw error;
}
```

**Python:**
```python
try:
    token = get_access_token(api_key)
except requests.HTTPError as e:
    if e.response.status_code == 401:
        print('Invalid API key. Please check your credentials.')
    raise
```

#### 2. Event Not Found (404)

**Node.js:**
```javascript
try {
  await acknowledgeEvent(token, eventId);
} catch (error) {
  if (error.message.includes('404')) {
    console.warn(`Event ${eventId} not found - may have been already acknowledged`);
  }
}
```

**Python:**
```python
try:
    acknowledge_event(token, event_id)
except requests.HTTPError as e:
    if e.response.status_code == 404:
        print(f'Event {event_id} not found - may have been already acknowledged')
```

#### 3. Token Expiration

Both client implementations include automatic token refresh. The token is refreshed 1 hour before expiry (23 hours after issuance) to prevent request failures.

#### 4. Network Errors

**Node.js:**
```javascript
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // 1 second

async function createEventWithRetry(token, event, retries = MAX_RETRIES) {
  try {
    return await createEvent(token, event);
  } catch (error) {
    if (retries > 0 && error.message.includes('ECONNREFUSED')) {
      console.log(`Retrying... (${MAX_RETRIES - retries + 1}/${MAX_RETRIES})`);
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
      return createEventWithRetry(token, event, retries - 1);
    }
    throw error;
  }
}
```

**Python:**
```python
import time
from typing import Dict, Any

MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

def create_event_with_retry(token: str, event: Dict[str, Any], retries: int = MAX_RETRIES) -> Dict[str, Any]:
    """Create event with automatic retry on network errors."""
    try:
        return create_event(token, event)
    except requests.ConnectionError as e:
        if retries > 0:
            print(f'Retrying... ({MAX_RETRIES - retries + 1}/{MAX_RETRIES})')
            time.sleep(RETRY_DELAY)
            return create_event_with_retry(token, event, retries - 1)
        raise
```

---

## Best Practices

### 1. Token Management

- Cache tokens for their full 24-hour lifetime
- Implement automatic token refresh before expiry
- Store tokens securely (never in version control)

### 2. Error Handling

- Always handle network errors with retries
- Log error details for debugging
- Implement graceful degradation

### 3. Event Processing

- Acknowledge events only after successful processing
- Implement idempotency in your event handlers
- Use batch processing for multiple events

### 4. Security

- Store API keys in environment variables
- Use HTTPS for all requests (enforced by API)
- Rotate API keys regularly

### 5. Rate Limiting

- The API does not currently enforce rate limits
- Implement client-side throttling for production use
- Monitor CloudWatch metrics for performance

### 6. Monitoring

- Log all API interactions
- Track success/failure rates
- Monitor token refresh patterns
- Alert on repeated failures

### Example Monitoring Setup (Node.js)

```javascript
class MonitoredZapierClient extends ZapierTriggersClient {
  constructor(apiKey, baseUrl, logger) {
    super(apiKey, baseUrl);
    this.logger = logger;
    this.metrics = {
      requests: 0,
      successes: 0,
      failures: 0,
    };
  }

  async createEvent(type, source, payload) {
    this.metrics.requests++;
    try {
      const result = await super.createEvent(type, source, payload);
      this.metrics.successes++;
      this.logger.info('Event created', { eventId: result.id, type });
      return result;
    } catch (error) {
      this.metrics.failures++;
      this.logger.error('Event creation failed', { error: error.message, type });
      throw error;
    }
  }

  getMetrics() {
    return {
      ...this.metrics,
      successRate: this.metrics.requests > 0
        ? (this.metrics.successes / this.metrics.requests) * 100
        : 0,
    };
  }
}
```

---

## Additional Resources

- **OpenAPI Documentation:** https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws/docs
- **API Specification (JSON):** https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws/openapi.json
- **ReDoc Documentation:** https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws/redoc
- **Full Examples:** See `/examples/nodejs/` and `/examples/python/` directories

---

## Support

For issues or questions:
- Check the OpenAPI documentation
- Review error messages in CloudWatch Logs
- Verify API key configuration in AWS Secrets Manager
- Contact API Support: support@example.com
