import pandas as pd
import streamlit as st

from analysis_helpers import (
    attr_label,
    build_simulation_result,
    format_percent,
    numeric_attr,
    parse_json_field,
    position_training_hint,
    readable_setting,
    safe_float,
)
from explanation_engine import build_growth_explanation
from growth_model import (
    LEVEL_DESCRIPTIONS,
    apply_ceiling_adjustment,
    build_manual_growth_insight,
    classify_league_level,
    classify_playing_opportunity,
    classify_risk_tendency,
    classify_training_intensity,
)
from services.db import get_scouting_notes, insert_scouting_note, query_df
from ui_components import render_page_actions


def note_summary_text(note):
    env = parse_json_field(note.get("env_settings"))
    sim = parse_json_field(note.get("simulation_result"))
    return (
        f"훈련 강도 {readable_setting('training_intensity', env.get('training_intensity', 0))}, "
        f"출전 기회 {readable_setting('playing_time_opportunity', env.get('playing_time_opportunity', 0))}, "
        f"커리어 선택 {readable_setting('career_choice', env.get('career_choice'))}, "
        f"성공 가능성 {format_percent(sim.get('prototype_success_probability'))}"
    )


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


def note_display_title(note):
    env = parse_json_field(note.get("env_settings")) if note is not None else {}
    if isinstance(env, dict):
        manual_player = env.get("manual_player") if isinstance(env.get("manual_player"), dict) else {}
        manual_name = safe_text(manual_player.get("name"), None)
        if manual_name:
            return manual_name

        player_name = safe_text(env.get("player_name"), None)
        if player_name:
            return player_name

    db_name = safe_text(note.get("player_name"), None) if note is not None else None
    if db_name:
        return db_name

    selected_name = safe_text(st.session_state.get("selected_player_name"), None)
    if selected_name:
        return selected_name

    return "이름 없는 직접 입력 노트"


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


