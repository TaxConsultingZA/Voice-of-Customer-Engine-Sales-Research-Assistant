import pytest
from pydantic import ValidationError

from services.nlp.app.llm_contract import TaxonomyLLMOutput, load_taxonomy_labels, parse_llm_output
from services.nlp.app.llm_prompt import build_taxonomy_system_prompt


def test_llm_output_accepts_valid_label():
    label = sorted(load_taxonomy_labels())[0]
    output = TaxonomyLLMOutput(
        label=label,
        confidence=0.87,
        sentiment_polarity=-0.45,
        at_risk_flag=True,
        reason_short="Customer reports repeated payment and access failures.",
        language_detected="en",
    )
    assert output.label == label


def test_llm_output_rejects_unknown_label():
    with pytest.raises(ValidationError):
        TaxonomyLLMOutput(
            label="Fake.Domain.Label",
            confidence=0.9,
            sentiment_polarity=-0.2,
            at_risk_flag=False,
            reason_short="unknown",
            language_detected="en",
        )


def test_parse_llm_output_validates_json_contract():
    label = sorted(load_taxonomy_labels())[0]
    raw = (
        "{"
        f'"label":"{label}",'
        '"confidence":0.76,'
        '"sentiment_polarity":-0.31,'
        '"at_risk_flag":true,'
        '"reason_short":"Customer likely to churn due to unresolved outage.",'
        '"language_detected":"en"'
        "}"
    )
    parsed = parse_llm_output(raw)
    assert parsed.label == label
    assert parsed.at_risk_flag is True


def test_system_prompt_includes_label_list_and_contract():
    prompt = build_taxonomy_system_prompt()
    labels = load_taxonomy_labels()
    assert "STRICT JSON only" in prompt
    assert f"Allowed labels ({len(labels)} total)" in prompt
    assert "reason_short" in prompt
