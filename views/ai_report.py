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
from gemini_client import get_gemini_sdk_unavailable_reason
from manual_prospect_helpers import manual_player_profile_panel_inputs
from player_coverage import build_data_coverage
from scouting_note_payload import build_ai_report_note_payload, build_manual_note_payload
from services.db import insert_scouting_note
from services.qualitative_evidence import (
    build_player_context_for_gemini,
    build_qualitative_evidence_payload,
    build_quantitative_summary_for_gemini,
    extract_qualitative_signals,
    generate_gemini_advisory,
    is_gemini_available,
    make_fallback_advisory,
    make_fallback_signals,
)
from ui_components import render_page_actions, render_player_profile_panel

# api_error 및 기타 fallback reason은 저장 payload에서 제외한다.
_SAVE_EXCLUDE_FALLBACK_REASONS = ("no_text_input", "no_api_key", "api_error", "parse_failed")

_SDK_NOT_INSTALLED_GUIDANCE = (
    "**Gemini SDK 미설치** — API key는 설정되어 있으나 Gemini SDK가 설치되지 않았습니다. "
    "터미널에서 `pip install -U google-genai` 를 실행한 뒤 앱을 재시작하세요."
)


def is_ceiling_context_current(context, player, profile, entity_type):
    if not isinstance(context, dict):
        return False

    if entity_type in ("manual_note", "manual_prospect"):
        return context.get("entity_type") == entity_type

    if context.get("entity_type") in ("manual_note", "manual_prospect") or not isinstance(player, dict):
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
    lines = ["분석 리포트 초안 (규칙 기반)"]
    for title, content in sections.items():
        lines.extend(["", title, str(content)])
    return "\n".join(lines)


_PROVENANCE_TEXT = (
    "현재 분석은 DB에 저장된 선수 기본 정보, 시장가치/출전 기록, "
    "FM 기반 능력치 및 멘탈 속성 proxy, Growth/Ceiling 규칙 모델을 바탕으로 생성되었습니다. "
    "뉴스 기사, 감독 인터뷰, 스카우팅 텍스트 기반 정성 분석은 아래 섹션에서 직접 입력할 수 있습니다."
)

_PROVENANCE_TABLE = """| 항목 | 출처 |
|---|---|
| 선수 기본 정보 | DB |
| 시장가치/출전 기록 | DB |
| 능력치/멘탈 속성 | FM proxy profile |
| 성장 점수 | rule-based Growth/Ceiling Model |
| 정성 텍스트 근거 | 사용자 직접 입력 (선택) |
| Gemini 분석 | 선택적 사용 (API key 필요) |
"""

_SIGNAL_LABELS = {
    "playing_time_signal": "출전기회 신호",
    "injury_risk_signal": "부상/피로 리스크",
    "coach_trust_signal": "감독 신뢰도",
    "development_signal": "성장/발전 신호",
    "transfer_rumor_signal": "이적 루머",
    "mentality_signal": "멘탈/태도 신호",
}

_SIGNAL_ICONS = {
    "positive": "✅",
    "neutral": "➖",
    "negative": "⚠️",
    "unknown": "❓",
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢",
}

_QUALITATIVE_EXAMPLE_TEXTS = """\
**예시 1 — 경기 관찰 메모:**
> 지난 3경기에서 주전 출전. 볼 받는 움직임이 능동적이며 수비 압박 시 패닉이 없다.
> 패스 연결 성공률이 높고 팀 빌드업에서 핵심 역할을 담당.
> 단, 공중볼 경합에서 신체적 열세가 보임. 부상 기록 없음.

**예시 2 — 스카우팅 리포트:**
> 선수는 현재 임대 계약 중으로 6개월 후 원소속팀 복귀 예정. 감독 신뢰가 두터워 주요 경기에서 꾸준히 기용됨.
> 체력 안정적이나 공격 전환 속도 개선 여지 있음. 이적 루머 미확인.

**예시 3 — 감독 인터뷰 발췌:**
> "그는 훈련 태도가 매우 성실하고 팀 플레이에 헌신적입니다. 아직 발전 여지가 있고 꾸준히 기용할 계획입니다."
"""

_GEMINI_API_KEY_GUIDANCE = (
    "**Gemini 미설정** — 정성 신호 추출 및 보조 추천을 사용하려면 API key를 설정하세요. "
    "`.streamlit/secrets.toml`에 `GEMINI_API_KEY = \"키값\"`을 추가하거나 "
    "환경변수 `GEMINI_API_KEY`(또는 `GOOGLE_API_KEY`)를 설정하면 됩니다. "
    "key가 없어도 DB/FM proxy 기반 분석은 그대로 동작합니다."
)


