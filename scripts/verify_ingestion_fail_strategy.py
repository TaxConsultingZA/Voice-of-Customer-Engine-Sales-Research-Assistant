import os
import sys
from pathlib import Path

import requests
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _set_env(monkey: dict[str, str]) -> dict[str, str | None]:
    previous = {}
    for key, value in monkey.items():
        previous[key] = os.getenv(key)
        os.environ[key] = value
    return previous


def _restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _stub_downstream_failure(main_module) -> tuple[object, object]:
    original_scan = main_module._call_redactor_scan
    original_redact = main_module._call_redactor_redact

    def broken_scan(text: str, timeout_seconds: float) -> dict:
        raise requests.RequestException("simulated redactor outage")

    main_module._call_redactor_scan = broken_scan
    return original_scan, original_redact


def _restore_downstream(main_module, original_scan, original_redact) -> None:
    main_module._call_redactor_scan = original_scan
    main_module._call_redactor_redact = original_redact


def verify_fail_modes() -> int:
    from services.ingestion.app import main

    client = TestClient(main.app)
    payload = {
        "source": "email",
        "payload": {
            "text": "I cannot log in to my account.",
            "customer_id": "user-123",
            "customer_arr": 150000,
        },
    }

    original_scan, original_redact = _stub_downstream_failure(main)
    failures = 0
    try:
        prev = _set_env(
            {
                "INGESTION_ENABLE_ENRICHMENT": "true",
                "INGESTION_FAIL_OPEN": "true",
            }
        )
        try:
            resp = client.post("/api/events", json=payload)
            if resp.status_code != 201:
                print(f"[FAIL] fail-open expected 201, got {resp.status_code}")
                failures += 1
            else:
                print("[PASS] fail-open mode keeps ingestion available (201).")
        finally:
            _restore_env(prev)

        prev = _set_env(
            {
                "INGESTION_ENABLE_ENRICHMENT": "true",
                "INGESTION_FAIL_OPEN": "false",
            }
        )
        try:
            resp = client.post("/api/events", json=payload)
            if resp.status_code != 400:
                print(f"[FAIL] fail-closed expected 400, got {resp.status_code}")
                failures += 1
            else:
                print("[PASS] fail-closed mode blocks ingestion when downstream fails (400).")
        finally:
            _restore_env(prev)
    finally:
        _restore_downstream(main, original_scan, original_redact)

    if failures == 0:
        print("All fail strategy checks passed.")
        return 0

    print(f"Fail strategy checks failed: {failures}")
    return 1


if __name__ == "__main__":
    raise SystemExit(verify_fail_modes())
