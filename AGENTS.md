# NEXT-LEGEND FINDER - Codex Project Rules

이 파일은 Codex 및 다른 코딩 에이전트가 이 프로젝트에서 작업할 때 따라야 하는 인수인계 규칙이다.
작업을 시작하기 전에 이 파일과 `CLAUDE_PROGRESS_SUMMARY.md`, `ACTIVE_FUNCTION_MAP.md`를 먼저 읽는다.

## Architecture

- 프로젝트명은 **NEXT-LEGEND FINDER**다.
- `app.py`는 라우터 중심 파일이다. 새 기능 구현을 이유로 대형화하지 않는다.
- 화면 구현은 기존 `views/*.py` 구조와 책임 경계를 따른다.
- `views/*.py`는 `app.py`를 import하면 안 된다. 순환 import와 라우터 결합을 만들지 않는다.
- 기존 helper와 모듈 패턴을 우선 사용하고, 불필요한 대규모 리팩터링을 하지 않는다.

## Protected Data And Infrastructure

- DB 스키마를 변경하지 않는다.
- `create_and_upload_db.py`를 수정하지 않는다.
- `.streamlit/secrets.toml`과 `.env`를 수정하거나 내용을 출력하지 않는다.
- 원본 CSV와 `Database_Project_Dataset/` 내용을 수정하거나 삭제하지 않는다.
- 외부 API 호출은 사용자가 해당 세션에서 명시적으로 요청한 경우에만 허용한다.
- Gemini API 기능은 optional + fallback + caching 구조로만 구현한다.

## Model Invariants

- Growth Model 공식을 변경하지 않는다.
- Ceiling Model 공식을 변경하지 않는다.
- 공식 변경이 필요해 보이면 코드 수정 전에 사용자에게 명시적으로 확인한다.

## Session State Invariants

다음 key는 Growth/Ceiling 흐름의 공개 계약이다. 함부로 삭제하거나 이름 및 구조를 변경하지 않는다.

- `growth_insight`
- `growth_explanation`
- `ceiling_growth_insight`
- `ceiling_growth_explanation`
- `ceiling_growth_context`

동작 규칙:

- Dashboard는 기본 Growth 결과를 갱신할 수 있지만 Ceiling 전용 결과를 삭제하거나 덮어쓰지 않는다.
- AI Report는 현재 선수/context와 일치하는 Ceiling 결과가 있으면 이를 우선 사용한다.
- 선수 변경 시 growth/ceiling/report 관련 session_state clear 흐름을 유지한다.
- 기존 stale `selected_profile_id` 수정 및 `selected_entity_type` 초기화 흐름을 깨지 않는다.
- Manual Note와 일반 선수의 Ceiling 결과를 `ceiling_growth_context`로 구분한다.
- "직접 입력 유망주"(`entity_type="manual_prospect"`, `views/manual_prospect.py`)는 Manual
  Note와 별개의 entity_type이다. `player_id=None`인 가상 player로 Dashboard/Career
  Simulation/유사 선수 후보/AI Report를 동일하게 사용하며, Dashboard는 기본 Growth만,
  Career Simulation은 Ceiling(`ceiling_growth_context.source="career_simulation"`)만
  갱신하는 규칙을 그대로 따른다.

## Coaching UI Invariants

- Career Simulation, Manual Note, AI Report의 기본 설명은 코칭 리포트형으로 유지한다.
- 공식, α/γ/β, training multiplier, Δleague 같은 개발자용 계산 근거는 기본 화면에 노출하지 않고
  `상세 계산 근거` expander에 둔다.
- 선택 조합의 위험도 calibration은 허용하지만 Growth Model 및 Ceiling Model 핵심 공식,
  ±15 scenario adjustment 범위, 0~100 Final Growth Score 범위는 변경하지 않는다.

## v18.3 Data Coverage Invariants

- `player_coverage.py`는 Streamlit/DB/app.py를 import하지 않는다. 순수 함수만 포함한다.
- `resolve_player_age(player, profile)`는 나이 계산의 단일 진실 공급원이다.
  선수 카드(`render_player_profile_panel`), Growth/Ceiling, Mentor age filter 모두 이 함수를 사용한다.
