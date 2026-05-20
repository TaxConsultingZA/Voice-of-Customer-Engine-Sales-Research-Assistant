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

## LLM Primary Path

- Primary LLM classification path: `services/nlp/app/llm_client.py` -> `services/nlp/app/pipeline.py`
- Configure Claude credentials and model in `.env`:
  - `CLAUDE_API_KEY`
  - `CLAUDE_MODEL` (current validated default: `claude-sonnet-4-6`)
  - `CLAUDE_TIMEOUT_SECONDS`
  - `CLAUDE_API_BASE_URL` (optional, defaults to Anthropic API)
- Runtime mode is controlled by `NLP_CLASSIFIER_MODE`:
  - `rules` = rules only
  - `shadow` = rules output + LLM shadow label for evaluation
  - `llm` = LLM output as primary taxonomy label
- Legacy module notice: `services/nlp/app/llm_adapter.py` is kept for older mock-based workflows and is not the active Claude production path.

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

# Synthetic load test for ingestion API
python scripts/load_test_ingestion.py --base-url http://localhost:8000 --requests 1000 --concurrency 50

# Synthetic load test + markdown report
python scripts/load_test_ingestion.py --base-url http://localhost:8000 --requests 1000 --concurrency 50 --report-output data/reports/load_test_report.md

# Verify fail-open / fail-closed strategy behavior
python scripts/verify_ingestion_fail_strategy.py

# One-command verification: health + fail strategy + load test + markdown report
python scripts/run_ingestion_verification.py --ingestion-url http://localhost:8000 --strict-health --output data/reports/ingestion_verification_report.md

# Shadow evaluation: rules vs Claude (requires expected_label dataset)
python scripts/eval_shadow_mode.py --input data/templates/shadow_eval_template.csv --output data/reports/shadow_eval_report.md

# Build a stratified 50-case candidate file for manual golden-set review
python scripts/generate_golden_candidates.py --count 50 --output data/templates/golden_50_candidates.csv

# Lint
black --check .
isort --check .
flake8 .
```

---

## Weekly dashboard (Streamlit)

```bash
pip install -r requirements-dashboard.txt
streamlit run streamlit_app.py
```

Open `http://localhost:8501`. The app reads `data/processed/uec_events.jsonl` (a committed demo snapshot is included for deploy).

**Deploy to Streamlit Community Cloud** (public URL for stakeholders):

1. Push this repo to GitHub (`dev` or `main`).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → select the repo.
3. Main file: `streamlit_app.py`.
4. Under **Advanced settings → Python dependencies**, point to `requirements-dashboard.txt` (avoids installing `torch` on Cloud).
5. Deploy. Share the `https://<app-name>.streamlit.app` link.

Re-populate events after a full corpus run:

```bash
python scripts/batch_classify_corpus.py
git add -f data/processed/uec_events.jsonl
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
