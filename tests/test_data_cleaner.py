"""
Data Cleaner Tests
------------------
Unit tests for data_cleaner.py — the first processing stage
before text reaches the NLP pipeline.
"""

import csv
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from data_cleaner import (
    choose_text_column,
    clean_records,
    clean_ticket_text,
    load_records,
    main,
    save_as_csv,
)

# ---------------------------------------------------------------------------
# clean_ticket_text
# ---------------------------------------------------------------------------


def test_html_tags_stripped():
    assert "<b>" not in clean_ticket_text("<b>My account is broken</b>")
    assert "My account is broken" in clean_ticket_text("<b>My account is broken</b>")


def test_urls_removed():
    result = clean_ticket_text("Visit https://example.co.za for help or www.site.com")
    assert "https://" not in result
    assert "example.co.za" not in result


def test_email_addresses_removed():
    result = clean_ticket_text("Email us at support@company.co.za for assistance")
    assert "@" not in result


def test_markdown_links_keep_visible_text():
    result = clean_ticket_text("See [our FAQ](https://example.co.za/faq) for details")
    assert "our FAQ" in result
    assert "https://" not in result


def test_filler_phrases_removed():
    result = clean_ticket_text("Please help, thank you, kind regards")
    assert "please help" not in result.lower()
    assert "thank you" not in result.lower()
    assert "kind regards" not in result.lower()


def test_ticket_id_removed():
    result = clean_ticket_text("Regarding ticket #12345, my login fails")
    assert "12345" not in result


def test_date_removed():
    result = clean_ticket_text("On 2024-01-15 my account was locked")
    assert "2024-01-15" not in result


def test_empty_string_returns_empty():
    assert clean_ticket_text("") == ""


def test_none_returns_empty():
    assert clean_ticket_text(None) == ""


def test_whitespace_normalised():
    result = clean_ticket_text("login    fails    every    day")
    assert "  " not in result


def test_repeated_punctuation_collapsed():
    result = clean_ticket_text("It's broken!!!!!")
    assert "!!!!!" not in result


def test_sa_slang_preserved():
    """SA slang must not be stripped — the NLP layer needs it."""
    result = clean_ticket_text("Eish, the app is kak and I can't login howzit")
    assert "eish" in result.lower() or "Eish" in result
    assert "howzit" in result.lower()


def test_system_bracket_tags_removed():
    result = clean_ticket_text("[Auto Reply] Your ticket has been received [Ticket Closed]")
    assert "[Auto Reply]" not in result
    assert "[Ticket Closed]" not in result


# ---------------------------------------------------------------------------
# clean_records
# ---------------------------------------------------------------------------


def test_duplicates_removed():
    records = [
        {"text": "My account is broken"},
        {"text": "My account is broken"},
        {"text": "Login fails every time"},
    ]
    cleaned = clean_records(records, "text")
    assert len(cleaned) == 2


def test_empty_text_rows_removed():
    records = [
        {"text": ""},
        {"text": "Valid complaint about login"},
        {"text": "   "},
    ]
    cleaned = clean_records(records, "text")
    assert len(cleaned) == 1


def test_cleaned_text_field_added():
    records = [{"text": "<b>Login is broken</b>"}]
    cleaned = clean_records(records, "text")
    assert "cleaned_text" in cleaned[0]
    assert "<b>" not in cleaned[0]["cleaned_text"]


def test_original_fields_preserved():
    records = [{"text": "Login broken", "ticket_id": "T-001", "priority": "high"}]
    cleaned = clean_records(records, "text")
    assert cleaned[0]["ticket_id"] == "T-001"
    assert cleaned[0]["priority"] == "high"


def test_none_text_field_removed():
    records = [{"text": None}, {"text": "Real complaint"}]
    cleaned = clean_records(records, "text")
    assert len(cleaned) == 1


# ---------------------------------------------------------------------------
# choose_text_column
# ---------------------------------------------------------------------------


def test_explicit_column_chosen():
    records = [{"custom_col": "Hello", "id": 1}]
    assert choose_text_column(records, "custom_col") == "custom_col"


