import json
from datetime import datetime
import inspect

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

import scouting_note_payload
from explanation_engine import build_growth_explanation
from growth_model import (
    apply_ceiling_adjustment,
    build_growth_insight,
    build_manual_growth_insight,
    classify_league_level,
    classify_playing_opportunity,
    classify_training_intensity,
    compute_age_potential,
    compute_attribute_strength,
    compute_ceiling_scenario_adjustment,
    compute_growth_score,
    compute_market_momentum,
    compute_mentality_strength,
    compute_playing_opportunity,
    compute_risk_penalty,
    map_league_difficulty,
    map_playing_opportunity,
    map_risk_tendency,
    map_training_intensity,
)
from manual_prospect_helpers import filter_mentor_candidates_by_age
from scouting_note_payload import (
    build_ai_report_note_payload,
    build_career_simulation_note_payload,
    build_manual_note_payload,
    compact_report_sections,
    extract_structured_note_result,
    json_safe,
)
from views.scouting_notes import ENTITY_TYPE_LABELS as SAVED_ENTITY_TYPE_LABELS
from views.scouting_notes import (
    NOTE_TYPE_LABELS,
    SOURCE_LABELS,
    saved_coaching_sections,
    saved_note_label,
    saved_report_original,
)


def navigate_to(at, page):
    nav_buttons = [button for button in at.button if button.key == f"navchip_{page}"]
    assert nav_buttons
    nav_buttons[0].click().run(timeout=30)
    return at


def test_market_momentum_with_two_valuations():
    valuations = pd.DataFrame({
        "date": ["2024-01-01", "2025-01-01"],
        "market_value_in_eur": [1_000_000, 3_000_000],
        "current_club_name": ["Club A", "Club B"],
    })
    result = compute_market_momentum(valuations)
    assert result["status"] == "ok"
    assert 0.0 <= result["score"] <= 1.0
    assert result["detail"]["market_growth"] > 0


def test_market_momentum_unavailable_with_insufficient_data():
    valuations = pd.DataFrame({
        "date": ["2025-01-01"],
        "market_value_in_eur": [1_000_000],
        "current_club_name": ["Club A"],
    })
    result = compute_market_momentum(valuations)
    assert result["status"] == "unavailable"
    assert result["score"] is None

    empty = pd.DataFrame(columns=["date", "market_value_in_eur", "current_club_name"])
    assert compute_market_momentum(empty)["status"] == "unavailable"
    assert compute_market_momentum(None)["status"] == "unavailable"


def test_no_profile_handling():
    assert compute_attribute_strength(None)["status"] == "unavailable"
    assert compute_mentality_strength(None)["status"] == "unavailable"
    assert compute_attribute_strength({})["status"] == "unavailable"

    age_result = compute_age_potential({}, None)
    assert age_result["status"] == "unavailable"


def test_playing_opportunity_appearance_fallback():
    appearances = pd.DataFrame({
        "date": ["2025-01-01"] * 3,
        "competition_id": ["L1"] * 3,
        "goals": [0, 1, 0],
        "assists": [0, 0, 1],
        "yellow_cards": [0, 0, 0],
        "red_cards": [0, 0, 0],
        "minutes_played": [None, None, None],
    })
    result = compute_playing_opportunity(appearances)
    assert result["status"] == "ok"
    assert result["detail"]["basis"] == "appearance_count"

    assert compute_playing_opportunity(pd.DataFrame())["status"] == "unavailable"
    assert compute_playing_opportunity(None)["status"] == "unavailable"


def test_growth_score_reweighting_on_missing_data():
    features_full = {
        "market_momentum": {"status": "ok", "score": 0.8},
        "playing_opportunity": {"status": "ok", "score": 0.6},
        "contribution_score": {"status": "ok", "score": 0.5},
        "age_potential": {"status": "ok", "score": 0.9},
        "attribute_strength": {"status": "ok", "score": 0.7},
        "mentality_strength": {"status": "ok", "score": 0.7},
    }
    risk = compute_risk_penalty(features_full)
    full_result = compute_growth_score(features_full, risk)
    assert full_result["status"] == "ok"
    assert full_result["available_weight"] == 1.0

    features_partial = dict(features_full)
    features_partial["attribute_strength"] = {"status": "unavailable", "score": None, "detail": {"reason": "no profile"}}
    features_partial["mentality_strength"] = {"status": "unavailable", "score": None, "detail": {"reason": "no profile"}}
    risk_partial = compute_risk_penalty(features_partial)
    partial_result = compute_growth_score(features_partial, risk_partial)
    assert partial_result["status"] == "ok"
    assert partial_result["available_weight"] == 0.8


def test_final_growth_score_in_range():
    valuations = pd.DataFrame({
        "date": ["2024-01-01", "2025-01-01"],
        "market_value_in_eur": [5_000_000, 1_000_000],
        "current_club_name": ["Club A", "Club B"],
    })
    appearances = pd.DataFrame({
        "date": ["2025-01-01"],
        "competition_id": ["L1"],
        "goals": [0],
        "assists": [0],
        "yellow_cards": [0],
        "red_cards": [0],
        "minutes_played": [10],
    })
    player = {"name": "Test Player", "position": "ST", "date_of_birth": "2005-01-01"}
    insight = build_growth_insight(player, None, appearances=appearances, valuations=valuations, entity_type="transfermarkt_only")
    assert insight["growth_status"] == "ok"
    assert 0.0 <= insight["growth_score"] <= 100.0


def test_manual_growth_score_calculation():
    manual_player = {"name": "Manual Player", "age": 19, "position": "CM"}
    manual_attributes = {"speed": 7, "dribble": 6, "finishing": 5, "passing": 7}
    career_settings = {
        "training_intensity": 1.5,
        "playing_time_opportunity": 0.7,
        "league_difficulty": "high",
        "risk_level": "aggressive",
    }
    insight = build_manual_growth_insight(manual_player, manual_attributes, career_settings)
    assert insight["mode"] == "manual_prototype"
    assert insight["growth_status"] == "ok"
    assert 0.0 <= insight["growth_score"] <= 100.0
    assert insight["levels"]["training_intensity"] == "높음"
    assert insight["levels"]["league_level"] == "높음"
    assert insight["levels"]["playing_opportunity"] == "높음"
    assert insight["levels"]["risk_tendency"] == "도전형"


def test_classification_helpers():
    assert classify_training_intensity(0.5) == "낮음"
    assert classify_training_intensity(1.0) == "보통"
    assert classify_training_intensity(1.4) == "높음"
    assert classify_training_intensity(2.0) == "매우 높음"

    assert classify_playing_opportunity(0.1) == "낮음"
    assert classify_playing_opportunity(0.4) == "보통"
    assert classify_playing_opportunity(0.6) == "높음"
    assert classify_playing_opportunity(0.9) == "매우 높음"

    assert classify_league_level("low") == "낮음"
    assert classify_league_level("elite") == "매우 높음"


def test_explanation_engine_data_driven():
    valuations = pd.DataFrame({
        "date": ["2024-01-01", "2025-01-01"],
        "market_value_in_eur": [1_000_000, 3_000_000],
        "current_club_name": ["Club A", "Club B"],
    })
    appearances = pd.DataFrame({
        "date": ["2025-01-01"] * 2,
        "competition_id": ["L1"] * 2,
        "goals": [1, 0],
        "assists": [0, 1],
        "yellow_cards": [0, 0],
        "red_cards": [0, 0],
        "minutes_played": [90, 80],
    })
    player = {"name": "Test Player", "position": "ST", "date_of_birth": "2005-01-01"}
    insight = build_growth_insight(player, None, appearances=appearances, valuations=valuations, entity_type="transfermarkt_only")
    explanation = build_growth_explanation(insight, player_context={"name": player["name"], "position": player["position"]})

    assert "summary" in explanation
    assert "score_reason" in explanation
    assert isinstance(explanation["strengths"], list) and explanation["strengths"]
    assert isinstance(explanation["risks"], list) and explanation["risks"]
    assert isinstance(explanation["recommendations"], list) and explanation["recommendations"]
    assert "data_limitations" in explanation
    assert "gemini_ready_payload" in explanation


def test_ceiling_model_mapping_functions():
    assert map_league_difficulty("low") == ("낮음", 0.5)
    assert map_league_difficulty("medium") == ("보통", 1.0)
    assert map_league_difficulty("high") == ("높음", 1.25)
    assert map_league_difficulty("elite") == ("매우 높음", 1.5)

    assert map_playing_opportunity(0.1) == ("낮음", 0.1)
    assert map_playing_opportunity(0.6) == ("높음", 0.7)

    assert map_training_intensity(0.5) == ("낮음", 1.0)
    assert map_training_intensity(2.0) == ("매우 높음", 2.0)

    assert map_risk_tendency("safe") == ("안정형", 0.10)
    assert map_risk_tendency("normal") == ("균형형", 0.25)
    assert map_risk_tendency("aggressive") == ("도전형", 0.40)


