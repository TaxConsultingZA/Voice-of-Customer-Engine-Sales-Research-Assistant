import os
from functools import lru_cache

from fastapi import FastAPI
from pydantic import BaseModel, Field
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

app = FastAPI(
    title="SA Redactor",
    description="POPIA-compliant PII detection and redaction service for the VoC Engine.",
    version="1.0.0",
)

from presidio_analyzer.nlp_engine import NlpEngineProvider

THRESHOLD = float(os.getenv("PRESIDIO_THRESHOLD", "0.85"))
SPACY_MODEL = os.getenv("SPACY_MODEL", "en_core_web_lg")


@lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerEngine:
    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": SPACY_MODEL}],
    })
    engine = AnalyzerEngine(nlp_engine=provider.create_engine())
    # Regex-based SA phone recognizer — catches +27 and 0XX formats reliably.
    sa_phone = PatternRecognizer(
        supported_entity="PHONE_NUMBER",
        patterns=[
            Pattern("sa_intl", r"\+27[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{4}", score=0.9),
            Pattern("sa_local", r"\b0\d{2}[\s\-]?\d{3}[\s\-]?\d{4}\b", score=0.85),
        ],
    )
    engine.registry.add_recognizer(sa_phone)
    return engine


@lru_cache(maxsize=1)
def get_anonymizer() -> AnonymizerEngine:
    return AnonymizerEngine()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class RedactRequest(BaseModel):
    text: str = Field(..., min_length=1)
    threshold: float = Field(default=THRESHOLD, ge=0.0, le=1.0)
    language: str = Field(default="en")


class RedactResponse(BaseModel):
    redacted_text: str
    entities_found: int
    original_length: int


class ScanRequest(BaseModel):
    text: str = Field(..., min_length=1)
    threshold: float = Field(default=THRESHOLD, ge=0.0, le=1.0)


class EntityHit(BaseModel):
    entity_type: str
    score: float
    start: int
    end: int


class ScanResponse(BaseModel):
    has_pii: bool
    entities: list[EntityHit]
    max_confidence: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    """Liveness probe — CI/CD pipeline checks this before any data processing."""
    return {"status": "ok", "service": "sa-redactor", "threshold": THRESHOLD}


@app.post("/redact", response_model=RedactResponse)
def redact(req: RedactRequest):
    """Redact PII from text. Returns anonymised text with entity count."""
    results = get_analyzer().analyze(
        text=req.text, language=req.language, score_threshold=req.threshold
    )
    anonymised = get_anonymizer().anonymize(text=req.text, analyzer_results=results)
    return RedactResponse(
        redacted_text=anonymised.text,
        entities_found=len(results),
        original_length=len(req.text),
    )


@app.post("/scan", response_model=ScanResponse)
def scan(req: ScanRequest):
    """Scan text for PII without redacting. Used by the CI/CD POPIA gate."""
    results = get_analyzer().analyze(
        text=req.text, language="en", score_threshold=req.threshold
    )
    entities = [
        EntityHit(entity_type=r.entity_type, score=r.score, start=r.start, end=r.end)
        for r in results
    ]
    max_confidence = max((r.score for r in results), default=0.0)
    return ScanResponse(
        has_pii=len(results) > 0,
        entities=entities,
        max_confidence=max_confidence,
    )
