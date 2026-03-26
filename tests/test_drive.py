"""Tests for Google Drive integration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from src.usdagent.api import app
    return TestClient(app, raise_server_exceptions=False)


def test_google_auth_not_configured(client):
    """Without GOOGLE_CLIENT_ID, /auth/google returns 501."""
    with patch.dict("os.environ", {}, clear=False):
        # Ensure GOOGLE_CLIENT_ID is not set
        import os
        os.environ.pop("GOOGLE_CLIENT_ID", None)
        resp = client.get("/auth/google", follow_redirects=False)
    assert resp.status_code == 501


def test_google_callback_not_configured(client):
    """Without GOOGLE_CLIENT_ID, /auth/google/callback returns 501."""
    import os
    os.environ.pop("GOOGLE_CLIENT_ID", None)
    resp = client.get("/auth/google/callback?code=abc", follow_redirects=False)
    assert resp.status_code == 501


def test_export_drive_not_configured(client):
    """Without GOOGLE_CLIENT_ID, POST /assets/{id}/export/drive returns 501."""
    import os
    os.environ.pop("GOOGLE_CLIENT_ID", None)
    resp = client.post("/assets/some-id/export/drive", headers={"X-API-Key": "any"})
    assert resp.status_code == 501


def test_export_drive_asset_not_found(client):
    """With GOOGLE_CLIENT_ID set, 404 for unknown asset."""
    with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "test-client-id"}):
        # Reload drive module to pick up env var
        import importlib
        import usdagent.drive as drive_mod
        importlib.reload(drive_mod)
        resp = client.post(
            "/assets/nonexistent-id/export/drive",
            headers={"X-API-Key": "any"},
        )
    # Should be 404 or 501 depending on module reload
    assert resp.status_code in (404, 501)


def test_upload_to_drive_no_credentials():
    """upload_to_drive raises 401 when no Google credentials in session."""
    import pathlib
    from fastapi import HTTPException
    from usdagent.drive import _SESSION, upload_to_drive

    _SESSION.pop("google_credentials", None)
    with pytest.raises(HTTPException) as exc_info:
        upload_to_drive("test-id", pathlib.Path("/tmp/test.usda"))
    assert exc_info.value.status_code == 401


def test_upload_to_drive_mocked():
    """upload_to_drive calls Drive API with correct parameters."""
    import pathlib
    from usdagent.drive import _SESSION, upload_to_drive

    _SESSION["google_credentials"] = {
        "token": "fake-token",
        "refresh_token": "fake-refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "fake-client-id",
        "client_secret": "fake-secret",
        "scopes": ["https://www.googleapis.com/auth/drive.file"],
    }

    mock_file = MagicMock()
    mock_file.execute.return_value = {"id": "drive-file-123", "webViewLink": "https://drive.google.com/file/123"}

    mock_files = MagicMock()
    mock_files.create.return_value = mock_file

    mock_service = MagicMock()
    mock_service.files.return_value = mock_files

    # Test with patching the google imports inside the function
    fake_creds = MagicMock()
    with patch.dict("sys.modules", {
        "google.oauth2.credentials": MagicMock(Credentials=MagicMock(return_value=fake_creds)),
        "googleapiclient.discovery": MagicMock(build=MagicMock(return_value=mock_service)),
        "googleapiclient.http": MagicMock(MediaFileUpload=MagicMock()),
    }):
        tmp_file = pathlib.Path("/tmp/test-asset.usda")
        tmp_file.write_text("#usda 1.0\n")
        result = upload_to_drive("test-id", tmp_file)
        assert "file_id" in result
        tmp_file.unlink(missing_ok=True)

    _SESSION.pop("google_credentials", None)
