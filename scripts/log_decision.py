"""
Append a VoC-driven business decision to data/reports/decision_log.md.

Every decision logged here counts towards the 90-day plan target:
"at least two decisions in the quarter traceable to VoC insights."

Usage:
    python scripts/log_decision.py \\
        --decision "Cut SMB pricing by 15%" \\
        --evidence "Billing.Subscription.Cancellation +12 this week (highest spike in 30 days)" \\
        --owner "Jane (PM)" \\
        --outcome "Monitor monthly churn rate — review in 30 days"
"""

import argparse
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "reports" / "decision_log.md"


def _next_row_number(log_text: str) -> int:
    count = sum(1 for line in log_text.splitlines() if line.startswith("| ") and line[2].isdigit())
    return count + 1


def append_decision(
    decision: str,
    evidence: str,
    owner: str,
    outcome: str,
) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not LOG_PATH.exists():
        LOG_PATH.write_text(_TEMPLATE, encoding="utf-8")
        print(f"Created decision log at {LOG_PATH}")

    log_text = LOG_PATH.read_text(encoding="utf-8")
    row_num = _next_row_number(log_text)
    date = datetime.date.today().isoformat()

    new_row = (
        f"| {row_num} "
        f"| {date} "
        f"| {decision} "
        f"| {evidence} "
        f"| {owner} "
        f"| {outcome} |\n"
    )

    marker = "<!-- ROWS -->"
    if marker in log_text:
        updated = log_text.replace(marker, marker + "\n" + new_row, 1)
    else:
        updated = log_text.rstrip() + "\n" + new_row

    LOG_PATH.write_text(updated, encoding="utf-8")
    print(f"Decision #{row_num} logged to {LOG_PATH}")


_TEMPLATE = """\
# VoC Decision Log

This file tracks every business decision that was directly influenced by the
weekly VoC digest or dashboard.  It provides audit evidence for the 90-day
plan target: "at least two decisions in the quarter traceable to VoC insights."

## How to add an entry

```bash
python scripts/log_decision.py \\
    --decision "Short description of the decision taken" \\
    --evidence "VoC signal that triggered it (taxonomy path, delta, ARR impact)" \\
    --owner "Name (role)" \\
    --outcome "What will be monitored / reviewed and when"
```

## Decision Table

| # | Date | Decision | VoC Evidence | Owner | Outcome / Tracking |
|---|------|----------|--------------|-------|--------------------|
<!-- ROWS -->
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Log a VoC-driven business decision.")
    parser.add_argument("--decision", required=True, help="Decision taken.")
    parser.add_argument(
        "--evidence",
        required=True,
        help="VoC signal (taxonomy spike, ARR impact, etc.) that drove the decision.",
    )
    parser.add_argument("--owner", required=True, help="Person / role who made the decision.")
    parser.add_argument(
        "--outcome",
        required=True,
        help="What will be tracked to measure success.",
    )
    args = parser.parse_args()

    for field, value in [
        ("decision", args.decision),
        ("evidence", args.evidence),
        ("owner", args.owner),
        ("outcome", args.outcome),
    ]:
        if "|" in value:
            sys.exit(f"ERROR: --{field} must not contain '|' (breaks Markdown table).")

    append_decision(
        decision=args.decision,
        evidence=args.evidence,
        owner=args.owner,
        outcome=args.outcome,
    )


if __name__ == "__main__":
    main()