def _render_qualitative_section(player, profile, growth_insight, growth_explanation, env_settings, simulation_result):
    """정성 텍스트 근거 분석 및 Gemini 보조 추천 UI 섹션."""
    st.subheader("정성 텍스트 근거 분석")
    st.info(
        "선수 관련 기사, 스카우팅 리포트, 감독 인터뷰, 관찰 메모를 붙여넣으면 정성 신호를 구조화해 분석합니다.\n"
        "텍스트를 입력하지 않으면 현재 DB/FM proxy 기반 분석만 사용됩니다."
    )

    gemini_ok = is_gemini_available()
    if not gemini_ok:
        unavail_reason = get_gemini_sdk_unavailable_reason()
        if unavail_reason == "sdk_not_installed":
            st.warning(_SDK_NOT_INSTALLED_GUIDANCE)
        else:
            st.info(_GEMINI_API_KEY_GUIDANCE)

    with st.expander("테스트용 정성 텍스트 입력 예시"):
        st.caption("아래 예시 중 하나를 복사해 텍스트 입력란에 붙여넣어 정성 신호 추출을 테스트해 볼 수 있습니다.")
        st.markdown(_QUALITATIVE_EXAMPLE_TEXTS)

    qualitative_text = st.text_area(
        "정성 텍스트 입력",
        value=st.session_state.get("qualitative_text_input", ""),
        height=160,
        placeholder="선수 관련 기사 본문, 스카우팅 리포트, 감독 인터뷰, 경기 관찰 메모 등을 붙여넣으세요.",
        key="qualitative_text_area_input",
        help="입력하지 않으면 DB/FM proxy/rule-based 분석만 유지됩니다.",
    )

    col1, col2 = st.columns(2)
    with col1:
        run_extraction = st.button(
            "🔍 정성 신호 추출 (Gemini)",
            disabled=not gemini_ok or not qualitative_text.strip(),
            help="Gemini API key가 필요합니다. 텍스트를 입력 후 버튼을 누르세요." if not gemini_ok else "Gemini를 호출해 정성 신호를 추출합니다.",
        )
    with col2:
        run_advisory = st.button(
            "📋 Gemini 보조 추천 생성",
            disabled=not gemini_ok or not st.session_state.get("qualitative_signals"),
            help="먼저 정성 신호 추출을 완료하세요." if not st.session_state.get("qualitative_signals") else "정량 분석 + 정성 신호를 종합한 보조 추천을 생성합니다.",
        )

    if run_extraction:
        st.session_state["qualitative_text_input"] = qualitative_text
        with st.spinner("Gemini가 정성 신호를 추출 중입니다..."):
            entity_type = st.session_state.get("selected_entity_type")
            gi, ge = get_current_growth_result(player, profile, entity_type)
            mentor_summary = st.session_state.get("mentor_summary")
            player_ctx = build_player_context_for_gemini(player, profile, gi, ge, mentor_summary)
            signals, err = extract_qualitative_signals(qualitative_text, player_ctx)
            st.session_state["qualitative_signals"] = signals
            st.session_state.pop("gemini_advisory", None)
        if err:
            st.error(f"Gemini 호출 중 오류가 발생했습니다: {err}")
        else:
            st.success("정성 신호 추출이 완료되었습니다.")

    if run_advisory:
        with st.spinner("Gemini가 보조 추천을 생성 중입니다..."):
            entity_type = st.session_state.get("selected_entity_type")
            gi, ge = get_current_growth_result(player, profile, entity_type)
            mentor_summary = st.session_state.get("mentor_summary")
            player_ctx = build_player_context_for_gemini(player, profile, gi, ge, mentor_summary)
            quant_summary = build_quantitative_summary_for_gemini(gi, ge, env_settings, simulation_result)
            signals = st.session_state.get("qualitative_signals") or {}
            advisory, err = generate_gemini_advisory(player_ctx, quant_summary, signals)
            st.session_state["gemini_advisory"] = advisory
        if err:
            st.error(f"Gemini 보조 추천 생성 중 오류가 발생했습니다: {err}")
        else:
            st.success("Gemini 보조 추천이 생성되었습니다.")

    _render_qualitative_results()
    _render_advisory_results()


