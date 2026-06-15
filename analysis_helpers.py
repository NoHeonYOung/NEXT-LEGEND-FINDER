"""분석/리포트/시뮬레이션 화면에서 공유되는 순수 helper 모음.

app.py를 import하지 않는다(순환 import 방지). DB 조회나 session_state 수정은
하지 않으며, st/pd/alt를 사용한 표시/계산용 순수 함수와 관련 상수만 담는다.
"""

import json

import altair as alt
import pandas as pd
import streamlit as st

from services.db import money


def parse_json_field(value):
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    try:
        return json.loads(value)
    except Exception:
        return {}


ATTRIBUTE_LABELS = {
    "Acc": ("가속도", "순간적으로 속도를 끌어올리는 능력"),
    "Pac": ("주력", "최고 속도와 전력 질주 능력"),
    "Sta": ("지구력", "경기 내내 활동량을 유지하는 능력"),
    "Dri": ("드리블", "공을 몰고 전진하는 능력"),
    "Fin": ("결정력", "찬스를 득점으로 연결하는 능력"),
    "Pas": ("패스", "동료에게 공을 전달하는 정확도"),
    "Vis": ("시야", "전진 패스와 기회 창출을 보는 능력"),
    "Wor": ("활동량", "전술 수행과 압박에 참여하는 성향"),
    "Tea": ("팀워크", "동료와 전술에 맞춰 움직이는 능력"),
    "Det": ("의지력", "훈련 지속성과 성장 가능성을 뒷받침하는 성향"),
    "Str": ("몸싸움", "경합 상황에서 버티는 힘"),
    "Jum": ("점프력", "공중볼 상황의 도약 능력"),
    "Agi": ("민첩성", "방향 전환과 몸놀림"),
    "Bal": ("균형감각", "접촉 상황에서 자세를 유지하는 능력"),
    "Tec": ("개인기", "공을 다루는 전반적인 기술"),
    "Fir": ("퍼스트 터치", "첫 볼 컨트롤의 안정성"),
    "OtB": ("오프더볼", "공이 없을 때 공간을 찾는 움직임"),
    "Ant": ("예측력", "다음 장면을 먼저 읽는 능력"),
    "Dec": ("판단력", "상황에 맞는 선택을 하는 능력"),
    "Cmp": ("침착성", "압박 상황에서 판단을 유지하는 능력"),
    "Bra": ("적극성", "위험을 감수하고 경합에 참여하는 성향"),
    "Agg": ("적극성", "경합과 압박에 참여하는 성향"),
    "Cro": ("크로스", "측면에서 공을 투입하는 능력"),
    "Lon": ("중거리슛", "먼 거리에서 슈팅하는 능력"),
    "Mar": ("마킹", "상대 선수를 추적하는 능력"),
    "Tck": ("태클", "공을 빼앗는 능력"),
    "Pos": ("위치선정", "수비 위치와 공간 점유 능력"),
    "Amb": ("야망", "높은 목표를 추구하는 성향"),
    "Ldr": ("리더십", "팀을 이끄는 성향"),
    "Loy": ("충성심", "소속팀과 관계를 유지하는 성향"),
    "Cons": ("꾸준함", "경기력 변동을 줄이는 성향"),
    "Pres": ("압박 대처", "부담이 큰 경기에서 버티는 성향"),
    "Prof": ("프로 의식", "자기관리와 훈련 태도"),
    "Sport": ("스포츠맨십", "페어플레이와 경기 태도"),
    "Spor": ("스포츠맨십", "페어플레이와 경기 태도"),
    "Temp": ("감정 조절", "흥분 상황에서 균형을 유지하는 성향"),
}

ATTRIBUTE_GROUPS = {
    "공격 능력": ["Fin", "OtB", "Cmp", "Lon"],
    "패스/창의성": ["Pas", "Vis", "Tec", "Fir"],
    "피지컬": ["Acc", "Pac", "Sta", "Str", "Jum", "Agi", "Bal"],
    "멘탈/활동량": ["Det", "Wor", "Tea", "Ant", "Dec"],
    "수비 능력": ["Mar", "Tck", "Pos"],
}

