# ACTIVE_FUNCTION_MAP.md
# app.py 함수 매핑 (활성 vs dead code)

---

# v16.1: Persistence QA and saved-note UI polish

- `scouting_note_payload.py::json_safe`: datetime/tuple/numpy·pandas scalar/NaN/NA 변환을 보장한다.
- `scouting_note_payload.py::compact_report_sections`: 최대 50개 섹션과 섹션당 5,000자 제한으로
  JSONB payload 크기를 방어한다.
- `views/scouting_notes.py::saved_note_label`: 내부 저장 type/source/entity 값을 사용자용 배지로 변환한다.
- 저장 노트 카드: 구조화 Growth 설명을 summary/strengths/weaknesses fallback으로 사용한다.
- 저장 버튼 UX: Career/AI/Manual 저장 성공 후 My Scouting Notes 재확인 경로를 안내한다.
- 신규/legacy 복원은 `extract_structured_note_result` 단일 흐름을 유지한다.

실제 DB INSERT는 자동 테스트에서 수행하지 않으며, AppTest는 조회 및 버튼/렌더링 흐름만 검증한다.

---

# v16: Scouting Notes structured persistence

## 신규 helper: `scouting_note_payload.py`

- `json_safe`: 날짜/numpy 계열 값을 JSONB에 안전한 값으로 변환한다.
- `build_player_snapshot`, `build_profile_snapshot`: 저장 시점 선수/프로필 메타데이터를 만든다.
- `build_ai_report_note_payload`: `note_type/source="ai_report"` 구조화 payload 생성.
- `build_manual_note_payload`: `note_type="manual_custom_prospect"`, `source="manual_note"` payload 생성.
- `build_career_simulation_note_payload`: `note_type/source="career_simulation"` payload 생성.
- `extract_structured_note_result`: 신규 구조를 복원하고 legacy note는 기존 simulation dict로 fallback한다.

## 수정된 view 흐름

- `views/ai_report.py::render_ai_report_view`: 저장 버튼에서 report/Growth/Ceiling/context를 JSONB payload로 묶는다.
- `views/career_simulation.py::render_career_simulation_view`: 실제 DB 선수 분석 결과 저장 버튼을 제공한다.
- `views/scouting_notes.py::render_scouting_notes_view`: Manual Note 구조화 저장, source 배지,
  Growth/Final Growth Score 및 코칭 리포트 복원을 수행한다.

`services/db.py::insert_scouting_note`와 `get_scouting_notes`의 역할과 시그니처, DB 스키마는 변경하지 않았다.

---

# v14: scoring calibration + coaching-style explanation 개선

## 핵심 함수

- `growth_model.py::compute_ceiling_scenario_adjustment`: 기존 Ceiling 공식을 유지하면서 선택값 조합별
  피로, 부상, 번아웃, 벤치 정체, 적응 실패 위험을 β에 추가 반영한다.
- `explanation_engine.py::build_ceiling_explanation`: 기존 설명 key를 유지하고 `coaching_summary`,
  `training_directions`, `expected_benefits`, `neglect_risks`, `risk_warnings`, `career_strategy`를 추가한다.
- `views/career_simulation.py`, `views/scouting_notes.py`: 코칭 섹션을 기본 표시하고 공식/변수는
  `상세 계산 근거` expander에서만 표시한다.
- `views/ai_report.py::build_report_sections`: `Ceiling Scenario Insight`를 코칭 리포트형으로 구성한다.

session_state key 분리와 context 판정은 v13 구조를 그대로 유지한다.

---

# v13 업데이트 (Ceiling session_state key 분리 및 보존)

v12 계산식과 화면 출력은 유지하면서, Dashboard 재방문으로 Ceiling 결과가 사라지는 session_state
흐름을 수정했다. app.py는 변경하지 않았으며 각 view는 app.py를 import하지 않는다.

## v13.1 session_state 구조

| key | 소유/용도 |
|---|---|
| `growth_insight` | 현재 화면에서 계산한 기본 또는 현재 Growth Insight |
| `growth_explanation` | 현재 화면의 기본 또는 현재 Growth Explanation |
| `ceiling_growth_insight` | `ceiling_model`이 포함된 보존용 최종 Growth Insight |
| `ceiling_growth_explanation` | `ceiling_explanation`이 포함된 보존용 Explanation |
| `ceiling_growth_context` | Ceiling 결과의 `entity_type`/`player_id`/`profile_id`/`source` 식별 정보 |

Dashboard는 기본 key만 갱신하며 Ceiling 전용 key를 건드리지 않는다. AI Report는 context가 현재
선택 상태와 일치할 때 Ceiling 전용 결과를 우선 사용한다.

## v13.2 수정 파일 위치

- `views/career_simulation.py`: Ceiling 결과를 기본 key와 Ceiling 전용 key에 모두 저장하고,
  `source="career_simulation"` context를 저장한다.
- `views/scouting_notes.py`: Manual Note Ceiling 결과와 `source="manual_note"` context를 저장한다.
- `views/ai_report.py`: `is_ceiling_context_current`, `get_current_growth_result`로 context를 판정하고
  Ceiling 결과 우선 또는 기본 Growth 결과 fallback을 수행한다.
- `views/prospect_search.py`: 다른 선수 선택 시 growth/ceiling/report 관련 key를 clear하며,
  기존 `selected_profile_id`/`selected_entity_type` stale state 초기화를 유지한다.
- `test_growth_model.py`: Ceiling key 저장, Dashboard 재방문 보존, AI Report 반영,
  다른 선수 선택 시 clear 흐름을 검증한다.

## v13.3 테스트 결과

- `python -m compileall .` - 통과
- `test_state_refactor.py` 3/3, `test_analysis_helpers_split.py` 4/4,
  `test_prospect_search_split.py` 2/2, `test_growth_model.py` 19/19 - 전부 통과
- Streamlit health check - HTTP 200, 응답 `ok`

---

# v12 업데이트 (Ceiling Model 시나리오 보정 레이어 추가, 최우선으로 읽을 것)

v11의 Real Data Growth Score / manual_growth_score 계산 로직은 그대로 두고, 그 위에 초기 기획의
Ceiling Model 공식(`Potential_final = Potential_base + Σ(Δleague × (α × γ × training_multiplier - β))`)을
보정 레이어로 추가했다. app.py는 이번 세션에서도 수정하지 않았다.

## v12.1 growth_model.py 추가분 (app.py를 import하지 않음)
- 신규 상수: `LEAGUE_DIFFICULTY_GAMMA`, `PLAYING_OPPORTUNITY_ALPHA`,
  `TRAINING_INTENSITY_MULTIPLIER`, `RISK_TENDENCY_BETA`, `DELTA_LEAGUE_VALUES`,
  `CEILING_ADJUSTMENT_MIN`/`CEILING_ADJUSTMENT_MAX` (-15/+15).
- 신규 함수:
  - `map_league_difficulty(value)` / `map_playing_opportunity(value)` /
    `map_training_intensity(value)` / `map_risk_tendency(value)` — 기존 `classify_*`를
    재사용해 `(level_label, numeric_value)` 튜플 반환 (γ/α/training_multiplier/β).
  - `compute_delta_league(career_choice, league_level, playing_opportunity)` — Δleague와
    시나리오 라벨, β 추가 증가 플래그(`extra_risk`) 반환.
  - `compute_ceiling_scenario_adjustment(env_settings)` — α/γ/β/training_multiplier/Δleague로
    `raw_adjustment`, `scenario_adjustment`(-15~+15 clamp), `scenario_label`, `notes` 계산.
  - `apply_ceiling_adjustment(growth_insight, env_settings)` — `growth_insight["growth_score"]`를
    `potential_base`로 사용해 `growth_insight["ceiling_model"]` key를 추가(append-only,
    기존 key 변경 없음).

