import streamlit as st

from player_coverage import build_data_coverage
from services.db import get_distinct_positions, money, search_players, show_db_error
from ui_components import (
    coverage_badge_html,
    format_coverage_reasons,
    render_data_coverage_panel,
    render_page_actions,
)

_LIMITED_ANALYSIS_NOTICE = (
    "이 선수는 Transfermarkt 기본 데이터만 연결되어 있어 "
    "FM 능력치, 멘탈 지표, style_vector 기반 유사 선수 분석은 제한됩니다. "
    "정밀 분석을 위해서는 FM profile 매칭 또는 직접 입력 유망주 기능을 사용하세요."
)


def _bool_from_row(row, key):
    value = row.get(key)
    return bool(value) if value is not None else False


def _coverage_from_search_row(row):
    player = {
        "player_id": row.get("player_id"),
        "name": row.get("name"),
        "date_of_birth": row.get("date_of_birth"),
        "market_value_in_eur": row.get("market_value_in_eur"),
        "highest_market_value_in_eur": row.get("highest_market_value_in_eur"),
    }
    has_profile = row.get("profile_id") is not None
    profile = None
    if has_profile:
        profile = {
            "profile_id": row.get("profile_id"),
            "age": row.get("age"),
            "style_vector": [1] if _bool_from_row(row, "has_style_vector") else None,
            "attributes_jsonb": {"available": True} if _bool_from_row(row, "has_attributes") else None,
            "mentality_jsonb": {"available": True} if _bool_from_row(row, "has_mentality") else None,
        }
    return player, profile


def _candidate_reason(coverage):
    level = coverage.get("analysis_level")
    if level == "full":
        return "FM profile과 style_vector가 있어 Dossier와 Mentor 분석까지 이어갈 수 있습니다."
    if level == "partial":
        return "일부 데이터가 부족하지만 Growth/Dossier 분석을 시작할 수 있습니다."
    return "FM profile 또는 핵심 분석 데이터가 부족해 제한 분석으로만 확인할 수 있습니다."


