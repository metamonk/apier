"""
Unit tests for Task 22.4 - CloudWatch Metrics and DynamoDB Updates
Tests DeliveryFailures, RetryCount metrics and delivery tracking field updates
"""
import json
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from datetime import datetime

# Set environment variables before importing main
import os
os.environ['API_BASE_URL'] = 'https://test-api.example.com'
os.environ['SECRET_ARN'] = 'arn:aws:secretsmanager:us-east-2:123456789012:secret:test-secret'
os.environ['DYNAMODB_TABLE_NAME'] = 'test-events-table'
os.environ['AWS_REGION'] = 'us-east-2'

# Import the main module
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main


@pytest.fixture
def mock_environment(monkeypatch):
    """Set up environment variables"""
    monkeypatch.setenv('API_BASE_URL', 'https://test-api.example.com')
    monkeypatch.setenv('SECRET_ARN', 'arn:aws:secretsmanager:us-east-2:123456789012:secret:test-secret')
    monkeypatch.setenv('DYNAMODB_TABLE_NAME', 'test-events-table')
    monkeypatch.setenv('AWS_REGION', 'us-east-2')


class TestDynamoDBFieldUpdates:
    """Test DynamoDB delivery tracking field updates (Task 22.4)"""

    @pytest.mark.asyncio
    @patch('main.table')
    async def test_update_event_delivery_status_success(self, mock_table):
        """Test updating DynamoDB fields on successful delivery"""
        event_id = 'test-event-123'
        created_at = '2024-01-15T10:30:00Z'
        attempts = 2

        await main.update_event_delivery_status(
            event_id=event_id,
            created_at=created_at,
            attempts=attempts,
            success=True
        )

        # Verify DynamoDB update was called with correct parameters
        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args

        # Check keys
        assert call_args[1]['Key'] == {
            'id': event_id,
            'created_at': created_at
        }

        # Check that attempts and last_delivery_attempt are updated
        assert ':attempts' in call_args[1]['ExpressionAttributeValues']
        assert call_args[1]['ExpressionAttributeValues'][':attempts'] == attempts
        assert ':last_attempt' in call_args[1]['ExpressionAttributeValues']

    @pytest.mark.asyncio
    @patch('main.table')
    async def test_update_event_delivery_status_failure(self, mock_table):
        """Test updating DynamoDB fields on failed delivery"""
        event_id = 'test-event-456'
        created_at = '2024-01-15T10:30:00Z'
        attempts = 3
        error_message = 'Connection timeout'

        await main.update_event_delivery_status(
            event_id=event_id,
            created_at=created_at,
            attempts=attempts,
            success=False,
            error_message=error_message
        )

        # Verify DynamoDB update was called
        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args

        # Check all failure fields are updated
        assert ':attempts' in call_args[1]['ExpressionAttributeValues']
        assert call_args[1]['ExpressionAttributeValues'][':attempts'] == attempts
        assert ':error' in call_args[1]['ExpressionAttributeValues']
        assert call_args[1]['ExpressionAttributeValues'][':error'] == error_message
        assert ':status' in call_args[1]['ExpressionAttributeValues']
        assert call_args[1]['ExpressionAttributeValues'][':status'] == 'failed'

    @pytest.mark.asyncio
    @patch('main.table')
    async def test_update_event_handles_exceptions(self, mock_table):
        """Test that update_event_delivery_status handles exceptions gracefully"""
        mock_table.update_item.side_effect = Exception("DynamoDB error")

        # Should not raise exception (graceful error handling)
        await main.update_event_delivery_status(
            event_id='test-event',
            created_at='2024-01-15T10:30:00Z',
            attempts=1,
            success=True
        )

        # Function should have attempted the update
        mock_table.update_item.assert_called_once()


class TestCloudWatchMetrics:
    """Test CloudWatch metrics publishing (Task 22.4)"""

    @patch('main.cloudwatch_client')
    def test_publish_delivery_failures_metric(self, mock_cloudwatch):
        """Test that DeliveryFailures metric is published"""
        metrics = {
            'failed_deliveries': 5
        }

        main.publish_metrics(metrics)

        # Verify CloudWatch was called
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args

        # Verify namespace
        assert call_args[1]['Namespace'] == 'ZapierTriggersAPI/Dispatcher'

        # Find DeliveryFailures metric
        metric_data = call_args[1]['MetricData']
        delivery_failures = [m for m in metric_data if m['MetricName'] == 'DeliveryFailures']

        assert len(delivery_failures) == 1
        assert delivery_failures[0]['Value'] == 5
        assert delivery_failures[0]['Unit'] == 'Count'

    @patch('main.cloudwatch_client')
    def test_publish_retry_count_metric(self, mock_cloudwatch):
        """Test that RetryCount metric is published"""
        metrics = {
            'total_retries': 12
        }

        main.publish_metrics(metrics)

        # Verify CloudWatch was called
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args

        # Find RetryCount metric
        metric_data = call_args[1]['MetricData']
        retry_count = [m for m in metric_data if m['MetricName'] == 'RetryCount']

        assert len(retry_count) == 1
        assert retry_count[0]['Value'] == 12
        assert retry_count[0]['Unit'] == 'Count'

    @patch('main.cloudwatch_client')
    def test_publish_all_dispatcher_metrics(self, mock_cloudwatch):
        """Test that all dispatcher metrics are published together"""
        metrics = {
            'total_events': 100,
            'successful_deliveries': 92,
            'failed_deliveries': 8,
            'total_retries': 15,
            'avg_delivery_time_ms': 234.5
        }

        main.publish_metrics(metrics)

        # Verify all expected metrics
        call_args = mock_cloudwatch.put_metric_data.call_args
        metric_data = call_args[1]['MetricData']

        metric_names = {m['MetricName'] for m in metric_data}
        expected_metrics = {
            'EventsProcessed',
            'SuccessfulDeliveries',
            'DeliveryFailures',
            'DispatcherDeliveryLatency',
            'RetryCount'
        }

        assert metric_names == expected_metrics

    @patch('main.cloudwatch_client')
    def test_publish_metrics_handles_exceptions(self, mock_cloudwatch):
        """Test that publish_metrics handles CloudWatch failures gracefully"""
        mock_cloudwatch.put_metric_data.side_effect = Exception("CloudWatch unavailable")

        metrics = {'total_events': 10}

        # Should not raise exception
        main.publish_metrics(metrics)

        # Should have attempted to publish
        mock_cloudwatch.put_metric_data.assert_called_once()