## v12.2 explanation_engine.py 추가분
- 신규 함수: `explain_ceiling_variables(ceiling_model)`,
  `build_scenario_strengths/risks/recommendations(ceiling_model)`,
  `build_ceiling_explanation(growth_insight)`.
- `build_growth_explanation`이 결과 dict에 `ceiling_explanation` key 추가
  (`growth_insight["ceiling_model"]`이 없으면 `None`).
- `build_gemini_ready_payload`에 `ceiling_model`/`ceiling_explanation` 포함하도록 확장.

## v12.3 views/career_simulation.py
- import 추가: `growth_model.apply_ceiling_adjustment`.
- 기존 "Real Data Growth Baseline (실제 DB 기반 비교)" 단일 섹션을 3단 구조로 재구성:
  - "1. Real Data Growth Baseline (실제 DB 기반)" — 기존 프로토타입 vs 실제 점수 비교 +
    feature별 점수 + summary (v11과 동일 내용).
  - "2. Ceiling Scenario Adjustment (초기 기획 수식 반영)" — α/γ/β/training_multiplier/Δleague
    값, scenario_adjustment(+/- 표시), variable_explanations, 시나리오 강점/리스크/추천 전략.
  - "3. Final Growth Score" — `ceiling_model["final_growth_score"]` metric+progress bar,
    프로토타입 점수와의 비교 문장.
- `build_growth_insight(...)` 호출 직후 `apply_ceiling_adjustment(growth_insight, env_settings)`
  호출 → `growth_insight`/`growth_explanation`을 session_state에 저장(덮어쓰기, 기존과 동일).

## v12.4 views/scouting_notes.py
- import 추가: `growth_model.apply_ceiling_adjustment`.
- manual_note 제출 시 `build_manual_growth_insight(...)` 다음에
  `apply_ceiling_adjustment(growth_insight, env_settings["career_settings"])` 호출.
- 미리보기 "Growth Insight (직접 입력 기반 prototype)" 섹션 내부에 Ceiling Scenario Adjustment
  블록 추가: Manual Prototype Baseline(기존 `growth_score`) → α/γ/β/training_multiplier/Δleague
  → Manual Final Growth Score(`ceiling_model["final_growth_score"]`). "직접 입력 기반
  prototype + 시나리오 보정"임을 caption으로 명시.

## v12.5 views/ai_report.py
- `get_report_sections`에서 `growth_explanation.get("ceiling_explanation")`이 있으면
  "Ceiling Scenario Insight" 섹션을 결과 dict에 추가 (Real Data Growth Baseline/Scenario
  Adjustment/Final Growth Score, α/γ/β/training_multiplier/Δleague, 시나리오 강점/리스크/추천
  전략). Gemini API 호출 없음, 기존 섹션 구조 변경 없음.

## v12.6 신규/확장 테스트 (test_growth_model.py)
- `test_ceiling_model_mapping_functions` — map_league_difficulty/playing_opportunity/
  training_intensity/risk_tendency 매핑값 확인.
- `test_compute_ceiling_scenario_adjustment_in_range` — scenario_adjustment가 -15~+15 범위.
- `test_apply_ceiling_adjustment_in_range` — `ceiling_model["final_growth_score"]`가 0~100,
  `ceiling_model` key가 추가됨.
- `test_manual_note_ceiling_model_and_explanation` — manual_note에도 `ceiling_model` 추가,
  `build_growth_explanation`이 `ceiling_explanation`을 생성, `gemini_ready_payload`에
  `ceiling_model`/`ceiling_explanation` 포함.
- `test_career_simulation_ceiling_sections_render` (AppTest) — Career Simulation 화면에서
  "Real Data Growth Baseline"/"Ceiling Scenario Adjustment"/"Final Growth Score" 헤더 확인.
- `test_manual_note_growth_insight_session_state` 확장 — `ceiling_model` 존재 및 "Manual Final
  Growth Score" metric 라벨 확인.

## v12.7 테스트 결과
- `python -m compileall .` — 에러 없음
- `test_state_refactor.py` 3/3, `test_analysis_helpers_split.py` 4/4,
  `test_prospect_search_split.py` 2/2, `test_growth_model.py` 16/16 — 전부 통과
- `streamlit run app.py --server.headless true` — HTTP 200

---

# v11 업데이트 (실 DB 기반 Growth Model + Explanation Engine 추가, 최우선으로 읽을 것)

