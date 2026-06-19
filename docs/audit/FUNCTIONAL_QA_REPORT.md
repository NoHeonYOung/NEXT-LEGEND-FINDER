# FUNCTIONAL_QA_REPORT.md
## v19 Final Functional QA — 2026-06-19

---

## 1. 작업 전 git status 요약

수정된 파일: `app.py`, `analysis_helpers.py`, `explanation_engine.py`, `gemini_client.py`, `manual_prospect_helpers.py`, `scouting_note_payload.py`, `services/db.py`, `state.py`, `theme.py`, `ui_components.py`, `views/` 전체, `test_*.py` 전체.

미추적 파일: `CLEANUP_AUDIT_REPORT.md`, `FOLDER_ORGANIZATION_REPORT.md`, `TECHNICAL_LOGIC_AUDIT_REPORT.md`, `V19_FINAL_*.md` task 파일들, `archive/`, `components/`, `docs/`, `styles/`.

v18~v19 작업 결과가 staging 상태이며, 이전 단계 정리 작업이 완료된 상태에서 기능 QA를 시작했다.

---

## 2. 발견한 기능 오류 목록

| # | 위치 | 오류 유형 | 내용 |
|---|------|-----------|------|
| 1 | `scouting_note_payload.py::_build_note_payload` | **Critical** – TypeError on save | `ceiling_growth_insight`, `ceiling_growth_explanation`, `ceiling_growth_context`, `entity_type`가 required 파라미터인데 호출부에서 전달하지 않아 모든 Notes 저장이 실패함 |
| 2 | `views/career_simulation.py` (DB 선수 저장) | **Critical** – same as #1 | `build_career_simulation_note_payload` 호출 시 `entity_type`, ceiling 3개 파라미터, `report_text` 모두 누락 |
| 3 | `views/career_simulation.py` (Manual 저장) | **Critical** – same as #1 | `build_manual_note_payload` 호출 시 ceiling 3개 파라미터 누락 |
| 4 | `views/ai_report.py` (DB 선수 저장) | **Critical** – same as #1 | `build_ai_report_note_payload` 호출 시 `entity_type`, `ceiling_growth_insight`, `ceiling_growth_explanation` 누락 |
| 5 | `views/ai_report.py` (Manual 저장) | **Critical** – same as #1 | `build_manual_note_payload` 호출 시 ceiling 3개 파라미터 누락 |
| 6 | `views/legend_matching.py::_render_mentor_section` | UX – 빈 상태 시 막힘 | 멘토 후보 없을 때 안내 메시지만 표시하고 CTA 버튼이 없어 흐름이 끊김 |
| 7 | `views/prospect_search.py::_ANALYSIS_STATE_KEYS` | UX – stale state | 선수 변경 시 `archive_selected_idx`가 초기화되지 않아 Archive 노트 선택 상태가 이전 선수 기준으로 남음 |

---

## 3. 수정한 기능 오류 목록

| # | 수정 파일 | 수정 내용 |
|---|-----------|-----------|
| 1 | `scouting_note_payload.py` | `_build_note_payload`의 `ceiling_growth_insight`, `ceiling_growth_explanation`, `ceiling_growth_context`, `entity_type` 파라미터에 `None` 기본값 추가 → 기존 호출부 호환 유지 |
| 2 | `views/career_simulation.py` | DB 선수 저장 호출에 `entity_type`, `ceiling_growth_insight`, `ceiling_growth_explanation`, `ceiling_growth_context`, `report_text` 추가 |
| 3 | `views/career_simulation.py` | Manual Prospect 저장 호출에 `ceiling_growth_insight`, `ceiling_growth_explanation`, `ceiling_growth_context` 추가 |
| 4 | `views/ai_report.py` | DB 선수 저장 호출에 `entity_type`, `ceiling_growth_insight`, `ceiling_growth_explanation` 추가 |
| 5 | `views/ai_report.py` | Manual Prospect 저장 호출에 `ceiling_growth_insight`, `ceiling_growth_explanation`, `ceiling_growth_context` 추가 |
| 6 | `views/legend_matching.py` | `_render_mentor_section` 빈 상태 메시지를 사용자 친화 문구로 개선, "Scouting Board로 돌아가기" / "커리어 시뮬레이션으로 이동" CTA 추가 |
| 7 | `views/prospect_search.py` | `_ANALYSIS_STATE_KEYS`에 `archive_selected_idx` 추가 |

---

## 4. 수정하지 않은 항목 및 이유

- **DB 스키마 변경 없음**: `insert_scouting_note` SQL과 `scouting_notes` 테이블 구조는 그대로. DB에 없는 확장 필드는 JSONB(`env_settings`, `simulation_result`) 안에 보관하는 기존 구조 유지.
- **Growth/Ceiling 공식 변경 없음**: `growth_model.py`, `explanation_engine.py` 로직 미변경.
- **Gemini client 구조 변경 없음**: 이미 구조적으로 안전하게 fallback 반환. 별도 수정 불필요.
- **원본 CSV, secrets, env 변경 없음**.

