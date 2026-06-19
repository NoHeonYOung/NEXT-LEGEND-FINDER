import streamlit as st

from explanation_engine import build_growth_explanation
from growth_model import build_manual_growth_insight
from manual_prospect_helpers import (
    STALE_SELECTION_KEYS,
    filter_mentor_candidates_by_age,
    manual_player_profile_panel_inputs,
    manual_similarity_candidates,
)
from ui_components import (
    FOOT_OPTIONS,
    MAIN_POSITION_OPTIONS,
    build_club_options,
    build_nationality_options,
    build_position_options,
    render_page_actions,
    render_player_profile_panel,
)

# 직접 입력 초기화 시 지워야 할 session_state key 목록
_MANUAL_CLEAR_KEYS = [
    "manual_player",
    "manual_attributes",
    "manual_career_settings",
    "manual_prospect_submitted",
] + STALE_SELECTION_KEYS


def _clear_manual_prospect_state():
    """직접 입력 유망주 관련 session_state를 전부 초기화한다."""
    for key in _MANUAL_CLEAR_KEYS:
        st.session_state.pop(key, None)
    if st.session_state.get("selected_entity_type") == "manual_prospect":
        st.session_state.pop("selected_entity_type", None)


def render_manual_prospect_view():
    """직접 입력 유망주 생성 화면.

    실제 DB 선수와 별도로, 사용자가 직접 입력한 능력치를 기반으로
    Dashboard / 유사 선수 후보 / 커리어 시뮬레이션 / AI 스카우팅 리포트 흐름을
    그대로 따라갈 수 있는 entity_type="manual_prospect" 선수를 생성한다."""
    st.title("직접 입력 유망주")
    st.info(
        "이 화면에서 입력한 유망주는 실제 DB 선수와 동일하게 통합 분석 대시보드, 유사 선수 후보, "
        "커리어 시뮬레이션, 분석 리포트 화면에서 분석할 수 있습니다. 생성 단계에서는 선수 정보와 능력치만 입력하고, "
        "훈련 강도와 리그 난이도는 Career Simulation에서 별도로 선택합니다."
    )

    # 이전에 생성된 직접 입력 유망주가 있으면 안내 배너 + 초기화 버튼 표시
    _prior_manual = st.session_state.get("manual_player")
    _prior_submitted = st.session_state.get("manual_prospect_submitted")
    _prior_entity = st.session_state.get("selected_entity_type") == "manual_prospect"
    if _prior_submitted and _prior_manual and _prior_entity:
        _prior_name = _prior_manual.get("name") or "직접 입력 유망주"
        _col_notice, _col_clear = st.columns([5, 1])
        with _col_notice:
            st.warning(
                f"이전에 생성된 **{_prior_name}** 유망주 결과가 있습니다. "
                "새로 생성하려면 아래 폼을 수정하고 '직접 입력 유망주 생성' 버튼을 누르거나, "
                "초기화 버튼을 클릭하세요."
            )
        with _col_clear:
            if st.button("직접 입력 초기화", key="clear_manual_top", type="secondary"):
                _clear_manual_prospect_state()
                st.rerun()

    # DB에서 국적/클럽 목록 로드 (실패 시 빈 목록으로 fallback)
    try:
        from services.db import get_distinct_nationalities, get_distinct_clubs
        _nat_list = get_distinct_nationalities()
        _club_list = get_distinct_clubs()
    except Exception:
        _nat_list = []
        _club_list = []

    _sub_position_options = build_position_options()
    _nationality_options = ["(선택 안 함)"] + build_nationality_options(_nat_list) + ["기타 / 직접 입력"]
    _club_options = ["(선택 안 함)"] + build_club_options(_club_list) + ["기타 / 직접 입력"]

    with st.form("manual_prospect_form"):
        c1, c2 = st.columns(2)
        with c1:
            custom_name = st.text_input("유망주 이름", placeholder="예: Custom Prospect A")
            custom_age = st.number_input("나이", min_value=14, max_value=35, value=18, step=1)
            custom_position = st.selectbox("주 포지션", MAIN_POSITION_OPTIONS, index=0)
            custom_sub_position = st.selectbox(
                "세부 포지션 (선택)",
                ["(없음)"] + _sub_position_options,
                index=0,
            )
            _club_sel = st.selectbox("소속팀 / 학교", _club_options, index=0)
            if _club_sel == "기타 / 직접 입력":
                custom_club = st.text_input("소속팀 직접 입력", placeholder="예: Academy FC")
            elif _club_sel == "(선택 안 함)":
                custom_club = ""
            else:
                custom_club = _club_sel
            _nat_sel = st.selectbox("국적", _nationality_options, index=0)
            if _nat_sel == "기타 / 직접 입력":
                custom_nationality = st.text_input("국적 직접 입력", placeholder="예: Korea")
            elif _nat_sel == "(선택 안 함)":
                custom_nationality = ""
            else:
                custom_nationality = _nat_sel
            custom_foot = st.selectbox("주발", FOOT_OPTIONS, index=0)
        with c2:
            custom_height = st.text_input("키(cm)", placeholder="예: 182")
            custom_note = st.text_area("관찰 메모", placeholder="예: 속도와 돌파는 좋지만 마무리와 수비 전개를 보완할 필요가 있음")
            speed = st.slider("속도/기동성", 1, 10, 7)
            dribble = st.slider("드리블", 1, 10, 6)
            finishing = st.slider("결정력", 1, 10, 5)
            passing = st.slider("패스/시야", 1, 10, 6)
            physical = st.slider("피지컬", 1, 10, 6)
            defending = st.slider("수비력", 1, 10, 5)
            work_rate = st.slider("활동량", 1, 10, 7)
            teamwork = st.slider("팀워크", 1, 10, 7)
            determination = st.slider("의지력", 1, 10, 7)
            pressing = st.slider("압박 대처", 1, 10, 5)
            growth_potential = st.slider("성장 잠재력", 1, 10, 8)

        submitted = st.form_submit_button("직접 입력 유망주 생성")

    if submitted:
        _sub = custom_sub_position if custom_sub_position != "(없음)" else ""
        manual_player = {
            "name": custom_name,
            "age": int(custom_age),
            "position": custom_position,
            "sub_position": _sub,
            "club": custom_club,
            "nationality": custom_nationality,
            "foot": custom_foot,
            "height": custom_height,
            "observation_note": custom_note,
        }
        manual_attributes = {
            "speed": float(speed),
            "dribble": float(dribble),
            "finishing": float(finishing),
            "passing": float(passing),
            "physical": float(physical),
            "defending": float(defending),
            "work_rate": float(work_rate),
            "teamwork": float(teamwork),
            "determination": float(determination),
            "pressing": float(pressing),
            "growth_potential": float(growth_potential),
        }
        manual_career_settings = {
            "training_intensity": 1.0,
            "playing_time_opportunity": 1.0,
            "league_difficulty": "medium",
            "career_choice": "stay",
            "risk_level": "normal",
        }

        for key in [
            "selected_player_id",
            "selected_player_name",
            "selected_profile_id",
            "selected_profile_fallback_note",
            "selected_manual_note_title",
            "selected_manual_note_payload",
        ] + STALE_SELECTION_KEYS:
            st.session_state.pop(key, None)

        st.session_state["manual_player"] = manual_player
        st.session_state["manual_attributes"] = manual_attributes
        st.session_state["manual_career_settings"] = manual_career_settings
        st.session_state["selected_entity_type"] = "manual_prospect"
        # 방금 제출한 폼 결과가 유효함을 표시하는 플래그
        st.session_state["manual_prospect_submitted"] = True

        growth_insight = build_manual_growth_insight(manual_player, manual_attributes, manual_career_settings)
        growth_explanation = build_growth_explanation(
            growth_insight,
            player_context={"name": manual_player.get("name"), "position": manual_player.get("position")},
        )
        st.session_state["growth_insight"] = growth_insight
        st.session_state["growth_explanation"] = growth_explanation

        st.session_state["nav_page_request"] = "유망주 통합 분석"
        st.rerun()

    # ── 생성된 직접 입력 유망주 패널 ─────────────────────────────────────────
    # manual_prospect_submitted 플래그가 있을 때만 표시한다.
    # 이전 세션의 stale manual_player가 자동으로 보이지 않도록 한다.
    manual_player = st.session_state.get("manual_player")
    if (
        not st.session_state.get("manual_prospect_submitted")
        or st.session_state.get("selected_entity_type") != "manual_prospect"
        or not manual_player
    ):
        return

    st.divider()
    st.subheader("생성된 직접 입력 유망주")

    panel_player, panel_profile = manual_player_profile_panel_inputs(manual_player)
    render_player_profile_panel(panel_player, panel_profile, entity_type="manual_prospect")

    growth_insight = st.session_state.get("growth_insight") or {}
    growth_explanation = st.session_state.get("growth_explanation") or {}
    if growth_insight:
        growth_score = growth_insight.get("growth_score")
        if growth_score is not None:
            st.metric("Manual Growth Score (기본)", f"{growth_score:.1f} / 100")
            st.progress(int(round(growth_score)))
        st.markdown(f"<div class='scout-panel'><b>왜 이 점수가 나왔나요?</b><br>{growth_explanation.get('score_reason', '')}</div>", unsafe_allow_html=True)

    st.subheader("멘토 후보")
    manual_attributes = st.session_state.get("manual_attributes") or {}
    mentor_pool = manual_similarity_candidates(manual_player, manual_attributes, limit=80)
    mentor_candidates, used_fallback = filter_mentor_candidates_by_age(
        mentor_pool,
        manual_player.get("age"),
        min_results=1,
    )
    mentor_candidates = mentor_candidates[:6]
    if used_fallback:
        st.info("나이 조건을 완화해 표시한 후보입니다.")

    if mentor_candidates:
        for mentor in mentor_candidates:
            st.markdown(
                f"""
                <div class="scout-panel">
                    <h3 style="margin-top:0;">{mentor['name']}</h3>
                    <div class="badge-row">
                        <span class="scout-badge">나이 {mentor.get('age') or '-'}</span>
                        <span class="scout-badge">{mentor.get('position') or '-'}</span>
                        <span class="scout-badge">{mentor.get('club') or '-'}</span>
                        <span class="scout-badge">멘토 적합 후보</span>
                    </div>
                    <p><b>왜 멘토로 볼 수 있나요?</b><br>{mentor.get('common_strengths', '-')}</p>
                    <p><b>훈련에서 참고할 부분</b><br>{mentor.get('difference_hint', '-')}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("이 멘토 선택", key=f"manual_prospect_mentor_{mentor['profile_id']}", type="secondary"):
                st.session_state["selected_mentor_profile_id"] = mentor['profile_id']
                st.session_state["selected_mentor_name"] = mentor['name']
                st.session_state["mentor_summary"] = (
                    f"{mentor['name']}은(는) 나이와 경험이 앞선 멘토 후보입니다. "
                    f"참고할 강점: {mentor['common_strengths']} / 훈련 과제: {mentor['difference_hint']}"
                )
                st.session_state["nav_page_request"] = "커리어 시뮬레이션"
                st.rerun()
    else:
        st.info("직접 입력 유망주를 먼저 생성해주세요. 생성 후 멘토 후보가 표시됩니다.")

    # 직접 입력 초기화 버튼 (패널 하단)
    st.divider()
    _clr_col, _ = st.columns([1, 3])
    with _clr_col:
        if st.button("직접 입력 초기화", key="clear_manual_bottom", type="secondary"):
            _clear_manual_prospect_state()
            st.rerun()

    render_page_actions([
        ("📊 통합 분석 대시보드로 이동", "유망주 통합 분석", "primary"),
        ("🤝 유사 선수 후보에서 멘토 찾기", "유사 선수 후보"),
        ("📈 커리어 시뮬레이션 시작", "커리어 시뮬레이션"),
    ], title="직접 입력 유망주 생성 완료 · 다음 단계")
