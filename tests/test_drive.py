"""Tests for Google Drive OAuth2 integration."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import src.usdagent.drive as drive_module
from src.usdagent.api import _assets, app

# Do not follow redirects by default so we can inspect 302 responses.
client = TestClient(app, follow_redirects=False)


def _authed_client(session_id: str) -> TestClient:
    """Return a TestClient with a drive_session cookie pre-set."""
    return TestClient(app, follow_redirects=False, cookies={"drive_session": session_id})

_FAKE_ENV = {
    "GOOGLE_CLIENT_ID": "test-client-id",
    "GOOGLE_CLIENT_SECRET": "test-client-secret",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_flow(
    auth_url: str = "https://accounts.google.com/o/oauth2/auth?foo=bar",
) -> MagicMock:
    """Return a mock Flow whose authorization_url returns a deterministic state."""
    flow = MagicMock()
    flow.authorization_url.return_value = (auth_url, "test-state-123")
    creds = MagicMock()
    creds.token = "ya29.test-access-token"
    creds.refresh_token = "1//test-refresh-token"
    creds.token_uri = "https://oauth2.googleapis.com/token"
    creds.client_id = "test-client-id"
    creds.client_secret = "test-client-secret"
    creds.scopes = ["https://www.googleapis.com/auth/drive.file"]
    flow.credentials = creds
    return flow


def _inject_session(session_id: str) -> None:
    """Directly insert a session into the in-memory store."""
    drive_module._sessions[session_id] = {
        "token": "ya29.test-token",
        "refresh_token": "1//test-refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "scopes": ["https://www.googleapis.com/auth/drive.file"],
    }


def _create_ready_asset() -> tuple[str, str]:
    """Create a temporary .usda file and register a ready asset. Returns (asset_id, file_path)."""
    asset_id = str(uuid.uuid4())
    tmp = tempfile.NamedTemporaryFile(suffix=".usda", delete=False)
    tmp.write(b"#usda 1.0\n")
    tmp.close()
    _assets[asset_id] = {
        "id": asset_id,
        "status": "ready",
        "description": "a test sphere",
        "options": {},
        "url": tmp.name,
        "parent_id": None,
        "created_at": datetime.now(tz=timezone.utc),
        "completed_at": datetime.now(tz=timezone.utc),
    }
    return asset_id, tmp.name


# ---------------------------------------------------------------------------
# OAuth2 redirect
# ---------------------------------------------------------------------------


def test_auth_google_redirects_to_google():
    """GET /auth/google should return 302 to Google's OAuth consent page."""
    mock_flow = _make_mock_flow()
    with patch.dict(os.environ, _FAKE_ENV):
        with patch("src.usdagent.drive.Flow.from_client_config", return_value=mock_flow):
            resp = client.get("/auth/google")

    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "accounts.google.com" in location


def test_auth_google_sets_session_cookie():
    """GET /auth/google should set a drive_session cookie."""
    mock_flow = _make_mock_flow()
    with patch.dict(os.environ, _FAKE_ENV):
        with patch("src.usdagent.drive.Flow.from_client_config", return_value=mock_flow):
            resp = client.get("/auth/google")

    assert "drive_session" in resp.cookies


def test_auth_google_missing_credentials_returns_503():
    """GET /auth/google without env vars should return 503."""
    with patch.dict(os.environ, {}, clear=True):
        resp = client.get("/auth/google")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# OAuth2 callback
# ---------------------------------------------------------------------------


def test_auth_google_callback_stores_session_and_redirects():
    """Callback with valid state/code should store credentials and redirect to /ui."""
    session_id = str(uuid.uuid4())
    drive_module._oauth_states["valid-state"] = session_id

    mock_flow = _make_mock_flow()
    with patch.dict(os.environ, _FAKE_ENV):
        with patch("src.usdagent.drive.Flow.from_client_config", return_value=mock_flow):
            resp = client.get(
                "/auth/google/callback",
                params={"state": "valid-state", "code": "4/test-auth-code"},
            )

    assert resp.status_code == 302
    assert resp.headers["location"].endswith("/ui")
    assert session_id in drive_module._sessions
    stored = drive_module._sessions[session_id]
    assert stored["token"] == "ya29.test-access-token"
    assert stored["client_id"] == "test-client-id"