def test_compute_ceiling_scenario_adjustment_in_range():
    env_settings = {
        "training_intensity": 1.8,
        "playing_time_opportunity": 0.85,
        "league_difficulty": "elite",
        "career_choice": "transfer",
        "risk_level": "aggressive",
    }
    result = compute_ceiling_scenario_adjustment(env_settings)
    assert result["status"] == "ok"
    assert -15 <= result["scenario_adjustment"] <= 15
    assert result["alpha"] == 0.9
    assert result["gamma"] == 1.5
    assert result["training_multiplier"] == 2.0

    env_settings_extreme = {
        "training_intensity": 2.0,
        "playing_time_opportunity": 0.95,
        "league_difficulty": "elite",
        "career_choice": "transfer",
        "risk_level": "aggressive",
    }
    extreme_result = compute_ceiling_scenario_adjustment(env_settings_extreme)
    assert -15 <= extreme_result["scenario_adjustment"] <= 15


def test_ceiling_overload_risk_notes_and_calibration():
    result = compute_ceiling_scenario_adjustment({
        "training_intensity": 2.0,
        "playing_time_opportunity": 0.95,
        "league_difficulty": "elite",
        "career_choice": "transfer",
        "risk_level": "aggressive",
    })
    notes = " ".join(result["notes"])

    assert "과부하" in notes
    assert "부상" in notes
    assert result["scenario_adjustment"] < 15


def test_ceiling_elite_league_low_playing_risk_notes():
    result = compute_ceiling_scenario_adjustment({
        "training_intensity": 1.2,
        "playing_time_opportunity": 0.1,
        "league_difficulty": "elite",
        "career_choice": "transfer",
        "risk_level": "normal",
    })
    notes = " ".join(result["notes"])

    assert "벤치 정체" in notes
    assert "출전기회" in notes or "경기 감각" in notes


def test_apply_ceiling_adjustment_in_range():
    valuations = pd.DataFrame({
        "date": ["2024-01-01", "2025-01-01"],
        "market_value_in_eur": [1_000_000, 3_000_000],
        "current_club_name": ["Club A", "Club B"],
    })
    appearances = pd.DataFrame({
        "date": ["2025-01-01"] * 2,
        "competition_id": ["L1"] * 2,
        "goals": [1, 0],
        "assists": [0, 1],
        "yellow_cards": [0, 0],
        "red_cards": [0, 0],
        "minutes_played": [90, 80],
    })
    player = {"name": "Test Player", "position": "ST", "date_of_birth": "2005-01-01"}
    insight = build_growth_insight(player, None, appearances=appearances, valuations=valuations, entity_type="transfermarkt_only")

    env_settings = {
        "training_intensity": 1.2,
        "playing_time_opportunity": 0.6,
        "league_difficulty": "medium",
        "career_choice": "stay",
        "risk_level": "normal",
    }
    insight = apply_ceiling_adjustment(insight, env_settings)

    assert "ceiling_model" in insight
    ceiling_model = insight["ceiling_model"]
    assert 0.0 <= ceiling_model["final_growth_score"] <= 100.0
    assert -15 <= ceiling_model["scenario_adjustment"] <= 15


def test_manual_note_ceiling_model_and_explanation():
    manual_player = {"name": "Manual Player", "age": 19, "position": "CM"}
    manual_attributes = {"speed": 7, "dribble": 6, "finishing": 5, "passing": 7}
    career_settings = {
        "training_intensity": 1.5,
        "playing_time_opportunity": 0.7,
        "league_difficulty": "high",
        "career_choice": "transfer",
        "risk_level": "aggressive",
    }
    insight = build_manual_growth_insight(manual_player, manual_attributes, career_settings)
    insight = apply_ceiling_adjustment(insight, career_settings)

    assert "ceiling_model" in insight
    assert 0.0 <= insight["ceiling_model"]["final_growth_score"] <= 100.0

    explanation = build_growth_explanation(insight, player_context={"name": manual_player["name"], "position": manual_player["position"]})
    assert explanation["ceiling_explanation"] is not None
    assert "scenario_variables" in explanation["ceiling_explanation"]
    assert explanation["ceiling_explanation"]["scenario_strengths"]
    assert explanation["ceiling_explanation"]["scenario_risks"]
    assert explanation["ceiling_explanation"]["scenario_recommendations"]
    assert explanation["ceiling_explanation"]["scenario_nature"]
    assert "직접 입력한 능력치" in " ".join(explanation["ceiling_explanation"]["training_directions"])
    assert "β" not in " ".join(explanation["ceiling_explanation"]["risk_warnings"])

    payload = explanation["gemini_ready_payload"]
    assert "ceiling_model" in payload
    assert payload["ceiling_model"] is not None
    assert "ceiling_explanation" in payload


def test_low_contribution_builds_coaching_training_direction():
    insight = {
        "mode": "data_driven",
        "growth_score": 55.0,
        "features": {
            "contribution_score": {"status": "ok", "score": 0.2},
        },
        "risk_penalty": {"penalty": 0, "notes": []},
    }
    insight = apply_ceiling_adjustment(insight, {
        "training_intensity": 1.2,
        "playing_time_opportunity": 0.6,
        "league_difficulty": "medium",
        "career_choice": "stay",
        "risk_level": "normal",
    })
    explanation = build_growth_explanation(insight, player_context={"position": "ST"})
    directions = " ".join(explanation["ceiling_explanation"]["training_directions"])

    assert "결정력" in directions
    assert "판단 속도" in directions
    assert "기여도" in directions


def test_filter_mentor_candidates_by_age_primary_rule():
    candidates = [
        {"profile_id": 1, "age": 30},
        {"profile_id": 2, "age": 27},
        {"profile_id": 3, "age": 32},
        {"profile_id": 4, "age": 21},
    ]
    filtered, used_fallback = filter_mentor_candidates_by_age(candidates, target_age=21, min_results=1)

    assert {c["profile_id"] for c in filtered} == {1, 3}
    assert used_fallback is False


def test_filter_mentor_candidates_by_age_fallback_when_too_few():
    candidates = [
        {"profile_id": 1, "age": 26},
        {"profile_id": 2, "age": 24},
        {"profile_id": 3, "age": 21},
    ]
    filtered, used_fallback = filter_mentor_candidates_by_age(candidates, target_age=21, min_results=1)

    assert {c["profile_id"] for c in filtered} == {1}
    assert used_fallback is True


def test_filter_mentor_candidates_by_age_excludes_self_and_missing_age():
    candidates = [
        {"profile_id": 5, "age": 35},
        {"profile_id": 6, "age": None},
        {"profile_id": 7, "age": 0},
        {"profile_id": 8, "age": 29},
    ]
    filtered, used_fallback = filter_mentor_candidates_by_age(
        candidates, target_age=21, exclude_ids=[5], min_results=1,
    )

    assert {c["profile_id"] for c in filtered} == {8}
    assert used_fallback is False


def structured_payload_inputs(entity_type="matched"):
    growth_insight = {"growth_score": 61.0, "ceiling_model": {"final_growth_score": 69.0}}
    growth_explanation = {
        "summary": "성장 요약",
        "ceiling_explanation": {
            "coaching_summary": "코칭 총평",
            "training_directions": ["훈련 방향"],
        },
    }
    return {
        "entity_type": entity_type,
        "player": {"player_id": 10, "name": "Payload Player", "position": "ST"},
        "profile": {"profile_id": 20, "name": "Payload Player", "position": "ST"},
        "env_settings": {"training_intensity": 1.2, "career_choice": "stay"},
        "simulation_result": {"prototype_growth_score": 55},
        "growth_insight": growth_insight,
        "growth_explanation": growth_explanation,
        "ceiling_growth_insight": growth_insight,
        "ceiling_growth_explanation": growth_explanation,
        "ceiling_growth_context": {"entity_type": entity_type, "player_id": 10},
        "report_sections": {"Ceiling Scenario Insight": "코칭 총평"},
        "report_text": "저장 리포트",
    }


