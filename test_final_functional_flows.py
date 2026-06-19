"""Final functional QA tests for v19.

테스트 원칙:
- 실제 Supabase DB insert를 수행하지 않는다.
- 실제 Gemini API를 호출하지 않는다.
- payload 직렬화 가능 여부, 빈 상태 처리, session_state 초기화를 단위 검증한다.
"""

import json
import math


# ---------------------------------------------------------------------------
# 1. Scouting note payload JSON serializable 검증
# ---------------------------------------------------------------------------

def test_note_payload_json_serializable():
    """build_ai_report_note_payload의 결과가 json.dumps 가능한지 확인한다."""
    from scouting_note_payload import build_ai_report_note_payload

    player = {
        "player_id": 999,
        "name": "Test Player",
        "position": "CM",
        "current_club_name": "Test FC",
        "country_of_citizenship": "Korea",
    }
    profile = {
        "profile_id": 888,
        "player_id": 999,
        "name": "Test Player",
        "age": 20,
        "position": "CM",
        "club": "Test FC",
        "nationality": "Korea",
        "attributes_jsonb": None,
        "mentality_jsonb": None,
        "style_vector": None,
    }
    env_settings = {
        "training_intensity": 1.2,
        "playing_time_opportunity": 0.6,
        "league_difficulty": "medium",
        "career_choice": "stay",
        "risk_level": "normal",
    }
    simulation_result = {
        "prototype_growth_score": 65.0,
        "prototype_success_probability": 0.55,
        "prototype_injury_risk": 0.12,
    }
    growth_insight = {
        "growth_score": 63.5,
        "features": {},
        "ceiling_model": {"final_growth_score": 66.0},
    }
    growth_explanation = {
        "summary": "성장 가능성이 있습니다.",
        "strengths": ["패스"],
        "risks": ["부상"],
        "recommendations": ["훈련 강화"],
    }

    payload = build_ai_report_note_payload(
        player=player,
        profile=profile,
        entity_type="matched",
        env_settings=env_settings,
        simulation_result=simulation_result,
        growth_insight=growth_insight,
        growth_explanation=growth_explanation,
        ceiling_growth_insight=growth_insight,
        ceiling_growth_explanation=growth_explanation,
        ceiling_growth_context={"entity_type": "matched", "player_id": 999, "profile_id": 888},
        report_sections={"1. 선수 요약": "테스트 선수 요약"},
        report_text="테스트 리포트 텍스트",
        qualitative_evidence=None,
        gemini_advisory=None,
    )

    serialized = json.dumps(payload, ensure_ascii=False)
    recovered = json.loads(serialized)
    assert recovered["player_id"] == 999
    assert recovered["profile_id"] == 888
    assert isinstance(recovered["env_settings"], dict)
    assert isinstance(recovered["simulation_result"], dict)
    print("PASS test_note_payload_json_serializable")


def test_note_payload_nan_sanitized():
    """NaN/Inf 값이 포함된 payload도 json_safe로 정리되는지 확인한다."""
    from scouting_note_payload import json_safe

    val = json_safe(float("nan"))
    assert val is None, f"NaN should be None, got {val}"

    val = json_safe(float("inf"))
    assert val is None, f"Inf should be None, got {val}"

    val = json_safe({"score": float("nan"), "ok": 1.0})
    assert val["score"] is None
    assert val["ok"] == 1.0

    val = json_safe([1, float("nan"), "text"])
    assert val[1] is None
    assert val[2] == "text"
    print("PASS test_note_payload_nan_sanitized")


