# V19_UI_REDESIGN_PHASE_B_TASK.md

## 0. 작업 목적

이 프로젝트는 `c:\Users\nhy81\Desktop\Database_Project`의 NEXT-LEGEND FINDER Streamlit + Supabase 기반 축구 유망주 스카우팅 웹앱이다.

현재 v19 UI Redesign Phase A/A.1까지 완료되어 다음이 반영되어 있다.

* `components/` 기반 공통 UI 구조
* `styles/` 기반 dark sports management UI CSS
* Scouting Board UI 개선
* Player Dossier UI 개선
* 공통 player header, badge, card, attribute bar, panel 스타일
* Data Coverage Panel과 Limited 선수 처리 UX 개선

이번 작업은 v19 UI Redesign Phase B이다.

목표:

* Career Simulation 화면을 game-style scenario lab으로 재구성
* Evidence & Advisory Report 화면을 game-style scouting report room으로 재구성
* 기존 Growth/Ceiling 공식과 Gemini 로직은 그대로 유지
* 기존 데이터 로직, session_state, Notes 저장 구조는 유지
* 새 디자인 시스템을 재사용해 기본 Streamlit 느낌을 더 줄임

---

## 1. 이번 작업 범위

이번 Phase에서 구현할 것:

1. Career Simulation UI 개편
2. Evidence & Advisory Report UI 개편
3. 기존 components/styles 디자인 시스템 재사용
4. use_container_width deprecation warning 가능한 범위에서 정리
5. 문서 최신화
6. 테스트 실행

이번 Phase에서 하지 않을 것:

* Style & Mentor Lab 전체 개편
* My Scouting Notes 전체 개편
* Manual Prospect 전체 개편
* DB Status 전체 개편
* DB 스키마 변경
* Growth/Ceiling 공식 변경
* Gemini 분석 로직 변경
* 뉴스 크롤링
* 10x10 Grid 구현

---

## 2. 먼저 읽을 파일

작업 전 아래 파일을 읽는다.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `V19_PRODUCT_REDESIGN_SPEC.md`
3. `AGENTS.md`
4. `ACTIVE_FUNCTION_MAP.md`
5. `REAL_MODEL_PLAN.md`
6. `app.py`
7. `theme.py`
8. `ui_components.py`
9. `player_coverage.py`
10. `components/layout.py`
11. `components/cards.py`
12. `components/badges.py`
13. `components/player_header.py`
14. `components/attribute_panels.py`
15. `styles/theme.py`
16. `styles/game_ui.css`
17. `views/dashboard.py`
18. `views/career_simulation.py`
19. `views/ai_report.py`
20. `scouting_note_payload.py`
21. `services/qualitative_evidence.py`
22. `gemini_client.py`
23. `growth_model.py`
24. `explanation_engine.py`
25. `test_growth_model.py`
26. `test_prospect_search_split.py`

주의:

* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않는다.
* secrets/env/API key 파일은 열람하지 않는다.

---

## 3. 핵심 디자인 방향

이번 작업은 기능 추가가 아니라 UI 구조 개선이다.

기존 Streamlit 기본 느낌을 줄이고, 아래와 같은 스포츠 매니지먼트 게임풍 화면으로 정리한다.

공통 UI 원칙:

* dark navy background
* panel/card layout
* compact typography
* thin border
* badge
* progress bar
* report panel
* scenario result card
* evidence card
* selected player header
* hover 효과
* 높은 정보 밀도

Streamlit 위젯은 내부 입력용으로 사용할 수 있다.
하지만 사용자에게 보이는 주요 결과 영역은 custom HTML/CSS card/panel 중심이어야 한다.

---

# PART A. Career Simulation UI 개편

## 4. Career Simulation 목표

`views/career_simulation.py`를 game-style scenario lab처럼 보이게 정리한다.

현재 기능은 유지한다.

유지해야 할 것:

