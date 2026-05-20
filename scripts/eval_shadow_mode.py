import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class EvalRow:
    case_id: str
    text: str
    customer_arr: float
    expected_label: str
    expected_high_risk: bool


@dataclass
class EvalResult:
    case_id: str
    expected_label: str
    rules_label: str
    llm_shadow_label: str | None
    expected_high_risk: bool
    rules_high_risk: bool
    llm_high_risk: bool
    llm_fallback_used: bool


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    value_str = str(value).strip().lower()
    return value_str in {"1", "true", "yes", "y", "t"}


def load_eval_rows(path: Path) -> list[EvalRow]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            records = list(csv.DictReader(f))
    elif suffix in {".json", ".jsonl"}:
        with path.open(encoding="utf-8") as f:
            if suffix == ".jsonl":
                records = [json.loads(line) for line in f if line.strip()]
            else:
                data = json.load(f)
                if not isinstance(data, list):
                    raise ValueError("JSON input must be a list of objects.")
                records = data
    else:
        raise ValueError("Input must be .csv, .json, or .jsonl")

    rows: list[EvalRow] = []
    for i, rec in enumerate(records, start=1):
        text = str(rec.get("text", "")).strip()
        expected_label = str(rec.get("expected_label", "")).strip()
        if not text or not expected_label:
            raise ValueError(
                f"Row {i}: both 'text' and 'expected_label' are required for shadow evaluation."
            )
        rows.append(
            EvalRow(
                case_id=str(rec.get("id", f"case_{i}")),
                text=text,
                customer_arr=float(rec.get("customer_arr", 0.0)),
                expected_label=expected_label,
                expected_high_risk=_to_bool(rec.get("expected_high_risk", False)),
            )
        )
    return rows


def _safe_recall(tp: int, positives: int) -> float:
    if positives <= 0:
        return 0.0
    return tp / positives


def _safe_accuracy(correct: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return correct / total


def evaluate_rows(rows: list[EvalRow]) -> tuple[list[EvalResult], dict]:
    from services.nlp.app.pipeline import process_complaint

    previous_mode = os.getenv("NLP_CLASSIFIER_MODE")
    details: list[EvalResult] = []

    try:
        for row in rows:
            os.environ["NLP_CLASSIFIER_MODE"] = "rules"
            rules_result = process_complaint({"text": row.text, "customer_arr": row.customer_arr})

            os.environ["NLP_CLASSIFIER_MODE"] = "shadow"
            shadow_result = process_complaint({"text": row.text, "customer_arr": row.customer_arr})

            os.environ["NLP_CLASSIFIER_MODE"] = "llm"
            llm_mode_result = process_complaint(
                {"text": row.text, "customer_arr": row.customer_arr}
            )

            details.append(
                EvalResult(
                    case_id=row.case_id,
                    expected_label=row.expected_label,
                    rules_label=rules_result.taxonomy_path,
                    llm_shadow_label=shadow_result.llm_shadow_label,
                    expected_high_risk=row.expected_high_risk,
                    rules_high_risk=rules_result.at_risk_flag,
                    llm_high_risk=llm_mode_result.at_risk_flag,
                    llm_fallback_used=llm_mode_result.llm_fallback_used,
                )
            )
    finally:
        if previous_mode is None:
            os.environ.pop("NLP_CLASSIFIER_MODE", None)
        else:
            os.environ["NLP_CLASSIFIER_MODE"] = previous_mode

    total = len(details)
    rules_correct = sum(1 for d in details if d.rules_label == d.expected_label)
    llm_valid = [d for d in details if d.llm_shadow_label is not None]
    llm_correct = sum(1 for d in llm_valid if d.llm_shadow_label == d.expected_label)
    llm_fallback_count = sum(1 for d in details if d.llm_fallback_used)

    expected_high_risk_total = sum(1 for d in details if d.expected_high_risk)
    rules_high_risk_tp = sum(1 for d in details if d.expected_high_risk and d.rules_high_risk)
    llm_high_risk_tp = sum(1 for d in details if d.expected_high_risk and d.llm_high_risk)

    metrics = {
        "total_cases": total,
        "rules_accuracy": _safe_accuracy(rules_correct, total),
        "llm_accuracy": _safe_accuracy(llm_correct, len(llm_valid)),
        "llm_valid_predictions": len(llm_valid),
        "llm_fallback_rate": _safe_accuracy(llm_fallback_count, total),
        "rules_high_risk_recall": _safe_recall(rules_high_risk_tp, expected_high_risk_total),
        "llm_high_risk_recall": _safe_recall(llm_high_risk_tp, expected_high_risk_total),
    }
    return details, metrics


def build_markdown_report(details: list[EvalResult], metrics: dict, input_path: Path) -> str:
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    mismatches = [
        d
        for d in details
        if d.rules_label != d.expected_label
        or (d.llm_shadow_label and d.llm_shadow_label != d.expected_label)
    ]
    mismatch_lines = (
        "\n".join(
            (
                f"- {d.case_id}: expected={d.expected_label}, "
                f"rules={d.rules_label}, llm={d.llm_shadow_label}"
            )
            for d in mismatches[:20]
        )
        if mismatches
        else "- none"
    )

    return (
        "# Shadow Mode Evaluation Report\n\n"
        f"Generated at (UTC): {generated_at}\n\n"
        f"Input dataset: `{input_path}`\n\n"
        "## Core Metrics\n"
        f"- Total cases: {metrics['total_cases']}\n"
        f"- Rules accuracy: {metrics['rules_accuracy'] * 100:.2f}%\n"
        f"- LLM accuracy (shadow label present): {metrics['llm_accuracy'] * 100:.2f}%\n"
        f"- LLM valid predictions: {metrics['llm_valid_predictions']}\n"
        f"- LLM fallback rate: {metrics['llm_fallback_rate'] * 100:.2f}%\n"
        f"- Rules high-risk recall: {metrics['rules_high_risk_recall'] * 100:.2f}%\n"
        f"- LLM high-risk recall: {metrics['llm_high_risk_recall'] * 100:.2f}%\n\n"
        "## Top Label Mismatches (first 20)\n"
        f"{mismatch_lines}\n"
    )


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(
        description="Evaluate rules vs LLM shadow labels on golden dataset."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to dataset (.csv/.json/.jsonl) with text and expected_label columns.",
    )
    parser.add_argument(
        "--output",
        default="data/reports/shadow_eval_report.md",
        help="Markdown report output path.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    rows = load_eval_rows(input_path)
    details, metrics = evaluate_rows(rows)
    report = build_markdown_report(details, metrics, input_path=input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"Shadow evaluation report written: {output_path}")
    print(f"Total cases: {metrics['total_cases']}")
    print(f"Rules accuracy: {metrics['rules_accuracy'] * 100:.2f}%")
    print(f"LLM accuracy: {metrics['llm_accuracy'] * 100:.2f}%")
    print(f"LLM high-risk recall: {metrics['llm_high_risk_recall'] * 100:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
