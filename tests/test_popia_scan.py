"""Tests for processed-event POPIA scanning helpers."""

import json
from pathlib import Path

import pytest

from services.ingestion.app.popia_scan import PII_ENTITY_TYPES, scan_processed_dir


def test_scan_processed_dir_missing_returns_empty(tmp_path: Path) -> None:
    assert scan_processed_dir(tmp_path / "missing") == []


def test_scan_processed_dir_clean_jsonl_passes(tmp_path: Path) -> None:
    pytest.importorskip("presidio_analyzer")
    from services.ingestion.app.popia_scan import build_analyzer

    path = tmp_path / "events.jsonl"
    path.write_text(
        json.dumps(
            {
                "event_id": "sample_001",
                "raw_text_preview": (
                    "The login feature is broken and I cannot access my dashboard."
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    violations = scan_processed_dir(tmp_path, analyzer=build_analyzer())
    assert violations == []


def test_pii_entity_filter_excludes_person_and_location_noise() -> None:
    assert "PERSON" not in PII_ENTITY_TYPES
    assert "LOCATION" not in PII_ENTITY_TYPES
    assert "DATE_TIME" not in PII_ENTITY_TYPES
    assert "EMAIL_ADDRESS" in PII_ENTITY_TYPES
