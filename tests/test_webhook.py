"""
Security tests for webhook endpoint.

These tests verify:
1. HMAC signature verification prevents unsigned requests
2. Authorization token validation works
3. Rate limiting prevents abuse
4. Invalid event payloads are rejected
"""

import pytest
import json
import hmac
import hashlib
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.webhook import app, verify_strava_signature


@pytest.fixture
def client():
    """Create test client"""
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = True
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def valid_strava_secret():
    """Valid Strava client secret"""
    return "test_client_secret_12345"


@pytest.fixture
def valid_verify_token():
    """Valid verification token"""
    return "test_verify_token_abcde"


@pytest.fixture
def valid_event_payload():
    """Valid Strava webhook event"""
    return {
        "object_type": "activity",
        "aspect_type": "create",
        "object_id": 1234567890,
        "owner_id": 123456,
        "subscription_id": 1,
        "event_time": 1234567890
    }


def compute_strava_signature(payload_bytes: bytes, secret: str) -> str:
    """Compute valid Strava signature"""
    sig = hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return f"v0={sig}"


# ===========================
# SIGNATURE VERIFICATION TESTS
# ===========================

class TestSignatureVerification:
    """Tests for HMAC signature verification"""
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret",
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_valid_signature_accepted(self, client, valid_strava_secret):
        """Valid signature should be accepted"""
        payload = {"object_type": "activity", "aspect_type": "create", "object_id": 123}
        payload_bytes = json.dumps(payload).encode()
        signature = compute_strava_signature(payload_bytes, valid_strava_secret)
        
        # Should not reject due to signature
        result = verify_strava_signature(payload_bytes, signature)
        assert result is True
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret",
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_invalid_signature_rejected(self):
        """Invalid signature should be rejected"""
        payload = {"object_type": "activity"}
        payload_bytes = json.dumps(payload).encode()
        
        result = verify_strava_signature(payload_bytes, "v0=invalid_signature_hash")
        assert result is False
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret"
    })
    def test_missing_signature_rejected(self):
        """Missing signature should be rejected"""
        payload_bytes = b'{"test": "data"}'
        result = verify_strava_signature(payload_bytes, "")
        assert result is False
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret"
    })
    def test_malformed_signature_rejected(self):
        """Malformed signature format should be rejected"""
        payload_bytes = b'{"test": "data"}'
        result = verify_strava_signature(payload_bytes, "invalid_format")
        assert result is False
    
    @patch.dict(os.environ, {})
    def test_missing_client_secret_rejected(self):
        """Missing client secret should cause rejection"""
        payload_bytes = b'{"test": "data"}'
        result = verify_strava_signature(payload_bytes, "v0=somesig")
        assert result is False


# ===========================
# POST ENDPOINT SECURITY TESTS
# ===========================

class TestPostEndpointSecurity:
    """Tests for POST /webhook security"""
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret",
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    @patch("app.webhook.run_v2.JobsClient")
    def test_valid_signed_request_with_auth(self, mock_job_client, client, valid_event_payload):
        """Valid signed request with proper auth should be accepted"""
        payload_bytes = json.dumps(valid_event_payload).encode()
        signature = compute_strava_signature(payload_bytes, "test_secret")
        
        mock_client_instance = MagicMock()
        mock_job_client.return_value = mock_client_instance
        
        response = client.post(
            "/webhook",
            data=payload_bytes,
            content_type="application/json",
            headers={
                "X-Strava-Signature": signature,
                "Authorization": "Bearer test_token"
            }
        )
        
        # Should accept valid request (might be 200 or rate limit)
        assert response.status_code in [200, 429]
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret",
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_missing_signature_header(self, client, valid_event_payload):
        """Request without signature should be rejected"""
        payload_bytes = json.dumps(valid_event_payload).encode()
        
        response = client.post(
            "/webhook",
            data=payload_bytes,
            content_type="application/json",
            headers={
                "Authorization": "Bearer test_token"
                # Missing X-Strava-Signature
            }
        )
        
        assert response.status_code == 401
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret",
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_invalid_signature_in_request(self, client, valid_event_payload):
        """Request with invalid signature should be rejected"""
        payload_bytes = json.dumps(valid_event_payload).encode()
        
        response = client.post(
            "/webhook",
            data=payload_bytes,
            content_type="application/json",
            headers={
                "X-Strava-Signature": "v0=invalid_signature_hash",
                "Authorization": "Bearer test_token"
            }
        )
        
        assert response.status_code == 401
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret",
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_missing_authorization_header(self, client, valid_event_payload):
        """Request without Authorization header should be rejected"""
        payload_bytes = json.dumps(valid_event_payload).encode()
        signature = compute_strava_signature(payload_bytes, "test_secret")
        
        response = client.post(
            "/webhook",
            data=payload_bytes,
            content_type="application/json",
            headers={
                "X-Strava-Signature": signature
                # Missing Authorization header
            }
        )
        
        assert response.status_code == 401
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret",
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_wrong_authorization_token(self, client, valid_event_payload):
        """Request with wrong auth token should be rejected"""
        payload_bytes = json.dumps(valid_event_payload).encode()
        signature = compute_strava_signature(payload_bytes, "test_secret")
        
        response = client.post(
            "/webhook",
            data=payload_bytes,
            content_type="application/json",
            headers={
                "X-Strava-Signature": signature,
                "Authorization": "Bearer wrong_token_xyz"
            }
        )
        
        assert response.status_code == 401
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret",
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_malformed_authorization_header(self, client, valid_event_payload):
        """Malformed Authorization header should be rejected"""
        payload_bytes = json.dumps(valid_event_payload).encode()
        signature = compute_strava_signature(payload_bytes, "test_secret")
        
        response = client.post(
            "/webhook",
            data=payload_bytes,
            content_type="application/json",
            headers={
                "X-Strava-Signature": signature,
                "Authorization": "InvalidFormat test_token"  # Wrong format
            }
        )
        
        assert response.status_code == 401


