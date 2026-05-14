# Voice of Customer Engine — Sales Research Assistant

SA-aware NLP platform that ingests customer complaints, classifies them, scores crisis risk, detects anomalies, and routes to the right team — automatically.

---

## What's been built

### Sprint 1 — Foundation & CI/CD

- Python environment, data cleaner, and synthetic SA customer corpus
- 7-stage CI/CD pipeline (Lint → Unit Tests → UEC Contract → POPIA Scan → Critical Scenarios → Sentiment Benchmark → SA Regional Latency)
- POPIA compliance service (`services/sa_redactor/`) — Presidio-based PII redaction at 0.85 threshold with SA phone number recognition (+27 and 0XX formats)
- PostgreSQL 15 (ltree), Redis 7.2, Kafka (single-broker dev / 3-broker HA prod) via docker-compose

### Sprint 2 — NLP Intelligence Layer

- `services/nlp/app/slang.py` — SA slang preprocessor (loads `data/sa_slang.json`, word-boundary matching)
- `services/nlp/app/sentiment.py` — lexicon-based sentiment analyser, polarity −1.0 → +1.0, SA slang-adjusted
- `services/nlp/app/taxonomy.py` — 22-rule UEC classifier (`Domain.Capability.Theme`), Signal Alpha domains first
- `services/nlp/app/anomaly.py` — z-score spike detector, four escalation tiers (Product / Engineering / Team Lead / Monitor)
- `services/nlp/app/pipeline.py` — `process_complaint()` crisis scoring engine, Green/Yellow/Red gates weighted by customer ARR
- `services/nlp/app/main.py` — FastAPI `GET /health` and `POST /analyze`
- `services/ingestion/app/main.py` — FastAPI `POST /api/events` (Email/WhatsApp/Zendesk adapters + redactor/NLP enrichment + UEC validation + dead-letter + event log persistence)
- `scripts/generate_weekly_digest.py` — Build markdown weekly digest from persisted UEC event log

---

## Services

| Service | Port | Purpose |
| --- | --- | --- |
| `voc-postgres` | 5432 | PostgreSQL 15 with ltree taxonomy storage |
| `voc-redis` | 6379 | Celery broker and cache |
| `voc-kafka` | 9092 | Event streaming |
| `voc-sa-redactor` | 8080 | POPIA PII redaction |
| `voc-nlp` | 8081 | NLP intelligence layer |
| `voc-ingestion` | 8000 | Channel ingestion and UEC normalization |

---

## Crisis Score Gates

| Gate | Score | Action |
| --- | --- | --- |
| Green | < 0.3 | Autonomous resolution |
| Yellow | 0.3 – 0.6 | Notify customer success, create priority ticket |
| Red | >= 0.6 | Human review required, no auto actions |

---

## Running locally

```bash
# Start all services
docker compose up -d

# Run unit tests
pytest tests/ --ignore=tests/integration --ignore=tests/critical_scenarios --ignore=tests/test_popia_compliance.py -v

# Generate weekly digest from persisted events
python scripts/generate_weekly_digest.py --input data/processed/uec_events.jsonl --output data/reports/weekly_digest.md

# Optional: also write a stakeholder-facing sample copy
python scripts/generate_weekly_digest.py --sample-output data/reports/weekly_digest_sample.md

# Lint
black --check .
isort --check .
flake8 .
```

---

## Git Rules

- `main` — locked, production only, all merges need a PR
- `dev` — active development branch
- `stans-commits` — working branch, CI validates here before merging to dev

---

## Sprints Remaining

- **Sprint 3** — Expand Ingestion API (`services/ingestion/`) from mock adapters to live Zendesk/WhatsApp/Email connectors + Kafka producer
- **Sprint 4** — Decision Intelligence Engine — crisis score enforcement + staging deploy (AWS af-south-1)
- **Sprint 5** — Weekly Intelligence Brief — automated Monday 09:00 SAST report
