import streamlit as st

from analysis_helpers import (
    MENTALITY_KEYS,
    attr_names,
    format_percent,
    parse_json_field,
    position_training_hint,
    safe_float,
    simulation_comment,
    top_attributes,
)
from scouting_note_payload import build_ai_report_note_payload
from services.db import insert_scouting_note
from ui_components import render_page_actions, render_player_profile_panel


def is_ceiling_context_current(context, player, profile, entity_type):
    if not isinstance(context, dict):
        return False

    if entity_type == "manual_note":
        return context.get("entity_type") == "manual_note"

    if context.get("entity_type") == "manual_note" or not isinstance(player, dict):
        return False

    current_player_id = player.get("player_id")
    if current_player_id is None or context.get("player_id") != current_player_id:
        return False

    current_profile_id = profile.get("profile_id") if isinstance(profile, dict) else None
    context_profile_id = context.get("profile_id")
    if current_profile_id is not None or context_profile_id is not None:
        return current_profile_id == context_profile_id

    return True


def get_current_growth_result(player, profile, entity_type):
    context = st.session_state.get("ceiling_growth_context")
    if is_ceiling_context_current(context, player, profile, entity_type):
        ceiling_insight = st.session_state.get("ceiling_growth_insight")
        ceiling_explanation = st.session_state.get("ceiling_growth_explanation")
        if (
            isinstance(ceiling_insight, dict)
            and ceiling_insight.get("ceiling_model")
            and isinstance(ceiling_explanation, dict)
            and ceiling_explanation.get("ceiling_explanation")
        ):
            return ceiling_insight, ceiling_explanation

    return (
        st.session_state.get("growth_insight"),
        st.session_state.get("growth_explanation"),
    )


def get_report_sections(player, profile, env_settings, simulation_result, growth_insight=None, growth_explanation=None):
    attributes = parse_json_field(profile.get("attributes_jsonb")) if profile else {}
    mentality = parse_json_field(profile.get("mentality_jsonb")) if profile else {}
    basis = mentality.get("basis", {}) if isinstance(mentality, dict) else {}
    strength_names = attr_names(top_attributes(attributes, limit=3)) or "주요 강점 데이터"
    weakness_names = attr_names(top_attributes(attributes, limit=2, reverse=False)) or "보완 데이터"
    mental_names = attr_names(top_attributes(basis, MENTALITY_KEYS, 2, True)) or "멘탈 강점"
    mental_weak = attr_names(top_attributes(basis, MENTALITY_KEYS, 2, False)) or "멘탈 보완점"
    age = profile.get("age") if isinstance(profile, dict) else None
    player_name = player.get("name") or "선택 선수"
    position = player.get("position") or "포지션 정보 없음"
    club = player.get("current_club_name") or "소속팀 정보 없음"
    growth_score = safe_float(simulation_result.get("prototype_growth_score"), None)
    growth_text = f"{growth_score:.1f}" if growth_score is not None else "-"
    success_text = format_percent(simulation_result.get("prototype_success_probability"))
    injury_text = format_percent(simulation_result.get("prototype_injury_risk"))
    mentor_summary = st.session_state.get("mentor_summary")
    mentor_note = mentor_summary or "선택된 멘토가 없어 이번 초안에는 멘토링 가이드가 반영되지 않았습니다."

    sections = {
        "종합 평가": (
            f"{player_name}은 나이 {age if age is not None else '-'}, {position}, {club} 소속으로 확인됩니다. "
            f"선택 선수 데이터와 FM 기반 proxy 능력치를 종합하면 {strength_names}이 돋보이는 유형으로 해석할 수 있습니다."
        ),
        "강점": (
            f"높은 능력치는 {strength_names}이며, 멘탈리티 강점은 {mental_names}입니다. "
            "현재 역할에서 강점을 유지하면서 반복적으로 활용할 수 있는 경기 환경이 중요합니다."
        ),
        "보완점": (
            f"낮은 능력치는 {weakness_names}이며, 멘탈리티 보완점은 {mental_weak}입니다. "
            "상위 수준으로 이동하기 전 해당 지표가 실제 경기에서 어떤 제약으로 나타나는지 함께 확인해야 합니다."
        ),
        "훈련 제안": (
            f"{position_training_hint(position, weakness_names)} 단기적으로는 {strength_names}을 유지하고, "
            f"{weakness_names}과 {mental_weak}을 단계적으로 보완하는 훈련 구성이 적절합니다."
        ),
        "커리어 조언": (
            f"{simulation_comment(env_settings, simulation_result)} 시뮬레이션 결과는 성장 점수 {growth_text}, "
            f"성공 가능성 {success_text}, 부상 리스크 {injury_text}입니다. 이는 실제 예측 모델이 아닌 프로토타입 결과입니다."
        ),
        "멘토링 참고사항": mentor_note,
        "저장 정보": (
            "저장 시 선택 선수, 시뮬레이션 설정값, 프로토타입 결과, 템플릿 기반 리포트 초안이 "
            "기존 scouting_notes 테이블에 저장됩니다. 앱은 DB 스키마를 자동 변경하지 않습니다."
        ),
    }

    if growth_insight and growth_explanation:
        growth_score = growth_insight.get("growth_score")
        score_text = f"{growth_score:.1f} / 100" if growth_score is not None else "산정 불가"
        mode_label = "직접 입력 기반 prototype" if growth_insight.get("mode") == "manual_prototype" else "실제 DB 기반"
        sections["Growth Model Insight"] = (
            f"({mode_label}) Growth Score: {score_text}<br>"
            f"{growth_explanation.get('summary', '')}<br>"
            f"{growth_explanation.get('score_reason', '')}<br>"
            "강점: " + " / ".join(growth_explanation.get("strengths", [])) + "<br>"
            "리스크: " + " / ".join(growth_explanation.get("risks", [])) + "<br>"
            "추천 성장 방향: " + " / ".join(growth_explanation.get("recommendations", []))
        )

        ceiling_explanation = growth_explanation.get("ceiling_explanation")
        if ceiling_explanation:
            final_score = ceiling_explanation.get("final_growth_score")
            final_text = f"{final_score:.1f} / 100" if final_score is not None else "산정 불가"
            sections["Ceiling Scenario Insight"] = (
                f"시나리오 성격: {ceiling_explanation.get('scenario_nature', ceiling_explanation.get('coaching_summary', ''))}<br>"
                f"성장 가능성: 현재 환경의 기회와 위험을 함께 반영한 종합 성장 전망은 {final_text}입니다.<br>"
                "추천 훈련 방향: " + " / ".join(ceiling_explanation.get("training_directions", [])) + "<br>"
                "기대 장점: " + " / ".join(ceiling_explanation.get("expected_benefits", [])) + "<br>"
                "리스크 경고: " + " / ".join(ceiling_explanation.get("risk_warnings", [])) + "<br>"
                "추천 커리어 전략: " + " / ".join(ceiling_explanation.get("career_strategy", []))
            )

    return sections


