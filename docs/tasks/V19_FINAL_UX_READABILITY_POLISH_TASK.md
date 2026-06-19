# V19_FINAL_UX_READABILITY_POLISH_TASK.md

## 0. 작업 목적

이 프로젝트는 `c:\Users\nhy81\Desktop\Database_Project`의 NEXT-LEGEND FINDER Streamlit + Supabase 기반 축구 유망주 스카우팅 웹앱이다.

현재 v19 UI Redesign, Final Polish, Folder Organization까지 완료되었고 기능 개발은 거의 끝났다.

사용자가 실제 브라우저 캡처를 확인한 결과, 기능은 동작하지만 최종 제출/사용자 관점에서 다음 문제가 확인되었다.

1. 전체적으로 글자 크기가 너무 작아 가독성이 낮다.
2. 다크 UI인데 일부 차트/그래프가 흰색 배경으로 표시되어 디자인이 깨진다.
3. 사용자 화면에 `proxy`, `style_vector`, `10x10 Grid`, `pgvector`, `attributes_jsonb` 같은 개발자용 표현이 직접 노출된다.
4. 멘토/유사 선수/강점/약점 설명이 너무 길고 빽빽하여 핵심 정보가 한눈에 들어오지 않는다.
5. 사용자는 내부 구현 방식보다 “그래서 이 선수가 어떤 유형이고, 무엇이 강점이며, 무엇을 보완해야 하는지”를 알고 싶어 한다.

이번 작업은 새로운 기능 추가가 아니라 최종 UX 가독성 개선 작업이다.

목표:

* 글자 크기와 줄 간격을 키워 읽기 쉽게 만들기
* 사용자 화면에서 개발자용 용어 제거
* 다크 UI와 맞지 않는 흰색 차트/그래프 개선
* 설명 텍스트를 사용자 친화적인 스카우팅 문장으로 바꾸기
* 상세 기술 근거는 developer/debug expander 안으로 이동
* 기존 기능, 계산식, DB 로직, session_state는 유지

---

## 1. 작업 전 확인

먼저 현재 상태를 확인한다.

```bash id="ud7fhp"
git status
```

주의:

* 기존 변경사항을 임의로 되돌리지 않는다.
* 기능 추가하지 않는다.
* DB 스키마, Growth/Ceiling 공식, Gemini 로직은 변경하지 않는다.
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않는다.
* `.env`, `.streamlit/secrets.toml`, API key 파일은 열람하거나 출력하지 않는다.

---

## 2. 먼저 읽을 파일

아래 파일을 읽고 현재 UI 구조를 파악한다.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `AGENTS.md`
3. `ACTIVE_FUNCTION_MAP.md`
4. `REAL_MODEL_PLAN.md`
5. `CLEANUP_AUDIT_REPORT.md`
6. `FOLDER_ORGANIZATION_REPORT.md`
7. `app.py`
8. `theme.py`
9. `ui_components.py`
10. `components/cards.py`
11. `components/badges.py`
12. `components/player_header.py`
13. `components/attribute_panels.py`
14. `styles/theme.py`
15. `styles/game_ui.css`
16. `views/prospect_search.py`
17. `views/dashboard.py`
18. `views/legend_matching.py`
19. `views/career_simulation.py`
20. `views/ai_report.py`
21. `views/scouting_notes.py`
22. `views/manual_prospect.py`
23. `explanation_engine.py`
24. `analysis_helpers.py`

---

# PART A. 전체 가독성 개선

## 3. 글자 크기 / 줄 간격 개선

현재 캡처에서 전반적으로 글자가 너무 작게 보인다.

`styles/game_ui.css`를 중심으로 전체 typography scale을 조정한다.

권장 기준:

```css id="mfrawy"
body, .stApp {
  font-size: 15px;
  line-height: 1.55;
}

.game-page-title h1,
.game-title,
h1 {
  font-size: 28px;
}

h2 {
  font-size: 22px;
}

h3 {
  font-size: 18px;
}

.game-card,
.game-panel,
.game-scout-card,
.game-mentor-card,
.game-note-card {
  font-size: 15px;
  line-height: 1.55;
}

.game-meta,
.game-muted,
.game-caption {
  font-size: 13px;
}

.game-badge {
  font-size: 12px;
}
```

실제 class 이름은 현재 CSS 구조에 맞춰 적용한다.