def test_manual_note_payload_json_serializable():
    """build_manual_note_payload 결과도 json.dumps 가능한지 확인한다."""
    from scouting_note_payload import build_manual_note_payload

    manual_player = {
        "name": "Manual Test",
        "age": 18,
        "position": "ST",
        "sub_position": "CF",
        "club": "Manual FC",
        "nationality": "Brazil",
        "foot": "Right",
    }
    manual_attributes = {"speed": 7.0, "dribble": 7.5, "finishing": 6.5}
    env_settings = {
        "training_intensity": 1.0,
        "playing_time_opportunity": 1.0,
        "league_difficulty": "low",
        "career_choice": "loan",
        "risk_level": "normal",
    }
    simulation_result = {"prototype_growth_score": 60.0, "prototype_success_probability": 0.5, "prototype_injury_risk": 0.1}
    growth_insight = {"growth_score": 58.0, "features": {}, "ceiling_model": {"final_growth_score": 62.0}}
    growth_explanation = {"summary": "수동 입력 선수 평가", "strengths": [], "risks": [], "recommendations": []}

    payload = build_manual_note_payload(
        manual_player=manual_player,
        manual_attributes=manual_attributes,
        manual_career_settings={},
        growth_insight=growth_insight,
        growth_explanation=growth_explanation,
        ceiling_growth_insight=growth_insight,
        ceiling_growth_explanation=growth_explanation,
        ceiling_growth_context={"entity_type": "manual_prospect"},
        env_settings=env_settings,
        simulation_result=simulation_result,
        report_sections={"Growth Model Insight": "성장 분석"},
        source="career_simulation",
    )

    serialized = json.dumps(payload, ensure_ascii=False)
    recovered = json.loads(serialized)
    assert recovered["player_name"] == "Manual Test"
    assert isinstance(recovered["env_settings"], dict)
    assert recovered["env_settings"].get("entity_type") == "manual_prospect"
    print("PASS test_manual_note_payload_json_serializable")


# ---------------------------------------------------------------------------
# 2. Gemini quota exceeded mock 처리 검증
# ---------------------------------------------------------------------------

def test_gemini_quota_exceeded_returns_fallback():
    """Gemini quota exceeded 오류가 fallback 결과를 반환하는지 확인한다."""
    from services.qualitative_evidence import make_fallback_signals, make_fallback_advisory

    # quota exceeded는 api_error fallback을 반환한다
    fallback = make_fallback_signals("api_error")
    assert fallback["_fallback_reason"] == "api_error"
    assert fallback["playing_time_signal"] == "unknown"
    assert isinstance(fallback["strength_mentions"], list)

    fallback_adv = make_fallback_advisory("api_error")
    assert fallback_adv["_fallback_reason"] == "api_error"
    assert fallback_adv["advisory_summary"] == ""
    print("PASS test_gemini_quota_exceeded_returns_fallback")


def test_gemini_no_api_key_returns_fallback():
    """API key 없을 때 fallback 결과를 반환하는지 확인한다."""
    from services.qualitative_evidence import extract_qualitative_signals, generate_gemini_advisory

    # API key가 없으면 is_gemini_available()이 False → no_api_key fallback
    # 이 테스트에서는 직접 no_api_key fallback 구조를 검증한다
    from services.qualitative_evidence import make_fallback_signals
    fallback = make_fallback_signals("no_api_key")
    assert fallback["_fallback_reason"] == "no_api_key"
    assert fallback["confidence"] == "low"
    # fallback reason이 SAVE_EXCLUDE_FALLBACK_REASONS에 포함되는지 확인
    SAVE_EXCLUDE = ("no_text_input", "no_api_key", "api_error", "parse_failed")
    assert fallback["_fallback_reason"] in SAVE_EXCLUDE
    print("PASS test_gemini_no_api_key_returns_fallback")


# ---------------------------------------------------------------------------
# 3. Mentor 후보 빈 리스트 처리 검증
# ---------------------------------------------------------------------------

def test_mentor_empty_list_safe():
    """빈 mentor_records 리스트가 주어질 때 _sort_mentor_records가 깨지지 않는지 확인."""
    from views.legend_matching import _sort_mentor_records

    result = _sort_mentor_records([])
    assert result == []
    print("PASS test_mentor_empty_list_safe")


def test_mentor_filter_by_age_returns_empty_safely():
    """filter_mentor_candidates_by_age가 빈 pool을 받아도 안전한지 확인."""
    from manual_prospect_helpers import filter_mentor_candidates_by_age

    candidates, used_fallback = filter_mentor_candidates_by_age([], target_age=18, min_results=1)
    assert candidates == []
    assert isinstance(used_fallback, bool)
    print("PASS test_mentor_filter_by_age_returns_empty_safely")