def test_ai_report_structured_note_payload():
    payload = build_ai_report_note_payload(**structured_payload_inputs())
    stored = payload["simulation_result"]

    assert payload["env_settings"]["note_type"] == "ai_report"
    assert payload["env_settings"]["source"] == "ai_report"
    assert stored["growth_insight"]["growth_score"] == 61.0
    assert stored["ceiling_growth_insight"]["ceiling_model"]["final_growth_score"] == 69.0
    assert stored["report_sections"]["Ceiling Scenario Insight"] == "코칭 총평"
    assert stored["generated_report_text"] == "저장 리포트"
    json.dumps(payload, ensure_ascii=False)


def test_manual_note_structured_note_payload():
    inputs = structured_payload_inputs("manual_note")
    inputs.update({
        "player": {"name": "Manual Payload Player", "age": 18, "club": "Academy"},
        "profile": None,
        "env_settings": {
            "note_type": "manual_custom_prospect",
            "manual_player": {"name": "Manual Payload Player", "age": 18},
            "manual_attributes": {"speed": 7},
            "career_settings": {"training_intensity": 1.2},
        },
        "ceiling_growth_context": {"entity_type": "manual_note", "source": "manual_note"},
    })
    payload = build_manual_note_payload(**inputs)

    assert payload["env_settings"]["note_type"] == "manual_custom_prospect"
    assert payload["env_settings"]["source"] == "manual_note"
    assert payload["env_settings"]["manual_player"]["name"] == "Manual Payload Player"
    assert payload["simulation_result"]["growth_explanation"]["ceiling_explanation"]["coaching_summary"] == "코칭 총평"


def test_manual_prospect_structured_note_payload():
    inputs = structured_payload_inputs("manual_prospect")
    inputs.update({
        "player": {"name": "Manual Prospect Player", "age": 18, "club": "Academy"},
        "profile": None,
        "env_settings": {
            "training_intensity": 1.2,
            "playing_time_opportunity": 0.6,
            "league_difficulty": "medium",
            "career_choice": "stay",
            "risk_level": "normal",
        },
        "ceiling_growth_context": {"entity_type": "manual_prospect", "source": "career_simulation"},
    })
    payload = build_manual_note_payload(**inputs)

    # entity_type은 manual_prospect로 유지되지만 note_type/source는 기존 DB 호환을 위해
    # manual_custom_prospect / manual_note로 유지된다.
    assert payload["env_settings"]["note_type"] == "manual_custom_prospect"
    assert payload["env_settings"]["source"] == "manual_note"
    assert payload["env_settings"]["entity_type"] == "manual_prospect"
    assert payload["simulation_result"]["ceiling_growth_context"]["entity_type"] == "manual_prospect"
    json.dumps(payload, ensure_ascii=False)


def test_career_simulation_structured_note_payload():
    payload = build_career_simulation_note_payload(**structured_payload_inputs("transfermarkt_only"))

    assert payload["env_settings"]["note_type"] == "career_simulation"
    assert payload["env_settings"]["source"] == "career_simulation"
    assert payload["env_settings"]["entity_type"] == "transfermarkt_only"
    assert payload["simulation_result"]["prototype_simulation"]["prototype_growth_score"] == 55
    assert payload["simulation_result"]["ceiling_growth_context"]["player_id"] == 10


def test_legacy_note_structured_result_fallback():
    legacy = {"prototype_growth_score": 44, "overall_summary": "legacy"}
    restored = extract_structured_note_result(legacy)

    assert restored["prototype_simulation"] == legacy
    assert restored["growth_insight"] == {}
    assert restored["ceiling_growth_explanation"] == {}


def test_scouting_note_payload_json_safety_and_compaction():
    converted = json_safe({
        "datetime": datetime(2026, 6, 16, 1, 2, 3),
        "tuple": (1, np.int64(2)),
        "nan": np.float64(np.nan),
        "pandas_na": pd.NA,
    })
    compacted = compact_report_sections({"긴 섹션": "x" * 6000})

    assert converted["datetime"] == "2026-06-16T01:02:03"
    assert converted["tuple"] == [1, 2]
    assert converted["nan"] is None
    assert converted["pandas_na"] is None
    assert compacted["긴 섹션"].endswith("... [truncated]")
    json.dumps({"converted": converted, "compacted": compacted}, ensure_ascii=False)


def test_scouting_note_payload_has_no_ui_or_db_dependency():
    source = inspect.getsource(scouting_note_payload)

    assert "import streamlit" not in source
    assert "services.db" not in source
    assert "import app" not in source


def test_saved_note_user_friendly_labels():
    assert saved_note_label("manual_custom_prospect", NOTE_TYPE_LABELS, "-") == "직접 입력 선수 노트"
    assert saved_note_label("career_simulation", SOURCE_LABELS, "-") == "커리어 시뮬레이션"
    assert saved_note_label("matched", SAVED_ENTITY_TYPE_LABELS, "-") == "실제 DB + FM 매칭 선수"
    assert saved_note_label("unknown", NOTE_TYPE_LABELS, "저장된 분석") == "저장된 분석"
    assert NOTE_TYPE_LABELS["ai_report"] == "규칙 기반 리포트 저장"
    assert SOURCE_LABELS["ai_report"] == "규칙 기반 리포트"


def test_saved_note_display_policy_and_legacy_fallback():
    coaching = {
        "coaching_summary": "저장된 코칭 총평",
        "training_directions": ["훈련 방향"],
        "expected_benefits": ["기대 장점"],
        "neglect_risks": ["소홀 리스크"],
        "risk_warnings": ["위험 경고"],
        "career_strategy": ["커리어 전략"],
    }
    sections = saved_coaching_sections(coaching, "legacy summary")

    assert [label for label, _ in sections] == [
        "종합 평가",
        "추천 훈련 방향",
        "기대 장점",
        "소홀히 했을 때의 단점",
        "리스크 경고",
        "추천 커리어 전략",
    ]
    assert sections[0][1] == "저장된 코칭 총평"
    assert saved_coaching_sections({}, "legacy summary") == [("종합 평가", "legacy summary")]
    assert saved_report_original({"gemini_report": "템플릿 원문"}, {"generated_report_text": "구조화 원문"}) == "템플릿 원문"
    assert saved_report_original({}, {"generated_report_text": "구조화 원문"}) == "구조화 원문"

    source = inspect.getsource(__import__("views.scouting_notes", fromlist=["render_scouting_notes_view"]))
    assert 'st.expander("상세 리포트 원문 보기")' in source
    assert 'st.expander("개발자용 저장 데이터 보기")' in source
    assert "선택된 멘토 없음" not in source


def test_explanation_engine_manual_note():
    manual_player = {"name": "Manual Player", "age": 19, "position": "CM"}
    manual_attributes = {"speed": 7, "dribble": 6, "finishing": 5, "passing": 7}
    career_settings = {
        "training_intensity": 0.6,
        "playing_time_opportunity": 0.2,
        "league_difficulty": "low",
        "risk_level": "safe",
    }
    insight = build_manual_growth_insight(manual_player, manual_attributes, career_settings)
    explanation = build_growth_explanation(insight, player_context={"name": manual_player["name"], "position": manual_player["position"]})

    assert "manual_prototype" in explanation["summary"] or "직접 입력" in explanation["summary"]
    assert explanation["strengths"]
    assert explanation["risks"]
    assert explanation["recommendations"]


def test_dashboard_growth_insight_renders_for_transfermarkt_only():
    at = AppTest.from_file("app.py")
    at.session_state["selected_player_id"] = 371998
    at.run(timeout=30)
    navigate_to(at, "유망주 통합 분석")
    assert not at.exception
    headers = "\n".join(s.value for s in at.subheader)
    # v18.3: TM-only 선수(≥25세)는 "현재 데이터 기반 성장 분석" 서브헤더를 사용한다.
    # 미래에 선수 데이터가 바뀔 경우를 대비해 두 값 중 하나라도 있으면 통과한다.
    assert "Growth Insight" in headers or "현재 데이터 기반 성장" in headers
    assert "growth_insight" in at.session_state
    assert "growth_explanation" in at.session_state


def test_player_dossier_shows_data_coverage_panel_for_limited_player():
    at = AppTest.from_file("app.py")
    at.session_state["selected_player_id"] = 371998
    at.run(timeout=30)
    navigate_to(at, "유망주 통합 분석")
    assert not at.exception

    titles = "\n".join(t.value for t in at.title)
    markdown = "\n".join(m.value for m in at.markdown)
    assert "Player Dossier" in titles
    assert "Data Coverage Panel" in markdown
    assert "분석 준비도 Limited" in markdown
    assert "직접 입력 유망주로 보완" in "\n".join(button.label for button in at.button)


