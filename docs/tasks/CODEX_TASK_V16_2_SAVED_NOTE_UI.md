# CODEX_TASK_V16_2_SAVED_NOTE_UI.md

## 작업 목표

이 프로젝트는 `c:\Users\nhy81\Desktop\Database_Project`의 NEXT-LEGEND FINDER Streamlit + Supabase 프로젝트입니다.

현재 상태:

* v16: Scouting Notes structured persistence 구현 완료
* v16.1: Persistence QA and saved-note UI polish 구현 완료
* 실제 Streamlit 화면에서 AI Report 저장 노트가 My Scouting Notes에 표시되는 것을 확인함
* Growth Score / Final Growth Score / 저장된 규칙 리포트가 복원됨

현재 문제:

1. Gemini API를 아직 사용하지 않는데 “AI 리포트”라는 표현이 너무 강하게 노출되어 사용자가 실제 AI 생성 리포트로 오해할 수 있음
2. 저장된 노트 화면에서 기존 템플릿 리포트와 규칙 기반 코칭 리포트가 중복으로 보임
3. 핵심인 “저장된 규칙 리포트”가 너무 아래에 배치됨
4. “AI 스카우팅 리포트 초안” 영역의 글자가 너무 어둡고 가독성이 낮음
5. 선택된 멘토가 없을 때 “선택된 멘토 없음”이 불필요하게 강조됨
6. 사용자 화면과 개발자용 JSON/상세 payload가 더 명확히 분리되어야 함

이번 작업 목표:
My Scouting Notes의 저장된 노트 조회 화면을 사용자 친화적으로 정리합니다.

문서 최신화가 없으면 작업 완료로 보지 않습니다.

---

## 1. 먼저 읽을 파일

작업 전 아래 파일을 읽으세요.

1. `AGENTS.md`
2. `CLAUDE_PROGRESS_SUMMARY.md`
3. `ACTIVE_FUNCTION_MAP.md`
4. `REAL_MODEL_PLAN.md`
5. `views/scouting_notes.py`
6. `scouting_note_payload.py`
7. `test_growth_model.py`

---

## 2. UI 정리 방향

`views/scouting_notes.py`의 저장된 노트 조회 화면을 다음 구조로 정리하세요.

### 2-1. 카드 상단

표시:

* 선수 이름
* 저장 시각
* note_type/source/entity_type 배지

라벨링 개선:

* `AI 리포트 저장`은 유지 가능하지만, Gemini 미사용 상태가 헷갈리면 다음 중 하나로 변경

  * `리포트 저장`
  * `규칙 기반 리포트`
  * `AI 리포트 준비용 저장`
* 실제 Gemini API를 호출하지 않은 경우에는 “Gemini 생성 리포트”처럼 보이지 않게 할 것

권장:

* 현재는 Gemini API를 호출하지 않으므로 기본 표현은 `규칙 기반 리포트` 또는 `저장된 분석 리포트`가 더 적절함

---

### 2-2. 핵심 점수 요약을 상단에 배치

카드 상단 가까이에 다음 정보를 명확히 표시하세요.

* 기본 성장 점수
* 시나리오 반영 성장 점수
* 부상 리스크

기존처럼 긴 문장 안에 섞지 말고, metric/card 형태로 보기 좋게 표시하는 것을 권장합니다.

---

### 2-3. 저장된 코칭 리포트를 우선 표시

기본 화면에서 가장 먼저 보여야 할 핵심 섹션:

1. 종합 평가
2. 추천 훈련 방향
3. 기대 장점
4. 소홀히 했을 때의 단점
5. 리스크 경고
6. 추천 커리어 전략

이 섹션은 `ceiling_growth_explanation` 또는 구조화된 `growth_explanation`에서 우선 복원하세요.

기존 `gemini_report` 문자열보다 이 코칭 리포트를 먼저 보여주세요.

---

### 2-4. 기존 템플릿 리포트는 expander로 이동

현재 화면의 “리포트 요약 / AI 스카우팅 리포트 초안” 영역은 다음처럼 처리하세요.

* 기본 화면에 길게 노출하지 말 것
* `상세 리포트 원문 보기` expander 안에 넣기
* 글자색이 너무 어둡지 않도록 가독성 개선
* Gemini API 미사용 상태라면 제목을 `저장된 리포트 원문` 또는 `템플릿 리포트 원문`으로 변경

