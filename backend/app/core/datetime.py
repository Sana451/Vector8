from datetime import UTC, datetime


def get_datetime_utc() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(UTC)
