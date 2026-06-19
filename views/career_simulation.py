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
from components.badges import source_badge_html
from components.cards import delta_badge_html, game_alert_html, score_card_html, stat_grid_html
from components.layout import render_game_page_title
from explanation_engine import build_growth_explanation
from growth_model import FEATURE_LABELS, apply_ceiling_adjustment, build_growth_insight, build_manual_growth_insight
from manual_prospect_helpers import manual_player_profile_panel_inputs
from player_coverage import build_data_coverage
from scouting_note_payload import build_career_simulation_note_payload, build_manual_note_payload
from services.db import get_appearances, get_valuations, insert_scouting_note
from ui_components import render_page_actions, render_player_profile_panel


_PROVENANCE_TEXT = (
    "현재 분석은 DB에 저장된 선수 기본 정보, 시장가치/출전 기록, 능력치 프로필, "
    "Growth/Ceiling 규칙 모델을 바탕으로 생성됩니다. 정성 텍스트는 점수를 바꾸지 않고 "
    "멘탈리티 해석, 리스크 관리, 추천 훈련 방향, 리포트 코멘트의 보조 근거로만 반영됩니다."
)

_PROVENANCE_TABLE = """| 항목 | 출처 |
|---|---|
| 선수 기본 정보 | DB |
| 시장가치/출전 기록 | DB |
| 능력치/멘탈 성향 | 능력치 프로필 |
| 성장 점수 | rule-based Growth/Ceiling Model |
| 정성 텍스트 근거 | 사용자 직접 입력 |
| Gemini 역할 | 정성 텍스트 보조 해석 |
"""

TRAINING_OPTIONS = {
    "낮음 - 회복 중심": {"value": 0.90, "description": "부상 위험을 낮추고 회복을 우선하는 관리형 훈련입니다."},
    "보통 - 균형 유지": {"value": 1.00, "description": "성장과 컨디션을 균형 있게 가져가는 기본 훈련 강도입니다."},
    "높음 - 성장 집중": {"value": 1.10, "description": "기술과 피지컬 향상을 적극적으로 노리는 훈련 강도입니다."},
    "매우 높음 - 단기 집중": {"value": 1.20, "description": "단기 성장 자극은 크지만 피로와 부상 관리가 꼭 필요한 강도입니다."},
}

PLAYTIME_OPTIONS = {
    "부족 - 벤치/간헐 출전": {"value": 0.60, "description": "정기적인 경기 리듬을 만들기 어려운 출전 환경입니다."},
    "제한적 - 교체 중심": {"value": 0.80, "description": "교체 출전이나 일부 컵 대회 중심으로 경험을 얻는 단계입니다."},
    "보통 - 로테이션": {"value": 1.00, "description": "리그와 컵에서 일정 수준의 출전 기회를 받는 환경입니다."},
    "충분 - 주전급 출전": {"value": 1.15, "description": "주요 경기 또는 꾸준한 로테이션으로 성장 경험을 쌓을 수 있습니다."},
    "과다 - 혹사 위험": {"value": 0.95, "description": "경험은 많지만 피로 누적과 부상 위험을 함께 관리해야 합니다."},
}

LEAGUE_DESCRIPTIONS = {
    "low": "적응 부담은 낮지만 성장 자극도 제한될 수 있습니다.",
    "medium": "성장과 적응 부담이 비교적 균형 잡힌 환경입니다.",
    "high": "강한 경쟁으로 성장 자극은 크지만 출전 시간 확보가 중요합니다.",
    "elite": "최상위 압박을 받는 환경입니다. 출전 기회가 부족하면 성장 효과가 제한될 수 있습니다.",
}

RISK_DESCRIPTIONS = {
    "safe": "안정적인 선택을 우선해 실패 가능성을 낮춥니다.",
    "normal": "성장 가능성과 안정성을 균형 있게 봅니다.",
    "aggressive": "성장 가능성은 키우지만 적응 실패와 부상 위험도 커집니다.",
}


