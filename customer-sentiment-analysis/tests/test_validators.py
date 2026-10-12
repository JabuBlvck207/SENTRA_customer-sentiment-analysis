"""Unit tests for validators."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.validators import (
    allowed_file,
    sanitize_filename,
    validate_feedback_text,
    validate_file_size,
    is_valid_sentiment,
)


def test_allowed_file():
    assert allowed_file("report.pdf") is True
    assert allowed_file("notes.TXT") is True
    assert allowed_file("doc.docx") is False
    assert allowed_file("") is False
    assert allowed_file("noext") is False


def test_sanitize_filename():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("my file (1).pdf") == "my file (1).pdf"
    assert "\\" not in sanitize_filename("a\\b\\c.txt")


def test_validate_feedback_text():
    ok, text = validate_feedback_text("  Hello world  ")
    assert ok is True
    assert text == "Hello world"

    ok, msg = validate_feedback_text("")
    assert ok is False

    ok, msg = validate_feedback_text("x" * 10001)
    assert ok is False


def test_validate_file_size():
    ok, _ = validate_file_size(1024, max_mb=10)
    assert ok is True

    ok, msg = validate_file_size(11 * 1024 * 1024, max_mb=10)
    assert ok is False

    ok, msg = validate_file_size(0)
    assert ok is False


def test_is_valid_sentiment():
    assert is_valid_sentiment("Positive") is True
    assert is_valid_sentiment("Negative") is True
    assert is_valid_sentiment("Neutral") is True
    assert is_valid_sentiment("positive") is False
    assert is_valid_sentiment("Happy") is False
