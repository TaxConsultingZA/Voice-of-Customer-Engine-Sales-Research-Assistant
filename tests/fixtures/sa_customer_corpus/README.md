# SA Customer Corpus

**Required size:** 500 labelled samples minimum  
**Gate:** F1 ≥ 0.94 — build fails if score drops below threshold  
**Location referenced by:** `tests/test_sentiment_accuracy.py`

## Format

Each file is a JSON object:

```json
{
  "id": "sample_001",
  "text": "Eish, the login has been broken for two days, this is unacceptable",
  "label": "negative",
  "channel": "email",
  "language": "en",
  "contains_slang": true,
  "annotator": "human"
}
```

**Labels:** `positive` | `negative` | `neutral`

## Corpus Guidelines

- Minimum 40% real-world SA colloquialisms (eish, lekker, howzit, etc.)
- At least 3 of the 12 official languages represented
- Balanced across channels: email, chat, WhatsApp, call transcripts
- No raw PII — all samples must be pre-redacted before committing
- Annotated by at least 2 human reviewers with inter-annotator agreement > 0.85

## Status

Corpus not yet populated. Coordinate with the data science team to source and label samples.  
Do NOT commit real customer data — synthetic or fully anonymised samples only.