def _option_value(options, label, default):
    return safe_float(options.get(label, {}).get("value"), default)


def _option_description(options, label):
    return options.get(label, {}).get("description", "")


def _render_ceiling_report(growth_insight, growth_explanation, proto_score, entity_label):
    ceiling_model = growth_insight.get("ceiling_model", {})
    ceiling_explanation = growth_explanation.get("ceiling_explanation") or {}
    real_score = growth_insight.get("growth_score")
    final_score = ceiling_model.get("final_growth_score")
    adjustment = ceiling_model.get("scenario_adjustment", 0)

    st.markdown(
        '<div class="game-lab-grid">'
        + score_card_html(
            f"{entity_label} Growth Baseline",
            "산정 불가" if real_score is None else f"{real_score:.1f}",
            "규칙 기반 성장 기준점",
            badge_html=source_badge_html("데이터 기반 분석", "ok"),
            progress=real_score,
        )
        + score_card_html(
            "Scenario Adjustment",
            f"{adjustment:+.1f}",
            "현재 선택한 환경 반영",
            badge_html=delta_badge_html(adjustment),
        )
        + score_card_html(
            "Final Growth Score",
            "산정 불가" if final_score is None else f"{final_score:.1f} / 100",
            "기준점 + 시나리오 조정",
            badge_html=source_badge_html("Ceiling result", "warning"),
            progress=final_score,
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    st.subheader("1. 성장 기준점")
    st.markdown(f"<div class='section-note'>{growth_explanation.get('summary', '')}</div>", unsafe_allow_html=True)
    if real_score is not None:
        diff = real_score - proto_score
        if abs(diff) < 5:
            diff_text = "프로토타입 설정값과 실제 데이터 기반 기준점이 비슷한 수준입니다."
        elif diff > 0:
            diff_text = f"실제 데이터 기반 기준점이 프로토타입보다 {diff:.1f}점 높습니다."
        else:
            diff_text = f"실제 데이터 기반 기준점이 프로토타입보다 {abs(diff):.1f}점 낮습니다."
        st.markdown(f"<div class='section-note'>{diff_text}</div>", unsafe_allow_html=True)

    feature_cols = st.columns(3)
    for index, (feature_name, feature_result) in enumerate(growth_insight.get("features", {}).items()):
        label = FEATURE_LABELS.get(feature_name, feature_name)
        with feature_cols[index % 3]:
            if feature_result.get("status") == "ok":
                st.metric(label, f"{feature_result.get('score', 0) * 100:.0f}점")
            else:
                st.markdown(f"<div class='muted'><b>{label}</b><br>데이터 부족</div>", unsafe_allow_html=True)

    st.divider()
    st.subheader("2. 코칭 시나리오 리포트")
    st.markdown(
        f"<div class='scout-panel'><b>시나리오 총평</b><br>{ceiling_explanation.get('coaching_summary', '')}</div>",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            "<div class='scout-panel'><b>추천 훈련 방향</b><br>"
            + "<br>".join(f"- {item}" for item in ceiling_explanation.get("training_directions", []))
            + "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='scout-panel'><b>소홀히 했을 때의 단점</b><br>"
            + "<br>".join(f"- {item}" for item in ceiling_explanation.get("neglect_risks", []))
            + "</div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            "<div class='scout-panel'><b>기대 장점</b><br>"
            + "<br>".join(f"- {item}" for item in ceiling_explanation.get("expected_benefits", []))
            + "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='scout-panel'><b>리스크 경고</b><br>"
            + "<br>".join(f"- {item}" for item in ceiling_explanation.get("risk_warnings", []))
            + "</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<div class='scout-panel'><b>추천 커리어 전략</b><br>"
        + "<br>".join(f"- {item}" for item in ceiling_explanation.get("career_strategy", []))
        + "</div>",
        unsafe_allow_html=True,
    )

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
    st.subheader("3. Final Growth Score")
    if final_score is None:
        st.metric("Final Growth Score", "산정 불가")
    else:
        st.metric("Final Growth Score", f"{final_score:.1f} / 100")
        st.progress(int(round(final_score)))
        st.caption("기본 성장 평가에 현재 시나리오의 기회와 위험을 반영한 결과입니다.")

    st.caption("데이터 커버리지: " + " / ".join(growth_explanation.get("data_limitations", [])))


def render_career_simulation_view(player, profile, entity_type=None):
    render_game_page_title(
        "Career Simulation",
        "훈련 강도, 출전 기회, 리그 난이도, 커리어 선택, 리스크 성향에 따른 성장 시나리오를 비교합니다.",
        kicker="Scenario Lab",
    )
    with st.expander("분석 근거 안내"):
        st.caption(_PROVENANCE_TEXT)
        st.markdown(_PROVENANCE_TABLE)

    manual_player = st.session_state.get("manual_player") if entity_type == "manual_prospect" else None
    if manual_player:
        panel_player, panel_profile = manual_player_profile_panel_inputs(manual_player)
        render_player_profile_panel(panel_player, panel_profile, entity_type="manual_prospect")
    else:
        render_player_profile_panel(player, profile, entity_type=entity_type)

    left, right = st.columns([1, 1.2])
    with left:
        st.markdown(
            """
            <div class="game-panel game-scenario-panel">
                <div class="kicker">Scenario Control Panel</div>
                <h3>Career environment</h3>
                <div class="game-muted">선택지는 기존 숫자값으로 변환되며 Growth/Ceiling 공식은 변경하지 않습니다.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.subheader("시나리오 설정")
        training_label = st.selectbox("훈련 강도", list(TRAINING_OPTIONS.keys()), index=3)
        training = _option_value(TRAINING_OPTIONS, training_label, 1.2)
        st.caption(_option_description(TRAINING_OPTIONS, training_label))

        playing_label = st.selectbox("출전 기회", list(PLAYTIME_OPTIONS.keys()), index=0)
        playing_time = _option_value(PLAYTIME_OPTIONS, playing_label, 0.6)
        st.caption(_option_description(PLAYTIME_OPTIONS, playing_label))

        league_difficulty = st.selectbox(
            "리그 난이도",
            ["low", "medium", "high", "elite"],
            index=1,
            format_func=lambda value: readable_setting("league_difficulty", value),
        )
        st.caption(LEAGUE_DESCRIPTIONS.get(league_difficulty, ""))

        career_choice = st.radio(
            "커리어 선택",
            ["stay", "loan", "transfer"],
            horizontal=True,
            format_func=lambda value: readable_setting("career_choice", value),
        )
        risk_level = st.radio(
            "리스크 성향",
            ["safe", "normal", "aggressive"],
            horizontal=True,
            index=1,
            format_func=lambda value: readable_setting("risk_level", value),
        )
        st.caption(RISK_DESCRIPTIONS.get(risk_level, ""))

    env_settings = {
        "training_intensity": safe_float(training, 1.2),
        "playing_time_opportunity": safe_float(playing_time, 0.6),
        "league_difficulty": league_difficulty,
        "career_choice": career_choice,
        "risk_level": risk_level,
        "training_label": training_label,
        "playing_time_label": playing_label,
    }
    simulation_result = build_simulation_result(env_settings)
    st.session_state["env_settings"] = env_settings
    st.session_state["simulation_result"] = simulation_result

    with right:
        st.markdown(
            """
            <div class="game-panel game-result-panel">
                <div class="kicker">Simulation Result Panel</div>
                <h3>Scenario readout</h3>
                <div class="game-muted">선택한 훈련 강도, 출전 기회, 리스크 성향에 따른 성장 가능성 변화를 비교합니다.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.subheader("결과 요약")
        st.markdown(
            stat_grid_html(
                [
                    ("성장 점수", simulation_result["prototype_growth_score"]),
                    ("성공 가능성", format_percent(simulation_result["prototype_success_probability"])),
                    ("부상 리스크", format_percent(simulation_result["prototype_injury_risk"])),
                ]
            ),
            unsafe_allow_html=True,
        )
        st.markdown(f'<div class="section-note">{simulation_comment(env_settings, simulation_result)}</div>', unsafe_allow_html=True)

    chart_data = pd.DataFrame(
        {
            "성장 단계": ["현재", "1년 후", "2년 후", "3년 후"],
            "점수": [
                max(20, simulation_result["prototype_growth_score"] - 18),
                max(25, simulation_result["prototype_growth_score"] - 9),
                simulation_result["prototype_growth_score"],
                min(100, simulation_result["prototype_growth_score"] + 5),
            ],
        }
    )
    st.subheader("조건별 성장 시나리오")
    chart = (
        alt.Chart(chart_data)
        .mark_line(point=alt.OverlayMarkDef(color="#6ee7a8"), color="#39d5bd", strokeWidth=3)
        .encode(
            x=alt.X("성장 단계:N", title="성장 단계"),
            y=alt.Y("점수:Q", scale=alt.Scale(domain=[0, 100]), title="점수"),
            tooltip=["성장 단계:N", "점수:Q"],
        )
        .properties(height=280, background="transparent")
        .configure_view(fill="transparent", stroke="transparent")
    )
    st.altair_chart(chart, use_container_width=True)
    st.markdown(
        game_alert_html(
            "시뮬레이션 해석 안내",
            "선택한 훈련 강도, 출전 기회, 리그 난이도, 리스크 성향에 따라 성장 가능성이 어떻게 달라질 수 있는지 비교해 보는 참고용 시뮬레이션입니다.",
            "info",
        ),
        unsafe_allow_html=True,
    )

    breakdown = build_simulation_breakdown(
        env_settings,
        simulation_result,
        entity_type=entity_type,
        mentor_name=st.session_state.get("selected_mentor_name"),
    )

    st.subheader("성장 점수 산정 근거")
    breakdown_df = pd.DataFrame(breakdown["growth_components"])
    breakdown_df.columns = ["구성 요소", "점수 기여"]
    st.dataframe(breakdown_df, width="stretch", hide_index=True)
    st.caption(f"위 항목들의 합을 0~100 범위로 제한한 값이 성장 점수({simulation_result['prototype_growth_score']})입니다.")

    st.subheader("기회 / 리스크 요약")
    st.markdown(f'<div class="section-note">{breakdown["opportunity_text"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-note">{breakdown["risk_text"]}</div>', unsafe_allow_html=True)

    if breakdown["mentor_text"] and st.session_state.get("selected_mentor_name"):
        st.subheader("멘토 참고")
        st.markdown(f'<div class="section-note">{breakdown["mentor_text"]}</div>', unsafe_allow_html=True)

    if entity_type == "transfermarkt_only":
        coverage = build_data_coverage(player, profile)
        resolved_age = coverage["resolved_age"]
        is_old_player = resolved_age is not None and resolved_age >= 25
        if is_old_player:
            st.info("이 분석은 기본 선수 정보 기반 제한 분석입니다. 능력치/멘탈 성향 기반 판단은 제외되었습니다.")
        else:
            st.info("이 분석은 기본 선수 정보 기반 제한 분석입니다. 정밀 분석에는 능력치 프로필이 필요합니다.")

    has_player_id = isinstance(player, dict) and player.get("player_id") is not None
    if has_player_id and entity_type != "manual_note":
        st.caption("아래에서는 실제 선수 데이터와 선택한 훈련·출전·커리어 환경을 함께 반영한 성장 전망을 확인할 수 있습니다.")

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

        _render_ceiling_report(growth_insight, growth_explanation, simulation_result["prototype_growth_score"], "Real Data")

        if st.button("현재 시뮬레이션 결과를 스카우팅 노트에 저장"):
            try:
                report_sections = {
                    "Growth Model Insight": growth_explanation.get("summary", ""),
                    "Ceiling Scenario Insight": (growth_explanation.get("ceiling_explanation") or {}).get("coaching_summary", ""),
                }
                report_text = "\n".join(filter(None, [report_sections.get("Growth Model Insight"), report_sections.get("Ceiling Scenario Insight")]))
                payload = build_career_simulation_note_payload(
                    player=player,
                    profile=profile,
                    entity_type=entity_type,
                    env_settings=env_settings,
                    simulation_result=simulation_result,
                    growth_insight=growth_insight,
                    growth_explanation=growth_explanation,
                    ceiling_growth_insight=growth_insight,
                    ceiling_growth_explanation=growth_explanation,
                    ceiling_growth_context=st.session_state.get("ceiling_growth_context"),
                    report_sections=report_sections,
                    report_text=report_text,
                )
                saved = insert_scouting_note(
                    player_id=payload["player_id"],
                    profile_id=payload["profile_id"],
                    env_settings=payload["env_settings"],
                    simulation_result=payload["simulation_result"],
                    report=payload["report"],
                )
                st.success(f"현재 시뮬레이션 결과가 스카우팅 노트에 저장되었습니다. note_id: {saved['note_id']}")
            except Exception as exc:
                st.error("시뮬레이션 결과 저장 중 오류가 발생했습니다.")
                with st.expander("개발 확인용 오류"):
                    st.exception(exc)
    elif entity_type == "manual_prospect" and manual_player:
        manual_attributes = st.session_state.get("manual_attributes") or {}
        manual_career_settings = st.session_state.get("manual_career_settings") or {}
        growth_insight = build_manual_growth_insight(manual_player, manual_attributes, manual_career_settings)
        growth_insight = apply_ceiling_adjustment(growth_insight, env_settings)
        growth_explanation = build_growth_explanation(
            growth_insight,
            player_context={"name": manual_player.get("name"), "position": growth_insight.get("position_used")},
        )
        st.session_state["growth_insight"] = growth_insight
        st.session_state["growth_explanation"] = growth_explanation
        st.session_state["ceiling_growth_insight"] = growth_insight
        st.session_state["ceiling_growth_explanation"] = growth_explanation
        st.session_state["ceiling_growth_context"] = {"entity_type": "manual_prospect", "source": "career_simulation"}

        _render_ceiling_report(growth_insight, growth_explanation, simulation_result["prototype_growth_score"], "Manual")

        if st.button("현재 시뮬레이션 결과를 스카우팅 노트에 저장"):
            try:
                payload = build_manual_note_payload(
                    manual_player=manual_player,
                    manual_attributes=manual_attributes,
                    manual_career_settings=manual_career_settings,
                    growth_insight=growth_insight,
                    growth_explanation=growth_explanation,
                    ceiling_growth_insight=growth_insight,
                    ceiling_growth_explanation=growth_explanation,
                    ceiling_growth_context={"entity_type": "manual_prospect", "source": "career_simulation"},
                    env_settings=env_settings,
                    simulation_result=simulation_result,
                    report_sections={"Growth Model Insight": growth_explanation.get("summary", "")},
                    source="career_simulation",
                )
                saved = insert_scouting_note(
                    player_id=payload["player_id"],
                    profile_id=payload["profile_id"],
                    env_settings=payload["env_settings"],
                    simulation_result=payload["simulation_result"],
                    report=payload["report"],
                )
                st.success(f"현재 시뮬레이션 결과가 스카우팅 노트에 저장되었습니다. note_id: {saved['note_id']}")
            except Exception as exc:
                st.error("시뮬레이션 결과 저장 중 오류가 발생했습니다.")
                with st.expander("개발 확인용 오류"):
                    st.exception(exc)
    else:
        st.info("Real Data Growth Baseline은 데이터와 매칭된 선수에서만 표시됩니다.")

    with st.expander("개발자용 시뮬레이션 원본 데이터 보기"):
        st.json({"env_settings": env_settings, "simulation_result": simulation_result, "breakdown": breakdown})

    render_page_actions(
        [
            ("분석 리포트 초안 생성", "AI 스카우팅 리포트", "primary"),
            ("My Scouting Notes에 저장/조회", "내 스카우팅 노트"),
        ]
    )
