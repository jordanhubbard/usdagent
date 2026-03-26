"""Google Drive integration for usdagent."""
from __future__ import annotations

import os
import pathlib
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

_GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
_GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
_GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
)
_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

router = APIRouter()

_SESSION: dict[str, Any] = {}  # In-memory session store (replace with real sessions in production)


def _drive_not_configured() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Google Drive not configured. Set GOOGLE_CLIENT_ID to enable.",
    )


@router.get("/auth/google")
async def google_auth(next: str = "/ui") -> RedirectResponse:
    """Redirect to Google OAuth2 consent screen."""
    if not _GOOGLE_CLIENT_ID:
        _drive_not_configured()

    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise HTTPException(status_code=501, detail="google-auth-oauthlib not installed")

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": _GOOGLE_CLIENT_ID,
                "client_secret": _GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [_GOOGLE_REDIRECT_URI],
            }
        },
        scopes=_SCOPES,
    )
    flow.redirect_uri = _GOOGLE_REDIRECT_URI
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=next,
    )
    return RedirectResponse(url=auth_url)


@router.get("/auth/google/callback")
async def google_callback(code: str, state: str = "/ui") -> RedirectResponse:
    """Handle Google OAuth2 callback."""
    if not _GOOGLE_CLIENT_ID:
        _drive_not_configured()

    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise HTTPException(status_code=501, detail="google-auth-oauthlib not installed")

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": _GOOGLE_CLIENT_ID,
                "client_secret": _GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [_GOOGLE_REDIRECT_URI],
            }
        },
        scopes=_SCOPES,
    )
    flow.redirect_uri = _GOOGLE_REDIRECT_URI
    flow.fetch_token(code=code)
    credentials = flow.credentials
    _SESSION["google_credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or []),
    }
    return RedirectResponse(url=state)


def upload_to_drive(asset_id: str, file_path: pathlib.Path) -> dict[str, str]:
    """Upload a .usda file to Google Drive. Returns {file_id, web_view_link}."""
    creds_data = _SESSION.get("google_credentials")
    if not creds_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated with Google. Visit /auth/google first.",
        )

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        raise HTTPException(status_code=501, detail="google-api-python-client not installed")

    creds = Credentials(**creds_data)
    service = build("drive", "v3", credentials=creds)

    file_metadata = {
        "name": f"{asset_id}.usda",
        "mimeType": "text/plain",
    }
    media = MediaFileUpload(str(file_path), mimetype="text/plain", resumable=False)
    result = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id,webViewLink")
        .execute()
    )
    return {
        "file_id": result.get("id", ""),
        "web_view_link": result.get("webViewLink", ""),
    }