MENTALITY_KEYS = ["Agg", "Amb", "Det", "Ldr", "Loy", "Tea", "Wor", "Cons", "Pres", "Prof", "Sport", "Spor", "Temp"]


def attr_label(key, with_code=False):
    if key is None:
        return "알 수 없음"
    label = ATTRIBUTE_LABELS.get(key, (str(key), ""))[0]
    return f"{label} ({key})" if with_code else label


def attr_description(key):
    if key is None:
        return "정의되지 않은 능력치입니다."
    return ATTRIBUTE_LABELS.get(key, (str(key), "설명 정보가 없는 proxy 능력치입니다."))[1]


def numeric_attr(attributes, key):
    if not isinstance(attributes, dict) or key is None:
        return None
    try:
        value = attributes.get(key)
        if value is None or value == "":
            return None
        value = float(value)
        if pd.isna(value):
            return None
        return value
    except Exception:
        return None


def average_attrs(attributes, keys):
    values = [numeric_attr(attributes, key) for key in keys]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def attributes_long_df(attributes, groups=None):
    if not isinstance(attributes, dict):
        return pd.DataFrame(columns=["그룹", "능력치", "점수", "설명"])
    rows = []
    for group, keys in (groups or ATTRIBUTE_GROUPS).items():
        for key in keys:
            value = numeric_attr(attributes, key)
            if value is None:
                continue
            rows.append(
                {
                    "그룹": group or "기타",
                    "능력치": attr_label(key) or "알 수 없음",
                    "점수": value,
                    "설명": attr_description(key) or "설명 없음",
                }
            )
    return pd.DataFrame(rows, columns=["그룹", "능력치", "점수", "설명"])


def attr_bar_chart(df, title=None, height=230):
    if df is None or df.empty:
        st.info("표시할 능력치 데이터가 없습니다.")
        return
    work = df.copy()
    for col in ["그룹", "능력치", "설명"]:
        if col not in work.columns:
            work[col] = "알 수 없음"
        work[col] = work[col].fillna("알 수 없음").replace("", "알 수 없음")
    if "점수" not in work.columns:
        st.info("표시할 능력치 데이터가 없습니다.")
        return
    work["점수"] = pd.to_numeric(work["점수"], errors="coerce")
    work = work.dropna(subset=["점수"])
    if work.empty:
        st.info("표시할 능력치 데이터가 없습니다.")
        return
    chart = (
        alt.Chart(work)
        .mark_bar(cornerRadiusEnd=4, color="#2A9D8F")
        .encode(
            x=alt.X("점수:Q", scale=alt.Scale(domain=[0, 20]), title="점수"),
            y=alt.Y("능력치:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("그룹:N", title="그룹"),
                alt.Tooltip("능력치:N", title="능력치"),
                alt.Tooltip("점수:Q", title="점수"),
                alt.Tooltip("설명:N", title="설명"),
            ],
        )
    )
    props = {"height": height}
    if title:
        props["title"] = str(title)
    st.altair_chart(chart.properties(**props), use_container_width=True)


def top_attributes(attributes, keys=None, limit=3, reverse=True):
    if not isinstance(attributes, dict):
        return []
    keys = keys or [key for group in ATTRIBUTE_GROUPS.values() for key in group]
    rows = [(key, numeric_attr(attributes, key)) for key in keys]
    rows = [(key, value) for key, value in rows if value is not None]
    return sorted(rows, key=lambda item: item[1], reverse=reverse)[:limit]


def summary_scores(attributes, mentality):
    basis = mentality.get("basis", {}) if isinstance(mentality, dict) else {}
    mental_score = mentality.get("mentality_score") if isinstance(mentality, dict) else None
    if mental_score is None:
        mental_score = average_attrs(basis, MENTALITY_KEYS)
    return {
        "공격 능력": average_attrs(attributes, ATTRIBUTE_GROUPS["공격 능력"]),
        "패스/창의성": average_attrs(attributes, ATTRIBUTE_GROUPS["패스/창의성"]),
        "피지컬": average_attrs(attributes, ATTRIBUTE_GROUPS["피지컬"]),
        "멘탈 종합": mental_score,
    }


def score_text(value):
    if value is None:
        return "-"
    try:
        return f"{float(value):.1f}"
    except Exception:
        return "-"


