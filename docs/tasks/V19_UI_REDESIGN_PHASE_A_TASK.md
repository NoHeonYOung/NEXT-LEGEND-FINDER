# V19_UI_REDESIGN_PHASE_A_TASK.md

## 0. 작업 목적

이 프로젝트는 `c:\Users\nhy81\Desktop\Database_Project`의 NEXT-LEGEND FINDER Streamlit + Supabase 기반 축구 유망주 스카우팅 웹앱이다.

현재 기능적으로는 v19 Phase 1~2까지 진행되어 Scouting Board, Player Dossier, Data Coverage Panel이 정리되었지만, UI가 여전히 기본 Streamlit 대시보드처럼 보인다.

이번 작업의 목표는 기존 기능과 데이터 로직을 유지하면서, 앱의 시각적 구조를 Football Manager에서 영감을 받은 “어두운 스포츠 매니지먼트 게임풍 스카우팅 센터 UI”로 리팩토링하는 것이다.

중요:
Football Manager의 로고, 이미지, 고유 에셋, 고유 UI를 복제하지 않는다.
독자적인 다크 네이비 기반 스포츠 스카우팅 UI를 만든다.

---

## 1. 이번 작업 범위

이번 작업은 v19 UI Redesign Phase A이다.

이번 Phase에서 구현할 것:

1. 공통 디자인 시스템 생성
2. 공통 CSS / theme 분리
3. 좌측 고정형 네비게이션 UI 준비
4. 상단 선택 선수 헤더 UI 개선
5. 공통 카드 / 패널 / badge / progress bar / stat row 컴포넌트 생성
6. Scouting Board 화면을 커스텀 카드형 UI로 개선
7. Player Dossier 화면을 선수 프로필/스카우팅 리포트형 UI로 개선
8. 기존 데이터 로직, Supabase 연결, 검색/선택/session_state/Growth/Gemini/Notes 흐름 유지
9. 문서 최신화
10. 테스트 실행

이번 Phase에서 하지 않을 것:

* Style & Mentor Lab 전체 개편
* Career Simulation 전체 개편
* Evidence & Advisory Report 전체 개편
* Notes 전체 개편
* Gemini 기능 변경
* Growth/Ceiling 공식 변경
* DB 스키마 변경
* 원본 CSV 변경

나머지 화면은 이번 Phase에서 공통 디자인 시스템과 충돌하지 않게 유지한다.
다음 Phase에서 순차적으로 같은 디자인 시스템을 적용할 예정이다.

---

## 2. 현재 문제

현재 앱은 기능은 많지만 다음 문제가 있다.

1. 기본 Streamlit 대시보드처럼 보인다.
2. `st.metric`, `st.dataframe`, `st.tabs`, `st.sidebar` 중심의 UI 느낌이 강하다.
3. 박스와 색상은 조금 들어갔지만 스포츠 매니지먼트 게임 UI처럼 보이지 않는다.
4. 화면별 정보 구조가 카드/패널/스카우팅 리포트처럼 느껴지지 않는다.
5. Scouting Board와 Player Dossier가 아직 “게임 속 스카우팅 센터”처럼 보이지 않는다.
6. 정보 밀도는 있지만 시각적 계층 구조가 약하다.
7. 선택 선수 헤더, 분석 준비도 badge, 능력치 패널, 리포트 패널이 하나의 디자인 시스템으로 통일되어 있지 않다.

이번 작업은 단순 색상 변경이 아니다.
레이아웃과 컴포넌트 구조를 재설계한다.

---

## 3. 디자인 목표

목표 UI는 다음과 같다.

어두운 스포츠 매니지먼트 게임풍 스카우팅 센터

시각 톤:

* 다크 네이비 배경
* 패널형 카드
* 얇은 border
* 높은 정보 밀도
* 작은 글씨
* hover 효과
* 선택된 카드 강조
* 등급 badge
* 능력치 progress bar
* 리포트 패널
* 좌측 고정 네비게이션
* 상단 선수 헤더
* 중앙 분석 영역
* 우측 attribute/risk panel

참고 감성:

* Football Manager식 정보 밀도
* 스카우팅 센터
* 선수 프로필
* 전술/분석 리포트 화면
* 스포츠 데이터 cockpit

주의:
Football Manager의 실제 로고, 고유 색상 조합, 고유 이미지, 고유 UI 에셋을 복제하지 말 것.
영감을 받은 독자적 UI로 구현할 것.

---

## 4. 기본 원칙

반드시 지킬 것:

1. 기존 데이터 로직 유지

   * Supabase 연결 유지
   * 선수 검색 기능 유지
   * selected_player / selected_profile / selected_entity_type session_state 유지
   * Growth/Ceiling/Gemini/Notes 기존 흐름 유지

