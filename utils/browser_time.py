"""Small helpers for displaying UTC timestamps in the viewer's browser timezone."""

from html import escape


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
        f'<span>{safe_value}</span></span>'
        "<script>(function(){document.querySelectorAll('.wo-time').forEach(function(e){"
        "var v=e.dataset.utc,d=new Date(v);if(!Number.isNaN(d.getTime())&&/T|Z|\\+\\d{2}:?\\d{2}/.test(v)){"
        "e.lastElementChild.textContent=d.toLocaleString([], {dateStyle:'medium', timeStyle:'short'});}})})();</script>"
    )