v10까지의 구조(app.py 389줄, views/*.py 분리 완료)는 그대로 유지했다. app.py는 수정하지 않았고,
신규 모듈 2개(growth_model.py, explanation_engine.py)와 views/dashboard.py·career_simulation.py·
scouting_notes.py·ai_report.py에 "Growth Insight" 관련 섹션을 추가했다. services/db.py는 기존
`get_valuations`/`get_appearances`를 그대로 재사용했고 신규 함수는 추가하지 않았다.

## v11.1 신규 모듈 (app.py를 import하지 않음, 순수 함수 + DataFrame/dict 인자만 사용)
- `growth_model.py` — `GROWTH_WEIGHTS`, `FEATURE_LABELS`, `LEVEL_DESCRIPTIONS`,
  `compute_market_momentum/playing_opportunity/contribution_score/age_potential/
  attribute_strength/mentality_strength/risk_penalty/growth_score`,
  `build_growth_insight(player, profile, appearances, valuations, entity_type)`,
  `build_manual_growth_insight(manual_player, manual_attributes, career_settings)`,
  `classify_training_intensity/playing_opportunity/league_level/risk_tendency`.
- `explanation_engine.py` — `build_growth_explanation(growth_insight, player_context)`이
  `growth_insight["mode"]`(`data_driven` / `manual_prototype`)에 따라 `_build_data_driven_explanation`
  또는 `_build_manual_explanation`을 호출. 반환 dict: `summary, score_reason, strengths, risks,
  recommendations, data_limitations, gemini_ready_payload`. `build_gemini_ready_payload`는 추후
  Gemini API에 그대로 전달 가능한 구조화 payload를 생성하지만 이번 세션에서는 호출하지 않음.

## v11.2 views/dashboard.py
- import 추가: `from explanation_engine import build_growth_explanation`,
  `from growth_model import FEATURE_LABELS, build_growth_insight`.
- `valuations`/`appearances` 조회를 entity_type 분기 앞으로 이동(1회만 조회, `get_appearances(...,
  limit=20)`로 확장하여 기존 차트(상위 10개)와 Growth Insight가 같은 데이터를 공유).
- `entity_type != "manual_note"`인 경우 "Growth Insight (실제 DB 기반 성장 분석)" 섹션 추가:
  Growth Score(metric+progress), 6개 feature 점수(불가 항목은 회색 텍스트), risk_penalty 경고,
  summary/score_reason/strengths/risks/recommendations/data_limitations, 개발자용 JSON expander.
  결과는 `st.session_state["growth_insight"]`/`["growth_explanation"]`에 저장.

## v11.3 views/career_simulation.py
- import 추가: `explanation_engine.build_growth_explanation`, `growth_model.FEATURE_LABELS`,
  `growth_model.build_growth_insight`, `services.db.get_appearances/get_valuations`.
- 기존 `env_settings`/`simulation_result`/`breakdown` 로직은 변경 없음. 마지막 expander 앞에
  "Real Data Growth Baseline (실제 DB 기반 비교)" 섹션 추가: `has_player_id and entity_type !=
  "manual_note"`일 때만 표시. 프로토타입 vs 실제 Growth Score 비교, 차이 해석 문장, feature별 점수,
  summary/recommendations/data_limitations. 결과를 `st.session_state["growth_insight"]`/
  `["growth_explanation"]`에 저장(덮어쓰기). manual_note/매칭 안 된 경우는 안내 문구만 표시.

## v11.4 views/scouting_notes.py
- import 추가: `explanation_engine.build_growth_explanation`, `growth_model.LEVEL_DESCRIPTIONS`,
  `growth_model.build_manual_growth_insight`, `growth_model.classify_*`.
- 직접 입력 폼의 훈련 강도/출전 기회/리그·팀 수준/리스크 성향 슬라이더 아래에 `st.caption`으로
  레벨 분류(낮음/보통/높음/매우 높음, 안정형/균형형/도전형) + `LEVEL_DESCRIPTIONS` 설명 표시.
- 제출 시 `build_manual_growth_insight` + `build_growth_explanation` 호출 → `custom_note_preview`에
  `growth_insight`/`growth_explanation` 저장, `st.session_state["growth_insight"]`/
  `["growth_explanation"]`에도 저장.
- 미리보기 섹션에 "Growth Insight (직접 입력 기반 prototype)" 섹션 추가(`st.warning`으로 실제 DB
  기반 모델과 구분 명시): Growth Score, score_reason, strengths/risks/recommendations.

## v11.5 views/ai_report.py
- `get_report_sections(player, profile, env_settings, simulation_result, growth_insight=None,
  growth_explanation=None)`로 시그니처 확장(뒤 2개 인자는 기본값 None, 하위 호환).
- `growth_insight`/`growth_explanation`이 모두 전달되면 "Growth Model Insight" 섹션을 결과 dict에
  추가(점수/모드/summary/score_reason/strengths/risks/recommendations). Gemini API 호출 없음.
- `render_ai_report_view`에서 `st.session_state.get("growth_insight"/"growth_explanation")`을 조회해
  전달. 둘 다 없으면 기존과 동일하게 동작.

## v11.6 신규 테스트
- `test_growth_model.py` — growth_model 단위 테스트(market_momentum 2개 이상/미만, playing_opportunity
  fallback, attribute/mentality unavailable, risk 재정규화, 0~100 범위, manual_growth_score,
  classify_* 함수), explanation_engine 단위 테스트(data_driven/manual_prototype), AppTest 기반
  Dashboard Growth Insight 렌더링 확인 및 Scouting Notes manual_note 제출 시 session_state 확인.

## v11.7 문서
- `REAL_MODEL_PLAN.md` 신규 작성 (Growth Model/Explanation Engine 설계 문서, 13개 섹션).

---

# v10 업데이트 (Experimental Data Lab 추가 + Career Simulation 확장, 최우선으로 읽을 것)

v9까지의 app.py(375줄) 구조에 **신규 메뉴 1개**와 **wrapper 함수 1개**만 추가했다.
기존 active 함수/줄 번호 구조는 거의 그대로이며, 아래 변경분만 추가로 반영한다.

## v10.1 app.py 변경 사항
- import 추가: `from views.experimental_data_lab import render_experimental_data_lab_view`
- 신규 wrapper: `render_data_lab()` → `render_experimental_data_lab_view()` (2줄,
  `render_db_status()` 바로 앞에 위치)
- `main()`의 `menu` dict: `"내 스카우팅 노트"`와 `"DB 상태 확인"` 사이에
  `"실험실 (Data Lab)": render_data_lab` 추가
- `render_home()`의 `feature_cards`: `"DB 상태 확인"` 카드 앞에 `"실험실 (Data Lab)"`
  카드 추가 (nav_target="실험실 (Data Lab)")
- `render_career_simulation()`: `entity_type = selected_entity_type()`을 계산해
  `render_career_simulation_view(player, profile, entity_type)`에 전달하도록 1줄 변경
  (선택 로직 자체는 변경 없음)

## v10.2 ui_components.py 변경 사항
- `NAV_TARGETS`: `"내 스카우팅 노트"`와 `"DB 상태 확인"` 사이에 `"실험실 (Data Lab)"` 추가
- `NAV_CHIP_LABELS`: `"실험실 (Data Lab)": "Lab"` 추가
- `render_nav_chips`/`go_to`는 `NAV_TARGETS`를 그대로 순회하므로 추가 수정 없음

## v10.3 신규 모듈 (app.py를 import하지 않음)
- `grid_pipeline.py` — 10x10 Grid Vector 순수 함수 모음 (DB/streamlit 비의존)
- `gemini_client.py` — Gemini API optional wrapper (streamlit.secrets만 의존)
- `evidence_extractor.py` — mentality evidence 추출 (`gemini_client`에 의존)
- `views/experimental_data_lab.py` — 위 3개 모듈을 사용하는 화면.
  `render_experimental_data_lab_view()` 단일 entrypoint, app.py 미참조

## v10.4 analysis_helpers.py / views/career_simulation.py 변경 사항
- `analysis_helpers.py`: `build_simulation_breakdown(env_settings, simulation_result,
  entity_type=None, mentor_name=None)` 신규 함수 + `ENTITY_TYPE_SIMULATION_NOTES` 신규
  상수 추가. 기존 `build_simulation_result` 등 다른 함수는 변경 없음.
- `views/career_simulation.py`: `render_career_simulation_view(player, profile,
  entity_type=None)`로 시그니처 확장(3번째 인자 기본값 있음, 하위 호환). 함수 본문 끝에
  성장 점수 산정 근거 표 + 기회/리스크 요약 + 멘토 유사도 참고 + 데이터 타입별 해석
  제한 안내 섹션 추가.

---

# v8 업데이트 (services.db 중복 DB helper 정리 + views/prospect_search.py 분리 세션, 최우선으로 읽을 것)

이번 세션에서 v7.4가 큰 작업으로 플래그한 9번 줄 `from services.db import (...)` (16개 이름)을
AST diff로 검증한 결과, app.py 자체 정의(49~494줄)와 100% 동일한 dead import였음을 확인하고
(DB_HELPER_DIFF.md), app.py 내부 16개 정의 + 연쇄 dead 4개(load_db_url/get_connection/
execute_one/TABLES)를 삭제해 import를 active화했다. 이어서 v7.4가 분리 계획을 기록해둔
`render_prospect_search`(765~887, 123줄)를 `views/prospect_search.py`로 분리했다.
app.py는 **941줄 → 375줄**(-566)로 축소되었고, 중복 정의는 여전히 **0개**다.

## v8.1 Step A — services.db 중복 DB 헬퍼 정리
- 삭제한 app.py 내부 정의(16개, services.db와 100% 동일 확인): `query_df`, `query_one`,
  `show_db_error`, `table_count`, `preview_table`, `search_players`, `search_players_with_modes`,
  `get_distinct_positions`, `get_player`, `get_profile_by_player_id`, `get_profile_by_name`,
  `get_player_profile`, `insert_scouting_note`, `get_scouting_notes`, `get_prospect_diagnostics`, `money`
- 연쇄적으로 dead가 되어 함께 삭제: `load_db_url`, `get_connection`, `execute_one`, `TABLES` 상수,
  그리고 이제 미사용인 top-level import `json`/`tomllib`/`pathlib.Path`/`pandas`/`psycopg`,
  `BASE_DIR`/`SECRETS_PATH` 상수
- 그대로 유지(services.db에 동일 함수 없음, 절대 삭제 금지): `get_profile_by_name_nationality_position`
  (32~55줄, `resolve_selected_player_context`의 fallback profile matching에서 호출)
- 최종 import (1~14줄): `from services.db import query_one, get_player, get_profile_by_player_id,
  get_player_profile` (16개 → 4개)
- 상세 비교표는 DB_HELPER_DIFF.md 참고

## v8.2 Step C — views/prospect_search.py 분리
- `render_prospect_search_view(show_selected_player_banner)` (129줄, 완전히 새로 작성 —
  기존 views/prospect_search.py는 미사용 구버전 구현이었음)
- import: `services.db`(get_distinct_positions, money, search_players, show_db_error),
  `ui_components`(render_page_actions)
- app.py의 `render_prospect_search()`는 2줄 wrapper:
  `return render_prospect_search_view(show_selected_player_banner)`
  (`show_selected_player_banner`를 인자로 전달하여 app.py import 없이 선택 로직 재사용,
  career_simulation/ai_report와 동일한 thin-wrapper 패턴)
- session_state 키 이름, 선택 버튼 key(`select_prospect_{player_id}`), previous_player_id 기반
  키 pop 로직 모두 1바이트도 변경 없이 그대로 포팅

## v8.3 현재(375줄) active 함수/상수 줄 번호

| 항목 | 줄 |
|---|---|
| 상단 import 블록 (services.db에서 4개만) | 1~14 |
| `PAGES` 상수 (완전 dead, 의도적으로 유지) | 17~26 |
| `st.set_page_config` | 29 |
| `get_profile_by_name_nationality_position` (app.py 전용) | 32~55 |
| `resolve_selected_player_context` (**DO NOT CHANGE**) | 58~127 |
| 선택 로직 (`selected_player_id` ~ `show_selected_player_banner`, **DO NOT CHANGE**) | 130~205 |
| `get_selected_player_status`/`render_app_header` | 208~255 |
| `render_dashboard` (6줄 wrapper → views/dashboard.py) | 258~263 |
| `render_home` | 266~312 |
| `render_db_status` (2줄 wrapper → views/db_status.py) | 315~316 |
| `render_prospect_search` (2줄 wrapper → views/prospect_search.py, **신규**) | 319~320 |
| `main` | 323~342 |
| `render_career_simulation` (wrapper → views/career_simulation.py) | 345~350 |
| `render_legend_matching` (wrapper → views/legend_matching.py) | 353~359 |
| `render_ai_report` (wrapper → views/ai_report.py) | 362~367 |
| `render_my_notes` (2줄 wrapper → views/scouting_notes.py) | 370~371 |
| `if __name__ == "__main__":` | 374~375 |

**중복 정의는 여전히 0개.**

## v8.4 다음 세션 후보 / 주의사항
- `PAGES` 상수(17~26줄)는 여전히 완전한 dead code (자기 정의 외 0회 참조)이지만, 이번 세션 범위
  밖이라 의도적으로 유지함. 다음 세션에서 제거 검토 가능.
- app.py가 375줄까지 축소되어 추가 view 분리는 더 이상 필수가 아님.
- DB_HELPER_DIFF.md는 이번 세션의 비교 작업 기록용 문서로 보존됨 (삭제하지 말 것).

---

# v7 업데이트 (views/scouting_notes.py 분리 + import 정리 세션, 최우선으로 읽을 것)

이번 세션에서 v6.5 후보였던 `similarity_reason`(미사용 dead, 731)과 `render_my_notes`(1040~1346, 308줄) +
보조 함수 8개(`note_summary_text`~`build_manual_analysis`, 755~1039, 285줄)를 `views/scouting_notes.py`로
분리했다. app.py는 **1573줄 → 941줄**(-632)로 축소되었고, 중복 정의는 여전히 **0개**다.
이동으로 인해 완전히 미사용이 된 `from analysis_helpers import (...)` 블록(14개 이름) 전체와,
이미 dead였던 `ui.components`/`ui.navigation` import 2줄, 그리고 미사용 `render_prospect_search_view` import도
함께 제거했다.

## v7.1 views/scouting_notes.py
- `render_scouting_notes_view()` (구 `render_my_notes` 본문, `st.title("My Scouting Notes")` 포함)
- 보조 함수: `note_summary_text`, `safe_text`, `get_career_settings`, `normalize_env_settings`,
  `setting_summary`, `manual_similarity_candidates`, `note_display_title`, `build_manual_analysis` (모두 그대로 이동)
- import: `analysis_helpers`(attr_label, build_simulation_result, format_percent, numeric_attr,
  parse_json_field, position_training_hint, readable_setting, safe_float),
  `services.db`(get_scouting_notes, insert_scouting_note, query_df), `ui_components`(render_page_actions)
- app.py의 `render_my_notes()`는 2줄 wrapper: `return render_scouting_notes_view()`

## v7.2 app.py에서 추가로 제거한 dead/미사용 항목
- `similarity_reason(base_profile, candidate_profile)`(731~752): v6.5에서 미사용으로 기록된 단일 정의,
  호출부가 전혀 없어 삭제.
- `from analysis_helpers import (ATTRIBUTE_LABELS, ATTRIBUTE_GROUPS, parse_json_field, attr_label,
  attr_description, numeric_attr, average_attrs, format_percent, build_simulation_result, safe_float,
  readable_setting, attr_names, position_training_hint, simulation_comment)`: similarity_reason +
  render_my_notes 이동 후 app.py에서 14개 이름 모두 0회 사용으로 확인되어 블록 전체 삭제.
- `from ui.components import apply_theme as apply_ui_theme, render_feature_card, render_metric_cards,
  render_status_banner, safe_text`(구 13번 줄): 5개 이름 모두 import 줄 외에는 0회 사용 (100% dead, app.py
  자체 정의에 의해 완전히 shadow됨).
- `from ui.navigation import init_navigation_state, navigate_to, render_app_header`(구 14번 줄): 3개 이름 모두
  import 줄 외에는 0회 사용 (`render_app_header`는 app.py 자체 정의(663)가 active).
- `from views.prospect_search import render_prospect_search as render_prospect_search_view`(구 15번 줄):
  app.py에서 호출되지 않음 (active `render_prospect_search`는 app.py 자체 정의, 765~887).

## v7.3 현재(941줄) active 함수/상수 줄 번호

| 항목 | 줄 |
|---|---|
| 상단 import 블록 | 1~19 |
| DB 헬퍼 (load_db_url ~ get_prospect_diagnostics, money) | 49~494 |
| 선택 로직 (resolve_selected_player_context ~ render_app_header) | 504~702 |
| render_dashboard (6줄 wrapper → views/dashboard.py) | 704~709 |
| render_home | 712~760 |
| render_db_status (4줄 wrapper → views/db_status.py) | 761~764 |
| render_prospect_search (active, 123줄 — Step D 분리 후보) | 765~887 |
| main | 889~908 |
| render_career_simulation (wrapper → views/career_simulation.py) | 911~917 |
| render_legend_matching (wrapper → views/legend_matching.py) | 919~926 |
| render_ai_report (wrapper → views/ai_report.py) | 928~934 |
| render_my_notes (2줄 wrapper → views/scouting_notes.py) | 936~937 |
| `if __name__ == "__main__":` | 940~941 |

**중복 정의는 여전히 0개.**

## v7.4 다음 세션 후보 / 주의사항
- **(신규 발견, 큰 작업)** 9번 줄 `from services.db import (...)` (16개 이름)은 app.py가 동일한 이름의
  함수를 49~494줄에서 전부 자체 재정의하고 있어 import 자체가 dead일 가능성이 있음. 다음 세션에서
  한 함수씩 `services.db` 구현과 diff 비교 후, 동일하면 app.py 자체 정의를 삭제하고 import만 남기는
  방향으로 정리 가능 (legend_matching/dashboard 분리 때 `get_similar_players`/`get_valuations` 처리한
  방식과 동일). **범위가 크므로 별도 세션으로 분리 권장.**
- `render_prospect_search`(765~887, 123줄) 분리 계획은 CLAUDE_PROGRESS_SUMMARY.md v7의 "7. Step D"
  섹션에 상세 기록함 (의존성, session_state 키 목록, views/prospect_search.py 기존 dead wrapper 교체 필요).
- `views/prospect_search.py`의 `render_prospect_search_view`(기존 구현)는 여전히 app.py에서 미사용 —
  prospect_search 분리 시 이 파일을 확인하고 교체할 것.

---

# v6 업데이트 (views/legend_matching.py + views/dashboard.py 분리 세션, 최우선으로 읽을 것)

이번 세션에서 v5.3 후보였던 `render_legend_matching`/`render_mentor_guide`를
`views/legend_matching.py`로, `render_dashboard`(+ `korean_appearances`)를
`views/dashboard.py`로 분리했다. app.py는 **1842줄 → 1573줄**(-269)로 축소되었고,
중복 정의는 여전히 **0개**다.

## v6.1 views/legend_matching.py
- `render_legend_matching_view(player, profile, ctx)` (구 render_legend_matching 본문, `st.title` 포함)
- `render_mentor_guide(selected_player, selected_profile, mentor_row, mentor_profile)` (그대로 이동)
- `get_profile_by_profile_id(profile_id)` (app.py에서 이동, `services.db.query_one` 사용 — app.py 자체 `query_one`과 동일 구현 확인 후 이동)
- import: `analysis_helpers`(generate_mentor_guide, generate_similarity_reason, parse_json_field, safe_float),
  `services.db`(get_similar_players, query_one), `ui_components`(render_page_actions, render_player_profile_panel)
- app.py의 `render_legend_matching()`은 5줄 wrapper:
  `require_selected_player()` → `resolve_selected_player_context()` → `selected_profile()` → `render_legend_matching_view(player, profile, ctx)`

## v6.2 views/dashboard.py
- `render_dashboard_view(player, profile, ctx, entity_type)` (구 render_dashboard 본문, `st.title` 포함)
- `korean_appearances(df)` (app.py에서 그대로 이동)
- import: `analysis_helpers`(ATTRIBUTE_GROUPS, MENTALITY_KEYS, attr_bar_chart, attributes_long_df, group_analysis,
  parse_json_field, render_metric_cards, score_text, strength_sentence, summary_scores, top_attributes, weakness_sentence),
  `services.db`(get_appearances, get_valuations), `ui_components`(render_page_actions, render_player_profile_panel)
- app.py의 `render_dashboard()`은 5줄 wrapper:
  `resolve_selected_player_context()` → `selected_entity_type()` → `selected_player()` → `selected_profile()` → `render_dashboard_view(player, profile, ctx, entity_type)`

## v6.3 app.py에서 추가로 제거한 dead/중복 항목
- `get_similar_players` (app.py 자체 정의, services.db의 동일 함수와 100% 동일 — app.py에서는 자체 def가
  import를 shadow하고 있었으나 legend matching 이동 후 미사용이 되어 정의 자체를 삭제. view는 services.db 버전을 import)
- `get_valuations`/`get_appearances` (app.py 자체 정의, services.db와 100% 동일 — dashboard 이동 후 미사용이 되어 삭제,
  view는 services.db 버전을 import)
- 미사용이 된 import 정리: `import altair as alt`, `from ui_components import render_player_profile_panel`,
  `services.db.get_valuations`, analysis_helpers의 `MENTALITY_KEYS`/`attributes_long_df`/`attr_bar_chart`/
  `top_attributes`/`summary_scores`/`score_text`/`render_metric_cards`/`strength_sentence`/`weakness_sentence`/
  `group_analysis`/`generate_similarity_reason`/`generate_mentor_guide`

`similarity_reason(base_profile, candidate_profile)`(app.py, 731번 줄)은 여전히 단일 정의로 남아있으나
호출부가 없는 미사용 함수다 (이번 세션 범위 밖이라 삭제하지 않음, 다음 세션 dead code 후보).

## v6.4 현재(1573줄) active 함수/상수 줄 번호

| 항목 | 줄 |
|---|---|
| 상단 import 블록 | 1~45 |
| DB 헬퍼 (load_db_url ~ get_prospect_diagnostics, money) | 67~512 |
| 선택 로직 (resolve_selected_player_context ~ render_app_header) | 522~722 |
| render_dashboard (5줄 wrapper → views/dashboard.py) | 723 |
| similarity_reason (미사용, dead) | 731 |
| note_summary_text ~ build_manual_analysis (My Notes 보조 함수) | 755~1039 |
| render_my_notes | 1040 |
| render_home | 1348 |
| render_db_status | 1397 (1줄 wrapper → views/db_status.py) |
| render_prospect_search | 1401 (1줄 wrapper → views/prospect_search.py) |
| main | 1525 |
| render_career_simulation | 1547 (5줄 wrapper → views/career_simulation.py) |
| render_legend_matching | 1555 (5줄 wrapper → views/legend_matching.py) |
| render_ai_report | 1564 (5줄 wrapper → views/ai_report.py) |
| `if __name__ == "__main__":` | 1572 |

**중복 정의는 여전히 0개.**

## v6.5 다음 세션 후보
- `views/prospect_search.py`/`views/home.py`/`render_my_notes`(1040~1347, 308줄)는 의존성이 크므로
  신중히 접근 (이번 세션 지시사항대로 무리하지 말 것).
- `similarity_reason`(731, 미사용) 등 소규모 dead code 정리는 다음 세션에서 검토 가능.
- app.py 13~14번 줄 부근의 `ui.components`/`ui.navigation` import 중 일부가 여전히 미확인 상태로 남아있을 수 있음
  (이번 세션에서는 legend_matching/dashboard 분리에 직접 관련된 import만 정리함).

---

# v5 업데이트 (dead code 제거 + import 정상화 세션, 최우선으로 읽을 것)

이번 세션에서 v4.2에 기록된 dead 중복 정의를 **전부 제거**했다.
app.py는 **4069줄 → 1842줄**로 축소되었고, 이제 모든 함수/상수는
**정확히 1회씩만 정의**된다 (중복 정의 0개).
analysis_helpers.py / ui_components.py import 블록도 파일 맨 끝에서
**상단 import 영역(20~50줄)으로 이동**했다.

## v5.1 제거한 dead 블록 (원본 4069줄 기준 줄 번호)
1. `3978-4025`: 사용되지 않는 `get_report_sections` 마지막 dead 정의
2. `2826-3055`: `render_legend_matching`/`readable_setting`/`simulation_comment`/
   `render_career_simulation`/`get_report_sections`/`sections_to_report_text`/
   `render_ai_report`의 dead 중복 정의 묶음
3. `2090-2674`: `korean_notes`/`template_player_sentence`/`render_player_profile_panel`/
   `render_dashboard`/`render_legend_matching`/`readable_setting`/
   `render_career_simulation`/`get_report_sections`/`sections_to_report_text`/
   `render_ai_report`/`render_my_notes`/`render_home`/`render_prospect_search`/
   `render_db_status`/`main`의 dead 중복 정의 묶음 (단, `korean_appearances`(2077~2089)는
   active 코드에서 사용 중이라 별도로 보존 — 현재 793번 줄)
4. `764-2076`: `render_home`/`render_dashboard`/`render_legend_matching`/
   `render_career_simulation`/`generate_template_report`/`render_ai_report`/
   `render_my_notes`/`render_prospect_search`/`render_db_status`/
   `ATTRIBUTE_LABELS`/`ATTRIBUTE_GROUPS`/`MENTALITY_KEYS`/`attr_label`/`attr_description`/
   `numeric_attr`/`average_attrs`/`score_level`/`attributes_long_df`/`attr_bar_chart`/
   `summary_scores`/`top_attributes`/`template_player_sentence`/`render_player_profile_panel`/
   `render_metric_cards`/`readable_setting`/`get_report_sections`/`sections_to_report_text`의
   dead 중복 정의 묶음 (analysis_helpers.py로 이동된 함수들의 dead 잔재 포함)
5. 추가로 작은 dead stub 2개 제거: `render_prospect_search`(4줄, 옛 3698) 및
   `main`(42줄, `ui.navigation` 기반 옛 버전, 옛 3706)

`generate_template_report`(옛 1006~1040)는 호출부가 dead `render_ai_report`(옛 1041) 안에만
있어 함께 제거됨. `score_level`, `template_player_sentence`, `get_report_sections`,
`sections_to_report_text`, `korean_notes`도 active 코드에서 호출되지 않아 함께 제거됨.

## v5.2 현재(1842줄) active 함수/상수 줄 번호

| 항목 | 줄 |
|---|---|
| 상단 import 블록 (analysis_helpers/ui_components 포함) | 1~50 |
| DB 헬퍼 (load_db_url ~ get_prospect_diagnostics, money) | 79~582 |
| 선택 로직 (resolve_selected_player_context ~ render_app_header) | 592~792 |
| korean_appearances | 793 |
| render_dashboard | 806 |
| get_profile_by_profile_id | 929 |
| similarity_reason | 933 |
| note_summary_text ~ build_manual_analysis (My Notes 보조 함수) | 957~1241 |
| render_my_notes | 1242 |
| render_home | 1550 |
| render_db_status | 1599 (1줄 wrapper → views/db_status.py) |
| render_prospect_search | 1603 (1줄 wrapper → views/prospect_search.py) |
| main | 1727 |
| render_career_simulation | 1749 (5줄 wrapper → views/career_simulation.py) |
| render_mentor_guide | 1757 |
| render_legend_matching | 1767 |
| render_ai_report | 1833 (5줄 wrapper → views/ai_report.py) |
| `if __name__ == "__main__":` | 1841 |

**중복 정의는 이제 0개.** 모든 함수/상수는 정확히 1회만 정의됨.
analysis_helpers.py/ui_components.py import는 정상적으로 파일 상단(21~50줄)에 위치하며,
더 이상 "맨 끝 위치 유지" 제약이 없음.

## v5.3 다음 세션 view 분리 후보 (참고)
- `render_db_status`(1599)/`render_prospect_search`(1603)는 이미 views/*.py wrapper 상태 (완료).
- `render_legend_matching`(1767~1832, 66줄)이 다음 분리 후보. 의존: `require_selected_player`,
  `resolve_selected_player_context`, `selected_profile`, `render_player_profile_panel`,
  `get_similar_players`, `get_profile_by_profile_id`, `generate_similarity_reason`,
  `generate_mentor_guide`, `safe_float`, `render_mentor_guide`(1757), `render_page_actions`.
  `render_mentor_guide`도 함께 옮겨야 함. career_simulation/ai_report 분리 때와 동일한
  thin-wrapper 패턴(`require_selected_player` → `get_player_profile` → `*_view(player, profile)`)
  적용 가능.

---

# v4 업데이트 (analysis_helpers.py + views/career_simulation.py·ai_report.py 분리 세션, 최우선으로 읽을 것)

이번 세션에서 ACTIVE_FUNCTION_MAP v3.2에 정리된 ~19개 공유 순수 함수/상수를
`analysis_helpers.py`로, `render_player_profile_panel`을 `ui_components.py`로
이동했다. 이어서 `render_career_simulation`/`render_ai_report`의 active 본문을
`views/career_simulation.py`/`views/ai_report.py`로 이동하고, app.py에는
`require_selected_player()` → `get_player_profile()` → `render_*_view(player, profile)`
순서로 호출하는 5줄짜리 wrapper만 남겼다. **선택 로직(resolve_selected_player_context 등)은
줄 위치/내용 모두 변경 없음.** 결과: **app.py 4583줄 → 4069줄**.

## v4.1 현재(4069줄) active 함수/import 줄 번호 (다음 세션 시작 시 grep으로 재확인)

| 항목 | 줄 |
|---|---|
| import 블록 (top) | 1~20 |
| analysis_helpers.py / ui_components.py import 블록 (파일 끝, **이동 금지** — v4 3번 참고) | 4030~4067 |
| `if __name__ == "__main__":` | 4068 |
| `main` (active) | 3872 |
| `render_career_simulation` (active, wrapper 5줄 → views/career_simulation.py) | 3894 |
| `render_mentor_guide` (active) | 3902 |
| `render_legend_matching` (active) | 3912 |
| `render_ai_report` (active, wrapper 5줄 → views/ai_report.py) | 4026 |
| `get_report_sections`@3978, `sections_to_report_text` 없음 — 이 위치는 **이제 dead** (render_ai_report가 더 이상 호출하지 않음) |

## v4.2 Step D(dead code 정리) 후보 — app.py 4000줄 이하를 위한 다음 세션 작업

아래는 이번 세션에 active 정의를 analysis_helpers.py/views/*.py로 옮기고 나서
app.py에 **그대로 남아있는 dead 중복 정의들**이다. 삭제 시 줄 번호가 바뀌므로
**파일 아래쪽부터 위쪽 순서로** 처리할 것. 각 항목은 다음 세션에서
`grep -n "^def 함수명\|^ATTRIBUTE_GROUPS\|^MENTALITY_KEYS"`로 재확인 후 진행.

- `render_ai_report`/`get_report_sections`/`sections_to_report_text` dead 정의 3세트
  (현재 약 1829/1566/1604, 2435/2385/2423, 2995/2966/2988 부근)
- `render_career_simulation` dead 정의 (현재 약 2308, 2906 부근)
- `render_legend_matching` dead 정의 (현재 약 2234, 2826 부근)
- `render_dashboard`/`render_home`/`render_prospect_search`/`render_db_status`/`main` dead 정의들
- `attr_label`/`attr_description`/`numeric_attr`/`average_attrs`/`attributes_long_df`/
  `attr_bar_chart`/`top_attributes`/`summary_scores`/`readable_setting`/`render_metric_cards`/
  `render_player_profile_panel`/`ATTRIBUTE_GROUPS`/`MENTALITY_KEYS` dead 정의들
  (현재 약 1946~2148, 2877, 2297 부근)

이 dead 정의들을 모두 제거하면 파일 끝의 analysis_helpers/ui_components import 블록을
다시 파일 상단으로 옮겨도 이름 충돌이 없어진다 (선택 사항).

---

# v3 (이전 세션 — state.py 분리, 참고용 — 아래 줄 번호는 4583줄 기준이라 현재는 모두 -514 shift됨)

이번 세션에서 `get_selected_player_status()`의 요약 생성 로직과
`ENTITY_TYPE_LABELS`/`DATA_MODE_BADGE_CLASS` 상수를 `state.py`
(`build_selected_player_status`)로 이동했다 (판정 로직 자체는 변경 없음,
app.py에는 1줄짜리 wrapper만 남음). 그 결과 **app.py 4631줄 → 4583줄**.

아래 v2 이하 섹션의 줄 번호는 모두 **구버전(4631줄 기준)**이며 현재는 약
-48 shift되어 있다. 다음 세션에서는 이 v3 표를 기준으로 사용할 것
(단, 추가 편집 전 항상 `grep -n "^def 함수명" app.py`로 재확인).

## v3.1 현재(4583줄) active 함수 줄 번호

### 선택 로직 / 헤더 (DO NOT CHANGE LOGIC, 558~ → 561~)
| 함수 | 줄 |
|---|---|
| resolve_selected_player_context | 561 |
| selected_player_id | 633 |
| selected_profile_id | 637 |
| selected_entity_type | 641 |
| selected_profile | 645 |
| selected_player | 655 |
| require_selected_player | 687 |
| show_selected_player_banner | 697 |
| get_selected_player_status (wrapper → state.build_selected_player_status) | 711 |
| render_app_header | 720 |
| parse_json_field | 761 |

### 단일 정의 (active) — 리포트/시뮬레이션 보조
| 함수 | 줄 |
|---|---|
| build_simulation_result | 949 |
| generate_template_report | 1061 |
| group_analysis | 2959 |
| get_profile_by_profile_id | 3089 |
| similarity_reason | 3093 |
| note_summary_text | 3347 |
| safe_text | 3358 |
| get_career_settings | 3371 |
| normalize_env_settings | 3396 |
| setting_summary | 3412 |
| manual_similarity_candidates | 3455 |
| note_display_title | 3533 |
| build_manual_analysis | 3556 |
| safe_float | 4185 |
| compare_attributes | 4223 |
| attr_names | 4254 |
| position_training_hint | 4258 |
| generate_similarity_reason | 4271 |
| generate_mentor_guide | 4312 |
| render_mentor_guide | 4415 |

### 중복 정의 — ACTIVE는 마지막 줄
| 함수 | ACTIVE 줄 |
|---|---|
| attr_label | 2780 |
| attr_description | 2787 |
| numeric_attr | 2793 |
| average_attrs | 2808 |
| score_level | 2104 |
| attributes_long_df | 2816 |
| attr_bar_chart | 2836 |
| template_player_sentence | 2156 |
| top_attributes | 2873 |
| summary_scores | 2882 |
| render_metric_cards | 2911 |
| render_player_profile_panel | 2931 |
| readable_setting | 4194 |
| get_report_sections | 4491 |
| sections_to_report_text | 3279 |
| format_percent | 2904 |
| score_text | 2895 |
| korean_appearances | 2132 |
| korean_notes | 2145 |
| simulation_comment | 4351 |
| render_home | 3940 |
| render_dashboard | 2966 |
| render_legend_matching | 4425 |
| render_career_simulation | 4369 |
| render_ai_report | 4539 |
| render_my_notes | 3632 |
| render_prospect_search | 4039 |
| render_db_status | 3993 |
| main | 4163 (4582번 줄 `if __name__ == "__main__":` 에서 호출) |

## v3.2 Step C(views 분리)를 위한 선행 작업: `analysis_helpers.py` 필요

Step C 우선순위 1번인 `views/career_simulation.py`를 시도해본 결과,
`render_career_simulation`(4369) 하나만 옮기려 해도 다음 의존 함수들이
**모두 함께 필요**하다 (모두 app.py 전역에 산재):
- render_player_profile_panel(2931) → attr_label(2780)/attr_description(2787)/
  numeric_attr(2793)/average_attrs(2808)/attributes_long_df(2816)/
  attr_bar_chart(2836)/summary_scores(2882)/top_attributes(2873)/
  score_text(2895)/render_metric_cards(2911)/group_analysis(2959)/
  strength_sentence/weakness_sentence(2917/2924)/format_percent(2904)
- readable_setting(4194), safe_float(4185), build_simulation_result(949),
  simulation_comment(4351), parse_json_field(761)

이들은 거의 모든 화면(Dashboard/Legend Matching/Career Simulation/AI Report/
My Notes)에서 공유되는 **순수 함수(st/pd/alt만 사용, app.py 전역 상태 비의존)**
이므로, views/*.py 분리보다 먼저 `analysis_helpers.py` (가칭) 모듈을 만들어
이 함수들을 옮기는 것이 안전한 순서다.

**다음 세션 권장 순서**:
1. 위 ~16개 함수를 `analysis_helpers.py`로 이동 (순수 함수, app.py import 없음).
   app.py는 해당 active 정의를 삭제하고 `from analysis_helpers import ...`로 대체.
   → app.py 줄 수 추가 감소 + Step C 선행 조건 충족.
2. compileall + AppTest(Dashboard/Career Simulation/Legend Matching/AI Report/My Notes 전부) 회귀 확인.
3. 이후 `views/career_simulation.py`부터 분리 진행
   (render_career_simulation은 require_selected_player/get_player_profile/
   render_page_actions/state.py/analysis_helpers.py만 있으면 이동 가능해짐).
4. 단, attr_label/attr_description/numeric_attr/... 등은 app.py에 **2~3개의
   dead 중복 정의**가 더 남아있으므로, analysis_helpers.py로 옮길 때 active
   정의만 옮기고 dead 정의는 그대로 두거나(추후 Step D에서 정리) 별도 처리할 것.

---

# v2 이하 (구버전, 4631줄 기준 — 참고용, 줄 번호는 위 v3 기준으로 약 -48 shift됨)

이 문서는 모듈화(Step 1)를 위한 분석 결과다. app.py는 총 **5104줄**이며,
중단된 리팩토링으로 인해 많은 함수가 2~5회 중복 정의되어 있다.
Python은 "마지막 정의"만 유효하므로, 마지막 줄 번호의 정의가 **active**, 그 이전 정의들은 **dead code**다.

`if __name__ == "__main__":` 은 5103번 줄 (`main()` 호출).

---

## 1. 단일 정의 (중복 없음) — 모두 ACTIVE

### 1.1 DB 접근 헬퍼 (45~548줄, services/db.py 후보)
| 함수 | 줄 |
|---|---|
| load_db_url | 45 |
| get_connection | 56 |
| query_df | 60 |
| query_one | 71 |
| execute_one | 85 |
| show_db_error | 101 |
| table_count | 124 |
| preview_table | 132 |
| search_players | 140 |
| search_players_with_modes | 188 |
| get_distinct_positions | 279 |
| get_player | 294 |
| get_valuations | 305 |
| get_appearances | 320 |
| get_profile_by_player_id | 339 |
| get_profile_by_name | 350 |
| get_profile_by_name_nationality_position | 362 |
| get_player_profile | 388 |
| get_similar_players | 404 |
| insert_scouting_note | 428 |
| get_scouting_notes | 463 |
| get_prospect_diagnostics | 484 |
| money | 548 |

### 1.2 선택 선수 / 네비게이션 / 공통 헤더 (558~865줄) — **DO NOT CHANGE LOGIC**
| 함수 | 줄 | 비고 |
|---|---|---|
| resolve_selected_player_context | 558 | 핵심 선택 로직, 절대 수정 금지 |
| selected_player_id | 630 | |
| selected_profile_id | 634 | |
| selected_entity_type | 638 | |
| selected_profile | 642 | |
| selected_player | 652 | |
| require_selected_player | 684 | |
| show_selected_player_banner | 694 | |
| (consts) ENTITY_TYPE_LABELS, DATA_MODE_BADGE_CLASS, NAV_TARGETS, NAV_CHIP_LABELS | 708~745 | |
| go_to | 748 | session_state["nav_page_request"] + rerun |
| render_nav_chips | 754 | 상태 의존 없음 (stateless) |
| render_page_actions | 771 | 상태 의존 없음 (stateless) |
| get_selected_player_status | 786 | selected_player()/selected_entity_type() 의존 |
| render_app_header | 814 | get_selected_player_status, render_nav_chips 의존 |
| parse_json_field | 855 | |

### 1.3 리포트/시뮬레이션 보조 (3613~5060줄 구간에서 1회만 정의)
| 함수 | 줄 |
|---|---|
| group_analysis | 3483 |
| get_profile_by_profile_id | 3613 |
| similarity_reason | 3617 |
| score_text | 3419 |
| strength_sentence | 3441 |
| weakness_sentence | 3448 |
| note_summary_text | 3871 |
| safe_text | 3882 |
| get_career_settings | 3895 |
| normalize_env_settings | 3920 |
| setting_summary | 3936 |
| manual_similarity_candidates | 3979 |
| note_display_title | 4057 |
| build_manual_analysis | 4080 |
| safe_float | 4706 |
| compare_attributes | 4744 |
| attr_names | 4775 |
| position_training_hint | 4779 |
| generate_similarity_reason | 4792 |
| generate_mentor_guide | 4833 |
| render_mentor_guide | 4936 |
| build_simulation_result | 1043 |
| generate_template_report | 1155 |

---

## 2. 중복 정의 — ACTIVE는 "마지막 줄 번호"만

| 함수 | 모든 정의 줄 | **ACTIVE** | dead 정의 |
|---|---|---|---|
| apply_theme | 1556, 2129, 3002 | **3002** | 1556, 2129 |
| attr_label | 1645, 2246, 3304 | **3304** | 1645, 2246 |
| attr_description | 1650, 2253, 3311 | **3311** | 1650, 2253 |
| numeric_attr | 1654, 2259, 3317 | **3317** | 1654, 2259 |
| average_attrs | 1664, 2274, 3332 | **3332** | 1664, 2274 |
| score_level | 1672, 2377 | **2377** | 1672 |
| attributes_long_df | 1682, 2282, 3340 | **3340** | 1682, 2282 |
| attr_bar_chart | 1700, 2306, 3360 | **3360** | 1700, 2306 |
| template_player_sentence | 1740, 2429 | **2429** | 1740 |
| top_attributes | 1729, 2365, 3397 | **3397** | 1729, 2365 |
| summary_scores | 1719, 2351, 3406 | **3406** | 1719, 2351 |
| render_metric_cards | 1786, 2391, 3435 | **3435** | 1786, 2391 |
| render_player_profile_panel | 1751, 2440, 3455 | **3455** | 1751, 2440 |
| readable_setting | 1793, 2625, 3692, 4715 | **4715** | 1793, 2625, 3692 |
| get_report_sections | 1804, 2714, 3781, 5012 | **5012** | 1804, 2714, 3781 |
| sections_to_report_text | 1842, 2752, 3803 | **3803** | 1842, 2752 |
| format_percent | 2398, 3428 | **3428** | 2398 |
| korean_appearances | 2405 | (단일) | - |
| korean_notes | 2418 | (단일) | - |
| render_home | 868, 2852, 4461 | **4461** | 868, 2852 |
| render_dashboard | 904, 1854, 2476, 3490 | **3490** | 904, 1854, 2476 |
| render_legend_matching | 996, 1932, 2562, 3641, 4946 | **4946** | 996, 1932, 2562, 3641 |
| render_career_simulation | 1089, 1987, 2636, 3721, 4890 | **4890** | 1089, 1987, 2636, 3721 |
| render_ai_report | 1190, 2067, 2764, 3810, 5060 | **5060** | 1190, 2067, 2764, 3810 |
| render_my_notes | 1256, 2822, 4156 | **4156** | 1256, 2822 |
| render_prospect_search | 1289, 1435, 2876, 4510, 4560 | **4560** | 1289, 1435, 2876, 4510 |
| render_db_status | 1406, 2958, 4514 | **4514** | 1406, 2958 |
| simulation_comment | 3703, 4872 | **4872** | 3703 |
| main | 2983, 4518, 4684 | **4684** | 2983, 4518 |

---

## 3. 전체 실행 흐름 요약

- 파일 끝 (5103줄) `if __name__ == "__main__": main()` → **4684번째 `main()`**이 실행됨.
- `main()`은 `st.set_page_config`, `apply_theme()`(3002), sidebar radio(`nav_page`), `render_app_header()`(814), 그리고 각 페이지의 **active** render_* 함수를 호출.
- `render_ai_report`(5060), `render_legend_matching`(4946), `render_career_simulation`(4890), `get_report_sections`(5012) 등은 `main()`(4684) **정의보다 뒤**에 위치하지만, 실제 호출은 5103번째 줄에서 일어나므로 문제 없음(모든 def가 먼저 평가된 후 main 실행).

---

## 4. 모듈화 우선순위 (Step 2 이후)

### Step 2 — 즉시 분리 가능 (상태 의존 없음, app.py import 불필요)
- `theme.py`: `apply_theme()` (3002) — CSS만 포함, 다크 콕핏 팔레트로 교체
- `ui_components.py`: `go_to`(748), `NAV_TARGETS`/`NAV_CHIP_LABELS`(725~745), `render_nav_chips`(754), `render_page_actions`(771)

### Step 3 — state.py 분리 대상 (선택 로직 그대로 이동, 로직 변경 금지)
- `resolve_selected_player_context`(558), `selected_player_id/profile_id/entity_type/profile/player`(630~682),
  `require_selected_player`(684), `show_selected_player_banner`(694), `get_selected_player_status`(786),
  `ENTITY_TYPE_LABELS`/`DATA_MODE_BADGE_CLASS`(708~722)
- 이들은 DB 헬퍼(get_player, get_profile_by_*, query_one 등)에 의존하므로 data_access 분리와 함께 진행 필요.
- `render_app_header`(814)는 `get_selected_player_status` + `render_nav_chips`에 의존 → state.py/ui_components.py 분리 이후에 이동 가능.

### Step 4 — views/*.py 분리 대상 (위험도 높음, 신중히 진행)
- render_home(4461), render_prospect_search(4560), render_dashboard(3490), render_legend_matching(4946),
  render_career_simulation(4890), render_ai_report(5060), render_my_notes(4156), render_db_status(4514, 이미 views/db_status.py 사용 중)
- 각 함수는 attr_* / score_* / report 관련 보조 함수(섹션 1.3, 2)와 DB 헬퍼(섹션 1.1)에 강하게 의존 → data_access.py 분리가 선행되어야 안전.

### dead code 정리
- 섹션 2의 "dead 정의" 줄들은 삭제 가능하지만, 줄 번호가 서로 얽혀 있어 한 번에 제거 시 위험. 모듈 분리가 끝난 뒤 별도 세션에서 일괄 삭제 권장.
