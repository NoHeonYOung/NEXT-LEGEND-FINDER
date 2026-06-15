import streamlit as st

from services.db import money

# 메인 메뉴(사이드바 radio)의 옵션 라벨과 반드시 일치해야 하는 nav target 목록.
NAV_TARGETS = [
    "홈 / 서비스 소개",
    "유망주 검색",
    "유망주 통합 분석",
    "유사 선수 후보",
    "커리어 시뮬레이션",
    "AI 스카우팅 리포트",
    "내 스카우팅 노트",
    "실험실 (Data Lab)",
    "DB 상태 확인",
]

NAV_CHIP_LABELS = {
    "홈 / 서비스 소개": "Home",
    "유망주 검색": "Search",
    "유망주 통합 분석": "Analysis",
    "유사 선수 후보": "Mentor",
    "커리어 시뮬레이션": "Simulation",
    "AI 스카우팅 리포트": "Report",
    "내 스카우팅 노트": "Notes",
    "실험실 (Data Lab)": "Lab",
    "DB 상태 확인": "DB",
}


def go_to(nav_target):
    """nav_page_request를 통해 다음 렌더링에서 main()이 sidebar.radio 값을 갱신하도록 한다."""
    st.session_state["nav_page_request"] = nav_target
    st.rerun()


def render_nav_chips(active_page):
    st.markdown('<div class="nav-chip-row">', unsafe_allow_html=True)
    cols = st.columns(len(NAV_TARGETS))
    for col, target in zip(cols, NAV_TARGETS):
        with col:
            is_active = target == active_page
            if st.button(
                NAV_CHIP_LABELS.get(target, target),
                key=f"navchip_{target}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
                disabled=is_active,
            ):
                go_to(target)
    st.markdown('</div>', unsafe_allow_html=True)


def render_page_actions(actions, title="다음 단계"):
    """화면 하단 '다음 단계' 버튼 그룹. actions: [(label, nav_target, type), ...]"""
    if not actions:
        return
    st.markdown("---")
    st.markdown(f'<div class="next-step-title">{title}</div>', unsafe_allow_html=True)
    cols = st.columns(len(actions))
    for col, action in zip(cols, actions):
        label, target = action[0], action[1]
        button_type = action[2] if len(action) > 2 else "secondary"
        with col:
            if st.button(label, key=f"pageaction_{title}_{target}_{label}", use_container_width=True, type=button_type):
                go_to(target)


def render_player_profile_panel(player, profile=None):
    age = profile.get("age") if isinstance(profile, dict) else None
    image_url = player.get("image_url") or ""
    photo_html = f'<img class="profile-photo" src="{image_url}" />' if image_url else '<div class="profile-photo"></div>'
    badges = [player.get("position"), player.get("sub_position"), player.get("foot"), player.get("country_of_citizenship")]
    badge_html = "".join(f'<span class="scout-badge">{badge}</span>' for badge in badges if badge)
    st.markdown(
        f"""
        <div class="scout-panel profile-card">
            <div>{photo_html}</div>
            <div>
                <div class="muted">선택된 유망주</div>
                <h2 style="margin: 0 0 8px 0;">{player.get('name') or '-'}</h2>
                <div><b>소속팀</b> {player.get('current_club_name') or '-'}</div>
                <div><b>국적</b> {player.get('country_of_citizenship') or '-'}</div>
                <div class="badge-row">{badge_html}</div>
            </div>
            <div>
                <div class="stat-box"><b>나이</b><br>{age if age is not None else '-'}</div>
                <div class="stat-box"><b>현재 시장가치</b><br>{money(player.get('market_value_in_eur'))}</div>
                <div class="stat-box"><b>최고 시장가치</b><br>{money(player.get('highest_market_value_in_eur'))}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
