"""Google Drive OAuth2 integration for usdagent."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Cookie, HTTPException, Request
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# In-memory session store: session_id -> credential dict
_sessions: dict[str, dict[str, Any]] = {}
# OAuth state -> session_id (consumed after one use)
_oauth_states: dict[str, str] = {}

router = APIRouter(tags=["drive"])


def _get_flow(redirect_uri: str) -> Flow:
    """Build an OAuth2 Flow from environment credentials."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Drive not configured — set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET"
            ),
        )
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)


@router.get("/auth/google")
async def auth_google(request: Request) -> RedirectResponse:
    """Initiate Google OAuth2 flow and redirect the user to Google's consent page."""
    redirect_uri = str(request.url_for("auth_google_callback"))
    flow = _get_flow(redirect_uri)
    session_id = str(uuid.uuid4())
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    _oauth_states[state] = session_id
    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie("drive_session", session_id, httponly=True, samesite="lax")
    return response


@router.get("/auth/google/callback", name="auth_google_callback")
async def auth_google_callback(
    request: Request,
    state: str,
    code: str,
) -> RedirectResponse:
    """Handle Google OAuth2 callback, store credentials, and redirect to the UI."""
    session_id = _oauth_states.pop(state, None)
    if session_id is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    redirect_uri = str(request.url_for("auth_google_callback"))
    flow = _get_flow(redirect_uri)
    flow.fetch_token(code=code)
    creds = flow.credentials

    _sessions[session_id] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
    }

    response = RedirectResponse(url="/ui", status_code=302)
    response.set_cookie("drive_session", session_id, httponly=True, samesite="lax")
    return response


@router.get("/auth/google/status")
async def auth_status(
    drive_session: str | None = Cookie(default=None),
) -> dict[str, bool]:
    """Return whether the current session is authenticated with Google Drive."""
    return {"authenticated": bool(drive_session and drive_session in _sessions)}


@router.post("/assets/{asset_id}/export/drive")
async def export_to_drive(
    asset_id: str,
    drive_session: str | None = Cookie(default=None),
) -> dict[str, str | None]:
    """Upload an asset USD file to the authenticated user's Google Drive."""
    if not drive_session or drive_session not in _sessions:
        raise HTTPException(status_code=401, detail="Not authenticated with Google Drive")

    # Lazy relative import avoids circular dependency with api.py
    from .api import _assets  # noqa: PLC0415

    record = _assets.get(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if record["status"] != "ready":
        raise HTTPException(status_code=400, detail="Asset is not ready for export")

    asset_path = Path(record["url"])
    if not asset_path.exists():
        raise HTTPException(status_code=404, detail="Asset file not found on disk")

    creds_data = _sessions[drive_session]
    creds = Credentials(
        token=creds_data["token"],
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data["token_uri"],
        client_id=creds_data["client_id"],
        client_secret=creds_data["client_secret"],
        scopes=creds_data["scopes"],
    )

    service = build("drive", "v3", credentials=creds)
    file_metadata = {
        "name": f"{asset_id}.usda",
        "description": record.get("description", ""),
    }
    media = MediaFileUpload(str(asset_path), mimetype="application/octet-stream", resumable=False)
    uploaded = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id,name,webViewLink")
        .execute()
    )

    # Persist refreshed token if it was renewed during the API call
    _sessions[drive_session]["token"] = creds.token

    return {
        "drive_file_id": uploaded.get("id"),
        "drive_file_name": uploaded.get("name"),
        "drive_url": uploaded.get("webViewLink"),
    }