* Growth baseline 계산
* Ceiling Scenario Adjustment
* Final Growth Score
* 훈련 강도
* 출전 기회
* 리그 수준
* 리스크 성향
* 기존 session_state 저장 흐름
* Notes 저장 흐름
* Growth/Ceiling 공식

절대 변경 금지:

* Growth/Ceiling 공식
* Scenario Adjustment 범위
* Final Growth Score 계산 방식
* 기존 저장 payload key

---

## 5. Career Simulation 화면 구조

권장 구조:

```text
[Top Player Header]

[Scenario Control Panel]      [Simulation Result Panel]
- 훈련 강도                  - Baseline Growth Score
- 출전 기회                  - Scenario Adjustment
- 리그 수준                  - Final Growth Score
- 리스크 성향                - 결과 verdict

[Coaching Recommendation Panel]
- 추천 훈련 방향
- 출전 관리 전략
- 리그 이동/잔류 판단
- 리스크 관리

[Detailed Calculation Expander]
- 기존 계산 근거
- 공식/디버그 정보
```

---

## 6. Career Simulation UI 요구사항

### 6.1 Page Title

화면 제목을 game page title 형태로 표시한다.

예시:

* Career Simulation
* 커리어 성장 시뮬레이션
* “훈련, 출전, 리그 선택에 따른 성장 여지를 시뮬레이션합니다.”

---

### 6.2 Scenario Control Panel

입력 영역을 기본 Streamlit form처럼 보이게 두지 말고, game panel로 감싼다.

표시할 입력:

* 훈련 강도
* 출전 기회
* 리그 수준
* 리스크 성향

요구사항:

* 각 입력값 옆에 짧은 설명 추가
* 선택값이 선수에게 어떤 의미인지 한 줄 설명
* 입력 위젯 자체는 Streamlit 사용 가능
* 주변 UI는 custom panel/card로 구성

---

### 6.3 Simulation Result Panel

결과를 단순 metric 나열로 표시하지 않는다.

표시 정보:

* Baseline Growth Score
* Scenario Adjustment
* Final Growth Score
* 상승/하락 indicator
* 결과 verdict
* 위험 경고

디자인:

* score card
* badge
* progress bar
* delta indicator
* warning panel

---

### 6.4 Coaching Recommendation Panel

기존 explanation_engine / growth explanation을 활용하되, report panel처럼 표시한다.

섹션:

* 추천 훈련 방향
* 출전 관리 전략
* 리그 선택 조언
* 리스크 관리
* 다음 행동 CTA

CTA:

* Evidence & Advisory Report로 이동
* 현재 시뮬레이션 저장
* Notes 보기

---

### 6.5 Limited 선수 처리

Limited 선수 또는 FM profile 없는 선수의 경우:

* 제한 분석 경고를 먼저 보여준다.
* “현재 데이터 기반 성장 여지 분석” 표현을 사용한다.
* FM profile/style_vector 기반 판단은 제한된다고 설명한다.
* Growth/Ceiling 계산이 가능한 범위는 유지하되, 데이터 한계를 명확히 표시한다.

---

# PART B. Evidence & Advisory Report UI 개편

## 7. Evidence & Advisory Report 목표

`views/ai_report.py`를 game-style scouting report room처럼 정리한다.

기존 AI Report 기능은 유지한다.

유지해야 할 것:

* Rule-based report
* Qualitative text input
* Gemini qualitative signal extraction
* Gemini advisory generation
* Final report preview
* Save to Notes
* qualitative_evidence 저장
* gemini_advisory 저장
* report_generation_mode 저장
* Gemini API key 처리 방식

절대 변경 금지:

* Gemini가 Growth/Ceiling 점수를 계산하게 만들지 말 것
* Gemini가 없는 사실을 만들게 하지 말 것
* Gemini 결과가 기존 점수를 덮어쓰게 하지 말 것
* secrets/env/API key 출력 금지

---

## 8. Evidence & Advisory Report 화면 구조

권장 구조:

```text
[Top Player Header]

[Rule-based Report Summary Panel]
- Growth/Ceiling 기반 리포트 초안
- 데이터 출처 badge

[Qualitative Evidence Input Panel]
- 기사/메모/인터뷰 텍스트 입력
- 예시 expander
- Gemini key 상태 안내

[Gemini Signal Extraction Panel]
- 정성 신호 추출 버튼
- 신호 결과 card grid
- evidence quote

[Gemini Advisory Panel]
- 보조 추천 생성 버튼
- 훈련/커리어/리스크/멘토 활용 추천

[Final Report Preview Panel]
- 규칙 기반 분석
- 정성 텍스트 근거
- Gemini 보조 추천
- 근거 부족 항목
- 최종 코멘트

[Save Panel]
- Notes 저장
```

---

## 9. Evidence & Advisory Report UI 요구사항

### 9.1 화면명

사용자 UI에서 “AI Report” 표현을 줄인다.

권장 표시:

* Evidence & Advisory Report
* 근거 기반 스카우팅 리포트
* 스카우팅 분석 리포트

내부 nav key 변경이 위험하면 label/title만 변경한다.

---

### 9.2 Rule-based Report Summary Panel

기존 규칙 기반 리포트 초안을 panel로 표시한다.

표시:

* Growth Score
* Final Growth Score가 있으면 같이 표시
* 리포트 요약
* 데이터 출처 badge
* rule-based badge

주의:

* Gemini 결과와 명확히 분리한다.
* 규칙 기반 분석이 기본이고 Gemini는 보조라는 점을 UI에서 드러낸다.

---

### 9.3 Qualitative Evidence Input Panel

정성 텍스트 입력 영역을 게임풍 evidence panel로 감싼다.

표시:

* 텍스트 입력
* 입력 예시 expander
* 입력 텍스트 길이
* 정성 텍스트가 없으면 “DB/FM proxy 기반 분석만 사용 중” 안내
* Gemini API key 상태 안내

주의:

* secrets 값 출력 금지
* API key 값을 화면에 절대 표시하지 말 것

---

### 9.4 Gemini Signal Extraction Panel

Gemini가 추출한 신호를 카드/grid 형태로 표시한다.

신호:

* playing_time_signal
* injury_risk_signal
* coach_trust_signal
* development_signal
* transfer_rumor_signal
* mentality_signal
* strength_mentions
* weakness_mentions
* risk_mentions
* recommended_focus
* evidence_quotes
* confidence

디자인:

* signal card
* confidence badge
* evidence quote card
* unsupported/unknown은 별도 muted panel

주의:

* 신호가 없으면 빈 데이터 상태를 명확히 표시
* Gemini 호출 실패 시 기본 Streamlit error만 던지지 말고 game alert panel로 표시

---

### 9.5 Gemini Advisory Panel

Gemini advisory 결과를 report panel로 표시한다.

표시:

* advisory_summary
* player_fit_assessment
* training_recommendations
* career_recommendations
* risk_management
* mentor_usage_recommendations
* what_to_monitor_next
* unsupported_or_unknown
* final_scouting_comment
* confidence

주의:

* advisory는 보조 추천임을 명확히 표시
* Growth/Ceiling 점수와 섞지 않는다.
* 최종 리포트에서는 별도 섹션으로 표시한다.

---

### 9.6 Final Report Preview Panel

최종 리포트 미리보기를 카드형으로 표시한다.

구성:

* 규칙 기반 분석
* 정성 텍스트 근거
* Gemini 보조 추천
* 근거 부족 항목
* 최종 스카우팅 코멘트

CTA:

* Notes에 저장
* Career Simulation으로 돌아가기
* Player Dossier로 돌아가기

---

### 9.7 Limited 선수 처리

FM profile 없는 선수:

* 제한 분석 안내 표시
* “FM 능력치/멘탈/style_vector 기반 판단은 제한됩니다.”
* Gemini 정성 텍스트가 있으면 정성 근거 기반 보조 추천은 가능하다고 설명
* 하지만 정량 점수 신뢰도는 제한됨을 표시

---

# PART C. 공통 CSS/컴포넌트 확장