class TestProcessEventsIntegration:
    """Integration tests for process_events with Task 22.4 enhancements"""

    @pytest.mark.asyncio
    @patch('main.get_secret')
    @patch('main.get_jwt_token')
    @patch('main.fetch_pending_events')
    @patch('main.deliver_event_with_retry')
    @patch('main.update_event_delivery_status')
    @patch('main.acknowledge_event')
    @patch('main.publish_metrics')
    async def test_process_events_updates_dynamodb_fields(
        self,
        mock_publish,
        mock_ack,
        mock_update_status,
        mock_deliver,
        mock_fetch,
        mock_token,
        mock_secret
    ):
        """Test that process_events calls update_event_delivery_status for all events"""
        # Setup mocks
        mock_secret.return_value = {
            'zapier_webhook_url': 'https://hooks.zapier.com/test',
            'zapier_api_key': 'test-key'
        }
        mock_token.return_value = 'test-token'

        events = [
            {
                'id': 'event-1',
                'type': 'test.event',
                'created_at': '2024-01-15T10:30:00Z',
                'payload': {}
            },
            {
                'id': 'event-2',
                'type': 'test.event',
                'created_at': '2024-01-15T10:31:00Z',
                'payload': {}
            }
        ]
        mock_fetch.return_value = events

        # Mock delivery results (1 success, 1 failure)
        mock_deliver.side_effect = [
            {
                'success': True,
                'event_id': 'event-1',
                'attempts': 1,
                'status_code': 200,
                'response_time_ms': 150
            },
            {
                'success': False,
                'event_id': 'event-2',
                'attempts': 3,
                'error': 'Connection timeout',
                'retryable': True
            }
        ]

        mock_update_status.return_value = None
        mock_ack.return_value = True

        # Execute
        result = await main.process_events()

        # Verify update_event_delivery_status was called for both events
        assert mock_update_status.call_count == 2

        # Verify first call (successful delivery)
        first_call = mock_update_status.call_args_list[0]
        assert first_call[1]['event_id'] == 'event-1'
        assert first_call[1]['success'] is True
        assert first_call[1]['attempts'] == 1

        # Verify second call (failed delivery)
        second_call = mock_update_status.call_args_list[1]
        assert second_call[1]['event_id'] == 'event-2'
        assert second_call[1]['success'] is False
        assert second_call[1]['attempts'] == 3
        assert second_call[1]['error_message'] == 'Connection timeout'

    @pytest.mark.asyncio
    @patch('main.get_secret')
    @patch('main.get_jwt_token')
    @patch('main.fetch_pending_events')
    @patch('main.deliver_event_with_retry')
    @patch('main.update_event_delivery_status')
    @patch('main.acknowledge_event')
    @patch('main.publish_metrics')
    async def test_process_events_publishes_correct_metrics(
        self,
        mock_publish,
        mock_ack,
        mock_update_status,
        mock_deliver,
        mock_fetch,
        mock_token,
        mock_secret
    ):
        """Test that process_events publishes correct DeliveryFailures and RetryCount metrics"""
        # Setup mocks
        mock_secret.return_value = {
            'zapier_webhook_url': 'https://hooks.zapier.com/test',
            'zapier_api_key': 'test-key'
        }
        mock_token.return_value = 'test-token'

        events = [
            {'id': f'event-{i}', 'type': 'test', 'created_at': '2024-01-15T10:30:00Z', 'payload': {}}
            for i in range(10)
        ]
        mock_fetch.return_value = events

        # 7 successful (1 attempt each), 3 failed (3 attempts each)
        delivery_results = []
        for i in range(7):
            delivery_results.append({
                'success': True,
                'event_id': f'event-{i}',
                'attempts': 1,
                'response_time_ms': 200
            })
        for i in range(7, 10):
            delivery_results.append({
                'success': False,
                'event_id': f'event-{i}',
                'attempts': 3,
                'error': 'Timeout'
            })

        mock_deliver.side_effect = delivery_results
        mock_update_status.return_value = None
        mock_ack.return_value = True

        # Execute
        result = await main.process_events()

        # Verify metrics were published
        mock_publish.assert_called_once()
        published_metrics = mock_publish.call_args[0][0]

        # Check metrics
        assert published_metrics['total_events'] == 10
        assert published_metrics['successful_deliveries'] == 7
        assert published_metrics['failed_deliveries'] == 3
        # Total retries: 7 successful (0 retries each) + 3 failed (2 retries each) = 6
        assert published_metrics['total_retries'] == 6
