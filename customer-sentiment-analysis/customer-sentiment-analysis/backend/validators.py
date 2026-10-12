"""Input validation helpers."""

import re
from pathlib import Path

ALLOWED_EXTENSIONS = {".pdf", ".txt"}
ALLOWED_MIME_PREFIXES = {
    "application/pdf",
    "text/plain",
    "text/txt",
}

# Soft limit – hard limit enforced by Flask / Werkzeug
DEFAULT_MAX_SIZE_MB = 10


def allowed_file(filename: str) -> bool:
    if not filename:
        return False
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def sanitize_filename(filename: str) -> str:
    """Return a safe basename without path components."""
    name = Path(filename).name
    # Remove any remaining path separators and control chars
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name)
    name = name.strip(". ")
    if not name:
        name = "upload"
    return name[:200]


def validate_feedback_text(text: str, max_len: int = 10000) -> tuple[bool, str]:
    if text is None:
        return False, "Feedback text is required."
    text = text.strip()
    if not text:
        return False, "Feedback text cannot be empty."
    if len(text) > max_len:
        return False, f"Feedback text exceeds maximum length of {max_len} characters."
    return True, text


def validate_file_size(size_bytes: int, max_mb: int = DEFAULT_MAX_SIZE_MB) -> tuple[bool, str]:
    max_bytes = max_mb * 1024 * 1024
    if size_bytes > max_bytes:
        return False, f"File exceeds maximum size of {max_mb} MB."
    if size_bytes == 0:
        return False, "File is empty."
    return True, ""


def is_valid_sentiment(sentiment: str) -> bool:
    return sentiment in ("Positive", "Negative", "Neutral")
