import streamlit as st

st.set_page_config(
    page_title="Wicket Odds",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded"
)

from pages_app import (
    fixtures_table,
    match_hub,
    model_performance,
    player_props,
    rivalry_analyzer,
    statistics,
    team_deep_dive,
    todays_matches,
    value_bets,
)
from utils.cache import load_cache

PAGES = {
    "Today's Matches": todays_matches.render,
    "Match Hub": match_hub.render,
    "Player Props": player_props.render,
    "Rivalry Analyzer": rivalry_analyzer.render,
    "Team Deep Dive": team_deep_dive.render,
    "Fixtures & Tournament Table": fixtures_table.render,
    "Value Bets": value_bets.render,
    "Model Performance": model_performance.render,
    "Statistics": statistics.render,
}

def main():
    with st.sidebar:
        st.image("data_files/logo.png", width='stretch')
        st.markdown("## Wicket Odds")
        st.markdown("*Cricket Betting Analytics*")
        st.divider()



    tabs = st.tabs(list(PAGES.keys()))
    for tab, (name, render_fn) in zip(tabs, PAGES.items()):
        with tab:
            render_fn()


if __name__ == "__main__":
    main()
