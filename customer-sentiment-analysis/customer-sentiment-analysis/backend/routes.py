"""Flask API routes for Customer Sentiment Analysis."""

import os
import logging
from functools import wraps
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app
from werkzeug.exceptions import RequestEntityTooLarge

from backend.database import (
    init_db,
    insert_feedback,
    get_feedback_by_id,
    get_feedback_list,
    insert_document,
    update_document_status,
    get_document,
    get_documents,
    delete_document,
    insert_document_report,
    get_document_report,
    get_stats,
    get_trends,
    get_insights,
)
from backend.sentiment_analyzer import analyzer, SentimentAnalyzerError
from backend.document_processor import (
    save_uploaded_file,
    extract_text,
    segment_feedback,
    chunk_for_ai,
    cleanup_file,
    DocumentProcessingError,
)
from backend.validators import validate_feedback_text

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__, url_prefix="/api")


def json_error(message: str, status: int = 400, **extra):
    payload = {"success": False, "error": message}
    payload.update(extra)
    return jsonify(payload), status


# ---------- Health ----------

@api.route("/health", methods=["GET"])
def health():
    ai_status = analyzer.health_check()
    return jsonify({
        "success": True,
        "status": "ok",
        "ai_service": ai_status,
        "model": analyzer.model if analyzer.is_configured() else None,
    })


# ---------- Individual analysis ----------

@api.route("/analyze", methods=["POST"])
def analyze_feedback():
    data = request.get_json(silent=True) or {}
    text = data.get("text") or data.get("feedback") or ""

    ok, result = validate_feedback_text(text)
    if not ok:
        return json_error(result)

    text = result  # cleaned

    try:
        analysis = analyzer.analyze(text)
    except SentimentAnalyzerError as e:
        logger.warning("Analysis failed: %s", e)
        return json_error(str(e), 502)
    except Exception as e:
        logger.exception("Unexpected analysis error")
        return json_error("An unexpected error occurred during analysis.", 500)

    try:
        feedback_id = insert_feedback(
            feedback_text=text,
            sentiment=analysis["sentiment"],
            explanation=analysis.get("explanation"),
            confidence=analysis.get("confidence"),
            keywords=analysis.get("keywords"),
            complaint_categories=analysis.get("complaint_categories"),
            suggested_action=analysis.get("suggested_action"),
            source_type="manual",
        )
    except Exception as e:
        logger.exception("Failed to save feedback")
        return json_error("Analysis succeeded but could not be saved.", 500)

    record = get_feedback_by_id(feedback_id)
    return jsonify({
        "success": True,
        "feedback_id": feedback_id,
        "analysis": analysis,
        "record": record,
    })


# ---------- Documents ----------

@api.route("/documents/upload", methods=["POST"])
def upload_document():
    if "file" not in request.files:
        return json_error("No file part in the request.")

    file = request.files["file"]
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    max_mb = current_app.config.get("MAX_UPLOAD_SIZE_MB", 10)

    try:
        storage_id, original, file_type, size = save_uploaded_file(
            file, upload_folder, max_mb=max_mb
        )
    except DocumentProcessingError as e:
        return json_error(str(e))
    except RequestEntityTooLarge:
        return json_error(f"File exceeds maximum size of {max_mb} MB.", 413)
    except Exception as e:
        logger.exception("Upload failed")
        return json_error("Failed to process uploaded file.", 500)

    try:
        doc_id = insert_document(
            original_filename=original,
            storage_id=storage_id,
            file_type=file_type,
            file_size=size,
        )
    except Exception as e:
        cleanup_file(storage_id, upload_folder)
        logger.exception("DB insert failed for document")
        return json_error("Failed to record uploaded document.", 500)

    doc = get_document(doc_id)
    return jsonify({
        "success": True,
        "document": doc,
        "message": "File uploaded successfully. Call the analyze endpoint to process it.",
    }), 201