목표:

* 기본 본문은 최소 14~15px
* 카드 본문은 최소 14~15px
* 설명 문단 line-height 1.5 이상
* 버튼 글자는 너무 작지 않게 조정
* badge는 작아도 읽을 수 있게 조정
* 모바일 대응보다는 데스크톱 발표/보고서 캡처 가독성을 우선

주의:

* 화면이 너무 커져서 카드가 과하게 늘어나면 안 된다.
* 정보 밀도는 유지하되 읽을 수 있게 만든다.

---

## 4. 버튼 / 네비게이션 가독성 개선

현재 좌측 네비게이션과 상단 네비게이션이 작게 보인다.

개선:

* 좌측 nav item font-size 상향
* 상단 nav button font-size 상향
* active 상태 contrast 강화
* 버튼 높이 약간 증가
* 버튼 텍스트가 중앙 정렬되도록 유지

주의:

* 네비게이션 구조 자체는 변경하지 않는다.
* 현재 동작하는 route/session_state 로직은 유지한다.

---

# PART B. 개발자용 표현 제거

## 5. 사용자 화면에서 숨길 개발자용 표현

아래 표현은 사용자 메인 화면에 직접 노출하지 않는다.

사용자 메인 화면에서 제거 또는 순화할 표현:

* `proxy`
* `FM proxy`
* `style_vector`
* `pgvector`
* `10x10 Grid`
* `attributes_jsonb`
* `mentality_jsonb`
* `JSONB`
* `vector`
* `cosine similarity`
* `DB schema`
* `fallback`
* `gating`
* `unavailable`

대체 표현:

* `FM proxy` → `능력치 기반 분석`
* `style_vector` → `플레이스타일 유사도`
* `pgvector` → `유사도 검색`
* `attributes_jsonb` → `능력치 데이터`
* `mentality_jsonb` → `멘탈/성향 데이터`
* `10x10 Grid 반영 안됨` → 사용자 화면에서는 표시하지 않음
* `fallback` → `대체 기준`
* `gating` → `분석 가능 여부 확인`
* `unavailable` → `현재 데이터 없음`

중요:

* 개발자용 상세 표현은 삭제하지 말고 “개발자용 상세 보기”, “데이터 근거 상세 보기”, “분석 기준 상세 보기” expander 안으로 이동한다.
* 일반 사용자 화면에는 “왜 유사한지”, “무엇을 배울 수 있는지”, “무엇을 보완해야 하는지”만 보여준다.

---

## 6. 사용자 친화 문장 원칙

설명 문장은 아래처럼 바꾼다.

나쁜 예:

```text id="mknjb9"
FM proxy 능력치 공통 강점: 감정 조절, 가속도, 주력. 근거: FM attributes_jsonb 기반 유사도 계산. 유사성: style_vector는 실제 위치 이벤트 데이터가 아닌 FM proxy 추정값입니다.
```

좋은 예:

```text id="yoo2rd"
공통 강점: 빠른 스피드와 순간적인 움직임을 바탕으로 공격 전환 상황에서 장점을 보일 수 있습니다.

해석: 이 선수는 정적인 빌드업보다는 빠르게 공간을 파고들거나, 측면에서 속도를 활용하는 상황에서 더 잘 맞는 유형으로 보입니다.

확인할 부분: 실제 경기 데이터가 충분하지 않기 때문에, 강한 압박을 받는 상황에서의 판단 속도와 마무리 선택은 추가 확인이 필요합니다.
```

개발자용 근거는 expander 안에서만 표시:

```text id="ntk9uh"
분석 기준 상세:
- 능력치 데이터 기반
- 플레이스타일 유사도 기반
- 실제 위치 이벤트 데이터는 사용하지 않음
```

---

# PART C. Player Dossier 개선

## 7. Player Dossier 흰색 차트 문제 해결

현재 Player Dossier에서 일부 bar chart가 흰색 배경으로 표시되어 dark UI와 어울리지 않는다.

대상:

* `views/dashboard.py`
* `components/attribute_panels.py`
* `ui_components.py`
* `styles/game_ui.css`

개선 방향 중 하나를 선택한다.

1. Altair/Matplotlib 차트의 배경, axis, label 색상을 dark theme에 맞게 조정
2. 차트 대신 기존 CSS 기반 progress bar / score bar로 대체
3. 차트를 유지하되 dark panel 안에서 배경이 흰색으로 보이지 않게 설정