def render_scouting_notes_view():
    st.title("My Scouting Notes")
    st.info(
        "이 화면은 직접 입력한 유망주 분석, 멘토 추천, 성장 가이드, 저장된 노트를 함께 보는 프로토타입 화면입니다. "
        "실제 Gemini API 호출은 없으며, FM 기반 proxy 능력치와 직접 입력값을 연결해 템플릿 기반 분석을 생성합니다."
    )

    st.subheader("직접 입력 유망주 분석 (prototype)")
    st.caption("선수 이름, 능력치, 메모를 입력하면 성장 잠재력, 강점/보완점, 훈련 방향, 멘토 후보, 멘토 기반 성장 가이드를 미리 확인할 수 있습니다.")

    with st.form("custom_note_form"):
        c1, c2 = st.columns(2)
        with c1:
            custom_name = st.text_input("유망주 이름", placeholder="예: Custom Prospect A")
            custom_age = st.number_input("나이", min_value=14, max_value=35, value=18, step=1)
            custom_position = st.text_input("포지션", placeholder="예: ST / CM / LB")
            custom_sub_position = st.text_input("세부 포지션", placeholder="예: CF / CM")
            custom_club = st.text_input("소속팀 / 학교", placeholder="예: Academy FC")
            custom_nationality = st.text_input("국적", placeholder="예: Korea")
            custom_foot = st.text_input("주발", placeholder="예: 오른발")
        with c2:
            custom_height = st.text_input("키(cm)", placeholder="예: 182")
            custom_note = st.text_area("관찰 메모", placeholder="예: 속도와 돌파는 좋지만 마무리와 수비 전개를 보완할 필요가 있음")
            speed = st.slider("속도/기동성", 1, 10, 7)
            dribble = st.slider("드리블", 1, 10, 6)
            finishing = st.slider("결정력", 1, 10, 5)
            passing = st.slider("패스/시야", 1, 10, 6)
            physical = st.slider("피지컬", 1, 10, 6)
            defending = st.slider("수비력", 1, 10, 5)
            work_rate = st.slider("활동량", 1, 10, 7)
            teamwork = st.slider("팀워크", 1, 10, 7)
            determination = st.slider("의지력", 1, 10, 7)
            pressing = st.slider("압박 대처", 1, 10, 5)
            growth_potential = st.slider("성장 잠재력", 1, 10, 8)

        training_intensity = st.slider("훈련 강도", 0.5, 2.0, 1.2, 0.1)
        training_level = classify_training_intensity(training_intensity)
        st.caption(f"훈련 강도: {training_level} — {LEVEL_DESCRIPTIONS['training_intensity'][training_level]}")

        playing_time = st.slider("출전 기회", 0.0, 1.0, 0.6, 0.05)
        playing_level = classify_playing_opportunity(playing_time)
        st.caption(f"출전 기회: {playing_level} — {LEVEL_DESCRIPTIONS['playing_opportunity'][playing_level]}")

        league_difficulty = st.selectbox("리그/팀 수준", ["low", "medium", "high", "elite"], index=1, format_func=lambda value: readable_setting("league_difficulty", value))
        league_level = classify_league_level(league_difficulty)
        st.caption(f"리그/팀 수준: {league_level} — {LEVEL_DESCRIPTIONS['league_level'][league_level]}")

        career_choice = st.radio("커리어 선택", ["stay", "loan", "transfer"], horizontal=True, format_func=lambda value: readable_setting("career_choice", value))

        risk_level = st.radio("리스크 성향", ["safe", "normal", "aggressive"], horizontal=True, index=1, format_func=lambda value: readable_setting("risk_level", value))
        risk_tendency = classify_risk_tendency(risk_level)
        st.caption(f"리스크 성향: {risk_tendency} — {LEVEL_DESCRIPTIONS['risk_tendency'][risk_tendency]}")

        submitted = st.form_submit_button("프로토타입 분석 생성")

    if submitted:
        env_settings = {
            "note_type": "manual_custom_prospect",
            "manual_player": {
                "name": custom_name,
                "age": int(custom_age),
                "position": custom_position,
                "sub_position": custom_sub_position,
                "club": custom_club,
                "nationality": custom_nationality,
                "foot": custom_foot,
                "height": custom_height,
                "observation_note": custom_note,
            },
            "manual_attributes": {
                "speed": float(speed),
                "dribble": float(dribble),
                "finishing": float(finishing),
                "passing": float(passing),
                "physical": float(physical),
                "defending": float(defending),
                "work_rate": float(work_rate),
                "teamwork": float(teamwork),
                "determination": float(determination),
                "pressing": float(pressing),
                "growth_potential": float(growth_potential),
            },
            "career_settings": {
                "training_intensity": float(training_intensity),
                "playing_time_opportunity": float(playing_time),
                "league_difficulty": league_difficulty,
                "career_choice": career_choice,
                "risk_level": risk_level,
            },
            "selected_mentor_profile_id": st.session_state.get("manual_selected_mentor_profile_id"),
            "selected_mentor_name": st.session_state.get("manual_selected_mentor_name"),
        }
        simulation_result = build_simulation_result(env_settings["career_settings"])
        analysis = build_manual_analysis(env_settings["manual_player"], env_settings["manual_attributes"], env_settings["career_settings"], simulation_result)

        growth_insight = build_manual_growth_insight(env_settings["manual_player"], env_settings["manual_attributes"], env_settings["career_settings"])
        growth_insight = apply_ceiling_adjustment(growth_insight, env_settings["career_settings"])
        growth_explanation = build_growth_explanation(
            growth_insight,
            player_context={"name": env_settings["manual_player"].get("name"), "position": env_settings["manual_player"].get("position")},
        )
        st.session_state["growth_insight"] = growth_insight
        st.session_state["growth_explanation"] = growth_explanation
        st.session_state["ceiling_growth_insight"] = growth_insight
        st.session_state["ceiling_growth_explanation"] = growth_explanation
        st.session_state["ceiling_growth_context"] = {
            "entity_type": "manual_note",
            "player_id": None,
            "profile_id": None,
            "source": "manual_note",
        }
        simulation_result.update({
            "prototype_growth_score": simulation_result.get("prototype_growth_score"),
            "prototype_success_probability": simulation_result.get("prototype_success_probability"),
            "prototype_injury_risk": simulation_result.get("prototype_injury_risk"),
            "strengths": [name for name, _ in analysis["strengths"]],
            "weaknesses": [name for name, _ in analysis["weaknesses"]],
            "training_recommendations": analysis["training_recommendations"],
            "career_advice": analysis["career_advice"],
            "risk_factors": analysis["risk_factors"],
            "mentor_guide": analysis["mentor_guide"],
            "overall_summary": analysis["overall_summary"],
        })

        report_text = "\n\n".join([
            "AI 스카우팅 리포트 초안 (프로토타입)",
            f"종합 평가\n{analysis['overall_summary']}",
            "핵심 강점\n" + "; ".join([f"{name}({score}/10)" for name, score in analysis['strengths']]),
            "보완점\n" + "; ".join([f"{name}({score}/10)" for name, score in analysis['weaknesses']]),
            "추천 훈련 방향\n" + "\n".join(analysis['training_recommendations']),
            "멘토 기반 성장 가이드\n" + analysis['mentor_guide'],
            "커리어 선택 조언\n" + analysis['career_advice'],
            "장점과 리스크\n" + "\n".join(analysis['risk_factors'] or ["현재 입력값 기준 리스크는 아직 명확하지 않습니다."]),
            "예상 성장 방향\n" + "이 분석은 실제 예측 모델이 아니라 FM 기반 proxy 능력치와 직접 입력값으로 만든 템플릿 기반 가이드입니다.",
        ])

        st.session_state["custom_note_preview"] = {
            "env_settings": env_settings,
            "simulation_result": simulation_result,
            "report": report_text,
            "analysis": analysis,
            "player_name": custom_name,
            "growth_insight": growth_insight,
            "growth_explanation": growth_explanation,
        }
        st.session_state["manual_analysis_result"] = analysis
        st.session_state["manual_report_text"] = report_text
        st.session_state["selected_entity_type"] = "manual_note"
        st.session_state["selected_manual_note_title"] = custom_name or "직접 입력 유망주"
        st.session_state["selected_manual_note_payload"] = env_settings

    preview = st.session_state.get("custom_note_preview")
    if preview:
        st.subheader("생성된 프로토타입 분석 미리보기")
        analysis = preview.get("analysis") or {}
        env_settings = normalize_env_settings(preview.get("env_settings"))
        career_settings = get_career_settings(env_settings)

        c1, c2, c3 = st.columns(3)
        c1.metric("성장 점수", preview["simulation_result"].get("prototype_growth_score", "-"))
        c2.metric("성공 가능성", format_percent(preview["simulation_result"].get("prototype_success_probability")))
        c3.metric("부상 리스크", format_percent(preview["simulation_result"].get("prototype_injury_risk")))

        st.markdown(f"<div class='scout-panel'><b>종합 평가</b><br>{analysis.get('overall_summary', '')}</div>", unsafe_allow_html=True)

        st.markdown(
            "<div class='scout-panel'>" +
            "<b>환경 요약</b><br>" +
            "<br>".join([
                setting_summary('training_intensity', career_settings.get('training_intensity')),
                setting_summary('playing_time_opportunity', career_settings.get('playing_time_opportunity')),
                setting_summary('league_difficulty', career_settings.get('league_difficulty')),
                setting_summary('career_choice', career_settings.get('career_choice')),
                setting_summary('risk_level', career_settings.get('risk_level')),
            ]) +
            "</div>",
            unsafe_allow_html=True,
        )

        st.subheader("Growth Insight (직접 입력 기반 prototype)")
        st.warning("이 점수는 실제 DB(player_valuations/appearances/player_profiles) 기반 예측이 아니라, 직접 입력한 조건을 바탕으로 한 prototype + 시나리오 보정 점수입니다.")
        growth_insight = preview.get("growth_insight") or {}
        growth_explanation = preview.get("growth_explanation") or {}
        if growth_insight:
            st.metric("Manual Prototype Baseline", f"{growth_insight['growth_score']:.1f} / 100")
            st.progress(int(round(growth_insight["growth_score"])))
            st.markdown(f"<div class='scout-panel'><b>왜 이 점수가 나왔나요?</b><br>{growth_explanation.get('score_reason', '')}</div>", unsafe_allow_html=True)
            gcols = st.columns(2)
            with gcols[0]:
                st.markdown("<div class='scout-panel'><b>강점</b><br>" + "<br>".join(f"• {item}" for item in growth_explanation.get("strengths", [])) + "</div>", unsafe_allow_html=True)
            with gcols[1]:
                st.markdown("<div class='scout-panel'><b>리스크</b><br>" + "<br>".join(f"• {item}" for item in growth_explanation.get("risks", [])) + "</div>", unsafe_allow_html=True)
            st.markdown("<div class='scout-panel'><b>추천 성장 방향</b><br>" + "<br>".join(f"• {item}" for item in growth_explanation.get("recommendations", [])) + "</div>", unsafe_allow_html=True)

            ceiling_model = growth_insight.get("ceiling_model", {})
            ceiling_explanation = growth_explanation.get("ceiling_explanation") or {}
            final_score = ceiling_model.get("final_growth_score")
            adjustment = ceiling_model.get("scenario_adjustment", 0)

            st.markdown("#### 코칭 시나리오 리포트")
            st.markdown("<div class='scout-panel'><b>시나리오 총평</b><br>" + ceiling_explanation.get("coaching_summary", "") + "</div>", unsafe_allow_html=True)

            if final_score is not None:
                st.metric("Manual Final Growth Score", f"{final_score:.1f} / 100")
                st.progress(int(round(final_score)))
                st.caption("직접 입력한 기본 성장 평가에 현재 시나리오의 기회와 위험을 반영한 prototype 결과입니다.")

            gcols2 = st.columns(2)
            with gcols2[0]:
                st.markdown("<div class='scout-panel'><b>추천 훈련 방향</b><br>" + "<br>".join(f"• {item}" for item in ceiling_explanation.get("training_directions", [])) + "</div>", unsafe_allow_html=True)
                st.markdown("<div class='scout-panel'><b>소홀히 했을 때의 단점</b><br>" + "<br>".join(f"• {item}" for item in ceiling_explanation.get("neglect_risks", [])) + "</div>", unsafe_allow_html=True)
            with gcols2[1]:
                st.markdown("<div class='scout-panel'><b>기대 장점</b><br>" + "<br>".join(f"• {item}" for item in ceiling_explanation.get("expected_benefits", [])) + "</div>", unsafe_allow_html=True)
                st.markdown("<div class='scout-panel'><b>리스크 경고</b><br>" + "<br>".join(f"• {item}" for item in ceiling_explanation.get("risk_warnings", [])) + "</div>", unsafe_allow_html=True)
            st.markdown("<div class='scout-panel'><b>추천 커리어 전략</b><br>" + "<br>".join(f"• {item}" for item in ceiling_explanation.get("career_strategy", [])) + "</div>", unsafe_allow_html=True)

            with st.expander("상세 계산 근거"):
                st.caption(f"공식: {ceiling_model.get('formula', '')}")
                st.caption(f"시나리오: {ceiling_model.get('scenario_label', '-')}")
                v1, v2, v3, v4, v5 = st.columns(5)
                v1.metric("α (출전 기회)", ceiling_model.get("alpha"))
                v2.metric("γ (리그 난이도)", ceiling_model.get("gamma"))
                v3.metric("β (리스크)", ceiling_model.get("beta"))
                v4.metric("훈련 배수", ceiling_model.get("training_multiplier"))
                v5.metric("Δleague", ceiling_model.get("delta_league"))
                st.caption(f"Ceiling Scenario Adjustment: {adjustment:+.1f}점")
                for line in ceiling_explanation.get("variable_explanations", []):
                    st.markdown(f"<div class='section-note'>{line}</div>", unsafe_allow_html=True)

        cols = st.columns(2)
        with cols[0]:
            st.markdown("<div class='scout-panel'><b>핵심 강점</b><br>" + "<br>".join([f"• {name}: {score}/10" for name, score in analysis.get('strengths', [])]) + "</div>", unsafe_allow_html=True)
            st.markdown("<div class='scout-panel'><b>보완점</b><br>" + "<br>".join([f"• {name}: {score}/10" for name, score in analysis.get('weaknesses', [])]) + "</div>", unsafe_allow_html=True)
        with cols[1]:
            st.markdown("<div class='scout-panel'><b>추천 훈련 방향</b><br>" + "<br>".join([f"• {item}" for item in analysis.get('training_recommendations', [])]) + "</div>", unsafe_allow_html=True)
            st.markdown("<div class='scout-panel'><b>커리어 선택 조언</b><br>" + analysis.get('career_advice', '') + "</div>", unsafe_allow_html=True)

        st.subheader("유사 멘토 후보")
        mentor_candidates = analysis.get("mentor_candidates", [])
        if mentor_candidates:
            for mentor in mentor_candidates:
                st.markdown(
                    f"""
                    <div class="scout-panel">
                        <h3 style="margin-top:0;">{mentor['name']}</h3>
                        <div class="badge-row">
                            <span class="scout-badge">나이 {mentor.get('age') or '-'}</span>
                            <span class="scout-badge">{mentor.get('position') or '-'}</span>
                            <span class="scout-badge">{mentor.get('club') or '-'}</span>
                            <span class="scout-badge">유사도 {mentor.get('similarity', '-')}</span>
                        </div>
                        <p><b>공통 강점</b><br>{mentor.get('common_strengths', '-')}</p>
                        <p><b>주요 차이점</b><br>{mentor.get('difference_hint', '-')}</p>
                        <p>이 멘토 후보는 직접 입력 능력치와 FM proxy 능력치를 비교했을 때 참고하기 좋은 형태의 프로토타입 추천입니다.</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("이 멘토 선택", key=f"manual_mentor_{mentor['profile_id']}", type="secondary"):
                    st.session_state["manual_selected_mentor_profile_id"] = mentor['profile_id']
                    st.session_state["manual_selected_mentor_name"] = mentor['name']
                    st.session_state["manual_mentor_summary"] = (
                        f"{mentor['name']}은(는) 현재 직접 입력 능력치와 유사한 강점을 보이는 후보입니다. "
                        f"공통 강점: {mentor['common_strengths']} / 차이점: {mentor['difference_hint']}"
                    )
                    st.success(f"{mentor['name']}을(를) 멘토 후보로 선택했습니다.")
        else:
            st.info("현재 입력값 기준으로 멘토 후보를 생성할 수 없었습니다. 프로필 속성 데이터가 없는 경우에는 기본 가이드만 표시됩니다.")

        mentor_name = st.session_state.get("manual_selected_mentor_name")
        mentor_summary = st.session_state.get("manual_mentor_summary")
        if mentor_name:
            st.markdown(
                f"<div class='scout-panel'><b>멘토 기반 성장 가이드</b><br>선택된 멘토: {mentor_name}<br>{mentor_summary or '선택한 멘토의 성장 가이드를 반영했습니다.'}</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div class='scout-panel'><b>장점과 리스크</b><br>" + "<br>".join(analysis.get('risk_factors', []) or ["현재 입력값 기준 리스크는 아직 충분하지 않습니다."]) + "</div>", unsafe_allow_html=True)

        if st.button("이 노트를 scouting_notes에 저장", type="primary"):
            try:
                saved = insert_scouting_note(
                    player_id=None,
                    profile_id=None,
                    env_settings=normalize_env_settings(preview.get("env_settings")),
                    simulation_result=preview["simulation_result"],
                    report=preview["report"],
                )
                st.success(f"직접 입력 노트가 저장되었습니다. note_id: {saved['note_id']}")
            except Exception as exc:
                st.error("직접 입력 노트 저장 중 오류가 발생했습니다.")
                with st.expander("개발 확인용 오류"):
                    st.exception(exc)

        with st.expander("개발자용 원본 JSON 보기"):
            st.json({"env_settings": preview.get("env_settings"), "simulation_result": preview.get("simulation_result"), "report": preview.get("report")})

        render_page_actions([
            ("🔎 새 유망주 검색", "유망주 검색", "primary"),
            ("📝 새 유망주 직접 입력", "내 스카우팅 노트"),
        ], title="저장 완료 · 다음 단계")

    st.divider()
    st.subheader("저장된 노트 조회")
    try:
        notes = get_scouting_notes(limit=20)
    except Exception as exc:
        st.error("스카우팅 노트 조회 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)
        return

    if notes.empty:
        st.info("현재 저장된 노트가 없습니다. 위에서 직접 입력한 커스텀 노트나 기존 저장 리포트를 확인할 수 있습니다.")
        render_page_actions([
            ("🔎 유망주 검색으로 이동", "유망주 검색", "primary"),
            ("📝 새 유망주 직접 입력", "내 스카우팅 노트"),
        ])
        return

    for _, note in notes.iterrows():
        env = parse_json_field(note.get("env_settings")) or {}
        sim = parse_json_field(note.get("simulation_result")) or {}
        manual_player = env.get("manual_player") if isinstance(env, dict) and isinstance(env.get("manual_player"), dict) else {}
        legacy_player = env.get("player") if isinstance(env, dict) and isinstance(env.get("player"), dict) else {}
        player_snapshot = manual_player or legacy_player
        if not player_snapshot and note.get("player_name"):
            player_snapshot = {
                "name": safe_text(note.get("player_name"), "이름 없는 노트"),
                "age": env.get("age"),
                "position": env.get("position"),
                "club": env.get("club"),
                "nationality": env.get("nationality"),
            }
        title = note_display_title(note)
        summary = safe_text(sim.get("overall_summary"), note_summary_text(note))
        strengths = sim.get("strengths") if isinstance(sim, dict) else []
        weaknesses = sim.get("weaknesses") if isinstance(sim, dict) else []
        mentor_name = env.get("selected_mentor_name") or "선택된 멘토 없음"
        growth_score = sim.get("prototype_growth_score", "-")
        injury_risk = sim.get("prototype_injury_risk")
        preview_text = safe_text(note.get("gemini_report"), "")

        st.markdown(
            f"""
            <div class="scout-panel">
                <h3 style="margin-top:0;">{title}</h3>
                <div class="muted">저장일 {note.get('created_at')}</div>
                <p><b>나이 / 포지션 / 소속팀 / 국적</b><br>
                {safe_text(player_snapshot.get('age'), '-') if isinstance(player_snapshot, dict) else '-'}세 ·
                {safe_text(player_snapshot.get('position'), '-') if isinstance(player_snapshot, dict) else '-'} ·
                {safe_text(player_snapshot.get('club'), '-') if isinstance(player_snapshot, dict) else '-'} ·
                {safe_text(player_snapshot.get('nationality'), '-') if isinstance(player_snapshot, dict) else '-'}
                </p>
                <p><b>종합 평가 요약</b><br>{summary}</p>
                <p><b>핵심 강점</b><br>{' · '.join(str(item) for item in strengths[:3]) if strengths else '정보 없음'}</p>
                <p><b>보완점</b><br>{' · '.join(str(item) for item in weaknesses[:2]) if weaknesses else '정보 없음'}</p>
                <p><b>선택한 멘토</b><br>{mentor_name}</p>
                <p><b>성장 가능성 / 부상 리스크</b><br>{growth_score} / {format_percent(injury_risk)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("상세 보기"):
            st.write("### 종합 평가")
            st.write(summary)
            if strengths:
                st.write("### 핵심 강점")
                for item in strengths:
                    st.write("- " + str(item))
            if weaknesses:
                st.write("### 보완점")
                for item in weaknesses:
                    st.write("- " + str(item))
            if env.get("selected_mentor_name"):
                st.write("### 선택한 멘토")
                st.write(env["selected_mentor_name"])
            if preview_text:
                st.write("### 리포트 요약")
                st.text(preview_text[:500])
        with st.expander("개발자용 원본 JSON 보기"):
            st.json({"env_settings": env, "simulation_result": sim, "gemini_report": note.get("gemini_report")})

    render_page_actions([
        ("🔎 새 유망주 검색", "유망주 검색", "primary"),
        ("📝 새 유망주 직접 입력", "내 스카우팅 노트"),
    ], title="다음 작업")
