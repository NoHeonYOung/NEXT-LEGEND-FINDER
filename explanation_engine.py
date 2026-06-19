"""growth_model.py의 Growth Insight를 사람이 이해할 수 있는 설명으로 변환하는
rule-based explanation engine.

이번 세션에서는 Gemini API를 호출하지 않는다. 대신 build_gemini_ready_payload()로
나중에 Gemini API에 그대로 넘길 수 있는 구조화된 payload를 함께 만들어 둔다.
app.py를 import하지 않는다(순환 import 방지).
"""

from growth_model import FEATURE_LABELS, GROWTH_WEIGHTS, LEVEL_DESCRIPTIONS


# FEATURE_LABELS의 개발자 용어를 사용자 친화 표현으로 덮어씁니다.
_FRIENDLY_LABELS = {**FEATURE_LABELS, "attribute_strength": "능력치 점수"}


def _label(feature_name):
    return _FRIENDLY_LABELS.get(feature_name, feature_name)


ENTITY_TYPE_CONTEXT_NOTES = {
    "matched": "Transfermarkt 실데이터와 능력치 프로필이 모두 매칭되어, 시장가치/출전 기록/능력치/멘탈리티를 종합적으로 반영한 평가입니다.",
    "fm_profile_only": "능력치 프로필만 연결되어 있어, 시장가치 흐름과 출전 기회 항목은 반영되지 않았습니다. 능력치/멘탈리티 중심의 제한적 평가입니다.",
    "transfermarkt_only": "Transfermarkt 실데이터만 연결되어 있어, 능력치/멘탈리티 항목은 반영되지 않았습니다. 시장가치와 출전 기록 중심의 제한적 평가입니다.",
    "manual_note": "직접 입력한 능력치와 환경 설정을 기반으로 성장 가능성을 평가했습니다. 시장가치와 실제 출전 기록이 없으므로 해당 항목은 제한적으로 반영됩니다.",
}

# feature별 출처 badge 라벨 매핑
FEATURE_SOURCE_BADGES = {
    "market_momentum": ["Transfermarkt"],
    "playing_opportunity": ["Transfermarkt"],
    "contribution_score": ["Transfermarkt"],
    "age_potential": ["DB"],
    "attribute_strength": ["능력치 기반"],
    "mentality_strength": ["능력치 기반"],
}


def _contribution(feature_name, feature_result):
    """feature가 최종 Growth Score에 실제로 기여한 점수(0~100 환산)."""
    if feature_result.get("status") != "ok":
        return None
    return GROWTH_WEIGHTS[feature_name] * feature_result["score"] * 100


def _level_text(score):
    if score >= 0.65:
        return "긍정적"
    if score >= 0.4:
        return "보통 수준"
    return "보완이 필요한"


