import streamlit as st
import pandas as pd
from utils.data import get_todays_matches, get_player_props

def render():
    st.title("🎯 Player Props")
    st.caption("Batter & Bowler projections vs DraftKings lines")

    matches = get_todays_matches()
    if not matches:
        st.info("No matches today.")
        return

    match_labels = [f"{m['team1']} vs {m['team2']}" for m in matches]
    selected_label = st.selectbox("Select Match", match_labels)
    selected_match = matches[match_labels.index(selected_label)]

    props = get_player_props(selected_match)
    df = pd.DataFrame(props)

    col1, col2, col3 = st.columns(3)
    with col1:
        role_filter = st.selectbox("Role", ["All", "Batter", "Bowler"])
    with col2:
        conf_filter = st.selectbox("Confidence", ["All", "High", "Medium", "Low"])
    with col3:
        rec_filter = st.selectbox("Recommendation", ["All", "OVER", "UNDER"])

    if role_filter != "All":
        df = df[df["role"] == role_filter]
    if conf_filter != "All":
        df = df[df["confidence"] == conf_filter]
    if rec_filter != "All":
        df = df[df["recommendation"] == rec_filter]

    df = df.sort_values("edge", key=abs, ascending=False)

    st.divider()

    for _, row in df.iterrows():
        edge_color = "green" if row["edge"] > 0 else "red"
        conf_icon = {"High": "🔴", "Medium": "🟡", "Low": "⚪"}.get(row["confidence"], "")
        rec_icon = "⬆️" if row["recommendation"] == "OVER" else "⬇️"

        col1, col2, col3, col4, col5, col6 = st.columns([2, 1.5, 1, 1, 1, 1])
        with col1:
            st.markdown(f"**{row['player']}** — *{row['team']}*")
            st.caption(f"{row['role']} | {row['market']}")
        with col2:
            st.metric("Projection", f"{row['projection']}")
        with col3:
            st.metric("DK Line", f"{row['dk_line']}")
        with col4:
            delta_str = f"{row['edge']:+.1f}"
            st.metric("Edge", delta_str, delta=delta_str)
        with col5:
            st.markdown(f"**{rec_icon} {row['recommendation']}**")
        with col6:
            st.markdown(f"{conf_icon} {row['confidence']}")
        st.divider()
