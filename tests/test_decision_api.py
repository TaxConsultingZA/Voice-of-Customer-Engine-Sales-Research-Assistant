"""
Decision Intelligence Engine — HTTP API Tests
-----------------------------------------------
Validates all FastAPI endpoints using TestClient.
Covers /decide, /pending, /approve, /reject, /watchlist, /health, /admin/reset.
"""

import pytest
from fastapi.testclient import TestClient

from services.decision.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    client.post("/admin/reset")
    yield
    client.post("/admin/reset")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["service"] == "voc-decision"


# ---------------------------------------------------------------------------
# POST /decide — gate routing
# ---------------------------------------------------------------------------


def _decide(crisis_score: float, arr: float = 0.0, customer_id: str = "", actions=None):
    return client.post(
        "/decide",
        json={
            "crisis_score": crisis_score,
            "customer_arr": arr,
            "customer_id": customer_id,
            "actions": actions or ["notify_customer_success"],
        },
    )


def test_decide_green_returns_auto_resolved():
    r = _decide(0.1)
    assert r.status_code == 200
    assert r.json()["status"] == "auto_resolved"
    assert r.json()["escalation_tier"] == "green"


def test_decide_yellow_returns_auto_notify():
    r = _decide(0.45)
    assert r.status_code == 200
    assert r.json()["status"] == "auto_notify"
    assert r.json()["escalation_tier"] == "yellow"


def test_decide_red_returns_pending_approval():
    r = _decide(0.75)
    assert r.status_code == 200
    assert r.json()["status"] == "pending_approval"
    assert r.json()["escalation_tier"] == "red"
    assert r.json()["approved_actions"] == []
    assert len(r.json()["blocked_actions"]) > 0


def test_decide_high_arr_returns_pending_approval():
    r = _decide(0.45, arr=100_000, customer_id="enterprise_001")
    assert r.status_code == 200
    assert r.json()["status"] == "pending_approval"
    assert r.json()["escalation_tier"] == "watchlist"
    assert r.json()["watchlist_flag"] is True


def test_decide_response_contains_decision_id():
    r = _decide(0.5)
    assert "decision_id" in r.json()
    assert len(r.json()["decision_id"]) > 0


def test_decide_stores_crisis_score():
    r = _decide(0.62)
    assert r.json()["crisis_score"] == 0.62


# ---------------------------------------------------------------------------
# GET /pending
# ---------------------------------------------------------------------------


def test_pending_empty_on_fresh_state():
    r = client.get("/pending")
    assert r.status_code == 200
    assert r.json() == []


def test_pending_contains_red_decision():
    decide_r = _decide(0.8)
    decision_id = decide_r.json()["decision_id"]

    r = client.get("/pending")
    ids = [d["decision_id"] for d in r.json()]
    assert decision_id in ids


def test_pending_does_not_contain_green_decision():
    _decide(0.1)
    r = client.get("/pending")
    assert r.json() == []


# ---------------------------------------------------------------------------
# POST /approve/{decision_id}
# ---------------------------------------------------------------------------


def test_approve_releases_blocked_actions():
    decide_r = _decide(0.8, actions=["escalate_to_account_manager"])
    decision_id = decide_r.json()["decision_id"]

    r = client.post(f"/approve/{decision_id}", json={"approved_by": "cse_lead"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert "escalate_to_account_manager" in r.json()["approved_actions"]
    assert r.json()["resolved_by"] == "cse_lead"


def test_approve_removes_from_pending():
    decide_r = _decide(0.75)
    decision_id = decide_r.json()["decision_id"]
    client.post(f"/approve/{decision_id}", json={})

    pending_ids = [d["decision_id"] for d in client.get("/pending").json()]
    assert decision_id not in pending_ids


def test_approve_unknown_id_returns_404():
    r = client.post("/approve/nonexistent-id", json={})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /reject/{decision_id}
# ---------------------------------------------------------------------------


def test_reject_sets_rejected_status():
    decide_r = _decide(0.8)
    decision_id = decide_r.json()["decision_id"]

    r = client.post(
        f"/reject/{decision_id}",
        json={"rejected_by": "compliance_team", "notes": "Risk too high"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert r.json()["approved_actions"] == []
    assert r.json()["resolved_by"] == "compliance_team"
    assert r.json()["notes"] == "Risk too high"


def test_reject_removes_from_pending():
    decide_r = _decide(0.75)
    decision_id = decide_r.json()["decision_id"]
    client.post(f"/reject/{decision_id}", json={})

    pending_ids = [d["decision_id"] for d in client.get("/pending").json()]
    assert decision_id not in pending_ids


def test_reject_unknown_id_returns_404():
    r = client.post("/reject/ghost-id", json={})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Watchlist CRUD
# ---------------------------------------------------------------------------


def test_watchlist_initially_empty():
    r = client.get("/watchlist")
    assert r.status_code == 200
    assert r.json() == {}


def test_watchlist_add_customer():
    r = client.post("/watchlist", json={"customer_id": "vip_001", "arr": 200_000})
    assert r.status_code == 200
    assert r.json()["added"] == "vip_001"

    wl = client.get("/watchlist").json()
    assert "vip_001" in wl


def test_watchlist_remove_customer():
    client.post("/watchlist", json={"customer_id": "to_remove", "arr": 150_000})
    r = client.delete("/watchlist/to_remove")
    assert r.status_code == 200
    assert r.json()["removed"] == "to_remove"

    wl = client.get("/watchlist").json()
    assert "to_remove" not in wl


def test_watchlist_remove_missing_returns_404():
    r = client.delete("/watchlist/does_not_exist")
    assert r.status_code == 404


def test_watchlisted_customer_always_gets_pending():
    client.post("/watchlist", json={"customer_id": "manual_vip", "arr": 50_000})

    r = _decide(0.1, arr=50_000, customer_id="manual_vip")
    assert r.json()["status"] == "pending_approval"
    assert r.json()["watchlist_flag"] is True


# ---------------------------------------------------------------------------
# POST /admin/reset
# ---------------------------------------------------------------------------


def test_admin_reset_clears_pending():
    _decide(0.8)
    _decide(0.9)
    assert len(client.get("/pending").json()) == 2

    r = client.post("/admin/reset")
    assert r.status_code == 200
    assert client.get("/pending").json() == []


def test_admin_reset_clears_watchlist():
    client.post("/watchlist", json={"customer_id": "to_clear", "arr": 200_000})
    client.post("/admin/reset")
    assert client.get("/watchlist").json() == {}
