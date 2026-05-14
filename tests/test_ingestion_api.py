import json

import pytest
import requests
from fastapi.testclient import TestClient

from services.ingestion.app import main
from services.ingestion.app.main import app


@pytest.fixture(autouse=True)
def _disable_external_enrichment(monkeypatch):
    monkeypatch.setenv("INGESTION_ENABLE_ENRICHMENT", "false")


def test_email_payload_is_normalized_and_accepted():
    client = TestClient(app)

    response = client.post(
        "/api/events",
        json={
            "source": "email",
            "payload": {
                "text": "I cannot log in to my account.",
                "customer_id": "cust-123",
                "timestamp": "2026-04-28T09:00:00Z",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["accepted"] is True
    assert body["channel"] == "email"
    assert body["taxonomy_path"].startswith("Authentication.")
    assert body["redaction_applied"] is False
    assert body["persisted"] is True


def test_zendesk_payload_maps_to_api_channel():
    client = TestClient(app)

    response = client.post(
        "/api/events",
        json={
            "source": "zendesk",
            "payload": {
                "description": "Payment failed at checkout.",
                "requester_id": "zd-user-99",
                "created_at": "2026-04-28T09:00:00Z",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["accepted"] is True
    assert body["channel"] == "api"
    assert body["taxonomy_path"].startswith("Billing.")
    assert body["redaction_applied"] is False
    assert body["persisted"] is True


def test_invalid_payload_goes_to_dead_letter(tmp_path, monkeypatch):
    dead_letter_path = tmp_path / "dead_letter.jsonl"
    monkeypatch.setenv("INGESTION_DEAD_LETTER_PATH", str(dead_letter_path))
    client = TestClient(app)

    response = client.post(
        "/api/events",
        json={
            "source": "email",
            "payload": {
                "text": "",
                "customer_id": "cust-123",
            },
        },
    )

    assert response.status_code == 400
    assert dead_letter_path.exists()
    lines = dead_letter_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["source"] == "email"
    assert "missing non-empty text" in record["reason"]


def test_uec_validation_failure_returns_422(tmp_path, monkeypatch):
    dead_letter_path = tmp_path / "dead_letter_schema.jsonl"
    monkeypatch.setenv("INGESTION_DEAD_LETTER_PATH", str(dead_letter_path))
    client = TestClient(app)

    response = client.post(
        "/api/events",
        json={
            "source": "email",
            "payload": {
                "text": "Please help with this request.",
                "customer_id": "cust-123",
                "sentiment_polarity": 2.0,
            },
        },
    )

    assert response.status_code == 422
    assert dead_letter_path.exists()


def test_enrichment_calls_redactor_and_nlp(monkeypatch):
    monkeypatch.setenv("INGESTION_ENABLE_ENRICHMENT", "true")
    client = TestClient(app)

    def fake_scan(text: str, timeout_seconds: float) -> dict:
        assert "log in" in text.lower()
        return {"has_pii": True}

    def fake_redact(text: str, timeout_seconds: float) -> dict:
        return {"redacted_text": "I cannot login, my number is [REDACTED]"}

    def fake_analyze(text: str, channel: str, customer_arr: float, timeout_seconds: float) -> dict:
        assert channel == "email"
        assert customer_arr == 150000.0
        return {
            "sentiment_polarity": -0.8,
            "sentiment_confidence": 0.92,
            "taxonomy_path": "Authentication.Login.Failure",
            "intent": "complaint",
            "at_risk_flag": True,
        }

    monkeypatch.setattr(main, "_call_redactor_scan", fake_scan)
    monkeypatch.setattr(main, "_call_redactor_redact", fake_redact)
    monkeypatch.setattr(main, "_call_nlp_analyze", fake_analyze)

    response = client.post(
        "/api/events",
        json={
            "source": "email",
            "payload": {
                "text": "I cannot log in and my number is +27 82 123 4567",
                "customer_id": "cust-123",
                "customer_arr": 150000,
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["accepted"] is True
    assert body["taxonomy_path"] == "Authentication.Login.Failure"
    assert body["redaction_applied"] is True


def test_fail_open_allows_ingestion_when_enrichment_down(monkeypatch):
    monkeypatch.setenv("INGESTION_ENABLE_ENRICHMENT", "true")
    monkeypatch.setenv("INGESTION_FAIL_OPEN", "true")
    client = TestClient(app)

    def broken_scan(text: str, timeout_seconds: float) -> dict:
        raise requests.RequestException("redactor unavailable")

    monkeypatch.setattr(main, "_call_redactor_scan", broken_scan)

    response = client.post(
        "/api/events",
        json={
            "source": "email",
            "payload": {
                "text": "I cannot log in to my account.",
                "customer_id": "cust-123",
            },
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["accepted"] is True
    assert body["redaction_applied"] is False


def test_fail_closed_rejects_when_enrichment_down(tmp_path, monkeypatch):
    dead_letter_path = tmp_path / "dead_letter_downstream.jsonl"
    monkeypatch.setenv("INGESTION_DEAD_LETTER_PATH", str(dead_letter_path))
    monkeypatch.setenv("INGESTION_ENABLE_ENRICHMENT", "true")
    monkeypatch.setenv("INGESTION_FAIL_OPEN", "false")
    client = TestClient(app)

    def broken_scan(text: str, timeout_seconds: float) -> dict:
        raise requests.RequestException("redactor unavailable")

    monkeypatch.setattr(main, "_call_redactor_scan", broken_scan)

    response = client.post(
        "/api/events",
        json={
            "source": "email",
            "payload": {
                "text": "I cannot log in to my account.",
                "customer_id": "cust-123",
            },
        },
    )

    assert response.status_code == 400
    assert dead_letter_path.exists()


def test_successful_ingestion_persists_event_log(tmp_path, monkeypatch):
    event_log_path = tmp_path / "uec_events.jsonl"
    monkeypatch.setenv("INGESTION_EVENT_LOG_PATH", str(event_log_path))
    client = TestClient(app)

    response = client.post(
        "/api/events",
        json={
            "source": "email",
            "payload": {
                "text": "My payment keeps failing at checkout.",
                "customer_id": "cust-abc",
            },
        },
    )

    assert response.status_code == 201
    assert event_log_path.exists()
    lines = event_log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["channel"] == "email"
    assert "event_id" in event