def sections_to_report_text(sections):
    lines = ["AI 스카우팅 리포트 초안"]
    for title, content in sections.items():
        lines.extend(["", title, str(content)])
    return "\n".join(lines)


def render_ai_report_view(player, profile):
    """AI Report 화면 본문. app.py의 render_ai_report()가 선택 선수/프로필
    (require_selected_player/get_player_profile)을 조회한 뒤 이 함수에
    전달한다 (선택 로직은 app.py에 그대로 유지)."""
    st.title("AI 스카우팅 리포트 초안")
    env_settings = st.session_state.get("env_settings")
    simulation_result = st.session_state.get("simulation_result")
    if env_settings is None or simulation_result is None:
        st.warning("먼저 커리어 시뮬레이션 화면에서 시뮬레이션 설정을 생성해 주세요.")
        render_page_actions([
            ("📈 커리어 시뮬레이션으로 이동", "커리어 시뮬레이션", "primary"),
        ])
        return
    render_player_profile_panel(player, profile)
    st.info("현재 리포트는 실제 Gemini API 호출 결과가 아니라, 선택 선수와 시뮬레이션 설정값을 바탕으로 생성한 템플릿 기반 초안입니다.")
    if st.session_state.get("mentor_summary"):
        st.markdown(f'<div class="section-note"><b>멘토링 반영 예정</b><br>{st.session_state["mentor_summary"]}</div>', unsafe_allow_html=True)
    if st.button("리포트 초안 생성", type="primary"):
        entity_type = st.session_state.get("selected_entity_type")
        growth_insight, growth_explanation = get_current_growth_result(player, profile, entity_type)
        sections = get_report_sections(player, profile, env_settings, simulation_result, growth_insight, growth_explanation)
        st.session_state["generated_report_sections"] = sections
        st.session_state["generated_report"] = sections_to_report_text(sections)
        st.session_state["generated_report_text"] = st.session_state["generated_report"]
    sections = st.session_state.get("generated_report_sections")
    report = st.session_state.get("generated_report")
    if not sections:
        return
    for title, body in sections.items():
        st.markdown(f'<div class="report-block"><h3 style="margin-top:0;">{title}</h3>{body}</div>', unsafe_allow_html=True)
    if st.button("이 AI 리포트를 My Scouting Notes에 저장"):
        try:
            entity_type = st.session_state.get("selected_entity_type")
            growth_insight, growth_explanation = get_current_growth_result(player, profile, entity_type)
            ceiling_context = st.session_state.get("ceiling_growth_context")
            context_is_current = is_ceiling_context_current(ceiling_context, player, profile, entity_type)
            payload = build_ai_report_note_payload(
                entity_type=entity_type,
                player=player,
                profile=profile,
                env_settings=env_settings,
                simulation_result=simulation_result,
                growth_insight=growth_insight,
                growth_explanation=growth_explanation,
                ceiling_growth_insight=st.session_state.get("ceiling_growth_insight") if context_is_current else None,
                ceiling_growth_explanation=st.session_state.get("ceiling_growth_explanation") if context_is_current else None,
                ceiling_growth_context=ceiling_context if context_is_current else None,
                report_sections=sections,
                report_text=report,
            )
            saved = insert_scouting_note(
                player_id=player["player_id"],
                profile_id=profile.get("profile_id") if profile else None,
                env_settings=payload["env_settings"],
                simulation_result=payload["simulation_result"],
                report=payload["report"],
            )
            st.success(
                f"AI 리포트가 스카우팅 노트에 저장되었습니다. "
                f"My Scouting Notes에서 다시 확인할 수 있습니다. note_id: {saved['note_id']}"
            )
        except Exception as exc:
            st.error("스카우팅 노트 저장 중 오류가 발생했습니다.")
            with st.expander("개발 확인용 오류"):
                st.exception(exc)

    render_page_actions([
        ("📝 My Scouting Notes에 저장/조회", "내 스카우팅 노트", "primary"),
        ("🔎 새 유망주 검색", "유망주 검색"),
    ])
