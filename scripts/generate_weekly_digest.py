import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    from services.ingestion.app.digest import build_weekly_digest, load_events, split_event_windows

    parser = argparse.ArgumentParser(description="Generate weekly VoC digest from UEC event log.")
    parser.add_argument(
        "--input",
        default="data/processed/uec_events.jsonl",
        help="Path to UEC event JSONL file.",
    )
    parser.add_argument(
        "--output",
        default="data/reports/weekly_digest.md",
        help="Path for generated markdown digest.",
    )
    parser.add_argument("--days", type=int, default=7, help="Rolling window in days.")
    parser.add_argument(
        "--sample-output",
        default=None,
        help="Optional path to also write a sample digest copy.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    events = load_events(input_path)
    current_events, previous_events = split_event_windows(events, days=max(args.days, 1))
    digest_md = build_weekly_digest(current_events, previous_events=previous_events)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(digest_md, encoding="utf-8")
    print(f"Weekly digest generated: {output_path}")
    print(f"Current window events analyzed: {len(current_events)}")
    print(f"Previous window events analyzed: {len(previous_events)}")

    if args.sample_output:
        sample_path = Path(args.sample_output)
        sample_path.parent.mkdir(parents=True, exist_ok=True)
        sample_path.write_text(digest_md, encoding="utf-8")
        print(f"Sample digest copy written: {sample_path}")


if __name__ == "__main__":
    main()