def explain_feature_score(feature_name, feature_result):
    """개별 feature 점수에 대한 구조화된 설명을 만든다.

    강점/보완점 모두 4부 구조(핵심 / 근거 / 해석 / 방향)로 설명한다.
    실제 데이터에 없는 사실을 만들지 않는다.
    """
    label = _label(feature_name)

    if feature_result.get("status") != "ok":
        reason = feature_result.get("detail", {}).get("reason", "데이터가 부족합니다.")
        # 내부 키 이름이 사용자 화면에 노출되지 않도록 치환
        reason = reason.replace("FM 프로필이 없습니다.", "능력치 프로필이 없습니다.")
        reason = reason.replace("attributes_jsonb", "능력치 데이터")
        reason = reason.replace("mentality_jsonb", "멘탈 데이터")
        return f"{label}: 데이터가 부족하여({reason}) 이번 평가에서 제외되었습니다."

    score = feature_result["score"]
    detail = feature_result.get("detail", {})
    lt = _level_text(score)
    is_strength = score >= 0.6
    score_pct = f"{score * 100:.0f}점"

    if feature_name == "market_momentum":
        growth = detail.get("market_growth")
        if growth is None:
            trend_str = "변화 없음(데이터 없음)"
        elif growth > 0.1:
            trend_str = f"상승 (+{growth:.1%})"
        elif growth < -0.05:
            trend_str = f"하락 ({growth:.1%})"
        else:
            trend_str = "소폭 변화 또는 정체"

        headline = (
            f"시장가치 흐름이 성장 잠재력을 긍정적으로 뒷받침하고 있습니다 ({score_pct})."
            if is_strength else
            f"최근 시장가치 흐름이 약해 성장 동력 확인이 필요합니다 ({score_pct})."
        )
        evidence = f"근거(Transfermarkt): 최근 시장가치 변화율 {trend_str}으로 산정되었습니다."
        interpretation = (
            "스카우팅 관점에서 상승 추세는 현장 평가와 이적 관심도가 함께 높아지고 있다는 간접 신호일 수 있습니다."
            if is_strength else
            "시장가치 정체 또는 하락은 출전 감소, 팀 내 역할 축소, 또는 평가 지연 등 다양한 요인이 복합적으로 작용한 결과일 수 있습니다."
        )
        direction = (
            "현재 상승 흐름을 유지하려면 꾸준한 출전과 팀 내 핵심 역할 확보가 중요합니다."
            if is_strength else
            "꾸준한 출전 확보를 통해 시장가치 반등의 근거를 만드는 것이 우선 과제입니다. 임대 출전 등 실전 기회를 늘리는 방향을 검토하세요."
        )
        return f"{headline} {evidence} {interpretation} {direction}"

    if feature_name == "playing_opportunity":
        if detail.get("basis") == "minutes":
            minutes_val = detail.get("recent_minutes", 0)
            evidence_str = f"최근 경기에서 약 {minutes_val:.0f}분 출전(출전 시간 기준, Transfermarkt)"
        else:
            apps_val = detail.get("recent_appearances", 0)
            evidence_str = f"최근 약 {apps_val}경기 출전(경기 수 기준, Transfermarkt)"

        headline = (
            f"꾸준한 출전 기회를 확보해 실전 경험을 쌓고 있습니다 ({score_pct})."
            if is_strength else
            f"출전 기회가 부족해 실전 감각 유지에 어려움이 있을 수 있습니다 ({score_pct})."
        )
        evidence = f"근거(Transfermarkt): {evidence_str}으로 산정되었습니다."
        interpretation = (
            "높은 출전 비중은 팀 내 신뢰와 역할이 확보되어 있다는 신호로 해석될 수 있습니다."
            if is_strength else
            "출전 부족은 자신감 저하, 경기 감각 둔화, 성장 속도 저하로 이어질 수 있습니다."
        )
        direction = (
            "현재 출전 흐름을 유지하면서 역할별 기여도(득점/어시스트 외 수비 기여 등)를 함께 높이는 것이 좋습니다."
            if is_strength else
            "임대, 로테이션 출전 등 실질적인 출전 기회 확보 방안을 적극 검토해야 합니다. 훈련만으로는 실전 감각을 대체하기 어렵습니다."
        )
        return f"{headline} {evidence} {interpretation} {direction}"

    if feature_name == "contribution_score":
        per90 = detail.get("goal_contribution_per90", 0)
        headline = (
            f"경기 기여도(골+어시스트)가 {lt} 평가를 받았습니다 ({score_pct}, 90분당 {per90:.2f})."
            if is_strength else
            f"경기 기여도(골+어시스트) 지표가 낮아 보완이 필요합니다 ({score_pct}, 90분당 {per90:.2f})."
        )
        evidence = f"근거(Transfermarkt): 출전 기록에서 산출한 90분당 공격 포인트(골+어시스트) {per90:.2f}를 기반으로 산정되었습니다."
        interpretation = (
            "공격 기여가 꾸준히 나오고 있다는 것은 팀 전술에서 핵심 공격 역할을 맡고 있음을 시사합니다."
            if is_strength else
            "공격 기여도가 낮다는 것이 반드시 선수 역량의 부재를 의미하지는 않습니다. 포지션 역할(수비형 미드필더 등), 출전 시간 부족, 팀 전술 등이 영향을 미쳤을 수 있습니다."
        )
        direction = (
            "현재 공격 기여 흐름을 유지하면서 오프더볼 움직임, 공간 창출 역할도 함께 발전시키는 것이 좋습니다."
            if is_strength else
            "포지션 기준 기여 방식(어시스트보다 공간 창출 등)을 재평가하고, 결정력과 찬스 메이킹 훈련을 병행하는 것이 좋습니다."
        )
        return f"{headline} {evidence} {interpretation} {direction}"

    if feature_name == "age_potential":
        age = detail.get("age")
        age_str = f"{age}세" if age is not None else "나이 정보 없음"
        headline = (
            f"나이 기준 성장 잠재력이 {lt} 위치에 있습니다 ({score_pct})."
        )
        evidence = f"근거(DB): {age_str}는 21세 기준 성장 곡선 모델에서 {score_pct}에 해당합니다."
        interpretation = (
            "현재 나이는 잠재력이 가장 빠르게 실력으로 전환되는 시기에 속합니다. 이 시기의 집중 훈련과 실전 경험은 장기 성장에 큰 영향을 미칩니다."
            if is_strength else
            "성장 곡선상 피크 시기가 지났거나 근접한 경우, 추가 성장보다 현재 강점 유지와 효율적 역할 배분이 더 중요해질 수 있습니다."
        )
        direction = (
            "현재 성장 모멘텀을 살려 실전 경험을 최대화하고, 동시에 부상 없이 훈련 강도를 단계적으로 높이는 것이 좋습니다."
            if is_strength else
            "나이 대비 성장 속도를 유지하려면 역할 전문화(포지션 특화 훈련)와 경험 축적을 병행하는 것이 현실적입니다."
        )
        return f"{headline} {evidence} {interpretation} {direction}"

    if feature_name == "attribute_strength":
        headline = (
            f"능력치 프로필이 {lt} 수준을 보입니다 ({score_pct})."
        )
        evidence = "근거(능력치 데이터): 능력치 데이터에서 산출한 주요 속성 평균값입니다. 실제 경기 기록이 아닌 능력치 기반 추정값임에 유의하세요."
        interpretation = (
            "능력치가 높다는 것은 기술/피지컬 기반이 상대적으로 좋은 프로필에 해당한다는 의미이며, 실전 적용 가능성을 직접 보장하지는 않습니다."
            if is_strength else
            "능력치가 낮다는 것은 기술/피지컬 기반 항목에서 개선 여지가 있음을 시사합니다."
        )
        direction = (
            "현재 능력치 강점을 실전에서 일관성 있게 발휘할 수 있도록 포지션 역할에 맞는 전술 훈련을 병행하는 것이 좋습니다."
            if is_strength else
            "기본 기술 및 피지컬 항목을 보완하는 훈련 계획이 필요합니다. 낮게 나온 능력치 그룹을 우선 확인하고 해당 항목 집중 훈련을 검토하세요."
        )
        return f"{headline} {evidence} {interpretation} {direction}"

    if feature_name == "mentality_strength":
        headline = (
            f"멘탈·성향 지표가 {lt} 수준을 보입니다 ({score_pct})."
        )
        evidence = "근거(능력치 데이터): 능력치 데이터에서 산출한 멘탈 관련 속성 평균값입니다. 실제 심리 평가가 아닌 능력치 기반 참고 지표입니다."
        interpretation = (
            "멘탈·성향 지표가 높다는 것은 팀워크, 판단력, 압박 대처, 의지력 등 관련 속성이 상대적으로 높은 프로필임을 의미합니다."
            if is_strength else
            "멘탈·성향 지표가 낮다는 것은 압박 상황 대처, 집중력, 팀워크 등에서 보완이 필요한 항목이 있음을 시사합니다. 실제 선수 멘탈과 다를 수 있으므로 스카우팅 관찰과 함께 판단하세요."
        )
        direction = (
            "멘탈 강점을 경기에서 일관성 있게 발휘하려면 고압적 상황(막판 동점/역전 위기 등)에서의 판단 훈련이 도움이 됩니다."
            if is_strength else
            "압박 상황에서의 첫 터치 방향, 주변 시야 확보, 팀워크 강화 훈련을 코칭에 포함하는 것이 좋습니다."
        )
        return f"{headline} {evidence} {interpretation} {direction}"

    return f"{label}: {lt} 평가({score_pct})입니다."