권장:

* 최종 제출 안정성을 위해 가능하면 CSS progress bar 방식으로 대체한다.
* 흰색 차트 영역이 남지 않게 한다.

유지해야 할 정보:

* 공격 능력
* 패스/창의성
* 피지컬
* 멘탈/활동량
* 수비 능력
* 멘탈 종합
* 각 세부 능력치

주의:

* 점수 계산 방식 변경 금지
* 시각화 방식만 변경

---

## 8. Player Dossier 설명 정리

현재 설명이 너무 작고, 일부 문장이 개발자용이다.

개선:

* 강점/보완점/추천 성장 방향 카드를 더 읽기 쉽게 조정
* 각 카드에 다음 구조를 적용

```text id="g7vnfq"
핵심 요약
근거
스카우팅 해석
추천 방향
```

단, 화면에 모든 항목을 너무 길게 한 번에 펼치지 않는다.

권장 UI:

* 핵심 요약은 메인 카드에 표시
* 근거/세부 해석은 expander 또는 secondary card에 표시
* badge는 `능력치 기반`, `성장 모델`, `시장가치`, `출전 기록`처럼 사용자 친화적으로 표시

---

# PART D. Style & Mentor Lab 개선

## 9. 유사 선수 카드 문구 정리

현재 유사 선수/멘토 카드에 `proxy`, `style_vector`, `attributes_jsonb`, `10x10 grid` 같은 표현이 노출되어 사용자 경험이 떨어진다.

대상:

* `views/legend_matching.py`
* `components/cards.py`
* `explanation_engine.py`
* `styles/game_ui.css`

개선:

* 유사 선수 카드의 메인 문구를 사용자 중심으로 변경
* 내부 계산 표현은 “분석 기준 상세 보기” expander로 이동
* 카드 본문은 3~4문장 이내로 압축
* 글자 크기와 줄 간격을 키운다

유사 선수 카드 권장 구조:

```text id="039wnq"
공통점:
이 선수는 현재 선택 선수와 공격 역할, 움직임 유형, 주요 능력치 패턴이 비슷합니다.

차이점:
다만 세부 능력치나 출전 경험, 시장가치 흐름은 다를 수 있으므로 직접적인 동일 유형으로 단정하면 안 됩니다.

스카우팅 해석:
현재 선수의 장점을 키우려면 이 후보와 유사한 역할에서 어떤 능력치를 강화해야 하는지 참고할 수 있습니다.
```

개발자용 상세:

```text id="qrn86v"
분석 기준:
- 능력치 데이터 기반 유사도
- 플레이스타일 벡터 기반 비교
- 실제 경기 위치 이벤트 데이터는 사용하지 않음
```

---

## 10. 멘토 카드 문구 정리

멘토 카드 권장 구조:

```text id="1h8r0p"
멘토 적합 이유:
나이와 경험 면에서 현재 선수보다 앞선 후보이며, 유사한 역할에서 참고할 수 있는 능력치 패턴을 보입니다.

배울 수 있는 점:
공격수 유형이라면 위치 선정, 마무리 선택, 침투 타이밍을 참고할 수 있습니다. 측면 자원이라면 속도 활용, 드리블 후 판단, 크로스 선택을 중심으로 비교합니다.

주의할 점:
유사도는 참고 지표이므로 실제 경기 스타일이나 리그 수준 차이는 별도로 확인해야 합니다.
```

주의:

* “레전드”라는 표현을 과하게 쓰지 않는다.
* “실제 위치 이벤트 데이터가 아니다” 같은 문장은 메인 카드에서 제거하고 상세 expander로 이동한다.
* 멘토 카드 하나의 높이가 지나치게 길어지지 않게 한다.
* 핵심 문구는 3~5문장 정도로 제한한다.

---

# PART E. Career Simulation 개선

## 11. Career Simulation 설명 가독성

대상:

* `views/career_simulation.py`
* `explanation_engine.py`
* `styles/game_ui.css`

개선:

* 결과 설명 font-size 상향
* Baseline / Adjustment / Final Score 구분 강화
* 추천 전략은 너무 긴 문단 하나가 아니라 3개 bullet-like card로 분리

권장 구조:

1. 현재 성장 위치
2. 시나리오 영향
3. 추천 관리 방향
4. 다음 관찰 지표

