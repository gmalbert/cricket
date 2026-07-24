"""Cache-only historical batter versus bowler research view."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.cache import load_cache_data_only


def _wagon_wheel(locations: list[dict]) -> go.Figure:
    """Render provider-supplied normalized locations; never invent coordinates."""
    fig = go.Figure()
    fig.add_shape(type="circle", x0=-1, y0=-1, x1=1, y1=1, line={"color": "#94a3b8"})
    colors = {0: "#94a3b8", 1: "#60a5fa", 2: "#60a5fa", 3: "#60a5fa", 4: "#22c55e", 6: "#f59e0b"}
    for shot in locations:
        runs = int(shot.get("runs_off_bat", 0))
        fig.add_trace(go.Scatter(
            x=[0, shot["x"]], y=[0, shot["y"]], mode="lines+markers",
            line={"color": colors.get(runs, "#94a3b8"), "width": 2}, marker={"size": 4},
            hovertemplate=f"{runs} runs<extra></extra>", showlegend=False,
        ))
    fig.update_xaxes(visible=False, range=[-1.1, 1.1])
    fig.update_yaxes(visible=False, range=[-1.1, 1.1], scaleanchor="x", scaleratio=1)
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10))
    return fig


def render() -> None:
    st.title("⚔️ Batter vs Bowler Rivalries")
    st.caption("Historical IPL ball-by-ball matchups. The matchup score is descriptive, not a win probability.")
    payload = load_cache_data_only("rivalries") or {}
    rows = payload.get("rivalries", [])
    if not rows:
        reason = payload.get("error", "Run the pipeline to build the historical rivalry cache.")
        st.info(f"Rivalry data is not available yet. {reason}")
        return

    df = pd.DataFrame(rows)
    col1, col2 = st.columns(2)
    with col1:
        batter = st.selectbox("Batter", sorted(df["batter"].dropna().unique()))
    with col2:
        bowlers = sorted(df.loc[df["batter"] == batter, "bowler"].dropna().unique())
        bowler = st.selectbox("Bowler", bowlers)
    row = df[(df["batter"] == batter) & (df["bowler"] == bowler)].iloc[0]

    if row["sample_tier"] == "low":
        st.warning("Low sample: use this as context only, not as an actionable advantage.")

    a, b, c, d = st.columns(4)
    a.metric("Runs / legal balls", f"{row['runs_off_bat']} / {row['legal_balls']}")
    b.metric("Strike rate", f"{row['strike_rate'] or 0:.1f}")
    c.metric("Bowler-credited dismissals", int(row["dismissals"]))
    d.metric("Historical read", row["score_label"])

    st.subheader("By innings phase")
    phases = pd.DataFrame(row["phase_splits"]).T.reset_index(names="Phase")
    phases["Strike rate"] = (
        100 * phases["runs_off_bat"] / phases["legal_balls"].replace(0, float("nan"))
    ).round(1)
    st.dataframe(phases[["Phase", "legal_balls", "runs_off_bat", "dismissals", "Strike rate"]], hide_index=True, width="stretch")
    figure = go.Figure(go.Bar(x=phases["Phase"], y=phases["Strike rate"], marker_color="#3498db"))
    figure.update_layout(height=260, yaxis_title="Strike rate", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(figure, width="stretch")

    st.subheader("Recent encounters")
    st.dataframe(pd.DataFrame(row["recent_encounters"]), hide_index=True, width="stretch")

    st.subheader("Shot map")
    locations_payload = load_cache_data_only("shot_locations") or {}
    locations = [
        location for location in locations_payload.get("locations", [])
        if location.get("batter") == batter and location.get("bowler") == bowler
    ]
    if locations:
        st.plotly_chart(_wagon_wheel(locations), width="stretch")
        st.caption(f"Shot locations supplied by {locations[0].get('source', 'an approved provider')}.")
    else:
        st.info("Shot locations are not enabled because no licensed location provider is configured.")
