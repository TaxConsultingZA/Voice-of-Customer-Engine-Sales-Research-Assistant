"""
UEC Contract Tests
------------------
Every pipeline change must validate against the Universal Event Contract.
Build fails if any of these tests fail.
"""

import copy

import jsonschema
import pytest

ALL_CHANNELS = [
    "email", "chat", "call", "sms", "whatsapp",
    "web_form", "mobile_app", "social_media",
    "in_person", "survey", "api", "internal_note", "sales_call",
]

ALL_ENTITY_TYPES = ["PRODUCT", "FEATURE", "PERSON", "ORG", "LOCATION", "DATE", "CURRENCY"]


def test_valid_event_passes_schema(uec_schema, sample_uec_event):
    jsonschema.validate(instance=sample_uec_event, schema=uec_schema)


def test_missing_required_fields_fail(uec_schema):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance={"event_id": "123"}, schema=uec_schema)


def test_invalid_channel_rejected(uec_schema, sample_uec_event):
    bad = copy.deepcopy(sample_uec_event)
    bad["channel"] = "carrier_pigeon"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=uec_schema)


def test_all_valid_channels_accepted(uec_schema, sample_uec_event):
    for channel in ALL_CHANNELS:
        event = copy.deepcopy(sample_uec_event)
        event["channel"] = channel
        jsonschema.validate(instance=event, schema=uec_schema)


def test_sentiment_polarity_above_max_rejected(uec_schema, sample_uec_event):
    bad = copy.deepcopy(sample_uec_event)
    bad["sentiment"]["polarity"] = 1.1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=uec_schema)


def test_sentiment_polarity_below_min_rejected(uec_schema, sample_uec_event):
    bad = copy.deepcopy(sample_uec_event)
    bad["sentiment"]["polarity"] = -1.1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=uec_schema)


def test_sentiment_confidence_above_max_rejected(uec_schema, sample_uec_event):
    bad = copy.deepcopy(sample_uec_event)
    bad["sentiment"]["confidence"] = 1.01
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=uec_schema)


def test_taxonomy_path_valid_format_accepted(uec_schema, sample_uec_event):
    valid_paths = [
        "Authentication.Login.PasswordReset",
        "Onboarding.Registration.EmailVerification",
        "Reporting.Dashboards.Export",
    ]
    for path in valid_paths:
        event = copy.deepcopy(sample_uec_event)
        event["taxonomy_path"] = path
        jsonschema.validate(instance=event, schema=uec_schema)


def test_taxonomy_path_invalid_format_rejected(uec_schema, sample_uec_event):
    invalid_paths = [
        "authentication.login.reset",  # must start uppercase
        "Auth.Login",                  # only two segments
        "Authentication-Login-Reset",  # wrong separator
        "plain_string",
    ]
    for path in invalid_paths:
        bad = copy.deepcopy(sample_uec_event)
        bad["taxonomy_path"] = path
        with pytest.raises(jsonschema.ValidationError, match=""):
            jsonschema.validate(instance=bad, schema=uec_schema)


def test_customer_id_wrong_length_rejected(uec_schema, sample_uec_event):
    bad = copy.deepcopy(sample_uec_event)
    bad["customer_id"] = "tooshort"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=uec_schema)


def test_all_entity_types_accepted(uec_schema, sample_uec_event):
    for entity_type in ALL_ENTITY_TYPES:
        event = copy.deepcopy(sample_uec_event)
        event["entities"] = [{"type": entity_type, "value": "example"}]
        jsonschema.validate(instance=event, schema=uec_schema)


def test_invalid_entity_type_rejected(uec_schema, sample_uec_event):
    bad = copy.deepcopy(sample_uec_event)
    bad["entities"] = [{"type": "UNKNOWN_TYPE", "value": "x"}]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=uec_schema)


def test_additional_properties_rejected(uec_schema, sample_uec_event):
    bad = copy.deepcopy(sample_uec_event)
    bad["undocumented_field"] = "sneaky"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=uec_schema)


def test_arr_linkage_negative_rejected(uec_schema, sample_uec_event):
    bad = copy.deepcopy(sample_uec_event)
    bad["arr_linkage"] = {"account_arr": -500, "at_risk_flag": False}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=uec_schema)


def test_event_without_optional_fields_passes(uec_schema):
    """Only the six required fields must be present."""
    minimal = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2024-01-15T09:00:00Z",
        "channel": "whatsapp",
        "customer_id": "c" * 64,
        "sentiment": {"polarity": 0.1, "confidence": 0.7},
        "taxonomy_path": "Onboarding.Registration.Setup",
    }
    jsonschema.validate(instance=minimal, schema=uec_schema)