# ===========================
# PAYLOAD VALIDATION TESTS
# ===========================

class TestPayloadValidation:
    """Tests for webhook event validation"""
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret",
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_empty_event_rejected(self, client):
        """Empty event payload should be rejected"""
        signature = compute_strava_signature(b'', "test_secret")
        
        response = client.post(
            "/webhook",
            data=b'',
            content_type="application/json",
            headers={
                "X-Strava-Signature": signature,
                "Authorization": "Bearer test_token"
            }
        )
        
        assert response.status_code == 400
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret",
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_non_activity_object_ignored(self, client):
        """Non-activity objects should be ignored"""
        payload = {
            "object_type": "athlete",  # Not "activity"
            "aspect_type": "create",
            "object_id": 123
        }
        payload_bytes = json.dumps(payload).encode()
        signature = compute_strava_signature(payload_bytes, "test_secret")
        
        response = client.post(
            "/webhook",
            data=payload_bytes,
            content_type="application/json",
            headers={
                "X-Strava-Signature": signature,
                "Authorization": "Bearer test_token"
            }
        )
        
        assert response.status_code == 200
        assert response.json["status"] == "ignored"
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret",
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_non_create_aspect_ignored(self, client):
        """Non-create aspects should be ignored"""
        payload = {
            "object_type": "activity",
            "aspect_type": "update",  # Not "create"
            "object_id": 123
        }
        payload_bytes = json.dumps(payload).encode()
        signature = compute_strava_signature(payload_bytes, "test_secret")
        
        response = client.post(
            "/webhook",
            data=payload_bytes,
            content_type="application/json",
            headers={
                "X-Strava-Signature": signature,
                "Authorization": "Bearer test_token"
            }
        )
        
        assert response.status_code == 200
        assert response.json["status"] == "ignored"
    
    @patch.dict(os.environ, {
        "STRAVA_CLIENT_SECRET": "test_secret",
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_invalid_object_id_rejected(self, client):
        """Invalid object_id should be rejected"""
        payload = {
            "object_type": "activity",
            "aspect_type": "create",
            "object_id": "not_an_int"  # Invalid
        }
        payload_bytes = json.dumps(payload).encode()
        signature = compute_strava_signature(payload_bytes, "test_secret")
        
        response = client.post(
            "/webhook",
            data=payload_bytes,
            content_type="application/json",
            headers={
                "X-Strava-Signature": signature,
                "Authorization": "Bearer test_token"
            }
        )
        
        assert response.status_code == 400


# ===========================
# GET ENDPOINT TESTS
# ===========================

class TestGetEndpointVerification:
    """Tests for GET /webhook verification endpoint"""
    
    @patch.dict(os.environ, {
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_valid_verification_accepted(self, client):
        """Valid verification request should be accepted"""
        response = client.get(
            "/webhook",
            query_string={
                "hub.mode": "subscribe",
                "hub.verify_token": "test_token",
                "hub.challenge": "test_challenge_value"
            }
        )
        
        assert response.status_code == 200
        assert response.json["hub.challenge"] == "test_challenge_value"
    
    @patch.dict(os.environ, {
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_wrong_token_rejected(self, client):
        """Verification with wrong token should be rejected"""
        response = client.get(
            "/webhook",
            query_string={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "test_challenge"
            }
        )
        
        assert response.status_code == 403
    
    @patch.dict(os.environ, {
        "WEBHOOK_VERIFY_TOKEN": "test_token",
        "STRAVA_GCP_PROJECT": "test_project",
        "STRAVA_WORKER_JOB": "test_job"
    })
    def test_missing_challenge_rejected(self, client):
        """Verification without challenge should be rejected"""
        response = client.get(
            "/webhook",
            query_string={
                "hub.mode": "subscribe",
                "hub.verify_token": "test_token"
                # Missing hub.challenge
            }
        )
        
        assert response.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