- `build_data_coverage(player, profile)`의 `analysis_level`은 "full"/"partial"/"limited" 세 값만 가진다.
  manual_prospect는 이 함수 범위 밖이며 별도 흐름을 유지한다.
- TM-only 선수에게 "full" analysis_level을 부여하지 않는다 (FM profile + style_vector 없음).
- `get_similar_players()` 호출 전 반드시 `has_fm_profile AND has_style_vector`를 확인한다.
- Prospect Search의 `analyze_only` 필터는 `profile_id.notna()` 후처리로 구현한다. DB 쿼리 변경 금지.
- Growth/Ceiling 공식을 변경하지 않는다. 나이 표현("현재 데이터 기반 성장 여지")은 표시 레이블만 변경이다.

## v19 Phase 1~2 Scouting Board / Player Dossier Invariants

- v19 전체 구현이 아니라 Scouting Board, Player Dossier, Data Coverage badge/panel 정리까지만 적용된 상태다.
- 기본 유망주 나이 기준은 15~25다.
- Scouting Board 기본 결과는 Full + Partial 중심이며 Limited 선수는 기본 제외한다.
- `analyze_only` 해제, `전체 DB 선수 포함`, 또는 `Limited 선수 포함` 옵션을 통해 Limited 선수를 볼 수 있다.
- FM profile 없는 Transfermarkt-only 선수는 v19 UI에서 Limited로 표시한다.
- Prospect Search의 `analyze_only` 핵심 필터는 계속 `profile_id.notna()` 후처리로 유지한다.
- 사용자 화면 제목은 `Scouting Board`, `Player Dossier`로 정리했지만 내부 nav key는 안정성을 위해 기존 값을 유지할 수 있다.
- `ui_components.render_data_coverage_panel`과 badge helper를 우선 사용해 Full / Partial / Limited / Manual 표시를 일관되게 유지한다.
- Player Dossier는 Growth 결과를 갱신할 수 있지만 Ceiling 전용 session_state를 삭제하거나 덮어쓰지 않는다.
- Style & Mentor Lab, Career Simulation, Evidence & Advisory Report, Notes 전체 개편은 아직 수행하지 않았다.

## Data Provenance and Labeling Invariants

현재 NEXT-LEGEND FINDER의 분석 방식을 실제 데이터 출처에 맞게 표현한다.

### 현재 데이터 출처 사실

- 멘탈리티 지표는 **FM mental attributes proxy**이다. 기사/스카우팅 텍스트 분석이 아니다.
  화면에서 "멘탈리티 평가"가 아니라 "FM 기반 멘탈 지표 (proxy)" 또는 "FM 멘탈 속성 proxy"로 표기한다.
- 리포트(AI Report 화면)는 **규칙 기반 리포트 초안**이다. Gemini API를 호출하지 않는다.
  화면에서 "AI 리포트"라는 표현 대신 "분석 리포트 초안", "규칙 기반 리포트", "스카우팅 분석 리포트 초안"을 사용한다.
- 정성 텍스트 분석(뉴스 기사, 감독 인터뷰, 스카우팅 텍스트)은 **아직 구현되지 않았다**.
  해당 입력이 없는 경우 "정성 텍스트 근거: 입력 없음"으로 표시한다.
- Gemini API는 **미사용**이다. `gemini_ready_payload`는 구조만 준비되어 있다.
  실제 Gemini 호출이 없는 결과에 "Gemini 분석" 라벨을 붙이지 않는다.

### 라벨링 규칙 (코딩 에이전트 준수 사항)

- `"AI 리포트"` 표현은 실제 Gemini/API 호출이 구현된 경우에만 사용한다.
  현재 상태에서는 `"규칙 기반 리포트"`, `"분석 리포트 초안"`, `"스카우팅 리포트 초안"`을 사용한다.