def test_auto_detects_message_column():
    records = [{"message": "Hello", "id": 1}]
    assert choose_text_column(records, None) == "message"


def test_auto_detects_description_column():
    records = [{"description": "Issue description", "id": 1}]
    assert choose_text_column(records, None) == "description"


def test_missing_explicit_column_raises():
    records = [{"text": "Hello"}]
    with pytest.raises(ValueError, match="not found"):
        choose_text_column(records, "nonexistent_column")


def test_empty_records_raises():
    with pytest.raises(ValueError):
        choose_text_column([], None)


# ---------------------------------------------------------------------------
# load_records
# ---------------------------------------------------------------------------


def test_load_csv():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "message"])
        writer.writeheader()
        writer.writerow({"id": "1", "message": "Login broken"})
        tmp_path = Path(f.name)

    records = load_records(tmp_path)
    assert len(records) == 1
    assert records[0]["message"] == "Login broken"
    tmp_path.unlink()


def test_load_json():
    data = [{"id": "1", "message": "Login broken"}]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f)
        tmp_path = Path(f.name)

    records = load_records(tmp_path)
    assert len(records) == 1
    tmp_path.unlink()


def test_load_jsonl():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        f.write('{"id": "1", "message": "Login broken"}\n')
        f.write('{"id": "2", "message": "Password reset fails"}\n')
        tmp_path = Path(f.name)

    records = load_records(tmp_path)
    assert len(records) == 2
    tmp_path.unlink()


def test_unsupported_file_type_raises():
    with pytest.raises(ValueError, match="Unsupported"):
        load_records(Path("data.pdf"))


def test_load_json_dict_format():
    """JSON files wrapping the record list in {"data": [...]} are supported."""
    data = {"data": [{"id": "1", "message": "Login broken"}]}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f)
        tmp_path = Path(f.name)

    records = load_records(tmp_path)
    assert len(records) == 1
    assert records[0]["message"] == "Login broken"
    tmp_path.unlink()


def test_load_excel_without_pandas_raises():
    """Excel loading raises ImportError with install instructions when pandas is absent."""
    with patch.dict("sys.modules", {"pandas": None}):
        with pytest.raises(ImportError, match="pandas"):
            load_records(Path("data.xlsx"))


# ---------------------------------------------------------------------------
# choose_text_column — edge cases
# ---------------------------------------------------------------------------


def test_fuzzy_fallback_detects_transcript_column():
    """Falls back to first column whose name contains 'transcript'."""
    records = [{"call_transcript": "Hello", "id": 1}]
    assert choose_text_column(records, None) == "call_transcript"


def test_no_detectable_column_raises():
    """Raises ValueError when no text-like column can be found."""
    records = [{"id": 1, "score": 5}]
    with pytest.raises(ValueError, match="auto-detect"):
        choose_text_column(records, None)


# ---------------------------------------------------------------------------
# save_as_csv
# ---------------------------------------------------------------------------


def test_save_as_csv_writes_file(tmp_path):
    rows = [{"id": "1", "cleaned_text": "Login broken"}]
    out = tmp_path / "output.csv"
    save_as_csv(rows, out)
    assert out.exists()
    assert "Login broken" in out.read_text(encoding="utf-8-sig")


def test_save_as_csv_empty_raises():
    with pytest.raises(ValueError, match="No cleaned rows"):
        save_as_csv([], Path("output.csv"))


# ---------------------------------------------------------------------------
# main() — end-to-end CLI
# ---------------------------------------------------------------------------


def test_main_runs_end_to_end(tmp_path, monkeypatch):
    """main() reads a CSV, cleans text, and writes a valid output file."""
    input_file = tmp_path / "input.csv"
    output_file = tmp_path / "output.csv"

    with input_file.open("w", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text"])
        writer.writeheader()
        writer.writerow({"text": "Login is broken"})

    monkeypatch.setattr(
        sys,
        "argv",
        ["data_cleaner.py", "--input", str(input_file), "--output", str(output_file)],
    )
    main()

    assert output_file.exists()
    assert "Login is broken" in output_file.read_text(encoding="utf-8-sig")
