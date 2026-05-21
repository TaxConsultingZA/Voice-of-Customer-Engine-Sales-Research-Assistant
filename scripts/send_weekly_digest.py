"""
Send the weekly VoC digest via SendGrid.

Usage:
    python scripts/send_weekly_digest.py --to ceo@example.com pm@example.com
    python scripts/send_weekly_digest.py  # reads DIGEST_TO_EMAILS from .env

Required environment variables:
    SENDGRID_API_KEY      SendGrid v3 API key
    DIGEST_FROM_EMAIL     Sender address verified in SendGrid
    DIGEST_TO_EMAILS      Comma-separated recipients (fallback when --to not given)

Optional:
    NLP_CLASSIFIER_MODE   Passed through to digest generation (default: rules)
"""

import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _build_digest() -> str:
    from services.ingestion.app.digest import build_weekly_digest, load_events, split_event_windows

    events_path = ROOT / "data" / "processed" / "uec_events.jsonl"
    events = load_events(events_path)
    current_events, previous_events = split_event_windows(events, days=7)
    return build_weekly_digest(current_events, previous_events=previous_events)


def _markdown_to_html(md: str) -> str:
    """Convert the digest Markdown into plain HTML (no extra dependencies)."""
    lines = []
    for line in md.splitlines():
        if line.startswith("## "):
            lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            lines.append(f"<h1 style='color:#1a1a2e'>{line[2:]}</h1>")
        elif line.startswith("- "):
            lines.append(f"<li>{line[2:]}</li>")
        elif not line.strip():
            lines.append("<br>")
        else:
            lines.append(f"<p>{line}</p>")
    header = (
        "<html><body style='"
        "font-family:Arial,sans-serif;"
        "max-width:680px;"
        "margin:32px auto;"
        "color:#333;"
        "line-height:1.6"
        "'>"
    )
    return header + "\n".join(lines) + "</body></html>"


def send_digest(
    api_key: str,
    from_email: str,
    to_emails: list[str],
    digest_md: str,
) -> None:
    today = datetime.date.today().strftime("%d %b %Y")
    subject = f"VoC Weekly Digest — {today}"
    html_body = _markdown_to_html(digest_md)

    payload = {
        "personalizations": [{"to": [{"email": addr} for addr in to_emails]}],
        "from": {"email": from_email},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": digest_md},
            {"type": "text/html", "value": html_body},
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"SendGrid HTTP {exc.code}: {body}") from exc

    print(f"Digest sent to {len(to_emails)} recipient(s) via SendGrid (HTTP {status}).")


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Generate and email the weekly VoC digest via SendGrid."
    )
    parser.add_argument(
        "--to",
        nargs="+",
        default=None,
        metavar="EMAIL",
        help="Recipient addresses (overrides DIGEST_TO_EMAILS env var).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print digest to stdout instead of sending.",
    )
    args = parser.parse_args()

    digest_md = _build_digest()

    if args.dry_run:
        print(digest_md)
        return

    api_key = os.getenv("SENDGRID_API_KEY", "")
    from_email = os.getenv("DIGEST_FROM_EMAIL", "")
    env_recipients = [e.strip() for e in os.getenv("DIGEST_TO_EMAILS", "").split(",") if e.strip()]
    to_emails = args.to or env_recipients

    if not api_key:
        sys.exit("ERROR: SENDGRID_API_KEY is not set.")
    if not from_email:
        sys.exit("ERROR: DIGEST_FROM_EMAIL is not set.")
    if not to_emails:
        sys.exit("ERROR: No recipients — pass --to or set DIGEST_TO_EMAILS.")

    send_digest(api_key, from_email, to_emails, digest_md)


if __name__ == "__main__":
    main()
