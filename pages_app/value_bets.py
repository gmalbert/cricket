import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.data import get_todays_matches, get_value_bets

def render():
    st.title("💰 Value Bets")
    st.caption("Aggregated best-bet table — sorted by model edge. Kelly Criterion sizing at 25% fractional.")

    matches = get_todays_matches()
    bets = get_value_bets(matches)

    # Build a UUID → "Team1 vs Team2" lookup to fix cached bets that stored match_id
    mid_to_label = {m["match_id"]: f"{m['team1']} vs {m['team2']}" for m in matches if m.get("match_id")}
    for b in bets:
        if b.get("match") in mid_to_label:
            b["match"] = mid_to_label[b["match"]]

    bets.sort(key=lambda x: -x["edge"])

    if not bets:
        st.info("No value bets identified today. Check back after odds update.")
        return

    col1, col2, col3 = st.columns(3)
    elite_count = sum(1 for b in bets if b["tier"] == "Elite Pick")
    strong_count = sum(1 for b in bets if b["tier"] == "Strong")
    avg_edge = round(sum(b["edge"] for b in bets) / len(bets) * 100, 1)

    col1.metric("Elite Picks", elite_count)
    col2.metric("Strong Picks", strong_count)
    col3.metric("Avg Edge", f"{avg_edge}%")

    st.divider()

    filter_type = st.multiselect(
        "Filter by Bet Type",
        ["Match Winner", "Total Runs", "Player Prop"],
        default=["Match Winner", "Total Runs", "Player Prop"]
    )

    filtered = [b for b in bets if b["type"] in filter_type]

    if not filtered:
        st.info("No bets match the selected filters.")
    else:
        type_icon = {"Match Winner": "🏏", "Total Runs": "📊", "Player Prop": "🎯"}
        tier_badge = {"Elite Pick": "🏆 ELITE", "Strong": "⭐ STRONG"}

        df = pd.DataFrame([
            {
                "Type": type_icon.get(b["type"], "") + " " + b["type"],
                "Bet": b["bet"],
                "Match": b["match"],
                "Tier": tier_badge.get(b["tier"], b["tier"]),
                "Model %": f"{b['model_prob']*100:.0f}%",
                "DK Implied": f"{b['implied_prob']*100:.0f}%",
                "Edge": f"{b['edge']*100:+.1f}%",
                "Kelly": b["kelly_stake"],
                "DK Odds": b["dk_odds"],
            }
            for b in filtered
        ])

        st.dataframe(
            df,
            width='stretch',
            hide_index=True,
            column_config={
                "Type": st.column_config.TextColumn(width="small"),
                "Bet": st.column_config.TextColumn(width="large"),
                "Match": st.column_config.TextColumn(width="medium"),
                "Tier": st.column_config.TextColumn(width="small"),
                "Model %": st.column_config.TextColumn(width="small"),
                "DK Implied": st.column_config.TextColumn(width="small"),
                "Edge": st.column_config.TextColumn(width="small"),
                "Kelly": st.column_config.TextColumn(width="small"),
                "DK Odds": st.column_config.TextColumn(width="small"),
            },
        )

    st.subheader("Edge Distribution")
    if filtered:
        edges = [b["edge"] * 100 for b in filtered]
        types = [b["type"] for b in filtered]
        labels = [b["bet"][:30] for b in filtered]

        color_map = {"Match Winner": "#3498db", "Total Runs": "#2ecc71", "Player Prop": "#9b59b6"}
        colors = [color_map.get(t, "#95a5a6") for t in types]

        fig = go.Figure(go.Bar(
            x=labels,
            y=edges,
            marker_color=colors,
            text=[f"{e:.1f}%" for e in edges],
            textposition="auto",
        ))
        fig.update_layout(
            yaxis_title="Edge (%)",
            xaxis_tickangle=-45,
            height=350,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, width='stretch')