def format_percent(value):
    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return "-"


def render_metric_cards(scores):
    cols = st.columns(len(scores))
    for col, (label, value) in zip(cols, scores.items()):
        col.metric(label, score_text(value))


def strength_sentence(rows):
    if not rows:
        return "뚜렷하게 확인되는 강점 데이터가 부족합니다."
    labels = [attr_label(key) for key, _ in rows[:2]]
    return f"{'와 '.join(labels)} 지표가 상대적으로 높아 해당 역할에서 강점으로 해석할 수 있습니다."


def weakness_sentence(rows):
    if not rows:
        return "명확한 보완점 데이터가 부족합니다."
    labels = [attr_label(key) for key, _ in rows[:1]]
    return f"{labels[0]} 지표가 상대적으로 낮아 경기 운영이나 전술 적응 과정에서 보완이 필요할 수 있습니다."


def group_analysis(attributes, group, keys):
    avg = average_attrs(attributes, keys)
    highs = top_attributes(attributes, keys, 2, reverse=True)
    lows = top_attributes(attributes, keys, 1, reverse=False)
    return avg, highs, lows


def build_simulation_result(env_settings):
    training = env_settings["training_intensity"]
    playing_time = env_settings["playing_time_opportunity"]
    difficulty = env_settings["league_difficulty"]
    risk_level = env_settings["risk_level"]

    difficulty_factor = {
        "low": 8,
        "medium": 0,
        "high": -8,
        "elite": -14,
    }[difficulty]

    choice_factor = {
        "stay": 4,
        "loan": 8,
        "transfer": 2,
    }[env_settings["career_choice"]]

    risk_factor = {
        "safe": -4,
        "normal": 0,
        "aggressive": 5,
    }[risk_level]

    growth_score = round(
        45 + training * 12 + playing_time * 25 + difficulty_factor + choice_factor + risk_factor
    )
    growth_score = max(0, min(100, growth_score))

    injury_risk = round(0.08 + training * 0.06 + {"safe": -0.02, "normal": 0.04, "aggressive": 0.1}[risk_level], 2)
    injury_risk = max(0.01, min(0.75, injury_risk))

    success_probability = round((growth_score / 100) * (1 - injury_risk), 2)

    return {
        "prototype_growth_score": growth_score,
        "prototype_success_probability": success_probability,
        "prototype_injury_risk": injury_risk,
        "message": (
            "현재 결과는 실제 예측 모델이 아니라 UI 흐름 검증을 위한 "
            "프로토타입 시뮬레이션 결과입니다."
        ),
    }


ENTITY_TYPE_SIMULATION_NOTES = {
    "matched": "이 선수는 Transfermarkt 실데이터와 FM 능력치 프로필이 모두 매칭되어 있어, 시장가치·출전 기록과 능력치 기반 분석을 함께 참고할 수 있습니다.",
    "fm_profile_only": "이 선수는 FM 능력치 프로필만 있는 후보로, 실제 시장가치·출전 기록 데이터가 없어 시뮬레이션 해석에 한계가 있습니다.",
    "transfermarkt_only": "이 선수는 Transfermarkt 실데이터만 있고 FM 능력치 프로필이 연결되지 않아, 능력치 기반 성장 요인 설명은 제한적입니다.",
    "manual_note": "이 선수는 사용자가 직접 입력한 노트 기반 정보로, 시뮬레이션 결과는 참고용 예시로만 활용해야 합니다.",
}


