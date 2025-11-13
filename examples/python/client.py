"""
Zapier Triggers API - Python Client

A production-ready client for interacting with the Zapier Triggers API.

Features:
- Automatic JWT token management and refresh
- Comprehensive error handling
- Event creation, retrieval, and acknowledgment
- Batch event processing
- Type hints for better IDE support

Usage:
    from client import ZapierTriggersClient
    import os

    client = ZapierTriggersClient(api_key=os.getenv('ZAPIER_API_KEY'))
    event = client.create_event(
        type='user.created',
        source='web-app',
        payload={'user_id': '123'}
    )
"""

import os
import time
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime, timedelta
import requests


class ZapierTriggersClient:
    """
    Client for interacting with the Zapier Triggers API.

    Attributes:
        api_key: Your Zapier API key from AWS Secrets Manager
        base_url: API base URL (default: production endpoint)
        token: Current JWT access token
        token_expiry: Token expiration datetime

    Example:
        client = ZapierTriggersClient(api_key=os.getenv('ZAPIER_API_KEY'))

        # Create an event
        event = client.create_event(
            type='user.created',
            source='web-app',
            payload={'user_id': '12345', 'email': 'user@example.com'}
        )

        # Process pending events
        results = client.process_inbox(lambda e: print(f"Processing {e['id']}"))
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = 'https://ollzpcmoeaco4cpc773nyz7c5q0zumqi.lambda-url.us-east-2.on.aws'
    ):
        """
        Initialize the Zapier Triggers API client.

        Args:
            api_key: Your Zapier API key from AWS Secrets Manager
            base_url: API base URL (default: production endpoint)

        Raises:
            ValueError: If api_key is not provided
        """
        if not api_key:
            raise ValueError('API key is required')

        self.api_key = api_key
        self.base_url = base_url
        self.token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None

    def _ensure_authenticated(self) -> None:
        """
        Ensure we have a valid token, refreshing if needed.

        This method is called automatically before each API request.
        """
        if not self.token or not self.token_expiry or self.token_expiry < datetime.utcnow():
            self._authenticate()

    def _authenticate(self) -> None:
        """
        Authenticate with the API and obtain JWT token.

        Token is valid for 24 hours and automatically refreshed 1 hour before expiry.

        Raises:
            requests.HTTPError: If authentication fails
        """
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

            print('Successfully authenticated with Zapier Triggers API')

        except requests.HTTPError as e:
            error_msg = f'Authentication failed: {e.response.status_code} {e.response.reason}'
            print(error_msg)
            if e.response.text:
                print(f'Error details: {e.response.text}')
            raise

    def create_event(
        self,
        type: str,
        source: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new event in the Zapier Triggers API.

        Args:
            type: Event type identifier (e.g., 'user.created', 'order.placed')
            source: Event source system (e.g., 'web-app', 'shopify')
            payload: Event data as dictionary

        Returns:
            Created event response with id, status, and timestamp

        Raises:
            requests.HTTPError: If event creation fails

        Example:
            event = client.create_event(
                type='user.created',
                source='web-app',
                payload={
                    'user_id': '12345',
                    'email': 'user@example.com',
                    'name': 'John Doe'
                }
            )
            print(f"Event created: {event['id']}")
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
            error_msg = f'Event creation failed: {e.response.status_code} - {e.response.text}'
            print(error_msg)
            raise

    def get_inbox(self) -> List[Dict[str, Any]]:
        """
        Retrieve all pending events from the inbox.

        Returns:
            List of pending events (max 100), sorted by creation time (newest first)

        Raises:
            requests.HTTPError: If retrieval fails

        Example:
            events = client.get_inbox()
            print(f"Found {len(events)} pending events")
            for event in events:
                print(f"  - {event['id']}: {event['type']}")
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
            error_msg = f'Inbox retrieval failed: {e.response.status_code} {e.response.reason}'
            print(error_msg)
            raise

    def acknowledge_event(self, event_id: str) -> Dict[str, Any]:
        """
        Acknowledge successful event processing.

        After processing an event, call this method to mark it as delivered.
        The event will no longer appear in future inbox queries.

        Args:
            event_id: Event ID to acknowledge

        Returns:
            Acknowledgment response with updated status

        Raises:
            requests.HTTPError: If acknowledgment fails (e.g., event not found)

        Example:
            result = client.acknowledge_event('550e8400-e29b-41d4-a716-446655440000')
            print(f"Event acknowledged: {result['status']}")  # 'delivered'
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

    def process_inbox(
        self,
        callback: Callable[[Dict[str, Any]], None]
    ) -> List[Dict[str, Any]]:
        """
        Process all pending events with a callback function.

        Retrieves all pending events and processes each one with the provided callback.
        Automatically acknowledges events after successful processing.

        Args:
            callback: Function to process each event. Should raise exception on failure.

        Returns:
            List of processing results with event_id and status

        Example:
            def process_event(event):
                print(f"Processing {event['id']}: {event['type']}")
                # Your processing logic here
                # Raise exception if processing fails

            results = client.process_inbox(process_event)
            successful = len([r for r in results if r['status'] == 'success'])
            print(f"Successfully processed {successful} events")
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

                results.append({
                    'event_id': event['id'],
                    'status': 'success'
                })
                print(f"✓ Processed and acknowledged event {event['id']}")

            except Exception as e:
                results.append({
                    'event_id': event['id'],
                    'status': 'failed',
                    'error': str(e)
                })
                print(f"✗ Failed to process event {event['id']}: {e}")

        return results

    def health_check(self) -> Dict[str, Any]:
        """
        Check API health status.

        Returns:
            Health status dictionary

        Example:
            health = client.health_check()
            print(f"API status: {health['status']}")
        """
        try:
            response = requests.get(f'{self.base_url}/health')
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            print(f'Health check failed: {e.response.status_code} {e.response.reason}')
            raise


