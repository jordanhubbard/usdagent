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
    assert data["status"] == "pending"
    assert "id" in data


def test_get_asset_not_found():
    resp = client.get(
        "/assets/nonexistent-id",
        headers={"X-API-Key": "test"},
    )
    assert resp.status_code == 404


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