def build_simulation_breakdown(env_settings, simulation_result, entity_type=None, mentor_name=None):
    """Career Simulation 결과의 설명력을 높이기 위한 부가 정보를 만든다.

    growth score를 구성하는 각 항목, 리스크/기회 요약, 멘토 유사도 참고
    설명, 데이터 타입(entity_type)에 따른 해석 제한 안내를 묶어서 반환한다.
    build_simulation_result의 반환값은 그대로 유지되며, 이 함수는 추가
    설명용 정보만 만든다.
    """
    training = env_settings["training_intensity"]
    playing_time = env_settings["playing_time_opportunity"]
    difficulty = env_settings["league_difficulty"]
    risk_level = env_settings["risk_level"]
    career_choice = env_settings["career_choice"]

    difficulty_factor = {"low": 8, "medium": 0, "high": -8, "elite": -14}[difficulty]
    choice_factor = {"stay": 4, "loan": 8, "transfer": 2}[career_choice]
    risk_factor = {"safe": -4, "normal": 0, "aggressive": 5}[risk_level]

    growth_components = [
        {"label": "기본 점수", "value": 45.0},
        {"label": "훈련 강도 기여 (훈련 강도 x 12)", "value": round(training * 12, 1)},
        {"label": "출전 기회 기여 (출전 기회 x 25)", "value": round(playing_time * 25, 1)},
        {"label": "리그 난이도 보정", "value": float(difficulty_factor)},
        {"label": "커리어 선택 보정", "value": float(choice_factor)},
        {"label": "리스크 성향 보정", "value": float(risk_factor)},
    ]

    growth_score = simulation_result["prototype_growth_score"]
    injury_risk = simulation_result["prototype_injury_risk"]

    if growth_score >= 70:
        opportunity_text = "현재 설정 기준 성장 점수가 높게 나타납니다. 다만 부상 리스크와 실제 출전 보장 여부를 함께 고려해야 합니다."
    elif growth_score >= 50:
        opportunity_text = "현재 설정 기준 성장 점수는 중간 수준입니다. 출전 기회나 훈련 강도를 조정하면 결과가 달라질 수 있습니다."
    else:
        opportunity_text = "현재 설정 기준 성장 점수는 낮은 편입니다. 리그 난이도나 출전 기회 설정을 조정해 다른 시나리오를 비교해 보세요."

    if injury_risk >= 0.3:
        risk_text = "부상 리스크가 높게 추정됩니다. 훈련 강도를 낮추거나 리스크 성향을 안정형으로 바꾸면 리스크가 줄어드는 경향을 확인할 수 있습니다."
    elif injury_risk >= 0.15:
        risk_text = "부상 리스크는 중간 수준으로 추정됩니다."
    else:
        risk_text = "부상 리스크는 낮게 추정됩니다."

    mentor_text = None
    if mentor_name:
        mentor_text = (
            f"현재 멘토로 선택된 '{mentor_name}' 선수와의 능력치 유사도는 '유사 선수 후보' 화면의 "
            "멘토링 가이드에서 설명한 보완 포인트를 참고용으로 제공합니다. 이 시뮬레이션의 성장 점수/"
            "리스크 계산 자체에는 멘토 유사도가 직접 반영되지 않으며, 멘토 비교는 별도의 설명적 "
            "참고 정보입니다."
        )

    limitation_note = ENTITY_TYPE_SIMULATION_NOTES.get(
        entity_type,
        "선수의 데이터 타입 정보가 없어 시뮬레이션 해석에 제한이 있을 수 있습니다.",
    )

    return {
        "growth_components": growth_components,
        "opportunity_text": opportunity_text,
        "risk_text": risk_text,
        "mentor_text": mentor_text,
        "limitation_note": limitation_note,
    }


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def readable_setting(key, value):
    if key == "training_intensity":
        number = safe_float(value, None)
        if number is None:
            return "알 수 없음"
        if number >= 1.4:
            return "높음"
        if number >= 0.9:
            return "보통"
        return "낮음"

    if key == "playing_time_opportunity":
        number = safe_float(value, None)
        if number is None:
            return "알 수 없음"
        if number >= 0.7:
            return "높음"
        if number >= 0.35:
            return "중간"
        return "낮음"

    maps = {
        "league_difficulty": {"low": "낮음", "medium": "중간", "high": "높음", "elite": "최상위"},
        "career_choice": {"stay": "잔류", "loan": "임대", "transfer": "이적"},
        "risk_level": {"safe": "안정형", "normal": "균형형", "aggressive": "공격형"},
    }
    return maps.get(key, {}).get(value, "알 수 없음" if value is None else str(value))


