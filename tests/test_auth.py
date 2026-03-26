"""Tests for authentication (JWT + API key validation)."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def set_api_keys(monkeypatch):
    monkeypatch.setenv("USDAGENT_API_KEYS", "validkey,anotherkey")
    monkeypatch.setenv("USDAGENT_USERS", "testuser:testpass")


@pytest.fixture()
def client():
    # Import after env vars are patched
    from src.usdagent.api import app
    return TestClient(app)


def test_valid_api_key_accepted(client):
    resp = client.get("/assets/nonexistent", headers={"X-API-Key": "validkey"})
    assert resp.status_code == 404  # asset not found, not 401


def test_invalid_api_key_rejected(client):
    resp = client.get("/assets/nonexistent", headers={"X-API-Key": "badkey"})
    assert resp.status_code == 401


def test_login_valid_credentials(client):
    resp = client.post(
        "/auth/token",
        data={"username": "testuser", "password": "testpass"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client):
    resp = client.post(
        "/auth/token",
        data={"username": "testuser", "password": "wrongpass"},
    )
    assert resp.status_code == 401


def test_auth_me_with_valid_token(client):
    # Get token
    login_resp = client.post(
        "/auth/token",
        data={"username": "testuser", "password": "testpass"},
    )
    token = login_resp.json()["access_token"]

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"


def test_auth_me_without_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_auth_me_with_invalid_token(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401