def test_career_simulation_ceiling_sections_render():
    at = AppTest.from_file("app.py")
    at.session_state["selected_player_id"] = 371998
    at.run(timeout=30)
    navigate_to(at, "커리어 시뮬레이션")
    assert not at.exception

    headers = "\n".join(s.value for s in at.subheader)
    assert "Real Data Growth Baseline" in headers
    assert "코칭 시나리오 리포트" in headers
    assert "Final Growth Score" in headers
    coaching_text = "\n".join(m.value for m in at.markdown)
    assert "추천 훈련 방향" in coaching_text
    assert "기대 장점" in coaching_text
    assert "리스크 경고" in coaching_text
    assert "추천 커리어 전략" in coaching_text
    assert "상세 계산 근거" in "\n".join(e.label for e in at.expander)
    assert "ceiling_model" in at.session_state["growth_insight"]
    assert "ceiling_explanation" in at.session_state["growth_explanation"]
    assert "ceiling_model" in at.session_state["ceiling_growth_insight"]
    assert "ceiling_explanation" in at.session_state["ceiling_growth_explanation"]
    assert at.session_state["ceiling_growth_context"]["player_id"] == 371998
    assert at.session_state["ceiling_growth_context"]["source"] == "career_simulation"
    assert "현재 시뮬레이션 결과를 스카우팅 노트에 저장" in "\n".join(button.label for button in at.button)


def create_manual_prospect(at, name="Custom Prospect A"):
    navigate_to(at, "직접 입력 유망주")
    assert not at.exception

    name_inputs = [t for t in at.text_input if "이름" in (t.label or "")]
    assert name_inputs
    name_inputs[0].set_value(name)

    submit_buttons = [b for b in at.button if "생성" in (b.label or "")]
    assert submit_buttons
    submit_buttons[0].click().run(timeout=30)
    assert not at.exception
    return at


def test_manual_prospect_creation_session_state():
    at = AppTest.from_file("app.py")
    at.run(timeout=30)
    create_manual_prospect(at)

    assert at.session_state["selected_entity_type"] == "manual_prospect"
    assert at.session_state["manual_player"]["name"] == "Custom Prospect A"
    assert "manual_attributes" in at.session_state
    assert "manual_career_settings" in at.session_state

    assert at.session_state["growth_insight"]["mode"] == "manual_prototype"
    assert "growth_explanation" in at.session_state
    assert "ceiling_growth_insight" not in at.session_state

    metric_labels = "\n".join(m.label for m in at.metric)
    assert "Manual Growth Score (기본)" in metric_labels


def test_manual_prospect_full_flow_through_career_simulation_and_ai_report():
    at = AppTest.from_file("app.py")
    at.run(timeout=30)
    create_manual_prospect(at, name="Custom Prospect B")

    navigate_to(at, "유망주 통합 분석")
    assert not at.exception
    assert at.session_state["growth_insight"]["mode"] == "manual_prototype"

    navigate_to(at, "커리어 시뮬레이션")
    assert not at.exception
    headers = "\n".join(s.value for s in at.subheader)
    assert "Manual Growth Baseline" in headers
    assert "코칭 시나리오 리포트" in headers
    assert "Final Growth Score" in headers
    assert at.session_state["ceiling_growth_context"]["entity_type"] == "manual_prospect"
    assert at.session_state["ceiling_growth_context"]["source"] == "career_simulation"
    assert "ceiling_model" in at.session_state["ceiling_growth_insight"]

    navigate_to(at, "유사 선수 후보")
    assert not at.exception

    navigate_to(at, "AI 스카우팅 리포트")
    assert not at.exception
    report_buttons = [button for button in at.button if button.label == "리포트 초안 생성"]
    assert report_buttons
    report_buttons[0].click().run(timeout=30)
    assert not at.exception
    assert "Ceiling Scenario Insight" in at.session_state["generated_report_sections"]

    save_buttons = [button for button in at.button if "이 분석 리포트를 My Scouting Notes에 저장" in (button.label or "")]
    assert save_buttons


def test_scouting_notes_view_has_no_creation_form():
    from views.scouting_notes import render_scouting_notes_view

    source = inspect.getsource(render_scouting_notes_view)
    assert "manual_prospect_form" not in source
    assert "custom_note_form" not in source
    assert "직접 입력 유망주" in source


def test_ceiling_result_survives_dashboard_and_ai_report():
    at = AppTest.from_file("app.py")
    at.session_state["selected_player_id"] = 371998
    at.run(timeout=30)
    navigate_to(at, "커리어 시뮬레이션")
    assert not at.exception

    ceiling_context = dict(at.session_state["ceiling_growth_context"])
    ceiling_final_score = at.session_state["ceiling_growth_insight"]["ceiling_model"]["final_growth_score"]

    navigate_to(at, "유망주 통합 분석")
    assert not at.exception
    assert "ceiling_model" not in at.session_state["growth_insight"]
    assert at.session_state["ceiling_growth_context"] == ceiling_context
    assert at.session_state["ceiling_growth_insight"]["ceiling_model"]["final_growth_score"] == ceiling_final_score

    navigate_to(at, "AI 스카우팅 리포트")
    assert not at.exception
    report_buttons = [button for button in at.button if button.label == "리포트 초안 생성"]
    assert report_buttons
    report_buttons[0].click().run(timeout=30)
    assert not at.exception
    assert "Ceiling Scenario Insight" in at.session_state["generated_report_sections"]
    ceiling_report = at.session_state["generated_report_sections"]["Ceiling Scenario Insight"]
    assert "추천 훈련 방향" in ceiling_report
    assert "리스크 경고" in ceiling_report
    assert "추천 커리어 전략" in ceiling_report
    assert "training_multiplier=" not in ceiling_report
    assert "이 분석 리포트를 My Scouting Notes에 저장" in "\n".join(button.label for button in at.button)


def test_selecting_different_player_clears_growth_session_state():
    at = AppTest.from_file("app.py")
    at.session_state["selected_player_id"] = 371998
    at.session_state["prospect_results"] = pd.DataFrame([{
        "player_id": 418560,
        "profile_id": 418560,
        "name": "Different Player",
        "age": 20,
        "position": "Midfield",
        "sub_position": "Central Midfield",
        "country_of_citizenship": "Test",
        "current_club_name": "Test Club",
        "market_value_in_eur": 1_000_000,
        "has_style_vector": True,
        "has_attributes": True,
        "has_mentality": True,
    }])
    at.session_state["last_search_filters"] = {"min_age": 15, "max_age": 25, "position": "All"}
    for key in [
        "growth_insight",
        "growth_explanation",
        "ceiling_growth_insight",
        "ceiling_growth_explanation",
        "ceiling_growth_context",
        "generated_report_sections",
        "generated_report_text",
    ]:
        at.session_state[key] = {"stale": True}

    at.run(timeout=30)
    navigate_to(at, "유망주 검색")
    assert not at.exception
    select_buttons = [button for button in at.button if button.key == "select_prospect_418560"]
    assert select_buttons
    select_buttons[0].click().run(timeout=30)
    assert not at.exception

    assert at.session_state["selected_player_id"] == 418560
    for key in [
        "growth_insight",
        "growth_explanation",
        "ceiling_growth_insight",
        "ceiling_growth_explanation",
        "ceiling_growth_context",
        "generated_report_sections",
        "generated_report_text",
    ]:
        assert key not in at.session_state


# ============================================================
# v18: Qualitative Evidence + Gemini Advisory — unit tests
# 실제 Gemini API 호출은 수행하지 않는다.
# API key가 없는 환경에서도 전부 통과해야 한다.
# ============================================================


def test_qualitative_evidence_importable_without_api_key():
    """services/qualitative_evidence.py는 API key 없이도 import 가능해야 한다."""
    import importlib
    mod = importlib.import_module("services.qualitative_evidence")
    assert hasattr(mod, "make_fallback_signals")
    assert hasattr(mod, "make_fallback_advisory")
    assert hasattr(mod, "extract_qualitative_signals")
    assert hasattr(mod, "generate_gemini_advisory")
    assert hasattr(mod, "build_qualitative_evidence_payload")


