# CODEX_TASK_V16_1_PERSISTENCE_QA.md

## 작업 목표

이 프로젝트는 `c:\Users\nhy81\Desktop\Database_Project`의 NEXT-LEGEND FINDER Streamlit + Supabase 프로젝트입니다.

현재 상태:

* v16: Scouting Notes structured persistence 구현 완료
* `scouting_note_payload.py` 추가 완료
* AI Report / Manual Note / Career Simulation 저장 payload 강화 완료
* My Scouting Notes 조회 화면 강화 완료
* 전체 테스트 통과
* Streamlit health check 정상

중요한 현재 한계:

* v16 테스트에서는 실제 DB INSERT를 수행하지 않았습니다.
* 따라서 이번 작업은 Gemini/API 추가가 아니라, 저장/조회 흐름이 실제 앱 기준으로 안전한지 검수하고 UI를 다듬는 작업입니다.

이번 작업 목표:

1. v16 저장 payload 구조가 실제 저장/조회 화면에서 깨지지 않는지 점검
2. My Scouting Notes에서 저장된 Growth/Ceiling/Coaching 결과가 사용자 친화적으로 보이는지 개선
3. legacy note fallback이 유지되는지 확인
4. 실제 DB INSERT는 Codex가 임의로 수행하지 말고, 필요한 경우 사용자 수동 검수 절차를 명확히 작성
5. 모든 변경 후 문서 최신화까지 완료

문서 최신화가 없으면 작업 완료로 보지 않습니다.

---

## 1. 먼저 읽을 파일

작업 전 아래 파일을 순서대로 읽으세요.

1. `AGENTS.md`
2. `CLAUDE_PROGRESS_SUMMARY.md`
3. `ACTIVE_FUNCTION_MAP.md`
4. `REAL_MODEL_PLAN.md`
5. `scouting_note_payload.py`
6. `services/db.py`
7. `views/scouting_notes.py`
8. `views/ai_report.py`
9. `views/career_simulation.py`
10. `test_growth_model.py`

먼저 현재 구조를 짧게 요약한 뒤 작업을 진행하세요.

---

## 2. 절대 원칙

* DB 스키마 변경 금지
* `create_and_upload_db.py` 수정 금지
* `.streamlit/secrets.toml` 출력/수정 금지
* `.env` 출력/수정 금지
* 원본 CSV 수정 금지
* Gemini API 호출 금지
* 기사 API 구현 금지
* 10x10 Grid 구현 금지
* `app.py` 대형화 금지
* 기존 Growth Model 공식 변경 금지
* 기존 Ceiling Model 공식 변경 금지
* 기존 session_state key 구조 삭제 금지
* 기존 scouting_notes JSONB payload 구조 삭제 금지
* legacy note fallback 삭제 금지
* 문서 최신화 누락 금지

---

## 3. 이번 작업 범위

이번 작업은 “새 기능 추가”가 아니라 v16 저장/조회 흐름 안정화입니다.

확인할 흐름:

```text id="mhzpd7"
Career Simulation
→ 현재 시뮬레이션 결과를 스카우팅 노트에 저장
→ My Scouting Notes에서 해당 노트 조회
→ Growth Score / Final Growth Score / 코칭 리포트 복원
```

```text id="kyx1pk"
AI Report
→ 리포트 저장
→ My Scouting Notes에서 리포트 조회
→ Growth/Ceiling 구조화 결과와 리포트 문자열 확인
```

```text id="k1lrd5"
Manual Note
→ 직접 입력 선수 분석 저장
→ My Scouting Notes에서 Manual Note 배지와 코칭 리포트 확인
```

---

## 4. 실제 DB INSERT 관련 지침

Codex는 테스트 과정에서 실제 Supabase DB에 임의 INSERT를 수행하지 마세요.

대신 다음 중 하나로 처리하세요.

1. 코드 레벨 검증:

   * payload helper가 JSON 직렬화 가능한 dict를 생성하는지 확인
   * 필수 key가 포함되는지 테스트
   * legacy payload도 렌더링 함수에서 깨지지 않는지 테스트

2. 앱 수동 검수 절차 작성:

   * 사용자가 실제 Streamlit 화면에서 어떤 버튼을 눌러 확인해야 하는지 단계별 체크리스트를 작성
   * 저장 성공 시 어떤 메시지가 보여야 하는지 작성
   * My Scouting Notes에서 어떤 항목이 보여야 정상인지 작성

실제 DB INSERT가 반드시 필요하다고 판단되면, 코드를 실행하기 전에 사용자에게 명확히 확인을 요청하도록 보고하세요.

---

## 5. My Scouting Notes UI 점검 및 개선

`views/scouting_notes.py`의 조회 화면을 점검하세요.

저장된 신규 구조가 있는 경우 다음 항목이 보기 좋게 표시되어야 합니다.

* note_type / source 배지
* 실제 DB 선수 / Manual Note 구분
* 선수 스냅샷
* Growth Score
* Final Growth Score
* 시나리오 총평
* 추천 훈련 방향
* 기대 장점
* 소홀히 했을 때의 단점
* 리스크 경고
* 추천 커리어 전략
* 저장된 리포트 문자열 일부

개선 방향:

* 내부 JSON key가 기본 화면에 너무 노출되지 않게 하기
* 공식/개발자용 정보는 expander 안으로 이동
* 사용자 화면에는 “저장된 분석 결과”처럼 읽히게 만들기
* legacy 노트는 기존 방식으로 계속 표시
* 신규 구조가 없는 노트에서 KeyError가 발생하지 않게 하기

---

## 6. 저장 버튼 UX 점검

### Career Simulation

