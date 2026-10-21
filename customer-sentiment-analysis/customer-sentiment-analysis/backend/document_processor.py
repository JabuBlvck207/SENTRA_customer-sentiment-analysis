"""PDF / TXT document text extraction and chunking for sentiment analysis."""

import os
import re
import uuid
import logging
from pathlib import Path
from typing import List, Tuple, Optional

import fitz  # PyMuPDF

from backend.validators import allowed_file, sanitize_filename, validate_file_size

logger = logging.getLogger(__name__)

# Approximate token budget – leave room for system prompt + response
MAX_CHARS_PER_CHUNK = 3500
MIN_USABLE_TEXT_LENGTH = 20


class DocumentProcessingError(Exception):
    pass


def save_uploaded_file(file_storage, upload_folder: str, max_mb: int = 10) -> Tuple[str, str, str, int]:
    """
    Validate and securely save an uploaded file.
    Returns (storage_id, original_filename, file_type, file_size).
    """
    if not file_storage or not file_storage.filename:
        raise DocumentProcessingError("No file provided.")

    original = sanitize_filename(file_storage.filename)
    if not allowed_file(original):
        raise DocumentProcessingError(
            "Unsupported file type. Only PDF and TXT files are accepted."
        )

    # Read content to check size (Werkzeug may not have content_length)
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)

    ok, msg = validate_file_size(size, max_mb)
    if not ok:
        raise DocumentProcessingError(msg)

    ext = Path(original).suffix.lower()
    file_type = "pdf" if ext == ".pdf" else "txt"

    storage_id = f"{uuid.uuid4().hex}{ext}"
    dest = Path(upload_folder) / storage_id
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        file_storage.save(str(dest))
    except Exception as e:
        raise DocumentProcessingError(f"Failed to save uploaded file: {e}")

    return storage_id, original, file_type, size


def extract_text(file_path: str, file_type: str) -> str:
    """Extract plain text from a PDF or TXT file."""
    path = Path(file_path)
    if not path.is_file():
        raise DocumentProcessingError("Stored file not found.")

    if file_type == "txt":
        return _extract_txt(path)
    if file_type == "pdf":
        return _extract_pdf(path)
    raise DocumentProcessingError(f"Unsupported file type: {file_type}")


def _extract_txt(path: Path) -> str:
    # Try common encodings
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = path.read_text(encoding=encoding)
            return text.strip()
        except (UnicodeDecodeError, LookupError):
            continue
    raise DocumentProcessingError("Could not decode text file with supported encodings.")


def _extract_pdf(path: Path) -> str:
    try:
        doc = fitz.open(str(path))
    except Exception as e:
        raise DocumentProcessingError(f"Cannot open PDF: {e}")

    try:
        pages_text = []
        for page in doc:
            text = page.get_text("text")
            if text:
                pages_text.append(text)
        full = "\n\n".join(pages_text).strip()

        if not full or len(full) < MIN_USABLE_TEXT_LENGTH:
            # Likely a scanned / image-only PDF
            raise DocumentProcessingError(
                "No selectable text found in the PDF. "
                "This may be a scanned document that requires OCR, which is not enabled by default."
            )
        return full
    finally:
        doc.close()


def segment_feedback(text: str) -> List[str]:
    """
    Split extracted document text into plausible feedback units.
    Prefer paragraph / line breaks that look like separate comments.
    Avoid treating every sentence as a distinct customer comment.
    """
    if not text or not text.strip():
        return []

    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Split on double newlines or lines that look like separators
    blocks = re.split(r"\n\s*\n+", text)

    segments = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Further split very long blocks on single newlines if they look like list items
        if len(block) > MAX_CHARS_PER_CHUNK:
            lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
            current = []
            current_len = 0
            for ln in lines:
                if current_len + len(ln) + 1 > MAX_CHARS_PER_CHUNK and current:
                    segments.append("\n".join(current))
                    current = [ln]
                    current_len = len(ln)
                else:
                    current.append(ln)
                    current_len += len(ln) + 1
            if current:
                segments.append("\n".join(current))
        else:
            # Skip tiny fragments that are unlikely to be real feedback
            if len(block) >= MIN_USABLE_TEXT_LENGTH:
                segments.append(block)

    # If still nothing useful, fall back to whole text as one segment (truncated)
    if not segments and text.strip():
        segments = [text.strip()[:MAX_CHARS_PER_CHUNK]]

    return segments


def chunk_for_ai(segments: List[str]) -> List[str]:
    """
    Ensure each piece sent to the model is within size limits.
    Multiple short segments can be batched if desired; for clarity we keep
    one segment per analysis call when possible.
    """
    chunks = []
    for seg in segments:
        if len(seg) <= MAX_CHARS_PER_CHUNK:
            chunks.append(seg)
        else:
            # Hard split remaining oversized pieces
            for i in range(0, len(seg), MAX_CHARS_PER_CHUNK):
                part = seg[i : i + MAX_CHARS_PER_CHUNK].strip()
                if part:
                    chunks.append(part)
    return chunks


def cleanup_file(storage_id: str, upload_folder: str) -> None:
    """Delete a stored file if it exists."""
    path = Path(upload_folder) / storage_id
    try:
        if path.is_file():
            path.unlink()
    except OSError as e:
        logger.warning("Could not delete file %s: %s", path, e)
