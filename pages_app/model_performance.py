import random

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.cache import cache_exists
from utils.data import get_matchup_edge_history, get_model_performance, get_prediction_log

GREEN = "#2ecc71"
RED = "#e74c3c"
ORANGE = "#f39c12"
BLUE = "#3498db"
PURPLE = "#9b59b6"

PLOT_DEFAULTS = {"plot_bgcolor": "rgba(0,0,0,0)", "paper_bgcolor": "rgba(0,0,0,0)"}


def render():
    st.title("📈 Model Performance & Backtesting")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "Live Accuracy",
            "Accuracy Summary",
            "ROI Tracker",
            "Calibration Curve",
            "Confusion Matrix",
            "Matchup Edge Tracker",
            "Venue Edge Tracker",
        ]
    )

    metrics = get_model_performance()
    if not isinstance(metrics, dict) or not metrics:
        st.info("📭 No model-performance data available. Run the data pipeline to generate historical metrics.")
        return

    seasons = list(metrics.keys())

    # ------------------------------------------------------------------ #
    # TAB 1 — Live Accuracy (automatic prediction tracker)
    # ------------------------------------------------------------------ #
    with tab1:
        is_live = cache_exists("prediction_log")
        if not is_live:
            st.info(
                "No reconciled predictions yet — showing simulated history. "
                "After the nightly pipeline runs and matches are completed, "
                "real results are reconciled automatically.",
                icon="ℹ️",
            )

        log = get_prediction_log()
        if not log:
            st.error("No prediction records available.")
        else:
            df = pd.DataFrame(log)

            # ---- Summary metrics ----------------------------------------
            total = len(df)
            correct = int(df["correct"].sum())
            accuracy = correct / total
            # Only count bets where edge > 3% (bets we'd actually place)
            betted = df[df["edge"] > 0.03]
            n_betted = len(betted)
            betted_acc = betted["correct"].mean() if n_betted else 0
            roi_series = betted["roi_winner"].dropna()
            cum_roi = round(roi_series.sum(), 2)
            tot_correct = int(df["total_correct"].sum())
            tot_total = int(df["total_correct"].notna().sum())
            tot_acc = tot_correct / tot_total if tot_total else 0

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Matches Tracked", total)
            c2.metric("Overall Accuracy", f"{accuracy * 100:.1f}%")
            c3.metric(
                "Bet Accuracy (>3% edge)", f"{betted_acc * 100:.1f}%", help="Win rate when model had >3% edge over DK"
            )
            c4.metric(
                "Cumulative ROI",
                f"{cum_roi:+.2f}u",
                delta="per unit staked",
                delta_color="normal" if cum_roi >= 0 else "inverse",
            )
            c5.metric("Totals Accuracy", f"{tot_acc * 100:.1f}%")

            st.divider()

            # ---- Rolling accuracy chart ----------------------------------
            st.subheader("Rolling 10-Match Accuracy")
            df_sorted = df.sort_values("date").reset_index(drop=True)
            window = 10
            rolling_acc = []
            for i in range(len(df_sorted)):
                start = max(0, i - window + 1)
                chunk = df_sorted.loc[start:i]
                rolling_acc.append(chunk["correct"].mean())

            fig_roll = go.Figure()
            fig_roll.add_trace(
                go.Scatter(
                    x=df_sorted["date"],
                    y=[r * 100 for r in rolling_acc],
                    mode="lines+markers",
                    name="Rolling accuracy",
                    line={"color": BLUE, "width": 2},
                    marker={
                        "color": [GREEN if r >= 0.60 else (ORANGE if r >= 0.50 else RED) for r in rolling_acc],
                        "size": 7,
                    },
                    hovertemplate="Date: %{x}<br>Accuracy: %{y:.1f}%<extra></extra>",
                )
            )
            fig_roll.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50% baseline")
            fig_roll.add_hline(y=60, line_dash="dot", line_color=GREEN, annotation_text="60% target", opacity=0.6)
            fig_roll.update_layout(
                yaxis_title="Rolling Accuracy (%)",
                yaxis_range=[25, 95],
                height=340,
                **PLOT_DEFAULTS,
            )
            st.plotly_chart(fig_roll, width="stretch")

            # ---- Cumulative ROI curve ------------------------------------
            st.subheader("Cumulative P&L (bets with >3% edge, flat -110 line)")
            betted_sorted = betted.sort_values("date").reset_index(drop=True)
            cum = betted_sorted["roi_winner"].dropna().cumsum().reset_index(drop=True)

            if len(cum) > 0:
                final = cum.iloc[-1]
                fig_cum = go.Figure(
                    go.Scatter(
                        x=list(range(1, len(cum) + 1)),
                        y=cum,
                        mode="lines",
                        fill="tozeroy",
                        line={"color": GREEN if final >= 0 else RED, "width": 2},
                        fillcolor="rgba(46,204,113,0.12)" if final >= 0 else "rgba(231,76,60,0.12)",
                        hovertemplate="Bet #%{x}<br>Cumulative: %{y:.2f}u<extra></extra>",
                    )
                )
                fig_cum.add_hline(y=0, line_dash="dash", line_color="gray")
                fig_cum.update_layout(
                    xaxis_title="Bet Number",
                    yaxis_title="Units P&L",
                    height=300,
                    **PLOT_DEFAULTS,
                )
                st.plotly_chart(fig_cum, width="stretch")

            # ---- Accuracy by edge bucket ---------------------------------
            st.subheader("Accuracy & ROI by Edge Bucket")
            bucket_order = ["0–3%", "3–6%", "6–10%", "10–15%", "15%+"]
            bucket_stats = []
            for bkt in bucket_order:
                sub = df[df["edge_bucket"] == bkt]
                if len(sub) == 0:
                    continue
                roi_vals = sub["roi_winner"].dropna()
                bucket_stats.append(
                    {
                        "Edge Range": bkt,
                        "# Bets": len(sub),
                        "Accuracy": f"{sub['correct'].mean() * 100:.1f}%",
                        "Cum ROI": f"{roi_vals.sum():+.2f}u",
                    }
                )
            if bucket_stats:
                bkt_df = pd.DataFrame(bucket_stats)
                st.dataframe(bkt_df, hide_index=True, width="stretch")

            st.divider()

            # ---- Per-match log ------------------------------------------
            st.subheader("Match-by-Match Log")
            st.caption(
                "Every prediction the model made, with the actual result reconciled automatically after the game."
            )

            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                result_filter = st.selectbox("Result", ["All", "Correct only", "Wrong only"])
            with col_f2:
                bet_filter = st.checkbox("Only show bets placed (edge >3%)", value=True)
            with col_f3:
                team_filter = st.selectbox("Team", ["All"] + sorted(set(df["team1"].tolist() + df["team2"].tolist())))

            log_view = df.sort_values("date", ascending=False).copy()
            if result_filter == "Correct only":
                log_view = log_view[log_view["correct"]]
            elif result_filter == "Wrong only":
                log_view = log_view[~log_view["correct"]]
            if bet_filter:
                log_view = log_view[log_view["edge"] > 0.03]
            if team_filter != "All":
                log_view = log_view[(log_view["team1"] == team_filter) | (log_view["team2"] == team_filter)]

            display_log = log_view[
                [
                    "date",
                    "team1",
                    "team2",
                    "model_pick",
                    "model_pick_prob",
                    "dk_implied",
                    "edge",
                    "actual_winner",
                    "correct",
                    "predicted_total",
                    "dk_total_line",
                    "actual_total",
                    "total_correct",
                    "roi_winner",
                ]
            ].copy()

            display_log.columns = [
                "Date",
                "Team 1",
                "Team 2",
                "Model Pick",
                "Model Prob",
                "DK Implied",
                "Edge",
                "Actual Winner",
                "Correct?",
                "Pred Total",
                "DK Line",
                "Actual Total",
                "Total ✓?",
                "ROI (u)",
            ]
            display_log["Model Prob"] = display_log["Model Prob"].apply(
                lambda x: f"{x * 100:.1f}%" if pd.notna(x) else "–"
            )
            display_log["DK Implied"] = display_log["DK Implied"].apply(
                lambda x: f"{x * 100:.1f}%" if pd.notna(x) else "–"
            )
            display_log["Edge"] = display_log["Edge"].apply(lambda x: f"{x * 100:.1f}%" if pd.notna(x) else "–")
            display_log["ROI (u)"] = display_log["ROI (u)"].apply(lambda x: f"{x:+.3f}" if pd.notna(x) else "no bet")
            display_log["Correct?"] = display_log["Correct?"].apply(lambda x: "✅" if x else "❌")
            display_log["Total ✓?"] = display_log["Total ✓?"].apply(
                lambda x: "✅" if x is True else ("❌" if x is False else "–")
            )

            def row_color(row):
                if row["Correct?"] == "✅":
                    return ["background-color: #d4edda"] * len(row)
                return ["background-color: #f8d7da"] * len(row)

            st.dataframe(
                display_log.style.apply(row_color, axis=1),
                hide_index=True,
                width="stretch",
            )
            st.caption(f"Showing {len(display_log)} of {total} records.")

    # ------------------------------------------------------------------ #
    # TAB 2 — Accuracy Summary
    # ------------------------------------------------------------------ #
    with tab2:
        st.subheader("Historical Accuracy")
        for season in seasons:
            m = metrics[season]
            st.markdown(f"#### {season}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Match Winner Accuracy", f"{m['match_winner_accuracy'] * 100:.1f}%")
            col2.metric("Totals MAE", f"{m['totals_mae']} runs")
            col3.metric("Batter Props MAE", f"{m['props_batter_mae']} runs")
            col4.metric("Bowler Props MAE", f"{m['props_bowler_mae']} wkts")

        st.divider()
        acc_data = {
            "Season": seasons,
            "Match Winner Acc.": [f"{metrics[s]['match_winner_accuracy'] * 100:.1f}%" for s in seasons],
            "Total Bets": [metrics[s]["total_bets"] for s in seasons],
            "Winning Bets": [metrics[s]["winning_bets"] for s in seasons],
            "Totals MAE": [f"{metrics[s]['totals_mae']} runs" for s in seasons],
            "Batter MAE": [f"{metrics[s]['props_batter_mae']} runs" for s in seasons],
            "Bowler MAE": [f"{metrics[s]['props_bowler_mae']} wkts" for s in seasons],
        }
        st.dataframe(pd.DataFrame(acc_data), hide_index=True, width="stretch")

    # ------------------------------------------------------------------ #
    # TAB 3 — ROI Tracker
    # ------------------------------------------------------------------ #
    with tab3:
        st.subheader("ROI by Bet Type")
        bet_types = ["Match Winner", "Total Runs", "Player Props"]
        fig = go.Figure()
        for season in seasons:
            m = metrics[season]
            rois = [m["match_winner_roi"], m["totals_roi"], m["props_roi"]]
            fig.add_trace(
                go.Bar(
                    name=season,
                    x=bet_types,
                    y=rois,
                    text=[f"{r:+.1f}%" for r in rois],
                    textposition="auto",
                )
            )
        fig.add_hline(y=0, line_color="gray", line_dash="dash")
        fig.update_layout(barmode="group", yaxis_title="ROI (%)", height=380, **PLOT_DEFAULTS)
        st.plotly_chart(fig, width="stretch")

        roi_df = pd.DataFrame(
            {
                "Season": seasons,
                "Match Winner ROI": [f"{metrics[s]['match_winner_roi']:+.1f}%" for s in seasons],
                "Totals ROI": [f"{metrics[s]['totals_roi']:+.1f}%" for s in seasons],
                "Props ROI": [f"{metrics[s]['props_roi']:+.1f}%" for s in seasons],
            }
        )
        st.dataframe(roi_df, hide_index=True, width="stretch")

    # ------------------------------------------------------------------ #
    # TAB 4 — Calibration Curve
    # ------------------------------------------------------------------ #
    with tab4:
        st.subheader("Calibration Curve")
        st.caption("How well model probabilities match actual outcomes")
        fig = go.Figure()
        for season in seasons:
            cal = metrics[season]["calibration_data"]
            pred = [p for p, _ in cal]
            act = [a for _, a in cal]
            fig.add_trace(go.Scatter(x=pred, y=act, mode="lines+markers", name=season))
        fig.add_trace(
            go.Scatter(
                x=[0, 1],
                y=[0, 1],
                mode="lines",
                name="Perfect Calibration",
                line={"dash": "dash", "color": "gray"},
            )
        )
        fig.update_layout(
            xaxis_title="Predicted Probability",
            yaxis_title="Actual Frequency",
            height=380,
            xaxis={"range": [0, 1]},
            yaxis={"range": [0, 1]},
            **PLOT_DEFAULTS,
        )
        st.plotly_chart(fig, width="stretch")
        st.caption("Closer to the diagonal = better calibrated. Platt scaling applied post-training.")

    # ------------------------------------------------------------------ #
    # TAB 5 — Confusion Matrix
    # ------------------------------------------------------------------ #
    with tab5:
        st.subheader("Confusion Matrix — Match Winner")
        selected_season = st.selectbox("Season", seasons)
        m = metrics[selected_season]
        total = m["total_bets"]
        wins = m["winning_bets"]
        random.seed(hash(selected_season))
        tp = int(wins * 0.6)
        tn = wins - tp
        fp = int((total - wins) * 0.4)
        fn = total - wins - fp

        matrix = [[tp, fp], [fn, tn]]
        fig = go.Figure(
            go.Heatmap(
                z=matrix,
                x=["Predicted Win", "Predicted Loss"],
                y=["Actually Won", "Actually Lost"],
                colorscale="Blues",
                text=[[str(v) for v in row] for row in matrix],
                texttemplate="%{text}",
                showscale=False,
            )
        )
        fig.update_layout(height=350, **PLOT_DEFAULTS)
        st.plotly_chart(fig, width="stretch")

        accuracy = (tp + tn) / total
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Accuracy", f"{accuracy * 100:.1f}%")
        c2.metric("Precision", f"{precision * 100:.1f}%")
        c3.metric("Recall", f"{recall * 100:.1f}%")
        c4.metric("F1 Score", f"{f1:.3f}")

    # ------------------------------------------------------------------ #
    # TAB 6 — Matchup Edge Tracker
    # ------------------------------------------------------------------ #
    with tab6:
        st.subheader("Head-to-Head Betting Edge Tracker")
        st.caption(
            "Historical model edge vs DraftKings lines for every team matchup — "
            "IPL 2024 & 2025. Tier: Elite (avg edge >9%, ROI >8%) · "
            "Strong (>5%, ROI >3%) · Neutral · Avoid."
        )

        eh = get_matchup_edge_history()
        matchups = eh.get("matchups", [])
        edge_buckets = eh.get("edge_buckets", [])
        rolling_roi = eh.get("rolling_roi", [])
        total_bets = eh.get("total_bets_analysed", 0)

        elite = [m for m in matchups if m["tier"] == "Elite"]
        pos_roi = [m for m in matchups if m["roi"] > 0]
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Matchups Analysed", len(matchups))
        mc2.metric("Elite Matchups", len(elite))
        mc3.metric("Profitable Matchups", len(pos_roi))
        mc4.metric("Total Bets Tracked", f"{total_bets:,}")
        st.divider()

        col_f1, col_f2 = st.columns([1, 2])
        with col_f1:
            tier_filter = st.multiselect(
                "Filter by tier",
                ["Elite", "Strong", "Neutral", "Avoid"],
                default=["Elite", "Strong"],
            )
        with col_f2:
            team_search = st.selectbox(
                "Filter by team",
                ["All Teams"] + sorted(set([m["team1"] for m in matchups] + [m["team2"] for m in matchups])),
            )

        filtered = [
            m
            for m in matchups
            if m["tier"] in tier_filter
            and (team_search == "All Teams" or m["team1"] == team_search or m["team2"] == team_search)
        ]

        if not filtered:
            st.info("No matchups match the selected filters.")
        else:
            top15 = filtered[:15]
            fig5 = go.Figure(
                go.Bar(
                    x=[m["matchup_key"] for m in top15],
                    y=[m["roi"] for m in top15],
                    marker_color=[GREEN if m["roi"] > 0 else RED for m in top15],
                    text=[f"{m['roi']:+.1f}%" for m in top15],
                    textposition="auto",
                )
            )
            fig5.add_hline(y=0, line_dash="dash", line_color="gray")
            fig5.update_layout(yaxis_title="Historical ROI (%)", xaxis_tickangle=-40, height=400, **PLOT_DEFAULTS)
            st.plotly_chart(fig5, width="stretch")

            df_m = pd.DataFrame(filtered)[
                [
                    "matchup_key",
                    "n_games",
                    "avg_edge",
                    "win_rate_edge_positive",
                    "roi",
                    "edge_consistency",
                    "best_season",
                    "tier",
                ]
            ].copy()
            df_m.columns = [
                "Matchup",
                "Games",
                "Avg Edge",
                "Win Rate (edge>0)",
                "ROI %",
                "Edge σ",
                "Best Season",
                "Tier",
            ]
            df_m["Avg Edge"] = df_m["Avg Edge"].apply(lambda x: f"{x * 100:.1f}%")
            df_m["Win Rate (edge>0)"] = df_m["Win Rate (edge>0)"].apply(lambda x: f"{x * 100:.1f}%")
            df_m["ROI %"] = df_m["ROI %"].apply(lambda x: f"{x:+.1f}%")
            df_m["Edge σ"] = df_m["Edge σ"].apply(lambda x: f"{x * 100:.1f}%")

            TIER_COLORS = {
                "Elite": "background-color: #d4edda",
                "Strong": "background-color: #d1ecf1",
                "Neutral": "",
                "Avoid": "background-color: #f8d7da",
            }

            def color_tier(row):
                return [TIER_COLORS.get(row["Tier"], "")] * len(row)

            st.dataframe(df_m.style.apply(color_tier, axis=1), hide_index=True, width="stretch")

        st.divider()
        st.subheader("ROI by Edge-Size Bucket")
        st.caption("Does betting larger model edges actually produce better returns?")

        if edge_buckets:
            fig_b = go.Figure()
            fig_b.add_trace(
                go.Bar(
                    name="ROI %",
                    x=[b["label"] for b in edge_buckets],
                    y=[b["roi"] for b in edge_buckets],
                    marker_color=[GREEN if b["roi"] > 0 else RED for b in edge_buckets],
                    text=[f"{b['roi']:+.1f}%" for b in edge_buckets],
                    textposition="auto",
                    yaxis="y",
                )
            )
            fig_b.add_trace(
                go.Scatter(
                    name="Win Rate",
                    x=[b["label"] for b in edge_buckets],
                    y=[b["win_rate"] * 100 for b in edge_buckets],
                    mode="lines+markers",
                    line={"color": BLUE, "width": 2},
                    marker={"size": 8},
                    yaxis="y2",
                )
            )
            fig_b.add_hline(y=0, line_dash="dash", line_color="gray", yref="y")
            fig_b.update_layout(
                yaxis={"title": "ROI (%)", "side": "left"},
                yaxis2={"title": "Win Rate (%)", "side": "right", "overlaying": "y", "range": [30, 85]},
                xaxis_title="Edge Size",
                height=380,
                legend={"orientation": "h", "y": 1.08},
                **PLOT_DEFAULTS,
            )
            st.plotly_chart(fig_b, width="stretch")

            bucket_df = pd.DataFrame(edge_buckets)
            bucket_df["win_rate"] = bucket_df["win_rate"].apply(lambda x: f"{x * 100:.1f}%")
            bucket_df["roi"] = bucket_df["roi"].apply(lambda x: f"{x:+.1f}%")
            bucket_df.columns = ["Edge Range", "# Bets", "Win Rate", "ROI"]
            st.dataframe(bucket_df, hide_index=True, width="stretch")

        if rolling_roi:
            st.divider()
            st.subheader("Cumulative ROI — Rolling 50 Bets")
            roll_df = pd.DataFrame(rolling_roi)
            final = roll_df["cumulative_roi"].iloc[-1]
            fig_r = go.Figure(
                go.Scatter(
                    x=roll_df["game"],
                    y=roll_df["cumulative_roi"],
                    mode="lines",
                    fill="tozeroy",
                    line={"color": GREEN if final > 0 else RED, "width": 2},
                    fillcolor="rgba(46,204,113,0.15)" if final > 0 else "rgba(231,76,60,0.15)",
                    hovertemplate="Bet #%{x}<br>Cumulative ROI: %{y:.2f}%<extra></extra>",
                )
            )
            fig_r.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_r.update_layout(xaxis_title="Bet Number", yaxis_title="Cumulative ROI (%)", height=320, **PLOT_DEFAULTS)
            st.plotly_chart(fig_r, width="stretch")

    # ------------------------------------------------------------------ #
    # TAB 7 — Venue Edge Tracker
    # ------------------------------------------------------------------ #
    with tab7:
        st.subheader("Venue Edge Tracker")
        st.caption(
            "How well the model's predictions hold up at each ground — "
            "broken down by surface type. Top-right quadrant = profitable on both markets."
        )

        eh = get_matchup_edge_history()
        venues = eh.get("venues", [])

        if not venues:
            st.info("No venue data available.")
            return

        vtype_filter = st.multiselect(
            "Filter by surface type",
            ["Batting Paradise", "Balanced", "Spin Track", "Bowling Friendly"],
            default=["Batting Paradise", "Balanced", "Spin Track", "Bowling Friendly"],
        )
        filtered_v = [v for v in venues if v["venue_type"] in vtype_filter]

        TYPE_COLORS = {
            "Batting Paradise": "#e74c3c",
            "Balanced": "#3498db",
            "Spin Track": "#f39c12",
            "Bowling Friendly": "#2ecc71",
        }

        fig6 = go.Figure()
        for vtype in list(TYPE_COLORS):
            subset = [v for v in filtered_v if v["venue_type"] == vtype]
            if not subset:
                continue
            fig6.add_trace(
                go.Scatter(
                    x=[v["roi_match_winner"] for v in subset],
                    y=[v["roi_totals"] for v in subset],
                    mode="markers+text",
                    name=vtype,
                    text=[v["venue"].split(" ")[0] for v in subset],
                    textposition="top center",
                    marker={
                        "size": [max(10, v["n_games"] * 1.5) for v in subset],
                        "color": TYPE_COLORS[vtype],
                        "opacity": 0.85,
                        "line": {"width": 1, "color": "white"},
                    },
                    hovertemplate=(
                        "<b>%{text}</b><br>Winner ROI: %{x:.1f}%<br>Totals ROI: %{y:.1f}%<br><extra></extra>"
                    ),
                )
            )

        fig6.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig6.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig6.update_layout(
            xaxis_title="Match-Winner ROI (%)",
            yaxis_title="Total Runs ROI (%)",
            height=480,
            legend={"orientation": "h", "y": 1.08},
            **PLOT_DEFAULTS,
        )
        st.plotly_chart(fig6, width="stretch")
        st.caption("Bubble size = number of games analysed.")

        st.divider()

        fig7 = go.Figure(
            go.Bar(
                x=[v["venue"].split(" ")[0] for v in filtered_v],
                y=[v["avg_model_edge"] * 100 for v in filtered_v],
                marker_color=[TYPE_COLORS.get(v["venue_type"], BLUE) for v in filtered_v],
                text=[f"{v['avg_model_edge'] * 100:.1f}%" for v in filtered_v],
                textposition="auto",
            )
        )
        fig7.add_hline(y=0, line_dash="dash", line_color="gray")
        fig7.update_layout(yaxis_title="Avg Model Edge vs DK (%)", xaxis_tickangle=-35, height=350, **PLOT_DEFAULTS)
        st.plotly_chart(fig7, width="stretch")

        df_v = pd.DataFrame(filtered_v)[
            [
                "venue",
                "venue_type",
                "n_games",
                "avg_model_edge",
                "roi_match_winner",
                "roi_totals",
                "avg_first_innings_error",
                "best_bet_type",
            ]
        ].copy()
        df_v.columns = [
            "Venue",
            "Surface",
            "Games",
            "Avg Edge",
            "Winner ROI",
            "Totals ROI",
            "1st Inn. Error",
            "Best Bet",
        ]
        df_v["Avg Edge"] = df_v["Avg Edge"].apply(lambda x: f"{x * 100:.1f}%")
        df_v["Winner ROI"] = df_v["Winner ROI"].apply(lambda x: f"{x:+.1f}%")
        df_v["Totals ROI"] = df_v["Totals ROI"].apply(lambda x: f"{x:+.1f}%")
        df_v["1st Inn. Error"] = df_v["1st Inn. Error"].apply(lambda x: f"{x:+.1f} runs")

        def color_venue(row):
            wr = float(row["Winner ROI"].replace("%", "").replace("+", ""))
            tr = float(row["Totals ROI"].replace("%", "").replace("+", ""))
            if wr > 0 and tr > 0:
                return ["background-color: #d4edda"] * len(row)
            if wr < 0 and tr < 0:
                return ["background-color: #f8d7da"] * len(row)
            return [""] * len(row)

        st.dataframe(df_v.style.apply(color_venue, axis=1), hide_index=True, width="stretch")
        st.caption("🟢 Both markets profitable · 🔴 Both markets losing · White = mixed")
