"""Basic API tests for usdagent."""

from fastapi.testclient import TestClient

from src.usdagent.api import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_asset():
    resp = client.post(
        "/assets",
        json={"description": "A simple red cube"},
        headers={"X-API-Key": "test"},
    )
    assert resp.status_code == 202
    data = resp.json()
    # Generation runs synchronously, so status is "ready" on return
    assert data["status"] == "ready"
    assert "id" in data
    assert data["url"] is not None


def test_get_asset_not_found():
    resp = client.get(
        "/assets/nonexistent-id",
        headers={"X-API-Key": "test"},
    )
    assert resp.status_code == 404


def test_ui_serves_html():
    """GET /ui should return the index.html with HTML content."""
    resp = client.get("/ui")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert b"usdagent" in resp.content


def test_static_css_served():
    """GET /static/style.css should return CSS content."""
    resp = client.get("/static/style.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]
    assert b"--bg" in resp.content


def test_static_js_served():
    """GET /static/app.js should return JavaScript content."""
    resp = client.get("/static/app.js")
    assert resp.status_code == 200
    content_type = resp.headers["content-type"]
    assert "javascript" in content_type or "text/plain" in content_type
    assert b"generateAsset" in resp.content


def test_create_and_get_asset():
    create_resp = client.post(
        "/assets",
        json={"description": "A blue sphere"},
        headers={"X-API-Key": "test"},
    )
    assert create_resp.status_code == 202
    asset_id = create_resp.json()["id"]

    get_resp = client.get(
        f"/assets/{asset_id}",
        headers={"X-API-Key": "test"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == asset_id


def test_refine_asset():
    """PATCH /assets/{id}/refine should create a child asset referencing the parent."""
    # Create parent
    parent_resp = client.post(
        "/assets",
        json={"description": "A green cube"},
        headers={"X-API-Key": "test"},
    )
    assert parent_resp.status_code == 202
    parent = parent_resp.json()
    parent_id = parent["id"]
    assert parent["status"] == "ready"

    # Refine
    refine_resp = client.patch(
        f"/assets/{parent_id}/refine",
        json={"feedback": "Make it purple", "options": {"preserve_geometry": False}},
        headers={"X-API-Key": "test"},
    )
    assert refine_resp.status_code == 202
    child = refine_resp.json()
    assert child["status"] == "ready"
    assert child["parent_id"] == parent_id
    assert child["id"] != parent_id
    assert child["url"] is not None


def test_refine_asset_preserve_geometry():
    """PATCH with preserve_geometry=True should still produce a ready asset."""
    parent_resp = client.post(
        "/assets",
        json={"description": "A red cylinder"},
        headers={"X-API-Key": "test"},
    )
    assert parent_resp.status_code == 202
    parent_id = parent_resp.json()["id"]

    refine_resp = client.patch(
        f"/assets/{parent_id}/refine",
        json={"feedback": "Change color to gold", "options": {"preserve_geometry": True}},
        headers={"X-API-Key": "test"},
    )
    assert refine_resp.status_code == 202
    child = refine_resp.json()
    assert child["status"] == "ready"
    assert child["parent_id"] == parent_id


def test_refine_asset_not_found():
    """PATCH on a non-existent asset should return 404."""
    resp = client.patch(
        "/assets/does-not-exist/refine",
        json={"feedback": "make it shinier"},
        headers={"X-API-Key": "test"},
    )
    assert resp.status_code == 404


def test_refine_asset_not_ready():
    """PATCH on an asset that isn't ready should return 400."""
    # Manually inject a non-ready asset into the store
    from src.usdagent.api import _assets
    import uuid
    from datetime import datetime, timezone
    fake_id = str(uuid.uuid4())
    _assets[fake_id] = {
        "id": fake_id,
        "status": "generating",
        "description": "pending asset",
        "options": {},
        "url": None,
        "parent_id": None,
        "created_at": datetime.now(tz=timezone.utc),
        "completed_at": None,
    }
    resp = client.patch(
        f"/assets/{fake_id}/refine",
        json={"feedback": "make it shinier"},
        headers={"X-API-Key": "test"},
    )
    assert resp.status_code == 400