def test_qualitative_evidence_fallback_without_api_key():
    """API key 유무에 관계없이 함수가 유효한 dict를 반환하고 예외를 던지지 않는다.
    key 없음 → 'no_api_key' fallback, key 있음 → 실제 호출(성공/실패) 또는 api_error fallback.
    어떤 경우에도 앱이 깨지지 않는 것이 핵심 불변식이다.
    """
    from services.qualitative_evidence import extract_qualitative_signals, generate_gemini_advisory

    signals, err = extract_qualitative_signals("기사 내용", {"name": "Test Player"})
    assert isinstance(signals, dict)
    # _fallback_reason은 key 설정 여부/API 상태에 따라 다르므로 허용 범위로 검사
    assert signals.get("_fallback_reason") in ("no_api_key", "api_error", "parse_failed", None)
    # err는 None이거나 문자열 에러 메시지 (API 오류 시)
    assert err is None or isinstance(err, str)
    assert signals.get("confidence") in ("low", "medium", "high")
    assert isinstance(signals.get("strength_mentions", []), list)

    advisory, err2 = generate_gemini_advisory({"name": "Test"}, {}, signals)
    assert isinstance(advisory, dict)
    assert advisory.get("_fallback_reason") in ("no_api_key", "api_error", "parse_failed", None)
    assert err2 is None or isinstance(err2, str)
    assert advisory.get("confidence") in ("low", "medium", "high")
    assert isinstance(advisory.get("training_recommendations", []), list)


def test_qualitative_evidence_fallback_with_no_text():
    """텍스트 입력이 없으면 no_text_input fallback이 반환되고 기존 분석 흐름이 유지된다."""
    from services.qualitative_evidence import extract_qualitative_signals

    signals, err = extract_qualitative_signals("", None)
    assert signals["_fallback_reason"] == "no_text_input"
    assert err is None

    signals2, err2 = extract_qualitative_signals("   ", None)
    assert signals2["_fallback_reason"] == "no_text_input"
    assert err2 is None

    signals3, err3 = extract_qualitative_signals(None, None)
    assert signals3["_fallback_reason"] == "no_text_input"
    assert err3 is None


def test_qualitative_evidence_safe_json_parsing():
    """_safe_parse_json이 다양한 입력에서 안전하게 동작한다."""
    from services.qualitative_evidence import _safe_parse_json

    valid_json = '{"qualitative_summary": "요약", "confidence": "medium"}'
    result = _safe_parse_json(valid_json)
    assert result is not None
    assert result["confidence"] == "medium"

    markdown_wrapped = '```json\n{"qualitative_summary": "요약"}\n```'
    result2 = _safe_parse_json(markdown_wrapped)
    assert result2 is not None
    assert result2["qualitative_summary"] == "요약"

    assert _safe_parse_json("completely invalid text ###") is None
    assert _safe_parse_json("") is None
    assert _safe_parse_json(None) is None
    assert _safe_parse_json(123) is None


def test_qualitative_evidence_bad_json_does_not_crash():
    """잘못된 JSON 응답이 와도 앱이 깨지지 않고 fallback 결과가 반환된다."""
    from services.qualitative_evidence import _validate_signals, _validate_advisory

    result = _validate_signals(None)
    assert isinstance(result, dict)
    assert result.get("_fallback_reason") == "parse_failed"
    assert result["confidence"] == "low"

    result2 = _validate_signals({"confidence": "invalid_value", "strength_mentions": "not a list"})
    assert result2["confidence"] == "low"
    assert isinstance(result2["strength_mentions"], list)

    adv = _validate_advisory(None)
    assert isinstance(adv, dict)
    assert adv.get("_fallback_reason") == "parse_failed"
    assert isinstance(adv["training_recommendations"], list)


def test_qualitative_signals_json_serializable():
    """qualitative signals dict가 JSON 직렬화 가능해야 한다."""
    from services.qualitative_evidence import make_fallback_signals, _validate_signals

    fallback = make_fallback_signals("no_api_key")
    json.dumps(fallback, ensure_ascii=False)

    valid = _validate_signals({
        "qualitative_summary": "요약",
        "playing_time_signal": "positive",
        "injury_risk_signal": "negative",
        "coach_trust_signal": "unknown",
        "development_signal": "neutral",
        "transfer_rumor_signal": "low",
        "mentality_signal": "positive",
        "strength_mentions": ["스피드", "드리블"],
        "weakness_mentions": ["슈팅"],
        "risk_mentions": ["부상 이력"],
        "recommended_focus": ["마무리 훈련"],
        "evidence_quotes": ["훈련 태도가 매우 성실"],
        "confidence": "high",
    })
    json.dumps(valid, ensure_ascii=False)


def test_gemini_advisory_json_serializable():
    """gemini advisory dict가 JSON 직렬화 가능해야 한다."""
    from services.qualitative_evidence import make_fallback_advisory, _validate_advisory

    fallback = make_fallback_advisory("no_api_key")
    json.dumps(fallback, ensure_ascii=False)

    valid = _validate_advisory({
        "advisory_summary": "종합 요약",
        "player_fit_assessment": "현재 역할에 적합",
        "training_recommendations": ["스피드 훈련"],
        "career_recommendations": ["현재팀 잔류 권장"],
        "risk_management": ["부상 방지 관리"],
        "mentor_usage_recommendations": ["멘토 관찰"],
        "what_to_monitor_next": ["다음 시즌 출전 시간"],
        "unsupported_or_unknown": ["이적설 — 텍스트 언급 없음"],
        "final_scouting_comment": "잠재력 높은 유망주",
        "confidence": "medium",
    })
    json.dumps(valid, ensure_ascii=False)


def test_qualitative_evidence_payload_json_serializable():
    """build_qualitative_evidence_payload 결과가 JSON 직렬화 가능해야 한다."""
    from services.qualitative_evidence import build_qualitative_evidence_payload, make_fallback_signals

    signals = make_fallback_signals("no_api_key")
    payload = build_qualitative_evidence_payload("기사 내용", signals)
    assert isinstance(payload, dict)
    assert payload["source"] == "manual_text_input"
    assert "created_at" in payload
    json.dumps(payload, ensure_ascii=False)

    payload2 = build_qualitative_evidence_payload("x" * 1000, signals)
    assert len(payload2["input_text_snapshot"]) <= 503
    json.dumps(payload2, ensure_ascii=False)


def test_scouting_note_payload_includes_qualitative_fields():
    """qualitative_evidence와 gemini_advisory가 payload에 포함되고 직렬화 가능해야 한다."""
    qual_evidence = {
        "source": "manual_text_input",
        "input_text_snapshot": "기사 요약",
        "extracted_signals": {"playing_time_signal": "positive", "confidence": "medium"},
        "created_at": "2026-06-18T00:00:00",
    }
    adv_payload = {
        "advisory_summary": "종합 요약",
        "training_recommendations": ["스피드 훈련"],
        "confidence": "medium",
    }
    inputs = structured_payload_inputs()
    inputs["qualitative_evidence"] = qual_evidence
    inputs["gemini_advisory"] = adv_payload

    payload = build_ai_report_note_payload(**inputs)
    stored = payload["simulation_result"]

    assert stored["qualitative_evidence"]["source"] == "manual_text_input"
    assert stored["gemini_advisory"]["advisory_summary"] == "종합 요약"
    assert payload["env_settings"]["report_generation_mode"] == "rule_based_with_gemini"
    assert payload["env_settings"]["qualitative_evidence_source"] == "manual_text_input"
    json.dumps(payload, ensure_ascii=False)


def test_scouting_note_payload_without_qualitative_fields():
    """qualitative_evidence가 없어도 기존 리포트 구조가 그대로 유지된다."""
    payload = build_ai_report_note_payload(**structured_payload_inputs())
    stored = payload["simulation_result"]

    assert stored["qualitative_evidence"] == {}
    assert stored["gemini_advisory"] == {}
    assert payload["env_settings"]["report_generation_mode"] == "rule_based"
    assert payload["env_settings"]["qualitative_evidence_source"] == "none"
    json.dumps(payload, ensure_ascii=False)


def test_extract_structured_note_result_includes_qualitative():
    """extract_structured_note_result가 qualitative_evidence와 gemini_advisory를 복원한다."""
    simulation_result = {
        "prototype_growth_score": 55,
        "qualitative_evidence": {"source": "manual_text_input", "confidence": "medium"},
        "gemini_advisory": {"advisory_summary": "보조 요약", "confidence": "low"},
    }
    restored = extract_structured_note_result(simulation_result)

    assert restored["qualitative_evidence"]["source"] == "manual_text_input"
    assert restored["gemini_advisory"]["advisory_summary"] == "보조 요약"


def test_legacy_note_fallback_maintained_with_qualitative_fields():
    """qualitative_evidence/gemini_advisory가 없는 legacy note도 fallback이 동작한다."""
    legacy = {"prototype_growth_score": 44, "overall_summary": "legacy"}
    restored = extract_structured_note_result(legacy)

    assert restored["prototype_simulation"] == legacy
    assert restored["growth_insight"] == {}
    assert restored["qualitative_evidence"] == {}
    assert restored["gemini_advisory"] == {}