def main():
    """
    Example usage of the Zapier Triggers API client.

    Demonstrates:
    - Health check
    - Event creation
    - Retrieving pending events
    - Processing events with custom logic
    - Error handling
    """
    # Initialize client with API key from environment variable
    api_key = os.getenv('ZAPIER_API_KEY')

    if not api_key:
        print('Error: ZAPIER_API_KEY environment variable not set')
        print('Usage: ZAPIER_API_KEY=your-key-here python client.py')
        exit(1)

    client = ZapierTriggersClient(api_key=api_key)

    try:
        # 1. Health check
        print('\n1. Checking API health...')
        health = client.health_check()
        print(f'API status: {health}')

        # 2. Create a sample event
        print('\n2. Creating sample event...')
        event = client.create_event(
            type='user.created',
            source='web-app',
            payload={
                'user_id': '12345',
                'email': 'john.doe@example.com',
                'name': 'John Doe',
                'created_at': datetime.utcnow().isoformat(),
                'metadata': {
                    'signup_source': 'web',
                    'plan': 'premium',
                }
            }
        )
        print(f"Event created: {event['id']} (status: {event['status']})")

        # 3. Retrieve pending events
        print('\n3. Retrieving pending events...')
        pending_events = client.get_inbox()
        print(f'Found {len(pending_events)} pending events')

        if pending_events:
            print('\nPending events:')
            for idx, evt in enumerate(pending_events[:5], 1):
                print(f"  {idx}. {evt['id']} - {evt['type']} ({evt['source']}) - {evt['created_at']}")

            if len(pending_events) > 5:
                print(f'  ... and {len(pending_events) - 5} more')

        # 4. Process events with custom handler
        print('\n4. Processing events...')

        def process_event(event: Dict[str, Any]) -> None:
            """Process a single event."""
            print(f"  Processing event {event['id']}: {event['type']}")
            print(f"    Source: {event['source']}")
            print(f"    Payload: {event['payload']}")

            # Simulate processing time
            time.sleep(0.1)

            # Your custom event processing logic here
            # For example: send to webhook, store in database, trigger workflow, etc.
            # Raise exception if processing fails

        results = client.process_inbox(process_event)

        # 5. Display results
        print('\n5. Processing complete!')
        successful = len([r for r in results if r['status'] == 'success'])
        failed = len([r for r in results if r['status'] == 'failed'])

        print(f'  ✓ Successful: {successful}')
        print(f'  ✗ Failed: {failed}')

        if failed > 0:
            print('\nFailed events:')
            for result in results:
                if result['status'] == 'failed':
                    print(f"  - {result['event_id']}: {result['error']}")

    except Exception as e:
        print(f'\n❌ Error: {e}')
        exit(1)


if __name__ == '__main__':
    main()