---

## 5. Scouting Notes 저장 흐름 점검 결과

**핵심 발견**: `_build_note_payload`에 required 파라미터 5개가 있는데 호출부 4곳 모두 일부를 전달하지 않았다. 이로 인해 Career Simulation, AI Report 양쪽에서 Notes 저장 버튼을 누르면 `TypeError`가 발생해 저장이 전혀 불가능했다.

**수정 후**:
- `_build_note_payload`에 기본값(`None`) 추가 → 기존 코드 호환성 확보.
- 호출부 4곳에 실제 ceiling/entity 값을 명시적으로 전달.
- payload의 모든 값은 `json_safe()`를 통과하므로 NaN/Inf/numpy 타입 문제 없음.
- DB insert 실패 시 `st.error()` + 개발자용 expander로 raw error 표시 (기존 코드 유지).

**검증**:
- `test_note_payload_json_serializable`: json.dumps 가능 확인.
- `test_note_payload_nan_sanitized`: NaN/Inf → None 변환 확인.
- `test_manual_note_payload_json_serializable`: manual payload 직렬화 확인.
- `test_manual_prospect_payload_no_conflict_with_insert`: insert 인자 구조 충돌 없음 확인.

---

## 6. Mentor Matching 흐름 점검 결과

**발견**: 멘토 후보가 없을 때 `empty_state_panel_html`만 표시하고 CTA가 없어 사용자가 다음 행동을 할 수 없었다. 또한 안내 메시지가 "다른 선수를 선택해보세요"만 있어 이유 설명 없이 끊김.

**수정 후**:
- "현재 조건에 맞는 멘토 후보를 찾지 못했습니다. 비슷한 포지션과 능력치 패턴을 가진 경험 많은 선수가 충분하지 않기 때문입니다. 다른 선수를 선택하거나 Scouting Board에서 다시 선택해보세요."
- "Scouting Board로 돌아가기" (primary) / "커리어 시뮬레이션으로 이동" CTA 추가.
- 기존 완화 기준 적용 로직(`filter_mentor_candidates_by_age`의 `min_results`)은 변경 없음.
- Manual Prospect 멘토 흐름도 같은 empty state 패턴을 이미 사용 중이라 추가 수정 불필요.

**검증**:
- `test_mentor_empty_list_safe`: 빈 리스트 정렬 안전성 확인.
- `test_mentor_filter_by_age_returns_empty_safely`: 빈 pool 필터 안전성 확인.

---

## 7. Gemini 실패 처리 점검 결과

**점검 결과: 기존 코드가 이미 잘 설계되어 있음.**

- `generate_gemini_content()` → `{"success": bool, "text": ..., "error": ...}` 구조 반환.
- `extract_qualitative_signals()`, `generate_gemini_advisory()` → `(result_dict, error_message|None)` 반환.
- quota 초과(`429`), key 없음(`no_api_key`), SDK 미설치(`sdk_not_installed`), 네트워크 실패 → 모두 safe fallback 반환.
- `views/ai_report.py`의 `_render_gemini_failure()` → 원인별 사용자 친화 문구로 분기.
- raw error는 `st.expander` 안에만 표시.
- `_SAVE_EXCLUDE_FALLBACK_REASONS`로 fallback signal/advisory를 저장에서 제외.

**추가 수정 없음. 설계가 이미 올바름.**

**검증**:
- `test_gemini_quota_exceeded_returns_fallback`: fallback 구조 확인.
- `test_gemini_no_api_key_returns_fallback`: no_api_key fallback 확인 및 SAVE_EXCLUDE 포함 확인.

---

## 8. Career Simulation → Report → Notes 연결 점검 결과

**흐름**: `env_settings` + `simulation_result` → `st.session_state` 저장 → `ai_report.py`에서 조회 → `generated_report_sections` 저장 → Notes 저장 버튼.

**발견**: 연결 자체는 정상이었으나 Notes 저장 시 ceiling 파라미터 누락으로 실패.

**수정 후**: Career Simulation에서 `ceiling_growth_context`를 session_state에 저장하는 기존 로직이 유지되고, AI Report에서 `is_ceiling_context_current()`로 유효성을 검증한 뒤 payload에 전달하는 흐름이 정상 동작.

**검증**: `test_note_payload_json_serializable`에서 end-to-end payload 빌드 확인.

---

## 9. Manual Prospect 흐름 점검 결과

**점검**:
- Manual Prospect 생성 → `selected_entity_type == "manual_prospect"` 설정 → `manual_player` session_state에 저장.
- Career Simulation, AI Report에서 `entity_type == "manual_prospect"` 분기로 처리.
- Notes 저장 시 `player_id=None`, `profile_id=None`이어도 insert SQL은 `null` 허용.

**발견**: build_manual_note_payload 호출 시 ceiling 파라미터 누락 (수정 완료).

