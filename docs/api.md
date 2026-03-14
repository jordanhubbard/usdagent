# API Reference

Base URL: `http://localhost:8000`

All API endpoints require an API key in the `X-API-Key` header unless otherwise noted.

---

## POST /assets

Create a new USD asset from a text description.

### Request

```json
{
  "description": "A red wooden chair with four legs and a curved back",
  "options": {
    "scale": 1.0,
    "up_axis": "Y",
    "units": "centimeters"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| description | string | yes | Plain-text description of the 3D asset |
| options.scale | float | no | Overall scale multiplier (default: 1.0) |
| options.up_axis | string | no | Up axis: "Y" or "Z" (default: "Y") |
| options.units | string | no | Scene units (default: "centimeters") |

### Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2026-03-14T12:00:00Z"
}
```

**Status codes**: 202 Accepted, 400 Bad Request, 401 Unauthorized

---

## GET /assets/{id}

Retrieve an asset and its generation status.

### Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "ready",
  "description": "A red wooden chair...",
  "url": "/assets/550e8400-e29b-41d4-a716-446655440000/output.usdc",
  "created_at": "2026-03-14T12:00:00Z",
  "completed_at": "2026-03-14T12:00:05Z"
}
```

**Status values**: `pending`, `generating`, `ready`, `failed`

**Status codes**: 200 OK, 404 Not Found, 401 Unauthorized

---

## PATCH /assets/{id}/refine

Iteratively refine an existing asset with additional feedback.

### Request

```json
{
  "feedback": "Make the seat cushion blue and add armrests",
  "options": {
    "preserve_geometry": true
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| feedback | string | yes | Plain-text refinement instructions |
| options.preserve_geometry | bool | no | Keep existing mesh, only change materials/details (default: false) |

### Response

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "parent_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2026-03-14T12:01:00Z"
}
```

**Status codes**: 202 Accepted, 404 Not Found, 400 Bad Request, 401 Unauthorized

---

## GET /ui

Web UI for asset viewer and Google Drive export.

Returns HTML page (no API key required for initial load; auth is session-based).

**Status codes**: 200 OK, 302 Redirect (if not authenticated)

---

## GET /health

Health check endpoint. No authentication required.

### Response

```json
{"status": "ok", "version": "0.1.0"}
```
