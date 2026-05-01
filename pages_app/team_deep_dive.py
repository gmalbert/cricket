import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from utils.data import IPL_TEAMS_2026, get_team_form, TEAM_PLAYERS
import random

def render():
    st.title("📊 Team Deep Dive")

    team = st.selectbox("Select Team", IPL_TEAMS_2026)
    form = get_team_form(team)
    df = pd.DataFrame(form)

    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    wins = sum(1 for r in form if r["result"] == "W")
    avg_score = int(sum(r["score"] for r in form) / len(form))
    avg_pp = int(sum(r["powerplay_runs"] for r in form) / len(form))
    avg_death = round(sum(r["death_economy"] for r in form) / len(form), 2)

    col1.metric("Last 10 Win Rate", f"{wins}/10")
    col2.metric("Avg Score", avg_score)
    col3.metric("Avg Powerplay Runs", avg_pp)
    col4.metric("Death Overs Economy", avg_death)

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(["Form Table", "Phase Breakdown", "Venue Record", "Head-to-Head"])

    with tab1:
        st.subheader("Last 10 T20 Results")
        display_df = df[["date", "opponent", "result", "score", "opp_score", "powerplay_runs", "death_economy"]].copy()
        display_df.columns = ["Date", "Opponent", "Result", "Score", "Opp Score", "Powerplay Runs", "Death Economy"]

        def highlight_result(val):
            if val == "W":
                return "background-color: #d4edda; color: #155724; font-weight: bold"
            elif val == "L":
                return "background-color: #f8d7da; color: #721c24; font-weight: bold"
            return ""

        styled = display_df.style.map(highlight_result, subset=["Result"])
        st.dataframe(styled, hide_index=True, use_container_width=True)

    with tab2:
        st.subheader("Phase-by-Phase Scoring Breakdown")
        random.seed(hash(team) % 1111)
        phases = ["Powerplay (1-6)", "Middle (7-15)", "Death (16-20)"]
        runs = [avg_pp, random.randint(68, 88), random.randint(52, 72)]
        wickets = [random.randint(0, 2), random.randint(1, 3), random.randint(1, 4)]

        fig = go.Figure()
        fig.add_trace(go.Bar(name="Avg Runs", x=phases, y=runs, marker_color="#3498db"))
        fig.add_trace(go.Bar(name="Avg Wickets", x=phases, y=wickets, marker_color="#e74c3c"))
        fig.update_layout(
            barmode="group",
            height=350,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Batting Phase Averages**")
            phase_df = pd.DataFrame({"Phase": phases, "Avg Runs": runs, "Avg Wickets": wickets})
            st.dataframe(phase_df, hide_index=True, use_container_width=True)
        with col2:
            st.markdown("**Economy Rate by Phase (Bowling)**")
            bowling_econ = [round(random.uniform(6.8, 8.2), 2) for _ in phases]
            bowl_df = pd.DataFrame({"Phase": phases, "Economy": bowling_econ})
            st.dataframe(bowl_df, hide_index=True, use_container_width=True)

    with tab3:
        st.subheader("Venue Record")
        from utils.data import IPL_VENUES
        venue_records = []
        random.seed(hash(team + "venue") % 3333)
        for venue in list(IPL_VENUES.keys())[:6]:
            played = random.randint(2, 8)
            won = random.randint(0, played)
            avg = random.randint(148, 190)
            venue_records.append({
                "Venue": venue,
                "Played": played,
                "Won": won,
                "Lost": played - won,
                "Win%": f"{int(won/played*100)}%",
                "Avg Score": avg,
            })
        vdf = pd.DataFrame(venue_records)
        st.dataframe(vdf, hide_index=True, use_container_width=True)

    with tab4:
        st.subheader("Head-to-Head vs All Teams (Last 10 T20s)")
        opponents = [t for t in IPL_TEAMS_2026 if t != team]
        selected_opp = st.selectbox("Select Opponent", opponents)
        random.seed(hash(team + selected_opp) % 4444)
        h2h = []
        for i in range(10):
            won = random.random() > 0.5
            score = random.randint(148, 205)
            opp_score = random.randint(120, score - 5) if won else random.randint(score + 5, score + 40)
            from datetime import datetime, timedelta
            match_date = (datetime.now() - timedelta(days=(10-i)*60)).strftime("%b %d, %Y")
            h2h.append({
                "Date": match_date,
                "Result": "W" if won else "L",
                f"{team} Score": score,
                f"{selected_opp} Score": opp_score,
                "Venue": random.choice(list(IPL_VENUES.keys())),
            })
        h2h_df = pd.DataFrame(h2h)
        wins_h2h = sum(1 for r in h2h if r["Result"] == "W")
        st.markdown(f"**{team}** leads **{selected_opp}**: {wins_h2h}–{10-wins_h2h}")

        def highlight_result(val):
            if val == "W":
                return "background-color: #d4edda; color: #155724; font-weight: bold"
            elif val == "L":
                return "background-color: #f8d7da; color: #721c24; font-weight: bold"
            return ""

        styled = h2h_df.style.map(highlight_result, subset=["Result"])
        st.dataframe(styled, hide_index=True, use_container_width=True)
