"""실제 DB 데이터(players/appearances/player_valuations/player_profiles) 기반
성장 예측(Growth Score) 모델.

app.py를 import하지 않는다(순환 import 방지). DB 조회나 session_state 접근은
하지 않으며, 이미 조회된 player/profile/appearances/valuations(dict, DataFrame)을
입력으로 받아 feature 점수와 Growth Score를 계산하는 순수 함수만 담는다.

Growth Score = 0~100
  시장가치 흐름 30% + 출전 기회 20% + 공격/수비 기여도 15% + 나이 잠재력 15%
  + FM 능력치 10% + 멘탈리티 10% - 리스크 패널티

일부 feature가 unavailable이면 해당 항목을 제외하고 남은 weight를 재정규화한다.
"""

import math
from datetime import date

import pandas as pd

from analysis_helpers import MENTALITY_KEYS, numeric_attr, parse_json_field, safe_float


GROWTH_WEIGHTS = {
    "market_momentum": 0.30,
    "playing_opportunity": 0.20,
    "contribution_score": 0.15,
    "age_potential": 0.15,
    "attribute_strength": 0.10,
    "mentality_strength": 0.10,
}

FEATURE_LABELS = {
    "market_momentum": "시장가치 흐름",
    "playing_opportunity": "출전 기회",
    "contribution_score": "공격/수비 기여도",
    "age_potential": "나이 잠재력",
    "attribute_strength": "FM 능력치",
    "mentality_strength": "멘탈리티",
}

ATTACK_POSITION_HINTS = ("attack", "forward", "winger", "striker", "wing")

RECENT_MINUTES_BASELINE = 900.0  # 최근 10경기 x 90분 기준
RECENT_APPEARANCES_LIMIT = 10
RECENT_FORM_LIMIT = 10  # market_momentum 비교 기준(약 6개월~1년)
MARKET_MOMENTUM_LOOKBACK_DAYS = 180

# Manual Note(직접 입력) prototype 매핑값
TRAINING_INTENSITY_SCORES = {"낮음": 0.35, "보통": 0.55, "높음": 0.75, "매우 높음": 0.90}
LEAGUE_LEVEL_SCORES = {"낮음": 0.35, "보통": 0.55, "높음": 0.75, "매우 높음": 0.90}
PLAYING_OPPORTUNITY_SCORES = {"낮음": 0.30, "보통": 0.55, "높음": 0.78, "매우 높음": 0.92}
RISK_TENDENCY_PENALTY = {"안정형": 2.0, "균형형": 5.0, "도전형": 8.0}
RISK_TENDENCY_GROWTH_BONUS = {"안정형": 0.0, "균형형": 0.0, "도전형": 3.0}

LEAGUE_LEVEL_FROM_DIFFICULTY = {"low": "낮음", "medium": "보통", "high": "높음", "elite": "매우 높음"}
RISK_TENDENCY_FROM_LEVEL = {"safe": "안정형", "normal": "균형형", "aggressive": "도전형"}

# Ceiling Model (Potential_final = Potential_base + Σ(Δleague × (α × γ × training_multiplier - β))) 매핑값
LEAGUE_DIFFICULTY_GAMMA = {"낮음": 0.5, "보통": 1.0, "높음": 1.25, "매우 높음": 1.5}
PLAYING_OPPORTUNITY_ALPHA = {"낮음": 0.1, "보통": 0.45, "높음": 0.7, "매우 높음": 0.9}
TRAINING_INTENSITY_MULTIPLIER = {"낮음": 1.0, "보통": 1.25, "높음": 1.6, "매우 높음": 2.0}
RISK_TENDENCY_BETA = {"안정형": 0.10, "균형형": 0.25, "도전형": 0.40}

DELTA_LEAGUE_VALUES = {
    "stable_stay": 4,
    "balanced_growth": 7,
    "league_challenge": 10,
    "risky_challenge": 6,
}

CEILING_ADJUSTMENT_MIN = -15
CEILING_ADJUSTMENT_MAX = 15

