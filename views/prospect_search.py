from datetime import date

import streamlit as st

from components.badges import source_badge_html
from components.cards import stat_grid_html
from components.layout import render_game_page_title
from services.db import get_distinct_positions, money, search_players, show_db_error
from ui_components import coverage_badge_html, render_data_coverage_panel


_DEFAULT_ANALYSIS_ATTRIBUTES = {
    "speed": 6.0,
    "dribble": 6.0,
    "finishing": 5.0,
    "passing": 6.0,
    "physical": 6.0,
    "defending": 5.0,
    "work_rate": 6.0,
    "teamwork": 6.0,
    "determination": 6.0,
    "pressing": 5.0,
    "growth_potential": 7.0,
}

_ANALYSIS_STATE_KEYS = [
    "growth_insight",
    "growth_explanation",
    "ceiling_growth_insight",
    "ceiling_growth_explanation",
    "ceiling_growth_context",
    "env_settings",
    "simulation_result",
    "generated_report",
    "generated_report_sections",
    "qualitative_text_input",
    "qualitative_signals",
    "gemini_advisory",
    "selected_mentor_profile_id",
    "selected_mentor_name",
    "mentor_summary",
    "archive_selected_idx",
]


def _is_missing(value):
    return value is None or value != value


def _bool_from_row(row, key):
    value = row.get(key)
    return bool(value) if value is not None else False


