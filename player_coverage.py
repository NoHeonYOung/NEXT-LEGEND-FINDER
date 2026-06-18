"""선수별 데이터 커버리지 분류 helper.

app.py / Streamlit / DB를 import하지 않는다.
player dict와 profile dict를 인자로 받아 커버리지를 분류하는 순수 함수만 담는다.

주요 함수:
    resolve_player_age(player, profile, reference_date) → float | None
        UI 전반(선수 카드 / Growth Model / Mentor age filter)에서 공통으로 사용해
        나이 표시를 일관되게 유지한다.

    build_data_coverage(player, profile) → dict
        analysis_level("full" | "partial" | "limited" | "manual_prospect")과
        missing_reasons 목록을 반환한다.
"""

import math
from datetime import date

import pandas as pd


def _safe_float(value):
    """값을 float으로 변환한다. 실패/None/NaN이면 None 반환."""
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result):
        return None
    return result


def resolve_player_age(player, profile=None, reference_date=None):
    """선수 나이를 일관되게 계산한다.

    우선순위:
    1. player_profiles.age (있으면 그대로 반환)
    2. players.date_of_birth (계산, reference_date 기준)
    3. 없으면 None 반환

    이 함수를 선수 카드 / Growth Model / Mentor age filter에서
    공통으로 사용해 UI 전반에서 나이 표시가 일치하도록 한다.
    """
    if reference_date is None:
        reference_date = date.today()

    if isinstance(profile, dict):
        age = _safe_float(profile.get("age"))
        if age is not None:
            return age

    if isinstance(player, dict):
        dob = player.get("date_of_birth")
        if dob:
            try:
                if isinstance(dob, str):
                    dob_date = pd.to_datetime(dob).date()
                elif isinstance(dob, date):
                    dob_date = dob
                else:
                    dob_date = pd.to_datetime(dob).date()
                computed = (reference_date - dob_date).days / 365.25
                return round(computed, 1)
            except Exception:
                pass

    return None


def build_data_coverage(player, profile=None):
    """선수별 데이터 커버리지를 분류한다.

    analysis_level:
      full            - age + valuation + appearances + FM profile + style_vector 모두 있음
      partial         - FM profile은 있으나 style_vector 또는 일부 proxy 데이터 부족
      limited         - FM profile 없음, age 없음, 핵심 데이터 다수 부족
      manual_prospect - 직접 입력 유망주 (별도 흐름, 이 함수 밖에서 처리)

    Returns:
        dict with keys:
            has_player, has_age, resolved_age, has_valuation, has_appearances,
            has_fm_profile, has_style_vector, has_mentality, has_attributes,
            analysis_level, missing_reasons
    """
    has_player = isinstance(player, dict) and bool(player.get("player_id"))
    has_fm_profile = isinstance(profile, dict) and bool(profile.get("profile_id"))
    has_style_vector = (
        isinstance(profile, dict) and profile.get("style_vector") is not None
    )
    has_mentality = isinstance(profile, dict) and bool(profile.get("mentality_jsonb"))
    has_attributes = isinstance(profile, dict) and bool(profile.get("attributes_jsonb"))

    resolved_age = resolve_player_age(player, profile)
    has_age = resolved_age is not None

    # Transfermarkt 데이터: player_id가 있으면 조회 가능하다고 간주
    has_valuation = has_player
    has_appearances = has_player

    missing = []
    if not has_age:
        missing.append("나이 데이터 없음")
    if not has_fm_profile:
        missing.append("FM 프로필 없음")
    if not has_style_vector:
        missing.append("style_vector 없음")
    if not has_mentality:
        missing.append("FM 멘탈 지표 없음")
    if not has_attributes:
        missing.append("FM 능력치 없음")

    # analysis_level 결정
    if has_player and has_fm_profile and has_style_vector and has_age:
        level = "full"
    elif not has_fm_profile:
        level = "limited"
    elif has_age and has_fm_profile:
        level = "partial"
    else:
        level = "limited"

    return {
        "has_player": has_player,
        "has_age": has_age,
        "resolved_age": resolved_age,
        "has_valuation": has_valuation,
        "has_appearances": has_appearances,
        "has_fm_profile": has_fm_profile,
        "has_style_vector": has_style_vector,
        "has_mentality": has_mentality,
        "has_attributes": has_attributes,
        "analysis_level": level,
        "missing_reasons": missing,
    }
