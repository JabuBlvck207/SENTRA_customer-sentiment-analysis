"""Tests for sentiment response validation (no live API calls)."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.sentiment_analyzer import SentimentAnalyzer, SentimentAnalyzerError


def make_analyzer():
    a = SentimentAnalyzer()
    a.api_key = "test-key"
    a.model = "test-model"
    return a


def test_parse_valid_json():
    a = make_analyzer()
    api_resp = {
        "choices": [{
            "message": {
                "content": '''{
                    "sentiment": "Negative",
                    "explanation": "Customer is unhappy with delivery.",
                    "confidence": null,
                    "keywords": ["late delivery", "support"],
                    "complaint_categories": ["Delivery", "Customer Service"],
                    "suggested_action": "Review logistics partners."
                }'''
            }
        }]
    }
    result = a._parse_and_validate(api_resp, "My package arrived late")
    assert result["sentiment"] == "Negative"
    assert "late delivery" in result["keywords"]
    assert result["confidence"] is None
    assert "Delivery" in result["complaint_categories"]


def test_parse_markdown_wrapped():
    a = make_analyzer()
    api_resp = {
        "choices": [{
            "message": {
                "content": '```json\n{"sentiment": "Positive", "explanation": "Happy", "keywords": [], "complaint_categories": [], "suggested_action": null}\n```'
            }
        }]
    }
    result = a._parse_and_validate(api_resp, "Love it")
    assert result["sentiment"] == "Positive"


def test_invalid_sentiment_raises():
    a = make_analyzer()
    api_resp = {
        "choices": [{
            "message": {"content": '{"sentiment": "Happy", "explanation": "x"}'}
        }]
    }
    try:
        a._parse_and_validate(api_resp, "text")
        assert False, "Should have raised"
    except SentimentAnalyzerError:
        pass


def test_not_configured():
    a = SentimentAnalyzer()
    a.api_key = ""
    try:
        a.analyze("hello")
        assert False
    except SentimentAnalyzerError as e:
        assert "not configured" in str(e).lower()


def test_analyze_with_mock():
    a = make_analyzer()
    mock_response = {
        "choices": [{
            "message": {
                "content": '{"sentiment": "Neutral", "explanation": "Factual statement.", "confidence": null, "keywords": ["order"], "complaint_categories": [], "suggested_action": null}'
            }
        }]
    }
    with patch.object(a, "_call_api", return_value=mock_response):
        result = a.analyze("I ordered the blue shirt.")
        assert result["sentiment"] == "Neutral"
        assert "order" in result["keywords"]
