"""
SA Sentiment Benchmark — Golden Test Suite
-------------------------------------------
Gate: F1 Score ≥ 0.94 on the 500-sample SA customer corpus.
Build fails and model rolls back if this threshold is not met.

Status: SKIPPED until model training is complete.
To activate: place model weights at models/sentiment-sa-v2/
             and corpus at tests/fixtures/sa_customer_corpus/
"""

import pytest

CORPUS_PATH = "tests/fixtures/sa_customer_corpus"
MODEL_PATH = "models/sentiment-sa-v2"
F1_THRESHOLD = 0.94
MIN_CORPUS_SIZE = 500


@pytest.mark.skip(reason="Requires trained model at models/sentiment-sa-v2 — activate post-training")
def test_sa_sentiment_f1_benchmark():
    """F1 ≥ 0.94 on SA customer corpus. Build gate — see SYSTEM_PROMPT §3.3."""
    from pathlib import Path
    import json
    from sklearn.metrics import f1_score

    corpus_dir = Path(CORPUS_PATH)
    assert corpus_dir.exists(), f"Corpus not found at {CORPUS_PATH}"

    samples = list(corpus_dir.glob("*.json"))
    assert len(samples) >= MIN_CORPUS_SIZE, (
        f"Corpus has {len(samples)} samples — need ≥{MIN_CORPUS_SIZE}"
    )

    texts, true_labels = [], []
    for path in samples:
        sample = json.loads(path.read_text(encoding="utf-8"))
        texts.append(sample["text"])
        true_labels.append(sample["label"])  # "positive" | "negative" | "neutral"

    # Import here so the skip fires before any import errors
    from services.nlp.app.sentiment import SentimentModel
    model = SentimentModel(model_path=MODEL_PATH)
    predictions = [model.predict(t).label for t in texts]

    f1 = f1_score(true_labels, predictions, average="weighted")
    assert f1 >= F1_THRESHOLD, (
        f"Sentiment F1 {f1:.3f} is below required threshold {F1_THRESHOLD}. "
        f"Rolling back model weights — see incident protocol §9.1."
    )


@pytest.mark.skip(reason="Requires trained model — activate post-training")
def test_sa_slang_sentiment_cases():
    """Specific SA slang terms must be classified correctly."""
    from services.nlp.app.sentiment import SentimentModel
    model = SentimentModel(model_path=MODEL_PATH)

    cases = [
        ("This service is lekker!", "positive"),
        ("Eish, the app crashed again", "negative"),
        ("Ag shame, I can't log in", "negative"),
        ("Howzit! Login works now, thanks", "positive"),
        ("Ja nee, the interface is confusing", "negative"),
        ("Yoh, this is hectic — nothing is working", "negative"),
        ("Sharp sharp, problem resolved, baie dankie!", "positive"),
    ]

    for text, expected in cases:
        result = model.predict(text)
        assert result.label == expected, (
            f"Slang misclassified: '{text}' → got '{result.label}', expected '{expected}'"
        )