LEVEL_DESCRIPTIONS = {
    "training_intensity": {
        "낮음": "부상 위험은 낮지만 성장 속도가 제한될 수 있습니다.",
        "보통": "안정성과 성장의 균형이 잡힌 설정입니다.",
        "높음": "성장 자극은 크지만 피로 누적 가능성이 존재합니다.",
        "매우 높음": "단기 성장 가능성은 높지만 부상/번아웃 위험이 증가합니다.",
    },
    "league_level": {
        "낮음": "적응은 쉽지만 성장 자극이 제한적입니다.",
        "보통": "안정적인 경기 경험을 확보할 수 있습니다.",
        "높음": "경쟁 강도가 높아 성장 자극이 크지만 출전 리스크가 있습니다.",
        "매우 높음": "상위 리그 수준의 압박이 있으며, 실패 시 경기 감각 저하 가능성이 있습니다.",
    },
    "playing_opportunity": {
        "낮음": "경기 경험 부족으로 성장이 제한될 수 있습니다.",
        "보통": "로테이션 수준의 성장을 기대할 수 있습니다.",
        "높음": "꾸준한 실전 경험으로 성장에 긍정적입니다.",
        "매우 높음": "주전급 경험이 가능하지만 과부하 위험도 존재합니다.",
    },
    "risk_tendency": {
        "안정형": "성장 속도는 느릴 수 있지만 실패 위험이 낮습니다.",
        "균형형": "성장과 안정의 균형을 추구합니다.",
        "도전형": "성장 잠재력은 크지만 실패/부상/적응 리스크가 증가합니다.",
    },
}


def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def safe_float_or_none(value):
    """value를 float으로 변환한다. 변환 불가/None/NaN이면 None을 반환한다."""
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result):
        return None
    return result


def _unavailable(reason):
    return {"status": "unavailable", "score": None, "detail": {"reason": reason}}


def _ok(score, detail=None):
    return {"status": "ok", "score": clamp(score, 0.0, 1.0), "detail": detail or {}}


def compute_market_momentum(valuations):
    """player_valuations 시계열에서 최근 valuation과 약 6개월~1년 전 valuation을
    비교해 시장가치 흐름 점수(0~1)를 계산한다. valuation이 2개 미만이면 unavailable.
    """
    if valuations is None or len(valuations) == 0:
        return _unavailable("시장가치 데이터가 없습니다.")

    df = valuations.copy()
    df["market_value_in_eur"] = pd.to_numeric(df["market_value_in_eur"], errors="coerce")
    df = df.dropna(subset=["market_value_in_eur", "date"])

    if len(df) < 2:
        return _unavailable("시장가치 데이터가 2개 미만입니다.")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    current_row = df.iloc[-1]
    current_value = float(current_row["market_value_in_eur"])
    current_date = current_row["date"]

    target_date = current_date - pd.Timedelta(days=MARKET_MOMENTUM_LOOKBACK_DAYS)
    past_candidates = df[df["date"] <= target_date]
    if not past_candidates.empty:
        past_row = past_candidates.iloc[-1]
    else:
        past_row = df.iloc[0]

    past_value = float(past_row["market_value_in_eur"])
    past_date = past_row["date"]

    market_growth = math.log((current_value + 1) / (past_value + 1))
    momentum = clamp((market_growth + 0.5) / 1.0, 0, 1)

    return _ok(
        momentum,
        {
            "current_value": current_value,
            "past_value": past_value,
            "current_date": str(current_date.date()),
            "past_date": str(past_date.date()),
            "market_growth": round(market_growth, 4),
            "data_points": len(df),
        },
    )


def compute_playing_opportunity(appearances):
    """appearances에서 최근 출전 시간(분)을 기준으로 출전 기회 점수(0~1)를 계산한다.
    minutes_played가 없으면 출전 횟수를 fallback으로 사용한다.
    """
    if appearances is None or appearances.empty:
        return _unavailable("출전 기록 데이터가 없습니다.")

    recent = appearances.head(RECENT_APPEARANCES_LIMIT)
    minutes = pd.to_numeric(recent["minutes_played"], errors="coerce") if "minutes_played" in recent.columns else pd.Series(dtype=float)

    if minutes.notna().sum() > 0:
        minutes_sum = float(minutes.dropna().sum())
        score = clamp(minutes_sum / RECENT_MINUTES_BASELINE, 0, 1)
        detail = {
            "basis": "minutes",
            "recent_minutes": minutes_sum,
            "baseline_minutes": RECENT_MINUTES_BASELINE,
            "matches_considered": len(recent),
        }
    else:
        count = len(recent)
        score = clamp(count / RECENT_APPEARANCES_LIMIT, 0, 1)
        detail = {
            "basis": "appearance_count",
            "recent_appearances": count,
            "baseline_appearances": RECENT_APPEARANCES_LIMIT,
        }

    return _ok(score, detail)


