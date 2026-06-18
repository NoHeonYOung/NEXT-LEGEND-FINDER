"""직접 입력(Manual Prospect) 유망주 관련 순수 helper 모음.

Streamlit UI(views/manual_prospect.py, views/scouting_notes.py)와 app.py 양쪽에서
재사용한다. 이 모듈 자체는 app.py를 import하지 않는다.
"""

import pandas as pd

from analysis_helpers import (
    attr_label,
    numeric_attr,
    parse_json_field,
    position_training_hint,
    readable_setting,
    safe_float,
)
from services.db import query_df


# 실제 선수 선택 <-> 직접 입력 유망주 생성 시 서로 정리해야 하는 분석/멘토/리포트 관련
# session_state key 목록. (selected_entity_type/selected_player_id/selected_profile_id 등
# 페이지별 식별 key는 호출부에서 별도로 처리한다.)
STALE_SELECTION_KEYS = [
    "selected_mentor_profile_id",
    "selected_mentor_name",
    "mentor_summary",
    "env_settings",
    "simulation_result",
    "generated_report_sections",
    "generated_report",
    "generated_report_text",
    "growth_insight",
    "growth_explanation",
    "ceiling_growth_insight",
    "ceiling_growth_explanation",
    "ceiling_growth_context",
]


def safe_text(value, fallback="이름 없는 직접 입력 노트"):
    if value is None:
        return fallback
    if isinstance(value, float) and pd.isna(value):
        return fallback
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else fallback
    if pd.isna(value):
        return fallback
    return str(value)


def get_career_settings(env_settings):
    if not isinstance(env_settings, dict):
        return {}

    career_settings = env_settings.get("career_settings")
    if isinstance(career_settings, dict):
        return career_settings

    legacy = {}
    for key in ["training_intensity", "playing_time_opportunity", "league_difficulty", "career_choice", "risk_level"]:
        if key in env_settings:
            legacy[key] = env_settings.get(key)

    nested = env_settings.get("env_settings") if isinstance(env_settings.get("env_settings"), dict) else None
    if isinstance(nested, dict):
        nested_career = nested.get("career_settings")
        if isinstance(nested_career, dict):
            return nested_career
        for key in ["training_intensity", "playing_time_opportunity", "league_difficulty", "career_choice", "risk_level"]:
            if key in nested and key not in legacy:
                legacy[key] = nested.get(key)

    return legacy


def normalize_env_settings(env_settings):
    if not isinstance(env_settings, dict):
        return {"note_type": "manual_custom_prospect", "career_settings": {}}

    career_settings = get_career_settings(env_settings)
    normalized = {
        "note_type": env_settings.get("note_type", "manual_custom_prospect"),
        "manual_player": env_settings.get("manual_player") if isinstance(env_settings.get("manual_player"), dict) else {},
        "manual_attributes": env_settings.get("manual_attributes") if isinstance(env_settings.get("manual_attributes"), dict) else {},
        "career_settings": career_settings,
        "selected_mentor_profile_id": env_settings.get("selected_mentor_profile_id"),
        "selected_mentor_name": env_settings.get("selected_mentor_name"),
    }
    return normalized