---

### 2-5. 멘토 정보 처리

선택된 멘토가 없는 경우:

* `선택된 멘토 없음`을 굳이 큰 섹션으로 표시하지 말 것
* 필요하면 작은 회색 안내문 또는 생략 처리

선택된 멘토가 있는 경우:

* 멘토 이름
* 멘토 기반 보완 포인트
* 멘토 참고용이라는 설명 표시

---

### 2-6. 개발자용 정보는 expander에 숨기기

아래 정보는 기본 화면에 노출하지 말고 expander 안으로 이동하세요.

* Raw JSON
* env_settings 원본
* simulation_result 원본
* internal key
* note_type/source/entity_type의 원본 JSON 구조

expander 제목 예시:

* `개발자용 저장 데이터 보기`
* `원본 JSON 보기`

---

## 3. Legacy note fallback 유지

중요:
기존 legacy 노트는 깨지면 안 됩니다.

* 구조화된 `growth_insight`가 없는 경우 기존 표시 방식 유지
* 구조화된 `ceiling_growth_explanation`이 없는 경우 `gemini_report` 또는 기존 summary를 fallback으로 표시
* 신규 구조가 없는 노트에서 KeyError가 발생하지 않게 할 것

---

## 4. 테스트 보강

가능하면 `test_growth_model.py`에 다음 테스트를 추가 또는 보강하세요.

1. 저장된 신규 노트에서 코칭 리포트 섹션이 기본 표시 데이터로 추출되는지
2. 기존 `gemini_report`는 원문/상세 리포트 영역으로 분리되는지
3. Gemini API 미사용 상태에서 라벨이 오해를 줄이지 않는지
4. 멘토가 없는 경우 “선택된 멘토 없음”이 과도하게 강조되지 않는지
5. legacy note fallback이 유지되는지

실제 DB INSERT 테스트는 수행하지 마세요.

---

## 5. 문서 최신화 필수

작업 후 아래 문서를 반드시 업데이트하세요.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `ACTIVE_FUNCTION_MAP.md`
3. `REAL_MODEL_PLAN.md`
4. `AGENTS.md`가 필요하면 보강

문서에는 다음 제목으로 기록하세요.

```text
v16.2: Saved note display polish
```

각 문서에 반영할 내용:

* 저장된 노트 화면 표시 순서
* 코칭 리포트 우선 표시 정책
* 템플릿/원문 리포트 expander 이동
* Gemini API 미사용 상태의 라벨링 정책
* legacy fallback 유지
* 개발자용 JSON expander 분리

중요:
문서 최신화가 없으면 작업 완료로 보지 않습니다.
완료 보고에는 반드시 수정한 MD 파일과 추가한 섹션명을 포함하세요.

---

## 6. 테스트 실행

작업 후 반드시 실행하세요.

```bash
python -m compileall .
python test_state_refactor.py
python test_analysis_helpers_split.py
python test_prospect_search_split.py
python test_growth_model.py
```

Streamlit health check도 실행하세요.

---

## 7. 절대 금지

* DB 스키마 변경 금지
* 실제 DB INSERT 테스트 금지
* `create_and_upload_db.py` 수정 금지
* `.streamlit/secrets.toml` 출력/수정 금지
* `.env` 출력/수정 금지
* 원본 CSV 수정 금지
* Gemini API 호출 금지
* 기사 API 구현 금지
* 10x10 Grid 구현 금지
* `app.py` 대형화 금지
* 기존 Growth/Ceiling 공식 변경 금지
* 기존 session_state key 구조 삭제 금지
* 기존 JSONB payload 구조 삭제 금지
* legacy fallback 삭제 금지
* 문서 최신화 누락 금지

---

## 8. 완료 보고 형식

완료 후 아래 형식으로 보고하세요.

1. 수정한 코드 파일
2. 수정한 MD 파일
3. 추가한 문서 섹션명
4. 저장된 노트 화면 표시 순서 변경 내용
5. 코칭 리포트 우선 표시 여부
6. 기존 리포트 원문 expander 이동 여부
7. 라벨링 변경 내용
8. legacy fallback 유지 여부
9. 테스트 결과
10. Streamlit health check 결과
11. 남은 문제