def compute_contribution_score(appearances, position=None):
    """appearances의 goals/assists/minutes_played로 90분당 공격 포인트를 계산하고,
    포지션에 따른 기준값과 비교해 기여도 점수(0~1)를 계산한다.
    """
    if appearances is None or appearances.empty:
        return _unavailable("출전 기록 데이터가 없습니다.")

    goals = pd.to_numeric(appearances.get("goals"), errors="coerce").fillna(0).sum() if "goals" in appearances.columns else 0.0
    assists = pd.to_numeric(appearances.get("assists"), errors="coerce").fillna(0).sum() if "assists" in appearances.columns else 0.0
    minutes = pd.to_numeric(appearances.get("minutes_played"), errors="coerce").fillna(0).sum() if "minutes_played" in appearances.columns else 0.0

    per90 = (goals + assists) / max(minutes / 90.0, 1.0)

    position_known = bool(position)
    position_lower = (position or "").lower()

    if any(hint in position_lower for hint in ATTACK_POSITION_HINTS):
        baseline = 0.5
        role = "attack"
    elif position_known:
        baseline = 0.25
        role = "non_attack"
    else:
        baseline = 0.35
        role = "unknown"

    score = clamp(per90 / baseline, 0, 1)

    return _ok(
        score,
        {
            "goals": float(goals),
            "assists": float(assists),
            "minutes": float(minutes),
            "goal_contribution_per90": round(per90, 3),
            "baseline": baseline,
            "role": role,
            "position_adjusted": position_known,
        },
    )


def compute_age_potential(player, profile):
    """player_profiles.age 또는 players.date_of_birth로 나이 잠재력 점수(0~1)를 계산한다.
    21세에 가까울수록 높은 점수, 멀어질수록 낮은 점수가 된다.
    """
    age = None
    source = None

    if isinstance(profile, dict):
        age = safe_float_or_none(profile.get("age"))
        if age is not None:
            source = "player_profiles.age"

    if age is None and isinstance(player, dict):
        dob = player.get("date_of_birth")
        if dob:
            try:
                if isinstance(dob, str):
                    dob_date = pd.to_datetime(dob).date()
                elif isinstance(dob, date):
                    dob_date = dob
                else:
                    dob_date = pd.to_datetime(dob).date()
                age = (date.today() - dob_date).days / 365.25
                source = "players.date_of_birth"
            except Exception:
                age = None

    if age is None:
        return _unavailable("나이 정보(age/date_of_birth)가 없습니다.")

    score = clamp(1 - abs(age - 21) / 8, 0, 1)
    return _ok(score, {"age": round(age, 1), "source": source})


def compute_attribute_strength(profile):
    """player_profiles.attributes_jsonb의 실제 key만 사용해 FM 능력치 강도 점수(0~1)를 계산한다."""
    if not isinstance(profile, dict):
        return _unavailable("FM 프로필이 없습니다.")

    attributes = parse_json_field(profile.get("attributes_jsonb"))
    if not isinstance(attributes, dict) or not attributes:
        return _unavailable("attributes_jsonb 데이터가 없습니다.")

    values = [numeric_attr(attributes, key) for key in attributes.keys()]
    values = [value for value in values if value is not None]

    if not values:
        return _unavailable("attributes_jsonb에 숫자 능력치가 없습니다.")

    average = sum(values) / len(values)
    scale = 20.0 if max(values) <= 20 else 100.0
    score = clamp(average / scale, 0, 1)

    return _ok(score, {"average": round(average, 1), "scale": scale, "attribute_count": len(values)})


