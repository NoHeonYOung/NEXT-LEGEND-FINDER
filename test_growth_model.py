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
from scouting_note_payload import (
    build_ai_report_note_payload,
    build_career_simulation_note_payload,
    build_manual_note_payload,
    compact_report_sections,
    extract_structured_note_result,
    json_safe,
)
from views.scouting_notes import ENTITY_TYPE_LABELS as SAVED_ENTITY_TYPE_LABELS
from views.scouting_notes import NOTE_TYPE_LABELS, SOURCE_LABELS, saved_note_label


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
    assert "Growth Insight" in headers
    assert "growth_insight" in at.session_state
    assert "growth_explanation" in at.session_state


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


def test_manual_note_growth_insight_session_state():
    at = AppTest.from_file("app.py")
    at.run(timeout=30)
    navigate_to(at, "내 스카우팅 노트")
    assert not at.exception
    assert "저장된 노트 조회" in "\n".join(s.value for s in at.subheader)

    name_inputs = [t for t in at.text_input if "이름" in (t.label or "")]
    assert name_inputs
    name_inputs[0].set_value("Custom Prospect A").run(timeout=30)

    submit_buttons = [b for b in at.button if "생성" in (b.label or "") or "제출" in (b.label or "")]
    assert submit_buttons
    submit_buttons[0].click().run(timeout=30)
    assert not at.exception

    assert "growth_insight" in at.session_state
    assert at.session_state["growth_insight"]["mode"] == "manual_prototype"
    assert "growth_explanation" in at.session_state
    assert "ceiling_model" in at.session_state["growth_insight"]
    assert "ceiling_model" in at.session_state["ceiling_growth_insight"]
    assert "ceiling_explanation" in at.session_state["ceiling_growth_explanation"]
    assert at.session_state["ceiling_growth_context"]["entity_type"] == "manual_note"
    assert at.session_state["ceiling_growth_context"]["source"] == "manual_note"

    metric_labels = "\n".join(m.label for m in at.metric)
    assert "Manual Final Growth Score" in metric_labels
    button_labels = "\n".join(button.label for button in at.button)
    assert "이 분석을 My Scouting Notes에 저장" in button_labels
    assert "이 노트를 scouting_notes에 저장" not in button_labels


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
    assert "이 AI 리포트를 My Scouting Notes에 저장" in "\n".join(button.label for button in at.button)


def test_selecting_different_player_clears_growth_session_state():
    at = AppTest.from_file("app.py")
    at.session_state["selected_player_id"] = 371998
    at.session_state["prospect_results"] = pd.DataFrame([{
        "player_id": 418560,
        "name": "Different Player",
        "age": 20,
        "position": "Midfield",
        "sub_position": "Central Midfield",
        "country_of_citizenship": "Test",
        "current_club_name": "Test Club",
        "market_value_in_eur": 1_000_000,
    }])
    at.session_state["last_search_filters"] = {"max_age": 21, "position": "All"}
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
    test_explanation_engine_data_driven()
    print("test_explanation_engine_data_driven OK")
    test_explanation_engine_manual_note()
    print("test_explanation_engine_manual_note OK")
    test_dashboard_growth_insight_renders_for_transfermarkt_only()
    print("test_dashboard_growth_insight_renders_for_transfermarkt_only OK")
    test_career_simulation_ceiling_sections_render()
    print("test_career_simulation_ceiling_sections_render OK")
    test_manual_note_growth_insight_session_state()
    print("test_manual_note_growth_insight_session_state OK")
    test_ceiling_result_survives_dashboard_and_ai_report()
    print("test_ceiling_result_survives_dashboard_and_ai_report OK")
    test_selecting_different_player_clears_growth_session_state()
    print("test_selecting_different_player_clears_growth_session_state OK")