def test_auth_google_callback_invalid_state_returns_400():
    """Callback with an unknown state parameter should return 400."""
    with patch.dict(os.environ, _FAKE_ENV):
        with patch("src.usdagent.drive.Flow.from_client_config", return_value=MagicMock()):
            resp = client.get(
                "/auth/google/callback",
                params={"state": "bogus-state", "code": "some-code"},
            )
    assert resp.status_code == 400


def test_auth_google_callback_state_is_consumed():
    """Each OAuth state should only be usable once (CSRF protection)."""
    session_id = str(uuid.uuid4())
    drive_module._oauth_states["one-time-state"] = session_id

    mock_flow = _make_mock_flow()
    with patch.dict(os.environ, _FAKE_ENV):
        with patch("src.usdagent.drive.Flow.from_client_config", return_value=mock_flow):
            client.get(
                "/auth/google/callback",
                params={"state": "one-time-state", "code": "code1"},
            )
            # Second attempt with the same state must fail
            resp2 = client.get(
                "/auth/google/callback",
                params={"state": "one-time-state", "code": "code2"},
            )

    assert resp2.status_code == 400


# ---------------------------------------------------------------------------
# Auth status
# ---------------------------------------------------------------------------


def test_auth_status_unauthenticated():
    """GET /auth/google/status without a session cookie returns authenticated=false."""
    # Use a fresh client to ensure no cookies from prior tests bleed through.
    resp = TestClient(app, follow_redirects=False).get("/auth/google/status")
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is False


def test_auth_status_authenticated():
    """GET /auth/google/status with a valid session cookie returns authenticated=true."""
    session_id = str(uuid.uuid4())
    _inject_session(session_id)
    resp = _authed_client(session_id).get("/auth/google/status")
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True


def test_auth_status_unknown_cookie():
    """GET /auth/google/status with an unrecognised session cookie returns authenticated=false."""
    resp = _authed_client("no-such-session").get("/auth/google/status")
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is False


# ---------------------------------------------------------------------------
# Export to Drive
# ---------------------------------------------------------------------------


def test_export_not_authenticated():
    """POST /assets/{id}/export/drive without a session cookie should return 401."""
    # Fresh client to avoid cookies accumulated from prior OAuth redirect tests.
    resp = TestClient(app, follow_redirects=False).post("/assets/any-id/export/drive")
    assert resp.status_code == 401


def test_export_unknown_session_returns_401():
    """POST with a session cookie that isn't in _sessions should return 401."""
    resp = _authed_client("ghost-session").post("/assets/any-id/export/drive")
    assert resp.status_code == 401


def test_export_asset_not_found():
    """Export should return 404 when the asset ID does not exist."""
    session_id = str(uuid.uuid4())
    _inject_session(session_id)
    resp = _authed_client(session_id).post(f"/assets/{uuid.uuid4()}/export/drive")
    assert resp.status_code == 404


def test_export_asset_not_ready():
    """Export should return 400 when the asset status is not 'ready'."""
    session_id = str(uuid.uuid4())
    _inject_session(session_id)
    asset_id = str(uuid.uuid4())
    _assets[asset_id] = {
        "id": asset_id,
        "status": "generating",
        "description": "pending asset",
        "options": {},
        "url": None,
        "parent_id": None,
        "created_at": datetime.now(tz=timezone.utc),
        "completed_at": None,
    }
    resp = _authed_client(session_id).post(f"/assets/{asset_id}/export/drive")
    assert resp.status_code == 400


def test_export_to_drive_success():
    """POST /assets/{id}/export/drive with valid session should upload and return Drive info."""
    session_id = str(uuid.uuid4())
    _inject_session(session_id)
    asset_id, tmp_path = _create_ready_asset()

    mock_service = MagicMock()
    mock_service.files.return_value.create.return_value.execute.return_value = {
        "id": "drive-abc-123",
        "name": f"{asset_id}.usda",
        "webViewLink": "https://drive.google.com/file/d/drive-abc-123/view",
    }

    try:
        with patch("src.usdagent.drive.build", return_value=mock_service):
            with patch("src.usdagent.drive.Credentials"):
                with patch("src.usdagent.drive.MediaFileUpload"):
                    resp = _authed_client(session_id).post(
                        f"/assets/{asset_id}/export/drive"
                    )

        assert resp.status_code == 200
        data = resp.json()
        assert data["drive_file_id"] == "drive-abc-123"
        assert data["drive_url"] == "https://drive.google.com/file/d/drive-abc-123/view"
        assert data["drive_file_name"] == f"{asset_id}.usda"
    finally:
        os.unlink(tmp_path)
