import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.data import get_todays_matches, get_value_bets, get_competition_status
from utils.cache import get_cache_metadata, is_mock_data, APP_ENV

def render():
    st.title("💰 Value Bets")
    st.caption("DraftKings-backed match-winner bets — sorted by model edge. Kelly Criterion sizing at 25% fractional.")

    # Check data status
    metadata = get_cache_metadata("value_bets")
    is_mock = is_mock_data("value_bets")
    
    if is_mock and APP_ENV == "development":
        st.warning("⚠️ **SIMULATED DATA** - Development mode is showing mock bets. Set APP_ENV=production to hide simulated data.")
    elif metadata:
        st.info(f"📊 Last updated: {metadata.get('generated_at', 'Unknown')}")

    matches = get_todays_matches()
    
    # Handle None matches
    if matches is None:
        st.info("📭 No match data available. The pipeline has not run yet.")
        if APP_ENV == "production":
            st.warning("Production mode: Mock data is disabled. Run the pipeline to generate value bets.")
        return
    
    bets = get_value_bets(matches)
    
    # Handle None bets
    if bets is None:
        st.info("📭 No bet data available.")
        if APP_ENV == "production":
            st.warning("Production mode: Mock data is disabled.")
        return
    
    status_report = get_competition_status().get("competitions", {})

    if status_report:
        status_df = pd.DataFrame([
            {
                "Competition": row.get("competition_name", slug),
                "Fixtures": row.get("fixtures_count", 0),
                "DraftKings": "✅ Available" if row.get("draftkings_available") else "❌ Unavailable",
                "Model": "✅ Ready" if row.get("model_ready") else "❌ Not ready",
                "Status": row.get("reason") or "ready",
            }
            for slug, row in status_report.items()
        ])
        with st.expander("Competition readiness", expanded=not bool(bets)):
            st.dataframe(status_df, hide_index=True, width="stretch")

    # Build a UUID → "Team1 vs Team2" lookup to fix cached bets that stored match_id
    mid_to_label = {m["match_id"]: f"{m['team1']} vs {m['team2']}" for m in matches if m.get("match_id")}
    for b in bets:
        if b.get("match") in mid_to_label:
            b["match"] = mid_to_label[b["match"]]

    bets.sort(key=lambda x: -x["edge"])

    if not bets:
        st.info("🎯 No qualifying DraftKings h2h bets identified today.")
        st.markdown("### Why no bets?")
        st.markdown("""
        Bets are only shown when:
        - ✅ Model edge > 5%
        - ✅ DraftKings market is available
        - ✅ Historical data is sufficient for reliable predictions
        - ✅ Model validation passes
        
        Check the competition readiness table above to see which gates are blocking each competition.
        """)
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
        ["Match Winner"],
        default=["Match Winner"]
    )

    filtered = [b for b in bets if b["type"] in filter_type]

    if not filtered:
        st.info("No bets match the selected filters.")
    else:
        type_icon = {"Match Winner": "🏏"}
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

        color_map = {"Match Winner": "#3498db"}
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