def test_ai_report_view_has_qualitative_section():
    """views/ai_report.py에 정성 텍스트 근거 분석 섹션이 존재한다."""
    import inspect
    from views.ai_report import render_ai_report_view, _render_qualitative_section

    source = inspect.getsource(render_ai_report_view)
    assert "_render_qualitative_section" in source
    assert "qualitative_text_input" in inspect.getsource(_render_qualitative_section)


def test_qualitative_evidence_service_has_no_ui_or_db_dependency():
    """services/qualitative_evidence.py는 streamlit, DB, app.py를 import하지 않는다."""
    import inspect
    import services.qualitative_evidence as qe_mod

    source = inspect.getsource(qe_mod)
    assert "import streamlit" not in source
    assert "services.db" not in source
    assert "import app" not in source


def test_manual_prospect_flow_not_broken_by_v18():
    """기존 manual_prospect 흐름이 v18 이후에도 깨지지 않는다."""
    at = AppTest.from_file("app.py")
    at.run(timeout=30)
    create_manual_prospect(at, name="V18 Test Prospect")

    assert at.session_state["selected_entity_type"] == "manual_prospect"
    assert at.session_state["manual_player"]["name"] == "V18 Test Prospect"
    assert at.session_state["growth_insight"]["mode"] == "manual_prototype"

    navigate_to(at, "커리어 시뮬레이션")
    assert not at.exception
    assert at.session_state["ceiling_growth_context"]["entity_type"] == "manual_prospect"


# ============================================================
# v18.1: Gemini runtime QA and user guidance
# ============================================================


def test_qualitative_section_has_example_texts_expander():
    """_render_qualitative_section에 테스트용 정성 텍스트 입력 예시 expander가 존재한다."""
    import inspect
    from views.ai_report import _render_qualitative_section

    source = inspect.getsource(_render_qualitative_section)
    assert "테스트용 정성 텍스트 입력 예시" in source


def test_qualitative_api_key_guidance_mentions_key_name():
    """API key 안내 메시지에 GEMINI_API_KEY가 언급된다."""
    import inspect
    import views.ai_report as ai_report_mod

    source = inspect.getsource(ai_report_mod)
    assert "GEMINI_API_KEY" in source
    assert "_GEMINI_API_KEY_GUIDANCE" in source


# ============================================================
# v18.2: Gemini API runtime integration QA
# 실제 Gemini API 호출은 수행하지 않는다.
# API key 없는 환경에서도 전부 통과해야 한다.
# ============================================================


def test_augment_sections_no_longer_blocks_successful_signals():
    """_augment_sections_with_qualitative의 has_signals 체크에서 None이 제거되었다.
    수정 전: not in ("no_text_input", "no_api_key", None) → 성공 신호(None 없음) 차단 버그.
    수정 후: not in ("no_text_input", "no_api_key", "api_error", "parse_failed") → 성공 신호 정상 통과.
    """
    import inspect
    from views.ai_report import _augment_sections_with_qualitative

    source = inspect.getsource(_augment_sections_with_qualitative)
    assert '"no_text_input", "no_api_key", None' not in source
    assert '"api_error"' in source
    assert '"parse_failed"' in source


def test_save_exclude_fallback_reasons_includes_api_error():
    """저장 payload 필터 상수 _SAVE_EXCLUDE_FALLBACK_REASONS에 api_error가 포함되어 있다."""
    import inspect
    import views.ai_report as ai_report_mod

    source = inspect.getsource(ai_report_mod)
    assert "_SAVE_EXCLUDE_FALLBACK_REASONS" in source
    assert '"api_error"' in source


def test_api_error_payload_does_not_set_rule_based_with_gemini():
    """api_error 시 qual_evidence=None → report_generation_mode는 rule_based를 유지한다."""
    inputs = structured_payload_inputs()
    inputs["qualitative_evidence"] = None
    inputs["gemini_advisory"] = None

    payload = build_ai_report_note_payload(**inputs)
    assert payload["env_settings"]["report_generation_mode"] == "rule_based"
    assert payload["env_settings"]["qualitative_evidence_source"] == "none"
    json.dumps(payload, ensure_ascii=False)


def test_gemini_sdk_unavailable_reason_returns_valid_value():
    """get_gemini_sdk_unavailable_reason은 None, 'no_api_key', 'sdk_not_installed' 중 하나를 반환한다."""
    from gemini_client import get_gemini_sdk_unavailable_reason

    reason = get_gemini_sdk_unavailable_reason()
    assert reason in (None, "no_api_key", "sdk_not_installed")


def test_gemini_client_has_sdk_install_guidance():
    """gemini_client.py에 google-genai 설치 안내와 신/구 SDK 분기가 포함되어 있다."""
    import inspect
    import gemini_client

    source = inspect.getsource(gemini_client)
    assert "pip install -U google-genai" in source
    assert "google-genai" in source
    assert "get_gemini_sdk_unavailable_reason" in source
    assert "sdk_not_installed" in source


def test_render_qualitative_section_has_sdk_not_installed_guidance():
    """_render_qualitative_section에 SDK 미설치 안내 분기와 상수가 있다."""
    import inspect
    from views.ai_report import _render_qualitative_section
    import views.ai_report as ai_report_mod

    section_source = inspect.getsource(_render_qualitative_section)
    module_source = inspect.getsource(ai_report_mod)
    assert "sdk_not_installed" in section_source
    assert "_SDK_NOT_INSTALLED_GUIDANCE" in module_source


def test_gemini_client_supports_both_sdk_imports():
    """gemini_client.py가 google.genai(신규)와 google.generativeai(구) 양쪽을 지원한다."""
    import inspect
    import gemini_client

    source = inspect.getsource(gemini_client)
    assert "from google import genai" in source
    assert "google.generativeai" in source


def test_qualitative_evidence_safe_parse_markdown_code_block():
    """_safe_parse_json이 다양한 markdown code block 형식을 정상적으로 파싱한다."""
    from services.qualitative_evidence import _safe_parse_json

    # 백틱 3개 + json 태그
    result = _safe_parse_json('```json\n{"confidence": "high"}\n```')
    assert result is not None
    assert result["confidence"] == "high"

    # 백틱 3개 + 태그 없음
    result2 = _safe_parse_json('```\n{"confidence": "medium"}\n```')
    assert result2 is not None
    assert result2["confidence"] == "medium"

    # 정상 JSON
    result3 = _safe_parse_json('{"confidence": "low"}')
    assert result3 is not None
    assert result3["confidence"] == "low"

    # JSON이 앞뒤 텍스트에 둘러싸인 경우
    result4 = _safe_parse_json('here is the json: {"confidence": "high"} end')
    assert result4 is not None
    assert result4["confidence"] == "high"


# ============================================================
# v18.3: 데이터 커버리지 gating 및 유망주 적격성 정리
# DB/Streamlit 의존 없이 순수 unit 테스트로 검증한다.
# ============================================================


def test_build_data_coverage_transfermarkt_only_is_not_full():
    """Transfermarkt-only 선수(profile=None)는 analysis_level이 'full'이 아니어야 한다."""
    from player_coverage import build_data_coverage

    player = {"player_id": 999, "name": "TM Only", "date_of_birth": "2005-01-01"}
    coverage = build_data_coverage(player, None)

    assert not coverage["has_fm_profile"]
    assert not coverage["has_style_vector"]
    assert coverage["analysis_level"] != "full"
    assert "FM 프로필 없음" in coverage["missing_reasons"]
    assert "style_vector 없음" in coverage["missing_reasons"]


def test_build_data_coverage_full_analysis():
    """player + FM profile + style_vector + age가 모두 있으면 analysis_level == 'full'."""
    from player_coverage import build_data_coverage

    player = {"player_id": 1, "name": "Full Player"}
    profile = {
        "profile_id": 1,
        "age": 21,
        "style_vector": [0.1] * 24,
        "attributes_jsonb": "{}",
        "mentality_jsonb": "{}",
    }
    coverage = build_data_coverage(player, profile)

    assert coverage["analysis_level"] == "full"
    assert coverage["has_fm_profile"]
    assert coverage["has_style_vector"]
    assert coverage["has_age"]
    assert not any(
        r in ("FM 프로필 없음", "style_vector 없음", "나이 데이터 없음")
        for r in coverage["missing_reasons"]
    )


def test_build_data_coverage_no_fm_profile_not_eligible_for_mentor():
    """FM profile이 없으면 has_fm_profile=False — 유사 선수(멘토) 분석 불가."""
    from player_coverage import build_data_coverage

    player = {"player_id": 42, "name": "No Profile", "date_of_birth": "2003-03-15"}
    coverage = build_data_coverage(player, None)

    assert not coverage["has_fm_profile"]
    # 멘토 분석 gating 조건: has_fm_profile AND has_style_vector
    assert not (coverage["has_fm_profile"] and coverage["has_style_vector"])