def build_strengths(features):
    """점수가 높은 feature를 강점으로 정리한다."""
    strengths = []
    for feature_name, feature_result in features.items():
        if feature_result.get("status") == "ok" and feature_result["score"] >= 0.6:
            strengths.append(explain_feature_score(feature_name, feature_result))

    if not strengths:
        strengths.append("현재 데이터 기준으로는 뚜렷하게 두드러지는 강점 지표가 확인되지 않았습니다.")

    return strengths


def build_strengths_with_meta(features):
    """강점 항목을 (text, source_badges) 튜플 리스트로 반환한다. UI badge 표시용."""
    items = []
    for feature_name, feature_result in features.items():
        if feature_result.get("status") == "ok" and feature_result["score"] >= 0.6:
            items.append((
                explain_feature_score(feature_name, feature_result),
                FEATURE_SOURCE_BADGES.get(feature_name, ["데이터 기반 분석"]),
            ))
    if not items:
        items.append(("현재 데이터 기준으로는 뚜렷하게 두드러지는 강점 지표가 확인되지 않았습니다.", ["데이터 기반 분석"]))
    return items


def build_risks(features, risk_penalty=None):
    """점수가 낮은 feature와 risk_penalty 사유를 리스크로 정리한다."""
    risks = []
    for feature_name, feature_result in features.items():
        if feature_result.get("status") == "ok" and feature_result["score"] < 0.4:
            risks.append(explain_feature_score(feature_name, feature_result))

    if risk_penalty:
        risks.extend(risk_penalty.get("notes", []))

    if not risks:
        risks.append("현재 데이터 기준으로는 특별히 두드러지는 리스크 요인이 확인되지 않았습니다.")

    return risks


def build_risks_with_meta(features, risk_penalty=None):
    """리스크 항목을 (text, source_badges) 튜플 리스트로 반환한다. UI badge 표시용."""
    items = []
    for feature_name, feature_result in features.items():
        if feature_result.get("status") == "ok" and feature_result["score"] < 0.4:
            items.append((
                explain_feature_score(feature_name, feature_result),
                FEATURE_SOURCE_BADGES.get(feature_name, ["데이터 기반 분석"]),
            ))
    if risk_penalty:
        for note in risk_penalty.get("notes", []):
            items.append((note, ["성장 가능성 모델"]))
    if not items:
        items.append(("현재 데이터 기준으로는 특별히 두드러지는 리스크 요인이 확인되지 않았습니다.", ["데이터 기반 분석"]))
    return items


