import streamlit as st

st.set_page_config(
    page_title="Wicket Oracle",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded"
)

from pages_app import todays_matches, player_props, team_deep_dive, fixtures_table, value_bets, model_performance, statistics

PAGES = {
    "Today's Matches": todays_matches.render,
    "Player Props": player_props.render,
    "Team Deep Dive": team_deep_dive.render,
    "Fixtures & Tournament Table": fixtures_table.render,
    "Value Bets": value_bets.render,
    "Model Performance": model_performance.render,
    "Statistics": statistics.render,
}

def main():
    with st.sidebar:
        st.image("data_files/logo.png", use_container_width=True)
        st.markdown("## Wicket Oracle")
        st.markdown("*Cricket Betting Analytics*")
        st.divider()
        page = st.selectbox("Navigate to", list(PAGES.keys()))
        st.divider()
        st.caption("IPL T20 2026 Season")
        st.caption("Data: Cricsheet · The Odds API · Open-Meteo")

    PAGES[page]()

if __name__ == "__main__":
    main()
