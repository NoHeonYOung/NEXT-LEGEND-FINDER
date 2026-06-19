import streamlit as st

from components.badges import coverage_badge_html as game_coverage_badge_html
from components.badges import coverage_label as game_coverage_label
from components.player_header import render_player_header
from player_coverage import build_data_coverage

# ── 입력 UI 옵션 상수 ────────────────────────────────────────────────────
POSITION_OPTIONS = [
    "Goalkeeper",
    "Defender",
    "Centre-Back",
    "Full-Back",
    "Wing-Back",
    "Midfielder",
    "Defensive Midfielder",
    "Central Midfielder",
    "Attacking Midfielder",
    "Winger",
    "Forward",
    "Striker",
]

# 직접 입력 폼의 "주 포지션" 드롭다운용 — 세부 포지션 없이 대분류만
MAIN_POSITION_OPTIONS = [
    "Goalkeeper",
    "Defender",
    "Midfielder",
    "Forward",
    "Striker",
]

FOOT_OPTIONS = ["Unknown", "Right", "Left", "Both"]


def build_position_options(extra_positions=None):
    """기본 포지션 목록에 DB/외부에서 가져온 추가 포지션을 합쳐 중복 제거 후 반환한다."""
    base = list(POSITION_OPTIONS)
    if extra_positions:
        for p in extra_positions:
            if p and p not in base:
                base.append(p)
    return sorted(set(base))


def build_nationality_options(nationalities=None):
    """국적 목록을 반환한다. DB에서 가져온 목록이 없으면 빈 리스트."""
    return sorted(set(n for n in (nationalities or []) if n))


def build_club_options(clubs=None):
    """클럽 목록을 반환한다. DB에서 가져온 목록이 없으면 빈 리스트."""
    return sorted(set(c for c in (clubs or []) if c))

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
    cols = st.columns(len(NAV_TARGETS))
    for col, target in zip(cols, NAV_TARGETS):
        with col:
            is_active = target == active_page
            if st.button(
                NAV_CHIP_LABELS.get(target, target),
                key=f"navchip_{target}",
                width="stretch",
                type="primary" if is_active else "secondary",
                disabled=is_active,
            ):
                go_to(target)


def render_page_actions(actions, title="다음 단계"):
    """화면 하단 '다음 단계' 버튼 그룹. actions: [(label, nav_target, type), ...]"""
    if not actions:
        return
    st.markdown(
        f"""
        <div class="game-panel game-action-panel">
            <div class="kicker">Next Actions</div>
            <div class="next-step-title">{title}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(len(actions))
    for col, action in zip(cols, actions):
        label, target = action[0], action[1]
        button_type = action[2] if len(action) > 2 else "secondary"
        with col:
            if st.button(label, key=f"pageaction_{title}_{target}_{label}", width="stretch", type=button_type):
                go_to(target)


def coverage_label(level):
    return game_coverage_label(level)


def coverage_badge_html(level):
    return game_coverage_badge_html(level, prefix="분석 준비도")


def _user_friendly_coverage_reason(reason):
    text = str(reason or "")
    replacements = {
        "FM 프로필 없음": "능력치 프로필이 아직 연결되지 않았습니다",
        "style_vector 없음": "플레이스타일 비교 데이터가 아직 없습니다",
        "나이 데이터 없음": "나이 정보가 부족합니다",
        "시장가치 데이터 없음": "시장가치 흐름 데이터가 부족합니다",
        "출전 기록 없음": "최근 출전 기록이 부족합니다",
        "attributes_jsonb 없음": "능력치 데이터가 부족합니다",
        "mentality_jsonb 없음": "멘탈/성향 데이터가 부족합니다",
    }
    return replacements.get(text, text)


def format_coverage_reasons(coverage, limit=2):
    reasons = coverage.get("missing_reasons") or []
    if not reasons:
        return "핵심 분석 데이터가 준비되어 있습니다."
    visible = [_user_friendly_coverage_reason(reason) for reason in reasons[:limit]]
    suffix = f" 외 {len(reasons) - limit}개" if len(reasons) > limit else ""
    return ", ".join(visible) + suffix


def render_data_coverage_badge(coverage, entity_type=None):
    """Compact coverage badge for cards/header areas."""
    if entity_type == "manual_prospect":
        level = "full"
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
            "has_valuation": True,
            "has_appearances": True,
            "has_fm_profile": True,
            "has_style_vector": True,
            "has_mentality": True,
            "has_attributes": True,
            "analysis_level": "full",
            "missing_reasons": [],
        }
    else:
        coverage = build_data_coverage(player, profile)

    level = "full" if entity_type == "manual_prospect" else coverage.get("analysis_level")
    status_items = [
        ("선수 기본정보", coverage.get("has_player") or entity_type == "manual_prospect"),
        ("나이", coverage.get("has_age")),
        ("시장가치 데이터", coverage.get("has_valuation")),
        ("출전 기록", coverage.get("has_appearances")),
        ("능력치 프로필", coverage.get("has_fm_profile")),
        ("플레이스타일 분석", coverage.get("has_style_vector")),
        ("멘탈/성향 데이터", coverage.get("has_mentality")),
        ("능력치 데이터", coverage.get("has_attributes")),
    ]

    coverage_grid_html = "".join(
        f"""
        <div class="game-coverage-item {'ok' if ok else 'missing'}">
            <span>{label}</span>
            <span class="status">{'OK' if ok else 'MISSING'}</span>
        </div>
        """
        for label, ok in status_items
    )

    st.markdown(
        f"""
        <div class="game-panel game-coverage-panel">
            <h3 style="margin-top:0;">{title}</h3>
            <div class="badge-row">
                {coverage_badge_html(level)}
                <span class="scout-badge">{format_coverage_reasons(coverage, limit=3)}</span>
            </div>
            <div class="game-coverage-grid">{coverage_grid_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if level == "limited":
        st.warning(
            "데이터 부족 선수입니다. 능력치 프로필 또는 플레이스타일 데이터가 없어 능력치/멘탈/유사 선수 분석이 제한됩니다."
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
                st.markdown(f"- {_user_friendly_coverage_reason(reason)}")
        st.caption(f"계산에 사용한 나이: {coverage.get('resolved_age') if coverage.get('resolved_age') is not None else '-'}")

    return coverage


def render_player_profile_panel(player, profile=None, entity_type=None):
    render_player_header(player, profile, entity_type=entity_type)
    return
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