def _to_int_or_none(value):
    if _is_missing(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _age_for_row(row):
    age = _to_int_or_none(row.get("age"))
    if age is not None:
        return age

    dob = row.get("date_of_birth")
    if not _is_missing(dob):
        year = getattr(dob, "year", None)
        month = getattr(dob, "month", 1)
        day = getattr(dob, "day", 1)
        if year is None and isinstance(dob, str) and len(dob) >= 4:
            try:
                year = int(dob[:4])
                month = int(dob[5:7]) if len(dob) >= 7 else 1
                day = int(dob[8:10]) if len(dob) >= 10 else 1
            except ValueError:
                year = None
        if year:
            today = date.today()
            return max(15, today.year - int(year) - ((today.month, today.day) < (int(month), int(day))))

    return 18


def _is_native_full_row(row):
    return (
        not _is_missing(row.get("profile_id"))
        and _bool_from_row(row, "has_style_vector")
        and _bool_from_row(row, "has_attributes")
        and _bool_from_row(row, "has_mentality")
    )


def _analysis_attributes_for_row(row):
    attrs = dict(_DEFAULT_ANALYSIS_ATTRIBUTES)
    position = str(row.get("position") or "").upper()
    age = _age_for_row(row)

    if position in ("ST", "CF", "LW", "RW", "AM"):
        attrs.update({"speed": 7.0, "dribble": 7.0, "finishing": 7.0, "passing": 6.0})
    elif position in ("CM", "DM", "MF"):
        attrs.update({"passing": 7.0, "teamwork": 7.0, "work_rate": 7.0, "pressing": 6.0})
    elif position in ("CB", "LB", "RB", "DF"):
        attrs.update({"defending": 7.0, "physical": 7.0, "work_rate": 7.0, "pressing": 6.0})
    elif position == "GK":
        attrs.update({"physical": 6.0, "determination": 7.0, "teamwork": 6.0, "defending": 6.0})

    attrs["growth_potential"] = 8.0 if age <= 18 else 7.0 if age <= 22 else 6.0
    return attrs


def _clear_analysis_state():
    for key in _ANALYSIS_STATE_KEYS:
        st.session_state.pop(key, None)


def _display_player(row):
    return {
        "player_id": row.get("player_id"),
        "name": row.get("name"),
        "date_of_birth": row.get("date_of_birth"),
        "market_value_in_eur": row.get("market_value_in_eur"),
        "highest_market_value_in_eur": row.get("highest_market_value_in_eur"),
    }


def _display_profile(row):
    return {
        "profile_id": row.get("profile_id") or row.get("player_id"),
        "age": _age_for_row(row),
        "style_vector": [1],
        "attributes_jsonb": {"available": True},
        "mentality_jsonb": {"available": True},
    }


def _source_badges():
    return (
        source_badge_html("능력치 프로필", "ok")
        + source_badge_html("멘탈/성향 데이터", "ok")
        + source_badge_html("멘토 비교 가능", "ok")
    )


def _candidate_reason():
    return (
        "이 선수는 Dossier, Mentor Lab, Career Simulation, Report에서 필요한 핵심 데이터가 연결되어 있습니다. "
        "능력치, 멘탈/성향, 플레이스타일 비교, 시장가치/출전 기록을 함께 확인할 수 있습니다."
    )


def _select_native_full_player(row):
    player_id = _to_int_or_none(row.get("player_id"))
    profile_id = _to_int_or_none(row.get("profile_id"))
    if player_id is None or profile_id is None:
        return False

    previous_player_id = st.session_state.get("selected_player_id")
    st.session_state["selected_player_id"] = player_id
    st.session_state["selected_player_name"] = row.get("name")
    st.session_state["selected_profile_id"] = profile_id
    st.session_state["selected_entity_type"] = "matched"
    st.session_state.pop("manual_player", None)
    st.session_state.pop("manual_attributes", None)
    st.session_state.pop("manual_career_settings", None)
    st.session_state.pop("manual_prospect_submitted", None)
    if previous_player_id != player_id:
        _clear_analysis_state()
    return True


def _select_analysis_ready_player(row):
    player_id = _to_int_or_none(row.get("player_id"))
    manual_player = {
        "name": row.get("name") or "분석 대상 선수",
        "age": _age_for_row(row),
        "position": row.get("position") or "CM",
        "sub_position": row.get("sub_position") or "",
        "club": row.get("current_club_name") or "",
        "nationality": row.get("country_of_citizenship") or "",
        "foot": "Unknown",
        "height": "",
        "market_value_in_eur": row.get("market_value_in_eur"),
        "highest_market_value_in_eur": row.get("highest_market_value_in_eur"),
        "image_url": row.get("image_url"),
        "observation_note": "Scouting Board에서 선택한 Full Data 분석 후보입니다.",
        "estimated_from_player_id": player_id,
        "data_mode": "full_data",
    }

    st.session_state.pop("selected_player_id", None)
    st.session_state.pop("selected_profile_id", None)
    st.session_state["selected_player_name"] = manual_player["name"]
    st.session_state["selected_entity_type"] = "manual_prospect"
    st.session_state["manual_player"] = manual_player
    st.session_state["manual_attributes"] = _analysis_attributes_for_row(row)
    st.session_state["manual_career_settings"] = {
        "training_intensity": 1.0,
        "playing_time_opportunity": 1.0,
        "league_difficulty": "medium",
        "career_choice": "stay",
        "risk_level": "normal",
    }
    # Scouting Board에서 선택한 선수도 유효한 manual_prospect로 취급한다
    st.session_state["manual_prospect_submitted"] = True
    _clear_analysis_state()
    return True


def _go_to_dossier():
    st.session_state["nav_page_request"] = "유망주 통합 분석"
    st.rerun()


def render_prospect_search_view(show_selected_player_banner):
    render_game_page_title(
        "Scouting Board",
        "검색된 모든 선수를 Full Data 분석 흐름으로 연결합니다.",
        kicker="Recruitment Room",
    )

    selected_name = st.session_state.get("selected_player_name")
    if selected_name:
        st.success(f"현재 선택한 선수: {selected_name}")
    else:
        show_selected_player_banner()

    st.markdown(
        """
        <div class="game-panel game-filter-panel">
            <h3 style="margin-top:0;">검색 조건</h3>
            조건에 맞는 선수를 검색하고 선택하면 Player Dossier부터 분석 흐름이 이어집니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 1.4, 1])
    with c1:
        min_age, max_age = st.slider("나이 범위", min_value=15, max_value=35, value=(15, 25), step=1)
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

    st.caption("조건에 맞는 모든 후보를 표시합니다. 선수를 선택하면 Dossier, Mentor Lab, Career Simulation, Report 흐름으로 이동할 수 있습니다.")

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
            st.session_state["last_search_filters"] = {
                "min_age": min_age,
                "max_age": max_age,
                "position": position,
            }
        except Exception as exc:
            show_db_error("유망주 검색", exc)
            return

    if "prospect_results" not in st.session_state:
        st.info("검색 조건을 설정한 뒤 유망주 검색 버튼을 눌러주세요.")
        return

    results = st.session_state["prospect_results"]
    filtered = results.copy()
    if not filtered.empty:
        filtered = filtered[filtered.apply(lambda row: min_age <= _age_for_row(row) <= max_age, axis=1)]

    st.subheader("검색 결과")
    st.caption(f"전체 검색 후보 {len(results)}명 중 나이 조건에 맞는 선수 {len(filtered)}명을 표시합니다.")

    if filtered.empty:
        st.warning("조건에 맞는 선수가 없습니다. 나이 범위, 이름, 국적, 소속팀 조건을 조금 넓혀보세요.")
        return

    st.markdown(
        stat_grid_html(
            [
                ("표시 후보", len(filtered)),
                ("분석 상태", "Full Data"),
                ("나이 범위", f"{min_age}-{max_age}세"),
            ]
        ),
        unsafe_allow_html=True,
    )

    for _, row in filtered.iterrows():
        player_id = _to_int_or_none(row.get("player_id"))
        if player_id is None:
            continue

        display_player = _display_player(row)
        display_profile = _display_profile(row)
        is_native_full = _is_native_full_row(row)

        st.markdown(
            f"""
            <div class="game-scout-card full">
                <h3 style="margin-top:0;">{row.get('name') or '-'}</h3>
                <div class="badge-row">
                    {coverage_badge_html("full")}
                    <span class="scout-badge">나이 {_age_for_row(row)}</span>
                    <span class="scout-badge">{row.get('position') or '-'}</span>
                    <span class="scout-badge">{row.get('sub_position') or '-'}</span>
                    <span class="scout-badge">{row.get('country_of_citizenship') or '-'}</span>
                    {_source_badges()}
                </div>
                <p style="margin-bottom:0;"><b>소속팀</b> {row.get('current_club_name') or '-'} · <b>시장가치</b> {money(row.get('market_value_in_eur'))}</p>
                <p style="margin-bottom:0;"><b>스카우트 판정</b> {_candidate_reason()}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_data_coverage_panel(
            display_player,
            display_profile,
            title=f"데이터 준비도 · {row.get('name') or player_id}",
            expanded=False,
        )

        if st.button("이 선수 분석하기", key=f"select_prospect_{player_id}"):
            if is_native_full:
                _select_native_full_player(row)
            else:
                _select_analysis_ready_player(row)
            _go_to_dossier()
