"""
Qualitative evidence extraction and Gemini advisory report generation.

Gemini의 두 가지 역할 (v18):
1. 사용자가 붙여넣은 텍스트(기사/스카우팅 리포트/감독 인터뷰/관찰 메모)에서 정성 신호 구조화 추출
2. 정량 분석 결과(DB/FM proxy/rule-based) + 정성 신호를 종합한 근거 기반 보조 스카우팅 추천 생성

Gemini가 하면 안 되는 것:
- 점수 계산 금지 (Growth/Ceiling Score 변경 금지)
- 없는 사실 단정 금지 (텍스트에 없는 내용 확정 표현 금지)
- Growth/Ceiling 공식 변경 금지

항상 optional + fallback:
- API key 없으면 fallback result 반환, 앱이 깨지지 않는다.
- 호출 실패 시 fallback + 오류 메시지 반환.
- 텍스트 입력이 없으면 no_text_input fallback.

DB, app.py, Streamlit UI를 import하지 않는다.
"""

import json
import re
from datetime import datetime

from gemini_client import generate_gemini_content, is_gemini_available


_SIGNAL_VALID = {
    "playing_time_signal": {"positive", "neutral", "negative", "unknown"},
    "injury_risk_signal": {"positive", "neutral", "negative", "unknown"},
    "coach_trust_signal": {"positive", "neutral", "negative", "unknown"},
    "development_signal": {"positive", "neutral", "negative", "unknown"},
    "transfer_rumor_signal": {"high", "medium", "low", "unknown"},
    "mentality_signal": {"positive", "neutral", "negative", "unknown"},
}

_CONFIDENCE_VALID = {"high", "medium", "low"}


def make_fallback_signals(reason="no_api_key"):
    """API key 없음 또는 호출 실패 시 반환하는 기본 정성 신호 dict."""
    return {
        "qualitative_summary": "",
        "playing_time_signal": "unknown",
        "injury_risk_signal": "unknown",
        "coach_trust_signal": "unknown",
        "development_signal": "unknown",
        "transfer_rumor_signal": "unknown",
        "mentality_signal": "unknown",
        "strength_mentions": [],
        "weakness_mentions": [],
        "risk_mentions": [],
        "recommended_focus": [],
        "evidence_quotes": [],
        "confidence": "low",
        "_fallback_reason": reason,
    }


def make_fallback_advisory(reason="no_api_key"):
    """API key 없음 또는 호출 실패 시 반환하는 기본 보조 추천 dict."""
    return {
        "advisory_summary": "",
        "player_fit_assessment": "",
        "training_recommendations": [],
        "career_recommendations": [],
        "risk_management": [],
        "mentor_usage_recommendations": [],
        "what_to_monitor_next": [],
        "unsupported_or_unknown": [],
        "final_scouting_comment": "",
        "confidence": "low",
        "_fallback_reason": reason,
    }


