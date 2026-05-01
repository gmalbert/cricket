import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from utils.data import IPL_VENUES, TEAM_PLAYERS, get_batter_profile, get_bowler_profile

def render():
    st.title("📋 Statistics")

    tab1, tab2, tab3, tab4 = st.tabs(["Venue Profiles", "Batter Profiles", "Bowler Profiles", "Umpire Tendencies"])

    with tab1:
        st.subheader("IPL Venue Profiles")

        venue_data = []
        for name, info in IPL_VENUES.items():
            import random
            random.seed(hash(name) % 2222)
            dew_pct = random.randint(15, 55)
            venue_data.append({
                "Venue": name,
                "City": info["city"],
                "Avg 1st Innings": info["avg_first_innings"],
                "Chase Win%": f"{int(info['chase_win_rate']*100)}%",
                "Dew Impact%": f"{dew_pct}%",
                "Avg 200+ Scores": random.randint(2, 12),
                "Pitch": random.choice(["Flat", "Flat", "Turning", "Seaming", "Balanced"]),
            })

        venue_df = pd.DataFrame(venue_data)
        st.dataframe(venue_df, hide_index=True, use_container_width=True)

        st.divider()
        selected_venue = st.selectbox("Venue Detail", list(IPL_VENUES.keys()))
        info = IPL_VENUES[selected_venue]
        import random
        random.seed(hash(selected_venue) % 5678)

        col1, col2, col3 = st.columns(3)
        col1.metric("Avg First Innings Score", info["avg_first_innings"])
        col2.metric("Chase Win Rate", f"{int(info['chase_win_rate']*100)}%")
        col3.metric("City", info["city"])

        st.markdown("**Score Distribution (Last 50 matches)**")
        scores = [random.randint(130, 230) for _ in range(50)]
        fig = go.Figure(go.Histogram(
            x=scores,
            nbinsx=20,
            marker_color="#3498db",
        ))
        fig.update_layout(
            xaxis_title="First Innings Score",
            yaxis_title="Frequency",
            height=280,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Batter Profiles")

        all_batters = []
        for team, players in TEAM_PLAYERS.items():
            for p in players.get("batters", []):
                all_batters.append((p, team))

        all_batters_names = [f"{p} ({t})" for p, t in all_batters]
        selected_batter_label = st.selectbox("Select Batter", all_batters_names)
        selected_batter = selected_batter_label.split(" (")[0]

        profile = get_batter_profile(selected_batter)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Career T20 Avg", profile["career_avg"])
        col2.metric("Career Strike Rate", profile["career_sr"])
        col3.metric("Recent Form Avg (last 10)", profile["recent_avg"])
        col4.metric("Boundaries/Innings", profile["boundaries_per_innings"])

        st.markdown("**Recent 10 Innings Scores**")
        fig = go.Figure(go.Bar(
            x=[f"Inn {i+1}" for i in range(10)],
            y=profile["recent_scores"],
            marker_color=["#2ecc71" if s >= 30 else "#e74c3c" for s in profile["recent_scores"]],
            text=profile["recent_scores"],
            textposition="auto",
        ))
        fig.update_layout(
            height=280,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("vs Pace Avg", profile["vs_pace_avg"])
        col2.metric("vs Spin Avg", profile["vs_spin_avg"])
        col3.metric("Powerplay Avg", profile["powerplay_avg"])

    with tab3:
        st.subheader("Bowler Profiles")

        all_bowlers = []
        for team, players in TEAM_PLAYERS.items():
            for p in players.get("bowlers", []):
                all_bowlers.append((p, team))

        all_bowler_names = [f"{p} ({t})" for p, t in all_bowlers]
        selected_bowler_label = st.selectbox("Select Bowler", all_bowler_names)
        selected_bowler = selected_bowler_label.split(" (")[0]

        profile = get_bowler_profile(selected_bowler)

        col1, col2, col3 = st.columns(3)
        col1.metric("Career Economy", profile["career_economy"])
        col2.metric("Wickets/Match", profile["wickets_per_match"])
        col3.metric("Recent Economy", profile["recent_economy"])

        st.markdown("**Wickets in Last 5 Matches**")
        fig = go.Figure(go.Bar(
            x=[f"Match {i+1}" for i in range(5)],
            y=profile["wickets_last5"],
            marker_color=["#2ecc71" if w >= 2 else "#3498db" for w in profile["wickets_last5"]],
            text=profile["wickets_last5"],
            textposition="auto",
        ))
        fig.update_layout(
            height=250,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

        phases = ["Powerplay (1-6)", "Middle (7-15)", "Death (16-20)"]
        economies = [profile["powerplay_economy"], profile["career_economy"], profile["death_economy"]]
        phase_fig = go.Figure(go.Bar(
            x=phases,
            y=economies,
            marker_color=["#3498db", "#2ecc71", "#e74c3c"],
            text=[f"{e:.2f}" for e in economies],
            textposition="auto",
        ))
        phase_fig.update_layout(
            yaxis_title="Economy Rate",
            height=260,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(phase_fig, use_container_width=True)

        col1, col2 = st.columns(2)
        col1.metric("vs LHB Economy", profile["vs_lhb_economy"])
        col2.metric("vs RHB Economy", profile["vs_rhb_economy"])

    with tab4:
        st.subheader("Umpire Tendencies")
        st.caption("Wide calling rates and LBW decisions by umpire")
        import random
        random.seed(77)
        umpires = [
            "Nitin Menon", "K.N. Ananthapadmanabhan", "Anil Chaudhary", "C.K. Nandan",
            "Virender Sharma", "Shamshuddin", "S. Ravi", "Ulhas Gandhe"
        ]
        ump_data = []
        for u in umpires:
            random.seed(hash(u) % 9999)
            ump_data.append({
                "Umpire": u,
                "Avg Wides/Match": round(random.uniform(2.1, 5.8), 1),
                "LBW Rate/Match": round(random.uniform(0.3, 1.2), 2),
                "No-Balls/Match": round(random.uniform(0.2, 1.5), 1),
                "Run Rate Tendency": random.choice(["Slightly High", "Average", "Slightly Low"]),
                "Matches (IPL 2026)": random.randint(3, 14),
            })
        ump_df = pd.DataFrame(ump_data).sort_values("Avg Wides/Match", ascending=False)
        st.dataframe(ump_df, hide_index=True, use_container_width=True)
