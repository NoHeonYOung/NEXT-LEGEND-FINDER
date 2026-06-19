from pathlib import Path

import streamlit as st


def load_game_ui_css():
    """Inject the shared game-style UI stylesheet."""
    css_path = Path(__file__).with_name("game_ui.css")
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