def setting_summary(key, value):
    if key == "training_intensity":
        number = safe_float(value, None)
        if number is None:
            return "훈련 강도: 정보 없음"
        if number >= 1.4:
            return "훈련 강도: 높음 — 빠른 성장을 기대할 수 있지만 피로 누적과 부상 위험이 증가할 수 있습니다."
        if number >= 0.9:
            return "훈련 강도: 보통 — 성장과 회복의 균형이 좋은 안정적 선택입니다."
        return "훈련 강도: 낮음 — 부상 위험은 낮지만 단기 성장 속도가 느릴 수 있습니다."

    if key == "playing_time_opportunity":
        number = safe_float(value, None)
        if number is None:
            return "출전 기회: 정보 없음"
        if number >= 0.7:
            return "출전 기회: 높음 — 경기 경험을 통해 빠른 성장을 기대할 수 있지만 체력 부담도 커질 수 있습니다."
        if number >= 0.35:
            return "출전 기회: 보통 — 훈련과 실전의 균형이 잡힌 환경입니다."
        return "출전 기회: 낮음 — 실전 경험이 부족해 성장 속도가 제한될 수 있습니다."

    if key == "league_difficulty":
        mapping = {"low": "낮음 — 적응은 쉽지만 성장 자극이 부족할 수 있습니다.",
                   "medium": "보통 — 현재 단계에서 안정적으로 성장하기 좋은 환경입니다.",
                   "high": "높음 — 경쟁 수준이 높아 성장 자극은 크지만 출전 기회가 줄 수 있습니다.",
                   "elite": "매우 높음 — 상위 환경 도전이 크지만 적응 실패와 벤치 리스크가 큽니다."}
        return f"리그/팀 수준: {mapping.get(value, '알 수 없음')}"

    if key == "career_choice":
        mapping = {"stay": "잔류 — 익숙한 환경에서 안정적으로 성장할 수 있습니다.",
                   "loan": "임대 — 출전 시간을 확보해 단기 성장 가능성을 높일 수 있습니다.",
                   "transfer": "이적 — 환경 변화가 큰 성장 자극이 되지만 적응 실패 리스크가 있습니다."}
        return f"커리어 선택: {mapping.get(value, '알 수 없음')}"

    if key == "risk_level":
        mapping = {"safe": "안정형 — 부상과 실패 가능성을 줄이는 대신 성장 속도는 완만할 수 있습니다.",
                   "normal": "균형형 — 성장과 리스크를 적절히 조절하는 선택입니다.",
                   "aggressive": "공격형 — 높은 성장 가능성을 노리지만 부상이나 적응 실패 위험이 커집니다."}
        return f"리스크 성향: {mapping.get(value, '알 수 없음')}"

    return f"{key}: {value}"


def manual_similarity_candidates(manual_player, manual_attributes, limit=5):
    try:
        profiles = query_df("""
            select profile_id, player_id, name, age, club, nationality, position, attributes_jsonb, mentality_jsonb
            from player_profiles
            where attributes_jsonb is not null
            limit 200
        """, ())
    except Exception:
        return []

    mapping = {
        "speed": ["Acc", "Pac", "Agi"],
        "dribble": ["Dri", "Tec", "Fir"],
        "finishing": ["Fin", "Cmp", "OtB"],
        "passing": ["Pas", "Vis", "Dec"],
        "physical": ["Str", "Sta", "Bal", "Jum"],
        "defending": ["Tck", "Mar", "Pos"],
        "work_rate": ["Wor", "Sta"],
        "teamwork": ["Tea"],
        "determination": ["Det"],
        "pressing": ["Pres", "Cmp"],
    }

    manual_position = (manual_player.get("position") or "").lower()
    candidates = []

    for _, row in profiles.iterrows():
        attrs = parse_json_field(row.get("attributes_jsonb")) or {}
        score = 0.0
        common_terms = []
        diff_terms = []
        count = 0

        for label, keys in mapping.items():
            manual_value = safe_float(manual_attributes.get(label), 0)
            values = [numeric_attr(attrs, key) for key in keys]
            values = [value for value in values if value is not None]
            if not values:
                continue
            avg_candidate = sum(values) / len(values)
            diff = abs((manual_value * 2.0) - avg_candidate)
            score += max(0.0, 100.0 - diff * 6.0)
            count += 1
            if diff <= 2.5:
                common_terms.append(attr_label(keys[0], with_code=False))
            else:
                diff_terms.append(attr_label(keys[0], with_code=False))

        if count == 0:
            continue

        score = score / count
        if manual_position and str(row.get("position") or "").lower():
            if manual_position in str(row.get("position") or "").lower() or str(row.get("position") or "").lower() in manual_position:
                score += 6
        if safe_float(manual_attributes.get("growth_potential"), 0) >= 7:
            score += 2

        score = min(99.9, max(0.0, score))
        candidates.append({
            "profile_id": row.get("profile_id"),
            "player_id": row.get("player_id"),
            "name": row.get("name") or "-",
            "age": row.get("age"),
            "club": row.get("club") or "-",
            "position": row.get("position") or "-",
            "nationality": row.get("nationality") or "-",
            "similarity": round(score, 1),
            "common_strengths": ", ".join(common_terms[:3]) or "전반적 스타일 유사성",
            "difference_hint": ", ".join(diff_terms[:3]) or "세부 차이가 제한적입니다.",
            "profile": row,
        })

    candidates = sorted(candidates, key=lambda item: item["similarity"], reverse=True)
    return candidates[:limit]


