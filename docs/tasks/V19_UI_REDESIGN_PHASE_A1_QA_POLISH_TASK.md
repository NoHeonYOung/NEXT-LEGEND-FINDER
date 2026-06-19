# V19_UI_REDESIGN_PHASE_A1_QA_POLISH_TASK.md

## 0. 작업 목적

이 프로젝트는 `c:\Users\nhy81\Desktop\Database_Project`의 NEXT-LEGEND FINDER Streamlit + Supabase 기반 축구 유망주 스카우팅 웹앱이다.

현재 `v19 UI Redesign Phase A`가 완료되어 다음 작업이 반영되어 있다.

* `components/` 구조 추가
* `styles/` 구조 추가
* `styles/game_ui.css` 추가
* dark sports management UI 스타일 추가
* Scouting Board UI 일부 개선
* Player Dossier UI 일부 개선
* 공통 player header / card / badge / attribute bar 구조 추가

이번 작업은 새로운 화면을 크게 구현하는 것이 아니라, Phase A 결과가 실제로 “기본 Streamlit 대시보드 느낌”에서 벗어나도록 시각적 완성도를 다듬는 QA/Polish 작업이다.

목표:

* Scouting Board와 Player Dossier가 진짜 게임풍 스카우팅 UI처럼 보이도록 정리
* components/styles 구조가 중복되거나 어색하지 않은지 정리
* 기본 Streamlit 느낌이 남아 있는 부분을 줄이기
* 기존 기능과 데이터 로직은 유지
* 아직 Style & Mentor Lab, Career Simulation, Evidence & Advisory Report, Notes 전체 개편은 하지 않음

---

## 1. 이번 작업 범위

이번 작업명:

`v19 UI Redesign Phase A.1: Visual QA and polish for Scouting Board and Player Dossier`

이번 작업에서 할 것:

1. Scouting Board UI polish
2. Player Dossier UI polish
3. components/styles 구조 정리
4. app.py가 비대해지지 않았는지 확인
5. root `theme.py`와 `styles/theme.py` 역할 중복 여부 확인
6. 기본 Streamlit UI 느낌이 남는 부분 최소화
7. CSS 적용 누락/깨짐/배경색 불일치 수정
8. 문서 최신화
9. 테스트 실행

이번 작업에서 하지 않을 것:

* Style & Mentor Lab 전체 개편
* Career Simulation 전체 개편
* Evidence & Advisory Report 전체 개편
* Notes 전체 개편
* DB Status 전체 개편
* Gemini 기능 변경
* Growth/Ceiling 공식 변경
* DB 스키마 변경

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
17. `views/prospect_search.py`
18. `views/dashboard.py`
19. `test_prospect_search_split.py`
20. `test_growth_model.py`

주의:

* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않는다.
* secrets/env/API key 파일은 열람하지 않는다.

---

## 3. 핵심 QA 기준

이번 작업은 기능 추가보다 “화면이 원하는 느낌인지”를 맞추는 작업이다.

다음 기준을 만족해야 한다.

### 3.1 Scouting Board

Scouting Board는 기본 Streamlit 검색 페이지처럼 보이면 안 된다.

확인할 것:

* 화면 제목이 커스텀 game page title처럼 보이는가
* 필터 영역이 기본 Streamlit form 느낌만 남아 있지 않은가
* 선수 결과가 card grid처럼 보이는가
* Full / Partial / Limited badge가 직관적으로 보이는가
* Limited 선수는 기본에서 제외되고, 표시될 때 경고/제한 상태가 명확한가
* 후보 수 summary strip이 게임 UI의 stat strip처럼 보이는가
* 선택된 선수 카드가 시각적으로 강조되는가
* hover 효과가 과하지 않지만 존재하는가
* 전체 배경이 다크 네이비로 통일되어 있는가

수정 방향:

* `st.dataframe` 또는 표 형태가 메인 검색 결과처럼 보이면 카드형으로 대체
* 결과 카드 spacing, border, badge, hover 정리
* 필터 영역은 compact filter panel로 감싸기
* 필터 입력 위젯 자체는 Streamlit이어도 되지만 주변 구조는 custom panel이어야 함

---

### 3.2 Player Dossier

Player Dossier는 단순 Dashboard가 아니라 선수 분석 허브처럼 보여야 한다.

확인할 것:

* 상단 player header가 눈에 잘 들어오는가
* 이름/나이/포지션/팀/시장가치/coverage badge가 한눈에 보이는가
* Data Coverage Panel이 너무 개발자용 dump처럼 보이지 않는가
* Growth Insight가 report panel처럼 보이는가
* Player Identity가 실제 스카우팅 리포트 섹션처럼 보이는가
* 우측 attribute panel이 능력치 패널처럼 보이는가
* progress bar가 제대로 렌더링되는가
* FM profile 없는 선수는 unavailable 텍스트만 나오지 않고 제한 분석 카드가 먼저 보이는가
* Next Action Panel이 게임 메뉴 CTA처럼 보이는가

수정 방향:

