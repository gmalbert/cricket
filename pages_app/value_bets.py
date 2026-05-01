import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.data import get_todays_matches, get_value_bets, get_player_props

def render():
    st.title("💰 Value Bets")
    st.caption("Aggregated best-bet table — sorted by model edge. Kelly Criterion sizing at 25% fractional.")

    matches = get_todays_matches()
    bets = get_value_bets(matches)

    for m in matches:
        props = get_player_props(m)
        for p in props:
            if p["confidence"] == "High" and abs(p["edge"]) > 6:
                import random
                random.seed(hash(p["player"]) % 8888)
                dk_odds = "-115" if p["recommendation"] == "OVER" else "-110"
                kelly = round(abs(p["edge"]) / (p["dk_line"] if p["dk_line"] > 0 else 1) * 0.25 * 100, 1)
                edge_ratio = abs(p["edge"]) / (p["dk_line"] if p["dk_line"] > 0 else 1)
                bets.append({
                    "match": f"{m['team1']} vs {m['team2']}",
                    "bet": f"{p['player']} {p['recommendation']} {p['dk_line']} {p['market']}",
                    "type": "Player Prop",
                    "model_prob": round(0.5 + edge_ratio * 0.5, 2),
                    "implied_prob": 0.5,
                    "edge": round(edge_ratio * 0.5, 3),
                    "dk_odds": dk_odds,
                    "kelly_stake": f"{kelly}%",
                    "tier": "Elite Pick" if edge_ratio > 0.25 else "Strong",
                })

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

    for b in filtered:
        tier_badge = "🏆 ELITE PICK" if b["tier"] == "Elite Pick" else "⭐ STRONG"
        type_icon = {"Match Winner": "🏏", "Total Runs": "📊", "Player Prop": "🎯"}.get(b["type"], "")

        with st.container():
            c1, c2, c3, c4, c5, c6 = st.columns([2, 2, 1, 1, 1, 1])
            with c1:
                st.markdown(f"**{type_icon} {b['bet']}**")
                st.caption(b["match"])
            with c2:
                st.caption(b["type"])
                st.markdown(f"{tier_badge}")
            with c3:
                st.metric("Model", f"{b['model_prob']*100:.0f}%")
            with c4:
                st.metric("DK Implied", f"{b['implied_prob']*100:.0f}%")
            with c5:
                st.metric("Edge", f"{b['edge']*100:+.1f}%")
            with c6:
                st.metric("Kelly Stake", b["kelly_stake"])
                st.caption(f"DK: {b['dk_odds']}")
            st.divider()

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
        st.plotly_chart(fig, use_container_width=True)
