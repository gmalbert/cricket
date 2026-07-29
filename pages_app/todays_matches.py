import plotly.graph_objects as go
import streamlit as st
from utils.browser_time import browser_time
try:
    from utils.browser_time import format_eastern_timestamp
except ImportError:  # Compatibility with deployments using an older utility module.
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

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
from utils.cache import APP_ENV, get_cache_metadata, is_mock_data, load_cache
from utils.data import get_competition_options, get_todays_matches

st.markdown(
    """
    <style>
    .wo-weather-grid { display:grid; grid-template-columns:1fr 1fr; gap:.55rem; margin:.4rem 0 .7rem; }
    .wo-weather-item { border:1px solid #e5e7eb; border-radius:8px; padding:.55rem .65rem; }
    .wo-weather-label { color:#64748b; font-size:.74rem; margin-bottom:.15rem; }
    .wo-weather-value { color:#1f2937; font-size:1.15rem; font-weight:650; }
    .wo-weather-note { border-radius:8px; padding:.55rem .7rem; font-size:.84rem; }
    .wo-weather-note.good { background:#ecfdf3; color:#15803d; }
    .wo-weather-note.warn { background:#fff7ed; color:#c2410c; }
    .wo-venue-row { display:grid; grid-template-columns:1fr 1fr; gap:.55rem; margin-top:.55rem; }
    .wo-venue-item { background:#f8fafc; border-radius:8px; padding:.5rem .65rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def render():
    st.title("🏏 Today's Matches")
    st.caption("Competition-aware h2h predictions & DraftKings comparison")

    # Check data status
    metadata = get_cache_metadata("todays_matches")
    is_mock = is_mock_data("todays_matches")

    if is_mock and APP_ENV == "development":
        st.warning(
            "⚠️ **SIMULATED DATA** - Development mode is showing mock predictions. Set APP_ENV=production to hide simulated data."
        )
    elif metadata:
        st.info(f"📊 Last updated: {format_eastern_timestamp(metadata.get('generated_at'))}")

    matches = get_todays_matches()

    # Handle None or empty matches
    if matches is None:
        st.info("📭 No match data available. The pipeline has not run yet or no cache exists.")
        if APP_ENV == "production":
            st.warning("Production mode: Mock data is disabled. Run the pipeline to generate predictions.")
        return

    match_hubs_data = load_cache("match_hubs")
    if isinstance(match_hubs_data, dict) and "data" in match_hubs_data:
        match_hubs = match_hubs_data.get("data", {}).get("matches", {})
    else:
        match_hubs = (match_hubs_data or {}).get("matches", {})

    competition_names = ["All competitions"] + [c["name"] for c in get_competition_options()]
    selected_competition = st.selectbox("Competition", competition_names)
    if selected_competition != "All competitions":
        matches = [m for m in matches if m.get("competition_name") == selected_competition]

    if not matches:
        st.info(f"📅 No matches scheduled today for {selected_competition}.")
        st.markdown("### Why no matches?")
        st.markdown("""
        - No fixtures scheduled for today in this competition
        - No DraftKings market available (we only show matches with betting markets)
        - Historical data for this competition is insufficient for predictions
        """)
        return

    for match_idx, m in enumerate(matches):
        edge_team1 = m.get("edge_team1") or 0
        edge_team2 = m.get("edge_team2") or 0
        best_edge = max(edge_team1, edge_team2)
        is_elite = best_edge > 0.10
        is_strong = best_edge > 0.05

        badge = ""
        if is_elite:
            badge = " 🏆 ELITE PICK"
        elif is_strong:
            badge = " ⭐ STRONG"

        label = m.get("competition_name", m.get("competition", "Cricket"))
        with st.expander(f"[{label}] {m['team1']} vs {m['team2']}{badge}", expanded=match_idx == 0):
            # Show verified badge if this is production data
            if metadata and not is_mock:
                st.caption(f"✅ Verified prediction | Model: {m.get('model_version', 'Unknown')}")
            st.markdown(browser_time(m.get("time"), "Scheduled"), unsafe_allow_html=True)

            col1, col2 = st.columns([1.7, 1], gap="large")

            with col1:
                st.subheader("Win Probabilities")
                fig = go.Figure(
                    go.Bar(
                        x=[m["team1"], m["team2"]],
                        y=[m["team1_win_prob"] * 100, m["team2_win_prob"] * 100],
                        marker_color=[
                            "#2ecc71" if edge_team1 > 0.05 else "#3498db",
                            "#2ecc71" if edge_team2 > 0.05 else "#e74c3c",
                        ],
                        text=[f"{m['team1_win_prob'] * 100:.1f}%", f"{m['team2_win_prob'] * 100:.1f}%"],
                        textposition="auto",
                    )
                )
                fig.update_layout(
                    yaxis_title="Win Probability (%)",
                    height=215,
                    margin={"l": 10, "r": 10, "t": 10, "b": 10},
                    showlegend=False,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(
                    fig,
                    width="stretch",
                    key=f"win-probability-{m.get('match_id') or match_idx}",
                )

            with col1:
                with st.container(border=True):
                    st.subheader("Model vs DraftKings")
                    data = {
                        "Team": [m["team1"], m["team2"]],
                        "Model %": [f"{m['team1_win_prob'] * 100:.1f}%", f"{m['team2_win_prob'] * 100:.1f}%"],
                        "DK %": [
                            f"{(m.get('dk_implied_prob_team1') or 0) * 100:.1f}%",
                            f"{(m.get('dk_implied_prob_team2') or 0) * 100:.1f}%",
                        ],
                        "Edge": [f"{edge_team1 * 100:+.1f}%", f"{edge_team2 * 100:+.1f}%"],
                    }
                    import pandas as pd

                    df = pd.DataFrame(data)

                    def color_edge(val):
                        v = float(val.replace("%", "").replace("+", ""))
                        if v > 5:
                            return "background-color: #d4edda; color: #155724;"
                        elif v < -5:
                            return "background-color: #f8d7da; color: #721c24;"
                        return ""

                    styled = df.style.map(color_edge, subset=["Edge"])
                    st.dataframe(styled, hide_index=True, width="stretch")

                    if not m.get("draftkings_available"):
                        st.info("No DraftKings h2h market found for this fixture.")

            with col2:
                st.subheader("Weather")
                temp = m.get("temperature")
                humidity = m.get("humidity")
                dew = m.get("dew_flag")
                weather_items = []
                if temp is not None:
                    weather_items.append(("Temperature", f"{temp}°C"))
                if humidity is not None:
                    weather_items.append(("Humidity", f"{humidity}%"))
                if weather_items:
                    weather_html = "".join(
                        f'<div class="wo-weather-item"><div class="wo-weather-label">{label}</div>'
                        f'<div class="wo-weather-value">{value}</div></div>'
                        for label, value in weather_items
                    )
                    st.markdown(f'<div class="wo-weather-grid">{weather_html}</div>', unsafe_allow_html=True)
                if dew:
                    st.markdown('<div class="wo-weather-note warn">🌫️ Dew factor expected</div>', unsafe_allow_html=True)
                elif temp is not None and humidity is not None:
                    st.markdown('<div class="wo-weather-note good">No dew expected</div>', unsafe_allow_html=True)

                venue_avg = m.get("venue_avg_first_innings")
                chase_rate = m.get("venue_chase_win_rate")
                chase_pct = int(chase_rate * 100) if chase_rate is not None else None
                venue_items = []
                if venue_avg:
                    venue_items.append(("Venue avg", venue_avg))
                if chase_pct is not None:
                    venue_items.append(("Chase win", f"{chase_pct}%"))
                if venue_items:
                    venue_html = "".join(
                        f'<div class="wo-venue-item"><div class="wo-weather-label">{label}</div>'
                        f"<strong>{value}</strong></div>"
                        for label, value in venue_items
                    )
                    st.markdown(f'<div class="wo-venue-row">{venue_html}</div>', unsafe_allow_html=True)

            hub = match_hubs.get(m.get("match_id", ""), {})
            key_rivalries = hub.get("key_rivalries", [])[:3]
            if key_rivalries:
                import pandas as pd

                st.subheader("Key historical battles")
                battle_df = pd.DataFrame(key_rivalries)
                display_cols = [
                    key for key in ("batter", "bowler", "strike_rate", "dismissals", "sample_tier") if key in battle_df
                ]
                st.dataframe(battle_df[display_cols], hide_index=True, width="stretch")