주의:

* Growth/Ceiling 공식 변경 금지
* 설명만 개선

---

# PART F. Evidence & Advisory Report 개선

## 12. Report 문구 정리

대상:

* `views/ai_report.py`
* `services/qualitative_evidence.py`
* `explanation_engine.py`
* `styles/game_ui.css`

개선:

* `FM proxy`, `style_vector`, `Gemini role`, `Rule-based` 같은 표현을 사용자 친화적으로 바꾼다.
* 단, “Gemini가 점수 계산을 하지 않음” 안내는 유지하되 더 자연스럽게 표현한다.

대체 문구:

```text id="k9ysvo"
이 리포트의 점수와 성장 판단은 앱 내부 성장 모델을 기준으로 계산됩니다. Gemini는 사용자가 입력한 정성 텍스트를 해석하고, 보조적인 스카우팅 코멘트를 제공하는 역할만 합니다.
```

정성 텍스트 없을 때:

```text id="9p3w6z"
현재는 저장된 선수 데이터와 능력치 기반 분석만 사용하고 있습니다. 기사, 코치 메모, 스카우팅 메모를 입력하면 정성 근거를 추가로 반영할 수 있습니다.
```

---

# PART G. Notes / Archive 개선

## 13. Notes 가독성 점검

대상:

* `views/scouting_notes.py`
* `components/cards.py`
* `styles/game_ui.css`

개선:

* note card 글자 크기 상향
* 상세 패널 section title 가독성 개선
* Developer JSON은 기본 접힘 유지
* 사용자용 화면에 JSON/technical key가 노출되지 않게 한다.

---

# PART H. 최종 확인 및 문서화

## 14. 문서 업데이트

작업 후 아래 문서를 업데이트한다.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `ACTIVE_FUNCTION_MAP.md`
3. `REAL_MODEL_PLAN.md`
4. `AGENTS.md`
5. `FOLDER_ORGANIZATION_REPORT.md` 또는 `CLEANUP_AUDIT_REPORT.md`에 추가 기록

섹션명:

```text id="pkwyqr"
v19 Final UX Readability Polish: user-facing text and dark UI readability
```

포함 내용:

* 글자 크기/가독성 개선
* 사용자 화면에서 개발자용 표현 제거
* Player Dossier 흰색 차트 개선
* Style & Mentor Lab 문구 개선
* Report 문구 개선
* Notes 가독성 개선
* 테스트 결과

---

## 15. 테스트 요구사항

작업 후 반드시 실행한다.

```bash id="hr2zky"
python -m compileall .
python test_state_refactor.py
python test_analysis_helpers_split.py
python test_prospect_search_split.py
python test_growth_model.py
```

Streamlit health check도 실행한다.

---

## 16. 절대 금지

* DB 스키마 변경 금지
* `create_and_upload_db.py` 수정 금지
* `.streamlit/secrets.toml` 내용 출력 금지
* `.env` 내용 출력 금지
* API key 값 출력/저장/문서화 금지
* 원본 CSV 수정 금지
* Growth/Ceiling 공식 변경 금지
* style_vector 계산 방식 변경 금지
* pgvector similarity 쿼리 변경 금지
* 기존 JSONB key 삭제 금지
* legacy fallback 삭제 금지
* Gemini에게 점수 계산 맡기기 금지
* Gemini가 없는 사실을 지어내게 하기 금지
* 실제 import되는 Python 파일 임의 이동/삭제 금지
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md` 읽기/수정 금지
* 데이터에 없는 강점/약점을 지어내는 것 금지
* 사용자용 화면에 개발자용 원자료 key를 노출하는 것 금지

---

## 17. 완료 보고 형식

완료 후 아래 형식으로 보고한다.

1. 수정한 코드 파일
2. 수정한 문서 파일
3. 글자 크기/가독성 개선 내용
4. 사용자 화면에서 제거한 개발자용 표현
5. Player Dossier 차트/시각화 개선 내용
6. Style & Mentor Lab 문구 개선 내용
7. Career Simulation 문구 개선 내용
8. Evidence & Advisory Report 문구 개선 내용
9. Notes 가독성 개선 내용
10. 기존 기능 보존 여부
11. session_state 영향 여부
12. 테스트 결과
13. Streamlit health check 결과
14. 사용자가 다시 확인해야 할 화면
15. 남은 문제