def _build_extraction_prompt(text_input, player_context):
    player_name = (player_context or {}).get("name", "선택 선수")
    position = (player_context or {}).get("position", "-")
    club = (player_context or {}).get("club", "-")
    age = (player_context or {}).get("age", "-")

    return f"""당신은 축구 스카우팅 분석가입니다.
아래 선수 정보와 사용자가 붙여넣은 텍스트에서 정성 신호를 추출해 JSON으로 반환하세요.

## 선수 정보
- 이름: {player_name}
- 포지션: {position}
- 소속팀: {club}
- 나이: {age}

## 사용자 입력 텍스트 (사용자 입력 텍스트 기반)
{text_input[:3000]}

## 지시사항 (반드시 준수)
- 제공된 텍스트에 없는 사실을 만들지 마세요.
- 실제 부상 이력, 이적설, 감독 발언은 텍스트에 없으면 unknown으로 처리하세요.
- 점수를 계산하지 마세요. Growth/Ceiling Score를 변경하지 마세요.
- evidence_quotes는 사용자가 붙여넣은 텍스트에서 짧은 근거 문장(50자 이내)만 추출하세요.
- 긴 원문 전체를 그대로 재출력하지 마세요.
- 불확실하면 confidence를 low로 두세요.
- 기사/리포트 출처가 없으면 "사용자 입력 텍스트 기반"으로만 표시하세요.
- 없는 정보를 바탕으로 단정하지 마세요.
- "확인 필요", "근거 부족", "텍스트상 언급 없음"을 명시하세요.

## 반환 JSON 형식 (이 구조만 반환, 설명 없이)
{{
  "qualitative_summary": "텍스트 전체를 한 줄로 요약",
  "playing_time_signal": "positive | neutral | negative | unknown",
  "injury_risk_signal": "positive | neutral | negative | unknown",
  "coach_trust_signal": "positive | neutral | negative | unknown",
  "development_signal": "positive | neutral | negative | unknown",
  "transfer_rumor_signal": "high | medium | low | unknown",
  "mentality_signal": "positive | neutral | negative | unknown",
  "strength_mentions": ["강점1"],
  "weakness_mentions": ["약점1"],
  "risk_mentions": ["리스크1"],
  "recommended_focus": ["보완 방향1"],
  "evidence_quotes": ["짧은 근거 문장"],
  "confidence": "high | medium | low"
}}"""


def _build_advisory_prompt(player_context, quantitative_summary, qualitative_signals):
    player_name = (player_context or {}).get("name", "선택 선수")
    position = (player_context or {}).get("position", "-")
    growth_score = (player_context or {}).get("growth_score", "-")
    final_growth_score = (player_context or {}).get("final_growth_score", "-")
    mentor_info = (player_context or {}).get("mentor_info", "없음")

    # Remove internal _fallback_reason before sending to Gemini
    clean_signals = {k: v for k, v in (qualitative_signals or {}).items() if not k.startswith("_")}
    signals_text = json.dumps(clean_signals, ensure_ascii=False, indent=2)[:1500]
    quant_text = json.dumps(quantitative_summary or {}, ensure_ascii=False, indent=2)[:1500]

    return f"""당신은 축구 스카우팅 보조 분석가입니다.
아래 정량 분석 결과와 정성 신호를 종합해 근거 기반 보조 추천 리포트를 JSON으로 반환하세요.

## 선수 정보
- 이름: {player_name}
- 포지션: {position}
- Growth Score (rule-based 계산 결과, 변경 금지): {growth_score}
- Final Growth Score (rule-based 계산 결과, 변경 금지): {final_growth_score}
- 멘토 후보: {mentor_info}

## 정량 분석 결과 (DB/FM proxy/rule-based — 이 점수는 절대 변경하지 마세요)
{quant_text}

## 정성 신호 추출 결과 (사용자 텍스트 기반)
{signals_text}

## 지시사항 (반드시 준수)
- 제공된 데이터와 텍스트에 없는 사실을 확정적으로 말하지 마세요.
- 점수를 계산하지 마세요. Growth/Ceiling 점수를 변경하거나 대체하지 마세요.
- 추천은 단정형이 아닌 분석형/제안형으로 표현하세요.
- "확인 필요", "근거 부족", "텍스트상 언급 없음"을 명시하세요.
- 근거가 부족한 항목은 unsupported_or_unknown에 넣으세요.
- 없는 정보를 바탕으로 "부상 위험이 높다", "감독 신뢰가 낮다"처럼 단정하지 마세요.

## 반환 JSON 형식 (이 구조만 반환, 설명 없이)
{{
  "advisory_summary": "데이터와 텍스트를 종합한 한 줄 요약",
  "player_fit_assessment": "현재 선수의 성장 방향/역할 적합성 판단 (근거 기반, 제안형)",
  "training_recommendations": ["훈련 추천1"],
  "career_recommendations": ["커리어 제안1"],
  "risk_management": ["리스크 관리 방안1"],
  "mentor_usage_recommendations": ["멘토 활용 제안1"],
  "what_to_monitor_next": ["추가 확인 필요 정보1"],
  "unsupported_or_unknown": ["근거 부족 항목1"],
  "final_scouting_comment": "최종 스카우팅 코멘트 (제안형)",
  "confidence": "high | medium | low"
}}"""


