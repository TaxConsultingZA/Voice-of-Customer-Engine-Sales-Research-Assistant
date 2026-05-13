import json
import os
import re
from functools import lru_cache
from pathlib import Path

_DEFAULT_SLANG_PATH = Path(__file__).parent.parent.parent.parent / "data" / "sa_slang.json"
SLANG_PATH = Path(os.getenv("SLANG_DICT_PATH", str(_DEFAULT_SLANG_PATH)))

_NEGATIVE_HINTS = {
    "frustrat",
    "negative",
    "disappoint",
    "concern",
    "shock",
    "alarm",
    "dismay",
    "bad",
    "terrible",
}
_POSITIVE_HINTS = {"positive", "good", "great", "greeting", "approval", "nice", "agree", "enjoy"}


@lru_cache(maxsize=1)
def _load_slang() -> dict:
    try:
        with SLANG_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


class SlangPreprocessor:
    def __init__(self):
        self._slang = _load_slang()

    def get_sentiment_adjustment(self, text: str) -> float:
        """Returns polarity adjustment [-0.3, 0.3] based on SA slang hits."""
        text_lower = text.lower()
        adjustment = 0.0

        for term, definition in self._slang.items():
            pattern = r"\b" + re.escape(term.lower()) + r"\b"
            if re.search(pattern, text_lower):
                defn = definition.lower()
                if any(hint in defn for hint in _NEGATIVE_HINTS):
                    adjustment -= 0.15
                elif any(hint in defn for hint in _POSITIVE_HINTS):
                    adjustment += 0.15

        return max(-0.3, min(0.3, adjustment))

    def contains_slang(self, text: str) -> bool:
        text_lower = text.lower()
        return any(
            re.search(r"\b" + re.escape(term.lower()) + r"\b", text_lower) for term in self._slang
        )
