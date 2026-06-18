import streamlit as st

from analysis_helpers import readable_setting, safe_float
from explanation_engine import build_growth_explanation
from growth_model import (
    LEVEL_DESCRIPTIONS,
    build_manual_growth_insight,
    classify_league_level,
    classify_playing_opportunity,
    classify_risk_tendency,
    classify_training_intensity,
)
from manual_prospect_helpers import (
    STALE_SELECTION_KEYS,
    filter_mentor_candidates_by_age,
    manual_player_profile_panel_inputs,
    manual_similarity_candidates,
)
from ui_components import render_page_actions, render_player_profile_panel


def render_manual_prospect_view():
    """직접 입력 유망주 생성 화면.

    실제 DB 선수와 별도로, 사용자가 직접 입력한 능력치를 기반으로
    Dashboard / 유사 선수 후보 / 커리어 시뮬레이션 / AI 스카우팅 리포트 흐름을
    그대로 따라갈 수 있는 entity_type="manual_prospect" 선수를 생성한다."""
    st.title("직접 입력 유망주")
    st.info(
        "이 화면에서 입력한 유망주는 실제 DB 선수와 동일하게 통합 분석 대시보드, 유사 선수 후보, "
        "커리어 시뮬레이션, AI 스카우팅 리포트 화면에서 분석할 수 있습니다. 실제 Gemini API 호출은 "
        "없으며, 입력값과 FM 기반 proxy 능력치를 연결한 prototype 분석입니다."
    )

    with st.form("manual_prospect_form"):
        c1, c2 = st.columns(2)
        with c1:
            custom_name = st.text_input("유망주 이름", placeholder="예: Custom Prospect A")
            custom_age = st.number_input("나이", min_value=14, max_value=35, value=18, step=1)
            custom_position = st.text_input("포지션", placeholder="예: ST / CM / LB")
            custom_sub_position = st.text_input("세부 포지션", placeholder="예: CF / CM")
            custom_club = st.text_input("소속팀 / 학교", placeholder="예: Academy FC")
            custom_nationality = st.text_input("국적", placeholder="예: Korea")
            custom_foot = st.text_input("주발", placeholder="예: 오른발")
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

        training_intensity = st.slider("훈련 강도", 0.5, 2.0, 1.2, 0.1)
        training_level = classify_training_intensity(training_intensity)
        st.caption(f"훈련 강도: {training_level} — {LEVEL_DESCRIPTIONS['training_intensity'][training_level]}")

        playing_time = st.slider("출전 기회", 0.0, 1.0, 0.6, 0.05)
        playing_level = classify_playing_opportunity(playing_time)
        st.caption(f"출전 기회: {playing_level} — {LEVEL_DESCRIPTIONS['playing_opportunity'][playing_level]}")

        league_difficulty = st.selectbox("리그/팀 수준", ["low", "medium", "high", "elite"], index=1, format_func=lambda value: readable_setting("league_difficulty", value))
        league_level = classify_league_level(league_difficulty)
        st.caption(f"리그/팀 수준: {league_level} — {LEVEL_DESCRIPTIONS['league_level'][league_level]}")

        career_choice = st.radio("커리어 선택", ["stay", "loan", "transfer"], horizontal=True, format_func=lambda value: readable_setting("career_choice", value))

        risk_level = st.radio("리스크 성향", ["safe", "normal", "aggressive"], horizontal=True, index=1, format_func=lambda value: readable_setting("risk_level", value))
        risk_tendency = classify_risk_tendency(risk_level)
        st.caption(f"리스크 성향: {risk_tendency} — {LEVEL_DESCRIPTIONS['risk_tendency'][risk_tendency]}")

        submitted = st.form_submit_button("직접 입력 유망주 생성")

    if submitted:
        manual_player = {
            "name": custom_name,
            "age": int(custom_age),
            "position": custom_position,
            "sub_position": custom_sub_position,
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
            "training_intensity": float(training_intensity),
            "playing_time_opportunity": float(playing_time),
            "league_difficulty": league_difficulty,
            "career_choice": career_choice,
            "risk_level": risk_level,
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

        growth_insight = build_manual_growth_insight(manual_player, manual_attributes, manual_career_settings)
        growth_explanation = build_growth_explanation(
            growth_insight,
            player_context={"name": manual_player.get("name"), "position": manual_player.get("position")},
        )
        st.session_state["growth_insight"] = growth_insight
        st.session_state["growth_explanation"] = growth_explanation

        st.success(f"'{manual_player.get('name') or '직접 입력 유망주'}'가 생성되었습니다. 아래에서 분석 결과를 확인하고 다음 화면으로 이동할 수 있습니다.")

    manual_player = st.session_state.get("manual_player")
    if st.session_state.get("selected_entity_type") != "manual_prospect" or not manual_player:
        return

    st.divider()
    st.subheader("생성된 직접 입력 유망주")

    panel_player, panel_profile = manual_player_profile_panel_inputs(manual_player)
    render_player_profile_panel(panel_player, panel_profile)

    growth_insight = st.session_state.get("growth_insight") or {}
    growth_explanation = st.session_state.get("growth_explanation") or {}
    if growth_insight:
        growth_score = growth_insight.get("growth_score")
        if growth_score is not None:
            st.metric("Manual Growth Score (기본)", f"{growth_score:.1f} / 100")
            st.progress(int(round(growth_score)))
        st.markdown(f"<div class='scout-panel'><b>왜 이 점수가 나왔나요?</b><br>{growth_explanation.get('score_reason', '')}</div>", unsafe_allow_html=True)

    st.subheader("유사 멘토 후보")
    manual_attributes = st.session_state.get("manual_attributes") or {}
    mentor_candidates = manual_similarity_candidates(manual_player, manual_attributes, limit=5)
    mentor_candidates, used_fallback = filter_mentor_candidates_by_age(mentor_candidates, manual_player.get("age"))
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
                        <span class="scout-badge">유사도 {mentor.get('similarity', '-')}</span>
                    </div>
                    <p><b>공통 강점</b><br>{mentor.get('common_strengths', '-')}</p>
                    <p><b>주요 차이점</b><br>{mentor.get('difference_hint', '-')}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("이 멘토 선택", key=f"manual_prospect_mentor_{mentor['profile_id']}", type="secondary"):
                st.session_state["selected_mentor_profile_id"] = mentor['profile_id']
                st.session_state["selected_mentor_name"] = mentor['name']
                st.session_state["mentor_summary"] = (
                    f"{mentor['name']}은(는) 현재 직접 입력 능력치와 유사한 강점을 보이는 후보입니다. "
                    f"공통 강점: {mentor['common_strengths']} / 차이점: {mentor['difference_hint']}"
                )
                st.success(f"{mentor['name']}을(를) 멘토 후보로 선택했습니다.")
    else:
        st.info("현재 입력값 기준으로 멘토 후보를 생성할 수 없었습니다.")

    render_page_actions([
        ("📊 통합 분석 대시보드로 이동", "유망주 통합 분석", "primary"),
        ("🤝 유사 선수 후보에서 멘토 찾기", "유사 선수 후보"),
        ("📈 커리어 시뮬레이션 시작", "커리어 시뮬레이션"),
    ], title="직접 입력 유망주 생성 완료 · 다음 단계")
