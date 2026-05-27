# VoC Decision Log

This file tracks every business decision that was directly influenced by the
weekly VoC digest or dashboard.  It provides audit evidence for the 90-day
plan target: "at least two decisions in the quarter traceable to VoC insights."

## How to add an entry

```bash
python scripts/log_decision.py \
    --decision "Short description of the decision taken" \
    --evidence "VoC signal that triggered it (taxonomy path, delta, ARR impact)" \
    --owner "Name (role)" \
    --outcome "What will be monitored / reviewed and when"
```

## Decision Table

| # | Date | Decision | VoC Evidence | Owner | Outcome / Tracking |
|---|------|----------|--------------|-------|--------------------|
<!-- ROWS -->
| 1 | 2026-05-26 | redesign checkout page | Billing.Payment.DuplicateCharge+12 this week | Stanley (System Design) | Monitor code progress for two weeks |

