"""POPIA scan helpers for processed UEC event logs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# High-confidence structured PII only — not PERSON/LOCATION/DATE, which false-positive
# on normal complaint language ("email" the word, product names, amounts).
PII_ENTITY_TYPES = frozenset(
    {
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "CREDIT_CARD",
        "US_SSN",
        "US_BANK_NUMBER",
        "IBAN_CODE",
        "IP_ADDRESS",
        "MEDICAL_LICENSE",
        "US_DRIVER_LICENSE",
        "US_PASSPORT",
        "UK_NHS",
    }
)


def build_analyzer(model: str | None = None) -> Any:
    """Return a Presidio AnalyzerEngine with SA phone patterns registered."""
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    spacy_model = model or os.getenv("SPACY_MODEL", "en_core_web_sm")
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": spacy_model}],
        }
    )
    engine = AnalyzerEngine(nlp_engine=provider.create_engine())
    sa_phone = PatternRecognizer(
        supported_entity="PHONE_NUMBER",
        patterns=[
            Pattern("sa_intl", r"\+27[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{4}", score=0.9),
            Pattern("sa_local", r"\b0\d{2}[\s\-]?\d{3}[\s\-]?\d{4}\b", score=0.85),
        ],
    )
    engine.registry.add_recognizer(sa_phone)
    return engine


def find_pii_hits(analyzer: Any, text: str, threshold: float = 0.85) -> list[Any]:
    """Return Presidio hits that look like real leaked PII, not NER noise."""
    results = analyzer.analyze(text=text, language="en", score_threshold=threshold)
    return [r for r in results if r.entity_type in PII_ENTITY_TYPES]


def scan_processed_dir(
    processed_dir: Path,
    *,
    threshold: float = 0.85,
    analyzer: Any | None = None,
) -> list[dict[str, Any]]:
    """
    Scan *.jsonl under processed_dir.

    Only inspects raw_text_preview per event line — not taxonomy paths, hashes,
    or numeric metadata that trigger Presidio false positives when scanning raw JSON.
    """
    violations: list[dict[str, Any]] = []

    if not processed_dir.exists():
        return violations

    engine = analyzer or build_analyzer()

    for path in sorted(processed_dir.glob("*.jsonl")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            text = str(event.get("raw_text_preview") or "").strip()
            if not text:
                continue
            hits = find_pii_hits(engine, text, threshold=threshold)
            if hits:
                violations.append(
                    {
                        "file": str(path),
                        "line": line_no,
                        "event_id": event.get("event_id"),
                        "entities": [
                            {
                                "type": r.entity_type,
                                "score": round(float(r.score), 3),
                                "text": text[r.start : r.end],
                            }
                            for r in hits
                        ],
                    }
                )
    return violations
