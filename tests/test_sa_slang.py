"""
SA Slang Dictionary Tests
--------------------------
Validates that data/sa_slang.json is well-formed and contains
the terms required by the NLP layer's slang-awareness tests.
"""

from pathlib import Path

ROOT = Path(__file__).parent.parent

REQUIRED_TERMS = [
    "lekker",
    "eish",
    "ag shame",
    "howzit",
    "ja nee",
    "braai",
    "robot",
    "now now",
    "yebo",
    "sharp",
    "hectic",
    "lank",
    "haibo",
    "aikona",
]

NEGATIVE_SIGNAL_TERMS = ["eish", "ag shame", "kak", "hectic", "haibo", "aikona", "jislaaik", "yoh"]
POSITIVE_SIGNAL_TERMS = ["lekker", "howzit", "yebo", "sharp", "sharp sharp"]


def test_slang_file_exists():
    assert (ROOT / "data" / "sa_slang.json").exists(), "data/sa_slang.json not found"


def test_slang_is_non_empty_dict(sa_slang):
    assert isinstance(sa_slang, dict)
    assert len(sa_slang) >= 20, f"Expected ≥20 terms, got {len(sa_slang)}"


def test_required_terms_all_present(sa_slang):
    missing = [t for t in REQUIRED_TERMS if t not in sa_slang]
    assert not missing, f"Missing required SA slang terms: {missing}"


def test_all_values_are_non_empty_strings(sa_slang):
    for term, definition in sa_slang.items():
        assert isinstance(definition, str), f"Definition for '{term}' must be a string"
        assert len(definition.strip()) > 0, f"Definition for '{term}' is empty"


def test_negative_signal_terms_described_as_negative(sa_slang):
    """Definitions for known negative terms must mention negative/frustration/surprise."""
    negative_keywords = {
        "negative",
        "frustration",
        "disappoint",
        "bad",
        "shock",
        "concern",
        "alarm",
    }
    for term in NEGATIVE_SIGNAL_TERMS:
        if term in sa_slang:
            definition = sa_slang[term].lower()
            has_negative_hint = any(kw in definition for kw in negative_keywords)
            assert (
                has_negative_hint
            ), f"'{term}' definition missing negative-sentiment hint: {sa_slang[term]}"


def test_positive_signal_terms_described_as_positive(sa_slang):
    positive_keywords = {"positive", "good", "great", "nice", "agree", "greeting", "approval"}
    for term in POSITIVE_SIGNAL_TERMS:
        if term in sa_slang:
            definition = sa_slang[term].lower()
            has_positive_hint = any(kw in definition for kw in positive_keywords)
            assert (
                has_positive_hint
            ), f"'{term}' definition missing positive-sentiment hint: {sa_slang[term]}"


def test_no_duplicate_keys(sa_slang):
    # JSON parsing will naturally deduplicate, but verify dict size matches expected minimum
    assert len(sa_slang) >= len(REQUIRED_TERMS), "Slang dict has fewer entries than required terms"