def _render_qualitative_results():
    """추출된 정성 신호 결과 표시."""
    signals = st.session_state.get("qualitative_signals")
    if not signals:
        return

    fallback_reason = signals.get("_fallback_reason", "")
    if fallback_reason == "no_text_input":
        st.caption("정성 텍스트 근거가 입력되지 않아 현재는 DB/FM proxy 및 규칙 기반 분석만 표시합니다.")
        return
    if fallback_reason in ("no_api_key",):
        return

    st.markdown("---")
    st.subheader("정성 신호 추출 결과")

    summary = signals.get("qualitative_summary", "")
    if summary:
        st.markdown(f"**정성 요약:** {summary}")

    # Signal badges
    sig_cols = st.columns(3)
    signal_items = list(_SIGNAL_LABELS.items())
    for idx, (key, label) in enumerate(signal_items):
        val = signals.get(key, "unknown")
        icon = _SIGNAL_ICONS.get(val, "❓")
        with sig_cols[idx % 3]:
            st.metric(label, f"{icon} {val}")

    col_a, col_b = st.columns(2)
    with col_a:
        strengths = signals.get("strength_mentions", [])
        if strengths:
            st.markdown("**언급된 강점**")
            for s in strengths:
                st.markdown(f"- {s}")
        weaknesses = signals.get("weakness_mentions", [])
        if weaknesses:
            st.markdown("**언급된 약점**")
            for w in weaknesses:
                st.markdown(f"- {w}")
    with col_b:
        risks = signals.get("risk_mentions", [])
        if risks:
            st.markdown("**언급된 리스크**")
            for r in risks:
                st.markdown(f"- {r}")
        focus = signals.get("recommended_focus", [])
        if focus:
            st.markdown("**추천 보완 방향**")
            for f in focus:
                st.markdown(f"- {f}")

    quotes = signals.get("evidence_quotes", [])
    if quotes:
        st.markdown("**근거 문장 (원문 발췌)**")
        for q in quotes:
            st.markdown(f"> {q}")

    confidence = signals.get("confidence", "low")
    st.caption(f"정성 분석 신뢰도: **{confidence}** (텍스트 근거 충분성 기준 — 높을수록 근거가 풍부함)")

    if fallback_reason == "api_error":
        st.warning("Gemini 호출에 실패했습니다. 기존 DB/FM proxy 분석은 그대로 유지됩니다.")


def _render_advisory_results():
    """Gemini 보조 추천 결과 표시."""
    advisory = st.session_state.get("gemini_advisory")
    if not advisory:
        return

    fallback_reason = advisory.get("_fallback_reason", "")
    if fallback_reason in ("no_api_key", "no_text_input"):
        return

    st.markdown("---")
    st.subheader("Gemini 보조 스카우팅 추천")
    st.caption(
        "⚠️ 이 추천은 DB/FM proxy/rule-based 점수를 대체하지 않습니다. "
        "정량 분석과 정성 텍스트를 종합한 보조 근거 기반 제안입니다."
    )

    summary = advisory.get("advisory_summary", "")
    if summary:
        st.info(summary)

    fit = advisory.get("player_fit_assessment", "")
    if fit:
        st.markdown(f"**역할 적합성 판단:** {fit}")

    sec_a, sec_b = st.columns(2)
    with sec_a:
        train_recs = advisory.get("training_recommendations", [])
        if train_recs:
            st.markdown("**추천 훈련 방향**")
            for t in train_recs:
                st.markdown(f"- {t}")
        career_recs = advisory.get("career_recommendations", [])
        if career_recs:
            st.markdown("**커리어 전략**")
            for c in career_recs:
                st.markdown(f"- {c}")
        risk_mgmt = advisory.get("risk_management", [])
        if risk_mgmt:
            st.markdown("**리스크 관리**")
            for r in risk_mgmt:
                st.markdown(f"- {r}")
    with sec_b:
        mentor_recs = advisory.get("mentor_usage_recommendations", [])
        if mentor_recs:
            st.markdown("**멘토 활용 방향**")
            for m in mentor_recs:
                st.markdown(f"- {m}")
        monitor = advisory.get("what_to_monitor_next", [])
        if monitor:
            st.markdown("**추가 확인 필요**")
            for w in monitor:
                st.markdown(f"- {w}")
        unknown = advisory.get("unsupported_or_unknown", [])
        if unknown:
            st.markdown("**근거 부족 항목**")
            for u in unknown:
                st.markdown(f"- {u}")

    final_comment = advisory.get("final_scouting_comment", "")
    if final_comment:
        st.markdown(f"**최종 스카우팅 코멘트:** {final_comment}")

    adv_confidence = advisory.get("confidence", "low")
    st.caption(f"보조 추천 신뢰도: **{adv_confidence}**")

    if fallback_reason == "api_error":
        st.warning("Gemini 보조 추천 호출에 실패했습니다. 기존 rule-based 분석은 그대로 유지됩니다.")


