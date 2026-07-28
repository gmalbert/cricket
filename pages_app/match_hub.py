"""Cache-only fixture research view combining model and historical evidence."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.cache import load_cache_data_only


def _percent(value) -> str:
    return f"{100 * float(value):.1f}%" if value is not None else "N/A"


def render() -> None:
    st.title("🧭 Match Hub")
    st.caption("Model, market, conditions, props, and historical player matchups in one cached research view.")
    payload = load_cache_data_only("match_hubs") or {}
    hubs = payload.get("matches", {})
    if not hubs:
        st.info("No Match Hub is cached yet. Run the pipeline to generate one.")
        return

    labels = {
        match_id: f"{hub['match'].get('team1', 'TBD')} vs {hub['match'].get('team2', 'TBD')} — {hub['match'].get('venue', 'Venue TBD')}"
        for match_id, hub in hubs.items()
    }
    match_id = st.selectbox("Select match", list(labels), format_func=labels.get)
    hub = hubs[match_id]
    match, prediction, market = hub["match"], hub["prediction"], hub["market"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(match.get("team1", "Team 1"), _percent(prediction.get("team1_win_prob")))
    c2.metric(match.get("team2", "Team 2"), _percent(prediction.get("team2_win_prob")))
    c3.metric("Projected total", prediction.get("predicted_total") or "N/A")
    c4.metric("Market total", market.get("total_line") or "N/A")

    st.subheader("Conditions")
    venue, weather = hub.get("venue", {}), hub.get("weather", {})
    a, b, c, d = st.columns(4)
    a.metric("Venue average", venue.get("avg_first_innings") or "N/A")
    b.metric("Chasing win rate", _percent(venue.get("chase_win_rate")))
    c.metric("Temperature", f"{weather['temperature']}°C" if weather.get("temperature") is not None else "N/A")
    d.metric("Dew", "Expected" if weather.get("dew_flag") else "Not expected")

    st.subheader("Recent team form")
    form = hub.get("team_form", {})
    left, right = st.columns(2)
    for column, team_key, team_name in (
        (left, "team1", match.get("team1", "Team 1")),
        (right, "team2", match.get("team2", "Team 2")),
    ):
        with column:
            st.markdown(f"**{team_name}**")
            rows = pd.DataFrame(form.get(team_key, []))
            if rows.empty:
                st.caption("No recent form cached.")
            else:
                display = [key for key in ("date", "opponent", "result", "score", "opp_score") if key in rows]
                st.dataframe(rows[display], hide_index=True, width="stretch")

    st.subheader("Key historical battles")
    rivalries = pd.DataFrame(hub.get("key_rivalries", []))
    if rivalries.empty:
        st.info("No confirmed historical player pairings are available for this fixture.")
    else:
        columns = [
            key
            for key in ("batter", "bowler", "legal_balls", "runs_off_bat", "dismissals", "score_label", "sample_tier")
            if key in rivalries
        ]
        st.dataframe(rivalries[columns], hide_index=True, width="stretch")

    st.subheader("Top model-vs-market props")
    props = pd.DataFrame(hub.get("top_props", []))
    if props.empty:
        st.caption("No player props are cached for this fixture.")
    else:
        st.dataframe(props, hide_index=True, width="stretch")

    unavailable = [name for name, status in hub.get("data_status", {}).items() if status != "available"]
    if unavailable:
        st.caption("Unavailable cached inputs: " + ", ".join(unavailable) + ".")
