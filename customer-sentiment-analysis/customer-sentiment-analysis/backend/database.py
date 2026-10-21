"""Database models and initialization for Customer Sentiment Analysis."""

import sqlite3
import json
import os
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path

# Default path relative to project root
DEFAULT_DB_PATH = os.getenv("DATABASE_PATH", "instance/sentiment.db")


def get_db_path():
    path = Path(DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database tables."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_filename TEXT NOT NULL,
                storage_id TEXT NOT NULL UNIQUE,
                file_type TEXT NOT NULL,
                processing_status TEXT NOT NULL DEFAULT 'pending',
                processing_error TEXT,
                total_feedback_items INTEGER DEFAULT 0,
                positive_count INTEGER DEFAULT 0,
                negative_count INTEGER DEFAULT 0,
                neutral_count INTEGER DEFAULT 0,
                upload_timestamp TEXT NOT NULL,
                completion_timestamp TEXT,
                file_size INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feedback_text TEXT NOT NULL,
                sentiment TEXT NOT NULL CHECK(sentiment IN ('Positive', 'Negative', 'Neutral')),
                explanation TEXT,
                confidence REAL,
                keywords TEXT,
                complaint_categories TEXT,
                suggested_action TEXT,
                source_type TEXT NOT NULL CHECK(source_type IN ('manual', 'document')),
                document_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL UNIQUE,
                overall_sentiment_summary TEXT,
                common_complaints TEXT,
                positive_themes TEXT,
                recommended_improvements TEXT,
                analysis_metadata TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """)

        # Indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_sentiment ON feedback(sentiment)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_document ON feedback(document_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status)")

    return True


def row_to_dict(row):
    """Convert sqlite3.Row to dict."""
    if row is None:
        return None
    return dict(row)


# ---------- Feedback helpers ----------

def insert_feedback(
    feedback_text: str,
    sentiment: str,
    explanation: str = None,
    confidence: float = None,
    keywords: list = None,
    complaint_categories: list = None,
    suggested_action: str = None,
    source_type: str = "manual",
    document_id: int = None,
) -> int:
    """Insert a feedback record and return its ID."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO feedback (
                feedback_text, sentiment, explanation, confidence,
                keywords, complaint_categories, suggested_action,
                source_type, document_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_text,
                sentiment,
                explanation,
                confidence,
                json.dumps(keywords or []),
                json.dumps(complaint_categories or []),
                suggested_action,
                source_type,
                document_id,
                now,
            ),
        )
        return cursor.lastrowid


def get_feedback_by_id(feedback_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM feedback WHERE id = ?", (feedback_id,)
        ).fetchone()
        return _parse_feedback_row(row)


def get_feedback_list(
    sentiment: str = None,
    source_type: str = None,
    document_id: int = None,
    search: str = None,
    date_from: str = None,
    date_to: str = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Return paginated feedback with optional filters."""
    conditions = []
    params = []

    if sentiment:
        conditions.append("sentiment = ?")
        params.append(sentiment)
    if source_type:
        conditions.append("source_type = ?")
        params.append(source_type)
    if document_id is not None:
        conditions.append("document_id = ?")
        params.append(document_id)
    if search:
        conditions.append("feedback_text LIKE ?")
        params.append(f"%{search}%")
    if date_from:
        conditions.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("created_at <= ?")
        params.append(date_to)

    where = " AND ".join(conditions) if conditions else "1=1"
    offset = (page - 1) * per_page

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM feedback WHERE {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT f.*, d.original_filename AS document_name
            FROM feedback f
            LEFT JOIN documents d ON f.document_id = d.id
            WHERE {where}
            ORDER BY f.created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [per_page, offset],
        ).fetchall()

        items = [_parse_feedback_row(r) for r in rows]

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page else 0,
    }


def _parse_feedback_row(row) -> dict:
    if row is None:
        return None
    d = dict(row)
    for key in ("keywords", "complaint_categories"):
        if d.get(key):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                d[key] = []
        else:
            d[key] = []
    return d


# ---------- Document helpers ----------

def insert_document(
    original_filename: str,
    storage_id: str,
    file_type: str,
    file_size: int = 0,
) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO documents (
                original_filename, storage_id, file_type,
                processing_status, upload_timestamp, file_size
            ) VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (original_filename, storage_id, file_type, now, file_size),
        )
        return cursor.lastrowid


def update_document_status(
    document_id: int,
    status: str,
    error: str = None,
    total_items: int = None,
    positive: int = None,
    negative: int = None,
    neutral: int = None,
):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_connection() as conn:
        fields = ["processing_status = ?"]
        params = [status]
        if error is not None:
            fields.append("processing_error = ?")
            params.append(error)
        if total_items is not None:
            fields.append("total_feedback_items = ?")
            params.append(total_items)
        if positive is not None:
            fields.append("positive_count = ?")
            params.append(positive)
        if negative is not None:
            fields.append("negative_count = ?")
            params.append(negative)
        if neutral is not None:
            fields.append("neutral_count = ?")
            params.append(neutral)
        if status in ("completed", "failed"):
            fields.append("completion_timestamp = ?")
            params.append(now)
        params.append(document_id)
        conn.execute(
            f"UPDATE documents SET {', '.join(fields)} WHERE id = ?",
            params,
        )


def get_document(document_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        return row_to_dict(row)


def get_documents(page: int = 1, per_page: int = 20) -> dict:
    offset = (page - 1) * per_page
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        rows = conn.execute(
            """
            SELECT * FROM documents
            ORDER BY upload_timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (per_page, offset),
        ).fetchall()
        items = [row_to_dict(r) for r in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page else 0,
    }