def render_ai_report_view(player, profile):
    """AI Report 화면 본문. app.py의 render_ai_report()가 선택 선수/프로필
    (require_selected_player/get_player_profile)을 조회한 뒤 이 함수에
    전달한다 (선택 로직은 app.py에 그대로 유지)."""
    st.title("스카우팅 분석 리포트 초안")
    with st.expander("분석 근거 안내"):
        st.caption(_PROVENANCE_TEXT)
        st.markdown(_PROVENANCE_TABLE)
    env_settings = st.session_state.get("env_settings")
    simulation_result = st.session_state.get("simulation_result")
    if env_settings is None or simulation_result is None:
        st.warning("먼저 커리어 시뮬레이션 화면에서 시뮬레이션 설정을 생성해 주세요.")
        render_page_actions([
            ("📈 커리어 시뮬레이션으로 이동", "커리어 시뮬레이션", "primary"),
        ])
        return
    manual_player = st.session_state.get("manual_player") if st.session_state.get("selected_entity_type") == "manual_prospect" else None
    if manual_player:
        panel_player, panel_profile = manual_player_profile_panel_inputs(manual_player)
        render_player_profile_panel(panel_player, panel_profile)
    else:
        render_player_profile_panel(player, profile)
    st.info("현재 리포트는 실제 Gemini API 호출 결과가 아니라, 선택 선수와 시뮬레이션 설정값을 바탕으로 생성한 템플릿 기반 초안입니다.")

    # FM profile 없는 선수에 대한 제한 분석 안내
    if not manual_player:
        coverage = build_data_coverage(player, profile)
        if not coverage["has_fm_profile"]:
            st.warning(
                "이 선수는 Transfermarkt 기본 데이터만 연결되어 있어 "
                "FM 능력치, 멘탈 지표, style_vector 기반 판단은 제외된 제한 분석입니다. "
                "정밀 분석을 위해서는 FM profile 매칭 또는 직접 입력 유망주 기능을 사용하세요."
            )

    if st.session_state.get("mentor_summary"):
        st.markdown(f'<div class="section-note"><b>멘토링 반영 예정</b><br>{st.session_state["mentor_summary"]}</div>', unsafe_allow_html=True)

    # --- 정성 텍스트 근거 분석 섹션 ---
    _render_qualitative_section(player, profile, None, None, env_settings, simulation_result)

    st.markdown("---")

    if st.button("리포트 초안 생성", type="primary"):
        entity_type = st.session_state.get("selected_entity_type")
        growth_insight, growth_explanation = get_current_growth_result(player, profile, entity_type)
        sections = get_report_sections(player, profile, env_settings, simulation_result, growth_insight, growth_explanation)

        # 정성 신호가 있으면 리포트 섹션에 보조 근거 추가
        sections = _augment_sections_with_qualitative(sections)

        st.session_state["generated_report_sections"] = sections
        st.session_state["generated_report"] = sections_to_report_text(sections)
        st.session_state["generated_report_text"] = st.session_state["generated_report"]
    sections = st.session_state.get("generated_report_sections")
    report = st.session_state.get("generated_report")
    if not sections:
        return
    for title, body in sections.items():
        st.markdown(f'<div class="report-block"><h3 style="margin-top:0;">{title}</h3>{body}</div>', unsafe_allow_html=True)
    if st.button("이 분석 리포트를 My Scouting Notes에 저장"):
        try:
            entity_type = st.session_state.get("selected_entity_type")
            growth_insight, growth_explanation = get_current_growth_result(player, profile, entity_type)
            ceiling_context = st.session_state.get("ceiling_growth_context")
            context_is_current = is_ceiling_context_current(ceiling_context, player, profile, entity_type)

            # 정성 텍스트 근거와 Gemini 보조 추천을 payload에 포함
            qualitative_text = st.session_state.get("qualitative_text_input", "")
            raw_signals = st.session_state.get("qualitative_signals")
            qual_evidence = None
            if raw_signals and raw_signals.get("_fallback_reason") not in _SAVE_EXCLUDE_FALLBACK_REASONS:
                qual_evidence = build_qualitative_evidence_payload(qualitative_text, raw_signals)
            raw_advisory = st.session_state.get("gemini_advisory")
            adv_payload = None
            if raw_advisory and raw_advisory.get("_fallback_reason") not in _SAVE_EXCLUDE_FALLBACK_REASONS:
                adv_payload = {k: v for k, v in raw_advisory.items() if not k.startswith("_")}

            if entity_type == "manual_prospect":
                payload = build_manual_note_payload(
                    entity_type="manual_prospect",
                    player=st.session_state.get("manual_player"),
                    profile=None,
                    env_settings=env_settings,
                    simulation_result=simulation_result,
                    growth_insight=growth_insight,
                    growth_explanation=growth_explanation,
                    ceiling_growth_insight=st.session_state.get("ceiling_growth_insight") if context_is_current else None,
                    ceiling_growth_explanation=st.session_state.get("ceiling_growth_explanation") if context_is_current else None,
                    ceiling_growth_context=ceiling_context if context_is_current else None,
                    report_sections=sections,
                    report_text=report,
                    qualitative_evidence=qual_evidence,
                    gemini_advisory=adv_payload,
                )
                saved = insert_scouting_note(
                    player_id=None,
                    profile_id=None,
                    env_settings=payload["env_settings"],
                    simulation_result=payload["simulation_result"],
                    report=payload["report"],
                )
            else:
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
                    qualitative_evidence=qual_evidence,
                    gemini_advisory=adv_payload,
                )
                saved = insert_scouting_note(
                    player_id=player["player_id"],
                    profile_id=profile.get("profile_id") if profile else None,
                    env_settings=payload["env_settings"],
                    simulation_result=payload["simulation_result"],
                    report=payload["report"],
                )
            st.success(
                f"분석 리포트(규칙 기반)가 스카우팅 노트에 저장되었습니다. "
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


def _augment_sections_with_qualitative(sections):
    """정성 신호와 Gemini 보조 추천이 있으면 기존 리포트 섹션에 보조 근거를 추가한다.
    기존 점수와 리포트 구조는 변경하지 않는다.
    """
    signals = st.session_state.get("qualitative_signals")
    advisory = st.session_state.get("gemini_advisory")

    has_signals = (
        isinstance(signals, dict)
        and signals.get("_fallback_reason") not in ("no_text_input", "no_api_key", "api_error", "parse_failed")
        and signals.get("qualitative_summary")
    )
    has_advisory = (
        isinstance(advisory, dict)
        and advisory.get("_fallback_reason") not in ("no_api_key", "no_text_input", "api_error", "parse_failed")
        and advisory.get("advisory_summary")
    )

    augmented = dict(sections)

    if has_signals:
        sig_lines = [f"**정성 텍스트 근거** (사용자 입력 텍스트 기반, 점수 계산과 무관한 보조 근거)"]
        summary = signals.get("qualitative_summary", "")
        if summary:
            sig_lines.append(f"정성 요약: {summary}")
        for key, label in _SIGNAL_LABELS.items():
            val = signals.get(key, "unknown")
            if val != "unknown":
                icon = _SIGNAL_ICONS.get(val, "")
                sig_lines.append(f"{label}: {icon} {val}")
        weakness_mentions = signals.get("weakness_mentions", [])
        if weakness_mentions:
            sig_lines.append("언급된 약점: " + ", ".join(weakness_mentions))
        injury_signal = signals.get("injury_risk_signal", "unknown")
        if injury_signal == "negative":
            sig_lines.append("⚠️ 텍스트에서 부상/피로 우려가 언급됨 — 리스크 경고 보강")
        coach_signal = signals.get("coach_trust_signal", "unknown")
        if coach_signal == "positive":
            sig_lines.append("✅ 텍스트에서 감독 신뢰/기용 의지가 긍정적으로 언급됨")
        confidence = signals.get("confidence", "low")
        sig_lines.append(f"정성 분석 신뢰도: {confidence}")
        augmented["정성 텍스트 근거"] = "<br>".join(sig_lines)

    if has_advisory:
        adv_lines = [
            "**Gemini 보조 스카우팅 추천** (정량 점수를 대체하지 않는 근거 기반 제안)",
        ]
        adv_summary = advisory.get("advisory_summary", "")
        if adv_summary:
            adv_lines.append(adv_summary)
        train_recs = advisory.get("training_recommendations", [])
        if train_recs:
            adv_lines.append("추천 훈련: " + " / ".join(train_recs))
        career_recs = advisory.get("career_recommendations", [])
        if career_recs:
            adv_lines.append("커리어 제안: " + " / ".join(career_recs))
        unknown_items = advisory.get("unsupported_or_unknown", [])
        if unknown_items:
            adv_lines.append("근거 부족 항목: " + ", ".join(unknown_items))
        final_comment = advisory.get("final_scouting_comment", "")
        if final_comment:
            adv_lines.append(f"최종 스카우팅 코멘트: {final_comment}")
        adv_confidence = advisory.get("confidence", "low")
        adv_lines.append(f"보조 추천 신뢰도: {adv_confidence}")
        augmented["Gemini 보조 스카우팅 추천"] = "<br>".join(adv_lines)

    return augmented
