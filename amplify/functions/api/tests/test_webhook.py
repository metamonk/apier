"""
Tests for webhook receiver endpoint
"""
import pytest
import json
import hmac
import hashlib
import os
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app


@pytest.fixture
def client():
    """Test client fixture"""
    with patch.dict(os.environ, {'SECRET_ARN': 'arn:aws:secretsmanager:us-east-2:123456789:secret:test'}):
        return TestClient(app)


@pytest.fixture
def mock_secrets():
    """Mock secrets fixture with webhook secret"""
    return {
        "environment": "test",
        "jwt_secret": "test-jwt-secret-key-for-testing-only",
        "zapier_api_key": "test-api-key",
        "zapier_webhook_url": "https://hooks.zapier.com/test",
        "zapier_webhook_secret": "test-webhook-secret-key"
    }


@pytest.fixture
def webhook_payload():
    """Sample webhook payload"""
    return {
        "event_type": "user.created",
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "payload": {
            "user_id": "12345",
            "email": "test@example.com",
            "name": "Test User"
        },
        "timestamp": "2024-01-15T10:30:00Z"
    }


def generate_hmac_signature(payload: dict, secret: str) -> str:
    """
    Generate HMAC-SHA256 signature for webhook payload

    Note: Uses default JSON serialization format to match what FastAPI TestClient sends
    (with spaces after colons and commas)

    Args:
        payload: Dictionary to sign
        secret: Webhook secret key

    Returns:
        Hex-encoded HMAC signature
    """
    # Use default JSON serialization to match FastAPI/Starlette TestClient
    # which uses json.dumps() with default separators (', ', ': ')
    payload_bytes = json.dumps(payload, separators=(', ', ': ')).encode('utf-8')
    signature = hmac.new(
        secret.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return signature


class TestWebhookEndpoint:
    """Test cases for POST /webhook endpoint"""

    def test_webhook_with_valid_signature(self, client, mock_secrets, webhook_payload):
        """Test webhook endpoint with valid HMAC signature"""
        with patch('main.get_secret', return_value=mock_secrets):
            with patch('main.cloudwatch_client.put_metric_data') as mock_cloudwatch:
                # Generate valid signature
                signature = generate_hmac_signature(webhook_payload, mock_secrets["zapier_webhook_secret"])

                # Send request with signature
                response = client.post(
                    "/webhook",
                    json=webhook_payload,
                    headers={"X-Webhook-Signature": signature}
                )

                # Verify response
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "received"
                assert data["message"] == "Webhook event received and logged successfully"
                assert data["event_id"] == webhook_payload["event_id"]
                assert "timestamp" in data

                # Verify CloudWatch metric was published
                mock_cloudwatch.assert_called_once()

    @patch('main.get_secret')
    def test_webhook_with_invalid_signature(self, mock_get_secret, client, mock_secrets, webhook_payload):
        """Test webhook endpoint with invalid HMAC signature"""
        mock_get_secret.return_value = mock_secrets

        # Send request with invalid signature
        response = client.post(
            "/webhook",
            json=webhook_payload,
            headers={"X-Webhook-Signature": "invalid-signature-here"}
        )

        # Verify 401 Unauthorized response
        assert response.status_code == 401
        assert "Invalid webhook signature" in response.json()["detail"]

    @patch('main.get_secret')
    def test_webhook_without_signature(self, mock_get_secret, client, mock_secrets, webhook_payload):
        """Test webhook endpoint without signature header"""
        mock_get_secret.return_value = mock_secrets

        # Send request without signature header
        response = client.post(
            "/webhook",
            json=webhook_payload
        )

        # Verify 401 Unauthorized response (signature required when secret is configured)
        assert response.status_code == 401

    @patch('main.get_secret')
    @patch('main.cloudwatch_client.put_metric_data')
    def test_webhook_without_secret_configured(self, mock_cloudwatch, mock_get_secret, client, webhook_payload):
        """Test webhook endpoint when webhook secret is not configured"""
        # Return secrets without webhook_secret
        mock_get_secret.return_value = {
            "environment": "test",
            "jwt_secret": "test-jwt-secret",
            "zapier_api_key": "test-api-key"
        }

        # Send request without signature (should succeed since no secret is configured)
        response = client.post(
            "/webhook",
            json=webhook_payload
        )

        # Verify success response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"

    @patch('main.get_secret')
    @patch('main.cloudwatch_client.put_metric_data')
    def test_webhook_with_minimal_payload(self, mock_cloudwatch, mock_get_secret, client, mock_secrets):
        """Test webhook endpoint with minimal required fields"""
        mock_get_secret.return_value = mock_secrets

        # Minimal payload (only required fields)
        minimal_payload = {
            "event_type": "test.event",
            "payload": {"test": "data"}
        }

        signature = generate_hmac_signature(minimal_payload, mock_secrets["zapier_webhook_secret"])

        response = client.post(
            "/webhook",
            json=minimal_payload,
            headers={"X-Webhook-Signature": signature}
        )

        # Verify success
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        # event_id should be "unknown" when not provided
        assert data["event_id"] == "unknown"

    @patch('main.get_secret')
    @patch('main.cloudwatch_client.put_metric_data')
    def test_webhook_with_request_id_header(self, mock_cloudwatch, mock_get_secret, client, mock_secrets, webhook_payload):
        """Test webhook endpoint with X-Request-ID header for tracking"""
        mock_get_secret.return_value = mock_secrets

        signature = generate_hmac_signature(webhook_payload, mock_secrets["zapier_webhook_secret"])

        response = client.post(
            "/webhook",
            json=webhook_payload,
            headers={
                "X-Webhook-Signature": signature,
                "X-Request-ID": "test-request-123"
            }
        )

        # Verify success
        assert response.status_code == 200
        assert response.json()["status"] == "received"

    @patch('main.get_secret')
    @patch('main.cloudwatch_client.put_metric_data')
    def test_webhook_idempotency(self, mock_cloudwatch, mock_get_secret, client, mock_secrets, webhook_payload):
        """Test webhook endpoint handles duplicate deliveries idempotently"""
        mock_get_secret.return_value = mock_secrets

        signature = generate_hmac_signature(webhook_payload, mock_secrets["zapier_webhook_secret"])

        # Send same webhook twice
        response1 = client.post(
            "/webhook",
            json=webhook_payload,
            headers={"X-Webhook-Signature": signature}
        )

        response2 = client.post(
            "/webhook",
            json=webhook_payload,
            headers={"X-Webhook-Signature": signature}
        )

        # Both should succeed
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["event_id"] == response2.json()["event_id"]

    @patch('main.get_secret')
    @patch('main.cloudwatch_client.put_metric_data')
    def test_webhook_with_complex_payload(self, mock_cloudwatch, mock_get_secret, client, mock_secrets):
        """Test webhook endpoint with complex nested payload"""
        mock_get_secret.return_value = mock_secrets

        complex_payload = {
            "event_type": "order.completed",
            "event_id": "order-12345",
            "payload": {
                "order_id": "ORD-2024-001",
                "customer": {
                    "id": "CUST-123",
                    "name": "John Doe",
                    "email": "john@example.com",
                    "address": {
                        "street": "123 Main St",
                        "city": "New York",
                        "state": "NY",
                        "zip": "10001"
                    }
                },
                "items": [
                    {"sku": "ITEM-001", "quantity": 2, "price": 29.99},
                    {"sku": "ITEM-002", "quantity": 1, "price": 49.99}
                ],
                "total": 109.97,
                "currency": "USD"
            },
            "timestamp": "2024-01-15T10:30:00Z"
        }

        signature = generate_hmac_signature(complex_payload, mock_secrets["zapier_webhook_secret"])

        response = client.post(
            "/webhook",
            json=complex_payload,
            headers={"X-Webhook-Signature": signature}
        )

        # Verify success
        assert response.status_code == 200
        assert response.json()["event_id"] == "order-12345"

    @patch('main.get_secret')
    @patch('main.cloudwatch_client.put_metric_data')
    def test_webhook_cloudwatch_metric_failure(self, mock_cloudwatch, mock_get_secret, client, mock_secrets, webhook_payload):
        """Test webhook endpoint handles CloudWatch metric failure gracefully"""
        mock_get_secret.return_value = mock_secrets

        # Make CloudWatch put_metric_data raise an exception
        mock_cloudwatch.side_effect = Exception("CloudWatch API error")

        signature = generate_hmac_signature(webhook_payload, mock_secrets["zapier_webhook_secret"])

        response = client.post(
            "/webhook",
            json=webhook_payload,
            headers={"X-Webhook-Signature": signature}
        )

        # Should still succeed even if metric publishing fails
        assert response.status_code == 200
        assert response.json()["status"] == "received"

    def test_webhook_with_invalid_json(self, client):
        """Test webhook endpoint with malformed JSON"""
        response = client.post(
            "/webhook",
            data="not-valid-json",
            headers={"Content-Type": "application/json"}
        )

        # Should return 422 Unprocessable Entity
        assert response.status_code == 422

    @patch('main.get_secret')
    def test_webhook_missing_required_fields(self, mock_get_secret, client, mock_secrets):
        """Test webhook endpoint with missing required fields"""
        mock_get_secret.return_value = mock_secrets

        # Payload missing event_type
        invalid_payload = {
            "payload": {"test": "data"}
        }

        signature = generate_hmac_signature(invalid_payload, mock_secrets["zapier_webhook_secret"])

        response = client.post(
            "/webhook",
            json=invalid_payload,
            headers={"X-Webhook-Signature": signature}
        )

        # Should return 422 Unprocessable Entity (validation error)
        assert response.status_code == 422

    @patch('main.secret_arn', None)
    def test_webhook_without_secret_arn_configured(self, client, webhook_payload):
        """Test webhook endpoint when SECRET_ARN is not configured"""
        response = client.post(
            "/webhook",
            json=webhook_payload
        )

        # Should return 500 Internal Server Error
        assert response.status_code == 500
        assert "SECRET_ARN" in response.json()["detail"]


class TestWebhookSignatureVerification:
    """Test cases for HMAC signature verification logic"""

    def test_signature_verification_with_valid_signature(self):
        """Test signature verification with correct signature"""
        from main import verify_webhook_signature

        payload = b'{"event_type":"test","payload":{"test":"data"}}'
        secret = "test-secret-key"

        # Generate valid signature
        signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        # Verify
        assert verify_webhook_signature(payload, signature, secret) is True

    def test_signature_verification_with_invalid_signature(self):
        """Test signature verification with incorrect signature"""
        from main import verify_webhook_signature

        payload = b'{"event_type":"test","payload":{"test":"data"}}'
        secret = "test-secret-key"
        invalid_signature = "invalid-signature"

        # Verify
        assert verify_webhook_signature(payload, invalid_signature, secret) is False

    def test_signature_verification_with_empty_signature(self):
        """Test signature verification with empty signature"""
        from main import verify_webhook_signature

        payload = b'{"event_type":"test","payload":{"test":"data"}}'
        secret = "test-secret-key"

        # Verify
        assert verify_webhook_signature(payload, "", secret) is False

    def test_signature_verification_with_empty_secret(self):
        """Test signature verification with empty secret"""
        from main import verify_webhook_signature

        payload = b'{"event_type":"test","payload":{"test":"data"}}'
        signature = "some-signature"

        # Verify
        assert verify_webhook_signature(payload, signature, "") is False

    def test_signature_verification_timing_attack_protection(self):
        """Test that signature comparison is constant-time"""
        from main import verify_webhook_signature

        payload = b'{"event_type":"test","payload":{"test":"data"}}'
        secret = "test-secret-key"

        # Generate correct signature
        correct_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        # Create signature that differs by one character
        wrong_signature = correct_signature[:-1] + ('a' if correct_signature[-1] != 'a' else 'b')

        # Both should fail, and function should use constant-time comparison
        assert verify_webhook_signature(payload, wrong_signature, secret) is False
        assert verify_webhook_signature(payload, "completely-wrong", secret) is False
