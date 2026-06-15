"""기사/스카우팅 문장 기반 mentality evidence 추출 (사용자 입력 텍스트 기반).

원래 기획은 대량 기사 크롤링 + Gemini 기반 정성 태그 추출이었다. 이번 세션에서는
사용자가 직접 입력한 제목/URL/snippet 텍스트만을 입력으로 받아, 다음 9개
category에 대한 점수/confidence/요약을 만든다:

    determination, work_rate, professionalism, pressure_handling,
    leadership, teamwork, injury_concern, discipline, adaptability

Gemini API key가 있으면 Gemini로 구조화 추출을 시도하고, 없거나 실패하면
rule-based keyword matching으로 fallback한다 (fallback의 confidence는 항상
낮게 표시한다). 이 모듈은 DB에 아무것도 저장하지 않으며, app.py를 import하지
않는다.
"""

import json
import re

from gemini_client import generate_gemini_content, is_gemini_available


EVIDENCE_CATEGORIES = [
    "determination",
    "work_rate",
    "professionalism",
    "pressure_handling",
    "leadership",
    "teamwork",
    "injury_concern",
    "discipline",
    "adaptability",
]

CATEGORY_LABELS = {
    "determination": "의지력 / 성장 의지",
    "work_rate": "활동량 / 헌신",
    "professionalism": "프로 의식 / 자기관리",
    "pressure_handling": "압박 대처 / 침착성",
    "leadership": "리더십",
    "teamwork": "팀워크",
    "injury_concern": "부상 우려",
    "discipline": "규율 / 절제",
    "adaptability": "적응력",
}

# rule-based fallback용 키워드 (영어/한국어 혼용 텍스트 모두 대응).
CATEGORY_KEYWORDS = {
    "determination": [
        "determination", "determined", "ambitious", "ambition", "drive", "hungry",
        "willpower", "의지", "성장 의지", "독한", "투지", "야망",
    ],
    "work_rate": [
        "work rate", "hard-working", "hardworking", "tireless", "relentless", "pressing",
        "활동량", "성실", "근면", "압박", "쉬지 않는",
    ],
    "professionalism": [
        "professional", "professionalism", "discipline", "dedication", "role model",
        "프로 의식", "성실함", "모범", "자기관리", "훈련 태도",
    ],
    "pressure_handling": [
        "composed", "composure", "pressure", "clutch", "big game", "calm under pressure",
        "침착", "압박 상황", "큰 경기", "냉정",
    ],
    "leadership": [
        "leader", "leadership", "captain", "vocal", "organizer",
        "리더십", "주장", "이끄는", "리더",
    ],
    "teamwork": [
        "team player", "teamwork", "selfless", "link-up", "collective",
        "팀워크", "동료", "헌신적", "팀 플레이",
    ],
    "injury_concern": [
        "injury", "injured", "injury-prone", "setback", "recovery", "sidelined", "muscle",
        "부상", "재활", "결장", "근육 부상",
    ],
    "discipline": [
        "red card", "yellow card", "suspended", "suspension", "misconduct", "ill-discipline",
        "퇴장", "경고", "징계", "출장 정지",
    ],
    "adaptability": [
        "adapt", "adaptable", "versatile", "flexible", "settled in", "new league", "new club",
        "적응", "새로운 환경", "유연", "다재다능",
    ],
}

# fallback은 항상 confidence를 낮게 표시한다.
FALLBACK_CONFIDENCE_PER_HIT = 0.12
FALLBACK_CONFIDENCE_MAX = 0.55
FALLBACK_BASE_SCORE_PER_HIT = 0.3
FALLBACK_SCORE_MAX = 0.9


def _empty_scores():
    return {category: 0.0 for category in EVIDENCE_CATEGORIES}


def _empty_confidence():
    return {category: 0.0 for category in EVIDENCE_CATEGORIES}


def extract_evidence_rule_based(text):
    """키워드 매칭 기반 fallback 추출. 항상 낮은 confidence를 반환한다."""
    lowered = (text or "").lower()
    scores = _empty_scores()
    confidence = _empty_confidence()
    matched_keywords = {category: [] for category in EVIDENCE_CATEGORIES}

    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = []
        for keyword in keywords:
            if keyword.lower() in lowered:
                hits.append(keyword)

        if hits:
            scores[category] = round(min(FALLBACK_SCORE_MAX, FALLBACK_BASE_SCORE_PER_HIT * len(hits)), 2)
            confidence[category] = round(min(FALLBACK_CONFIDENCE_MAX, FALLBACK_CONFIDENCE_PER_HIT * len(hits)), 2)
            matched_keywords[category] = hits

    matched_categories = [category for category, hits in matched_keywords.items() if hits]
    if matched_categories:
        labels = ", ".join(CATEGORY_LABELS[category] for category in matched_categories)
        evidence_summary = (
            f"입력 텍스트에서 {labels} 관련 키워드가 발견되어 해당 항목의 점수를 산정했습니다. "
            "이 결과는 Gemini가 아닌 규칙 기반(rule-based) 키워드 매칭이므로 confidence가 낮게 표시됩니다."
        )
    else:
        evidence_summary = (
            "입력 텍스트에서 9개 category와 관련된 키워드를 찾지 못했습니다. "
            "더 구체적인 평가/성향 관련 문장을 포함한 텍스트를 입력하면 더 나은 결과를 얻을 수 있습니다."
        )

    return {
        "mode": "fallback",
        "scores": scores,
        "confidence": confidence,
        "matched_keywords": matched_keywords,
        "evidence_summary": evidence_summary,
        "risk_note": None,
        "raw_error": None,
    }