def compute_mentality_strength(profile):
    """player_profiles.mentality_jsonb의 basis(또는 mentality_score)를 사용해 멘탈리티 강도 점수(0~1)를 계산한다."""
    if not isinstance(profile, dict):
        return _unavailable("FM 프로필이 없습니다.")

    mentality = parse_json_field(profile.get("mentality_jsonb"))
    if not isinstance(mentality, dict) or not mentality:
        return _unavailable("mentality_jsonb 데이터가 없습니다.")

    basis = mentality.get("basis", {})
    values = []
    if isinstance(basis, dict):
        values = [numeric_attr(basis, key) for key in MENTALITY_KEYS]
        values = [value for value in values if value is not None]

    if values:
        average = sum(values) / len(values)
        scale = 20.0 if max(values) <= 20 else 100.0
        score = clamp(average / scale, 0, 1)
        return _ok(score, {"average": round(average, 1), "scale": scale, "attribute_count": len(values), "source": "basis"})

    mentality_score = numeric_attr(mentality, "mentality_score")
    if mentality_score is None:
        return _unavailable("mentality_jsonb에 사용 가능한 멘탈리티 항목이 없습니다.")

    scale = 20.0 if mentality_score <= 20 else 100.0
    score = clamp(mentality_score / scale, 0, 1)
    return _ok(score, {"mentality_score": mentality_score, "scale": scale, "source": "mentality_score"})


def compute_risk_penalty(features):
    """시장가치 하락세 / 낮은 출전 기회 / 데이터 부족을 기준으로 risk_penalty(0~15)를 계산한다."""
    penalty = 0.0
    notes = []

    market = features.get("market_momentum", {})
    if market.get("status") == "ok" and market["score"] < 0.35:
        penalty += 5.0
        notes.append("최근 시장가치 흐름이 하락세에 가깝습니다.")

    playing = features.get("playing_opportunity", {})
    if playing.get("status") == "ok" and playing["score"] < 0.2:
        penalty += 5.0
        notes.append("최근 출전 기록이 거의 없어 실전 경험이 부족합니다.")

    unavailable_count = sum(1 for feature in features.values() if feature.get("status") == "unavailable")
    if unavailable_count >= 3:
        penalty += 5.0
        notes.append("핵심 데이터가 다수 부족해 평가 신뢰도가 제한적입니다.")
    elif unavailable_count >= 1:
        penalty += 2.0
        notes.append("일부 데이터가 부족해 평가에 제한이 있습니다.")

    penalty = clamp(penalty, 0, 15)
    return {"penalty": penalty, "notes": notes, "unavailable_count": unavailable_count}


def compute_growth_score(features, risk_penalty):
    """feature 점수와 risk_penalty로 최종 Growth Score(0~100)를 계산한다.
    unavailable feature는 제외하고 남은 weight를 재정규화한다.
    """
    available = {key: value for key, value in features.items() if value.get("status") == "ok"}

    if not available:
        return {"score": None, "status": "unavailable", "available_weight": 0.0}

    total_weight = sum(GROWTH_WEIGHTS[key] for key in available)
    weighted_sum = sum(GROWTH_WEIGHTS[key] * available[key]["score"] for key in available)
    available_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    final_score = clamp(available_score * 100 - risk_penalty["penalty"], 0, 100)
    return {"score": round(final_score, 1), "status": "ok", "available_weight": round(total_weight, 2)}


def build_growth_insight(player, profile, appearances=None, valuations=None, entity_type=None):
    """players/appearances/player_valuations/player_profiles 조회 결과로 Growth Insight를 만든다.

    DB 조회는 이 함수 밖(services.db)에서 수행하고, 그 결과를 인자로 전달한다.
    """
    position = None
    if isinstance(player, dict):
        position = player.get("position")
    if not position and isinstance(profile, dict):
        position = profile.get("position")

    features = {
        "market_momentum": compute_market_momentum(valuations),
        "playing_opportunity": compute_playing_opportunity(appearances),
        "contribution_score": compute_contribution_score(appearances, position),
        "age_potential": compute_age_potential(player, profile),
        "attribute_strength": compute_attribute_strength(profile),
        "mentality_strength": compute_mentality_strength(profile),
    }

    risk = compute_risk_penalty(features)
    growth = compute_growth_score(features, risk)

    return {
        "mode": "data_driven",
        "entity_type": entity_type,
        "features": features,
        "risk_penalty": risk,
        "growth_score": growth["score"],
        "growth_status": growth["status"],
        "available_weight": growth.get("available_weight"),
        "position_used": position,
    }


def classify_training_intensity(value):
    number = safe_float(value, 1.2)
    if number < 0.8:
        return "낮음"
    if number < 1.2:
        return "보통"
    if number < 1.6:
        return "높음"
    return "매우 높음"


def classify_playing_opportunity(value):
    number = safe_float(value, 0.5)
    if number < 0.3:
        return "낮음"
    if number < 0.55:
        return "보통"
    if number < 0.8:
        return "높음"
    return "매우 높음"


