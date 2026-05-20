import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CorpusRow:
    source_file: str
    case_id: str
    text: str
    label: str
    channel: str
    language: str
    taxonomy_path: str
    annotator: str


HIGH_RISK_KEYWORDS = (
    "Cancellation",
    "DataAccessRequest",
    "ProcessingError",
    "SsoFailure",
    "Failure",
    "Fraud",
    "Breach",
    "Outage",
)


def infer_high_risk(row: CorpusRow) -> bool:
    if any(token in row.taxonomy_path for token in HIGH_RISK_KEYWORDS):
        return True
    return row.label.lower() == "negative"


def _largest_remainder_quota(counts: Counter[str], total: int) -> dict[str, int]:
    keys = sorted(counts.keys())
    if not keys:
        return {}

    quotas = {k: 1 for k in keys}
    remaining = total - len(keys)
    if remaining <= 0:
        return quotas

    grand_total = sum(counts.values())
    shares = {k: remaining * (counts[k] / grand_total) for k in keys}
    base = {k: int(shares[k]) for k in keys}

    for k in keys:
        quotas[k] += base[k]

    assigned = sum(base.values())
    leftovers = remaining - assigned
    ranked = sorted(keys, key=lambda k: (shares[k] - base[k], counts[k], k), reverse=True)
    for k in ranked[:leftovers]:
        quotas[k] += 1
    return quotas


def _rank_rows(rows: list[CorpusRow], taxonomy_counts: Counter[str], language_counts: Counter[str]) -> list[CorpusRow]:
    return sorted(
        rows,
        key=lambda r: (
            taxonomy_counts[r.taxonomy_path],
            language_counts[r.language],
            r.case_id,
        ),
    )


def stratified_sample(rows: list[CorpusRow], target_n: int, seedless: bool = True) -> list[CorpusRow]:
    del seedless  # Deterministic by sorted order; no RNG used.
    if target_n <= 0:
        return []
    if target_n >= len(rows):
        return rows

    by_channel: dict[str, list[CorpusRow]] = defaultdict(list)
    for row in rows:
        by_channel[row.channel].append(row)

    channel_counts = Counter({channel: len(items) for channel, items in by_channel.items()})
    channel_quota = _largest_remainder_quota(channel_counts, target_n)

    taxonomy_counts = Counter(r.taxonomy_path for r in rows)
    language_counts = Counter(r.language for r in rows)

    selected: list[CorpusRow] = []
    selected_ids: set[str] = set()

    for channel in sorted(by_channel.keys()):
        channel_rows = _rank_rows(by_channel[channel], taxonomy_counts, language_counts)
        quota = min(channel_quota.get(channel, 0), len(channel_rows))
        if quota <= 0:
            continue

        by_label: dict[str, list[CorpusRow]] = defaultdict(list)
        for row in channel_rows:
            by_label[row.label].append(row)

        ordered_labels = sorted(by_label.keys(), key=lambda x: (len(by_label[x]), x))
        channel_selected: list[CorpusRow] = []

        # Round-robin over labels first to improve label diversity in each channel.
        while len(channel_selected) < quota and ordered_labels:
            progressed = False
            for label in ordered_labels:
                bucket = by_label[label]
                if not bucket:
                    continue
                candidate = bucket.pop(0)
                if candidate.case_id not in selected_ids:
                    channel_selected.append(candidate)
                    selected_ids.add(candidate.case_id)
                    progressed = True
                    if len(channel_selected) >= quota:
                        break
            if not progressed:
                break

        if len(channel_selected) < quota:
            leftovers = [
                row
                for row in channel_rows
                if row.case_id not in {item.case_id for item in channel_selected}
            ]
            for row in leftovers[: quota - len(channel_selected)]:
                if row.case_id not in selected_ids:
                    channel_selected.append(row)
                    selected_ids.add(row.case_id)

        selected.extend(channel_selected)

    if len(selected) < target_n:
        selected_set = {row.case_id for row in selected}
        leftovers = [
            row for row in _rank_rows(rows, taxonomy_counts, language_counts) if row.case_id not in selected_set
        ]
        selected.extend(leftovers[: target_n - len(selected)])

    return selected[:target_n]


def load_rows(corpus_dir: Path) -> list[CorpusRow]:
    rows: list[CorpusRow] = []
    for path in sorted(corpus_dir.glob("sample_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            CorpusRow(
                source_file=str(path.as_posix()),
                case_id=str(data.get("id", path.stem)),
                text=str(data.get("text", "")).strip(),
                label=str(data.get("label", "unknown")),
                channel=str(data.get("channel", "unknown")),
                language=str(data.get("language", "unknown")),
                taxonomy_path=str(data.get("taxonomy_path", "unknown")),
                annotator=str(data.get("annotator", "unknown")),
            )
        )
    if not rows:
        raise ValueError(f"No sample_*.json files found under {corpus_dir}")
    return rows


def write_candidates(output_path: Path, selected: list[CorpusRow]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "candidate_rank",
                "id",
                "source_file",
                "channel",
                "language",
                "label",
                "suggested_taxonomy_path",
                "suggested_high_risk",
                "annotator",
                "review_status",
                "reviewed_by",
                "review_notes",
                "text",
            ],
        )
        writer.writeheader()
        for idx, row in enumerate(selected, start=1):
            writer.writerow(
                {
                    "candidate_rank": idx,
                    "id": row.case_id,
                    "source_file": row.source_file,
                    "channel": row.channel,
                    "language": row.language,
                    "label": row.label,
                    "suggested_taxonomy_path": row.taxonomy_path,
                    "suggested_high_risk": str(infer_high_risk(row)).lower(),
                    "annotator": row.annotator,
                    "review_status": "pending",
                    "reviewed_by": "",
                    "review_notes": "",
                    "text": row.text,
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a stratified 50-case candidate list for human-reviewed golden set creation."
    )
    parser.add_argument(
        "--corpus-dir",
        default="tests/fixtures/sa_customer_corpus",
        help="Directory that contains sample_*.json corpus files.",
    )
    parser.add_argument(
        "--output",
        default="data/templates/golden_50_candidates.csv",
        help="Output CSV path for manual review.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of candidate rows to generate.",
    )
    args = parser.parse_args()

    rows = load_rows(Path(args.corpus_dir))
    selected = stratified_sample(rows, target_n=args.count)
    write_candidates(Path(args.output), selected)

    channel_counts = Counter(r.channel for r in selected)
    language_counts = Counter(r.language for r in selected)
    label_counts = Counter(r.label for r in selected)
    print(f"Generated candidate file: {args.output}")
    print(f"Selected rows: {len(selected)}")
    print(f"Channel distribution: {dict(sorted(channel_counts.items()))}")
    print(f"Language distribution: {dict(sorted(language_counts.items()))}")
    print(f"Label distribution: {dict(sorted(label_counts.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
