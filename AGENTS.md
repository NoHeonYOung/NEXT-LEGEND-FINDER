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

## Coaching UI Invariants

- Career Simulation, Manual Note, AI Report의 기본 설명은 코칭 리포트형으로 유지한다.
- 공식, α/γ/β, training multiplier, Δleague 같은 개발자용 계산 근거는 기본 화면에 노출하지 않고
  `상세 계산 근거` expander에 둔다.
- 선택 조합의 위험도 calibration은 허용하지만 Growth Model 및 Ceiling Model 핵심 공식,
  ±15 scenario adjustment 범위, 0~100 Final Growth Score 범위는 변경하지 않는다.

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
