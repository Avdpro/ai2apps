"""Canonical UTC timestamp helpers for durable platform records."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return an aware UTC datetime."""

    return datetime.now(UTC)


def format_utc(value: datetime) -> str:
    """Format an aware datetime as RFC 3339 UTC with microsecond precision."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Platform timestamps must be timezone-aware")
    return (
        value.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def utc_now_text() -> str:
    """Return the current time in canonical durable representation."""

    return format_utc(utc_now())


def parse_utc(value: str) -> datetime:
    """Parse an RFC 3339 timestamp and normalize it to aware UTC."""

    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid RFC 3339 timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Platform timestamps must include a timezone")
    return parsed.astimezone(UTC)