2. app.py 비대화 금지

   * app.py에 대량 HTML/CSS를 직접 넣지 말 것
   * UI 관련 코드는 `components/`와 `styles/`로 분리

3. 기본 Streamlit UI 느낌 최소화

   * `st.metric`, `st.dataframe`, `st.tabs`, `st.sidebar`를 메인 시각 UI처럼 쓰지 말 것
   * 필요한 경우 내부 동작용으로는 Streamlit 위젯 사용 가능
   * 사용자에게 보이는 핵심 레이아웃은 HTML/CSS 기반 custom card/panel/grid 중심으로 구현

4. HTML/CSS 기반 커스텀 UI 사용

   * `st.markdown(..., unsafe_allow_html=True)` 기반 렌더링 가능
   * CSS는 별도 파일 또는 style loader로 분리
   * 컴포넌트는 재사용 가능한 함수로 분리

5. 기능 제거 금지

   * 기존 화면 기능을 없애지 말 것
   * 이번 Phase에서 바꾸는 화면은 Scouting Board와 Player Dossier 중심
   * 나머지 화면은 깨지지 않게 유지

6. 문서 최신화 필수

   * 작업 후 문서에 v19 UI Redesign Phase A 기록

---

## 5. 권장 폴더 구조

다음 구조를 권장한다. 기존 구조와 충돌하지 않게 만든다.

```text
components/
  __init__.py
  layout.py
  cards.py
  badges.py
  player_header.py
  attribute_panels.py

styles/
  __init__.py
  theme.py
  game_ui.css
```

역할 예시:

`styles/game_ui.css`

* 전체 다크 테마
* shell layout
* left nav
* top player header
* card
* panel
* badge
* progress bar
* hover state
* selected state

`styles/theme.py`

* CSS 로드 함수
* 공통 색상 변수 문자열
* 필요 시 inject 함수

`components/layout.py`

* 앱 셸 구조
* 좌측 네비게이션 렌더링
* page title section
* section grid wrapper

`components/cards.py`

* scout card
* summary card
* report panel
* strength/weakness card
* selected player card

`components/badges.py`

* Full / Partial / Limited / Manual badge
* risk badge
* rating badge
* data source badge

`components/player_header.py`

* 선택 선수 상단 헤더
* 이름, 나이, 포지션, 팀, 국적, 시장가치, coverage badge 표시

`components/attribute_panels.py`

* 능력치 progress bar
* Physical / Technical / Mental 그룹
* risk panel
* training recommendation panel

주의:
구조는 권장안이다. 기존 코드와 더 잘 맞는 구조가 있으면 최소 변경으로 조정 가능하다.
하지만 UI 관련 코드가 app.py와 views 파일에 무분별하게 길게 들어가면 안 된다.

---

## 6. 공통 앱 셸 요구사항

### 6.1 좌측 고정 네비게이션

목표:
기본 Streamlit sidebar 느낌을 줄이고, 게임 UI 같은 좌측 고정 navigation rail을 만든다.

표시 메뉴:

* Home
* Scouting Board
* Player Dossier
* Style & Mentor Lab
* Career Simulation
* Evidence & Advisory Report
* Notes
* Manual Prospect
* DB Status

요구사항:

* 현재 선택된 메뉴 강조
* hover 효과
* 작은 설명 텍스트 또는 icon-like marker 허용
* Streamlit 기본 sidebar처럼 보이지 않게 할 것
* 내부 nav key는 기존 구조를 깨지 않는 선에서 유지 가능
* 내부 key 변경이 위험하면 label만 변경

주의:
Streamlit 특성상 버튼 자체는 Streamlit 위젯을 사용할 수 있다.
다만 최종 화면이 기본 sidebar처럼 보이면 안 된다.
가능하면 CSS로 nav 버튼 느낌을 통일한다.

---

### 6.2 상단 선택 선수 헤더

모든 주요 분석 화면 상단에 같은 스타일의 선수 헤더를 표시할 수 있게 공통 컴포넌트화한다.

표시 정보:

* 선수 이름
* 포지션
* 나이
* 소속팀
* 국적
* 현재 시장가치
* 분석 준비도 badge
* 데이터 모드
* Full / Partial / Limited / Manual 상태
* 선택된 선수 없음 상태도 처리

디자인:

* 어두운 카드형 horizontal header
* 좌측에 initials/avatar placeholder
* 중앙에 이름/팀/포지션
* 우측에 시장가치/나이/coverage badge
* 얇은 border
* hover는 필요 없음
* 페이지 상단에서 앱의 기준점을 잡아주는 역할

---

## 7. 공통 컴포넌트 요구사항

다음 컴포넌트를 재사용 가능하게 만든다.

### 7.1 Panel Card

용도:

* 주요 섹션 카드
* 리포트 박스
* 선수 요약
* 능력치 영역

필수 스타일:

