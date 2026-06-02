"""
Ingest internal case study PDFs into the pgvector `case_study_chunks` table.

Pipeline:
    PDF files  ->  extract text (pypdf)  ->  chunk (~800 chars, 120 overlap)
    ->  embed (sentence-transformers/all-MiniLM-L6-v2, 384-dim)
    ->  upsert into PostgreSQL case_study_chunks

This is the RAG ingestion side that feeds services/sales_research/app/
case_retriever.py. Run it once whenever the case study library changes.

Prerequisites:
    pip install -r requirements-sales.txt
    psql $DATABASE_URL -f scripts/init-sales-schema.sql   # creates the table
    export DATABASE_URL=postgresql://user:pass@host:5432/dbname

Usage:
    # Ingest every PDF in a folder, tagging them all as 'banking'
    python scripts/ingest_case_studies.py --dir data/case_studies --industry banking

    # Ingest a single file with multiple industry tags
    python scripts/ingest_case_studies.py --file acme.pdf --industry banking fintech

    # Re-ingest (idempotent): existing chunks for a case_id are replaced
    python scripts/ingest_case_studies.py --dir data/case_studies --industry retail

Design notes:
- case_id is derived from the filename (slugified) so re-running replaces
  the same case cleanly instead of duplicating it.
- Embeddings are normalised (cosine-ready) to match the <=> operator used by
  case_retriever.py and the HNSW vector_cosine_ops index.
- The script degrades with a clear error if DATABASE_URL, pypdf,
  sentence-transformers, or the pgvector table is missing.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
EMBEDDING_MODEL = os.getenv("SALES_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = 384


def _slugify(name: str) -> str:
    """Turn 'FNB Compliance Win.pdf' -> 'fnb-compliance-win'."""
    stem = Path(name).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "-", stem)
    return stem.strip("-") or "case"


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit(
            "pypdf is not installed. Run: pip install -r requirements-sales.txt"
        ) from exc

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return "\n".join(pages)


def _clean_text(text: str) -> str:
    # Collapse whitespace and drop control characters that survive PDF extraction.
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Sliding-window character chunks with overlap so context isn't cut mid-idea."""
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + size, length)
        chunk = text[start:end].strip()
        if len(chunk) >= 40:  # skip tiny trailing fragments
            chunks.append(chunk)
        if end == length:
            break
        start = end - overlap
    return chunks


def _load_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit(
            "sentence-transformers is not installed. " "Run: pip install -r requirements-sales.txt"
        ) from exc
    print(f"[model] loading {EMBEDDING_MODEL} (first run downloads weights)...")
    return SentenceTransformer(EMBEDDING_MODEL)


def _connect():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL is not set. Export it before running this script.")
    try:
        import psycopg2
    except ImportError as exc:
        raise SystemExit("psycopg2 is not installed. Run: pip install psycopg2-binary") from exc
    return psycopg2.connect(db_url)


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


def ingest_file(conn, model, path: Path, industry_tags: list[str]) -> int:
    """Ingest a single PDF. Returns number of chunks written."""
    case_id = _slugify(path.name)
    title = path.stem.replace("-", " ").replace("_", " ").strip().title()

    raw = _extract_pdf_text(path)
    text = _clean_text(raw)
    chunks = _chunk_text(text)

    if not chunks:
        print(f"[skip] {path.name}: no extractable text (scanned image PDF?)")
        return 0

    embeddings = model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)

    with conn:
        with conn.cursor() as cur:
            # Replace any prior version of this case so re-runs stay clean.
            cur.execute("DELETE FROM case_study_chunks WHERE case_id = %s", (case_id,))
            for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                cur.execute(
                    """
                    INSERT INTO case_study_chunks
                        (case_id, title, chunk_index, content, embedding, industry_tags)
                    VALUES (%s, %s, %s, %s, %s::vector, %s)
                    ON CONFLICT (case_id, chunk_index) DO UPDATE
                        SET content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            industry_tags = EXCLUDED.industry_tags,
                            title = EXCLUDED.title
                    """,
                    (
                        case_id,
                        title,
                        idx,
                        chunk,
                        _vec_literal(list(emb)),
                        [t.lower() for t in industry_tags],
                    ),
                )
    print(f"[ok]   {path.name}: case_id='{case_id}', {len(chunks)} chunks, tags={industry_tags}")
    return len(chunks)


def _collect_pdfs(args: argparse.Namespace) -> list[Path]:
    if args.file:
        path = Path(args.file)
        if not path.exists():
            raise SystemExit(f"File not found: {path}")
        return [path]
    folder = Path(args.dir)
    if not folder.exists():
        raise SystemExit(f"Directory not found: {folder}")
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDF files found in {folder}")
    return pdfs


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest case study PDFs into pgvector.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dir", help="Folder containing case study PDFs.")
    source.add_argument("--file", help="Single PDF file to ingest.")
    parser.add_argument(
        "--industry",
        nargs="+",
        default=[],
        metavar="TAG",
        help="Industry tags applied to all ingested files (e.g. banking fintech).",
    )
    args = parser.parse_args()

    pdfs = _collect_pdfs(args)
    model = _load_model()
    conn = _connect()

    total_chunks = 0
    try:
        for pdf in pdfs:
            total_chunks += ingest_file(conn, model, pdf, args.industry)
    finally:
        conn.close()

    print(f"\nDone. {len(pdfs)} file(s), {total_chunks} chunks written to case_study_chunks.")
    if total_chunks == 0:
        sys.exit("WARNING: nothing was ingested — check the PDFs are text-based, not scans.")


if __name__ == "__main__":
    main()
