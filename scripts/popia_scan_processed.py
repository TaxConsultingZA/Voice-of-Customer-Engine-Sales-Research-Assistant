"""CI gate: scan processed UEC JSONL for leaked PII in complaint text."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ingestion.app.popia_scan import scan_processed_dir  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="POPIA scan on data/processed/*.jsonl")
    parser.add_argument(
        "--dir",
        default="data/processed",
        help="Directory containing processed JSONL event logs.",
    )
    parser.add_argument("--threshold", type=float, default=0.85)
    args = parser.parse_args()

    processed_dir = Path(args.dir)
    if not processed_dir.exists():
        print("No processed data directory found — skipping file scan.")
        return 0

    violations = scan_processed_dir(processed_dir, threshold=args.threshold)
    if violations:
        print("POPIA VIOLATION — PII detected in processed output:")
        print(json.dumps(violations, indent=2))
        return 1

    print("POPIA scan passed — no PII detected above threshold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
