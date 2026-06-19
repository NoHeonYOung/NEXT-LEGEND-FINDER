import streamlit as st


def render_sidebar_brand():
    st.sidebar.markdown(
        """
        <div class="game-sidebar-brand">
            <div class="kicker">Scouting Center</div>
            <div class="name">NEXT-LEGEND FINDER</div>
            <div class="sub">Board, dossier, mentors, simulation, reports</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_game_page_title(title, subtitle, kicker="Scouting Operations"):
    st.markdown(
        f"""
        <div class="game-page-title">
            <div class="kicker">{kicker}</div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