def _safe_parse_json(text):
    """Gemini 응답에서 JSON을 안전하게 파싱한다. 실패하면 None을 반환한다."""
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _validate_signals(parsed):
    """파싱된 signals dict를 검증/정규화한다. 누락된 키는 기본값으로 채운다."""
    if not isinstance(parsed, dict):
        return make_fallback_signals("parse_failed")

    result = {
        "qualitative_summary": "",
        "playing_time_signal": "unknown",
        "injury_risk_signal": "unknown",
        "coach_trust_signal": "unknown",
        "development_signal": "unknown",
        "transfer_rumor_signal": "unknown",
        "mentality_signal": "unknown",
        "strength_mentions": [],
        "weakness_mentions": [],
        "risk_mentions": [],
        "recommended_focus": [],
        "evidence_quotes": [],
        "confidence": "low",
    }

    summary = parsed.get("qualitative_summary", "")
    result["qualitative_summary"] = str(summary)[:500] if summary else ""

    for key, valid_vals in _SIGNAL_VALID.items():
        val = parsed.get(key, "unknown")
        result[key] = val if val in valid_vals else "unknown"

    val = parsed.get("confidence", "low")
    result["confidence"] = val if val in _CONFIDENCE_VALID else "low"

    for key in ("strength_mentions", "weakness_mentions", "risk_mentions",
                "recommended_focus", "evidence_quotes"):
        val = parsed.get(key, [])
        if isinstance(val, list):
            result[key] = [str(v)[:200] for v in val[:10] if v]
        else:
            result[key] = []

    return result


def _validate_advisory(parsed):
    """파싱된 advisory dict를 검증/정규화한다."""
    if not isinstance(parsed, dict):
        return make_fallback_advisory("parse_failed")

    result = {
        "advisory_summary": "",
        "player_fit_assessment": "",
        "training_recommendations": [],
        "career_recommendations": [],
        "risk_management": [],
        "mentor_usage_recommendations": [],
        "what_to_monitor_next": [],
        "unsupported_or_unknown": [],
        "final_scouting_comment": "",
        "confidence": "low",
    }

    for key in ("advisory_summary", "player_fit_assessment", "final_scouting_comment"):
        val = parsed.get(key, "")
        result[key] = str(val)[:800] if val else ""

    for key in ("training_recommendations", "career_recommendations", "risk_management",
                "mentor_usage_recommendations", "what_to_monitor_next", "unsupported_or_unknown"):
        val = parsed.get(key, [])
        if isinstance(val, list):
            result[key] = [str(v)[:300] for v in val[:10] if v]
        else:
            result[key] = []

    val = parsed.get("confidence", "low")
    result["confidence"] = val if val in _CONFIDENCE_VALID else "low"

    return result


def extract_qualitative_signals(text_input, player_context=None):
    """사용자 붙여넣기 텍스트에서 정성 신호를 추출한다.

    Returns: (signals_dict, error_message|None)
    - text_input이 없으면: (no_text_input fallback, None)
    - API key 없으면: (no_api_key fallback, None)
    - 호출 실패: (api_error fallback, 오류 메시지)
    실제 Gemini 호출은 사용자가 버튼을 눌렀을 때만 수행된다.
    """
    if not text_input or not text_input.strip():
        return make_fallback_signals("no_text_input"), None

    if not is_gemini_available():
        return make_fallback_signals("no_api_key"), None

    prompt = _build_extraction_prompt(text_input, player_context or {})
    result = generate_gemini_content(prompt)

    if not result["success"]:
        return make_fallback_signals("api_error"), result.get("error", "알 수 없는 오류")

    parsed = _safe_parse_json(result["text"])
    return _validate_signals(parsed), None