def build_recommendations(features, player_context=None):
    """feature 결과를 바탕으로 추천 성장 방향을 만든다."""
    player_context = player_context or {}
    recommendations = []

    market = features.get("market_momentum", {})
    if market.get("status") == "ok" and market["score"] < 0.4:
        recommendations.append(
            "우선 훈련 목표: 출전 기회를 통한 시장가치 반등 기반 마련. "
            "왜 필요한가: 최근 시장가치 흐름이 약해 꾸준한 출전이 가장 직접적인 반등 신호가 됩니다(Transfermarkt 기반). "
            "훈련 방향: 팀 내 역할을 유지하면서 임대 등 출전 기회를 적극 확보하세요. "
            "관찰 지표: 시장가치 변화율, 최근 출전 경기 수."
        )

    playing = features.get("playing_opportunity", {})
    if playing.get("status") == "ok" and playing["score"] < 0.4:
        recommendations.append(
            "우선 훈련 목표: 실전 출전 기회 확보. "
            "왜 필요한가: 출전 시간이 부족하면 경기 감각과 판단 속도가 둔화되어 성장 정체로 이어질 수 있습니다(Transfermarkt 기반). "
            "훈련 방향: 임대, 로테이션 출전 등을 통해 실질적인 출전 기회를 늘리고, 훈련만으로는 실전 감각을 대체하기 어렵다는 점을 인식하세요. "
            "관찰 지표: 최근 경기 출전 시간, 출전 경기 수."
        )

    contribution = features.get("contribution_score", {})
    if contribution.get("status") == "ok" and contribution["score"] < 0.4:
        position = player_context.get("position") or "현재 포지션"
        recommendations.append(
            f"우선 훈련 목표: {position} 기준 경기 기여도(골+어시스트) 향상. "
            "왜 필요한가: 90분당 공격 포인트가 낮은 편으로, 결정적 장면에서의 영향력이 제한적일 수 있습니다(Transfermarkt 기반). "
            "훈련 방향: 결정력, 오프더볼 움직임, 패스 선택, 판단 속도, 찬스 메이킹 훈련을 집중적으로 진행하세요. 포지션 역할에 따라 기여 방식(어시스트 vs 공간 창출)을 구분해서 접근하세요. "
            "관찰 지표: 90분당 골+어시스트, 슈팅 정확도, 키패스 수."
        )

    attribute = features.get("attribute_strength", {})
    if attribute.get("status") == "ok" and attribute["score"] < 0.4:
        recommendations.append(
            "우선 훈련 목표: 기술/피지컬 능력치 보완. "
            "왜 필요한가: 능력치 평균이 낮은 편으로, 기본 기술/피지컬 기반을 강화할 필요가 있습니다. "
            "훈련 방향: 낮게 나온 능력치 그룹(기술, 피지컬, 멘탈 등)을 우선 식별하고, 해당 항목을 집중 훈련하세요. "
            "관찰 지표: 능력치 평균 변화, 특정 속성 그룹 개선 여부."
        )

    mentality = features.get("mentality_strength", {})
    if mentality.get("status") == "ok" and mentality["score"] < 0.4:
        recommendations.append(
            "우선 훈련 목표: 압박 상황 대처 및 팀워크 강화. "
            "왜 필요한가: 멘탈·성향 지표가 낮은 편으로, 고압적 상황에서의 판단력과 팀 협업 측면에서 개선 여지가 있습니다. "
            "훈련 방향: 고압 상황에서의 첫 터치, 주변 시야 확보, 수비 전환 타이밍 훈련을 코칭에 포함하세요. "
            "관찰 지표: 멘탈 관련 능력치 변화, 경기 중 실수 빈도, 팀워크 평가."
        )

    age = features.get("age_potential", {})
    if age.get("status") == "ok" and age["score"] >= 0.6:
        recommendations.append(
            "우선 훈련 목표: 현재 성장 모멘텀 극대화. "
            "왜 필요한가: 나이 기준 성장 곡선상 유리한 시기에 있어 집중 투자의 효과가 클 수 있습니다(DB 기반 나이 곡선 모델). "
            "훈련 방향: 강점 항목을 꾸준히 실전에서 활용하면서, 부상 없이 훈련 강도를 단계적으로 높이는 것이 좋습니다. "
            "관찰 지표: 출전 시간, 시장가치 흐름, 성장 곡선상 위치."
        )

    if not recommendations:
        recommendations.append(
            "현재 데이터 기준으로는 특정 항목 우선 개선보다 현재 흐름을 유지하는 것이 좋습니다. "
            "출전 시간과 시장가치 추이를 지속적으로 관찰하면서, 다음 시점 데이터와 함께 재평가하는 것이 권장됩니다."
        )

    return recommendations


def _score_reason_data_driven(features, growth_score):
    available = [
        (feature_name, _contribution(feature_name, feature_result))
        for feature_name, feature_result in features.items()
        if feature_result.get("status") == "ok"
    ]
    available = sorted(available, key=lambda item: item[1], reverse=True)

    if not available:
        return "현재 사용 가능한 데이터가 없어 Growth Score를 산정할 수 없습니다."

    top = available[:2]
    top_text = ", ".join(f"{_label(name)}({contribution:.1f}점 기여)" for name, contribution in top)

    bottom = [item for item in available if item[1] is not None and item[1] < (GROWTH_WEIGHTS[item[0]] * 100 * 0.4)]
    unavailable = [_label(name) for name, result in features.items() if result.get("status") == "unavailable"]

    reason = f"Growth Score({growth_score})는 주로 {top_text} 항목의 기여로 산정되었습니다."

    if bottom:
        bottom_text = ", ".join(_label(name) for name, _ in bottom)
        reason += f" 반면 {bottom_text} 항목은 기여가 낮아 점수를 끌어내리는 요인이 되었습니다."

    if unavailable:
        reason += f" {', '.join(unavailable)} 항목은 데이터가 없어 평가에서 제외되었고, 남은 항목들의 비중을 재조정해 계산했습니다."

    return reason


def _build_data_driven_explanation(growth_insight, player_context):
    features = growth_insight["features"]
    growth_score = growth_insight["growth_score"]
    entity_type = growth_insight.get("entity_type")
    risk_penalty = growth_insight.get("risk_penalty")

    context_note = ENTITY_TYPE_CONTEXT_NOTES.get(entity_type, "")

    if growth_score is None:
        summary = "현재 선수는 시장가치/출전 기록/능력치 데이터가 모두 부족하여 Growth Score를 산정할 수 없습니다."
    elif growth_score >= 70:
        summary = f"이 선수는 Growth Score {growth_score}점으로 높은 성장 잠재력을 보입니다. {context_note}"
    elif growth_score >= 45:
        summary = f"이 선수는 Growth Score {growth_score}점으로 중간 수준의 성장 잠재력을 보입니다. {context_note}"
    else:
        summary = f"이 선수는 Growth Score {growth_score}점으로 현재 데이터 기준 성장 잠재력이 제한적입니다. {context_note}"

    score_reason = _score_reason_data_driven(features, growth_score) if growth_score is not None else "데이터 부족으로 점수를 산정하지 못했습니다."

    data_limitations = []
    for feature_name, feature_result in features.items():
        if feature_result.get("status") == "unavailable":
            feat_label = _label(feature_name)
            reason = feature_result.get("detail", {}).get("reason", "데이터가 부족합니다.")
            reason = reason.replace("FM 프로필이 없습니다.", "능력치 프로필이 없습니다.")
            reason = reason.replace("attributes_jsonb", "능력치 데이터")
            reason = reason.replace("mentality_jsonb", "멘탈 데이터")
            data_limitations.append(f"{feat_label} 항목: {reason}")

    if not data_limitations:
        data_limitations.append("모든 feature 항목에 사용 가능한 데이터가 있습니다.")

    return {
        "summary": summary.strip(),
        "score_reason": score_reason,
        "strengths": build_strengths(features),
        "risks": build_risks(features, risk_penalty),
        "recommendations": build_recommendations(features, player_context),
        "data_limitations": data_limitations,
    }


