import streamlit as st

from player_coverage import build_data_coverage, resolve_player_age
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
    "직접 입력 유망주",
    "실험실 (Data Lab)",
    "DB 상태 확인",
]

NAV_CHIP_LABELS = {
    "홈 / 서비스 소개": "Home",
    "유망주 검색": "Board",
    "유망주 통합 분석": "Dossier",
    "유사 선수 후보": "Mentor",
    "커리어 시뮬레이션": "Simulation",
    "AI 스카우팅 리포트": "Report",
    "내 스카우팅 노트": "Notes",
    "직접 입력 유망주": "Manual",
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


_COVERAGE_LABELS = {
    "full": "Full",
    "partial": "Partial",
    "limited": "Limited",
    "manual_prospect": "Manual",
}

_COVERAGE_BADGE_STYLE = {
    "full": "background:#2A9D8F;color:#fff;",
    "partial": "background:#F2C94C;color:#111;",
    "limited": "background:#A8B3C5;color:#111;",
    "manual_prospect": "background:#48C78E;color:#102335;",
}


def coverage_label(level):
    return _COVERAGE_LABELS.get(level, str(level or "-").title())


def coverage_badge_html(level):
    label = coverage_label(level)
    style = _COVERAGE_BADGE_STYLE.get(level, "background:#A8B3C5;color:#111;")
    return f'<span class="scout-badge" style="{style}">분석 준비도 {label}</span>'


def format_coverage_reasons(coverage, limit=2):
    reasons = coverage.get("missing_reasons") or []
    if not reasons:
        return "핵심 분석 데이터가 준비되어 있습니다."
    visible = reasons[:limit]
    suffix = f" 외 {len(reasons) - limit}개" if len(reasons) > limit else ""
    return ", ".join(visible) + suffix


def render_data_coverage_badge(coverage, entity_type=None):
    """Compact coverage badge for cards/header areas."""
    if entity_type == "manual_prospect":
        level = "manual_prospect"
    else:
        level = coverage.get("analysis_level")
    st.markdown(
        f"""
        <div class="badge-row">
            {coverage_badge_html(level)}
            <span class="scout-badge">{format_coverage_reasons(coverage)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_data_coverage_panel(player=None, profile=None, entity_type=None, title="Data Coverage Panel", expanded=False):
    """Display analysis readiness consistently across views.

    Manual prospects live outside player_coverage.py by design, so this helper
    renders a manual-specific coverage dict without changing the pure classifier.
    """
    if entity_type == "manual_prospect":
        coverage = {
            "has_player": True,
            "has_age": True,
            "resolved_age": (player or {}).get("age"),
            "has_valuation": False,
            "has_appearances": False,
            "has_fm_profile": True,
            "has_style_vector": False,
            "has_mentality": True,
            "has_attributes": True,
            "analysis_level": "manual_prospect",
            "missing_reasons": ["DB 시장가치 없음", "DB 출전 기록 없음", "style_vector 없음"],
        }
    else:
        coverage = build_data_coverage(player, profile)

    level = "manual_prospect" if entity_type == "manual_prospect" else coverage.get("analysis_level")
    status_items = [
        ("선수 기본정보", coverage.get("has_player") or entity_type == "manual_prospect"),
        ("나이", coverage.get("has_age")),
        ("시장가치 데이터", coverage.get("has_valuation")),
        ("출전 기록", coverage.get("has_appearances")),
        ("FM profile", coverage.get("has_fm_profile")),
        ("style_vector", coverage.get("has_style_vector")),
        ("FM 멘탈 속성 proxy", coverage.get("has_mentality")),
        ("FM 능력치", coverage.get("has_attributes")),
        ("정성 텍스트 분석", bool(st.session_state.get("qualitative_signals"))),
        ("Gemini 보조 추천", bool(st.session_state.get("gemini_advisory"))),
    ]

    st.markdown(
        f"""
        <div class="scout-panel">
            <h3 style="margin-top:0;">{title}</h3>
            <div class="badge-row">
                {coverage_badge_html(level)}
                <span class="scout-badge">{format_coverage_reasons(coverage, limit=3)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if level == "limited":
        st.warning(
            "Limited 분석 대상입니다. FM profile 또는 style_vector가 없어 능력치/멘탈/유사 선수 분석이 제한됩니다."
        )

    with st.expander("Data Coverage 상세 보기", expanded=expanded):
        cols = st.columns(2)
        for idx, (label, ok) in enumerate(status_items):
            marker = "OK" if ok else "MISSING"
            text = f"{marker} · {label}"
            with cols[idx % 2]:
                if ok:
                    st.success(text)
                else:
                    st.warning(text)
        reasons = coverage.get("missing_reasons") or []
        if reasons:
            st.markdown("**부족한 데이터**")
            for reason in reasons:
                st.markdown(f"- {reason}")
        st.caption(f"resolved_age: {coverage.get('resolved_age') if coverage.get('resolved_age') is not None else '-'}")

    return coverage


def render_player_profile_panel(player, profile=None):
    # resolve_player_age: profile.age 우선, 없으면 date_of_birth 계산 fallback
    age = resolve_player_age(player, profile)
    if age is not None:
        age_display = str(int(age)) if age == int(age) else f"{age:.1f}"
    else:
        age_display = "나이 데이터 부족"
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
                <div class="stat-box"><b>나이</b><br>{age_display}</div>
                <div class="stat-box"><b>현재 시장가치</b><br>{money(player.get('market_value_in_eur'))}</div>
                <div class="stat-box"><b>최고 시장가치</b><br>{money(player.get('highest_market_value_in_eur'))}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