`views/career_simulation.py`의 저장 버튼을 점검하세요.

정상 조건:

* 버튼 이름이 사용자가 이해하기 쉬워야 함
* 저장 성공 시 note_id를 보여줘야 함
* 저장 후 My Scouting Notes에서 확인 가능하다는 안내가 있으면 좋음
* 저장 실패 시 에러 메시지가 과도하게 기술적이지 않아야 함

권장 문구:

```text id="8fr1un"
현재 시뮬레이션 결과가 스카우팅 노트에 저장되었습니다.
My Scouting Notes에서 다시 확인할 수 있습니다.
```

### AI Report

`views/ai_report.py`의 저장 버튼을 점검하세요.

정상 조건:

* Growth/Ceiling 구조화 결과가 simulation_result에 포함됨
* 리포트 문자열은 gemini_report에 유지됨
* 저장 성공/실패 메시지가 명확함

### Manual Note

`views/scouting_notes.py`의 Manual Note 저장 흐름을 점검하세요.

정상 조건:

* note_type이 manual_custom_prospect로 저장됨
* source가 manual_note로 저장됨
* 직접 입력 선수와 실제 DB 선수가 혼동되지 않음
* Manual Growth/Ceiling/Coaching 결과가 구조화 저장됨

---

## 7. Payload helper 점검

`scouting_note_payload.py`를 점검하세요.

확인할 것:

* Streamlit 의존성이 없는지
* DB 의존성이 없는지
* app.py import가 없는지
* JSON 직렬화가 안전한지
* None, tuple, numpy/pandas scalar, datetime 같은 값이 안전하게 변환되는지
* legacy payload 복원 시 에러가 나지 않는지
* report_sections가 너무 큰 경우에도 안전하게 compact되는지

필요하면 최소 수정으로 보강하세요.

---

## 8. 테스트 보강

기존 테스트를 유지하고, 가능하면 다음 테스트를 추가 또는 보강하세요.

1. `scouting_note_payload.py`가 Streamlit/DB 없이 import 가능한지
2. AI Report payload가 JSON 직렬화 가능한지
3. Manual Note payload가 JSON 직렬화 가능한지
4. Career Simulation payload가 JSON 직렬화 가능한지
5. legacy note payload에서 growth_insight가 없어도 복원 로직이 깨지지 않는지
6. note_type/source가 payload에 명시되는지
7. saved note 조회용 helper가 신규/legacy 구조를 모두 처리하는지

실제 DB INSERT 테스트는 수행하지 마세요.

---

## 9. 수동 검수 체크리스트 작성

작업 후 문서 또는 완료 보고에 사용자가 직접 확인할 수 있는 체크리스트를 작성하세요.

체크리스트 예시:

```text id="tc41hu"
1. Streamlit 실행
2. Prospect Search에서 선수 선택
3. Career Simulation 이동
4. 훈련강도/출전기회/리그난이도 조정
5. 현재 시뮬레이션 결과를 스카우팅 노트에 저장 클릭
6. 저장 성공 메시지와 note_id 확인
7. My Scouting Notes 이동
8. 방금 저장한 노트 확인
9. Growth Score / Final Growth Score 표시 확인
10. 코칭 리포트 섹션 표시 확인
11. 개발자용 JSON은 expander 안에 있는지 확인
```

---

## 10. 문서 최신화 필수

작업 후 아래 문서를 반드시 업데이트하세요.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `ACTIVE_FUNCTION_MAP.md`
3. `REAL_MODEL_PLAN.md`
4. `AGENTS.md`가 필요하면 보강

문서에는 다음 제목으로 기록하세요.

```text id="bbz6y4"
v16.1: Persistence QA and saved-note UI polish
```

각 문서에 반영할 내용:

### CLAUDE_PROGRESS_SUMMARY.md

* v16.1에서 무엇을 점검/수정했는지
* 실제 DB INSERT는 테스트에서 수행하지 않았다는 점
* 수동 검수 체크리스트
* 테스트 결과
* 남은 문제

### ACTIVE_FUNCTION_MAP.md

* `scouting_note_payload.py` 주요 helper 정리
* 저장/조회 UI 흐름 정리
* 신규/legacy note 처리 흐름 정리

### REAL_MODEL_PLAN.md

* 저장된 결과는 저장 시점 스냅샷이라는 점
* My Scouting Notes에서 복원되는 항목
* legacy fallback 정책
* 실제 DB 검수 절차

### AGENTS.md

* Scouting Notes 저장 구조를 바꿀 때 문서 최신화 필수
* 실제 DB INSERT 테스트는 사용자 확인 없이 수행하지 말 것
* JSONB payload 구조와 legacy fallback 유지

중요:
문서 최신화가 없으면 작업 완료로 보지 않습니다.
완료 보고에는 반드시 수정한 MD 파일과 추가한 섹션명을 포함하세요.

---

## 11. 테스트 실행

작업 후 반드시 실행하세요.

```bash id="fye15g"
python -m compileall .
python test_state_refactor.py
python test_analysis_helpers_split.py
python test_prospect_search_split.py
python test_growth_model.py
```

Streamlit health check도 실행하세요.

---

## 12. 완료 보고 형식

완료 후 아래 형식으로 보고하세요.

1. 수정한 코드 파일
2. 새로 만든 코드 파일
3. 수정한 MD 파일
4. 추가한 문서 섹션명
5. 저장/조회 UI 개선 내용
6. payload helper 보강 내용
7. legacy fallback 검증 내용
8. 실제 DB INSERT 테스트 수행 여부
9. 사용자가 직접 확인할 수동 검수 체크리스트
10. 테스트 결과
11. Streamlit health check 결과
12. 남은 문제
