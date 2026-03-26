"""Basic API tests for usdagent."""

import pytest
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
