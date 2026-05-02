import streamlit as st
import plotly.graph_objects as go
from utils.data import get_todays_matches, IPL_VENUES

def render():
    st.title("🏏 Today's Matches")
    st.caption(f"IPL 2026 — Live Predictions & Odds Comparison")

    matches = get_todays_matches()

    if not matches:
        st.info("No matches scheduled today.")
        return

    for m in matches:
        edge_team1 = m["edge_team1"]
        edge_team2 = m["edge_team2"]
        best_edge = max(edge_team1, edge_team2)
        is_elite = best_edge > 0.10
        is_strong = best_edge > 0.05

        badge = ""
        if is_elite:
            badge = " 🏆 ELITE PICK"
        elif is_strong:
            badge = " ⭐ STRONG"

        with st.expander(f"{m['team1']} vs {m['team2']}  |  {m['venue']}  |  {m['time']}{badge}", expanded=True):
            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                st.subheader("Win Probabilities")
                fig = go.Figure(go.Bar(
                    x=[m["team1"], m["team2"]],
                    y=[m["team1_win_prob"] * 100, m["team2_win_prob"] * 100],
                    marker_color=["#2ecc71" if edge_team1 > 0.05 else "#3498db",
                                  "#2ecc71" if edge_team2 > 0.05 else "#e74c3c"],
                    text=[f"{m['team1_win_prob']*100:.1f}%", f"{m['team2_win_prob']*100:.1f}%"],
                    textposition="auto",
                ))
                fig.update_layout(
                    yaxis_title="Win Probability (%)",
                    height=250,
                    margin=dict(l=10, r=10, t=10, b=10),
                    showlegend=False,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, width='stretch')

            with col2:
                st.subheader("Model vs DraftKings")
                data = {
                    "Team": [m["team1"], m["team2"]],
                    "Model Prob": [f"{m['team1_win_prob']*100:.1f}%", f"{m['team2_win_prob']*100:.1f}%"],
                    "DK Implied": [f"{m['dk_implied_prob_team1']*100:.1f}%", f"{m['dk_implied_prob_team2']*100:.1f}%"],
                    "Edge": [f"{edge_team1*100:+.1f}%", f"{edge_team2*100:+.1f}%"],
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
                st.dataframe(styled, hide_index=True, width='stretch')

                total_diff = m["predicted_total"] - m["dk_total_line"]
                direction = "OVER" if total_diff > 0 else "UNDER"
                color = "green" if abs(total_diff) > 10 else "gray"
                st.markdown(f"**Total Runs:** Model {m['predicted_total']} vs DK {m['dk_total_line']} "
                            f"→ :{color}[**{direction} by {abs(total_diff)}**]")

            with col3:
                st.subheader("Weather")
                temp = m["temperature"]
                humidity = m["humidity"]
                dew = m["dew_flag"]
                st.metric("Temperature", f"{temp}°C")
                st.metric("Humidity", f"{humidity}%")
                if dew:
                    st.error("🌫️ DEW FACTOR")
                else:
                    st.success("No Dew Expected")

                st.divider()
                st.metric("Venue Avg Score", m["venue_avg_first_innings"] or "N/A")
                chase_rate = m.get("venue_chase_win_rate")
                chase_pct = int(chase_rate * 100) if chase_rate is not None else None
                st.metric("Chase Win Rate", f"{chase_pct}%" if chase_pct is not None else "N/A")