## 10. 추가/개선할 컴포넌트

가능하면 기존 components를 확장한다.

권장 추가/개선:

* scenario card
* score card
* delta badge
* recommendation panel
* evidence input panel
* signal card
* report preview panel
* game alert panel
* CTA card

가능한 위치:

* `components/cards.py`
* `components/badges.py`
* `components/attribute_panels.py`
* `styles/game_ui.css`
* 필요 시 새 파일 `components/reports.py`

주의:

* components가 너무 커지면 기능별로 분리
* app.py에 직접 긴 HTML 넣지 말 것

---

## 11. use_container_width warning 정리

가능한 범위에서 Streamlit deprecation warning을 줄인다.

대상:

* `use_container_width=True`

가능하면:

* `width="stretch"`

주의:

* 모든 파일을 무리하게 바꾸지 말 것
* 동작 깨질 가능성이 있으면 이번 Phase에서 최소 수정
* 테스트 통과 우선

---

## 12. 기능 보존 요구사항

반드시 보존:

* Supabase DB 연결
* 검색 기능
* 선수 선택 기능
* session_state 흐름
* Data Coverage
* Growth Insight 계산
* Ceiling Scenario 계산
* Gemini 정성 신호 추출
* Gemini advisory 생성
* Notes 저장/조회
* Manual Prospect 흐름
* legacy fallback

선수 변경 시 stale state 초기화 흐름 유지:

* growth
* ceiling
* report
* qualitative_signals
* gemini_advisory

---

## 13. 문서 업데이트

작업 후 아래 문서를 업데이트한다.

* `CLAUDE_PROGRESS_SUMMARY.md`
* `ACTIVE_FUNCTION_MAP.md`
* `REAL_MODEL_PLAN.md`
* `AGENTS.md`

섹션명:

```text
v19 UI Redesign Phase B: Career Simulation and Evidence Report styling
```

문서에 포함:

* Career Simulation UI 변경
* Evidence & Advisory Report UI 변경
* Gemini 역할 유지
* Growth/Ceiling 공식 보존
* 새/확장 컴포넌트
* 아직 개편하지 않은 화면
* 수동 확인 화면

주의:

* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않는다.

---

## 14. 테스트 요구사항

작업 후 반드시 실행한다.

```bash
python -m compileall .
python test_state_refactor.py
python test_analysis_helpers_split.py
python test_prospect_search_split.py
python test_growth_model.py
```

Streamlit health check도 실행한다.

---

## 15. 절대 금지

* DB 스키마 변경 금지
* `create_and_upload_db.py` 수정 금지
* `secrets.toml` 내용 출력 금지
* `.env` 내용 출력 금지
* API key 값 출력/저장/문서화 금지
* 원본 CSV 수정 금지
* 뉴스 자동 크롤링 구현 금지
* 10x10 Grid 구현 금지
* Growth/Ceiling 공식 변경 금지
* 기존 JSONB 저장 구조 삭제 금지
* legacy fallback 삭제 금지
* Gemini에게 점수 계산 맡기기 금지
* Gemini가 없는 사실을 지어내게 하기 금지
* app.py 대형화 금지
* Football Manager 고유 로고/이미지/에셋 복제 금지
* UI 작업 범위를 전 화면으로 확대 금지
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md` 수정 금지
* 기존 session_state key 삭제 금지

---

## 16. 완료 보고 형식

완료 후 아래 형식으로 보고한다.

1. 수정한 코드 파일
2. 새로 만든 코드 파일
3. 수정한 문서 파일
4. Career Simulation UI 변경 내용
5. Evidence & Advisory Report UI 변경 내용
6. 새/확장 컴포넌트
7. CSS/theme 변경 내용
8. use_container_width warning 정리 여부
9. 기존 기능 보존 여부
10. session_state 영향 여부
11. 테스트 결과
12. Streamlit health check 결과
13. 사용자가 직접 확인해야 할 화면
14. 아직 개편하지 않은 화면
15. 다음 Phase 추천
16. 남은 문제