def compare_attributes(selected_attrs, candidate_attrs):
    if not isinstance(selected_attrs, dict) or not isinstance(candidate_attrs, dict):
        return {"common_high": [], "mentor_higher": [], "candidate_higher": [], "selected_higher": []}

    known_keys = [key for group in ATTRIBUTE_GROUPS.values() for key in group]
    keys = list(dict.fromkeys(known_keys + list(selected_attrs) + list(candidate_attrs)))
    common_high = []
    candidate_higher = []
    selected_higher = []

    for key in keys:
        selected_value = numeric_attr(selected_attrs, key)
        candidate_value = numeric_attr(candidate_attrs, key)
        if selected_value is None or candidate_value is None:
            continue
        if selected_value >= 12 and candidate_value >= 12:
            common_high.append((key, round((selected_value + candidate_value) / 2, 1)))
        diff = candidate_value - selected_value
        if diff >= 2:
            candidate_higher.append((key, round(diff, 1)))
        elif diff <= -2:
            selected_higher.append((key, round(abs(diff), 1)))

    return {
        "common_high": sorted(common_high, key=lambda item: item[1], reverse=True)[:3],
        "mentor_higher": sorted(candidate_higher, key=lambda item: item[1], reverse=True)[:3],
        "candidate_higher": sorted(candidate_higher, key=lambda item: item[1], reverse=True)[:3],
        "selected_higher": sorted(selected_higher, key=lambda item: item[1], reverse=True)[:2],
    }


def attr_names(rows):
    return ", ".join(attr_label(key) for key, _ in rows)


def position_training_hint(position, improvement_names):
    text = (position or "").lower()
    if "attack" in text or "forward" in text or "striker" in text:
        return f"공격수 유형이라면 {improvement_names}을 보완해 마무리뿐 아니라 연계와 침투 선택지를 넓히는 방향이 좋습니다."
    if "midfield" in text:
        return f"미드필더 유형이라면 {improvement_names}을 보완해 전개, 압박 회피, 전술 연결 능력을 키우는 방향이 좋습니다."
    if "defender" in text or "back" in text:
        return f"수비수 유형이라면 {improvement_names}을 보완해 수비 위치 선정과 빌드업 안정성을 함께 높이는 방향이 좋습니다."
    if "goalkeeper" in text:
        return f"골키퍼 유형이라면 {improvement_names}을 보완해 안정적인 경기 운영 능력을 키우는 방향이 좋습니다."
    return f"현재 포지션에서는 {improvement_names}을 중심으로 약점을 보완하고, 이미 높은 강점은 유지하는 방향이 적절합니다."


def generate_similarity_reason(selected_player, candidate_player, selected_attrs, candidate_attrs):
    comparison = compare_attributes(selected_attrs, candidate_attrs)
    common_names = attr_names(comparison["common_high"])
    candidate_higher_names = attr_names(comparison["candidate_higher"])
    selected_higher_names = attr_names(comparison["selected_higher"])

    if common_names:
        similarity_reason = (
            f"두 선수는 {common_names}에서 공통으로 높은 수치를 보여 유사한 역할 후보로 해석할 수 있습니다. "
            "pgvector 유사도는 FM 기반 proxy style_vector(24차원) 전반의 가까움을 함께 반영합니다."
        )
        common_strengths = common_names
    else:
        similarity_reason = (
            "공통으로 높게 나타난 세부 능력치는 제한적이지만, FM 기반 proxy style_vector(24차원) "
            "전반의 거리가 가까워 비교 후보로 제시되었습니다."
        )
        common_strengths = "세부 공통 강점 데이터가 부족합니다."

    difference_parts = []
    if candidate_higher_names:
        difference_parts.append(f"후보가 앞선 능력치는 {candidate_higher_names}입니다")
    if selected_higher_names:
        difference_parts.append(f"선택 선수가 앞선 능력치는 {selected_higher_names}입니다")
    differences = ". ".join(difference_parts) + "." if difference_parts else "뚜렷한 능력치 차이 데이터가 부족합니다."

    position = selected_player.get("position") or candidate_player.get("position") or "현재 포지션"
    improvement_names = candidate_higher_names or "세부 능력치"
    tactical_interpretation = (
        f"{position} 역할에서 {common_names or '전반적인 스타일'}을 공통 기반으로 활용할 수 있습니다. "
        f"{position_training_hint(position, improvement_names)}"
    )
    return {
        "comparison": comparison,
        "common_strengths": common_strengths,
        "differences": differences,
        "similarity_reason": similarity_reason,
        "tactical_interpretation": tactical_interpretation,
    }


