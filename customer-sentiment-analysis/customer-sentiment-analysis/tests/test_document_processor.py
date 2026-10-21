"""Document processor unit tests."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.document_processor import (
    extract_text,
    segment_feedback,
    chunk_for_ai,
    DocumentProcessingError,
)


def test_extract_txt():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("This is a test feedback document.\n\nSecond paragraph of feedback.")
        path = f.name
    try:
        text = extract_text(path, "txt")
        assert "test feedback" in text
        assert "Second paragraph" in text
    finally:
        Path(path).unlink(missing_ok=True)


def test_segment_feedback():
    text = (
        "I really love this great product and would buy again.\n\n"
        "Terrible support experience with no response for days.\n\n\n"
        "The packaging was okay overall but nothing special."
    )
    segs = segment_feedback(text)
    assert len(segs) >= 2
    assert any("great product" in s.lower() for s in segs)


def test_chunk_for_ai():
    short = ["Hello world"]
    assert chunk_for_ai(short) == short

    long = ["x" * 5000]
    chunks = chunk_for_ai(long)
    assert len(chunks) >= 2
    assert all(len(c) <= 3500 for c in chunks)


def test_empty_text_segments():
    assert segment_feedback("") == []
    assert segment_feedback("   ") == []