def test_build_data_coverage_no_style_vector_not_full():
    """FM profile이 있어도 style_vector가 None이면 analysis_level != 'full'."""
    from player_coverage import build_data_coverage

    player = {"player_id": 1}
    profile = {"profile_id": 1, "age": 22, "style_vector": None}
    coverage = build_data_coverage(player, profile)

    assert coverage["has_fm_profile"]
    assert not coverage["has_style_vector"]
    assert coverage["analysis_level"] != "full"
    assert "style_vector 없음" in coverage["missing_reasons"]


def test_resolve_player_age_from_profile():
    """profile.age가 있으면 그 값을 float으로 반환한다."""
    from player_coverage import resolve_player_age

    profile = {"age": 21}
    age = resolve_player_age({}, profile)
    assert age == 21.0


def test_resolve_player_age_from_dob_fallback():
    """profile이 없어도 date_of_birth로 나이를 계산한다."""
    from player_coverage import resolve_player_age

    # 오늘(2026-06-18) 기준 기대 나이: 약 26세
    player = {"date_of_birth": "2000-06-18"}
    age = resolve_player_age(player, None)

    assert age is not None
    assert 25 <= age <= 27


def test_resolve_player_age_consistent_across_sources():
    """profile.age와 date_of_birth 기반 나이가 합리적 범위 내에서 일치한다."""
    from player_coverage import resolve_player_age

    profile = {"age": 22.0}
    player_with_dob = {"date_of_birth": "2004-01-15"}

    age_from_profile = resolve_player_age({}, profile)
    age_from_dob = resolve_player_age(player_with_dob, None)

    assert age_from_profile == 22.0
    # DOB 기반 나이: 2026-06-18 기준 약 22.4세
    assert age_from_dob is not None
    assert 21 <= age_from_dob <= 23


def test_resolve_player_age_none_when_no_data():
    """player도 profile도 없으면 None을 반환한다."""
    from player_coverage import resolve_player_age

    assert resolve_player_age({}, None) is None
    assert resolve_player_age(None, None) is None


def test_prospect_search_filter_default_is_on():
    """유망주 검색 화면의 'FM profile 있는 선수만 보기' 체크박스가 기본값 True로 설정된다."""
    import inspect
    from views.prospect_search import render_prospect_search_view

    source = inspect.getsource(render_prospect_search_view)
    assert "value=True" in source
    assert "analyze_only" in source
    assert "FM profile" in source
    assert "15, 25" in source


def test_prospect_search_filter_logic_uses_profile_id_notna():
    """analyze_only 필터가 profile_id.notna()로 후처리 필터링을 수행한다 (DB 스키마 변경 없음)."""
    import inspect
    from views.prospect_search import render_prospect_search_view

    source = inspect.getsource(render_prospect_search_view)
    assert "profile_id" in source
    assert "notna()" in source


def test_prospect_search_shows_limited_notice_for_tm_only():
    """FM profile 없는 선수에게 제한 분석 안내 상수(_LIMITED_ANALYSIS_NOTICE)가 표시된다."""
    import inspect
    from views import prospect_search as ps_mod

    assert hasattr(ps_mod, "_LIMITED_ANALYSIS_NOTICE")
    assert "FM" in ps_mod._LIMITED_ANALYSIS_NOTICE

    source = inspect.getsource(ps_mod.render_prospect_search_view)
    assert "has_profile" in source
    assert "_LIMITED_ANALYSIS_NOTICE" in source


def test_v19_scouting_board_limited_policy_and_filters():
    """v19 Phase 1: 기본은 Full/Partial 중심이며 Limited는 옵션 또는 analyze_only 해제 시 표시된다."""
    import inspect
    from views.prospect_search import render_prospect_search_view

    source = inspect.getsource(render_prospect_search_view)
    assert "Scouting Board" in source
    assert "전체 DB 선수 포함" in source
    assert "Limited 선수 포함" in source
    assert '["Full", "Partial", "Limited"]' in source
    assert 'default=["Full", "Partial"]' in source
    assert "limited_visible = include_limited or include_all_db or not analyze_only" in source
    assert "notna()" in source


def test_v19_data_coverage_helpers_available():
    """공통 badge/panel helper가 ui_components에 존재하고 Manual/Full/Partial/Limited 라벨을 제공한다."""
    import inspect
    import ui_components

    source = inspect.getsource(ui_components)
    assert "render_data_coverage_panel" in source
    assert "render_data_coverage_badge" in source
    assert "coverage_badge_html" in source
    assert "manual_prospect" in source
    assert "Full" in source and "Partial" in source and "Limited" in source and "Manual" in source


def test_legend_matching_gates_on_style_vector():
    """유사 선수 후보 화면이 style_vector 없을 때 get_similar_players 호출 전에 조기 반환한다."""
    import inspect
    from views.legend_matching import render_legend_matching_view

    source = inspect.getsource(render_legend_matching_view)
    assert 'profile.get("style_vector")' in source
    assert "get_similar_players" in source
    # style_vector 체크 블록이 get_similar_players 호출보다 앞에 있어야 한다.
    sv_pos = source.index('profile.get("style_vector")')
    sim_pos = source.index("get_similar_players")
    assert sv_pos < sim_pos


def test_manual_prospect_not_broken_by_v18_3():
    """manual_prospect 흐름이 v18.3 이후에도 깨지지 않는다."""
    import inspect
    from views import legend_matching as lm_mod
    from views.legend_matching import render_legend_matching_view

    source = inspect.getsource(render_legend_matching_view)
    assert "manual_player" in source
    assert "render_manual_prospect_mentors" in source

    lm_source = inspect.getsource(lm_mod)
    assert "from player_coverage import build_data_coverage" in lm_source
    assert "render_manual_prospect_mentors(manual_player)" in lm_source


def test_v18_3_gemini_not_broken():
    """v18.3 변경 이후 Gemini 관련 함수가 여전히 import 가능하고 fallback이 동작한다."""
    from services.qualitative_evidence import (
        extract_qualitative_signals,
        generate_gemini_advisory,
        make_fallback_signals,
        make_fallback_advisory,
    )
    from gemini_client import get_gemini_sdk_unavailable_reason

    reason = get_gemini_sdk_unavailable_reason()
    assert reason in (None, "no_api_key", "sdk_not_installed")

    signals, err = extract_qualitative_signals("", None)
    assert signals["_fallback_reason"] == "no_text_input"
    assert err is None


def test_v18_3_legacy_saved_note_fallback_maintained():
    """v18.3 이후에도 legacy 저장 노트의 extract_structured_note_result fallback이 유지된다."""
    from scouting_note_payload import extract_structured_note_result

    legacy = {"prototype_growth_score": 44, "overall_summary": "legacy note"}
    restored = extract_structured_note_result(legacy)

    assert restored["prototype_simulation"] == legacy
    assert restored["growth_insight"] == {}
    assert restored["qualitative_evidence"] == {}
    assert restored["gemini_advisory"] == {}


def test_player_coverage_has_no_ui_or_db_dependency():
    """player_coverage.py는 streamlit, DB, app.py를 import하지 않는다."""
    import inspect
    import player_coverage

    source = inspect.getsource(player_coverage)
    assert "import streamlit" not in source
    assert "services.db" not in source
    assert "import app" not in source


