"""
SA Regional Latency Tests
--------------------------
Validates that staging deployments in af-south-1 (Cape Town) or
southafricanorth (Johannesburg) meet latency SLAs.

Runs only on pushes to main (requires STAGING_API_URL secret).
See SYSTEM_PROMPT §3.7 for targets:
  - P95 < 500ms for event ingestion
  - P99 < 1000ms for NLP processing
"""

import copy
import os
import time

import numpy as np
import pytest
import requests

STAGING_API_URL = os.getenv("STAGING_API_URL", "http://localhost:8000")
SAMPLE_COUNT = 100
P95_BUDGET_SECONDS = 0.5
P99_BUDGET_SECONDS = 1.0


@pytest.fixture(scope="module")
def latency_event(sample_uec_event):
    return copy.deepcopy(sample_uec_event)


@pytest.mark.integration
def test_event_ingestion_p95_latency(latency_event):
    """P95 < 500ms — measured from SA network via af-south-1 endpoint."""
    endpoint = f"{STAGING_API_URL}/api/events"
    latencies = []

    for _ in range(SAMPLE_COUNT):
        start = time.perf_counter()
        response = requests.post(endpoint, json=latency_event, timeout=5)
        latencies.append(time.perf_counter() - start)
        assert response.status_code in (200, 201), f"Unexpected status: {response.status_code}"

    p95 = float(np.percentile(latencies, 95))
    p99 = float(np.percentile(latencies, 99))

    assert p95 < P95_BUDGET_SECONDS, (
        f"P95 latency {p95 * 1000:.0f}ms exceeds 500ms budget — " f"check af-south-1 region routing"
    )
    assert p99 < P99_BUDGET_SECONDS, f"P99 latency {p99 * 1000:.0f}ms exceeds 1000ms NLP budget"


@pytest.mark.integration
def test_sa_redactor_health_check():
    """sa_redactor /health must return 200 before any pipeline stage runs."""
    redactor_url = os.getenv("REDACTOR_URL", f"{STAGING_API_URL.rstrip('/')}/redactor")
    response = requests.get(f"{redactor_url}/health", timeout=5)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