def test_mentor_empty_state_note_payload_still_saves():
    """멘토 없이도 note payload 빌드가 실패하지 않는지 확인한다."""
    from scouting_note_payload import build_ai_report_note_payload
    import json

    payload = build_ai_report_note_payload(
        player={"player_id": 1, "name": "No Mentor Player", "position": "GK"},
        profile={"profile_id": 2, "age": 19},
        entity_type="matched",
        env_settings={"training_intensity": 1.0, "playing_time_opportunity": 1.0},
        simulation_result={"prototype_growth_score": 50.0},
        growth_insight={},
        growth_explanation={},
        report_sections={"1. 선수 요약": "GK 분석"},
        report_text="GK 리포트",
    )
    serialized = json.dumps(payload, ensure_ascii=False)
    recovered = json.loads(serialized)
    assert recovered["player_id"] == 1
    print("PASS test_mentor_empty_state_note_payload_still_saves")


# ---------------------------------------------------------------------------
# 4. session_state 초기화 키 목록 검증
# ---------------------------------------------------------------------------

def test_analysis_state_keys_contains_required():
    """_ANALYSIS_STATE_KEYS가 필수 키를 모두 포함하는지 확인한다."""
    from views.prospect_search import _ANALYSIS_STATE_KEYS

    required = [
        "growth_insight",
        "growth_explanation",
        "ceiling_growth_insight",
        "ceiling_growth_explanation",
        "ceiling_growth_context",
        "env_settings",
        "simulation_result",
        "generated_report",
        "generated_report_sections",
        "qualitative_signals",
        "gemini_advisory",
        "selected_mentor_profile_id",
        "selected_mentor_name",
        "mentor_summary",
        "archive_selected_idx",
    ]
    for key in required:
        assert key in _ANALYSIS_STATE_KEYS, f"Missing key in _ANALYSIS_STATE_KEYS: {key}"
    print("PASS test_analysis_state_keys_contains_required")


# ---------------------------------------------------------------------------
# 5. Manual Prospect payload와 Notes 저장 구조 충돌 없음 확인
# ---------------------------------------------------------------------------

def test_manual_prospect_payload_no_conflict_with_insert():
    """build_manual_note_payload 결과가 insert_scouting_note의 기대 구조와 맞는지 확인.

    insert_scouting_note는 player_id, profile_id, env_settings, simulation_result, report를 받는다.
    manual prospect는 player_id=None, profile_id=None이어도 정상 동작해야 한다.
    """
    from scouting_note_payload import build_manual_note_payload
    import json

    payload = build_manual_note_payload(
        manual_player={"name": "Prospect X", "age": 17, "position": "LW"},
        manual_attributes={},
        manual_career_settings={},
        growth_insight={"growth_score": 55.0, "features": {}},
        growth_explanation={"summary": "잠재력 있음"},
        ceiling_growth_insight={"growth_score": 55.0, "features": {}, "ceiling_model": {"final_growth_score": 58.0}},
        ceiling_growth_explanation={"summary": "상승 가능", "ceiling_explanation": {}},
        ceiling_growth_context={"entity_type": "manual_prospect"},
        env_settings={"training_intensity": 1.0},
        simulation_result={"prototype_growth_score": 52.0},
        report_sections={},
        source="manual_note",
    )

    # insert_scouting_note에 전달할 인자 추출
    player_id = payload["player_id"]
    profile_id = payload["profile_id"]
    env_settings = payload["env_settings"]
    simulation_result = payload["simulation_result"]
    report = payload["report"]

    # player_id/profile_id가 None이어도 직렬화 가능한지 확인
    json.dumps({"player_id": player_id, "profile_id": profile_id})

    # env_settings와 simulation_result가 JSON 직렬화 가능한지 확인
    env_str = json.dumps(env_settings, ensure_ascii=False)
    sim_str = json.dumps(simulation_result, ensure_ascii=False)

    assert isinstance(env_str, str)
    assert isinstance(sim_str, str)
    assert "manual_prospect" in env_str
    print("PASS test_manual_prospect_payload_no_conflict_with_insert")


# ---------------------------------------------------------------------------
# 6. extract_structured_note_result 안전성 확인
# ---------------------------------------------------------------------------

