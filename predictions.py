"""Wicket Oracle Streamlit entry point and grouped application navigation."""

import streamlit as st
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from pages_app import (
    fixtures_table,
    match_hub,
    model_performance,
    player_props,
    rivalry_analyzer,
    statistics,
    team_deep_dive,
    todays_matches,
    value_bets,
)
from pipeline.status import ProductionStatus, plain_language_status
try:
    from utils.browser_time import format_eastern_timestamp
except ImportError:  # Compatibility with deployments using an older utility module.
    def format_eastern_timestamp(value):
        try:
            timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            return timestamp.astimezone(ZoneInfo("America/New_York")).strftime(
                "%B %-d, %Y at %-I:%M %p ET"
            )
        except (TypeError, ValueError):
            return str(value or "Unknown")
from utils.cache import (
    APP_ENV,
    get_cache_metadata,
    is_cache_stale,
    is_mock_data,
    load_cache_data_only,
)
from utils.data import get_competition_status

st.set_page_config(
    page_title="Wicket Oracle",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { border-right: 1px solid #e5e7eb; }
    [data-testid="stSidebar"] img { max-width: 150px; margin-bottom: .25rem; }
    .wo-kicker { color: #64748b; font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; }
    .wo-status { border: 1px solid #dbe3ec; border-radius: 12px; padding: 1rem 1.1rem; background: #fff; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _status_rows() -> list[dict]:
    raw = get_competition_status().get("competitions", {})
    rows = []
    for slug, item in raw.items():
        status = item.get("status", "not_run")
        try:
            status_text = plain_language_status(ProductionStatus(status))
        except ValueError:
            status_text = status.replace("_", " ").title()
        rows.append(
            {
                "Competition": item.get("competition_name", slug),
                "Status": status_text,
                "Fixtures": item.get("fixtures_count", item.get("fixture_count", 0)),
                "Markets": item.get("draftkings_events", item.get("draftkings_event_count", 0)),
                "Value bets": item.get("qualifying_bets", item.get("qualifying_bet_count", 0)),
            }
        )
    return rows


def status_page() -> None:
    """System health and competition coverage view."""
    st.title("Wicket Oracle")
    st.markdown('<div class="wo-kicker">Cricket betting analytics · system status</div>', unsafe_allow_html=True)
    st.write("")

    metadata = get_cache_metadata("last_updated") or get_cache_metadata("todays_matches") or {}
    stale = is_cache_stale("last_updated", max_age_hours=24)
    simulated = is_mock_data("last_updated") or is_mock_data("todays_matches")
    status_label = (
        "Simulated data" if simulated and APP_ENV == "development" else ("Needs refresh" if stale else "Live")
    )
    a, b, c = st.columns(3)
    a.metric("System", status_label, help="Status reflects the most recent cached pipeline output.")
    b.metric("Environment", APP_ENV.title())
    c.metric("Model", "h2h-v1" if load_cache_data_only("todays_matches") else "Not available")

    if metadata.get("generated_at"):
        st.markdown(f"**Last pipeline update:** {format_eastern_timestamp(metadata['generated_at'])}")

    st.subheader("Competition coverage")
    rows = _status_rows()
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info("No competition status has been cached yet.")

    st.subheader("What’s where")
    st.caption(
        "Use the grouped sidebar navigation to move between live matches, betting markets, team/tournament research, and model diagnostics."
    )


def _sidebar_brand() -> None:
    with st.sidebar:
        st.image("data_files/logo.png", width="stretch")
        st.markdown("**Wicket Oracle**")
        st.caption("Cricket betting analytics")
        if APP_ENV == "development":
            st.caption("🔧 Development mode")


_sidebar_brand()

pg = st.navigation(
    {
        "": [st.Page(status_page, title="Status", icon="🏠", url_path="status")],
        "Live": [
            st.Page(todays_matches.render, title="Today's Matches", icon="📅", url_path="todays-matches", default=True),
            st.Page(match_hub.render, title="Match Hub", icon="🧭", url_path="match-hub"),
        ],
        "Markets": [
            st.Page(value_bets.render, title="Value Bets", icon="💰", url_path="value-bets"),
            st.Page(player_props.render, title="Player Props", icon="🎯", url_path="player-props"),
        ],
        "Teams & Tournament": [
            st.Page(team_deep_dive.render, title="Team Deep Dive", icon="📊", url_path="team-deep-dive"),
            st.Page(fixtures_table.render, title="Fixtures & Table", icon="📅", url_path="fixtures-table"),
        ],
        "Research": [
            st.Page(statistics.render, title="Statistics", icon="📋", url_path="statistics"),
            st.Page(rivalry_analyzer.render, title="Rivalry Analyzer", icon="⚔️", url_path="rivalry-analyzer"),
        ],
        "Model": [st.Page(model_performance.render, title="Performance", icon="📈", url_path="performance")],
    }
)
pg.run()