def _build_manual_explanation(growth_insight, player_context):
    levels = growth_insight["levels"]
    scores = growth_insight["scores"]
    growth_score = growth_insight["growth_score"]
    risk_penalty = growth_insight.get("risk_penalty", {})

    training_level = levels["training_intensity"]
    league_level = levels["league_level"]
    playing_level = levels["playing_opportunity"]
    risk_level = levels["risk_tendency"]

    summary = (
        f"직접 입력한 능력치와 환경 설정을 기반으로 Growth Score {growth_score}점이 계산되었습니다. "
        f"훈련강도 '{training_level}', 리그난이도 '{league_level}', 출전기회 '{playing_level}', "
        f"리스크성향 '{risk_level}' 조건을 종합한 성장 평가입니다. "
        f"{ENTITY_TYPE_CONTEXT_NOTES['manual_note']}"
    )

    _KEY_KO = {"training_intensity": "훈련강도", "playing_opportunity": "출전기회", "league_level": "리그수준"}
    score_reason_parts = []
    for key, level_label in [
        ("training_intensity", training_level),
        ("playing_opportunity", playing_level),
        ("league_level", league_level),
    ]:
        score_reason_parts.append(f"{_KEY_KO.get(key, key)} '{level_label}': {LEVEL_DESCRIPTIONS[key][level_label]}")
    score_reason_parts.append(f"리스크성향 '{risk_level}': {LEVEL_DESCRIPTIONS['risk_tendency'][risk_level]}")

    if scores.get("self_attribute") is not None:
        score_reason_parts.append(f"직접 입력한 능력치 평균이 능력치 점수({scores['self_attribute'] * 100:.0f}점)에 반영되었습니다.")
    else:
        score_reason_parts.append("능력치 입력값이 없어 능력치 점수 항목은 평가에서 제외되고 나머지 항목 비중이 재조정되었습니다.")

    score_reason = " ".join(score_reason_parts)

    strengths = []
    risks = []
    if training_level in ("높음", "매우 높음"):
        strengths.append(f"훈련강도 '{training_level}': {LEVEL_DESCRIPTIONS['training_intensity'][training_level]}")
    else:
        risks.append(f"훈련강도 '{training_level}': {LEVEL_DESCRIPTIONS['training_intensity'][training_level]}")

    if playing_level in ("높음", "매우 높음"):
        strengths.append(f"출전기회 '{playing_level}': {LEVEL_DESCRIPTIONS['playing_opportunity'][playing_level]}")
    else:
        risks.append(f"출전기회 '{playing_level}': {LEVEL_DESCRIPTIONS['playing_opportunity'][playing_level]}")

    if league_level in ("높음", "매우 높음"):
        strengths.append(f"리그난이도 '{league_level}': {LEVEL_DESCRIPTIONS['league_level'][league_level]}")
    else:
        risks.append(f"리그난이도 '{league_level}': {LEVEL_DESCRIPTIONS['league_level'][league_level]}")

    risks.append(f"리스크성향 '{risk_level}': {LEVEL_DESCRIPTIONS['risk_tendency'][risk_level]}")
    risks.extend(risk_penalty.get("notes", []))

    if not strengths:
        strengths.append("현재 입력 조건에서는 뚜렷한 강점 요인이 확인되지 않았습니다.")

    recommendations = []
    if playing_level in ("낮음", "보통") and training_level in ("높음", "매우 높음"):
        recommendations.append("훈련강도는 높지만 출전기회가 부족합니다. 임대 등을 통해 실전 출전 시간을 함께 확보하는 전략이 필요합니다.")
    if league_level in ("높음", "매우 높음") and risk_level == "도전형":
        recommendations.append("리그난이도가 높고 리스크성향이 도전형이므로, 적응 실패 위험을 줄이기 위해 훈련강도를 단계적으로 조절하는 것이 좋습니다.")
    if risk_level == "안정형" and growth_score < 50:
        recommendations.append("안정형 리스크성향은 안전하지만 성장 속도가 느릴 수 있습니다. 출전기회나 훈련강도를 한 단계 높여보는 시나리오도 함께 비교해 보세요.")
    if not recommendations:
        recommendations.append("현재 입력 조건은 비교적 균형 잡혀 있습니다. 출전 시간을 안정적으로 확보하면서 현재 성장 속도를 유지하는 것이 좋습니다.")

    data_limitations = [
        "직접 입력한 능력치와 환경 설정 기반 분석입니다. 시장가치 및 실제 출전 기록은 참조 선수가 연결된 경우에만 표시됩니다.",
    ]
    if scores.get("self_attribute") is None:
        data_limitations.append("능력치 입력값이 없어 능력치 점수 항목은 제외되었습니다.")

    return {
        "summary": summary,
        "score_reason": score_reason,
        "strengths": strengths,
        "risks": risks,
        "recommendations": recommendations,
        "data_limitations": data_limitations,
    }


