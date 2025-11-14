"""
Unit tests for the Event Dispatcher Lambda function
Tests event fetching, webhook delivery, retry logic, and acknowledgment
"""
import json
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

# Import the main module
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main


@pytest.fixture
def mock_secrets():
    """Mock secrets from AWS Secrets Manager"""
    return {
        'zapier_api_key': 'test-api-key-12345',
        'zapier_webhook_url': 'https://hooks.zapier.com/test-webhook',
        'jwt_secret': 'test-jwt-secret'
    }


@pytest.fixture
def mock_jwt_token():
    """Mock JWT token"""
    return 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.token'


@pytest.fixture
def sample_events():
    """Sample events from the inbox"""
    return [
        {
            'id': '550e8400-e29b-41d4-a716-446655440000',
            'type': 'user.created',
            'source': 'web-app',
            'payload': {'user_id': '12345', 'email': 'test@example.com'},
            'status': 'pending',
            'created_at': '2024-01-15T10:30:00Z',
            'updated_at': '2024-01-15T10:30:00Z'
        },
        {
            'id': '550e8400-e29b-41d4-a716-446655440001',
            'type': 'order.placed',
            'source': 'shopify',
            'payload': {'order_id': '67890', 'total': 99.99},
            'status': 'pending',
            'created_at': '2024-01-15T10:31:00Z',
            'updated_at': '2024-01-15T10:31:00Z'
        }
    ]


@pytest.fixture
def mock_environment(monkeypatch):
    """Set up environment variables"""
    monkeypatch.setenv('API_BASE_URL', 'https://test-api.example.com')
    monkeypatch.setenv('SECRET_ARN', 'arn:aws:secretsmanager:us-east-2:123456789012:secret:test-secret')
    monkeypatch.setenv('DYNAMODB_TABLE_NAME', 'test-events-table')
    monkeypatch.setenv('AWS_REGION', 'us-east-2')
    monkeypatch.setenv('MAX_EVENTS_PER_RUN', '100')


class TestSecretRetrieval:
    """Test secret retrieval from AWS Secrets Manager"""

    @patch('main.secrets_client')
    def test_get_secret_success(self, mock_secrets_client, mock_secrets):
        """Test successful secret retrieval"""
        # Clear cache
        main._secrets_cache.clear()

        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': json.dumps(mock_secrets)
        }

        result = main.get_secret('test-secret-arn')

        assert result == mock_secrets
        assert 'test-secret-arn' in main._secrets_cache
        mock_secrets_client.get_secret_value.assert_called_once_with(SecretId='test-secret-arn')

    @patch('main.secrets_client')
    def test_get_secret_cached(self, mock_secrets_client, mock_secrets):
        """Test that secrets are cached on subsequent calls"""
        main._secrets_cache['test-secret-arn'] = mock_secrets

        result = main.get_secret('test-secret-arn')

        assert result == mock_secrets
        mock_secrets_client.get_secret_value.assert_not_called()

    @patch('main.secrets_client')
    def test_get_secret_not_found(self, mock_secrets_client):
        """Test handling of non-existent secret"""
        main._secrets_cache.clear()

        from botocore.exceptions import ClientError
        mock_secrets_client.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException'}},
            'GetSecretValue'
        )

        with pytest.raises(Exception, match='ResourceNotFoundException'):
            main.get_secret('nonexistent-secret')


class TestAuthentication:
    """Test JWT token authentication"""

    @patch('main.get_secret')
    @patch('httpx.Client')
    def test_get_jwt_token_success(self, mock_client, mock_get_secret, mock_secrets, mock_jwt_token):
        """Test successful JWT token retrieval"""
        mock_get_secret.return_value = mock_secrets

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'access_token': mock_jwt_token, 'token_type': 'bearer'}

        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        token = main.get_jwt_token()

        assert token == mock_jwt_token
        mock_client_instance.post.assert_called_once()

    @patch('main.get_secret')
    @patch('httpx.Client')
    def test_get_jwt_token_auth_failure(self, mock_client, mock_get_secret, mock_secrets):
        """Test handling of authentication failure"""
        mock_get_secret.return_value = mock_secrets

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'

        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_client_instance

        with pytest.raises(Exception, match='Authentication failed'):
            main.get_jwt_token()


