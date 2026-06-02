"""Unit tests for the pure-logic helpers in scripts/ingest_case_studies.py.

We test slugify / clean / chunk because they run with no DB or model and must
behave deterministically — they decide case_id stability and retrieval quality.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ingest_case_studies.py"
_spec = importlib.util.spec_from_file_location("ingest_case_studies", _SCRIPT)
ingest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ingest)


def test_slugify_stable_case_id():
    assert ingest._slugify("FNB Compliance Win.pdf") == "fnb-compliance-win"
    assert ingest._slugify("Capitec_API__migration.PDF") == "capitec-api-migration"
    assert ingest._slugify("###.pdf") == "case"


def test_clean_text_collapses_whitespace():
    raw = "Hello\x00   world\n\n\n\nnext"
    cleaned = ingest._clean_text(raw)
    assert "\x00" not in cleaned
    assert "  " not in cleaned
    assert "\n\n\n" not in cleaned


def test_chunk_text_respects_size_and_overlap():
    text = "abcdefghij" * 200  # 2000 chars
    chunks = ingest._chunk_text(text, size=800, overlap=120)
    assert len(chunks) >= 2
    assert all(len(c) <= 800 for c in chunks)


def test_chunk_text_empty_returns_empty():
    assert ingest._chunk_text("") == []


def test_chunk_text_drops_tiny_fragments():
    # Below the 40-char minimum -> dropped entirely.
    assert ingest._chunk_text("tiny") == []
    # At/above the minimum -> kept as a single chunk.
    long_enough = "this sentence is comfortably over forty characters long"
    assert ingest._chunk_text(long_enough, size=800) == [long_enough]


def test_vec_literal_format():
    assert ingest._vec_literal([0.1, -0.2, 0.3]).startswith("[")
    assert ingest._vec_literal([0.1, -0.2, 0.3]).endswith("]")
    assert "," in ingest._vec_literal([0.1, 0.2])
