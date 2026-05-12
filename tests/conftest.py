import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def uec_schema():
    with (ROOT / "schemas" / "uec_v1.json").open() as f:
        return json.load(f)


@pytest.fixture(scope="session")
def sa_slang():
    with (ROOT / "data" / "sa_slang.json").open() as f:
        return json.load(f)


@pytest.fixture
def sample_uec_event():
    """Minimal valid UEC event — Authentication.Login.PasswordReset scenario."""
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2024-01-15T09:00:00Z",
        "channel": "email",
        "customer_id": "a" * 64,  # SHA-256 length
        "sentiment": {"polarity": -0.75, "confidence": 0.92},
        "taxonomy_path": "Authentication.Login.PasswordReset",
        "entities": [{"type": "FEATURE", "value": "password reset"}],
        "arr_linkage": {"account_arr": 150000, "at_risk_flag": True},
        "intent": "complaint",
        "language_detected": "en",
        "model_version": "sentiment-sa-v2.1.3",
        "raw_text_hash": "b" * 64,
    }
