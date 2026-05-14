from fastapi import FastAPI
from pydantic import BaseModel, Field

from .pipeline import process_complaint

app = FastAPI(
    title="VoC NLP Service",
    description="SA-aware NLP pipeline — sentiment, taxonomy, intent, crisis scoring.",
    version="1.0.0",
)


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    customer_arr: float = Field(default=0.0, ge=0)
    channel: str = Field(default="email")
    anomaly_topic: str | None = None
    anomaly_count: int | None = Field(default=None, ge=0)
    anomaly_baseline_mean: float | None = Field(default=None, ge=0)
    anomaly_baseline_std: float | None = Field(default=None, ge=0)


class AnalyzeResponse(BaseModel):
    crisis_score: float
    intent: str
    taxonomy_path: str
    sentiment_polarity: float
    sentiment_confidence: float
    at_risk_flag: bool
    requires_approval: bool
    actions: list[str]
    routing: list[str]
    contains_slang: bool
    anomaly_sigma: float | None = None
    anomaly_is_detected: bool
    anomaly_recommended_action: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "voc-nlp", "version": "1.0.0"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    result = process_complaint(req.model_dump())
    return AnalyzeResponse(
        crisis_score=result.crisis_score,
        intent=result.intent,
        taxonomy_path=result.taxonomy_path,
        sentiment_polarity=result.sentiment_polarity,
        sentiment_confidence=result.sentiment_confidence,
        at_risk_flag=result.at_risk_flag,
        requires_approval=result.requires_approval,
        actions=result.actions,
        routing=result.routing,
        contains_slang=result.contains_slang,
        anomaly_sigma=result.anomaly_sigma,
        anomaly_is_detected=result.anomaly_is_detected,
        anomaly_recommended_action=result.anomaly_recommended_action,
    )