def filter_mentor_candidates_by_age(candidates, target_age, age_key="age", exclude_ids=None, id_key="profile_id", min_results=3):
    """멘토 후보 목록에서 너무 어린 후보를 걸러낸다.

    규칙: mentor_min_age = max(28, target_age + 5). 결과가 min_results보다 적으면
    fallback_min_age = max(26, target_age + 3) 기준으로 완화해서 다시 시도한다
    (이 경우에도 26세 미만은 계속 제외한다).

    target_age가 없으면(None) 나이 기준으로 판단할 수 없으므로 원본 후보 목록을
    그대로 반환한다.

    Returns: (filtered_candidates, used_fallback)
    """
    target_age = safe_float(target_age, None)
    if target_age is None:
        return list(candidates), False

    exclude_ids = {str(value) for value in (exclude_ids or []) if value is not None}

    def candidate_age(item):
        value = item.get(age_key) if hasattr(item, "get") else None
        value = safe_float(value, None)
        return value

    def is_excluded(item):
        candidate_id = item.get(id_key) if hasattr(item, "get") else None
        return candidate_id is not None and str(candidate_id) in exclude_ids

    primary_min_age = max(28.0, target_age + 5)
    fallback_min_age = max(26.0, target_age + 3)

    eligible = [item for item in candidates if not is_excluded(item)]

    primary = [item for item in eligible if candidate_age(item) is not None and candidate_age(item) >= primary_min_age]
    if len(primary) >= min_results:
        return primary, False

    fallback = [item for item in eligible if candidate_age(item) is not None and candidate_age(item) >= fallback_min_age]
    if len(fallback) > len(primary):
        return fallback, True

    return primary, False


def manual_player_profile_panel_inputs(manual_player):
    """render_player_profile_panel(player, profile)에 전달할 (player, profile) dict를
    직접 입력 유망주 정보(manual_player)로부터 합성한다."""
    manual_player = manual_player if isinstance(manual_player, dict) else {}
    player = {
        "name": manual_player.get("name") or "직접 입력 유망주",
        "current_club_name": manual_player.get("club"),
        "country_of_citizenship": manual_player.get("nationality"),
        "position": manual_player.get("position"),
        "sub_position": manual_player.get("sub_position"),
        "foot": manual_player.get("foot"),
        "market_value_in_eur": None,
        "highest_market_value_in_eur": None,
        "image_url": None,
    }
    profile = {"age": manual_player.get("age")}
    return player, profile


