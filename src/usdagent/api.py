"""FastAPI application for usdagent."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pathlib

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from usdagent.usd_generator import generate_asset

_STATIC_DIR = Path(__file__).parent / "static"
_TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

app = FastAPI(
    title="usdagent",
    description="USD Asset Generation API",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

# Drive OAuth2 router — relative import keeps both modules in the same package namespace
from .drive import router as _drive_router  # noqa: E402

app.include_router(_drive_router)


# ---------------------------------------------------------------------------
# API key auth middleware (Issue #5)
# /ui and /static/* are exempt; all other routes require the key when
# USDAGENT_API_KEY env var is set.
# ---------------------------------------------------------------------------

_EXEMPT_PREFIXES = ("/ui", "/view/", "/static/", "/auth/", "/health", "/docs", "/openapi")


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):  # type: ignore[return]
    required_key = os.environ.get("USDAGENT_API_KEY", "")
    if required_key:
        path = request.url.path
        exempt = any(path == p or path.startswith(p) for p in _EXEMPT_PREFIXES)
        if not exempt:
            provided = request.headers.get("X-API-Key", "")
            if provided != required_key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key"},
                )
    return await call_next(request)


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
) -> AssetResponse:
    """Create a new USD asset from a text description."""
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
    except Exception:  # noqa: BLE001
        record["status"] = "error"
        record["url"] = None

    return AssetResponse(**record)


@app.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: str,
) -> AssetResponse:
    """Retrieve an asset and its generation status."""
    record = _assets.get(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return AssetResponse(**record)


@app.patch("/assets/{asset_id}/refine", status_code=202, response_model=AssetResponse)
async def refine_asset(
    asset_id: str,
    req: RefineAssetRequest,
) -> AssetResponse:
    """Iteratively refine an existing asset."""
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

    # Build options — carry parent options forward, overlay refine options
    parent_options = dict(parent.get("options") or {})
    refine_opts = req.options.model_dump()
    generation_options = {**parent_options, **refine_opts}

    # Run generation synchronously
    try:
        record["status"] = "generating"
        out_path = generate_asset(new_id, refined_description, generation_options)
        record["status"] = "ready"
        record["url"] = str(out_path)
        record["completed_at"] = datetime.now(tz=timezone.utc)
    except Exception:  # noqa: BLE001
        record["status"] = "error"
        record["url"] = None

    return AssetResponse(**record)


@app.get("/assets", response_model=list[AssetResponse])
async def list_assets() -> list[AssetResponse]:
    """List all assets."""
    return [AssetResponse(**record) for record in _assets.values()]


@app.get("/ui", response_class=HTMLResponse)
async def web_ui(request: Request) -> HTMLResponse:
    """Serve the Jinja2-rendered asset management UI."""
    google_configured = bool(os.environ.get("GOOGLE_CLIENT_ID"))
    return _templates.TemplateResponse(
        "ui.html",
        {"request": request, "google_configured": google_configured},
    )


@app.get("/assets/{asset_id}/file")
async def get_asset_file(asset_id: str) -> FileResponse:
    """Serve the raw .usda file for an asset."""
    record = _assets.get(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if record["status"] != "ready" or not record["url"]:
        raise HTTPException(status_code=404, detail="Asset file not ready")
    path = Path(record["url"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Asset file not found on disk")
    return FileResponse(path, media_type="text/plain", filename=f"{asset_id}.usda")


@app.get("/view/{asset_id}", response_class=HTMLResponse)
async def view_asset(asset_id: str) -> HTMLResponse:
    """Serve the Three.js USD viewer for a single asset.

    COOP/COEP headers are set here (and only here) so that the Three.js
    USDLoader WASM can use SharedArrayBuffer without affecting OAuth flows
    on the rest of the app.
    """
    record = _assets.get(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    html = (_STATIC_DIR / "viewer.html").read_text()
    return HTMLResponse(
        content=html,
        headers={
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin",
        },
    )