def generate_mentor_guide(selected_player, mentor_player, selected_attrs, mentor_attrs, simulation_result=None):
    reason = generate_similarity_reason(selected_player, mentor_player, selected_attrs, mentor_attrs)
    comparison = reason["comparison"]
    if not comparison["common_high"] and not comparison["mentor_higher"]:
        limited = "현재 후보 선수의 세부 능력치 데이터가 부족하여 상세 멘토링은 제한적으로 제공됩니다."
        return {
            "similarity_reason": limited,
            "improvement_points": limited,
            "training_recommendation": "우선 선택 선수의 출전 기록과 시장가치 흐름을 함께 확인하며 기본 성장 방향을 설정하는 것이 좋습니다.",
            "career_advice": "현재 단계에서는 무리한 이적보다 안정적인 출전 시간을 확보할 수 있는 환경을 우선 검토하는 전략이 적합합니다.",
            "mentor_summary": limited,
        }

    common_names = attr_names(comparison["common_high"]) or "스타일 벡터 전반"
    improvement_names = attr_names(comparison["mentor_higher"]) or "세부 능력치"
    selected_better = attr_names(comparison["selected_higher"]) or "일부 강점"
    similarity_reason = reason["similarity_reason"]
    improvement_points = f"선택 유망주는 후보 선수와 비교했을 때 {improvement_names}에서 보완 여지가 있습니다. 반대로 {selected_better}에서는 선택 유망주가 이미 경쟁력을 보일 수 있습니다."
    training_recommendation = reason["tactical_interpretation"]
    career_advice = f"현재 유망주의 시장가치는 {money(selected_player.get('market_value_in_eur'))}입니다. 상위 리그 이적보다 안정적인 출전 시간을 확보할 수 있는 팀에서 성장하는 전략을 우선 검토하는 것이 좋습니다."
    if simulation_result:
        career_advice += f" 현재 시뮬레이션 기준 성공 가능성은 {format_percent(simulation_result.get('prototype_success_probability'))}입니다."
    mentor_summary = (
        f"멘토 후보 {mentor_player.get('name') or '-'} 참고 가이드. "
        f"유사 후보 이유: {similarity_reason} "
        f"보완할 점: {improvement_points} "
        f"추천 훈련: {training_recommendation} "
        f"커리어 조언: {career_advice} "
        "이 내용은 실제 레전드 성장 로그가 아니라 FM 기반 proxy 능력치 차이를 활용한 프로토타입 조언입니다."
    )
    return {
        "similarity_reason": similarity_reason,
        "improvement_points": improvement_points,
        "training_recommendation": training_recommendation,
        "career_advice": career_advice,
        "mentor_summary": mentor_summary,
    }


def simulation_comment(env_settings, simulation_result):
    training = readable_setting("training_intensity", env_settings.get("training_intensity"))
    playing = readable_setting("playing_time_opportunity", env_settings.get("playing_time_opportunity"))
    choice = readable_setting("career_choice", env_settings.get("career_choice"))
    risk = readable_setting("risk_level", env_settings.get("risk_level"))
    choice_text = {
        "stay": "잔류는 안정적인 출전 기회를 확보하는 시나리오입니다.",
        "loan": "임대는 단기 성장 기회를 찾는 시나리오입니다.",
        "transfer": "이적은 상위 리그 도전 또는 환경 변화를 선택하는 시나리오입니다.",
    }.get(env_settings.get("career_choice"), "커리어 선택 정보가 제한적입니다.")
    risk_text = {
        "safe": "안정형은 안정적 성장을 우선합니다.",
        "normal": "균형형은 성장과 리스크의 균형을 보는 설정입니다.",
        "aggressive": "공격형은 높은 성장 가능성과 높은 리스크를 함께 감수하는 설정입니다.",
    }.get(env_settings.get("risk_level"), "리스크 성향 정보가 제한적입니다.")
    return f"현재 설정은 훈련 강도 {training}, 출전 기회 {playing}, 커리어 선택 {choice}, 리스크 성향 {risk}입니다. {choice_text} {risk_text}"