def generate_gemini_advisory(player_context, quantitative_summary, qualitative_signals):
    """정량 분석 결과 + 정성 신호를 종합한 근거 기반 보조 추천을 생성한다.

    Returns: (advisory_dict, error_message|None)
    - API key 없으면: (no_api_key fallback, None)
    - 호출 실패: (api_error fallback, 오류 메시지)
    실제 Gemini 호출은 사용자가 버튼을 눌렀을 때만 수행된다.
    """
    if not is_gemini_available():
        return make_fallback_advisory("no_api_key"), None

    prompt = _build_advisory_prompt(player_context, quantitative_summary, qualitative_signals)
    result = generate_gemini_content(prompt)

    if not result["success"]:
        return make_fallback_advisory("api_error"), result.get("error", "알 수 없는 오류")

    parsed = _safe_parse_json(result["text"])
    return _validate_advisory(parsed), None


def build_player_context_for_gemini(player, profile, growth_insight, growth_explanation, mentor_summary=None):
    """Gemini 프롬프트용 선수 context dict를 생성한다 (UI와 분리된 순수 helper)."""
    growth_score = None
    final_growth_score = None
    if isinstance(growth_insight, dict):
        growth_score = growth_insight.get("growth_score")
        ceiling = growth_insight.get("ceiling_model", {})
        if isinstance(ceiling, dict):
            final_growth_score = ceiling.get("final_growth_score")

    return {
        "name": (player or {}).get("name") or "선택 선수",
        "position": (player or {}).get("position") or "-",
        "age": (profile or {}).get("age") or (player or {}).get("age") or "-",
        "club": (player or {}).get("current_club_name") or "-",
        "growth_score": f"{growth_score:.1f}" if growth_score is not None else "-",
        "final_growth_score": f"{final_growth_score:.1f}" if final_growth_score is not None else "-",
        "mentor_info": mentor_summary or "없음",
    }


def build_quantitative_summary_for_gemini(growth_insight, growth_explanation, env_settings=None, simulation_result=None):
    """Gemini 프롬프트용 정량 분석 요약 dict를 생성한다 (UI와 분리된 순수 helper)."""
    result = {}
    if isinstance(growth_explanation, dict):
        result["summary"] = growth_explanation.get("summary", "")
        result["strengths"] = growth_explanation.get("strengths", [])
        result["risks"] = growth_explanation.get("risks", [])
        result["recommendations"] = growth_explanation.get("recommendations", [])
        ceiling_exp = growth_explanation.get("ceiling_explanation")
        if isinstance(ceiling_exp, dict):
            result["ceiling_coaching_summary"] = ceiling_exp.get("coaching_summary", "")
            result["final_growth_score"] = ceiling_exp.get("final_growth_score")
            result["training_directions"] = ceiling_exp.get("training_directions", [])
            result["risk_warnings"] = ceiling_exp.get("risk_warnings", [])
            result["career_strategy"] = ceiling_exp.get("career_strategy", [])
    return result


def build_qualitative_evidence_payload(text_input, signals):
    """저장용 qualitative_evidence payload를 생성한다.

    원문 전체가 아닌 적절히 truncate된 스냅샷만 저장한다.
    _fallback_reason 같은 내부 키는 제거한다.
    """
    snapshot = ""
    if text_input and isinstance(text_input, str):
        snapshot = text_input[:500] + ("..." if len(text_input) > 500 else "")

    clean_signals = {k: v for k, v in (signals or {}).items() if not k.startswith("_")}

    return {
        "source": "manual_text_input",
        "input_text_snapshot": snapshot,
        "extracted_signals": clean_signals,
        "created_at": datetime.utcnow().isoformat(),
    }
