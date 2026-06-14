import streamlit as st


def init_navigation_state():
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "home"


def navigate_to(page_name):
    st.session_state["current_page"] = page_name
    try:
        st.rerun()
    except Exception:
        pass


def render_app_header(title="NEXT-LEGEND FINDER", subtitle="스카우팅 센터"):
    st.markdown(
        """
        <div style="padding: 0.75rem 0 1rem 0; border-bottom: 1px solid #e5e7eb; margin-bottom: 1rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                <div>
                    <div style="font-size: 0.92rem; color: #475569; text-transform: uppercase; letter-spacing: 0.18em;">SCOUTING CENTER</div>
                    <div style="font-size: 1.9rem; font-weight: 800; color: #0f172a;">{title}</div>
                    <div style="font-size: 0.98rem; color: #475569;">{subtitle}</div>
                </div>
                <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
                    <button type="button" style="border: 1px solid #cbd5e1; border-radius: 999px; padding: 0.45rem 0.8rem; background: white; color: #0f172a; cursor: pointer;">홈</button>
                </div>
            </div>
        </div>
        """.format(title=title, subtitle=subtitle),
        unsafe_allow_html=True,
    )


def render_quick_nav():
    with st.sidebar:
        st.caption("빠른 이동")
        for page_label, page_key in [
            ("홈", "home"),
            ("유망주 찾기", "prospect_search"),
            ("선수 분석", "dashboard"),
            ("유사 선수", "legend_matching"),
            ("시뮬레이션", "career_simulation"),
            ("리포트", "ai_report"),
            ("노트", "scouting_notes"),
            ("DB 상태", "db_status"),
        ]:
            if st.button(page_label, key=f"nav_{page_key}", use_container_width=True):
                navigate_to(page_key)