def build_manual_analysis(manual_player, manual_attributes, env_settings, simulation_result):
    manual_position = safe_text(manual_player.get("position"), "포지션 미입력")
    manual_name = safe_text(manual_player.get("name"), "이름 없는 직접 입력 노트")
    manual_age = manual_player.get("age") or "-"
    manual_club = safe_text(manual_player.get("club"), "소속팀 미입력")
    manual_nationality = safe_text(manual_player.get("nationality"), "국적 미입력")

    attr_scores = {
        "속도/기동성": safe_float(manual_attributes.get("speed"), 0),
        "드리블": safe_float(manual_attributes.get("dribble"), 0),
        "결정력": safe_float(manual_attributes.get("finishing"), 0),
        "패스/시야": safe_float(manual_attributes.get("passing"), 0),
        "피지컬": safe_float(manual_attributes.get("physical"), 0),
        "수비력": safe_float(manual_attributes.get("defending"), 0),
        "활동량": safe_float(manual_attributes.get("work_rate"), 0),
        "팀워크": safe_float(manual_attributes.get("teamwork"), 0),
        "의지력": safe_float(manual_attributes.get("determination"), 0),
        "압박 대처": safe_float(manual_attributes.get("pressing"), 0),
        "성장 잠재력": safe_float(manual_attributes.get("growth_potential"), 0),
    }

    strengths = sorted(attr_scores.items(), key=lambda item: item[1], reverse=True)[:3]
    weaknesses = sorted(attr_scores.items(), key=lambda item: item[1])[:2]
    strength_names = ", ".join([name for name, _ in strengths]) or "강점 데이터 부족"
    weakness_names = ", ".join([name for name, _ in weaknesses]) or "보완 데이터 부족"

    position_hint = position_training_hint(manual_position, weakness_names)
    training_recommendations = [
        "3개월: 가장 시급한 약점인 " + weakness_names + "을 중심으로 반복적인 훈련을 설계합니다.",
        "6개월: " + manual_position + " 역할에 꼭 필요한 핵심 능력인 " + strength_names + "을 강화해 실제 경기 적용력과 전술 적응력을 끌어올립니다.",
        "1년: 성장 잠재력과 실행력의 균형을 맞추며, 강점을 확장하는 동시에 약점을 보완하는 로드맵을 진행합니다.",
    ]

    risk_factors = []
    if safe_float(env_settings.get("training_intensity"), 0) >= 1.4:
        risk_factors.append("훈련 강도가 높아 피로 누적과 부상 위험이 커질 수 있습니다.")
    if str(env_settings.get("league_difficulty", "")).lower() in ("high", "elite"):
        risk_factors.append("리그 난이도가 높아 적응 부담과 출전 기회 변수에 민감할 수 있습니다.")
    if str(env_settings.get("risk_level", "")).lower() == "aggressive":
        risk_factors.append("공격형 리스크 성향은 성장 기회는 크지만 적응 실패 가능성도 함께 증가합니다.")

    career_advice = "현재 입력값 기준으로는 " + readable_setting("career_choice", env_settings.get("career_choice")) + "이 가장 적절한 선택지입니다. "
    if env_settings.get("career_choice") == "loan":
        career_advice += "출전 시간이 부족하다면 한 시즌 임대가 성장 속도를 높일 수 있습니다."
    elif env_settings.get("career_choice") == "transfer":
        career_advice += "환경 변화는 성장 자극이 크지만, 현재 피지컬/압박 대처가 낮다면 리스크를 먼저 점검해야 합니다."
    else:
        career_advice += "안정적인 환경에서 현재 강점을 유지하며 성장하는 것이 우선입니다."

    overall = (
        f"{manual_name}은(는) 나이 {manual_age}세, {manual_position}, {manual_club} 소속으로 보이며, "
        f"{strength_names}이 핵심 강점으로 보입니다. 현재 입력값과 시뮬레이션 결과를 종합하면, "
        f"성장 잠재력 {safe_float(manual_attributes.get('growth_potential'), 0)}/10 수준에서 {manual_nationality}의 환경 속에서 안정적인 성장을 기대할 수 있습니다."
    )

    mentor_candidates = manual_similarity_candidates(manual_player, manual_attributes, limit=5)
    mentor_guide = "이 선수는 현재 입력값 기준으로 멘토 후보와의 공통 강점을 바탕으로 성장 루트를 설계할 수 있습니다. " + position_hint

    return {
        "overall_summary": overall,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "strength_names": strength_names,
        "weakness_names": weakness_names,
        "training_recommendations": training_recommendations,
        "career_advice": career_advice,
        "risk_factors": risk_factors,
        "mentor_candidates": mentor_candidates,
        "mentor_guide": mentor_guide,
        "simulation_result": simulation_result,
        "env_settings": env_settings,
        "manual_player": manual_player,
        "manual_attributes": manual_attributes,
    }