* dark navy background
* subtle border
* border radius
* compact padding
* title + subtitle
* optional footer

---

### 7.2 Scout Card

용도:

* Scouting Board 선수 결과 카드
* 유사 선수 후보 카드
* 멘토 후보 카드

필수 정보:

* 이름
* 포지션
* 나이
* 팀
* 국적
* 시장가치
* coverage badge
* 핵심 설명 1줄
* missing reason
* CTA 영역

스타일:

* hover 효과
* 선택된 선수 강조
* Limited 선수는 색상/아이콘으로 제한 상태 표시

---

### 7.3 Badge

종류:

* Full
* Partial
* Limited
* Manual
* DB
* FM Proxy
* Gemini
* Rule-based
* Risk Low / Medium / High

색상 원칙:

* Full: 긍정
* Partial: 주의
* Limited: 경고
* Manual: 중립/보라 계열
* Gemini: 별도 강조색
* Rule-based: 차분한 정보색

---

### 7.4 Attribute Bar

용도:

* 피지컬/기술/멘탈 능력치 표시
* 데이터 기반 점수 표시
* 리스크 레벨 표시

형태:

* label
* numeric value 또는 grade
* horizontal progress bar
* small note

주의:
실제 데이터가 없으면 “데이터 없음”을 명확히 표시한다.
값을 임의로 만들지 않는다.

---

### 7.5 Report Panel

용도:

* AI/Gemini 리포트가 아니라도 모든 리포트형 텍스트 표시
* Growth Insight
* Player Identity
* Scouting Summary

구성:

* 제목
* short verdict
* bullet-like compact rows
* evidence/source badge
* limitation note

---

## 8. Scouting Board UI 개선 요구사항

대상 파일:

* `views/prospect_search.py`
* 필요 시 `services/db.py`
* 필요 시 `ui_components.py`
* 새 components 파일

목표:
Scouting Board를 기본 Streamlit 검색 폼처럼 보이지 않게 하고, 스카우팅 리스트/보드처럼 보이게 한다.

### 8.1 화면 구조

상단:

* Page title: Scouting Board
* subtitle: “분석 가능한 유망주를 찾고, 데이터 준비도를 확인하세요.”
* compact filter panel

중앙:

* 선수 카드 grid
* Full / Partial 우선
* Limited는 기본 제외

우측 또는 상단 summary:

* 전체 후보 수
* Full 수
* Partial 수
* Limited 수
* 현재 필터 요약

필터:

* 이름
* 포지션
* 나이 범위
* 분석 가능한 유망주만 보기
* 전체 DB 선수 포함
* Limited 포함
* FM profile 있음
* style_vector 있음

주의:
필터 자체는 Streamlit 입력 위젯을 써도 된다.
다만 결과 표시와 전체 레이아웃은 기본 Streamlit 느낌이 아니라 custom card/grid 느낌이어야 한다.

---

### 8.2 선수 카드

각 선수는 카드로 표시한다.

표시 정보:

* 이름
* 포지션
* 나이
* 팀
* 국적
* 현재 시장가치
* coverage badge
* FM profile 여부
* style_vector 여부
* 데이터 부족 이유
* 추천/후보 이유 한 줄

CTA:

* Analyze / 이 선수 분석하기
* Coverage / 데이터 커버리지 보기

Limited 선수인 경우:

* Limited badge
* “FM profile 또는 style_vector가 없어 정밀 분석이 제한됩니다.”
* “직접 입력 유망주로 보완하기”
* “분석 가능한 선수 다시 검색하기”

---

## 9. Player Dossier UI 개선 요구사항

대상 파일:

* `views/dashboard.py`
* `ui_components.py`
* `player_coverage.py`
* 새 components 파일

목표:
기존 Dashboard를 Player Dossier, 즉 선수 분석 허브처럼 보이게 만든다.

### 9.1 화면 구조

상단:

* 공통 선수 헤더

메인 레이아웃:

* 좌/중앙 main content
* 우측 attribute/risk panel

추천 배치:

```text
[Top Player Header]

[Left/Main 70%]                         [Right 30%]
- Player Summary Panel                  - Physical / Technical / Mental
- Data Coverage Panel                   - Risk Assessment
- Growth Insight Report                 - Training Direction
- Player Identity                       - Data Source Badges
- Next Action Panel
```

Streamlit columns를 내부 배치에 사용할 수는 있다.
다만 패널 자체는 custom HTML/CSS card로 보여야 한다.

---

### 9.2 Player Summary Panel

표시 정보:

* 선수 핵심 요약
* 나이/포지션/팀/국적
* 시장가치
* 데이터 모드
* coverage badge
* 현재 분석 상태

---

### 9.3 Data Coverage Panel

`build_data_coverage()` 기반으로 표시한다.

표시 항목:

