import json
import logging

from app.core.logging import StructuredJsonFormatter, scrub_sensitive_dict


def test_scrub_sensitive_dict():
    raw_data = {
        "user_id": "usr_123",
        "email": "editor@aurahealth.com",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "api_key": "gemini_secret_key_abc",
        "nested": {
            "password": "supersecretpassword",
            "safe_field": "public_value",
        },
        "items": [
            {"token": "secret_session_token", "name": "item1"},
            "plain_string",
        ],
    }

    scrubbed = scrub_sensitive_dict(raw_data)

    assert scrubbed["user_id"] == "usr_123"
    assert scrubbed["email"] == "editor@aurahealth.com"
    assert scrubbed["authorization"] == "[REDACTED]"
    assert scrubbed["api_key"] == "[REDACTED]"
    assert scrubbed["nested"]["password"] == "[REDACTED]"
    assert scrubbed["nested"]["safe_field"] == "public_value"
    assert scrubbed["items"][0]["token"] == "[REDACTED]"
    assert scrubbed["items"][0]["name"] == "item1"


def test_structured_json_formatter():
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Guideline parsed successfully",
        args=(),
        exc_info=None,
    )
    record.request_id = "req_test_998877"
    record.extra_data = {"document_id": "doc_456", "token": "sensitive_leak"}

    formatted_str = formatter.format(record)
    parsed = json.loads(formatted_str)

    assert parsed["level"] == "INFO"
    assert parsed["message"] == "Guideline parsed successfully"
    assert parsed["request_id"] == "req_test_998877"
    assert parsed["data"]["document_id"] == "doc_456"
    assert parsed["data"]["token"] == "[REDACTED]"
    assert "timestamp" in parsed
