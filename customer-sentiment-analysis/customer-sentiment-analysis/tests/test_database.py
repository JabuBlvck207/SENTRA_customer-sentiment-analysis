"""Database operation tests (uses a temporary SQLite file)."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Point database to a temp file before importing
_tmpdir = tempfile.mkdtemp()
os.environ["DATABASE_PATH"] = str(Path(_tmpdir) / "test.db")

from backend.database import (
    init_db,
    insert_feedback,
    get_feedback_by_id,
    get_feedback_list,
    insert_document,
    get_document,
    update_document_status,
    get_stats,
    insert_document_report,
    get_document_report,
)


def setup_module():
    init_db()


def test_insert_and_get_feedback():
    fid = insert_feedback(
        feedback_text="Great product!",
        sentiment="Positive",
        explanation="Customer expresses satisfaction.",
        keywords=["great product"],
        complaint_categories=[],
        source_type="manual",
    )
    assert fid > 0
    rec = get_feedback_by_id(fid)
    assert rec["sentiment"] == "Positive"
    assert rec["keywords"] == ["great product"]
    assert rec["source_type"] == "manual"


def test_feedback_list_filter():
    insert_feedback("Bad service", "Negative", source_type="manual")
    data = get_feedback_list(sentiment="Negative", per_page=50)
    assert data["total"] >= 1
    assert all(i["sentiment"] == "Negative" for i in data["items"])


def test_document_lifecycle():
    did = insert_document("feedback.pdf", "abc123.pdf", "pdf", file_size=1024)
    doc = get_document(did)
    assert doc["original_filename"] == "feedback.pdf"
    assert doc["processing_status"] == "pending"

    update_document_status(did, "completed", total_items=5, positive=3, negative=1, neutral=1)
    doc = get_document(did)
    assert doc["processing_status"] == "completed"
    assert doc["positive_count"] == 3

    insert_document_report(
        did,
        overall_summary="Mostly positive",
        common_complaints=[{"category": "Delivery", "count": 1}],
        positive_themes=[{"theme": "quality", "count": 2}],
        recommended_improvements=["Improve delivery times"],
    )
    report = get_document_report(did)
    assert report["overall_sentiment_summary"] == "Mostly positive"
    assert len(report["common_complaints"]) == 1


def test_stats():
    stats = get_stats()
    assert "total_feedback" in stats
    assert "positive_pct" in stats
    assert stats["total_feedback"] >= 1