- `"멘탈리티 평가"`가 실제 텍스트/행동 분석을 암시할 경우 `"FM 기반 멘탈 지표 (proxy)"`로 대체한다.
- `"정성 분석"`은 실제 텍스트 입력이 없으면 `"규칙 기반 코칭 해석"`으로 표현한다.
- `"뉴스 기반"`, `"텍스트 기반"`, `"Gemini 기반"` 표현은 해당 기능이 실제 구현된 경우에만 사용한다.
- Dashboard / Career Simulation / AI Report / My Scouting Notes 화면에 `분석 근거 안내` expander가
  있어야 한다. 화면 수정 후 expander가 제거되지 않도록 주의한다.

### v18.2 이후 허용 표현 (업데이트)

v18.2에서 실제 Gemini API 호출 경로가 동작하도록 버그가 수정되었으므로:
- `secrets.toml`에 `GEMINI_API_KEY`가 있으면 실제 호출이 가능하다.
- `GOOGLE_API_KEY`도 fallback으로 인식된다.
- API key 값 자체는 어디에도 출력하지 않는다.
- SDK 설치: `pip install -U google-genai` (신규) 또는 `pip install google-generativeai` (구)

### v18 이후 허용 표현

v18에서 뉴스/스카우팅 텍스트 입력 기능이 실제로 추가되었으므로 다음 표현을 사용할 수 있다:
- "정성 텍스트 근거: [요약]" (텍스트가 입력되고 Gemini 추출이 완료된 경우에만)
- "Gemini 보조 스카우팅 추천" (실제 API 호출이 완료된 경우에만)
- Gemini API key가 없거나 텍스트를 입력하지 않으면 기존 DB/FM proxy/rule-based 분석만 표시한다.

### v18 Gemini 역할 정의

Gemini는 두 가지 역할만 수행한다:
1. 사용자가 붙여넣은 텍스트에서 정성 신호 구조화 추출
2. 정량 분석 결과 + 정성 신호를 종합한 근거 기반 보조 스카우팅 추천

Gemini가 하면 안 되는 것:
- 점수 계산 금지 (Growth/Ceiling Score 변경 금지)
- 없는 사실 단정 금지 (텍스트에 없는 내용 확정 표현 금지)
- Growth/Ceiling 공식 변경 금지
- 문장 미화 도구로 사용 금지

### v18 Qualitative Evidence Invariants

- `services/qualitative_evidence.py`는 DB/app.py/Streamlit UI를 import하지 않는다.
- `extract_qualitative_signals`와 `generate_gemini_advisory`는 항상 (result, error|None) 튜플을 반환한다.
- API key 없음, 텍스트 없음, 호출 실패 시 fallback dict를 반환하고 앱이 깨지지 않는다.
- Gemini 호출은 자동으로 수행되지 않는다. 사용자가 버튼을 눌렀을 때만 1회 호출한다.
- 정성 텍스트 분석이 없으면 기존 Growth/Ceiling/Coaching 리포트 구조가 그대로 유지된다.
- qualitative_evidence와 gemini_advisory는 scouting_notes JSONB의 simulation_result 안에 append-only key로 저장한다.
- DB 스키마를 변경하지 않는다. insert_scouting_note() 시그니처를 변경하지 않는다.
- 실제 Gemini API 호출 테스트는 자동 테스트에서 수행하지 않는다.
- `_augment_sections_with_qualitative`의 `has_signals`/`has_advisory` 체크에서 `None`을 제외 목록에 넣지 않는다 (v18.2 버그 수정).
- `_SAVE_EXCLUDE_FALLBACK_REASONS = ("no_text_input", "no_api_key", "api_error", "parse_failed")` — api_error 시 qual_evidence를 저장하지 않아 report_generation_mode가 rule_based로 유지된다.
- `gemini_client.py`는 google-genai(신규 SDK) → google-generativeai(구 SDK) 순으로 시도한다. 두 SDK 모두 없으면 설치 안내 오류를 반환한다.
- `get_gemini_sdk_unavailable_reason()`은 None/"no_api_key"/"sdk_not_installed" 중 하나를 반환한다. SDK 미설치와 key 미설정을 구분한다.

