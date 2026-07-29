"""Small helpers for displaying UTC timestamps in the viewer's browser timezone."""

from html import escape
from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def format_eastern_timestamp(value: str | None) -> str:
    """Format an ISO timestamp as a readable US Eastern Time value."""
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        eastern = timestamp.astimezone(ZoneInfo("America/New_York"))
        return eastern.strftime("%B %-d, %Y at %-I:%M %p ET")
    except (TypeError, ValueError):
        return str(value or "Unknown")


def browser_time(value: str | None, label: str = "Local time") -> str:
    """Return a client-rendered timestamp using the browser's local timezone.

    The server should not guess a user's timezone. ISO timestamps are converted
    by the browser; non-ISO values are shown as supplied with a clear label.
    """
    if not value:
        return f"**{escape(label)}:** —"
    safe_value = escape(str(value), quote=True)
    return (
        f'<span class="wo-time" data-utc="{safe_value}"><strong>{escape(label)}:</strong> '
        f"<span>{safe_value}</span></span>"
        "<script>(function(){document.querySelectorAll('.wo-time').forEach(function(e){"
        "var v=e.dataset.utc,d=new Date(v);if(!Number.isNaN(d.getTime())&&/T|Z|\\+\\d{2}:?\\d{2}/.test(v)){"
        "e.lastElementChild.textContent=d.toLocaleString([], {dateStyle:'medium', timeStyle:'short'});}})})();</script>"
    )
