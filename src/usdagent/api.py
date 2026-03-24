"""FastAPI application for usdagent."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from usdagent.usd_generator import generate_asset

app = FastAPI(
    title="usdagent",
    description="USD Asset Generation API",
    version="0.1.0",
)


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
    x_api_key: str = Header(...),
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
    x_api_key: str = Header(...),
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
    x_api_key: str = Header(...),
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


@app.get("/ui", response_class=HTMLResponse)
async def web_ui() -> str:
    """Basic web UI for asset viewer and Google Drive export."""
    # TODO: replace with proper template
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>usdagent — USD Asset Viewer</title>
  <style>
    body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }
    h1 { color: #333; }
    #generate-form { margin: 20px 0; }
    textarea { width: 100%; height: 100px; }
    button { padding: 8px 16px; background: #0066cc; color: white; border: none; cursor: pointer; }
    #result { margin-top: 20px; padding: 10px; background: #f0f0f0; display: none; }
  </style>
</head>
<body>
  <h1>usdagent — USD Asset Viewer</h1>
  <div id="generate-form">
    <h2>Generate a USD Asset</h2>
    <textarea id="description" placeholder="Describe your 3D asset..."></textarea>
    <br><br>
    <button onclick="generateAsset()">Generate</button>
  </div>
  <div id="result">
    <h3>Result</h3>
    <pre id="result-text"></pre>
    <button onclick="exportToDrive()" style="background:#34a853">Export to Google Drive</button>
  </div>
  <script>
    async function generateAsset() {
      const desc = document.getElementById('description').value;
      if (!desc) { alert('Please enter a description'); return; }
      const resp = await fetch('/assets', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-API-Key': 'demo'},
        body: JSON.stringify({description: desc})
      });
      const data = await resp.json();
      document.getElementById('result').style.display = 'block';
      document.getElementById('result-text').textContent = JSON.stringify(data, null, 2);
      pollStatus(data.id);
    }
    async function pollStatus(id) {
      const resp = await fetch('/assets/' + id, {headers: {'X-API-Key': 'demo'}});
      const data = await resp.json();
      document.getElementById('result-text').textContent = JSON.stringify(data, null, 2);
      if (data.status === 'pending' || data.status === 'generating') {
        setTimeout(() => pollStatus(id), 2000);
      }
    }
    function exportToDrive() {
      window.location.href = '/auth/google?next=' + encodeURIComponent(window.location.href);
    }
  </script>
</body>
</html>"""
