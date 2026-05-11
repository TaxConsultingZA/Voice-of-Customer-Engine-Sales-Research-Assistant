import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

# Common low-value phrases that appear in service tickets or transcripts.
# Keep this list small and practical at the beginning.
FILLER_PATTERNS = [
    r"\bplease\s+help\b",
    r"\bthanks?\b",
    r"\bthank\s+you\b",
    r"\basap\b",
    r"\bkind\s+regards\b",
    r"\bbest\s+regards\b",
]

# Candidate field names for text content in exported files.
TEXT_COLUMN_CANDIDATES = [
    "complaint_text",
    "ticket_text",
    "message",
    "content",
    "description",
    "body",
    "transcript",
    "issue",
    "customer_voice",
]


def clean_ticket_text(raw_text: str) -> str:
    """
    Clean one raw ticket/transcript string into compact plain text.
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""

    text = raw_text

    # Remove HTML tags from CRM/email exports.
    text = re.sub(r"<[^>]+>", " ", text)

    # Remove markdown links but keep visible text.
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)

    # Remove URLs and email addresses.
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", " ", text)

    # Remove system-style bracket tags: [Auto Reply], [Ticket Closed], etc.
    text = re.sub(r"\[[^\]]{1,40}\]", " ", text)

    # Remove simple ticket IDs and timestamps that add little NLP value.
    text = re.sub(r"\b(?:ticket|case|id)[:#\s-]*\d+\b", " ", text, flags=re.I)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", text)
    text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", " ", text)

    # Remove low-value filler phrases.
    for pattern in FILLER_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.I)

    # Keep letters/numbers/basic punctuation and CJK range; drop odd symbols.
    text = re.sub(r"[^\w\s\u4e00-\u9fff.,!?;:'\"-]", " ", text)

    # Compress repeated punctuation and spaces.
    text = re.sub(r"([!?.,])\1{1,}", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def load_records(input_path: Path) -> List[Dict]:
    """
    Load records from CSV/JSON/JSONL (and Excel if pandas is installed).
    """
    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        with input_path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    if suffix in [".json", ".jsonl"]:
        with input_path.open("r", encoding="utf-8") as f:
            if suffix == ".jsonl":
                return [json.loads(line) for line in f if line.strip()]
            data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                # Support top-level {"data": [...]} style payloads.
                for value in data.values():
                    if isinstance(value, list):
                        return value
            raise ValueError("JSON file must contain a list of records.")

    if suffix in [".xlsx", ".xls"]:
        try:
            import pandas as pd  # Optional dependency
        except ImportError as exc:
            raise ImportError(
                "Excel detected. Install pandas and openpyxl first: "
                "pip install pandas openpyxl"
            ) from exc
        return pd.read_excel(input_path).to_dict(orient="records")

    raise ValueError(f"Unsupported file type: {suffix}")


def choose_text_column(records: List[Dict], text_column: Optional[str]) -> str:
    """
    Pick the text column from user input or common field names.
    """
    if not records:
        raise ValueError("No records found in input file.")

    if text_column:
        if text_column not in records[0]:
            raise ValueError(f"Column '{text_column}' not found in file.")
        return text_column

    lower_to_actual = {str(k).lower(): k for k in records[0].keys()}
    for candidate in TEXT_COLUMN_CANDIDATES:
        if candidate in lower_to_actual:
            return lower_to_actual[candidate]

    # Fallback: choose the first column containing "text/message/content" words.
    for key in records[0].keys():
        key_lower = str(key).lower()
        if any(x in key_lower for x in ["text", "message", "content", "desc", "transcript"]):
            return key

    raise ValueError(
        "Cannot auto-detect text column. Please pass --text-column explicitly."
    )


def clean_records(records: List[Dict], text_column: str) -> List[Dict]:
    """
    Clean text field and drop empty/duplicate rows.
    """
    cleaned: List[Dict] = []
    seen = set()

    for row in records:
        raw_text = row.get(text_column, "")
        normalized = clean_ticket_text("" if raw_text is None else str(raw_text))
        if not normalized:
            continue
        if normalized in seen:
            continue

        seen.add(normalized)
        new_row = dict(row)
        new_row["cleaned_text"] = normalized
        cleaned.append(new_row)

    return cleaned


def save_as_csv(rows: List[Dict], output_path: Path) -> None:
    """
    Save cleaned records into UTF-8 CSV (Excel-friendly BOM included).
    """
    if not rows:
        raise ValueError("No cleaned rows to save.")

    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean customer tickets/transcripts into plain text."
    )
    parser.add_argument("--input", required=True, help="Input file path (.csv/.json/.jsonl/.xlsx)")
    parser.add_argument("--output", default="cleaned_output.csv", help="Output CSV path")
    parser.add_argument("--text-column", default=None, help="Column containing raw text")
    parser.add_argument("--preview", type=int, default=3, help="Number of cleaned samples to print")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    records = load_records(input_path)
    text_column = choose_text_column(records, args.text_column)
    cleaned_rows = clean_records(records, text_column)
    save_as_csv(cleaned_rows, output_path)

    print("=== Data Cleaner Finished ===")
    print(f"Input rows        : {len(records)}")
    print(f"Rows after clean  : {len(cleaned_rows)}")
    print(f"Detected text col : {text_column}")
    print(f"Saved to          : {output_path.resolve()}")
    print("=============================")

    for i, row in enumerate(cleaned_rows[: max(args.preview, 0)], start=1):
        print(f"[Sample {i}] {row.get('cleaned_text', '')}")


if __name__ == "__main__":
    main()