* 기본 `st.metric` 느낌이 남아 있으면 custom stat tile로 대체
* 기본 표/탭 느낌이 강하면 panel/card 구조로 감싸기
* `st.tabs`가 메인 UI로 사용되고 있으면 가능하면 section/panel 기반으로 정리
* 상세 계산 근거는 expander에 두되, 메인 화면에는 요약 중심으로 표시

---

### 3.3 공통 디자인 시스템

확인할 것:

* `components/`와 `styles/`가 실제로 재사용 가능한 구조인가
* 동일한 badge/card/header 스타일이 중복 구현되어 있지 않은가
* `theme.py`와 `styles/theme.py` 역할이 혼란스럽지 않은가
* CSS 로더가 중복 호출되더라도 깨지지 않는가
* app.py에 긴 CSS/HTML이 들어가 있지 않은가
* CSS class 이름이 너무 일반적이라 Streamlit 내부와 충돌하지 않는가

정리 방향:

* app.py에는 최소한의 layout/bootstrap만 둔다.
* 공통 UI 함수는 components 또는 ui_components에 둔다.
* CSS는 styles/game_ui.css 중심으로 둔다.
* root `theme.py`가 기존 프로젝트에서 쓰이는 파일이면 깨지지 않게 유지하되, 역할이 겹치면 주석/문서로 정리한다.
* 새 UI 관련 CSS는 가능한 `styles/` 아래에 둔다.

---

## 4. 구체 작업 요구사항

### 4.1 Scouting Board polish

대상:

* `views/prospect_search.py`
* `components/cards.py`
* `components/badges.py`
* `components/layout.py`
* `styles/game_ui.css`

작업:

* 후보 카드의 시각 계층 정리
* 선택 선수 카드 강조
* coverage badge 색상/크기 정리
* candidate reason / missing reason 표시 방식 개선
* Limited 선수 카드 경고 스타일 개선
* filter panel과 result grid 간격 정리
* summary stat strip 디자인 정리

주의:

* 검색/필터 로직 변경은 최소화
* v19 Phase 1~2에서 만든 분석 가능 선수 기본 필터 정책 유지
* Bo-kyung Kim 같은 Limited 선수는 기본 결과에서 제외되어야 함

---

### 4.2 Player Dossier polish

대상:

* `views/dashboard.py`
* `ui_components.py`
* `components/player_header.py`
* `components/attribute_panels.py`
* `components/cards.py`
* `styles/game_ui.css`

작업:

* 상단 player header 디자인 정리
* Data Coverage Panel을 compact game panel로 정리
* Growth Insight를 report panel로 보이게 정리
* Player Identity를 scouting report card처럼 정리
* 우측 attribute panel의 progress bar 정리
* Limited 선수 안내 card 정리
* Next Action CTA 버튼/카드 정리

주의:

* Growth/Ceiling 계산 로직 변경 금지
* session_state 변경 금지
* Gemini/Notes 흐름 변경 금지

---

### 4.3 CSS / theme 정리

대상:

* `theme.py`
* `styles/theme.py`
* `styles/game_ui.css`
* `app.py`

작업:

* CSS 로딩 위치와 책임 정리
* 중복 theme 함수가 있다면 역할을 명확히 주석 처리
* app.py에 긴 style block이 있으면 styles로 이동
* Streamlit 기본 흰 배경이 보이지 않도록 전체 배경 통일
* sidebar/nav radio/button이 최대한 game nav처럼 보이게 정리

주의:

* 기존 import 경로 깨뜨리지 말 것
* 기존 theme.py를 삭제하지 말 것
* 모듈 import 순환 만들지 말 것

---

## 5. 수동 확인용 기준을 문서에 남기기

작업 후 문서에 사용자가 직접 봐야 할 화면 체크리스트를 남긴다.

체크리스트:

1. Scouting Board 기본 화면
2. Scouting Board Limited 포함 화면
3. FM profile 있는 선수의 Player Dossier
4. FM profile 없는 Limited 선수의 Player Dossier
5. 기존 Career Simulation 진입
6. 기존 Evidence/AI Report 진입
7. 기존 Notes 진입

---

## 6. 문서 업데이트

작업 후 아래 문서를 업데이트한다.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `ACTIVE_FUNCTION_MAP.md`
3. `REAL_MODEL_PLAN.md`
4. `AGENTS.md`

섹션명:

`v19 UI Redesign Phase A.1: Visual QA and polish`

문서에 포함:

* Scouting Board polish 내용
* Player Dossier polish 내용
* CSS/theme 정리 내용
* 사용자가 직접 확인해야 할 화면
* 아직 개편하지 않은 화면
* 다음 Phase 후보

주의:

* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않는다.

---

## 7. 테스트 요구사항

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

## 8. 절대 금지

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

## 9. 완료 보고 형식

완료 후 아래 형식으로 보고한다.

1. 수정한 코드 파일
2. 수정한 문서 파일
3. Scouting Board polish 내용
4. Player Dossier polish 내용
5. CSS/theme 정리 내용
6. app.py 비대화 여부
7. 기존 기능 보존 여부
8. session_state 영향 여부
9. 테스트 결과
10. Streamlit health check 결과
11. 사용자가 직접 확인해야 할 화면
12. 아직 개편하지 않은 화면
13. 다음 Phase 추천
14. 남은 문제
