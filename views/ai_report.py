import re as _re

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
from components.badges import source_badge_html
from components.cards import game_alert_html, signal_grid_html, stat_grid_html
from components.layout import render_game_page_title
from gemini_client import DEFAULT_GEMINI_MODEL, get_gemini_sdk_unavailable_reason
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
)
from ui_components import render_page_actions, render_player_profile_panel

_SAVE_EXCLUDE_FALLBACK_REASONS = ("no_text_input", "no_api_key", "api_error", "parse_failed")

_SDK_NOT_INSTALLED_GUIDANCE = (
    "**Gemini SDK 미설치** - API key는 설정되어 있으나 Gemini SDK가 설치되지 않았습니다. "
    "터미널에서 `pip install -U google-genai` 를 실행한 뒤 앱을 재시작하세요."
)

_GEMINI_API_KEY_GUIDANCE = (
    "**Gemini 미설정** - 정성 신호 추출 및 보조 추천을 사용하려면 API key를 설정하세요. "
    "key가 없어도 저장된 선수 데이터 기반 분석은 그대로 동작합니다."
)

_PROVENANCE_TEXT = (
    "현재 리포트는 선수 기본 정보, 시장가치/출전 기록, 능력치 프로필, Growth/Ceiling 규칙 모델을 바탕으로 생성됩니다. "
    "Gemini는 사용자가 입력한 정성 텍스트를 구조화하고 보조 추천을 만드는 역할만 하며 점수를 계산하지 않습니다."
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

_SIGNAL_LABELS = {
    "playing_time_signal": "출전기회 신호",
    "injury_risk_signal": "부상/피로 리스크",
    "coach_trust_signal": "감독 신뢰도",
    "development_signal": "성장/발전 신호",
    "transfer_rumor_signal": "이적 루머",
    "mentality_signal": "멘탈/태도 신호",
}

# Gemini advisory 항목의 영문 signal 키 → 사용자 친화적 한국어 레이블
_SIGNAL_KO_FULL = {
    "playing_time_signal": "출전 시간 및 경기 내용",
    "injury_risk_signal": "부상 이력 및 발생 가능성",
    "coach_trust_signal": "감독 신뢰도 및 기용 계획",
    "development_signal": "성장 속도 및 능력치 변화",
    "transfer_rumor_signal": "이적 관련 동향",
    "mentality_signal": "멘탈 및 태도",
    # 공백/하이픈 변형도 함께 처리
    "playing time signal": "출전 시간 및 경기 내용",
    "injury risk signal": "부상 이력 및 발생 가능성",
    "coach trust signal": "감독 신뢰도 및 기용 계획",
    "development signal": "성장 속도 및 능력치 변화",
    "transfer rumor signal": "이적 관련 동향",
    "mentality signal": "멘탈 및 태도",
}


def _clean_advisory_item(item: str) -> str:
    """Gemini가 생성한 advisory 항목 문자열에서 영문 technical 표현을 한국어로 바꾼다.

    처리 우선순위:
    1. "signal_key: unknown" → "한국어 레이블: 확인 필요"
    2. "English Signal Name (한국어 설명)" → 괄호 안 한국어만 추출
    3. 영문 signal 키 단어를 한국어 레이블로 치환
    """
    if not isinstance(item, str):
        return str(item)

    # 1. "key_name: unknown" 패턴
    for key, label in _SIGNAL_KO_FULL.items():
        if _re.search(_re.escape(key) + r'\s*:\s*unknown', item, _re.IGNORECASE):
            return f"{label}: 확인 필요"

    # 2. "English (...한국어...)" — 괄호 안이 한국어이면 그것만 반환
    m = _re.search(r'\(([^)]+)\)', item)
    if m:
        inner = m.group(1).strip()
        if any(0xAC00 <= ord(c) <= 0xD7A3 for c in inner):
            return inner

    # 3. 영문 signal 키 단어 치환
    result = item
    for key, label in _SIGNAL_KO_FULL.items():
        result = _re.sub(_re.escape(key), label, result, flags=_re.IGNORECASE)
    # "Signal" 단어 단독 잔존 제거
    result = _re.sub(r'\bsignal\b\s*', '', result, flags=_re.IGNORECASE).strip()
    return result

_SIGNAL_ICONS = {
    "positive": "+",
    "neutral": "=",
    "negative": "!",
    "unknown": "?",
    "high": "HIGH",
    "medium": "MID",
    "low": "LOW",
}

_QUALITATIVE_EXAMPLE_TEXTS = """\
**예시 1 - 경기 관찰 메모:**
> 지난 3경기에서 주전 출전. 볼 받는 움직임이 능동적이며 수비 압박 시 침착함.
> 패스 연결 성공률이 높고 팀 빌드업에서 핵심 역할을 담당.
> 단, 공중볼 경합에서 신체적 열세가 보임. 부상 기록 없음.

**예시 2 - 스카우팅 리포트:**
> 선수는 현재 임대 계약 중으로 6개월 후 원소속팀 복귀 예정. 감독 신뢰가 두터워 주요 경기에서 꾸준히 기용됨.
> 체력은 안정적이나 공격 전환 속도 개선 여지 있음. 이적 루머는 확인되지 않음.
"""


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
    return st.session_state.get("growth_insight"), st.session_state.get("growth_explanation")


def _badge(label, status="ok"):
    return source_badge_html(label, status)


def _gemini_failure_notice(raw_error=None, context="qualitative"):
    raw_text = str(raw_error or "")
    lowered = raw_text.lower()
    if any(token in lowered for token in ("quota", "resource_exhausted", "429", "exceeded")):
        return (
            "Gemini 사용 한도 안내",
            "정성 텍스트 보조 분석을 실행하지 못했지만 기본 분석은 정상 사용 가능합니다. 호출 한도가 회복된 뒤 다시 시도해 주세요.",
        )
    if any(token in lowered for token in ("503", "unavailable", "high demand", "temporarily")):
        return (
            "정성 텍스트 보조 분석 지연",
            "현재 모델 사용량이 많아 정성 텍스트 보조 분석을 실행하지 못했지만 기본 분석은 정상 사용 가능합니다. 잠시 후 다시 시도해 주세요.",
        )
    return (
        "정성 텍스트 보조 분석 안내",
        "정성 텍스트 보조 분석을 실행하지 못했지만 기본 분석은 정상 사용 가능합니다.",
    )


def _render_gemini_failure(raw_error=None, context="qualitative"):
    title, body = _gemini_failure_notice(raw_error, context)
    st.warning(f"{title}: {body}")
    if raw_error:
        with st.expander("상세 오류 보기"):
            st.text(str(raw_error))


def _signal_text(value):
    return {
        "positive": "긍정 신호",
        "neutral": "중립/확인 필요",
        "negative": "주의 신호",
        "high": "높음",
        "medium": "보통",
        "low": "낮음",
        "unknown": "언급 없음",
    }.get(value, str(value or "언급 없음"))


def _qualitative_signal_summary(signals):
    positive = []
    caution = []
    neutral = []
    for key, label in _SIGNAL_LABELS.items():
        value = signals.get(key, "unknown") if isinstance(signals, dict) else "unknown"
        text = f"{label}: {_signal_text(value)}"
        if value == "positive" or (key == "transfer_rumor_signal" and value == "low"):
            positive.append(text)
        elif value == "negative" or (key == "transfer_rumor_signal" and value in ("high", "medium")):
            caution.append(text)
        elif value != "unknown":
            neutral.append(text)
    return positive, caution, neutral


_QUALITATIVE_APPLICATIONS = (
    ("멘탈리티 해석", "훈련 태도, 팀 충성도, 압박 상황 판단, 경기 집중도 같은 메모를 능력치 기반 멘탈 지표의 보조 근거로 봅니다."),
    ("리스크 관리", "부상/피로, 적응 부담, 이적 루머, 출전 불안정 신호를 주의 항목으로 분리합니다."),
    ("추천 훈련 방향", "반복해서 언급된 약점과 추천 보완 방향을 훈련 우선순위 설명에 연결합니다."),
    ("Career Simulation 해석", "점수는 바꾸지 않고, 같은 시나리오를 해석할 때 위험/기회 코멘트로 참고합니다."),
    ("Evidence & Advisory Report 최종 코멘트", "리포트 초안의 정성 근거 및 최종 스카우팅 코멘트에 보조 자료로 반영됩니다."),
)


def get_report_sections(player, profile, env_settings, simulation_result, growth_insight=None, growth_explanation=None):
    attributes = parse_json_field(profile.get("attributes_jsonb")) if profile else {}
    mentality = parse_json_field(profile.get("mentality_jsonb")) if profile else {}
    basis = mentality.get("basis", {}) if isinstance(mentality, dict) else {}
    strength_names = attr_names(top_attributes(attributes, limit=3)) or "주요 강점 데이터 없음"
    weakness_names = attr_names(top_attributes(attributes, limit=2, reverse=False)) or "보완 데이터 없음"
    mental_names = attr_names(top_attributes(basis, MENTALITY_KEYS, 2, True)) or "멘탈 강점 데이터 없음"
    mental_weak = attr_names(top_attributes(basis, MENTALITY_KEYS, 2, False)) or "멘탈 보완 데이터 없음"
    age = profile.get("age") if isinstance(profile, dict) else None
    player_name = player.get("name") or "선택 선수"
    position = player.get("position") or "포지션 정보 없음"
    club = player.get("current_club_name") or "소속팀 정보 없음"
    proto_score = safe_float(simulation_result.get("prototype_growth_score"), None)
    growth_text = f"{proto_score:.1f}" if proto_score is not None else "-"
    success_text = format_percent(simulation_result.get("prototype_success_probability"))
    injury_text = format_percent(simulation_result.get("prototype_injury_risk"))
    mentor_summary = st.session_state.get("mentor_summary")
    mentor_note = mentor_summary or "선택된 멘토가 없어 이번 초안에는 멘토링 가이드가 반영되지 않았습니다."

    sections = {
        "1. 선수 요약": (
            f'{_badge("DB")} {player_name}은 나이 {age if age is not None else "-"}, {position}, {club} 소속으로 확인됩니다. '
            f'{_badge("능력치 기반", "warning")} 저장된 능력치 프로필이 있는 경우 능력치와 멘탈/성향 항목을 함께 참고합니다.'
        ),
        "2. 데이터 기반 강점": (
            f"능력치 기반 강점: {strength_names}. 멘탈/성향 강점: {mental_names}. "
            "이 내용은 저장된 데이터에서 확인되는 항목만 요약합니다."
        ),
        "3. 데이터 기반 보완점": (
            f"능력치 기반 보완 항목: {weakness_names}. 멘탈/성향 보완 항목: {mental_weak}. "
            f"{position_training_hint(position, weakness_names)}"
        ),
        "4. 성장 시나리오 해석": (
            f'{_badge("데이터 기반 분석", "neutral")} {simulation_comment(env_settings, simulation_result)} '
            f"시나리오 결과: 성장 점수 {growth_text}, 성공 가능성 {success_text}, 부상 리스크 {injury_text}."
        ),
        "5. 멘토 참고사항": f'{_badge("멘토 참고", "neutral")} {mentor_note}',
        "6. 근거 부족 / 주의사항": (
            "Gemini가 포함된 경우에도 점수 계산은 Growth/Ceiling 모델이 수행합니다. "
            "정성 텍스트가 없으면 멘탈/태도/리스크 보조 근거는 반영되지 않습니다."
        ),
    }

    if growth_insight and growth_explanation:
        real_growth_score = growth_insight.get("growth_score")
        score_text_val = f"{real_growth_score:.1f} / 100" if real_growth_score is not None else "산정 불가"
        sections["Growth Model Insight"] = (
            f'{_badge("Growth Model", "ok")} Growth Score: {score_text_val}<br>'
            f"{growth_explanation.get('summary', '')}<br>"
            f"<b>산정 근거:</b> {growth_explanation.get('score_reason', '')}<br>"
            f"<b>강점:</b> {' / '.join(growth_explanation.get('strengths', []))}<br>"
            f"<b>리스크:</b> {' / '.join(growth_explanation.get('risks', []))}<br>"
            f"<b>추천 성장 방향:</b> {' / '.join(growth_explanation.get('recommendations', []))}"
        )
        ceiling_explanation = growth_explanation.get("ceiling_explanation")
        if ceiling_explanation:
            final_score = ceiling_explanation.get("final_growth_score")
            final_text = f"{final_score:.1f} / 100" if final_score is not None else "산정 불가"
            sections["Ceiling Scenario Insight"] = (
                f'{_badge("Ceiling Scenario", "ok")} '
                f"현재 환경의 기회와 위험을 반영한 종합 성장 전망은 {final_text}입니다.<br>"
                f"<b>추천 훈련 방향:</b> {' / '.join(ceiling_explanation.get('training_directions', []))}<br>"
                f"<b>기대 장점:</b> {' / '.join(ceiling_explanation.get('expected_benefits', []))}<br>"
                f"<b>리스크 경고:</b> {' / '.join(ceiling_explanation.get('risk_warnings', []))}<br>"
                f"<b>추천 커리어 전략:</b> {' / '.join(ceiling_explanation.get('career_strategy', []))}"
            )
    return sections


def sections_to_report_text(sections):
    lines = ["분석 리포트 초안 (규칙 기반)"]
    for title, content in sections.items():
        lines.extend(["", title, str(content)])
    return "\n".join(lines)


def _render_qualitative_section(player, profile, growth_insight, growth_explanation, env_settings, simulation_result):
    st.markdown(
        """
            <div class="game-panel game-evidence-input-panel">
                <div class="kicker">Qualitative Evidence Input Panel</div>
            <h3>정성 메모 입력</h3>
            <div class="game-muted">정성 메모는 Growth Score를 직접 변경하지 않습니다. 대신 멘탈리티 해석, 리스크 관리, 추천 훈련 방향, 최종 스카우팅 코멘트에 보조 근거로 반영됩니다.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.subheader("정성 텍스트 근거 분석")
    st.info(
        "선수 관련 기사, 스카우팅 리포트, 감독 인터뷰, 경기 관찰 메모를 붙여넣으면 멘탈/태도/리스크 보조 신호를 구조화합니다. "
        "Growth/Ceiling 점수와 공식은 그대로 유지되고, 텍스트를 입력하지 않으면 저장된 선수 데이터 기반 분석만 사용합니다."
    )

    gemini_ok = is_gemini_available()
    if not gemini_ok:
        unavail_reason = get_gemini_sdk_unavailable_reason()
        if unavail_reason == "sdk_not_installed":
            st.warning(_SDK_NOT_INSTALLED_GUIDANCE)
        else:
            st.info(_GEMINI_API_KEY_GUIDANCE)

    with st.expander("테스트용 정성 텍스트 입력 예시"):
        st.markdown(_QUALITATIVE_EXAMPLE_TEXTS)

    qualitative_text = st.text_area(
        "정성 텍스트 입력",
        value=st.session_state.get("qualitative_text_input", ""),
        height=160,
        placeholder="선수 관련 기사 본문, 스카우팅 리포트, 감독 인터뷰, 경기 관찰 메모 등을 붙여넣으세요.",
        key="qualitative_text_area_input",
        help="입력하지 않으면 저장된 데이터 기반 성장 모델 분석만 유지됩니다.",
    )

    col1, col2 = st.columns(2)
    with col1:
        run_extraction = st.button(
            "선택 호출: 정성 신호 추출",
            disabled=not gemini_ok or not qualitative_text.strip(),
            help=f"버튼을 누를 때만 {DEFAULT_GEMINI_MODEL} 모델을 1회 호출합니다.",
        )
    with col2:
        run_advisory = st.button(
            "선택 호출: 보조 추천 생성",
            disabled=not gemini_ok or not st.session_state.get("qualitative_signals"),
            help=f"먼저 정성 신호 추출을 완료하세요. 버튼을 누를 때만 {DEFAULT_GEMINI_MODEL} 모델을 1회 호출합니다.",
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
            _render_gemini_failure(err, "qualitative")
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
            _render_gemini_failure(err, "advisory")
        else:
            st.success("Gemini 보조 추천이 생성되었습니다.")

    _render_qualitative_results()
    _render_advisory_results()


def _render_qualitative_results():
    signals = st.session_state.get("qualitative_signals")
    qualitative_text = st.session_state.get("qualitative_text_input", "")
    if not signals:
        if qualitative_text and qualitative_text.strip():
            st.info("정성 메모가 입력되어 있습니다. '선택 호출: 정성 신호 추출'을 실행하면 멘탈리티 보조 신호와 리스크/훈련 참고 항목으로 정리됩니다.")
        else:
            st.caption("정성 메모 없음 — 현재는 저장된 선수 데이터 기반 분석만 사용 중입니다.")
        return
    fallback_reason = signals.get("_fallback_reason", "")
    if fallback_reason == "no_text_input":
        st.caption("정성 메모 없음 — 현재는 저장된 선수 데이터 기반 분석만 사용 중입니다.")
        return
    if fallback_reason in ("no_api_key",):
        st.info("정성 텍스트 보조 분석을 실행하지 못했지만 기본 분석은 정상 사용 가능합니다.")
        return
    if fallback_reason == "api_error":
        st.warning("정성 텍스트 보조 분석을 실행하지 못했지만 기본 분석은 정상 사용 가능합니다.")
        return

    st.markdown(
        """
        <div class="game-panel game-report-section">
            <div class="kicker">Qualitative Support Signals</div>
            <h3>정성 메모 반영 결과</h3>
            <div class="game-muted">이 섹션은 점수 계산이 아니라 해석과 코멘트에 쓰이는 보조 근거입니다.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.subheader("멘탈리티 보조 신호")
    summary = signals.get("qualitative_summary", "")
    if summary:
        st.markdown(f"**정성 요약:** {summary}")

    positive, caution, neutral = _qualitative_signal_summary(signals)
    sig_cols = st.columns(3)
    with sig_cols[0]:
        st.markdown("**긍정 신호**")
        for item in positive or ["명확한 긍정 신호 없음"]:
            st.markdown(f"- {item}")
    with sig_cols[1]:
        st.markdown("**주의 신호**")
        for item in caution or ["명확한 주의 신호 없음"]:
            st.markdown(f"- {item}")
    with sig_cols[2]:
        st.markdown("**중립/확인 필요**")
        for item in neutral or ["추가 확인 필요 항목 없음"]:
            st.markdown(f"- {item}")

    col_a, col_b = st.columns(2)
    with col_a:
        for title, key in (("언급된 강점", "strength_mentions"), ("언급된 약점", "weakness_mentions")):
            items = signals.get(key, [])
            if items:
                st.markdown(f"**{title}**")
                for item in items:
                    st.markdown(f"- {item}")
    with col_b:
        for title, key in (("언급된 리스크", "risk_mentions"), ("추천 보완 방향", "recommended_focus")):
            items = signals.get(key, [])
            if items:
                st.markdown(f"**{title}**")
                for item in items:
                    st.markdown(f"- {item}")

    quotes = signals.get("evidence_quotes", [])
    if quotes:
        st.markdown("**근거 문장 (원문 발췌)**")
        for quote in quotes:
            st.markdown(f"> {quote}")

    st.markdown("**어디에 반영되나요?**")
    for title, body in _QUALITATIVE_APPLICATIONS:
        st.markdown(f"- **{title}**: {body}")

    st.caption(f"정성 분석 신뢰도: **{signals.get('confidence', 'low')}**")


def _render_advisory_results():
    advisory = st.session_state.get("gemini_advisory")
    if not advisory:
        return
    fallback_reason = advisory.get("_fallback_reason", "")
    if fallback_reason in ("no_api_key", "no_text_input"):
        return

    st.markdown(
        """
        <div class="game-panel game-report-section">
            <div class="kicker">Gemini Advisory Panel</div>
            <h3>Evidence-backed advisory</h3>
            <div class="game-muted">Advisory output is separated from rule-based scoring.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.subheader("Gemini 보조 스카우팅 추천")
    st.caption("이 추천은 Growth/Ceiling 점수를 대체하지 않는 보조 근거 기반 제안입니다.")

    if advisory.get("advisory_summary"):
        st.markdown(f"**요약:** {advisory['advisory_summary']}")
    if advisory.get("player_fit_assessment"):
        st.markdown(f"**역할 적합성 판단:** {advisory['player_fit_assessment']}")

    sec_a, sec_b = st.columns(2)
    with sec_a:
        for title, key in (("추천 훈련 방향", "training_recommendations"), ("커리어 전략", "career_recommendations"), ("리스크 관리", "risk_management")):
            items = advisory.get(key, [])
            if items:
                st.markdown(f"**{title}**")
                for item in items:
                    st.markdown(f"- {item}")
    with sec_b:
        for title, key in (
            ("멘토 활용 방향", "mentor_usage_recommendations"),
            ("추가 확인 필요", "what_to_monitor_next"),
            ("텍스트에서 확인되지 않은 항목", "unsupported_or_unknown"),
        ):
            raw_items = advisory.get(key, [])
            if not raw_items:
                continue
            cleaned = [_clean_advisory_item(i) for i in raw_items]
            if key == "unsupported_or_unknown":
                # 모든 항목이 "확인 필요"로만 이루어진 경우 → 한 줄 안내로 대체
                only_unknown = all("확인 필요" in c for c in cleaned)
                if only_unknown:
                    labels = [c.split(":")[0].strip() for c in cleaned if ":" in c]
                    if labels:
                        st.markdown(f"**{title}**")
                        st.caption(
                            f"입력된 텍스트에서 확인하지 못한 항목: {', '.join(labels)}. "
                            "정성 메모를 보완하면 분석 정확도를 높일 수 있습니다."
                        )
                    continue
            st.markdown(f"**{title}**")
            for item in cleaned:
                st.markdown(f"- {item}")

    if advisory.get("final_scouting_comment"):
        st.markdown(f"**최종 스카우팅 코멘트:** {advisory['final_scouting_comment']}")
    st.caption(f"보조 추천 신뢰도: **{advisory.get('confidence', 'low')}**")
    if fallback_reason == "api_error":
        st.warning("Gemini 보조 추천을 완료하지 못했습니다. 기존 rule-based 분석은 그대로 유지됩니다.")


def _augment_sections_with_qualitative(sections):
    signals = st.session_state.get("qualitative_signals")
    advisory = st.session_state.get("gemini_advisory")
    has_signals = isinstance(signals, dict) and signals.get("_fallback_reason") not in _SAVE_EXCLUDE_FALLBACK_REASONS
    has_advisory = isinstance(advisory, dict) and advisory.get("_fallback_reason") not in _SAVE_EXCLUDE_FALLBACK_REASONS
    augmented = dict(sections)

    if has_signals:
        sig_lines = ["**정성 텍스트 근거** (사용자 입력 텍스트 기반, 점수 계산과 무관한 보조 근거)"]
        if signals.get("qualitative_summary"):
            sig_lines.append(f"정성 요약: {signals['qualitative_summary']}")
        positive, caution, neutral = _qualitative_signal_summary(signals)
        if positive:
            sig_lines.append("긍정 신호: " + " / ".join(positive))
        if caution:
            sig_lines.append("주의 신호: " + " / ".join(caution))
        if neutral:
            sig_lines.append("확인 필요: " + " / ".join(neutral))
        for key, label in _SIGNAL_LABELS.items():
            val = signals.get(key, "unknown")
            if val != "unknown":
                sig_lines.append(f"{label}: {_SIGNAL_ICONS.get(val, '?')} {val}")
        for key, label in (("risk_mentions", "언급된 리스크"), ("recommended_focus", "추천 보완 방향")):
            items = signals.get(key, [])
            if items:
                sig_lines.append(f"{label}: " + ", ".join(items))
        sig_lines.append("반영 위치: " + " / ".join(title for title, _ in _QUALITATIVE_APPLICATIONS))
        sig_lines.append(f"정성 분석 신뢰도: {signals.get('confidence', 'low')}")
        augmented["정성 텍스트 근거"] = "<br>".join(sig_lines)

    if has_advisory:
        adv_lines = ["**Gemini 보조 스카우팅 추천** (정량 점수를 대체하지 않는 근거 기반 제안)"]
        if advisory.get("advisory_summary"):
            adv_lines.append(advisory["advisory_summary"])
        for key, label in (("training_recommendations", "추천 훈련"), ("career_recommendations", "커리어 제안"), ("unsupported_or_unknown", "근거 부족 항목")):
            items = advisory.get(key, [])
            if items:
                adv_lines.append(f"{label}: " + " / ".join(items))
        if advisory.get("final_scouting_comment"):
            adv_lines.append(f"최종 스카우팅 코멘트: {advisory['final_scouting_comment']}")
        adv_lines.append(f"보조 추천 신뢰도: {advisory.get('confidence', 'low')}")
        augmented["Gemini 보조 스카우팅 추천"] = "<br>".join(adv_lines)

    return augmented


def render_ai_report_view(player, profile):
    render_game_page_title(
        "Evidence & Advisory Report",
        "성장 모델 기반 스카우팅 리포트 초안과 정성 텍스트/Gemini 보조 추천을 분리해 확인합니다.",
        kicker="Scouting Report Room",
    )
    with st.expander("분석 근거 안내"):
        st.caption(_PROVENANCE_TEXT)
        st.markdown(_PROVENANCE_TABLE)

    env_settings = st.session_state.get("env_settings")
    simulation_result = st.session_state.get("simulation_result")
    if env_settings is None or simulation_result is None:
        st.warning("먼저 커리어 시뮬레이션 화면에서 시뮬레이션 설정을 생성해 주세요.")
        render_page_actions([("커리어 시뮬레이션으로 이동", "커리어 시뮬레이션", "primary")])
        return

    manual_player = st.session_state.get("manual_player") if st.session_state.get("selected_entity_type") == "manual_prospect" else None
    if manual_player:
        panel_player, panel_profile = manual_player_profile_panel_inputs(manual_player)
        render_player_profile_panel(panel_player, panel_profile, entity_type="manual_prospect")
    else:
        render_player_profile_panel(player, profile, entity_type=st.session_state.get("selected_entity_type"))

    st.markdown(
        game_alert_html(
            "분석 리포트 생성 안내",
            "점수는 Growth/Ceiling 모델이 계산합니다. Gemini는 사용자가 입력한 정성 텍스트를 해석하고 보조 코멘트를 제공하는 역할만 합니다.",
            "info",
        ),
        unsafe_allow_html=True,
    )

    entity_type = st.session_state.get("selected_entity_type")
    growth_insight, growth_explanation = get_current_growth_result(player, profile, entity_type)
    growth_score = growth_insight.get("growth_score") if isinstance(growth_insight, dict) else None
    ceiling_model = growth_insight.get("ceiling_model") if isinstance(growth_insight, dict) else {}
    final_score = ceiling_model.get("final_growth_score") if isinstance(ceiling_model, dict) else None
    st.markdown(
        '<div class="game-panel game-report-room">'
        '<div class="kicker">리포트 준비 현황</div>'
        '<h3>리포트 생성 준비</h3>'
        + stat_grid_html(
            [
                ("성장 점수", "-" if growth_score is None else f"{growth_score:.1f}"),
                ("최종 성장 점수", "-" if final_score is None else f"{final_score:.1f}"),
                ("리포트 모드", "성장 모델 기반"),
                ("Gemini 역할", "정성 보조 추천"),
            ]
        )
        + '<div class="game-card-row">'
        + source_badge_html("성장 모델 기반 초안", "ok")
        + source_badge_html("Gemini 점수 계산 금지", "warning")
        + "</div></div>",
        unsafe_allow_html=True,
    )

    if not manual_player:
        coverage = build_data_coverage(player, profile)
        if not coverage["has_fm_profile"]:
            st.warning(
                "이 선수는 기본 선수 정보만 연결되어 있어 능력치, 멘탈/성향, 멘토 비교 판단은 제외된 제한 분석입니다. "
                "정밀 분석을 위해서는 직접 입력 유망주 기능을 사용하세요."
            )

    if st.session_state.get("mentor_summary"):
        st.markdown(f'<div class="section-note"><b>멘토링 반영 예정</b><br>{st.session_state["mentor_summary"]}</div>', unsafe_allow_html=True)

    _render_qualitative_section(player, profile, growth_insight, growth_explanation, env_settings, simulation_result)
    st.markdown("---")

    if st.button("리포트 초안 생성", type="primary"):
        growth_insight, growth_explanation = get_current_growth_result(player, profile, entity_type)
        sections = get_report_sections(player, profile, env_settings, simulation_result, growth_insight, growth_explanation)
        sections = _augment_sections_with_qualitative(sections)
        st.session_state["generated_report_sections"] = sections
        st.session_state["generated_report"] = sections_to_report_text(sections)

    sections = st.session_state.get("generated_report_sections")
    report = st.session_state.get("generated_report")
    if not sections:
        return

    st.markdown(
        """
        <div class="game-panel game-report-section">
            <div class="kicker">Final Report Preview Panel</div>
            <h3>Generated scouting report draft</h3>
            <div class="game-muted">규칙 기반 분석, 정성 근거, Gemini 보조 추천을 분리해 표시합니다.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for title, body in sections.items():
        st.markdown(f'<div class="report-block game-report-section"><h3 style="margin-top:0;">{title}</h3>{body}</div>', unsafe_allow_html=True)

    if st.button("이 분석 리포트를 My Scouting Notes에 저장"):
        try:
            growth_insight, growth_explanation = get_current_growth_result(player, profile, entity_type)
            ceiling_context = st.session_state.get("ceiling_growth_context")
            context_is_current = is_ceiling_context_current(ceiling_context, player, profile, entity_type)

            qualitative_text = st.session_state.get("qualitative_text_input", "")
            raw_signals = st.session_state.get("qualitative_signals")
            qual_evidence = None
            if isinstance(raw_signals, dict) and raw_signals.get("_fallback_reason") not in _SAVE_EXCLUDE_FALLBACK_REASONS:
                qual_evidence = build_qualitative_evidence_payload(qualitative_text, raw_signals)

            raw_advisory = st.session_state.get("gemini_advisory")
            advisory = raw_advisory if isinstance(raw_advisory, dict) and raw_advisory.get("_fallback_reason") not in _SAVE_EXCLUDE_FALLBACK_REASONS else None

            if entity_type == "manual_prospect":
                payload = build_manual_note_payload(
                    manual_player=st.session_state.get("manual_player") or {},
                    manual_attributes=st.session_state.get("manual_attributes") or {},
                    manual_career_settings=st.session_state.get("manual_career_settings") or {},
                    growth_insight=growth_insight,
                    growth_explanation=growth_explanation,
                    ceiling_growth_insight=growth_insight,
                    ceiling_growth_explanation=growth_explanation,
                    ceiling_growth_context=ceiling_context if context_is_current else {"entity_type": "manual_prospect", "source": "ai_report"},
                    env_settings=env_settings,
                    simulation_result=simulation_result,
                    report_sections=sections,
                    source="ai_report",
                    qualitative_evidence=qual_evidence,
                    gemini_advisory=advisory,
                )
            else:
                payload = build_ai_report_note_payload(
                    player=player,
                    profile=profile,
                    entity_type=entity_type,
                    env_settings=env_settings,
                    simulation_result=simulation_result,
                    growth_insight=growth_insight,
                    growth_explanation=growth_explanation,
                    ceiling_growth_insight=growth_insight if context_is_current else None,
                    ceiling_growth_explanation=growth_explanation if context_is_current else None,
                    report_sections=sections,
                    report_text=report,
                    ceiling_growth_context=ceiling_context if context_is_current else None,
                    qualitative_evidence=qual_evidence,
                    gemini_advisory=advisory,
                )

            saved = insert_scouting_note(
                player_id=payload["player_id"],
                profile_id=payload["profile_id"],
                env_settings=payload["env_settings"],
                simulation_result=payload["simulation_result"],
                report=payload["report"],
            )
            st.success(f"분석 리포트(규칙 기반)가 스카우팅 노트에 저장되었습니다. note_id: {saved['note_id']}")
        except Exception as exc:
            st.error("스카우팅 노트 저장 중 오류가 발생했습니다.")
            with st.expander("개발 확인용 오류"):
                st.exception(exc)

    render_page_actions(
        [
            ("My Scouting Notes에 저장/조회", "내 스카우팅 노트", "primary"),
            ("새 유망주 검색", "유망주 검색"),
        ]
    )