def classify_league_level(value):
    return LEAGUE_LEVEL_FROM_DIFFICULTY.get(value, "보통")


def classify_risk_tendency(value):
    return RISK_TENDENCY_FROM_LEVEL.get(value, "균형형")


def build_manual_growth_insight(manual_player, manual_attributes, career_settings):
    """Manual Note(직접 입력) 기반 prototype Growth Score를 계산한다.

    실제 DB 기반 예측이 아니라, 사용자가 입력한 훈련강도/리그난이도/출전기회/
    리스크성향/능력치를 바탕으로 한 prototype 점수다.
    """
    manual_player = manual_player or {}
    manual_attributes = manual_attributes or {}
    career_settings = career_settings or {}

    age = safe_float_or_none(manual_player.get("age"))
    age_potential = clamp(1 - abs(age - 21) / 8, 0, 1) if age is not None else None

    training_level = classify_training_intensity(career_settings.get("training_intensity"))
    league_level = classify_league_level(career_settings.get("league_difficulty"))
    playing_level = classify_playing_opportunity(career_settings.get("playing_time_opportunity"))
    risk_level = classify_risk_tendency(career_settings.get("risk_level"))

    training_score = TRAINING_INTENSITY_SCORES[training_level]
    league_score = LEAGUE_LEVEL_SCORES[league_level]
    playing_score = PLAYING_OPPORTUNITY_SCORES[playing_level]

    attr_values = [safe_float_or_none(value) for value in manual_attributes.values()]
    attr_values = [value for value in attr_values if value is not None]
    self_attribute_score = clamp((sum(attr_values) / len(attr_values)) / 10.0, 0, 1) if attr_values else None

    components = {
        "age_potential": (0.25, age_potential),
        "playing_opportunity": (0.20, playing_score),
        "training_intensity": (0.20, training_score),
        "league_level": (0.20, league_score),
        "self_attribute": (0.15, self_attribute_score),
    }
    available = {key: value for key, value in components.items() if value[1] is not None}
    total_weight = sum(weight for weight, _ in available.values())
    weighted_sum = sum(weight * score for weight, score in available.values())
    base_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0

    risk_penalty = RISK_TENDENCY_PENALTY[risk_level]
    risk_notes = [f"리스크성향({risk_level}) 기본 패널티 {risk_penalty:.0f}점이 반영되었습니다."]
    if league_level in ("높음", "매우 높음") and risk_level == "도전형":
        risk_penalty += 3.0
        risk_notes.append("높은 리그 난이도와 도전형 리스크 성향이 함께 선택되어 추가 패널티가 적용되었습니다.")
    risk_penalty = clamp(risk_penalty, 0, 15)

    growth_bonus = RISK_TENDENCY_GROWTH_BONUS[risk_level]
    if growth_bonus:
        risk_notes.append("도전형 리스크 성향은 성장 잠재력에 보너스 점수를 더하지만 리스크 패널티도 함께 증가시킵니다.")

    final_score = clamp(base_score * 100 + growth_bonus - risk_penalty, 0, 100)

    return {
        "mode": "manual_prototype",
        "entity_type": "manual_note",
        "growth_score": round(final_score, 1),
        "growth_status": "ok" if available else "unavailable",
        "available_weight": round(total_weight, 2),
        "levels": {
            "training_intensity": training_level,
            "league_level": league_level,
            "playing_opportunity": playing_level,
            "risk_tendency": risk_level,
        },
        "scores": {
            "age_potential": age_potential,
            "playing_opportunity": playing_score,
            "training_intensity": training_score,
            "league_level": league_score,
            "self_attribute": self_attribute_score,
        },
        "risk_penalty": {"penalty": risk_penalty, "notes": risk_notes, "growth_bonus": growth_bonus},
    }


def map_league_difficulty(value):
    """리그 난이도 입력값을 분류 레벨과 γ(gamma)로 매핑한다."""
    level = classify_league_level(value)
    return level, LEAGUE_DIFFICULTY_GAMMA[level]


def map_playing_opportunity(value):
    """출전 기회 입력값을 분류 레벨과 α(alpha)로 매핑한다."""
    level = classify_playing_opportunity(value)
    return level, PLAYING_OPPORTUNITY_ALPHA[level]