def delete_document(document_id: int) -> bool:
    with get_connection() as conn:
        # Cascade will remove feedback and reports
        cursor = conn.execute(
            "DELETE FROM documents WHERE id = ?", (document_id,)
        )
        return cursor.rowcount > 0


# ---------- Document Reports ----------

def insert_document_report(
    document_id: int,
    overall_summary: str = None,
    common_complaints: list = None,
    positive_themes: list = None,
    recommended_improvements: list = None,
    metadata: dict = None,
) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO document_reports (
                document_id, overall_sentiment_summary, common_complaints,
                positive_themes, recommended_improvements, analysis_metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                overall_summary,
                json.dumps(common_complaints or []),
                json.dumps(positive_themes or []),
                json.dumps(recommended_improvements or []),
                json.dumps(metadata or {}),
                now,
            ),
        )
        return cursor.lastrowid


def get_document_report(document_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM document_reports WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ("common_complaints", "positive_themes", "recommended_improvements", "analysis_metadata"):
            if d.get(key):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    d[key] = [] if key != "analysis_metadata" else {}
            else:
                d[key] = [] if key != "analysis_metadata" else {}
        return d


# ---------- Stats & Trends ----------

def get_stats(date_from: str = None, date_to: str = None) -> dict:
    conditions = []
    params = []
    if date_from:
        conditions.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("created_at <= ?")
        params.append(date_to)
    where = " AND ".join(conditions) if conditions else "1=1"

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM feedback WHERE {where}", params
        ).fetchone()[0]

        counts = conn.execute(
            f"""
            SELECT sentiment, COUNT(*) as cnt
            FROM feedback WHERE {where}
            GROUP BY sentiment
            """,
            params,
        ).fetchall()

        sentiment_counts = {"Positive": 0, "Negative": 0, "Neutral": 0}
        for r in counts:
            sentiment_counts[r["sentiment"]] = r["cnt"]

        doc_total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        doc_completed = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE processing_status = 'completed'"
        ).fetchone()[0]

    def pct(n):
        return round((n / total * 100) if total else 0, 1)

    return {
        "total_feedback": total,
        "positive_count": sentiment_counts["Positive"],
        "negative_count": sentiment_counts["Negative"],
        "neutral_count": sentiment_counts["Neutral"],
        "positive_pct": pct(sentiment_counts["Positive"]),
        "negative_pct": pct(sentiment_counts["Negative"]),
        "neutral_pct": pct(sentiment_counts["Neutral"]),
        "total_documents": doc_total,
        "completed_documents": doc_completed,
    }


def get_trends(date_from: str = None, date_to: str = None) -> list:
    """Return daily sentiment counts for trend charts."""
    conditions = []
    params = []
    if date_from:
        conditions.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("created_at <= ?")
        params.append(date_to)
    where = " AND ".join(conditions) if conditions else "1=1"

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT date(created_at) as day,
                   sentiment,
                   COUNT(*) as cnt
            FROM feedback
            WHERE {where}
            GROUP BY day, sentiment
            ORDER BY day
            """,
            params,
        ).fetchall()

    # Aggregate into day -> {Positive, Negative, Neutral}
    days = {}
    for r in rows:
        day = r["day"]
        if day not in days:
            days[day] = {"date": day, "Positive": 0, "Negative": 0, "Neutral": 0}
        days[day][r["sentiment"]] = r["cnt"]

    return list(days.values())


def get_complaint_categories(limit: int = 15) -> list:
    """Aggregate complaint categories across all feedback."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT complaint_categories FROM feedback WHERE complaint_categories IS NOT NULL AND complaint_categories != '[]'"
        ).fetchall()

    from collections import Counter
    counter = Counter()
    for r in rows:
        try:
            cats = json.loads(r["complaint_categories"] or "[]")
            for c in cats:
                if c:
                    counter[c] += 1
        except (json.JSONDecodeError, TypeError):
            continue

    return [{"category": k, "count": v} for k, v in counter.most_common(limit)]


def get_insights() -> dict:
    """Build customer insights from stored data."""
    stats = get_stats()
    complaints = get_complaint_categories(10)

    # Positive themes from keywords on positive feedback
    with get_connection() as conn:
        pos_rows = conn.execute(
            "SELECT keywords FROM feedback WHERE sentiment = 'Positive' AND keywords IS NOT NULL"
        ).fetchall()
        neg_rows = conn.execute(
            "SELECT keywords FROM feedback WHERE sentiment = 'Negative' AND keywords IS NOT NULL"
        ).fetchall()

    from collections import Counter
    pos_kw = Counter()
    neg_kw = Counter()
    for r in pos_rows:
        try:
            for k in json.loads(r["keywords"] or "[]"):
                if k:
                    pos_kw[k] += 1
        except Exception:
            pass
    for r in neg_rows:
        try:
            for k in json.loads(r["keywords"] or "[]"):
                if k:
                    neg_kw[k] += 1
        except Exception:
            pass

    trends = get_trends()
    trend_note = None
    if len(trends) < 3:
        trend_note = "Insufficient data for meaningful trend analysis (need at least 3 days of data)."

    return {
        "stats": stats,
        "top_complaints": complaints,
        "top_positive_keywords": [{"keyword": k, "count": v} for k, v in pos_kw.most_common(10)],
        "top_negative_keywords": [{"keyword": k, "count": v} for k, v in neg_kw.most_common(10)],
        "trends": trends,
        "trend_note": trend_note,
        "improvement_areas": [c["category"] for c in complaints[:5]],
    }