def render_prospect_search_view(show_selected_player_banner):
    st.title("Scouting Board")
    st.caption("분석 가능한 15~25세 유망주를 우선 보여주고, Limited 선수는 옵션을 켰을 때만 표시합니다.")

    selected_name = st.session_state.get("selected_player_name")
    if selected_name:
        st.success(f"현재 선택된 선수: {selected_name}")
        render_page_actions([
            ("📊 통합 분석으로 이동", "유망주 통합 분석", "primary"),
            ("🤝 유사 멘토 찾기", "유사 선수 후보"),
        ], title="선수 선택 완료 · 다음 단계")
    else:
        show_selected_player_banner()

    st.markdown(
        """
        <div class="scout-panel">
            <h3 style="margin-top:0;">검색 조건</h3>
            기본 정책: 15~25세 · Full/Partial 기본 노출 · Limited 기본 제외
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 기본 필터 옵션 ──────────────────────────────────────────────────
    analyze_only = st.checkbox(
        "분석 가능한 유망주만 보기 (FM profile 있는 선수)",
        value=True,
        help=(
            "체크 시 FM profile이 연결된 선수(유사 선수 후보·멘탈 분석 가능)만 표시합니다. "
            "해제하면 Transfermarkt 기반 전체 선수도 포함됩니다."
        ),
    )
    include_all_db = st.checkbox(
        "전체 DB 선수 포함",
        value=False,
        help="체크하면 FM profile이 없는 Limited 선수도 검색 결과에 포함할 수 있습니다.",
    )
    include_limited = st.checkbox(
        "Limited 선수 포함",
        value=False,
        help="전체 DB 선수 포함과 함께 사용하면 제한 분석 대상도 표시합니다.",
    )

    c1, c2, c3 = st.columns([1, 1.4, 1])
    with c1:
        age_range = st.slider("나이 범위", min_value=15, max_value=30, value=(15, 25), step=1)
        min_age, max_age = age_range
    with c2:
        keyword = st.text_input("선수 이름", placeholder="예: Bellingham, Yamal, Son")
    with c3:
        try:
            positions = get_distinct_positions(max_age=max_age)
        except Exception as exc:
            show_db_error("포지션 목록 조회", exc)
            positions = ["All"]
        position = st.selectbox("포지션", positions)

    c4, c5 = st.columns(2)
    with c4:
        nationality = st.text_input("국적", placeholder="예: Korea")
    with c5:
        club = st.text_input("소속팀", placeholder="예: Dortmund")

    with st.expander("고급 필터"):
        readiness = st.multiselect(
            "분석 준비도",
            ["Full", "Partial", "Limited"],
            default=["Full", "Partial"],
            help="기본 검색에서는 Full/Partial만 표시합니다. Limited는 옵션을 켠 경우에만 포함하세요.",
        )
        require_fm_profile = st.checkbox("FM profile 있음", value=False)
        require_style_vector = st.checkbox("style_vector 있음", value=False)

    filters = {
        "keyword": keyword,
        "position": position,
        "nationality": nationality,
        "club": club,
        "min_age": min_age,
        "max_age": max_age,
        "analyze_only": analyze_only,
        "include_all_db": include_all_db,
        "include_limited": include_limited,
        "readiness": readiness,
        "require_fm_profile": require_fm_profile,
        "require_style_vector": require_style_vector,
    }

    if st.button("유망주 검색", type="primary"):
        try:
            results = search_players(
                keyword=keyword,
                position=position,
                nationality=nationality,
                club=club,
                max_age=max_age,
            )
            st.session_state["prospect_results"] = results
            st.session_state["last_search_filters"] = filters
        except Exception as exc:
            show_db_error("유망주 검색", exc)
            return

    if "prospect_results" not in st.session_state:
        st.info("검색 조건을 설정한 뒤 유망주 검색 버튼을 눌러주세요.")
        return

    results = st.session_state["prospect_results"]
    last_filters = st.session_state.get("last_search_filters", {})

    # ── analyze_only 후처리 필터 ─────────────────────────────────────
    # search_players() 반환 결과에 profile_id 컬럼이 포함되어 있으므로
    # DB 스키마 변경 없이 후처리로 필터링한다.
    effective_analyze_only = analyze_only and not include_all_db
    if effective_analyze_only and "profile_id" in results.columns:
        filtered = results[results["profile_id"].notna()]
        hidden_count = len(results) - len(filtered)
    else:
        filtered = results
        hidden_count = 0

    if "age" in filtered.columns:
        age_mask = filtered["age"].isna() | ((filtered["age"] >= min_age) & (filtered["age"] <= max_age))
        filtered = filtered[age_mask]

    if require_fm_profile and "profile_id" in filtered.columns:
        before = len(filtered)
        filtered = filtered[filtered["profile_id"].notna()]
        hidden_count += before - len(filtered)

    if require_style_vector and "has_style_vector" in filtered.columns:
        filtered = filtered[filtered["has_style_vector"] == True]  # noqa: E712

    limited_visible = include_limited or include_all_db or not analyze_only

    if readiness:
        allowed_levels = {item.lower() for item in readiness}
        if limited_visible:
            allowed_levels.add("limited")
        level_values = []
        for _, row in filtered.iterrows():
            row_player, row_profile = _coverage_from_search_row(row)
            coverage = build_data_coverage(row_player, row_profile)
            level_values.append(coverage["analysis_level"])
        if level_values:
            filtered = filtered.assign(_analysis_level=level_values)
            filtered = filtered[filtered["_analysis_level"].isin(allowed_levels)]

    if not limited_visible and "_analysis_level" in filtered.columns:
        filtered = filtered[filtered["_analysis_level"] != "limited"]
    elif not limited_visible:
        level_values = []
        for _, row in filtered.iterrows():
            row_player, row_profile = _coverage_from_search_row(row)
            coverage = build_data_coverage(row_player, row_profile)
            level_values.append(coverage["analysis_level"])
        if level_values:
            filtered = filtered.assign(_analysis_level=level_values)
            filtered = filtered[filtered["_analysis_level"] != "limited"]

    st.subheader("검색 결과")
    caption_parts = [
        f"나이 {last_filters.get('min_age', '-')}-{last_filters.get('max_age', '-')}세",
        f"포지션 {last_filters.get('position', 'All')}",
    ]
    if effective_analyze_only:
        caption_parts.append("FM profile 있는 선수만 표시")
    if not limited_visible:
        caption_parts.append("Limited 제외")
    if hidden_count > 0:
        caption_parts.append(f"FM profile 없는 선수 {hidden_count}명 제외됨")
    st.caption(" · ".join(caption_parts) + " 기준으로 조회한 결과입니다.")

    if filtered.empty:
        st.warning("조건에 맞는 유망주가 없습니다.")
        if analyze_only and hidden_count > 0:
            st.info(
                f"FM profile 없는 선수 {hidden_count}명이 필터링되었습니다. "
                "'전체 DB 선수 포함'과 'Limited 선수 포함'을 켜면 제한 분석 선수도 볼 수 있습니다."
            )
        elif filtered.empty:
            st.info("최대 나이나 검색 조건을 조정해보세요.")
        return

    for _, row in filtered.iterrows():
        player_id = int(row["player_id"]) if row.get("player_id") is not None else None
        if player_id is None:
            continue

        row_player, row_profile = _coverage_from_search_row(row)
        coverage = build_data_coverage(row_player, row_profile)
        has_profile = coverage["has_fm_profile"]
        has_style_vector = coverage["has_style_vector"]
        profile_badge = (
            '<span class="scout-badge" style="background:#2A9D8F;color:#fff;">FM profile ✓</span>'
            if has_profile
            else '<span class="scout-badge" style="background:#aaa;color:#fff;">Transfermarkt only</span>'
        )
        style_badge = (
            '<span class="scout-badge" style="background:#2A9D8F;color:#fff;">style_vector ✓</span>'
            if has_style_vector
            else '<span class="scout-badge" style="background:#aaa;color:#fff;">style_vector 없음</span>'
        )

        st.markdown(
            f"""
            <div class="scout-panel">
                <h3 style="margin-top:0;">{row.get('name') or '-'}</h3>
                <div class="badge-row">
                    {coverage_badge_html(coverage.get('analysis_level'))}
                    <span class="scout-badge">나이 {row.get('age') or '-'}</span>
                    <span class="scout-badge">{row.get('position') or '-'}</span>
                    <span class="scout-badge">{row.get('sub_position') or '-'}</span>
                    <span class="scout-badge">{row.get('country_of_citizenship') or '-'}</span>
                    {profile_badge}
                    {style_badge}
                </div>
                <p style="margin-bottom:0;">
                    <b>소속팀</b> {row.get('current_club_name') or '-'} ·
                    <b>현재 시장가치</b> {money(row.get('market_value_in_eur'))}
                </p>
                <p style="margin-bottom:0;"><b>후보 판단</b> {_candidate_reason(coverage)}</p>
                <p style="margin-bottom:0;"><b>데이터 부족</b> {format_coverage_reasons(coverage, limit=3)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_data_coverage_panel(
            row_player,
            row_profile,
            title=f"데이터 커버리지 · {row.get('name') or player_id}",
            expanded=False,
        )
        if not has_profile:
            st.caption(f"⚠ {_LIMITED_ANALYSIS_NOTICE}")
            render_page_actions([
                ("✏️ 직접 입력 유망주로 보완하기", "직접 입력 유망주", "primary"),
                ("🔍 분석 가능한 선수 다시 검색하기", "유망주 검색"),
            ], title=f"Limited 선수 · {row.get('name') or player_id}")
        if st.button("이 선수 분석하기", key=f"select_prospect_{player_id}"):
            previous_player_id = st.session_state.get("selected_player_id")
            st.session_state["selected_player_id"] = player_id
            st.session_state["selected_player_name"] = row.get("name")
            if previous_player_id != player_id:
                for key in [
                    "selected_mentor_profile_id",
                    "selected_mentor_name",
                    "mentor_summary",
                    "env_settings",
                    "simulation_result",
                    "generated_report_sections",
                    "generated_report",
                    "generated_report_text",
                    "growth_insight",
                    "growth_explanation",
                    "ceiling_growth_insight",
                    "ceiling_growth_explanation",
                    "ceiling_growth_context",
                    "selected_profile_id",
                    "selected_profile_fallback_note",
                    "selected_entity_type",
                    "manual_player",
                    "manual_attributes",
                    "manual_career_settings",
                    "qualitative_text_input",
                    "qualitative_signals",
                    "gemini_advisory",
                ]:
                    st.session_state.pop(key, None)
            st.success("선수가 선택되었습니다. 유망주 통합 분석 화면에서 확인할 수 있습니다.")
            if not has_profile:
                st.warning(
                    "이 선수는 FM profile이 없습니다. "
                    "통합 분석, 유사 선수 후보, 멘탈 지표 분석은 제한됩니다."
                )
            st.info("왼쪽 메뉴에서 '유망주 통합 분석'으로 이동하세요.")
