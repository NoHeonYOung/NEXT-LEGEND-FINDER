import altair as alt
import pandas as pd
import streamlit as st

from analysis_helpers import (
    build_simulation_breakdown,
    build_simulation_result,
    format_percent,
    readable_setting,
    safe_float,
    simulation_comment,
)
from explanation_engine import build_growth_explanation
from growth_model import FEATURE_LABELS, apply_ceiling_adjustment, build_growth_insight
from scouting_note_payload import build_career_simulation_note_payload
from services.db import get_appearances, get_valuations, insert_scouting_note
from ui_components import render_page_actions, render_player_profile_panel


def render_career_simulation_view(player, profile, entity_type=None):
    """Career Simulation 화면 본문. app.py의 render_career_simulation()이
    선택 선수/프로필(require_selected_player/get_player_profile)을 조회한 뒤
    이 함수에 전달한다 (선택 로직은 app.py에 그대로 유지)."""
    st.title("커리어 시뮬레이션 프로토타입")
    render_player_profile_panel(player, profile)
    left, right = st.columns([1, 1.2])
    with left:
        st.subheader("시나리오 설정")
        training = st.slider("훈련 강도", 0.5, 2.0, 1.2, 0.1)
        playing_time = st.slider("출전 기회", 0.0, 1.0, 0.6, 0.05)
        league_difficulty = st.selectbox("리그 난이도", ["low", "medium", "high", "elite"], index=1, format_func=lambda value: readable_setting("league_difficulty", value))
        career_choice = st.radio("커리어 선택", ["stay", "loan", "transfer"], horizontal=True, format_func=lambda value: readable_setting("career_choice", value))
        risk_level = st.radio("리스크 성향", ["safe", "normal", "aggressive"], horizontal=True, index=1, format_func=lambda value: readable_setting("risk_level", value))
    env_settings = {
        "training_intensity": safe_float(training, 1.2),
        "playing_time_opportunity": safe_float(playing_time, 0.6),
        "league_difficulty": league_difficulty,
        "career_choice": career_choice,
        "risk_level": risk_level,
    }
    simulation_result = build_simulation_result(env_settings)
    st.session_state["env_settings"] = env_settings
    st.session_state["simulation_result"] = simulation_result
    with right:
        st.subheader("결과 요약")
        c1, c2, c3 = st.columns(3)
        c1.metric("성장 점수", simulation_result["prototype_growth_score"])
        c2.metric("성공 가능성", format_percent(simulation_result["prototype_success_probability"]))
        c3.metric("부상 리스크", format_percent(simulation_result["prototype_injury_risk"]))
        st.markdown(f'<div class="section-note">{simulation_comment(env_settings, simulation_result)}</div>', unsafe_allow_html=True)
    chart_data = pd.DataFrame({"성장 단계": ["현재", "1년 후", "2년 후", "3년 후"], "점수": [max(20, simulation_result["prototype_growth_score"] - 18), max(25, simulation_result["prototype_growth_score"] - 9), simulation_result["prototype_growth_score"], min(100, simulation_result["prototype_growth_score"] + 5)]})
    st.subheader("예상 성장 곡선")
    chart = alt.Chart(chart_data).mark_line(point=True, color="#2A9D8F", strokeWidth=3).encode(x=alt.X("성장 단계:N", title="성장 단계"), y=alt.Y("점수:Q", scale=alt.Scale(domain=[0, 100]), title="점수"), tooltip=["성장 단계:N", "점수:Q"]).properties(height=280)
    st.altair_chart(chart, use_container_width=True)
    st.markdown('<div class="warning-note">현재 결과는 실제 예측 모델이 아니라 UI 흐름 검증을 위한 프로토타입 시뮬레이션입니다.</div>', unsafe_allow_html=True)

    breakdown = build_simulation_breakdown(
        env_settings,
        simulation_result,
        entity_type=entity_type,
        mentor_name=st.session_state.get("selected_mentor_name"),
    )

    st.subheader("성장 점수 산정 근거")
    breakdown_df = pd.DataFrame(breakdown["growth_components"])
    breakdown_df.columns = ["구성 요소", "점수 기여"]
    st.dataframe(breakdown_df, use_container_width=True, hide_index=True)
    st.caption(f"위 항목들의 합을 0~100 범위로 clamp한 값이 성장 점수({simulation_result['prototype_growth_score']})입니다.")

    st.subheader("기회 / 리스크 요약")
    st.markdown(f'<div class="section-note">{breakdown["opportunity_text"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-note">{breakdown["risk_text"]}</div>', unsafe_allow_html=True)

    if breakdown["mentor_text"]:
        st.subheader("멘토 유사도 참고")
        st.markdown(f'<div class="section-note">{breakdown["mentor_text"]}</div>', unsafe_allow_html=True)

    st.subheader("데이터 타입에 따른 해석 제한 안내")
    st.markdown(f'<div class="warning-note">{breakdown["limitation_note"]}</div>', unsafe_allow_html=True)

    has_player_id = isinstance(player, dict) and player.get("player_id") is not None
    if has_player_id and entity_type != "manual_note":
        st.caption("위 시뮬레이션은 입력 조건을 비교하기 위한 프로토타입입니다. 아래에서는 실제 선수 데이터와 선택한 훈련·출전·커리어 환경을 함께 반영한 성장 전망을 확인할 수 있습니다.")

        valuations = get_valuations(player["player_id"])
        appearances = get_appearances(player["player_id"], limit=20)
        growth_insight = build_growth_insight(player, profile, appearances=appearances, valuations=valuations, entity_type=entity_type)
        growth_insight = apply_ceiling_adjustment(growth_insight, env_settings)
        growth_explanation = build_growth_explanation(
            growth_insight,
            player_context={"name": player.get("name"), "position": growth_insight.get("position_used")},
        )
        st.session_state["growth_insight"] = growth_insight
        st.session_state["growth_explanation"] = growth_explanation
        st.session_state["ceiling_growth_insight"] = growth_insight
        st.session_state["ceiling_growth_explanation"] = growth_explanation
        st.session_state["ceiling_growth_context"] = {
            "entity_type": entity_type,
            "player_id": player.get("player_id"),
            "profile_id": profile.get("profile_id") if isinstance(profile, dict) else None,
            "source": "career_simulation",
        }

        ceiling_model = growth_insight.get("ceiling_model", {})
        ceiling_explanation = growth_explanation.get("ceiling_explanation") or {}

        real_score = growth_insight["growth_score"]
        proto_score = simulation_result["prototype_growth_score"]
        final_score = ceiling_model.get("final_growth_score")
        adjustment = ceiling_model.get("scenario_adjustment", 0)

        # 1) Real Data Growth Baseline
        st.subheader("1. Real Data Growth Baseline (실제 DB 기반)")
        st.markdown('<div class="section-note">이 선수의 기본 성장 점수는 실제 시장가치 흐름, 출전 기록, 나이, FM 프로필을 바탕으로 계산되었습니다.</div>', unsafe_allow_html=True)

        b1, b2 = st.columns(2)
        b1.metric("프로토타입 성장 점수", proto_score)
        if real_score is None:
            b2.metric("Real Data Growth Baseline", "산정 불가")
        else:
            b2.metric("Real Data Growth Baseline", f"{real_score:.1f}")

        if real_score is not None:
            diff = real_score - proto_score
            if abs(diff) < 5:
                diff_text = "두 점수가 비슷한 수준으로, 프로토타입 시나리오 설정이 실제 데이터 흐름과 큰 차이가 없습니다."
            elif diff > 0:
                diff_text = f"실제 데이터 기반 점수가 프로토타입보다 {diff:.1f}점 높습니다. 실제 시장가치/출전 흐름이 시나리오 설정보다 더 긍정적입니다."
            else:
                diff_text = f"실제 데이터 기반 점수가 프로토타입보다 {abs(diff):.1f}점 낮습니다. 시나리오 설정이 실제 흐름보다 다소 낙관적일 수 있습니다."
            st.markdown(f'<div class="section-note">{diff_text}</div>', unsafe_allow_html=True)

        feature_cols = st.columns(3)
        for index, (feature_name, feature_result) in enumerate(growth_insight["features"].items()):
            col = feature_cols[index % 3]
            label = FEATURE_LABELS.get(feature_name, feature_name)
            with col:
                if feature_result["status"] == "ok":
                    st.metric(label, f"{feature_result['score'] * 100:.0f}점")
                else:
                    st.markdown(f"<div class='muted'><b>{label}</b><br>데이터 부족</div>", unsafe_allow_html=True)

        st.markdown(f"<div class='section-note'>{growth_explanation['summary']}</div>", unsafe_allow_html=True)

        st.divider()

        # 2) Coaching Scenario Report
        st.subheader("2. 코칭 시나리오 리포트")
        st.markdown("<div class='scout-panel'><b>시나리오 총평</b><br>" + ceiling_explanation.get("coaching_summary", "") + "</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='scout-panel'><b>추천 훈련 방향</b><br>" + "<br>".join(f"• {item}" for item in ceiling_explanation.get("training_directions", [])) + "</div>", unsafe_allow_html=True)
            st.markdown("<div class='scout-panel'><b>소홀히 했을 때의 단점</b><br>" + "<br>".join(f"• {item}" for item in ceiling_explanation.get("neglect_risks", [])) + "</div>", unsafe_allow_html=True)
        with c2:
            st.markdown("<div class='scout-panel'><b>기대 장점</b><br>" + "<br>".join(f"• {item}" for item in ceiling_explanation.get("expected_benefits", [])) + "</div>", unsafe_allow_html=True)
            st.markdown("<div class='scout-panel'><b>리스크 경고</b><br>" + "<br>".join(f"• {item}" for item in ceiling_explanation.get("risk_warnings", [])) + "</div>", unsafe_allow_html=True)
        st.markdown("<div class='scout-panel'><b>추천 커리어 전략</b><br>" + "<br>".join(f"• {item}" for item in ceiling_explanation.get("career_strategy", [])) + "</div>", unsafe_allow_html=True)

        with st.expander("상세 계산 근거"):
            st.caption(f"공식: {ceiling_model.get('formula', '')}")
            st.caption(f"시나리오: {ceiling_model.get('scenario_label', '-')}")
            v1, v2, v3, v4, v5 = st.columns(5)
            v1.metric("α (출전 기회)", ceiling_model.get("alpha"))
            v2.metric("γ (리그 난이도)", ceiling_model.get("gamma"))
            v3.metric("β (리스크)", ceiling_model.get("beta"))
            v4.metric("훈련 배수", ceiling_model.get("training_multiplier"))
            v5.metric("Δleague", ceiling_model.get("delta_league"))
            st.caption(f"Ceiling Scenario Adjustment: {adjustment:+.1f}점")
            for line in ceiling_explanation.get("variable_explanations", []):
                st.markdown(f"<div class='section-note'>{line}</div>", unsafe_allow_html=True)

        st.divider()

        # 3) Final Growth Score
        st.subheader("3. Final Growth Score")
        if final_score is None:
            st.metric("Final Growth Score", "산정 불가")
        else:
            st.metric("Final Growth Score", f"{final_score:.1f} / 100")
            st.progress(int(round(final_score)))
            st.caption("기본 성장 평가에 현재 시나리오의 기회와 위험을 반영한 결과입니다.")

            f_diff = final_score - proto_score
            if abs(f_diff) < 5:
                f_diff_text = "Final Growth Score는 프로토타입 성장 점수와 비슷한 수준입니다."
            elif f_diff > 0:
                f_diff_text = f"Final Growth Score가 프로토타입 성장 점수보다 {f_diff:.1f}점 높습니다."
            else:
                f_diff_text = f"Final Growth Score가 프로토타입 성장 점수보다 {abs(f_diff):.1f}점 낮습니다."
            st.markdown(f'<div class="section-note">{f_diff_text}</div>', unsafe_allow_html=True)

        st.caption("데이터 커버리지: " + " / ".join(growth_explanation["data_limitations"]))

        if st.button("현재 시뮬레이션 결과를 스카우팅 노트에 저장"):
            try:
                report_sections = {
                    "Growth Model Insight": growth_explanation.get("summary", ""),
                    "Ceiling Scenario Insight": ceiling_explanation.get("coaching_summary", ""),
                }
                report_text = "\n\n".join(
                    f"{title}\n{body}" for title, body in report_sections.items() if body
                )
                payload = build_career_simulation_note_payload(
                    entity_type=entity_type,
                    player=player,
                    profile=profile,
                    env_settings=env_settings,
                    simulation_result=simulation_result,
                    growth_insight=growth_insight,
                    growth_explanation=growth_explanation,
                    ceiling_growth_insight=st.session_state.get("ceiling_growth_insight"),
                    ceiling_growth_explanation=st.session_state.get("ceiling_growth_explanation"),
                    ceiling_growth_context=st.session_state.get("ceiling_growth_context"),
                    report_sections=report_sections,
                    report_text=report_text,
                )
                saved = insert_scouting_note(
                    player_id=player.get("player_id"),
                    profile_id=profile.get("profile_id") if isinstance(profile, dict) else None,
                    env_settings=payload["env_settings"],
                    simulation_result=payload["simulation_result"],
                    report=payload["report"],
                )
                st.success(
                    f"현재 시뮬레이션 결과가 스카우팅 노트에 저장되었습니다. "
                    f"My Scouting Notes에서 다시 확인할 수 있습니다. note_id: {saved['note_id']}"
                )
            except Exception as exc:
                st.error("시뮬레이션 결과 저장 중 오류가 발생했습니다.")
                with st.expander("개발 확인용 오류"):
                    st.exception(exc)
    else:
        st.info("Real Data Growth Baseline은 Transfermarkt/FM 데이터와 매칭된 선수에서만 표시됩니다. (직접 입력 노트는 prototype 점수만 제공됩니다.)")

    with st.expander("개발자용 시뮬레이션 원본 데이터 보기"):
        st.json({"env_settings": env_settings, "simulation_result": simulation_result, "breakdown": breakdown})

    render_page_actions([
        ("📄 AI 스카우팅 리포트 생성", "AI 스카우팅 리포트", "primary"),
        ("📝 My Scouting Notes에 저장", "내 스카우팅 노트"),
    ])