if __name__ == "__main__":
    test_market_momentum_with_two_valuations()
    print("test_market_momentum_with_two_valuations OK")
    test_market_momentum_unavailable_with_insufficient_data()
    print("test_market_momentum_unavailable_with_insufficient_data OK")
    test_no_profile_handling()
    print("test_no_profile_handling OK")
    test_playing_opportunity_appearance_fallback()
    print("test_playing_opportunity_appearance_fallback OK")
    test_growth_score_reweighting_on_missing_data()
    print("test_growth_score_reweighting_on_missing_data OK")
    test_final_growth_score_in_range()
    print("test_final_growth_score_in_range OK")
    test_manual_growth_score_calculation()
    print("test_manual_growth_score_calculation OK")
    test_classification_helpers()
    print("test_classification_helpers OK")
    test_ceiling_model_mapping_functions()
    print("test_ceiling_model_mapping_functions OK")
    test_compute_ceiling_scenario_adjustment_in_range()
    print("test_compute_ceiling_scenario_adjustment_in_range OK")
    test_ceiling_overload_risk_notes_and_calibration()
    print("test_ceiling_overload_risk_notes_and_calibration OK")
    test_ceiling_elite_league_low_playing_risk_notes()
    print("test_ceiling_elite_league_low_playing_risk_notes OK")
    test_apply_ceiling_adjustment_in_range()
    print("test_apply_ceiling_adjustment_in_range OK")
    test_manual_note_ceiling_model_and_explanation()
    print("test_manual_note_ceiling_model_and_explanation OK")
    test_low_contribution_builds_coaching_training_direction()
    print("test_low_contribution_builds_coaching_training_direction OK")
    test_ai_report_structured_note_payload()
    print("test_ai_report_structured_note_payload OK")
    test_manual_note_structured_note_payload()
    print("test_manual_note_structured_note_payload OK")
    test_manual_prospect_structured_note_payload()
    print("test_manual_prospect_structured_note_payload OK")
    test_career_simulation_structured_note_payload()
    print("test_career_simulation_structured_note_payload OK")
    test_legacy_note_structured_result_fallback()
    print("test_legacy_note_structured_result_fallback OK")
    test_scouting_note_payload_json_safety_and_compaction()
    print("test_scouting_note_payload_json_safety_and_compaction OK")
    test_scouting_note_payload_has_no_ui_or_db_dependency()
    print("test_scouting_note_payload_has_no_ui_or_db_dependency OK")
    test_saved_note_user_friendly_labels()
    print("test_saved_note_user_friendly_labels OK")
    test_saved_note_display_policy_and_legacy_fallback()
    print("test_saved_note_display_policy_and_legacy_fallback OK")
    test_explanation_engine_data_driven()
    print("test_explanation_engine_data_driven OK")
    test_explanation_engine_manual_note()
    print("test_explanation_engine_manual_note OK")
    test_dashboard_growth_insight_renders_for_transfermarkt_only()
    print("test_dashboard_growth_insight_renders_for_transfermarkt_only OK")
    test_player_dossier_shows_data_coverage_panel_for_limited_player()
    print("test_player_dossier_shows_data_coverage_panel_for_limited_player OK")
    test_career_simulation_ceiling_sections_render()
    print("test_career_simulation_ceiling_sections_render OK")
    test_manual_prospect_creation_session_state()
    print("test_manual_prospect_creation_session_state OK")
    test_manual_prospect_full_flow_through_career_simulation_and_ai_report()
    print("test_manual_prospect_full_flow_through_career_simulation_and_ai_report OK")
    test_scouting_notes_view_has_no_creation_form()
    print("test_scouting_notes_view_has_no_creation_form OK")
    test_ceiling_result_survives_dashboard_and_ai_report()
    print("test_ceiling_result_survives_dashboard_and_ai_report OK")
    test_filter_mentor_candidates_by_age_primary_rule()
    print("test_filter_mentor_candidates_by_age_primary_rule OK")
    test_filter_mentor_candidates_by_age_fallback_when_too_few()
    print("test_filter_mentor_candidates_by_age_fallback_when_too_few OK")
    test_filter_mentor_candidates_by_age_excludes_self_and_missing_age()
    print("test_filter_mentor_candidates_by_age_excludes_self_and_missing_age OK")
    test_selecting_different_player_clears_growth_session_state()
    print("test_selecting_different_player_clears_growth_session_state OK")
    test_qualitative_evidence_importable_without_api_key()
    print("test_qualitative_evidence_importable_without_api_key OK")
    test_qualitative_evidence_fallback_without_api_key()
    print("test_qualitative_evidence_fallback_without_api_key OK")
    test_qualitative_evidence_fallback_with_no_text()
    print("test_qualitative_evidence_fallback_with_no_text OK")
    test_qualitative_evidence_safe_json_parsing()
    print("test_qualitative_evidence_safe_json_parsing OK")
    test_qualitative_evidence_bad_json_does_not_crash()
    print("test_qualitative_evidence_bad_json_does_not_crash OK")
    test_qualitative_signals_json_serializable()
    print("test_qualitative_signals_json_serializable OK")
    test_gemini_advisory_json_serializable()
    print("test_gemini_advisory_json_serializable OK")
    test_qualitative_evidence_payload_json_serializable()
    print("test_qualitative_evidence_payload_json_serializable OK")
    test_scouting_note_payload_includes_qualitative_fields()
    print("test_scouting_note_payload_includes_qualitative_fields OK")
    test_scouting_note_payload_without_qualitative_fields()
    print("test_scouting_note_payload_without_qualitative_fields OK")
    test_extract_structured_note_result_includes_qualitative()
    print("test_extract_structured_note_result_includes_qualitative OK")
    test_legacy_note_fallback_maintained_with_qualitative_fields()
    print("test_legacy_note_fallback_maintained_with_qualitative_fields OK")
    test_ai_report_view_has_qualitative_section()
    print("test_ai_report_view_has_qualitative_section OK")
    test_qualitative_evidence_service_has_no_ui_or_db_dependency()
    print("test_qualitative_evidence_service_has_no_ui_or_db_dependency OK")
    test_manual_prospect_flow_not_broken_by_v18()
    print("test_manual_prospect_flow_not_broken_by_v18 OK")
    test_qualitative_section_has_example_texts_expander()
    print("test_qualitative_section_has_example_texts_expander OK")
    test_qualitative_api_key_guidance_mentions_key_name()
    print("test_qualitative_api_key_guidance_mentions_key_name OK")
    test_augment_sections_no_longer_blocks_successful_signals()
    print("test_augment_sections_no_longer_blocks_successful_signals OK")
    test_save_exclude_fallback_reasons_includes_api_error()
    print("test_save_exclude_fallback_reasons_includes_api_error OK")
    test_api_error_payload_does_not_set_rule_based_with_gemini()
    print("test_api_error_payload_does_not_set_rule_based_with_gemini OK")
    test_gemini_sdk_unavailable_reason_returns_valid_value()
    print("test_gemini_sdk_unavailable_reason_returns_valid_value OK")
    test_gemini_client_has_sdk_install_guidance()
    print("test_gemini_client_has_sdk_install_guidance OK")
    test_render_qualitative_section_has_sdk_not_installed_guidance()
    print("test_render_qualitative_section_has_sdk_not_installed_guidance OK")
    test_gemini_client_supports_both_sdk_imports()
    print("test_gemini_client_supports_both_sdk_imports OK")
    test_qualitative_evidence_safe_parse_markdown_code_block()
    print("test_qualitative_evidence_safe_parse_markdown_code_block OK")
    test_build_data_coverage_transfermarkt_only_is_not_full()
    print("test_build_data_coverage_transfermarkt_only_is_not_full OK")
    test_build_data_coverage_full_analysis()
    print("test_build_data_coverage_full_analysis OK")
    test_build_data_coverage_no_fm_profile_not_eligible_for_mentor()
    print("test_build_data_coverage_no_fm_profile_not_eligible_for_mentor OK")
    test_build_data_coverage_no_style_vector_not_full()
    print("test_build_data_coverage_no_style_vector_not_full OK")
    test_resolve_player_age_from_profile()
    print("test_resolve_player_age_from_profile OK")
    test_resolve_player_age_from_dob_fallback()
    print("test_resolve_player_age_from_dob_fallback OK")
    test_resolve_player_age_consistent_across_sources()
    print("test_resolve_player_age_consistent_across_sources OK")
    test_resolve_player_age_none_when_no_data()
    print("test_resolve_player_age_none_when_no_data OK")
    test_prospect_search_filter_default_is_on()
    print("test_prospect_search_filter_default_is_on OK")
    test_prospect_search_filter_logic_uses_profile_id_notna()
    print("test_prospect_search_filter_logic_uses_profile_id_notna OK")
    test_prospect_search_shows_limited_notice_for_tm_only()
    print("test_prospect_search_shows_limited_notice_for_tm_only OK")
    test_v19_scouting_board_limited_policy_and_filters()
    print("test_v19_scouting_board_limited_policy_and_filters OK")
    test_v19_data_coverage_helpers_available()
    print("test_v19_data_coverage_helpers_available OK")
    test_legend_matching_gates_on_style_vector()
    print("test_legend_matching_gates_on_style_vector OK")
    test_manual_prospect_not_broken_by_v18_3()
    print("test_manual_prospect_not_broken_by_v18_3 OK")
    test_v18_3_gemini_not_broken()
    print("test_v18_3_gemini_not_broken OK")
    test_v18_3_legacy_saved_note_fallback_maintained()
    print("test_v18_3_legacy_saved_note_fallback_maintained OK")
    test_player_coverage_has_no_ui_or_db_dependency()
    print("test_player_coverage_has_no_ui_or_db_dependency OK")
