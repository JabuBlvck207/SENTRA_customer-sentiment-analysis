"""Customer insights aggregation helpers."""

from backend.database import get_insights, get_complaint_categories, get_trends, get_stats


def build_insights_payload() -> dict:
    """Return the full insights object used by the API and frontend."""
    return get_insights()


def get_dashboard_stats(date_from: str = None, date_to: str = None) -> dict:
    return get_stats(date_from=date_from, date_to=date_to)


def get_sentiment_trends(date_from: str = None, date_to: str = None) -> list:
    return get_trends(date_from=date_from, date_to=date_to)
