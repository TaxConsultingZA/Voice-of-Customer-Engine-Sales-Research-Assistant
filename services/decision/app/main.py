"""
VoC Decision Intelligence Engine — HTTP API.
Port 8082
"""

from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from .auth import require_api_key
from .engine import (
    approve_decision,
    clear_state,
    decide,
    get_watchlist,
    list_pending,
    reject_decision,
    restore_state_from_db,
)
from .models import DecisionRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    restore_state_from_db()
    yield


app = FastAPI(
    title="VoC Decision Intelligence Engine",
    description="Governance layer — routes, blocks, or approves automated actions based on crisis score.",  # noqa: E501
    version="1.0.0",
    lifespan=lifespan,
)


# ── Pydantic request/response models ──────────────────────────────────────────


class DecisionPayload(BaseModel):
    text: str = ""
    crisis_score: float
    intent: str = "complaint"
    taxonomy_path: str = ""
    customer_id: str = ""
    customer_arr: float = 0.0
    actions: list[str] = []
    routing: list[str] = []
    sentiment_polarity: float = 0.0


class ApprovePayload(BaseModel):
    approved_by: str = "human_agent"


class RejectPayload(BaseModel):
    rejected_by: str = "human_agent"
    notes: str = ""


class WatchlistAddPayload(BaseModel):
    customer_id: str
    arr: float


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok", "service": "voc-decision", "version": "1.0.0"}


@app.post("/decide", dependencies=[Depends(require_api_key)])
def make_decision(payload: DecisionPayload):
    req = DecisionRequest(
        text=payload.text,
        crisis_score=payload.crisis_score,
        intent=payload.intent,
        taxonomy_path=payload.taxonomy_path,
        customer_id=payload.customer_id,
        customer_arr=payload.customer_arr,
        actions=payload.actions,
        routing=payload.routing,
        sentiment_polarity=payload.sentiment_polarity,
    )
    return asdict(decide(req))


@app.get("/pending", dependencies=[Depends(require_api_key)])
def pending_decisions():
    return [asdict(d) for d in list_pending()]


@app.post("/approve/{decision_id}", dependencies=[Depends(require_api_key)])
def approve(decision_id: str, payload: ApprovePayload):
    result = approve_decision(decision_id, payload.approved_by)
    if not result:
        raise HTTPException(
            status_code=404, detail=f"Decision {decision_id} not found in pending queue"
        )
    return asdict(result)


@app.post("/reject/{decision_id}", dependencies=[Depends(require_api_key)])
def reject(decision_id: str, payload: RejectPayload):
    result = reject_decision(decision_id, payload.rejected_by, payload.notes)
    if not result:
        raise HTTPException(
            status_code=404, detail=f"Decision {decision_id} not found in pending queue"
        )
    return asdict(result)


@app.get("/watchlist", dependencies=[Depends(require_api_key)])
def watchlist_entries():
    return get_watchlist().list_entries()


@app.post("/watchlist", dependencies=[Depends(require_api_key)])
def add_to_watchlist(payload: WatchlistAddPayload):
    get_watchlist().add(payload.customer_id, payload.arr)
    return {"added": payload.customer_id, "arr": payload.arr}


@app.delete("/watchlist/{customer_id}", dependencies=[Depends(require_api_key)])
def remove_from_watchlist(customer_id: str):
    removed = get_watchlist().remove(customer_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id!r} not on watchlist")
    return {"removed": customer_id}


@app.post("/admin/reset", dependencies=[Depends(require_api_key)])
def reset_state():
    """Dev/test endpoint — clears all in-memory state."""
    clear_state()
    return {"status": "reset"}
