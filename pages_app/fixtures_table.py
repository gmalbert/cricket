import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from utils.data import get_ipl_schedule, get_points_table

def render():
    st.title("📅 Fixtures & Tournament Table")

    tab1, tab2, tab3 = st.tabs(["Points Table", "Full Schedule", "Playoff Probabilities"])

    with tab1:
        st.subheader("IPL 2026 Points Table")
        table = get_points_table()
        df = pd.DataFrame(table)
        display_cols = ["Pos", "Team", "P", "W", "L", "NRR", "Pts"]
        display_df = df[display_cols].copy()

        def highlight_playoff(row):
            if row["Pos"] <= 4:
                return ["background-color: #d4edda"] * len(row)
            return [""] * len(row)

        styled = display_df.style.apply(highlight_playoff, axis=1)
        st.dataframe(styled, hide_index=True, use_container_width=True)
        st.caption("🟢 Green = Playoff qualification zone (Top 4)")

    with tab2:
        st.subheader("Full IPL 2026 Schedule")
        schedule = get_ipl_schedule()
        df = pd.DataFrame(schedule)

        filter_team = st.selectbox("Filter by Team", ["All Teams"] + sorted(set(df["team1"].tolist() + df["team2"].tolist())))
        show_upcoming = st.checkbox("Show only upcoming matches", value=False)

        filtered = df.copy()
        if filter_team != "All Teams":
            filtered = filtered[(filtered["team1"] == filter_team) | (filtered["team2"] == filter_team)]
        if show_upcoming:
            filtered = filtered[~filtered["played"]]

        def format_row(row):
            result = ""
            if row["played"] and row["winner"]:
                result = f"✅ {row['winner']}"
            else:
                result = f"🏏 {row['team1_win_prob']*100:.0f}% / {row['team2_win_prob']*100:.0f}%"
            return result

        filtered = filtered.copy()
        filtered["Prediction / Result"] = filtered.apply(format_row, axis=1)
        display = filtered[["match", "date", "team1", "team2", "venue", "Prediction / Result"]].copy()
        display.columns = ["#", "Date", "Team 1", "Team 2", "Venue", "Prediction / Result"]

        st.dataframe(display, hide_index=True, use_container_width=True)

    with tab3:
        st.subheader("Playoff Probability (Monte Carlo Simulation)")
        table = get_points_table()
        df = pd.DataFrame(table)
        df = df.sort_values("Playoff Prob", ascending=False)

        fig = go.Figure(go.Bar(
            x=df["Team"],
            y=df["Playoff Prob"] * 100,
            marker_color=[
                "#2ecc71" if p > 0.6 else ("#f39c12" if p > 0.35 else "#e74c3c")
                for p in df["Playoff Prob"]
            ],
            text=[f"{p*100:.0f}%" for p in df["Playoff Prob"]],
            textposition="auto",
        ))
        fig.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50% threshold")
        fig.update_layout(
            yaxis_title="Playoff Probability (%)",
            xaxis_tickangle=-30,
            height=400,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Methodology:** 10,000 Monte Carlo simulations using current form, remaining schedule, and NRR tiebreakers.")
        prob_df = df[["Team", "Pts", "NRR", "Playoff Prob"]].copy()
        prob_df["Playoff Prob"] = prob_df["Playoff Prob"].apply(lambda x: f"{x*100:.0f}%")
        st.dataframe(prob_df, hide_index=True, use_container_width=True)