def map_training_intensity(value):
    """훈련 강도 입력값을 분류 레벨과 training_multiplier로 매핑한다."""
    level = classify_training_intensity(value)
    return level, TRAINING_INTENSITY_MULTIPLIER[level]


def map_risk_tendency(value):
    """리스크 성향 입력값을 분류 레벨과 β(beta)로 매핑한다."""
    level = classify_risk_tendency(value)
    return level, RISK_TENDENCY_BETA[level]


def compute_delta_league(career_choice, league_level, playing_opportunity):
    """커리어 선택/리그 난이도/출전 기회 조합으로 Δleague(환경 변화량)와 시나리오 라벨을 계산한다.

    반환값: (delta_league, scenario_label, extra_risk_flag)
    extra_risk_flag가 True면 이적/임대 + 낮은 출전기회 조합으로 β(적응 실패 리스크)가
    추가로 증가해야 함을 의미한다.
    """
    high_levels = ("높음", "매우 높음")
    low_levels = ("낮음", "보통")

    if career_choice == "stay":
        if playing_opportunity in high_levels:
            return DELTA_LEAGUE_VALUES["balanced_growth"], "균형형 성장 환경 시나리오", False
        return DELTA_LEAGUE_VALUES["stable_stay"], "안정적 잔류 성장 시나리오", False

    # loan / transfer
    if playing_opportunity in low_levels:
        return DELTA_LEAGUE_VALUES["risky_challenge"], "무리한 도전/출전 부족 시나리오", True

    if league_level in high_levels:
        return DELTA_LEAGUE_VALUES["league_challenge"], "상위 리그 도전형 성장 시나리오", False

    return DELTA_LEAGUE_VALUES["balanced_growth"], "균형형 성장 환경 시나리오", False