## Scouting Notes Persistence Invariants

- `scouting_notes` DB 스키마와 기존 `insert_scouting_note()` 시그니처를 변경하지 않는다.
- `env_settings` JSONB의 `note_type`, `source`, `entity_type`, snapshots, `ceiling_growth_context`,
  `career_settings` 메타데이터 구조를 유지한다.
- `simulation_result` JSONB의 기존 prototype 최상위 key를 유지하고, 구조화 Growth/Ceiling/Coaching
  결과는 append-only key로 저장한다.
- AI Report, Manual Note, Career Simulation 저장은 `scouting_note_payload.py`의 순수 helper를 사용한다.
- 신규 구조가 없는 legacy note 조회 fallback을 제거하거나 깨지 않는다.
- 저장된 Growth/Ceiling 결과는 저장 시점 스냅샷이며 조회 시 현재 공식으로 자동 재계산하지 않는다.
- 실제 `scouting_notes` DB INSERT 테스트는 사용자 명시 확인 없이 수행하지 않는다.
- payload helper의 Streamlit/DB/app.py 비의존성과 JSON 직렬화 안전성을 유지한다.
- 저장 노트 기본 화면에는 내부 JSON key 대신 사용자용 라벨을 표시하고 원본 payload는 expander에 둔다.
- 저장 노트 기본 화면은 점수 요약과 구조화 코칭 리포트를 원문 리포트보다 먼저 표시한다.
- Gemini API 미사용 저장 결과는 `규칙 기반 리포트`로 표시하며 Gemini 생성물처럼 라벨링하지 않는다.
- 템플릿/원문 리포트와 개발자용 저장 데이터는 서로 분리된 expander에 둔다.
- 선택된 멘토가 없을 때 별도 멘토 섹션을 강조하지 않으며, legacy note fallback을 유지한다.
- Scouting Notes 저장/조회 구조를 변경하면 `CLAUDE_PROGRESS_SUMMARY.md`, `ACTIVE_FUNCTION_MAP.md`,
  `REAL_MODEL_PLAN.md`, `AGENTS.md`를 같은 작업에서 최신화한다.
- `views/scouting_notes.py`("My Scouting Notes")는 저장 노트 조회 전용 화면이다. 새 유망주
  생성 폼은 "직접 입력 유망주"(`views/manual_prospect.py`)에 있다 — 다시 합치지 않는다.

## Mentor Matching Invariants

- 유사 선수 후보(멘토) 목록은 `manual_prospect_helpers.filter_mentor_candidates_by_age`로
  나이 필터를 적용한다: 1차 기준 `max(28, target_age + 5)`, 완화 기준
  `max(26, target_age + 3)`, 자기 자신과 나이 없음/0세 후보는 제외한다.
- 완화 기준이 적용되면(`used_fallback=True`) "조건을 완화해 표시한 후보입니다." 안내를
  표시한다. 이 필터 규칙을 약화하거나 제거하지 않는다.

## Required Verification

코드 또는 동작에 영향을 주는 변경 후 아래 테스트를 반드시 실행하고 결과를 보고한다.

```bash
python -m compileall .
python test_state_refactor.py
python test_analysis_helpers_split.py
python test_prospect_search_split.py
python test_growth_model.py
```

Streamlit도 headless 모드로 실행하고 `/_stcore/health`가 HTTP 200과 `ok`를 반환하는지 확인한다.
Supabase 조회가 필요한 AppTest가 샌드박스 네트워크 제한으로 실패하면, 허용된 네트워크 환경에서
동일 테스트를 다시 실행해 실제 회귀 여부를 확인한다.

## Reporting

- 수정한 파일과 변경한 동작을 구체적으로 보고한다.
- 실행한 테스트별 통과 수와 Streamlit health check 결과를 보고한다.
- 실행하지 못한 테스트나 남은 문제를 숨기지 않는다.
- DB, secrets, 원본 데이터, 외부 API를 건드리지 않았는지 명확히 기록한다.
