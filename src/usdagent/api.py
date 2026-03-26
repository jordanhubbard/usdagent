"""FastAPI application for usdagent."""

from __future__ import annotations

import os
import pathlib
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from usdagent.usd_generator import generate_asset
from usdagent.auth import verify_api_key, get_current_user, authenticate_user, _create_access_token

app = FastAPI(
    title="usdagent",
    description="USD Asset Generation API",
    version="0.1.0",
)

_templates_dir = pathlib.Path(__file__).parent / "templates"
_templates = Jinja2Templates(directory=str(_templates_dir))


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class AssetOptions(BaseModel):
    scale: float = 1.0
    up_axis: str = "Y"
    units: str = "centimeters"


class CreateAssetRequest(BaseModel):
    description: str
    options: AssetOptions = AssetOptions()


class RefineOptions(BaseModel):
    preserve_geometry: bool = False


class RefineAssetRequest(BaseModel):
    feedback: str
    options: RefineOptions = RefineOptions()


class AssetResponse(BaseModel):
    id: str
    status: str
    description: str | None = None
    url: str | None = None
    parent_id: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# In-memory store (replace with DB in production)
# ---------------------------------------------------------------------------

_assets: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok", "version": "0.1.0"}


@app.post("/assets", status_code=202, response_model=AssetResponse)
async def create_asset(
    req: CreateAssetRequest,
    _key: str = Depends(verify_api_key),
) -> AssetResponse:
    """Create a new USD asset from a text description."""
    # TODO: validate API key
    asset_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc)
    record: dict[str, Any] = {
        "id": asset_id,
        "status": "pending",
        "description": req.description,
        "options": req.options.model_dump(),
        "url": None,
        "parent_id": None,
        "created_at": now,
        "completed_at": None,
    }
    _assets[asset_id] = record

    # Run generation synchronously (async queue is a future enhancement)
    try:
        record["status"] = "generating"
        out_path = generate_asset(asset_id, req.description, req.options.model_dump())
        record["status"] = "ready"
        record["url"] = str(out_path)
        record["completed_at"] = datetime.now(tz=timezone.utc)
    except Exception as exc:  # noqa: BLE001
        record["status"] = "error"
        record["url"] = None

    return AssetResponse(**record)


@app.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: str,
    _key: str = Depends(verify_api_key),
) -> AssetResponse:
    """Retrieve an asset and its generation status."""
    # TODO: validate API key
    record = _assets.get(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return AssetResponse(**record)


@app.patch("/assets/{asset_id}/refine", status_code=202, response_model=AssetResponse)
async def refine_asset(
    asset_id: str,
    req: RefineAssetRequest,
    _key: str = Depends(verify_api_key),
) -> AssetResponse:
    """Iteratively refine an existing asset."""
    # TODO: validate API key
    parent = _assets.get(asset_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if parent["status"] != "ready":
        raise HTTPException(status_code=400, detail="Asset is not ready for refinement")

    new_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc)
    record: dict[str, Any] = {
        "id": new_id,
        "status": "pending",
        "description": req.feedback,
        "options": req.options.model_dump(),
        "url": None,
        "parent_id": asset_id,
        "created_at": now,
        "completed_at": None,
    }
    _assets[new_id] = record

    # Build refined description combining parent context with new feedback
    refined_description = f"{req.feedback} (refined from: {parent.get('description', '')})"

    # Run generation synchronously
    try:
        record["status"] = "generating"
        out_path = generate_asset(new_id, refined_description, req.options.model_dump())
        record["status"] = "ready"
        record["url"] = str(out_path)
        record["completed_at"] = datetime.now(tz=timezone.utc)
    except Exception as exc:  # noqa: BLE001
        record["status"] = "error"
        record["url"] = None

    return AssetResponse(**record)


@app.post("/auth/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict[str, str]:
    """Obtain a JWT access token."""
    username = authenticate_user(form_data.username, form_data.password)
    if not username:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = _create_access_token(username)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/auth/me")
async def auth_me(current_user: str = Depends(get_current_user)) -> dict[str, str]:
    """Return info about the current authenticated user."""
    return {"username": current_user}


@app.get("/assets", response_model=list[AssetResponse])
async def list_assets(_key: str = Depends(verify_api_key)) -> list[AssetResponse]:
    """List all assets."""
    return [AssetResponse(**record) for record in _assets.values()]


@app.get("/ui", response_class=HTMLResponse)
async def web_ui(request: Request) -> HTMLResponse:
    """Web UI for asset management."""
    google_configured = bool(os.environ.get("GOOGLE_CLIENT_ID"))
    return _templates.TemplateResponse(
        "ui.html",
        {"request": request, "google_configured": google_configured},
    )


