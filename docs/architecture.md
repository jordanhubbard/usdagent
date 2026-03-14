# Architecture

## Overview

usdagent is a Python service built on FastAPI. It accepts text descriptions of 3D assets and generates USD (Universal Scene Description) files using OpenUSD Python bindings.

```
┌─────────────────────────────────────────────────────────────────┐
│                          usdagent                               │
│                                                                 │
│  ┌─────────┐    ┌──────────────┐    ┌────────────────────────┐ │
│  │  REST   │    │  Generation  │    │     Asset Store        │ │
│  │  API    │───▶│  Pipeline    │───▶│  (local disk / S3)     │ │
│  │(FastAPI)│    │  (OpenUSD)   │    │                        │ │
│  └────┬────┘    └──────────────┘    └────────────────────────┘ │
│       │                                          │              │
│  ┌────▼────┐                        ┌────────────▼───────────┐ │
│  │  Web UI │                        │   Google Drive Export  │ │
│  │(HTML/JS)│                        │   (OAuth2)             │ │
│  └─────────┘                        └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### REST API (FastAPI)
- Handles incoming HTTP requests
- Manages async job queue for USD generation
- Returns task IDs for polling

### Generation Pipeline
- Parses text descriptions into scene parameters
- Uses OpenUSD Python bindings (`pxr`) to construct USD stages
- Supports meshes, materials, lights, and cameras

### Asset Store
- Stores generated `.usd` and `.usdc` files
- Keyed by asset ID (UUID)
- Supports local disk (default) and S3-compatible storage

### Web UI
- Vanilla HTML/JS frontend served at `/ui`
- USD file preview using `three.js` or `babylon.js`
- Google Drive OAuth2 flow for export

### Authentication
- JWT-based auth for the web UI
- API key auth for programmatic access

## Data Flow

1. Client POSTs text description to `/assets`
2. API enqueues a generation job, returns `{"id": "<uuid>", "status": "pending"}`
3. Worker picks up job, runs OpenUSD generation pipeline
4. Asset stored on disk; status updated to `"ready"`
5. Client GETs `/assets/{id}` to retrieve the USD file URL
6. Client can PATCH `/assets/{id}/refine` with feedback to trigger a new generation pass
7. Web UI polls for status and displays the asset when ready

## Dependencies

- Python 3.10+
- FastAPI + uvicorn
- OpenUSD (`pxr`) Python bindings
- Google API Python client (for Drive integration)
- SQLite (for job queue and asset metadata)
