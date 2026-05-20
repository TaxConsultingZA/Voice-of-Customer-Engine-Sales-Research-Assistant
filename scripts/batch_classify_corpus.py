"""Batch-classify the synthetic SA customer corpus through the live Claude pipeline.

Writes one UEC-shaped JSON event per line to data/processed/uec_events.jsonl so
downstream digest, anomaly, and trend tooling have real signal to consume.

The script is deterministic: customer_id, customer_arr, and event timestamps
are derived from each sample's id, so re-runs produce a stable event log.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Synthetic ARR tiers that cover Green / Yellow / Red governance and the
# digest "high ARR at-risk accounts" section.
ARR_TIERS = (5_000.0, 15_000.0, 35_000.0, 80_000.0, 150_000.0, 250_000.0)
CUSTOMER_POOL = 137


def _hash_int(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest(), 16)


def _synthesize_customer(sample_id: str) -> tuple[str, float]:
    h = _hash_int(sample_id)
    pool_slot = h % CUSTOMER_POOL
    customer_seed = f"cust_pool_{pool_slot:04d}"
    customer_id = hashlib.sha256(customer_seed.encode("utf-8")).hexdigest()
    arr = ARR_TIERS[h % len(ARR_TIERS)]
    return customer_id, arr


def _synthesize_timestamp(sample_id: str, base: datetime, window_days: int) -> str:
    h = _hash_int(sample_id)
    minutes = h % (window_days * 24 * 60)
    ts = base - timedelta(minutes=minutes)
    return ts.isoformat().replace("+00:00", "Z")


def _load_samples(corpus_dir: Path, limit: int | None) -> list[dict]:
    files = sorted(corpus_dir.glob("sample_*.json"))
    samples: list[dict] = []
    for path in files:
        samples.append(json.loads(path.read_text(encoding="utf-8")))
    if limit is not None and limit > 0:
        samples = samples[:limit]
    return samples


def _build_event(
    sample: dict,
    process_complaint,
    customer_id: str,
    customer_arr: float,
    timestamp: str,
) -> dict:
    text = str(sample.get("text", ""))
    channel = str(sample.get("channel", "api"))
    result = process_complaint({"text": text, "customer_arr": customer_arr, "channel": channel})

    return {
        "event_id": str(sample.get("id", "")),
        "timestamp": timestamp,
        "channel": channel,
        "customer_id": customer_id,
        "language_detected": result.language_detected,
        "intent": result.intent,
        "taxonomy_path": result.taxonomy_path,
        "sentiment": {
            "polarity": result.sentiment_polarity,
            "confidence": result.sentiment_confidence,
        },
        "arr_linkage": {
            "account_arr": customer_arr,
            "at_risk_flag": bool(result.at_risk_flag),
        },
        "crisis_score": result.crisis_score,
        "escalation_triggered": bool(result.escalation_triggered),
        "requires_approval": bool(result.requires_approval),
        "actions": list(result.actions),
        "routing": list(result.routing),
        "llm_mode": result.llm_mode,
        "llm_fallback_used": bool(result.llm_fallback_used),
        "llm_shadow_label": result.llm_shadow_label,
        "raw_text_preview": text[:160],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the live Claude pipeline over the synthetic SA corpus."
    )
    parser.add_argument(
        "--corpus-dir",
        default="tests/fixtures/sa_customer_corpus",
        help="Directory containing sample_*.json files.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/uec_events.jsonl",
        help="UEC event log output path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="If > 0, only process the first N samples (useful for smoke checks).",
    )
    parser.add_argument(
        "--mode",
        choices=("llm", "shadow", "rules"),
        default="llm",
        help="Classifier mode for this run.",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=14,
        help="Spread synthetic event timestamps across this many days back from now.",
    )
    parser.add_argument(
        "--throttle-ms",
        type=int,
        default=0,
        help="Optional pause between LLM calls (milliseconds) to avoid hammering the API.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to the existing event log instead of truncating it.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Print a progress line every N samples.",
    )
    args = parser.parse_args()

    os.environ["NLP_CLASSIFIER_MODE"] = args.mode

    from services.nlp.app.pipeline import process_complaint

    corpus_dir = Path(args.corpus_dir)
    samples = _load_samples(corpus_dir, args.limit or None)
    if not samples:
        print(f"No samples found under {corpus_dir}")
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not args.append:
        output_path.write_text("", encoding="utf-8")

    base = datetime.now(UTC)
    processed = 0
    fallback_count = 0
    high_risk_count = 0
    started = time.time()

    with output_path.open("a", encoding="utf-8") as f:
        for idx, sample in enumerate(samples, start=1):
            sample_id = str(sample.get("id", f"sample_{idx:03d}"))
            customer_id, customer_arr = _synthesize_customer(sample_id)
            timestamp = _synthesize_timestamp(sample_id, base, max(args.window_days, 1))

            try:
                event = _build_event(
                    sample,
                    process_complaint,
                    customer_id=customer_id,
                    customer_arr=customer_arr,
                    timestamp=timestamp,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[ERROR] sample={sample_id} failed: {exc}")
                continue

            f.write(json.dumps(event, ensure_ascii=True) + "\n")
            processed += 1
            if event.get("llm_fallback_used"):
                fallback_count += 1
            if event.get("arr_linkage", {}).get("at_risk_flag"):
                high_risk_count += 1

            if args.progress_every > 0 and idx % args.progress_every == 0:
                elapsed = time.time() - started
                rate = processed / elapsed if elapsed > 0 else 0.0
                remaining = (len(samples) - idx) / rate if rate > 0 else float("inf")
                print(
                    f"  progress {idx}/{len(samples)} | rate {rate:.2f}/s | "
                    f"eta ~{remaining/60:.1f} min | fallback {fallback_count} | "
                    f"at_risk {high_risk_count}"
                )

            if args.throttle_ms > 0:
                time.sleep(args.throttle_ms / 1000.0)

    elapsed = time.time() - started
    print("---")
    print(f"Wrote {processed} events to {output_path}")
    print(f"Mode: {args.mode}")
    print(f"LLM fallback events: {fallback_count}")
    print(f"At-risk events: {high_risk_count}")
    print(f"Elapsed: {elapsed/60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
