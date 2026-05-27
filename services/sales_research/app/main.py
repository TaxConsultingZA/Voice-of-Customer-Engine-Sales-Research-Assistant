"""
FastAPI surface for the Sales Research Assistant.

Mirrors services/nlp/app/main.py for consistency. Exposes:
    POST /api/briefs           generate (or cache-hit) a brief
    GET  /health               liveness probe (auth-exempt)

X-Api-Key auth comes from the shared auth module pattern used by every other
service in this repo — copy services/nlp/app/auth.py into this service when
moving past skeleton (each service keeps its own copy so it stays deployable
in isolation).

Wire-up checklist (Wei, Task 3):
- Add services/sales_research/Dockerfile (copy from services/nlp/Dockerfile).
- Add services/sales_research/requirements.txt (fastapi, uvicorn, requests,
  pydantic, psycopg2-binary, sentence-transformers).
- Add to docker-compose.staging.yml with port 8084.
- Add new ACR push + SSH deploy step in .github/workflows/ci.yml Stage 8.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI

from .auth import require_api_key
from .contracts import BriefRequest, SalesBrief
from .pipeline import run_pipeline

app = FastAPI(
    title="VoC Sales Research Assistant",
    description="Generate a one-page pre-call brief from public web + internal case studies.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "sales-research", "version": "0.1.0"}


@app.post("/api/briefs", response_model=SalesBrief, dependencies=[Depends(require_api_key)])
def create_brief(req: BriefRequest, force_refresh: bool = False) -> SalesBrief:
    record = run_pipeline(req, force_refresh=force_refresh)
    return record.brief_payload
