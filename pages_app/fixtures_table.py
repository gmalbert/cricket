import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.cache import cache_exists
from utils.data import get_ipl_schedule, get_playoff_probabilities, get_points_table

QUALIFY_GREEN = "#2ecc71"
DANGER_RED = "#e74c3c"
WARNING_ORANGE = "#f39c12"
NEUTRAL_BLUE = "#3498db"


def render():
    st.title("📅 Fixtures & Tournament Table")

    tab1, tab2, tab3 = st.tabs(["Points Table", "Full Schedule", "Playoff Probabilities"])

    # ------------------------------------------------------------------ #
    # TAB 1 — Points Table
    # ------------------------------------------------------------------ #
    with tab1:
        st.subheader("IPL 2026 Points Table")
        table = get_points_table()
        df = pd.DataFrame(table)
        display_cols = ["Pos", "Team", "P", "W", "L", "NRR", "Pts"]
        missing_cols = [col for col in display_cols if col not in df.columns]
        if df.empty:
            st.info("📭 No points-table data available. Run the data pipeline to generate the points table.")
        elif missing_cols:
            st.warning(f"The cached points table has an unexpected schema. Missing columns: {', '.join(missing_cols)}.")
        else:
            display_df = df[display_cols].copy()

            def highlight_playoff(row):
                if row["Pos"] <= 4:
                    return ["background-color: #d4edda"] * len(row)
                return [""] * len(row)

            styled = display_df.style.apply(highlight_playoff, axis=1)
            st.dataframe(styled, hide_index=True, width="stretch")
            st.caption("🟢 Green = Playoff qualification zone (Top 4)")

    # ------------------------------------------------------------------ #
    # TAB 2 — Full Schedule
    # ------------------------------------------------------------------ #
    with tab2:
        st.subheader("Full IPL 2026 Schedule")
        schedule = get_ipl_schedule()
        df = pd.DataFrame(schedule)

        schedule_cols = ["match", "date", "team1", "team2", "venue", "played"]
        missing_schedule_cols = [col for col in schedule_cols if col not in df.columns]
        if df.empty:
            st.info("📭 No schedule data available. Run the data pipeline to generate it.")
        elif missing_schedule_cols:
            st.warning(
                f"The cached schedule has an unexpected schema. Missing columns: {', '.join(missing_schedule_cols)}."
            )
        else:
            all_teams = sorted(set(df["team1"].tolist() + df["team2"].tolist()))
            filter_team = st.selectbox("Filter by Team", ["All Teams"] + all_teams)
            show_upcoming = st.checkbox("Show only upcoming matches", value=False)

            filtered = df.copy()
            if filter_team != "All Teams":
                filtered = filtered[(filtered["team1"] == filter_team) | (filtered["team2"] == filter_team)]
            if show_upcoming:
                filtered = filtered[~filtered["played"]]

            def format_row(row):
                if row["played"] and row.get("winner"):
                    return f"✅ {row['winner']}"
                p1 = row.get("team1_win_prob", 0.5)
                p2 = row.get("team2_win_prob", 0.5)
                return f"🏏 {p1 * 100:.0f}% / {p2 * 100:.0f}%"

            filtered = filtered.copy()
            filtered["Prediction / Result"] = filtered.apply(format_row, axis=1)
            display = filtered[["match", "date", "team1", "team2", "venue", "Prediction / Result"]].copy()
            display.columns = ["#", "Date", "Team 1", "Team 2", "Venue", "Prediction / Result"]
            st.dataframe(display, hide_index=True, width="stretch")

    # ------------------------------------------------------------------ #
    # TAB 3 — Monte Carlo Playoff Probabilities
    # ------------------------------------------------------------------ #
    with tab3:
        is_cached = cache_exists("playoff_probabilities")
        if not is_cached:
            st.info(
                "No cached simulation found — running a fresh simulation against "
                "simulated standings. Run the nightly pipeline to use real data.",
                icon="ℹ️",
            )

        with st.spinner("Running 10,000 Monte Carlo simulations..."):
            mc = get_playoff_probabilities()

        if not mc or not mc.get("team_results"):
            st.error("Simulation failed — no results available.")
            return

        team_results = mc["team_results"]
        match_importance = mc.get("match_importance", [])
        n_sims = mc.get("n_simulations", 10_000)
        remaining = mc.get("remaining_matches", 0)

        # --- Header metrics ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Simulations Run", f"{n_sims:,}")
        col2.metric("Remaining Matches", remaining)
        col3.metric("Teams Tracked", len(team_results))

        st.divider()

        inner_tab1, inner_tab2, inner_tab3, inner_tab4 = st.tabs(
            ["Qualification Odds", "Title Race", "Position Distribution", "Match Importance"]
        )

        # ---- Qualification Odds ----------------------------------------
        with inner_tab1:
            st.subheader("Playoff Qualification Probability")

            tr_df = pd.DataFrame(team_results)
            tr_df = tr_df.sort_values("qualify_prob", ascending=False)

            colors = [
                QUALIFY_GREEN if p >= 0.60 else WARNING_ORANGE if p >= 0.35 else DANGER_RED
                for p in tr_df["qualify_prob"]
            ]

            fig = go.Figure(
                go.Bar(
                    x=tr_df["team"],
                    y=tr_df["qualify_prob"] * 100,
                    marker_color=colors,
                    text=[f"{p * 100:.1f}%" for p in tr_df["qualify_prob"]],
                    textposition="auto",
                    hovertemplate=("<b>%{x}</b><br>Qualify: %{y:.1f}%<br><extra></extra>"),
                )
            )
            fig.add_hline(
                y=50,
                line_dash="dash",
                line_color="gray",
                annotation_text="50% line",
                annotation_position="right",
            )
            fig.update_layout(
                yaxis_title="Qualification Probability (%)",
                yaxis_range=[0, 105],
                xaxis_tickangle=-30,
                height=420,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, width="stretch")

            # Summary table
            summary = tr_df[
                [
                    "team",
                    "current_pts",
                    "games_remaining",
                    "qualify_prob",
                    "avg_finish",
                    "avg_final_pts",
                ]
            ].copy()
            summary.columns = [
                "Team",
                "Current Pts",
                "Games Left",
                "Qualify %",
                "Avg Finish",
                "Avg Final Pts",
            ]
            summary["Qualify %"] = summary["Qualify %"].apply(lambda x: f"{x * 100:.1f}%")
            summary["Avg Finish"] = summary["Avg Finish"].apply(lambda x: f"{x:.2f}")
            summary["Avg Final Pts"] = summary["Avg Final Pts"].apply(lambda x: f"{x:.1f}")

            def color_qualify(row):
                val = float(row["Qualify %"].replace("%", ""))
                if val >= 60:
                    return ["background-color: #d4edda"] * len(row)
                if val <= 15:
                    return ["background-color: #f8d7da"] * len(row)
                return [""] * len(row)

            st.dataframe(
                summary.style.apply(color_qualify, axis=1),
                hide_index=True,
                width="stretch",
            )

            # Magic numbers
            st.subheader("Qualification Status")
            for row in team_results:
                qp = row["qualify_prob"]
                gr = row["games_remaining"]
                if qp >= 0.99:
                    status = "🏆 **Qualified** (effectively guaranteed)"
                elif qp >= 0.75:
                    status = f"🟢 Strong position — {qp * 100:.0f}% chance"
                elif qp >= 0.40:
                    status = f"🟡 In contention — {qp * 100:.0f}% chance, {gr} games left"
                elif qp > 0.05:
                    status = f"🔴 Long shot — {qp * 100:.0f}% chance"
                else:
                    status = "⬛ Effectively eliminated"
                st.markdown(f"**{row['team']}** — {status}")

        # ---- Title Race ------------------------------------------------
        with inner_tab2:
            st.subheader("Tournament Title Probability (Finishing #1 in League Stage)")

            tr_df2 = pd.DataFrame(team_results).sort_values("title_prob", ascending=False)
            tr_df2 = tr_df2[tr_df2["title_prob"] > 0.001]

            fig2 = go.Figure(
                go.Bar(
                    x=tr_df2["team"],
                    y=tr_df2["title_prob"] * 100,
                    marker_color=NEUTRAL_BLUE,
                    text=[f"{p * 100:.1f}%" for p in tr_df2["title_prob"]],
                    textposition="auto",
                )
            )
            fig2.update_layout(
                yaxis_title="Title Probability (%)",
                xaxis_tickangle=-30,
                height=380,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig2, width="stretch")

            # Qualification + Title combined table
            combined = pd.DataFrame(team_results)[
                ["team", "qualify_prob", "title_prob", "current_pts", "games_remaining", "avg_finish"]
            ].copy()
            combined.columns = ["Team", "Qualify %", "Title %", "Pts", "Games Left", "Avg Finish"]
            combined["Qualify %"] = combined["Qualify %"].apply(lambda x: f"{x * 100:.1f}%")
            combined["Title %"] = combined["Title %"].apply(lambda x: f"{x * 100:.1f}%")
            combined["Avg Finish"] = combined["Avg Finish"].apply(lambda x: f"{x:.2f}")
            st.dataframe(combined, hide_index=True, width="stretch")

        # ---- Position Distribution -------------------------------------
        with inner_tab3:
            st.subheader("Finishing Position Distribution")
            st.caption("Stacked bars show how often each team finishes in each position across all simulations.")

            teams_list = [r["team"] for r in team_results]
            pos_colors = [
                QUALIFY_GREEN,
                "#27ae60",
                WARNING_ORANGE,
                "#e67e22",
                DANGER_RED,
                "#c0392b",
                "#8e44ad",
                "#2980b9",
                "#1abc9c",
                "#95a5a6",
            ]

            fig3 = go.Figure()
            for pos in range(1, 6):
                probs = [r["position_dist"].get(f"P{pos}", 0) for r in team_results]
                fig3.add_trace(
                    go.Bar(
                        name=f"#{pos}",
                        x=teams_list,
                        y=probs,
                        marker_color=pos_colors[pos - 1],
                        hovertemplate=f"<b>%{{x}}</b><br>Finish #{pos}: %{{y:.1f}}%<extra></extra>",
                    )
                )

            fig3.update_layout(
                barmode="stack",
                yaxis_title="Probability (%)",
                xaxis_tickangle=-30,
                height=420,
                legend_title="Position",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig3, width="stretch")

            # Team selector for detailed view
            selected_team = st.selectbox("Detailed view for team:", teams_list)
            team_row = next((r for r in team_results if r["team"] == selected_team), None)
            if team_row:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Qualify Prob", f"{team_row['qualify_prob'] * 100:.1f}%")
                col2.metric("Title Prob", f"{team_row['title_prob'] * 100:.1f}%")
                col3.metric("Avg Finish", f"{team_row['avg_finish']:.2f}")
                col4.metric("Avg Final Pts", f"{team_row['avg_final_pts']:.1f}")

                pos_data = team_row.get("position_dist", {})
                pos_df = pd.DataFrame(
                    [{"Position": f"#{k[1:]}", "Probability": f"{v:.1f}%"} for k, v in sorted(pos_data.items())]
                )
                if not pos_df.empty:
                    st.dataframe(pos_df, hide_index=True, width="stretch")

        # ---- Match Importance ------------------------------------------
        with inner_tab4:
            st.subheader("Match Importance Ranking")
            st.caption(
                "Importance = average swing in playoff qualification probability "
                "when forcing each team to win. Higher = more playoff-critical."
            )

            if not match_importance:
                st.info("No remaining match importance data available.")
            else:
                mi_df = pd.DataFrame(match_importance)

                fig4 = go.Figure(
                    go.Bar(
                        x=[f"{r['team1']} vs {r['team2']}" for r in match_importance[:10]],
                        y=[r["importance"] * 100 for r in match_importance[:10]],
                        marker_color=[
                            QUALIFY_GREEN
                            if r["importance"] > 0.15
                            else WARNING_ORANGE
                            if r["importance"] > 0.08
                            else NEUTRAL_BLUE
                            for r in match_importance[:10]
                        ],
                        text=[f"{r['importance'] * 100:.1f}%" for r in match_importance[:10]],
                        textposition="auto",
                    )
                )
                fig4.update_layout(
                    yaxis_title="Importance Score (%)",
                    xaxis_tickangle=-35,
                    height=380,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig4, width="stretch")

                # Full table
                mi_display = mi_df[["match", "date", "team1", "team2", "importance", "t1_swing", "t2_swing"]].copy()
                mi_display.columns = [
                    "#",
                    "Date",
                    "Team 1",
                    "Team 2",
                    "Importance",
                    "T1 Qualify Swing",
                    "T2 Qualify Swing",
                ]
                mi_display["Importance"] = mi_display["Importance"].apply(lambda x: f"{x * 100:.1f}%")
                mi_display["T1 Qualify Swing"] = mi_display["T1 Qualify Swing"].apply(lambda x: f"{x * 100:.1f}%")
                mi_display["T2 Qualify Swing"] = mi_display["T2 Qualify Swing"].apply(lambda x: f"{x * 100:.1f}%")
                st.dataframe(mi_display, hide_index=True, width="stretch")

                st.markdown(f"*{mc.get('methodology', '')}*")