def explain_ceiling_variables(ceiling_model):
    """α, γ, β, training_multiplier, Δleague가 각각 무엇을 의미하는지 한 문장씩 설명한다."""
    levels = ceiling_model.get("levels", {})

    return [
        f"α(출전 확률/출전 기회) = {ceiling_model['alpha']} — 출전기회 '{levels.get('playing_opportunity', '-')}' 설정을 반영한 값으로, "
        "실전에서 성장 자극을 받을 확률을 의미합니다.",
        f"γ(리그 난이도) = {ceiling_model['gamma']} — 리그난이도 '{levels.get('league_level', '-')}' 설정을 반영한 값으로, "
        "환경 수준이 성장 ceiling(한계치)에 미치는 영향을 의미합니다.",
        f"β(부상/적응 실패 리스크) = {ceiling_model['beta']} — 리스크성향 '{levels.get('risk_tendency', '-')}' 설정을 반영한 값으로, "
        "부상이나 새로운 환경 적응 실패로 인한 성장 손실 위험을 의미합니다.",
        f"training_multiplier(훈련 강도 배수) = {ceiling_model['training_multiplier']} — 훈련강도 '{levels.get('training_intensity', '-')}' "
        "설정을 반영한 값으로, 성장 속도(곡선의 기울기)를 조절합니다.",
        f"Δleague(환경 변화량) = {ceiling_model['delta_league']} — '{ceiling_model.get('scenario_label')}' 시나리오에 해당하는 "
        "리그/환경 이동의 변화 크기를 의미합니다.",
    ]


def build_scenario_strengths(ceiling_model):
    """어떤 선택값이 Ceiling Scenario Adjustment를 끌어올렸는지 정리한다."""
    levels = ceiling_model.get("levels", {})
    strengths = []

    if levels.get("playing_opportunity") in ("높음", "매우 높음"):
        strengths.append(f"출전기회 '{levels['playing_opportunity']}' 설정(α={ceiling_model['alpha']})이 성장 보정값을 끌어올리는 주요 요인입니다.")
    if levels.get("league_level") in ("높음", "매우 높음"):
        strengths.append(f"리그난이도 '{levels['league_level']}' 설정(γ={ceiling_model['gamma']})이 성장 ceiling을 높이는 요인입니다.")
    if levels.get("training_intensity") in ("높음", "매우 높음"):
        strengths.append(f"훈련강도 '{levels['training_intensity']}' 설정(training_multiplier={ceiling_model['training_multiplier']})이 성장 속도를 가속합니다.")
    if ceiling_model["scenario_adjustment"] > 0:
        strengths.append(f"Ceiling Scenario Adjustment가 +{ceiling_model['scenario_adjustment']}점으로 Real Data Growth Baseline에 긍정적으로 반영되었습니다.")

    if not strengths:
        strengths.append("현재 시나리오 설정에서는 뚜렷한 긍정 보정 요인이 확인되지 않았습니다.")

    return strengths


def build_scenario_risks(ceiling_model):
    """어떤 선택값이 β(리스크)나 Scenario Adjustment를 낮췄는지 정리한다."""
    levels = ceiling_model.get("levels", {})
    risks = []

    if levels.get("career_choice") in ("loan", "transfer") and levels.get("playing_opportunity") in ("낮음", "보통"):
        risks.append(f"이적/임대 + 출전기회 '{levels['playing_opportunity']}' 조합은 적응 실패 리스크(β={ceiling_model['beta']})를 높입니다.")
    if levels.get("risk_tendency") == "도전형":
        risks.append(f"리스크성향 '도전형'(β={ceiling_model['beta']})은 부상/적응 실패 가능성을 높입니다.")
    if levels.get("league_level") == "매우 높음" and levels.get("career_choice") in ("loan", "transfer"):
        risks.append("매우 높은 리그난이도로의 이동은 적응 실패 시 ceiling 손실 위험이 큽니다.")
    if ceiling_model["scenario_adjustment"] < 0:
        risks.append(f"Ceiling Scenario Adjustment가 {ceiling_model['scenario_adjustment']}점으로 Real Data Growth Baseline을 낮추는 방향으로 반영되었습니다.")

    risks.extend(note for note in ceiling_model.get("notes", []) if "추가로 증가" in note or "범위를 벗어나" in note)

    if not risks:
        risks.append("현재 시나리오 설정에서는 뚜렷한 리스크 요인이 확인되지 않았습니다.")

    return risks


def build_scenario_recommendations(ceiling_model):
    """Ceiling Scenario Adjustment 결과를 바탕으로 추천 성장 전략을 만든다."""
    levels = ceiling_model.get("levels", {})
    recommendations = []

    if ceiling_model["scenario_adjustment"] > 0:
        recommendations.append("현재 시나리오는 Real Data Growth Baseline보다 높은 ceiling을 제공합니다. 출전 기회를 안정적으로 확보해 이 보정값을 실제 성장으로 전환하는 것이 중요합니다.")
    elif ceiling_model["scenario_adjustment"] < 0:
        recommendations.append("현재 시나리오는 리스크 대비 보상이 낮습니다. 출전기회·리그난이도·리스크성향 설정을 조정해 더 안전한 시나리오를 함께 비교해 보세요.")
    else:
        recommendations.append("현재 시나리오는 Real Data Growth Baseline과 큰 차이가 없는 중립적인 보정입니다.")

    if levels.get("risk_tendency") == "도전형" and levels.get("playing_opportunity") in ("낮음", "보통"):
        recommendations.append("도전형 리스크 성향과 낮은 출전기회가 함께 선택된 경우, 훈련강도를 조절해 적응 부담을 줄이는 전략이 도움이 될 수 있습니다.")

    return recommendations


def build_coaching_scenario_summary(ceiling_model):
    levels = ceiling_model.get("levels", {})
    adjustment = ceiling_model.get("scenario_adjustment", 0)
    high_risk = (
        levels.get("training_intensity") == "매우 높음"
        or levels.get("league_level") == "매우 높음"
        or levels.get("playing_opportunity") == "낮음"
        or levels.get("risk_tendency") == "도전형"
    )

    if adjustment > 5 and high_risk:
        nature = "성장 자극은 크지만 회복과 출전 관리가 반드시 필요한 도전형 시나리오"
    elif adjustment > 0:
        nature = "성장 가능성과 위험을 비교적 균형 있게 가져가는 시나리오"
    elif adjustment < 0:
        nature = "현재 조건에서는 성장 이득보다 정체 또는 적응 실패 위험이 큰 시나리오"
    else:
        nature = "기본 성장 흐름을 크게 바꾸지 않는 중립 시나리오"

    return f"현재 선택은 {nature}입니다."


