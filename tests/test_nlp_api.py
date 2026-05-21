"""
NLP Service — HTTP API tests.

Covers the FastAPI app in services/nlp/app/main.py and the auth middleware.
The pipeline itself is exercised by test_nlp_pipeline.py; these tests focus
on the HTTP layer: routing, request/response shapes, and auth enforcement.
"""

import pytest
from fastapi.testclient import TestClient

from services.nlp.app.main import app

client = TestClient(app)

_ANALYZE_PAYLOAD = {
    "text": "I cannot log in — password reset is broken.",
    "customer_arr": 15000.0,
    "channel": "email",
}


# ── Health ─────────────────────────────────────────────────────────────────────


def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["service"] == "voc-nlp"


# ── POST /analyze ──────────────────────────────────────────────────────────────


def test_analyze_returns_expected_fields():
    r = client.post("/analyze", json=_ANALYZE_PAYLOAD)
    assert r.status_code == 200
    body = r.json()
    for field in (
        "crisis_score",
        "intent",
        "taxonomy_path",
        "sentiment_polarity",
        "sentiment_confidence",
        "at_risk_flag",
        "requires_approval",
        "actions",
        "routing",
        "contains_slang",
        "anomaly_is_detected",
    ):
        assert field in body, f"missing field: {field}"


def test_analyze_crisis_score_within_bounds():
    r = client.post("/analyze", json=_ANALYZE_PAYLOAD)
    score = r.json()["crisis_score"]
    assert 0.0 <= score <= 1.0


def test_analyze_missing_text_returns_422():
    r = client.post("/analyze", json={"customer_arr": 0.0})
    assert r.status_code == 422


def test_analyze_empty_text_returns_422():
    r = client.post("/analyze", json={"text": "", "customer_arr": 0.0})
    assert r.status_code == 422


# ── Auth middleware ────────────────────────────────────────────────────────────


def test_auth_disabled_when_no_key_set(monkeypatch):
    monkeypatch.delenv("VOC_API_KEY", raising=False)
    r = client.post("/analyze", json=_ANALYZE_PAYLOAD)
    assert r.status_code == 200


def test_auth_accepts_correct_key(monkeypatch):
    monkeypatch.setenv("VOC_API_KEY", "nlp-secret")
    r = client.post(
        "/analyze",
        headers={"X-Api-Key": "nlp-secret"},
        json=_ANALYZE_PAYLOAD,
    )
    assert r.status_code == 200


def test_auth_rejects_wrong_key(monkeypatch):
    monkeypatch.setenv("VOC_API_KEY", "nlp-secret")
    r = client.post(
        "/analyze",
        headers={"X-Api-Key": "wrong"},
        json=_ANALYZE_PAYLOAD,
    )
    assert r.status_code == 401


def test_auth_rejects_missing_key_header(monkeypatch):
    monkeypatch.setenv("VOC_API_KEY", "nlp-secret")
    r = client.post("/analyze", json=_ANALYZE_PAYLOAD)
    assert r.status_code == 401


def test_health_exempt_from_auth(monkeypatch):
    monkeypatch.setenv("VOC_API_KEY", "nlp-secret")
    r = client.get("/health")
    assert r.status_code == 200