@api.route("/documents/<int:document_id>/analyze", methods=["POST"])
def analyze_document(document_id: int):
    doc = get_document(document_id)
    if not doc:
        return json_error("Document not found.", 404)

    if doc["processing_status"] == "processing":
        return json_error("Document is already being processed.", 409)
    if doc["processing_status"] == "completed":
        # Allow re-analysis only if forced; otherwise return existing report
        report = get_document_report(document_id)
        return jsonify({
            "success": True,
            "message": "Document already analysed.",
            "document": doc,
            "report": report,
            "already_completed": True,
        })

    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    file_path = Path(upload_folder) / doc["storage_id"]

    update_document_status(document_id, "processing")

    try:
        text = extract_text(str(file_path), doc["file_type"])
    except DocumentProcessingError as e:
        update_document_status(document_id, "failed", error=str(e))
        return json_error(str(e), 422)

    segments = segment_feedback(text)
    chunks = chunk_for_ai(segments)

    if not chunks:
        update_document_status(document_id, "failed", error="No usable text segments found.")
        return json_error("No usable text segments found in the document.", 422)

    # Cap number of chunks to avoid runaway cost / time
    MAX_CHUNKS = 40
    if len(chunks) > MAX_CHUNKS:
        chunks = chunks[:MAX_CHUNKS]
        truncated = True
    else:
        truncated = False

    results = []
    positive = negative = neutral = 0
    all_complaints = []
    all_positive_themes = []
    failed_chunks = 0

    for i, chunk in enumerate(chunks):
        try:
            analysis = analyzer.analyze(chunk)
            insert_feedback(
                feedback_text=chunk,
                sentiment=analysis["sentiment"],
                explanation=analysis.get("explanation"),
                confidence=analysis.get("confidence"),
                keywords=analysis.get("keywords"),
                complaint_categories=analysis.get("complaint_categories"),
                suggested_action=analysis.get("suggested_action"),
                source_type="document",
                document_id=document_id,
            )
            results.append(analysis)
            if analysis["sentiment"] == "Positive":
                positive += 1
                all_positive_themes.extend(analysis.get("keywords") or [])
            elif analysis["sentiment"] == "Negative":
                negative += 1
                all_complaints.extend(analysis.get("complaint_categories") or [])
            else:
                neutral += 1
        except SentimentAnalyzerError as e:
            logger.warning("Chunk %d analysis failed: %s", i, e)
            failed_chunks += 1
            continue
        except Exception:
            logger.exception("Unexpected error on chunk %d", i)
            failed_chunks += 1
            continue

    total = positive + negative + neutral
    if total == 0:
        update_document_status(
            document_id, "failed",
            error="All analysis requests failed. Check API key and model availability.",
        )
        return json_error(
            "Could not analyse any portion of the document. Check AI service status.",
            502,
        )

    update_document_status(
        document_id,
        "completed",
        total_items=total,
        positive=positive,
        negative=negative,
        neutral=neutral,
    )

    # Aggregate report
    from collections import Counter
    complaint_counts = Counter(all_complaints)
    theme_counts = Counter(all_positive_themes)

    common_complaints = [{"category": k, "count": v} for k, v in complaint_counts.most_common(10)]
    positive_themes = [{"theme": k, "count": v} for k, v in theme_counts.most_common(10)]

    overall = "Neutral"
    if positive > negative and positive > neutral:
        overall = "Positive"
    elif negative > positive and negative > neutral:
        overall = "Negative"

    summary = (
        f"Analysed {total} feedback segment(s) from the document. "
        f"Overall dominant sentiment: {overall}. "
        f"Positive: {positive}, Negative: {negative}, Neutral: {neutral}."
    )
    if truncated:
        summary += f" (Note: only the first {MAX_CHUNKS} segments were analysed due to length limits.)"
    if failed_chunks:
        summary += f" {failed_chunks} segment(s) could not be analysed."

    recommendations = []
    for c in common_complaints[:5]:
        recommendations.append(f"Address recurring issue: {c['category']} ({c['count']} mentions).")

    insert_document_report(
        document_id=document_id,
        overall_summary=summary,
        common_complaints=common_complaints,
        positive_themes=positive_themes,
        recommended_improvements=recommendations,
        metadata={
            "segments_analysed": total,
            "chunks_attempted": len(chunks),
            "failed_chunks": failed_chunks,
            "truncated": truncated,
            "dominant_sentiment": overall,
        },
    )

    doc = get_document(document_id)
    report = get_document_report(document_id)

    return jsonify({
        "success": True,
        "document": doc,
        "report": report,
        "feedback_count": total,
        "sentiment_counts": {
            "Positive": positive,
            "Negative": negative,
            "Neutral": neutral,
        },
    })


@api.route("/documents", methods=["GET"])
def list_documents():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    data = get_documents(page=page, per_page=per_page)
    return jsonify({"success": True, **data})


@api.route("/documents/<int:document_id>", methods=["GET"])
def get_document_detail(document_id: int):
    doc = get_document(document_id)
    if not doc:
        return json_error("Document not found.", 404)
    report = get_document_report(document_id)
    feedback = get_feedback_list(document_id=document_id, per_page=100)
    return jsonify({
        "success": True,
        "document": doc,
        "report": report,
        "feedback": feedback["items"],
    })


@api.route("/documents/<int:document_id>", methods=["DELETE"])
def remove_document(document_id: int):
    doc = get_document(document_id)
    if not doc:
        return json_error("Document not found.", 404)
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    cleanup_file(doc["storage_id"], upload_folder)
    delete_document(document_id)
    return jsonify({"success": True, "message": "Document and associated records deleted."})


# ---------- Feedback list ----------

@api.route("/feedback", methods=["GET"])
def list_feedback():
    sentiment = request.args.get("sentiment")
    source_type = request.args.get("source_type")
    search = request.args.get("search")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    document_id = request.args.get("document_id", type=int)

    data = get_feedback_list(
        sentiment=sentiment,
        source_type=source_type,
        document_id=document_id,
        search=search,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page,
    )
    return jsonify({"success": True, **data})


@api.route("/feedback/<int:feedback_id>", methods=["GET"])
def get_feedback(feedback_id: int):
    record = get_feedback_by_id(feedback_id)
    if not record:
        return json_error("Feedback not found.", 404)
    return jsonify({"success": True, "feedback": record})


# ---------- Stats / Trends / Insights ----------

@api.route("/stats", methods=["GET"])
def stats():
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    data = get_stats(date_from=date_from, date_to=date_to)
    return jsonify({"success": True, "stats": data})


@api.route("/trends", methods=["GET"])
def trends():
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    data = get_trends(date_from=date_from, date_to=date_to)
    return jsonify({"success": True, "trends": data})


@api.route("/insights", methods=["GET"])
def insights():
    data = get_insights()
    return jsonify({"success": True, "insights": data})