def build_coaching_training_directions(growth_insight, ceiling_model):
    if growth_insight.get("mode") == "manual_prototype":
        directions = ["직접 입력한 능력치 기준으로 보완이 필요한 기술 항목을 우선 선정하고, 주간 훈련에서 한두 항목씩 집중하는 것이 좋습니다."]
        self_attribute = growth_insight.get("scores", {}).get("self_attribute")
        if self_attribute is not None and self_attribute < 0.6:
            directions.append("자기평가 능력치가 낮은 편이므로 기본 기술과 피지컬을 먼저 안정시킨 뒤 역할별 훈련으로 확장하는 편이 좋습니다.")
    else:
        directions = build_recommendations(growth_insight.get("features", {}))
    levels = ceiling_model.get("levels", {})

    if levels.get("training_intensity") == "매우 높음":
        directions.append("고강도 세션 사이에 회복일과 부하 관리 세션을 배치해 훈련 효과가 부상이나 번아웃으로 상쇄되지 않도록 해야 합니다.")
    if levels.get("playing_opportunity") in ("낮음", "보통"):
        directions.append("훈련만 늘리기보다 로테이션 출전, 임대, 하위 리그 실전 경험을 통해 경기 감각과 판단 속도를 확보해야 합니다.")

    return directions


def build_coaching_expected_benefits(ceiling_model):
    levels = ceiling_model.get("levels", {})
    benefits = []

    if levels.get("training_intensity") in ("높음", "매우 높음"):
        benefits.append("높은 훈련강도는 피지컬, 활동량, 경기 체력 향상에 도움이 될 수 있습니다.")
    if levels.get("playing_opportunity") in ("높음", "매우 높음"):
        benefits.append("충분한 출전기회는 경기 감각, 판단 속도, 실전 자신감을 끌어올릴 수 있습니다.")
    if levels.get("league_level") in ("높음", "매우 높음"):
        benefits.append("높은 리그난이도는 강한 압박과 빠른 경기 템포 적응을 돕고 성장 상한선을 높일 수 있습니다.")
    if not benefits:
        benefits.append("현재 환경은 급격한 변화보다 안정적인 적응과 기본기 유지에 유리합니다.")

    return benefits


def build_coaching_neglect_risks(growth_insight, ceiling_model):
    features = growth_insight.get("features", {})
    levels = ceiling_model.get("levels", {})
    risks = []

    if levels.get("playing_opportunity") in ("낮음", "보통"):
        risks.append("실전 출전을 확보하지 못하면 경기 감각과 판단 속도가 둔화되고 성장 정체로 이어질 수 있습니다.")
    if levels.get("training_intensity") == "낮음":
        risks.append("훈련 자극이 부족하면 피지컬 성장과 상위 리그 템포 적응이 늦어질 수 있습니다.")
    mentality = features.get("mentality_strength", {})
    if mentality.get("status") == "ok" and mentality.get("score") is not None and mentality["score"] < 0.4:
        risks.append("멘탈리티 보완을 소홀히 하면 압박 상황 실수와 자신감 저하가 반복될 수 있습니다.")
    contribution = features.get("contribution_score", {})
    if contribution.get("status") == "ok" and contribution.get("score") is not None and contribution["score"] < 0.4:
        risks.append("기여도 개선이 없으면 결정적 장면에서의 영향력과 찬스 메이킹이 제한될 수 있습니다.")
    if not risks:
        risks.append("현재 강점을 유지하더라도 회복과 출전 계획을 점검하지 않으면 성장 효과가 실제 경기력으로 이어지지 않을 수 있습니다.")

    return risks


def build_coaching_risk_warnings(ceiling_model):
    levels = ceiling_model.get("levels", {})
    warnings = []

    if levels.get("training_intensity") == "매우 높음" and levels.get("playing_opportunity") == "매우 높음":
        warnings.append("훈련과 출전 부하가 모두 매우 높아 과부하, 부상, 번아웃 위험이 큽니다. 회복일과 출전량 상한을 함께 관리해야 합니다.")
    elif levels.get("training_intensity") == "매우 높음":
        warnings.append("매우 높은 훈련강도는 회복이 늦어질 경우 피로 누적과 부상으로 이어질 수 있습니다.")

    if levels.get("league_level") == "매우 높음" and levels.get("playing_opportunity") in ("낮음", "보통"):
        warnings.append("리그 수준은 크게 높아지지만 출전이 부족해 벤치 정체와 경기 감각 저하가 발생할 수 있습니다.")
    if levels.get("career_choice") == "transfer" and levels.get("playing_opportunity") == "낮음":
        warnings.append("출전 계획이 불확실한 이적은 성장보다 적응 실패와 벤치 정체 가능성을 높입니다.")
    if levels.get("league_level") in ("높음", "매우 높음") and levels.get("risk_tendency") == "도전형":
        warnings.append("높은 리그 수준과 도전형 선택이 겹쳐 초기 적응 실패와 자신감 저하 위험이 있습니다.")

    return warnings or ["현재 선택 조합에서는 즉시 경고할 고위험 요인이 크지 않지만, 출전 시간과 회복 상태를 계속 관찰해야 합니다."]