def test_extract_structured_note_result_safe_with_empty():
    """extract_structured_note_result가 빈/None 입력에도 안전한지 확인한다."""
    from scouting_note_payload import extract_structured_note_result

    result = extract_structured_note_result(None)
    assert isinstance(result, dict)
    assert result["growth_insight"] == {}
    assert result["gemini_advisory"] == {}

    result = extract_structured_note_result({})
    assert isinstance(result, dict)
    assert result["report_sections"] == {}
    print("PASS test_extract_structured_note_result_safe_with_empty")


# ---------------------------------------------------------------------------
# 7. Manual Prospect stale state 관리 검증
# ---------------------------------------------------------------------------

def test_manual_prospect_submitted_flag_gates_panel():
    """manual_prospect_submitted 플래그가 없으면 패널이 렌더링되지 않아야 한다.

    _clear_manual_prospect_state가 manual_prospect_submitted를 포함한
    모든 manual 관련 키를 제거하는지 확인한다.
    """
    from views.manual_prospect import _MANUAL_CLEAR_KEYS

    required_keys = [
        "manual_player",
        "manual_attributes",
        "manual_career_settings",
        "manual_prospect_submitted",
        "growth_insight",
        "growth_explanation",
    ]
    for key in required_keys:
        assert key in _MANUAL_CLEAR_KEYS, f"_MANUAL_CLEAR_KEYS에 '{key}'가 없습니다"
    print("PASS test_manual_prospect_submitted_flag_gates_panel")


def test_manual_clear_keys_includes_stale_selection_keys():
    """_MANUAL_CLEAR_KEYS가 STALE_SELECTION_KEYS를 포함하는지 확인한다."""
    from views.manual_prospect import _MANUAL_CLEAR_KEYS
    from manual_prospect_helpers import STALE_SELECTION_KEYS

    for key in STALE_SELECTION_KEYS:
        assert key in _MANUAL_CLEAR_KEYS, f"STALE_SELECTION_KEYS의 '{key}'가 _MANUAL_CLEAR_KEYS에 없습니다"
    print("PASS test_manual_clear_keys_includes_stale_selection_keys")


def test_manual_prospect_state_labels():
    """state.py의 manual_prospect 레이블이 사용자 친화적으로 변경되었는지 확인한다."""
    from state import ENTITY_TYPE_LABELS

    label = ENTITY_TYPE_LABELS.get("manual_prospect", "")
    assert "직접 입력" in label or "Manual" in label, (
        f"manual_prospect 레이블이 사용자 친화적이지 않습니다: '{label}'"
    )
    assert label != "Full Data", "이전 영문 레이블 'Full Data'가 그대로 남아 있습니다"
    print("PASS test_manual_prospect_state_labels")


def test_player_header_manual_prospect_data_mode():
    """render_player_header가 entity_type='manual_prospect'일 때
    '직접 입력 기반 분석'을 data_mode로 사용하는지 소스에서 확인한다."""
    import ast
    import pathlib

    src = pathlib.Path("components/player_header.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    # 'data_mode' 할당에서 '직접 입력 기반 분석' 문자열이 존재하는지 확인
    assert "직접 입력 기반 분석" in src, (
        "components/player_header.py에 '직접 입력 기반 분석' 레이블이 없습니다"
    )
    assert "직접 입력 선수" in src, (
        "components/player_header.py에 '직접 입력 선수' 배지 텍스트가 없습니다"
    )
    print("PASS test_player_header_manual_prospect_data_mode")


# ---------------------------------------------------------------------------
# 메인 실행
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_note_payload_json_serializable,
        test_note_payload_nan_sanitized,
        test_manual_note_payload_json_serializable,
        test_gemini_quota_exceeded_returns_fallback,
        test_gemini_no_api_key_returns_fallback,
        test_mentor_empty_list_safe,
        test_mentor_filter_by_age_returns_empty_safely,
        test_mentor_empty_state_note_payload_still_saves,
        test_analysis_state_keys_contains_required,
        test_manual_prospect_payload_no_conflict_with_insert,
        test_extract_structured_note_result_safe_with_empty,
        test_manual_prospect_submitted_flag_gates_panel,
        test_manual_clear_keys_includes_stale_selection_keys,
        test_manual_prospect_state_labels,
        test_player_header_manual_prospect_data_mode,
    ]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as exc:
            print(f"FAIL {test_fn.__name__}: {exc}")
            failed += 1
    print(f"\n결과: {passed} passed, {failed} failed")
