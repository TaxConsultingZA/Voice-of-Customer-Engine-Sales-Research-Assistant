import hashlib
import os
from typing import Literal

import jsonschema
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .adapters import NORMALIZERS, extract_customer_arr, extract_text
from .dead_letter import write_dead_letter
from .event_store import persist_event
from .uec import validate_uec_event

app = FastAPI(
    title="VoC Ingestion Service",
    description="Normalize Zendesk/WhatsApp/Email payloads into UEC events.",
    version="0.1.0",
)


class IngestRequest(BaseModel):
    source: Literal["email", "whatsapp", "zendesk"]
    payload: dict = Field(default_factory=dict)


class IngestResponse(BaseModel):
    accepted: bool
    event_id: str
    channel: str
    taxonomy_path: str
    redaction_applied: bool
    persisted: bool


@app.get("/health")
def health():
    return {"status": "ok", "service": "voc-ingestion", "version": "0.1.0"}


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _call_redactor_scan(text: str, timeout_seconds: float) -> dict:
    redactor_url = os.getenv("REDACTOR_URL", "http://sa-redactor:8080")
    response = requests.post(
        f"{redactor_url.rstrip('/')}/scan",
        json={"text": text},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def _call_redactor_redact(text: str, timeout_seconds: float) -> dict:
    redactor_url = os.getenv("REDACTOR_URL", "http://sa-redactor:8080")
    response = requests.post(
        f"{redactor_url.rstrip('/')}/redact",
        json={"text": text},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def _call_nlp_analyze(text: str, channel: str, customer_arr: float, timeout_seconds: float) -> dict:
    nlp_url = os.getenv("NLP_URL", "http://nlp:8081")
    response = requests.post(
        f"{nlp_url.rstrip('/')}/analyze",
        json={"text": text, "channel": channel, "customer_arr": customer_arr},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


@app.post("/api/events", response_model=IngestResponse, status_code=201)
def ingest_event(req: IngestRequest):
    normalizer = NORMALIZERS[req.source]
    raw_text = extract_text(req.source, req.payload)
    customer_arr = extract_customer_arr(req.payload)
    text_for_nlp = raw_text
    redaction_applied = False
    enable_enrichment = _env_bool("INGESTION_ENABLE_ENRICHMENT", True)
    fail_open = _env_bool("INGESTION_FAIL_OPEN", True)
    timeout_seconds = float(os.getenv("INGESTION_HTTP_TIMEOUT_SECONDS", "2.0"))

    try:
        event = normalizer(req.payload)

        if enable_enrichment:
            try:
                scan_result = _call_redactor_scan(raw_text, timeout_seconds=timeout_seconds)
                if scan_result.get("has_pii"):
                    redact_result = _call_redactor_redact(raw_text, timeout_seconds=timeout_seconds)
                    text_for_nlp = str(redact_result.get("redacted_text", raw_text))
                    redaction_applied = True

                nlp_result = _call_nlp_analyze(
                    text_for_nlp,
                    channel=event["channel"],
                    customer_arr=customer_arr,
                    timeout_seconds=timeout_seconds,
                )
                event["sentiment"] = {
                    "polarity": float(nlp_result["sentiment_polarity"]),
                    "confidence": float(nlp_result["sentiment_confidence"]),
                }
                event["taxonomy_path"] = str(nlp_result["taxonomy_path"])
                event["intent"] = str(nlp_result["intent"])
                event["language_detected"] = "en"
                event["model_version"] = "sentiment-sa-v0.1.0"
                event["raw_text_hash"] = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
                event["arr_linkage"] = {
                    "account_arr": customer_arr,
                    "at_risk_flag": bool(nlp_result.get("at_risk_flag", False)),
                }
            except requests.RequestException as exc:
                if not fail_open:
                    raise ValueError(f"Downstream enrichment failed: {exc}") from exc

        validate_uec_event(event)
        persist_event(event)
    except ValueError as exc:
        write_dead_letter(req.source, req.payload, reason=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        reason = f"Event persistence failed: {exc}"
        write_dead_letter(req.source, req.payload, reason=reason)
        raise HTTPException(status_code=500, detail=reason) from exc
    except (jsonschema.ValidationError, jsonschema.SchemaError) as exc:
        reason = f"UEC validation failed: {exc.message}"
        write_dead_letter(req.source, req.payload, reason=reason)
        raise HTTPException(status_code=422, detail=reason) from exc

    return IngestResponse(
        accepted=True,
        event_id=event["event_id"],
        channel=event["channel"],
        taxonomy_path=event["taxonomy_path"],
        redaction_applied=redaction_applied,
        persisted=True,
    )