**수정 후**: Manual Prospect Notes 저장 흐름 정상 동작 예상.

**검증**: `test_manual_note_payload_json_serializable`, `test_manual_prospect_payload_no_conflict_with_insert`.

---

## 10. session_state 초기화 점검 결과

**점검**:
- `_ANALYSIS_STATE_KEYS` 목록 확인.
- `_select_native_full_player()`: player_id가 바뀔 때 `_clear_analysis_state()` 호출.
- `_select_analysis_ready_player()`: 항상 `_clear_analysis_state()` 호출.

**발견**: `archive_selected_idx`가 누락되어 있어 선수 변경 후 Archive 노트 선택 상태가 남아있었음.

**수정**: `archive_selected_idx`를 `_ANALYSIS_STATE_KEYS`에 추가.

**검증**: `test_analysis_state_keys_contains_required`.

**남은 주의사항**: `qualitative_text_input`은 `_ANALYSIS_STATE_KEYS`에 이미 포함되어 있음. `manual_player`, `manual_attributes`, `manual_career_settings`는 선수 선택 시 직접 `pop` 처리함 (기존 로직).

---

## 11. 추가한 테스트

파일: `test_final_functional_flows.py` (11개 테스트, 전체 통과)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_note_payload_json_serializable` | DB 선수 note payload json.dumps 가능 |
| `test_note_payload_nan_sanitized` | NaN/Inf → None 변환 |
| `test_manual_note_payload_json_serializable` | Manual Prospect payload 직렬화 |
| `test_gemini_quota_exceeded_returns_fallback` | quota 초과 fallback 구조 |
| `test_gemini_no_api_key_returns_fallback` | no_api_key fallback 및 SAVE_EXCLUDE 확인 |
| `test_mentor_empty_list_safe` | 빈 mentor_records 정렬 안전성 |
| `test_mentor_filter_by_age_returns_empty_safely` | 빈 pool 필터 안전성 |
| `test_mentor_empty_state_note_payload_still_saves` | 멘토 없이 payload 빌드 |
| `test_analysis_state_keys_contains_required` | 필수 state key 누락 없음 |
| `test_manual_prospect_payload_no_conflict_with_insert` | manual payload insert 구조 확인 |
| `test_extract_structured_note_result_safe_with_empty` | 빈/None 입력 안전성 |

---

## 12. 기존 테스트 결과

| 파일 | 결과 |
|------|------|
| `python -m compileall .` | OK (오류 없음) |
| `test_growth_model.py` | 82 passed |
| `test_state_refactor.py` | 3 passed |
| `test_analysis_helpers_split.py` | 4 passed |
| `test_prospect_search_split.py` | 2 passed |
| `test_final_functional_flows.py` | 11 passed |

**전체: 102 passed, 0 failed**

---

## 13. Streamlit health check 결과

`python -m compileall . -q` → 구문 오류 0건.

Streamlit 브라우저 수동 실행은 자동화 환경 제약으로 수행하지 못했다. 아래 화면은 사용자가 직접 확인해야 한다.

---

## 14. 사용자가 직접 확인해야 할 화면

1. **Scouting Board → 선수 선택 → Player Dossier 이동**: 선수 선택이 session_state에 정상 저장되는지.
2. **Career Simulation 저장 버튼**: Notes 저장 후 `note_id` 성공 메시지 표시 여부.
3. **AI Report 저장 버튼**: Notes 저장 후 `note_id` 성공 메시지 표시 여부.
4. **Mentor Matching — 멘토 후보 없음**: CTA 버튼이 표시되는지.
5. **Manual Prospect → Career Simulation → Notes 저장**: Manual 흐름 end-to-end.
6. **Scouting Archive 조회**: 저장한 노트가 보이고 상세 보기가 작동하는지.
7. **선수 A 분석 후 선수 B 선택**: growth/mentor/report 상태가 초기화되는지.

---

## 15. 남은 리스크

| 항목 | 위험도 | 내용 |
|------|--------|------|
| Supabase 실제 insert | 중 | DB 연결 상태, JSONB 크기 제한, RLS 정책에 따라 저장 실패 가능. 로컬 테스트에서는 검증 불가. |
| Gemini API key 없는 환경 | 낮 | 이미 fallback 처리됨. 단 SDK가 설치되어 있어야 `is_gemini_available()`이 정상 작동. |
| `style_vector` 없는 선수 Mentor Matching | 낮 | `profile.get('style_vector')` None 체크 후 early return으로 처리됨. |
| 매우 큰 report_sections | 낮 | `compact_report_sections`의 `MAX_REPORT_SECTIONS=50`, `MAX_REPORT_SECTION_CHARS=5000`으로 제한됨. |
| `streamlit.testing.v1` 의존 테스트 | 낮 | DB 연결이 필요한 테스트는 실제 Supabase에 의존. CI 환경에서는 실패할 수 있음. |
