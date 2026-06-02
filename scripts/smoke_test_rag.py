"""
End-to-end smoke test for the Sales Research RAG pipeline — NO real data needed.

What it proves (the "试车" / test drive):
    1. We can write fake case-study PDFs.
    2. ingest_case_studies.py reads them, chunks, embeds, and stores in pgvector.
    3. case_retriever.retrieve_case_studies() pulls the RIGHT case back by meaning.

If this prints sensible matches, the whole ingest -> store -> retrieve chain is
wired correctly, and you can swap Stanley's real PDFs in with confidence.

Prerequisites:
    pip install -r requirements-sales.txt
    docker compose -f docker-compose.sales.yml up -d        # starts pgvector on 5433
    export DATABASE_URL=postgresql://sales:sales_dev_secret@localhost:5433/sales_research
        (PowerShell sets the same value via:
         $env:DATABASE_URL = "postgresql://sales:sales_dev_secret@localhost:5433/sales_research")

Run:
    python scripts/smoke_test_rag.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# Make `services` package importable when run as a plain script.
sys.path.insert(0, str(REPO_ROOT))

# Three fake case studies, each clearly about a different domain so we can prove
# retrieval ranks the semantically closest one first.
FAKE_CASES = {
    "fnb-fraud-detection": (
        "FNB Real-Time Fraud Detection",
        "banking",
        (
            "First National Bank struggled with card fraud losses across millions of "
            "daily transactions. They needed sub-second anomaly detection without "
            "blocking legitimate customers. We deployed a streaming machine learning "
            "model that scored every transaction in under 50 milliseconds. Fraudulent "
            "charge-backs dropped 38 percent in the first quarter while false declines "
            "fell by half. The risk and compliance teams gained a live dashboard of "
            "flagged transactions and audit trails for every automated decision."
        ),
    ),
    "shoprite-supply-chain": (
        "Shoprite Supply Chain Forecasting",
        "retail",
        (
            "Shoprite faced stock-outs on fast-moving groceries and overstock on "
            "seasonal goods across hundreds of stores. We built a demand forecasting "
            "system that combined point-of-sale history, weather, and promotions to "
            "predict per-store replenishment. Out-of-stock incidents fell 27 percent "
            "and wastage on perishables dropped sharply, improving margins for the "
            "retail operations team during peak holiday trading."
        ),
    ),
    "discovery-claims-automation": (
        "Discovery Health Claims Automation",
        "insurance",
        (
            "Discovery Health processed medical claims manually, creating long "
            "turnaround times and inconsistent adjudication. We introduced a document "
            "extraction pipeline that read scanned claim forms and routed them through "
            "automated validation rules. Straight-through processing rose to 71 percent, "
            "average claim settlement time dropped from days to hours, and the claims "
            "operations team could focus on genuine edge cases and member disputes."
        ),
    ),
}


def _load_ingest_module():
    script = REPO_ROOT / "scripts" / "ingest_case_studies.py"
    spec = importlib.util.spec_from_file_location("ingest_case_studies", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_fake_pdfs(folder: Path) -> None:
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise SystemExit(
            "fpdf2 is not installed. Run: pip install -r requirements-sales.txt"
        ) from exc

    folder.mkdir(parents=True, exist_ok=True)
    for case_id, (title, _industry, body) in FAKE_CASES.items():
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", style="B", size=16)
        pdf.multi_cell(0, 10, title)
        pdf.ln(4)
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 8, body)
        pdf.output(str(folder / f"{case_id}.pdf"))
    print(f"[setup] wrote {len(FAKE_CASES)} fake case study PDFs to {folder}")


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise SystemExit(
            "DATABASE_URL not set. Start the db and export it:\n"
            "  docker compose -f docker-compose.sales.yml up -d\n"
            "  $env:DATABASE_URL = "
            '"postgresql://sales:sales_dev_secret@localhost:5433/sales_research"'
        )

    ingest = _load_ingest_module()

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "case_studies"
        _write_fake_pdfs(folder)

        print("\n[ingest] loading embedding model + connecting to pgvector...")
        model = ingest._load_model()
        conn = ingest._connect()
        try:
            for case_id, (_title, industry, _body) in FAKE_CASES.items():
                ingest.ingest_file(conn, model, folder / f"{case_id}.pdf", [industry])
        finally:
            conn.close()

    # Now exercise the REAL retriever the pipeline uses in production.
    from services.sales_research.app.case_retriever import retrieve_case_studies

    queries = [
        ("A bank that wants to stop credit card fraud in real time", "banking"),
        ("A grocery retailer with stock-out and inventory problems", None),
        ("A health insurer drowning in manual paperwork", None),
    ]

    print("\n" + "=" * 70)
    print("RETRIEVAL TEST — does the closest case come back on top?")
    print("=" * 70)
    all_ok = True
    expected_top = {
        queries[0][0]: "fnb-fraud-detection",
        queries[1][0]: "shoprite-supply-chain",
        queries[2][0]: "discovery-claims-automation",
    }
    for query, hint in queries:
        results = retrieve_case_studies(query, industry_hint=hint, top_k=3)
        print(f"\nQuery: {query!r}  (industry_hint={hint})")
        if not results:
            print("  -> NO RESULTS (check DB/model/ingest)")
            all_ok = False
            continue
        for rank, r in enumerate(results, 1):
            marker = "  <== expected top" if rank == 1 and r.case_id == expected_top[query] else ""
            print(f"  {rank}. {r.case_id:30s} | {r.title}{marker}")
        if results[0].case_id != expected_top[query]:
            all_ok = False

    print("\n" + "=" * 70)
    if all_ok:
        print("SMOKE TEST PASSED — ingest -> store -> retrieve chain works end to end.")
    else:
        print("SMOKE TEST INCOMPLETE — top match was not as expected (see above).")
        sys.exit(1)


if __name__ == "__main__":
    main()