def _build_gemini_prompt(player_name, source_title, source_url, text):
    categories_text = "\n".join(f"- {category}: {CATEGORY_LABELS[category]}" for category in EVIDENCE_CATEGORIES)
    return f"""다음은 축구 유망주 "{player_name}"에 대한 기사/스카우팅 텍스트입니다.

제목: {source_title or "(제목 없음)"}
URL: {source_url or "(URL 없음)"}
본문/snippet:
{text}

아래 9개 category 각각에 대해 0~1 사이의 score(해당 성향이 텍스트에서
얼마나 긍정적으로/명확하게 언급되는지)와 0~1 사이의 confidence를 추정하고,
전체 evidence_summary(한국어 2~3문장)와 risk_note(부상/규율 등 우려 사항,
없으면 null)를 작성해 주세요.

category 목록:
{categories_text}

다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이 JSON만):
{{
  "determination": {{"score": 0.0, "confidence": 0.0}},
  "work_rate": {{"score": 0.0, "confidence": 0.0}},
  "professionalism": {{"score": 0.0, "confidence": 0.0}},
  "pressure_handling": {{"score": 0.0, "confidence": 0.0}},
  "leadership": {{"score": 0.0, "confidence": 0.0}},
  "teamwork": {{"score": 0.0, "confidence": 0.0}},
  "injury_concern": {{"score": 0.0, "confidence": 0.0}},
  "discipline": {{"score": 0.0, "confidence": 0.0}},
  "adaptability": {{"score": 0.0, "confidence": 0.0}},
  "evidence_summary": "...",
  "risk_note": null
}}"""


def _parse_gemini_json(text):
    if not text:
        return None

    cleaned = text.strip()
    # ```json ... ``` 코드블록으로 감싸져 오는 경우 제거
    cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None


def extract_evidence_with_gemini(player_name, source_title, source_url, text):
    """Gemini API로 구조화 추출을 시도한다. 실패하면 None을 반환한다 (호출부에서 fallback 처리)."""
    prompt = _build_gemini_prompt(player_name, source_title, source_url, text)
    result = generate_gemini_content(prompt)

    if not result["success"]:
        return None, result["error"]

    parsed = _parse_gemini_json(result["text"])
    if parsed is None:
        return None, "Gemini 응답을 JSON으로 해석할 수 없습니다."

    scores = _empty_scores()
    confidence = _empty_confidence()
    matched_keywords = {category: [] for category in EVIDENCE_CATEGORIES}

    for category in EVIDENCE_CATEGORIES:
        entry = parsed.get(category) or {}
        try:
            scores[category] = round(float(entry.get("score", 0.0)), 2)
        except Exception:
            scores[category] = 0.0
        try:
            confidence[category] = round(float(entry.get("confidence", 0.0)), 2)
        except Exception:
            confidence[category] = 0.0

    evidence_summary = parsed.get("evidence_summary") or "Gemini가 evidence_summary를 반환하지 않았습니다."
    risk_note = parsed.get("risk_note")

    return {
        "mode": "gemini",
        "scores": scores,
        "confidence": confidence,
        "matched_keywords": matched_keywords,
        "evidence_summary": evidence_summary,
        "risk_note": risk_note,
        "raw_error": None,
    }, None


def extract_mentality_evidence(player_name, source_title, source_url, text, use_gemini=False):
    """player_name/source_title/source_url/text를 받아 evidence 결과를 만든다.

    use_gemini=True이고 Gemini API key가 있으면 Gemini를 우선 시도하고,
    실패하면 rule-based fallback으로 전환한다 (fallback_reason에 사유를 남긴다).
    """
    fallback_reason = None

    if use_gemini and is_gemini_available():
        gemini_result, error = extract_evidence_with_gemini(player_name, source_title, source_url, text)
        if gemini_result is not None:
            result = gemini_result
        else:
            result = extract_evidence_rule_based(text)
            fallback_reason = error or "Gemini 호출에 실패하여 rule-based fallback을 사용했습니다."
    else:
        result = extract_evidence_rule_based(text)
        if use_gemini and not is_gemini_available():
            fallback_reason = "GEMINI_API_KEY가 설정되어 있지 않아 rule-based fallback을 사용했습니다."

    result = dict(result)
    result["player_name"] = player_name
    result["source_title"] = source_title
    result["source_url"] = source_url
    result["fallback_reason"] = fallback_reason
    return result