* 선수 기본정보
* 나이
* 시장가치 데이터
* 출전 기록
* FM profile
* style_vector
* FM 멘탈 속성 proxy
* 정성 텍스트 분석
* Gemini 보조 추천

디자인:

* check / warning / missing row
* compact grid
* 자세한 missing reason은 expander 또는 small note

---

### 9.4 Growth Insight Report Panel

기존 Growth 로직을 유지한다.

표시:

* Growth Score
* 구성 요소별 설명
* 데이터 기반 성장 여지
* 제한 분석 warning
* 25세 이상이면 “유망주 잠재력”이 아니라 “현재 데이터 기반 성장 여지” 표현 사용

주의:
점수 계산식은 바꾸지 않는다.
표현과 UI만 바꾼다.

---

### 9.5 Player Identity Panel

FM profile이 있는 경우:

* 포지션/역할 요약
* 주요 강점
* 약점/보완점
* FM proxy 기반 멘탈 요약
* style_vector 기반 플레이스타일 요약

FM profile이 없는 경우:

* unavailable 텍스트만 던지지 않는다.
* 제한 분석 안내를 카드로 표시한다.
* 직접 입력 유망주 보완 CTA를 제공한다.

---

### 9.6 Right Attribute Panel

우측 패널에는 다음을 표시한다.

* 피지컬 능력치
* 기술 능력치
* 멘탈 능력치
* progress bar 또는 grade badge
* 리스크 평가
* 추천 훈련 방향

주의:
데이터가 없으면 임의 값을 만들지 말고 “데이터 없음”으로 표시한다.

---

### 9.7 Next Action Panel

표시 CTA:

* Style & Mentor Lab으로 이동
* Career Simulation으로 이동
* Evidence & Advisory Report로 이동
* Notes로 이동

Limited 선수 CTA:

* 직접 입력 유망주로 보완하기
* 분석 가능한 선수 다시 검색하기

CTA는 게임 메뉴처럼 카드형 버튼으로 보여준다.

---

## 10. Styling 요구사항

CSS에서 다음을 구현한다.

색상 예시:

* background: #07111f 또는 유사 dark navy
* panel: #0d1b2e
* panel elevated: #12243a
* border: rgba(255,255,255,0.08)
* text main: #e7eef8
* text muted: #8ea0b8
* accent: teal/cyan/green 계열
* warning: amber 계열
* danger: red 계열

디자인:

* border-radius 12~18px
* thin border
* compact padding
* small font-size
* uppercase label
* hover transform 또는 border glow
* selected card highlight
* progress bar
* badge

주의:

* 너무 밝은 색 금지
* 과도한 애니메이션 금지
* 기본 Streamlit 흰 배경이 보이면 안 됨
* 앱 전체 배경을 통일

---

## 11. 기능 보존 요구사항

반드시 보존:

* Supabase DB 연결
* 검색 기능
* 선수 선택 기능
* session_state 흐름
* Growth Insight 계산
* Ceiling 관련 state
* Gemini 관련 state
* Notes 저장/조회
* Manual Prospect 흐름
* Existing legacy fallback

선수 변경 시 stale state 초기화 흐름 유지:

* growth
* ceiling
* report
* qualitative_signals
* gemini_advisory

---

## 12. 테스트 요구사항

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

## 13. 문서 업데이트

작업 후 아래 문서를 업데이트한다.

* `CLAUDE_PROGRESS_SUMMARY.md`
* `ACTIVE_FUNCTION_MAP.md`
* `REAL_MODEL_PLAN.md`
* `AGENTS.md`

섹션명:

```text
v19 UI Redesign Phase A: Game-style shell, Scouting Board, and Player Dossier
```

문서에 포함:

* 새 components/ 구조
* 새 styles/ 구조
* 공통 디자인 시스템
* Scouting Board UI 변경
* Player Dossier UI 변경
* 기존 기능 보존 내용
* 아직 개편하지 않은 화면

주의:
`CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않는다.

---

## 14. 절대 금지

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
* UI 작업 범위를 전 화면으로 무리하게 확대 금지
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md` 수정 금지

---

## 15. 완료 보고 형식

완료 후 아래 형식으로 보고한다.

1. 수정한 코드 파일
2. 새로 만든 코드 파일
3. 수정한 문서 파일
4. 새 components/ 구조
5. 새 styles/ 구조
6. 공통 디자인 시스템 요약
7. Scouting Board UI 변경 내용
8. Player Dossier UI 변경 내용
9. 기본 Streamlit UI 느낌을 줄이기 위해 한 작업
10. 기존 기능 보존 여부
11. session_state 영향 여부
12. 테스트 결과
13. Streamlit health check 결과
14. 사용자가 직접 확인해야 할 화면
15. 아직 개편하지 않은 화면
16. 남은 문제