class TestEventFetching:
    """Test event fetching from inbox"""

    @pytest.mark.asyncio
    async def test_fetch_pending_events_success(self, sample_events, mock_jwt_token):
        """Test successful event fetching"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_events

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            events = await main.fetch_pending_events(mock_jwt_token)

            assert len(events) == 2
            assert events[0]['id'] == '550e8400-e29b-41d4-a716-446655440000'
            mock_client_instance.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_pending_events_empty(self, mock_jwt_token):
        """Test fetching when no events are pending"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = []

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            events = await main.fetch_pending_events(mock_jwt_token)

            assert events == []

    @pytest.mark.asyncio
    async def test_fetch_pending_events_error(self, mock_jwt_token):
        """Test handling of fetch error"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = 'Internal Server Error'

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            with pytest.raises(Exception, match='Failed to fetch inbox'):
                await main.fetch_pending_events(mock_jwt_token)


class TestEventDelivery:
    """Test event delivery with retry logic"""

    @pytest.mark.asyncio
    async def test_deliver_event_success_first_attempt(self, sample_events):
        """Test successful delivery on first attempt"""
        event = sample_events[0]
        webhook_url = 'https://hooks.zapier.com/test'

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.150

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await main.deliver_event_with_retry(event, webhook_url, max_retries=3)

            assert result['success'] is True
            assert result['attempts'] == 1
            assert result['status_code'] == 200
            assert 'response_time_ms' in result
            mock_client_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_deliver_event_retry_then_success(self, sample_events):
        """Test delivery with retry and eventual success"""
        event = sample_events[0]
        webhook_url = 'https://hooks.zapier.com/test'

        with patch('httpx.AsyncClient') as mock_client:
            # First attempt fails, second succeeds
            mock_response_fail = Mock()
            mock_response_fail.status_code = 500

            mock_response_success = Mock()
            mock_response_success.status_code = 200
            mock_response_success.elapsed.total_seconds.return_value = 0.200

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(
                side_effect=[mock_response_fail, mock_response_success]
            )
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await main.deliver_event_with_retry(event, webhook_url, max_retries=3)

            assert result['success'] is True
            assert result['attempts'] == 2
            assert mock_client_instance.post.call_count == 2

    @pytest.mark.asyncio
    async def test_deliver_event_non_retryable_error(self, sample_events):
        """Test handling of non-retryable error (4xx)"""
        event = sample_events[0]
        webhook_url = 'https://hooks.zapier.com/test'

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 400  # Bad request - non-retryable

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await main.deliver_event_with_retry(event, webhook_url, max_retries=3)

            assert result['success'] is False
            assert result['retryable'] is False
            assert result['attempts'] == 1
            mock_client_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_deliver_event_max_retries_exhausted(self, sample_events):
        """Test when all retry attempts are exhausted"""
        event = sample_events[0]
        webhook_url = 'https://hooks.zapier.com/test'

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 503  # Service unavailable - retryable

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await main.deliver_event_with_retry(event, webhook_url, max_retries=3)

            assert result['success'] is False
            assert result['retryable'] is True
            assert result['attempts'] == 3
            assert mock_client_instance.post.call_count == 3

    @pytest.mark.asyncio
    async def test_deliver_event_timeout(self, sample_events):
        """Test handling of timeout errors"""
        event = sample_events[0]
        webhook_url = 'https://hooks.zapier.com/test'

        import httpx

        with patch('httpx.AsyncClient') as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(side_effect=httpx.TimeoutException('Timeout'))
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await main.deliver_event_with_retry(event, webhook_url, max_retries=2)

            assert result['success'] is False
            assert 'Timeout' in result['error']
            assert result['attempts'] == 2


class TestEventAcknowledgment:
    """Test event acknowledgment"""

    @pytest.mark.asyncio
    async def test_acknowledge_event_success(self, mock_jwt_token):
        """Test successful event acknowledgment"""
        event_id = '550e8400-e29b-41d4-a716-446655440000'

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await main.acknowledge_event(event_id, mock_jwt_token)

            assert result is True
            mock_client_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_acknowledge_event_failure(self, mock_jwt_token):
        """Test handling of acknowledgment failure"""
        event_id = '550e8400-e29b-41d4-a716-446655440000'

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.text = 'Not Found'

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await main.acknowledge_event(event_id, mock_jwt_token)

            assert result is False


class TestMetricsPublishing:
    """Test CloudWatch metrics publishing"""

    @patch('main.cloudwatch_client')
    def test_publish_metrics_success(self, mock_cloudwatch_client):
        """Test successful metrics publishing"""
        metrics = {
            'total_events': 10,
            'successful_deliveries': 8,
            'failed_deliveries': 2,
            'avg_delivery_time_ms': 150.5,
            'total_retries': 3
        }

        main.publish_metrics(metrics)

        mock_cloudwatch_client.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch_client.put_metric_data.call_args
        assert call_args[1]['Namespace'] == 'ZapierTriggersAPI/Dispatcher'
        assert len(call_args[1]['MetricData']) == 5

    @patch('main.cloudwatch_client')
    def test_publish_metrics_empty(self, mock_cloudwatch_client):
        """Test publishing empty metrics"""
        metrics = {}

        main.publish_metrics(metrics)

        mock_cloudwatch_client.put_metric_data.assert_not_called()


class TestLambdaHandler:
    """Test Lambda handler function"""

    @patch('main.process_events')
    def test_handler_success(self, mock_process_events, mock_environment):
        """Test successful Lambda handler execution"""
        mock_process_events.return_value = {
            'total_events': 5,
            'successful_deliveries': 5,
            'failed_deliveries': 0,
            'processing_time_seconds': 2.5
        }

        # Mock asyncio.run to avoid actually running async code
        with patch('asyncio.run', return_value=mock_process_events.return_value):
            event = {}
            context = Mock()

            result = main.handler(event, context)

            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert body['total_events'] == 5
            assert body['successful_deliveries'] == 5

    @patch('main.process_events')
    def test_handler_error(self, mock_process_events, mock_environment):
        """Test Lambda handler error handling"""
        mock_process_events.side_effect = Exception('Processing failed')

        with patch('asyncio.run', side_effect=mock_process_events.side_effect):
            with patch('main.publish_metrics'):
                event = {}
                context = Mock()

                result = main.handler(event, context)

                assert result['statusCode'] == 500
                body = json.loads(result['body'])
                assert 'error' in body
                assert 'Processing failed' in body['error']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
