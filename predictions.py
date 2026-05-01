import streamlit as st

st.set_page_config(
    page_title="Wicket Oracle",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded"
)

from pages_app import todays_matches, player_props, team_deep_dive, fixtures_table, value_bets, model_performance, statistics
from utils.cache import load_cache, cache_exists, cache_status, get_last_updated

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

        last_updated = get_last_updated()
        has_cache = cache_exists("todays_matches")

        if has_cache and last_updated:
            ts = last_updated.replace("T", " ").replace("Z", " UTC")
            st.success(f"Live data cached\n\n{ts}")
        else:
            st.warning(
                "No cached data found.\n\n"
                "Showing simulated data.\n\n"
                "Run the nightly pipeline to load real predictions."
            )

        with st.expander("Cache status", expanded=False):
            status = cache_status()
            for key, ts in status.items():
                icon = "✅" if ts else "⬜"
                label = ts if ts else "missing"
                st.caption(f"{icon} **{key}**: {label}")

        st.divider()
        st.caption("IPL T20 2026 Season")
        st.caption("Data: Cricsheet · The Odds API · Open-Meteo")

    PAGES[page]()


if __name__ == "__main__":
    main()
