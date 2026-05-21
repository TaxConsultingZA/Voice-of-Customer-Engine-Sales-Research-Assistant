"""
Tests for VOC_API_KEY authentication middleware.

Verifies that all non-health endpoints enforce the key when VOC_API_KEY is set
and pass through freely when it is absent (local dev / CI with no key configured).
"""

import pytest
from fastapi.testclient import TestClient

from services.decision.app.engine import clear_state
from services.decision.app.main import app

_DECIDE_PAYLOAD = {"crisis_score": 0.1, "actions": []}


@pytest.fixture(autouse=True)
def _reset():
    clear_state()
    yield
    clear_state()


def _client():
    return TestClient(app, raise_server_exceptions=True)


# ── Auth disabled (no VOC_API_KEY configured) ─────────────────────────────────


def test_no_key_configured_allows_any_request(monkeypatch):
    monkeypatch.delenv("VOC_API_KEY", raising=False)
    r = _client().post("/decide", json=_DECIDE_PAYLOAD)
    assert r.status_code == 200


def test_no_key_configured_allows_request_without_header(monkeypatch):
    monkeypatch.delenv("VOC_API_KEY", raising=False)
    r = _client().get("/pending")
    assert r.status_code == 200


# ── Auth enabled (VOC_API_KEY is set) ─────────────────────────────────────────


def test_correct_key_is_accepted(monkeypatch):
    monkeypatch.setenv("VOC_API_KEY", "test-secret-key")
    r = _client().post(
        "/decide",
        headers={"X-Api-Key": "test-secret-key"},
        json=_DECIDE_PAYLOAD,
    )
    assert r.status_code == 200


def test_wrong_key_returns_401(monkeypatch):
    monkeypatch.setenv("VOC_API_KEY", "test-secret-key")
    r = _client().post(
        "/decide",
        headers={"X-Api-Key": "wrong-key"},
        json=_DECIDE_PAYLOAD,
    )
    assert r.status_code == 401


def test_missing_key_header_returns_401(monkeypatch):
    monkeypatch.setenv("VOC_API_KEY", "test-secret-key")
    r = _client().post("/decide", json=_DECIDE_PAYLOAD)
    assert r.status_code == 401


def test_health_endpoint_exempt_from_auth(monkeypatch):
    monkeypatch.setenv("VOC_API_KEY", "test-secret-key")
    r = _client().get("/health")
    assert r.status_code == 200
