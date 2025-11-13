# Zapier Triggers API - Python Client

Production-ready Python client for the Zapier Triggers API with automatic token management, type hints, and comprehensive error handling.

## Installation

```bash
pip install -r requirements.txt
```

Or manually install dependencies:

```bash
pip install requests python-dotenv
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
ZAPIER_API_KEY=your-key-here python client.py
```

### As a Module

```python
from client import ZapierTriggersClient
import os

client = ZapierTriggersClient(api_key=os.getenv('ZAPIER_API_KEY'))

# Create an event
event = client.create_event(
    type='user.created',
    source='web-app',
    payload={
        'user_id': '12345',
        'email': 'user@example.com'
    }
)

# Get pending events
events = client.get_inbox()

# Process all events
def process_event(event):
    print(f"Processing: {event['id']}")
    # Your processing logic here

results = client.process_inbox(process_event)
```

### With python-dotenv

```python
from dotenv import load_dotenv
load_dotenv()  # Load .env file automatically

client = ZapierTriggersClient(api_key=os.getenv('ZAPIER_API_KEY'))
```

## API Reference

### Constructor

```python
client = ZapierTriggersClient(api_key: str, base_url: str = None)
```

**Parameters:**
- `api_key` (required): Your Zapier API key
- `base_url` (optional): API base URL (default: production endpoint)

### Methods

#### `create_event(type: str, source: str, payload: Dict[str, Any]) -> Dict[str, Any]`

Create a new event.

**Parameters:**
- `type`: Event type (e.g., 'user.created')
- `source`: Event source (e.g., 'web-app')
- `payload`: Event data as dictionary

**Returns:** Created event with id, status, timestamp

#### `get_inbox() -> List[Dict[str, Any]]`

Retrieve pending events.

**Returns:** List of pending events (max 100)

#### `acknowledge_event(event_id: str) -> Dict[str, Any]`

Acknowledge event delivery.

**Parameters:**
- `event_id`: Event ID to acknowledge

**Returns:** Acknowledgment response

#### `process_inbox(callback: Callable[[Dict[str, Any]], None]) -> List[Dict[str, Any]]`

Process all pending events with a callback.

**Parameters:**
- `callback`: Function to process each event

**Returns:** List of processing results

#### `health_check() -> Dict[str, Any]`

Check API health status.

**Returns:** Health status dictionary

## Error Handling

The client includes comprehensive error handling:

```python
import requests

try:
    client.create_event('user.created', 'web-app', {})
except requests.HTTPError as e:
    if e.response.status_code == 401:
        print('Invalid API key')
    elif e.response.status_code == 404:
        print('Event not found')
    else:
        print(f'Error: {e}')
```

## Type Hints

The client includes full type hints for better IDE support and type checking:

```python
from typing import Dict, Any

def my_processor(event: Dict[str, Any]) -> None:
    """Process an event with type hints."""
    event_id: str = event['id']
    event_type: str = event['type']
    payload: Dict[str, Any] = event['payload']
```

## Features

- Automatic JWT token management and refresh
- Token caching for 23 hours (refreshes 1 hour before expiry)
- Comprehensive error handling with detailed messages
- Type hints for better IDE support
- Batch event processing
- Python 3.8+ compatibility

## Type Checking

Run mypy for static type checking:

```bash
mypy client.py --strict
```

## Requirements

- Python 3.8 or higher
- Active Zapier API key from AWS Secrets Manager

## Documentation

See the main [SDK Snippets documentation](../../docs/SDK_SNIPPETS.md) for more examples and best practices.