def build_coaching_career_strategy(ceiling_model):
    levels = ceiling_model.get("levels", {})
    strategy = []

    if levels.get("career_choice") == "transfer" and levels.get("playing_opportunity") in ("낮음", "보통"):
        strategy.append("빅리그 즉시 이적보다 주전 경쟁이 가능하거나 출전 시간이 보장되는 팀을 우선 검토하는 편이 안정적입니다.")
    elif levels.get("career_choice") == "loan" and levels.get("playing_opportunity") in ("높음", "매우 높음"):
        strategy.append("현재 임대 시나리오는 실전 경험 확보에 유리하므로 역할과 출전 시간 보장을 계약 단계에서 확인하는 것이 중요합니다.")
    elif levels.get("career_choice") == "stay" and levels.get("playing_opportunity") in ("높음", "매우 높음"):
        strategy.append("잔류 후 꾸준한 출전으로 성장 기반을 만든 뒤 더 높은 리그로 이동하는 단계적 전략이 적합합니다.")
    else:
        strategy.append("훈련강도보다 실제 출전 가능성과 팀 내 역할을 우선해 다음 커리어 선택을 비교하는 것이 좋습니다.")

    if levels.get("training_intensity") == "매우 높음":
        strategy.append("훈련강도는 회복 상태에 따라 주기적으로 낮추고, 출전이 몰리는 기간에는 부하를 분산해야 합니다.")

    return strategy


def build_ceiling_explanation(growth_insight):
    """growth_insight["ceiling_model"]을 사람이 이해할 수 있는 설명으로 변환한다.

    ceiling_model이 없으면 None을 반환한다.
    """
    ceiling_model = growth_insight.get("ceiling_model")
    if not ceiling_model:
        return None

    potential_base = ceiling_model["potential_base"]
    scenario_adjustment = ceiling_model["scenario_adjustment"]
    final_score = ceiling_model["final_growth_score"]

    base_text = f"{potential_base:.1f}점" if potential_base is not None else "산정 불가"
    final_text = f"{final_score:.1f}점" if final_score is not None else "산정 불가"

    scenario_nature = build_coaching_scenario_summary(ceiling_model)
    ceiling_summary = (
        f"{scenario_nature} "
        f"기본 성장 평가 {base_text}에 현재 환경의 기회와 위험을 반영한 최종 성장 점수는 {final_text}입니다."
    )

    return {
        "ceiling_summary": ceiling_summary,
        "scenario_variables": {
            "alpha": ceiling_model["alpha"],
            "gamma": ceiling_model["gamma"],
            "beta": ceiling_model["beta"],
            "training_multiplier": ceiling_model["training_multiplier"],
            "delta_league": ceiling_model["delta_league"],
        },
        "variable_explanations": explain_ceiling_variables(ceiling_model),
        "scenario_adjustment": scenario_adjustment,
        "final_growth_score": final_score,
        "scenario_strengths": build_scenario_strengths(ceiling_model),
        "scenario_risks": build_scenario_risks(ceiling_model),
        "scenario_recommendations": build_scenario_recommendations(ceiling_model),
        "scenario_nature": scenario_nature,
        "coaching_summary": ceiling_summary,
        "training_directions": build_coaching_training_directions(growth_insight, ceiling_model),
        "expected_benefits": build_coaching_expected_benefits(ceiling_model),
        "neglect_risks": build_coaching_neglect_risks(growth_insight, ceiling_model),
        "risk_warnings": build_coaching_risk_warnings(ceiling_model),
        "career_strategy": build_coaching_career_strategy(ceiling_model),
    }


def build_growth_explanation(growth_insight, player_context=None):
    """growth_model의 Growth Insight를 받아 설명 구조(dict)를 만든다.

    matched / transfermarkt_only / fm_profile_only / manual_note 모드에 따라
    설명 방식을 구분한다. growth_insight에 ceiling_model이 있으면
    `ceiling_explanation` key를 추가로 생성한다.
    """
    if growth_insight.get("mode") == "manual_prototype":
        explanation = _build_manual_explanation(growth_insight, player_context)
    else:
        explanation = _build_data_driven_explanation(growth_insight, player_context)

    explanation["ceiling_explanation"] = build_ceiling_explanation(growth_insight)
    explanation["gemini_ready_payload"] = build_gemini_ready_payload(growth_insight, explanation, player_context)
    return explanation


def build_gemini_ready_payload(growth_insight, explanation, player_context=None):
    """나중에 Gemini API에 그대로 전달할 수 있는 구조화된 payload를 만든다.

    이번 세션에서는 Gemini API를 호출하지 않으며, 이 payload는 세션 내에서만
    사용되는 구조화 데이터다.
    """
    return {
        "player_context": player_context or {},
        "mode": growth_insight.get("mode"),
        "entity_type": growth_insight.get("entity_type"),
        "growth_score": growth_insight.get("growth_score"),
        "growth_status": growth_insight.get("growth_status"),
        "features": growth_insight.get("features"),
        "levels": growth_insight.get("levels"),
        "scores": growth_insight.get("scores"),
        "risk_penalty": growth_insight.get("risk_penalty"),
        "ceiling_model": growth_insight.get("ceiling_model"),
        "rule_based_explanation": {
            "summary": explanation["summary"],
            "score_reason": explanation["score_reason"],
            "strengths": explanation["strengths"],
            "risks": explanation["risks"],
            "recommendations": explanation["recommendations"],
            "data_limitations": explanation["data_limitations"],
        },
        "ceiling_explanation": explanation.get("ceiling_explanation"),
        "instructions_for_gemini": (
            "위 rule_based_explanation과 ceiling_explanation을 참고하여, 같은 데이터를 기반으로 더 자연스러운 "
            "한국어 스카우팅 리포트 문체로 다시 작성해 주세요. 점수/사실 자체를 바꾸지 말고 "
            "설명 톤만 다듬어 주세요."
        ),
    }