def compute_ceiling_scenario_adjustment(env_settings):
    """초기 기획의 Ceiling Model 공식으로 Scenario Adjustment를 계산한다.

    Potential_final = Potential_base + Σ(Δleague × (α × γ × training_multiplier - β))
    raw_adjustment = Δleague × ((α × γ × training_multiplier) - β)
    scenario_adjustment = clamp(raw_adjustment, -15, 15)
    """
    env_settings = env_settings or {}

    league_level, gamma = map_league_difficulty(env_settings.get("league_difficulty"))
    playing_level, alpha = map_playing_opportunity(env_settings.get("playing_time_opportunity"))
    training_level, training_multiplier = map_training_intensity(env_settings.get("training_intensity"))
    risk_level, beta = map_risk_tendency(env_settings.get("risk_level"))
    career_choice = env_settings.get("career_choice", "stay")

    delta_league, scenario_label, extra_risk = compute_delta_league(career_choice, league_level, playing_level)

    notes = [
        f"리그난이도 '{league_level}' → γ(리그 난이도)={gamma}",
        f"출전기회 '{playing_level}' → α(출전 확률)={alpha}",
        f"훈련강도 '{training_level}' → training_multiplier={training_multiplier}",
        f"리스크성향 '{risk_level}' → β(부상/적응 리스크)={beta}",
        f"커리어 선택 '{career_choice}'과 환경 조합 → Δleague={delta_league} ({scenario_label})",
    ]

    if extra_risk:
        beta = clamp(beta + 0.10, 0, 2)
        notes.append("이적/임대 + 낮은 출전기회 조합으로 β(적응 실패 리스크)가 추가로 증가했습니다.")

    if career_choice in ("loan", "transfer") and league_level == "매우 높음" and playing_level in ("낮음", "보통") and risk_level == "도전형":
        beta = clamp(beta + 0.10, 0, 2)
        notes.append("이적/임대 + 매우 높은 리그난이도 + 낮은 출전기회 + 도전형 리스크 성향 조합으로 β가 추가로 증가했습니다.")

    risk_adjustments = []
    if training_level == "매우 높음":
        risk_adjustments.append((0.15, "매우 높은 훈련강도는 단기 성장 자극과 함께 피로 누적, 부상, 번아웃 리스크를 높입니다."))
        if risk_level == "도전형":
            risk_adjustments.append((0.15, "매우 높은 훈련강도와 도전형 성향이 겹쳐 회복 실패 및 부상 리스크가 추가됩니다."))
        if playing_level == "매우 높음":
            risk_adjustments.append((0.25, "매우 높은 훈련강도와 매우 높은 출전기회 조합은 과부하 및 부상 위험을 크게 높입니다."))
        if league_level == "매우 높음":
            risk_adjustments.append((0.20, "매우 높은 훈련강도와 매우 높은 리그난이도 조합은 적응 실패와 피로 누적 위험을 높입니다."))

    if playing_level == "낮음":
        risk_adjustments.append((0.15, "낮은 출전기회는 경기 감각 저하와 성장 정체 위험을 높입니다."))
    elif playing_level == "매우 높음":
        risk_adjustments.append((0.10, "매우 높은 출전기회는 실전 경험에 유리하지만 어린 선수의 과부하 위험도 높입니다."))

    if league_level == "매우 높음":
        risk_adjustments.append((0.15, "매우 높은 리그난이도는 성장 상한선을 높이지만 적응 실패, 출전 감소, 자신감 저하 위험도 높입니다."))
        if playing_level in ("낮음", "보통"):
            risk_adjustments.append((0.20, "매우 높은 리그난이도에서 출전기회가 부족하면 벤치 정체와 경기 감각 저하 위험이 큽니다."))

    if career_choice == "stay" and league_level == "낮음":
        risk_adjustments.append((0.05, "낮은 난이도 리그 잔류는 적응에는 유리하지만 성장 상한선을 제한할 수 있습니다."))
    if career_choice == "transfer" and playing_level == "낮음":
        risk_adjustments.append((0.20, "이적 후 낮은 출전기회는 성장보다 벤치 정체 위험을 키웁니다."))
        if risk_level == "도전형":
            risk_adjustments.append((0.10, "이적, 도전형 성향, 낮은 출전기회 조합은 적응 실패 가능성이 높은 고위험 시나리오입니다."))

    for risk_increment, risk_note in risk_adjustments:
        beta = clamp(beta + risk_increment, 0, 2)
        notes.append(risk_note)

    raw_adjustment = delta_league * ((alpha * gamma * training_multiplier) - beta)
    scenario_adjustment = clamp(raw_adjustment, CEILING_ADJUSTMENT_MIN, CEILING_ADJUSTMENT_MAX)

    if scenario_adjustment != raw_adjustment:
        notes.append(f"raw_adjustment({raw_adjustment:.2f})이 범위를 벗어나 {CEILING_ADJUSTMENT_MIN}~{CEILING_ADJUSTMENT_MAX}로 제한되었습니다.")

    return {
        "status": "ok",
        "baseline_formula": "Potential_final = Potential_base + Σ(Δleague × (α × γ × training_multiplier - β))",
        "alpha": alpha,
        "gamma": gamma,
        "beta": round(beta, 2),
        "training_multiplier": training_multiplier,
        "delta_league": delta_league,
        "raw_adjustment": round(raw_adjustment, 2),
        "scenario_adjustment": round(scenario_adjustment, 2),
        "scenario_label": scenario_label,
        "levels": {
            "league_level": league_level,
            "playing_opportunity": playing_level,
            "training_intensity": training_level,
            "risk_tendency": risk_level,
            "career_choice": career_choice,
        },
        "notes": notes,
    }


def apply_ceiling_adjustment(growth_insight, env_settings):
    """Real Data Growth Baseline(또는 manual_growth_score) 위에 Ceiling Scenario
    Adjustment를 더해 Final Growth Score를 계산하고, 기존 growth_insight에
    `ceiling_model` key를 추가한다. 기존 key는 변경하지 않는다.
    """
    potential_base = growth_insight.get("growth_score")
    ceiling = compute_ceiling_scenario_adjustment(env_settings)

    if potential_base is None:
        final_growth_score = None
    else:
        final_growth_score = round(clamp(potential_base + ceiling["scenario_adjustment"], 0, 100), 1)

    growth_insight["ceiling_model"] = {
        "potential_base": potential_base,
        "scenario_adjustment": ceiling["scenario_adjustment"],
        "final_growth_score": final_growth_score,
        "alpha": ceiling["alpha"],
        "gamma": ceiling["gamma"],
        "beta": ceiling["beta"],
        "training_multiplier": ceiling["training_multiplier"],
        "delta_league": ceiling["delta_league"],
        "scenario_label": ceiling["scenario_label"],
        "levels": ceiling["levels"],
        "formula": ceiling["baseline_formula"],
        "notes": ceiling["notes"],
    }
    return growth_insight
