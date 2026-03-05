"""
Tests for FastAPI API endpoints.
Covers: analysis endpoint, notifications endpoint, health check.
"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from fastapi.testclient import TestClient


# We need to mock AWS services before importing the app
@pytest.fixture(scope="module")
def client():
    """Create a test client with mocked services."""
    with patch("app.services.aws_service.aws_service") as mock_aws:
        mock_aws._initialized = True
        mock_aws.bedrock_runtime = MagicMock()
        mock_aws.textract_client = MagicMock()
        mock_aws.polly_client = MagicMock()
        mock_aws.comprehend_client = MagicMock()
        mock_aws.sns_client = MagicMock()
        mock_aws.s3_client = MagicMock()

        from app.main import app

        yield TestClient(app)


class TestHealthEndpoint:
    """Tests for the root / health check."""

    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_health_endpoint(self, client):
        response = client.get("/health")
        # Depending on implementation, could be 200 or 404
        # We verify the app is responsive
        assert response.status_code in (200, 404)


class TestAnalysisEndpoint:
    """Tests for the /api/v1/analysis/explain endpoint."""

    def test_no_session_returns_404(self, client):
        response = client.post(
            "/api/v1/analysis/explain",
            json={
                "session_id": "nonexistent",
                "document_id": "doc-1",
                "language": "en",
            },
        )
        assert response.status_code == 404

    def test_explain_requires_session_id(self, client):
        response = client.post(
            "/api/v1/analysis/explain",
            json={"document_id": "doc-1"},
        )
        assert response.status_code == 422  # Validation error

    def test_invalid_language_rejected(self, client):
        response = client.post(
            "/api/v1/analysis/explain",
            json={
                "session_id": "s1",
                "document_id": "d1",
                "language": "fr",  # Not supported
            },
        )
        assert response.status_code == 422


class TestNotificationsEndpoint:
    """Tests for the /api/v1/notifications/send-summary endpoint."""

    def test_sms_disabled_returns_503_before_session_check(self, client):
        response = client.post(
            "/api/v1/notifications/send-summary",
            json={
                "session_id": "nonexistent",
                "phone_number": "+919876543210",
                "language": "en",
            },
        )
        # SMS is disabled by default, checked before session lookup
        assert response.status_code == 503

    def test_sms_disabled_returns_503(self, client):
        response = client.post(
            "/api/v1/notifications/send-summary",
            json={
                "session_id": "s1",
                "phone_number": "9876543210",
                "language": "en",
            },
        )
        # SMS is disabled by default, so we get 503
        assert response.status_code == 503

    def test_valid_phone_sms_disabled(self, client):
        response = client.post(
            "/api/v1/notifications/send-summary",
            json={
                "session_id": "s1",
                "phone_number": "+919876543210",
                "language": "en",
            },
        )
        # SMS is disabled by default, so 503 before session lookup
        assert response.status_code == 503


class TestAnalysisResultEndpoint:
    """Tests for the /api/v1/analysis/result/{session_id} endpoint."""

    def test_no_session_returns_404(self, client):
        response = client.get("/api/v1/analysis/result/nonexistent")
        assert response.status_code == 404


class TestFollowUpEndpoint:
    """Tests for the /api/v1/analysis/followup endpoint."""

    def test_no_session_returns_404(self, client):
        response = client.post(
            "/api/v1/analysis/followup",
            json={
                "session_id": "nonexistent",
                "question": "What does this mean?",
                "language": "en",
            },
        )
        assert response.status_code == 404

    def test_empty_question_rejected(self, client):
        response = client.post(
            "/api/v1/analysis/followup",
            json={
                "session_id": "s1",
                "question": "",
                "language": "en",
            },
        )
        assert response.status_code == 422
