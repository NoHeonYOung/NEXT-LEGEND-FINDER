# V19_UI_REDESIGN_PHASE_C_TASK.md

## 0. 작업 목적

이 프로젝트는 `c:\Users\nhy81\Desktop\Database_Project`의 NEXT-LEGEND FINDER Streamlit + Supabase 기반 축구 유망주 스카우팅 웹앱이다.

현재 Codex를 통해 다음 단계까지 완료되어 있다.

* v19 Phase 1~2: Scouting Board + Player Dossier 구조 정리
* v19 UI Redesign Phase A: 공통 components/styles 기반 dark sports management UI 도입
* v19 UI Redesign Phase A.1: Scouting Board / Player Dossier polish
* v19 UI Redesign Phase B: Career Simulation / Evidence & Advisory Report UI 개선

이번 작업은 Claude Code가 Codex 작업을 이어받아 진행하는 v19 UI Redesign Phase C이다.

목표:

1. 현재 Codex가 만든 UI 구조와 변경사항을 먼저 파악한다.
2. 기존 components/styles 디자인 시스템을 유지/확장한다.
3. Style & Mentor Lab을 game-style mentor analysis lab으로 개편한다.
4. My Scouting Notes를 game-style scouting archive로 개편한다.
5. 기존 기능, DB 로직, pgvector 유사도, Notes 저장/조회, legacy fallback은 유지한다.
6. 문서 최신화와 테스트를 수행한다.

---

## 1. 작업 전 반드시 확인할 것

먼저 아래 명령으로 현재 워크트리를 확인한다.

```bash
git status
```

주의:

* Codex가 만든 변경사항을 임의로 되돌리지 말 것
* 이미 존재하는 components/styles 구조를 재사용할 것
* app.py를 다시 비대하게 만들지 말 것
* 기존 UI 시스템과 충돌하는 별도 CSS 체계를 새로 만들지 말 것

---

## 2. 현재 기준

현재 구현 상태:

* `components/` 구조 존재
* `styles/` 구조 존재
* `styles/game_ui.css` 존재
* `styles/theme.py`에서 CSS 로드
* Scouting Board UI 개선 완료
* Player Dossier UI 개선 완료
* Career Simulation UI 개선 완료
* Evidence & Advisory Report UI 개선 완료
* 공통 player header, card, badge, panel, score card, alert, signal grid 등 존재
* Growth/Ceiling 공식 변경 없음
* Gemini는 점수 계산이 아니라 정성 신호 추출과 보조 추천 역할만 수행
* DB schema, secrets/env, 원본 CSV는 건드리지 않음

이번 Phase C에서는 아직 개편되지 않은 다음 화면을 정리한다.

* Style & Mentor Lab
* My Scouting Notes

이번 Phase C에서는 아직 다음 화면은 전체 개편하지 않는다.

* Manual Prospect
* DB Status

---

## 3. 먼저 읽을 파일

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
17. `views/legend_matching.py`
18. `views/scouting_notes.py`
19. `views/dashboard.py`
20. `views/prospect_search.py`
21. `views/career_simulation.py`
22. `views/ai_report.py`
23. `scouting_note_payload.py`
24. `services/db.py`
25. `manual_prospect_helpers.py`
26. `test_growth_model.py`
27. `test_prospect_search_split.py`

주의:

* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않는다.
* secrets/env/API key 파일은 열람하지 않는다.

---

# PART A. Style & Mentor Lab UI 개편

## 4. 목표

`views/legend_matching.py`를 game-style Style & Mentor Lab으로 개편한다.

현재 기능은 유지한다.

유지해야 할 것:

* pgvector 기반 style_vector 유사도 검색
* 기존 유사 선수 후보 조회
* 기존 멘토 후보 필터
* 자기 자신 제외
* 나이 조건 필터
* fallback 나이 기준
* style_vector 없을 때 조기 차단
* FM profile 없을 때 제한 분석 안내
* session_state 흐름

절대 변경 금지:

* DB schema
* style_vector 차원
* pgvector cosine similarity 방식
* 기존 쿼리 의미
* Growth/Ceiling 공식
* Gemini 로직

---

## 5. Style & Mentor Lab 화면 구조

권장 구조:

```text
[Top Player Header]

[Current Style Snapshot Panel]
- 현재 선수 포지션/역할
- FM profile / style_vector 상태
- 분석 준비도 badge
- 스타일 요약
- 데이터 부족 안내

[Similarity Candidates Section]
- 유사 선수 후보 카드 grid
- similarity score
- 유사한 이유
- 다른 점
- 데이터 출처 badge

[Mentor Candidates Section]
- 멘토 후보 카드 grid
- 나이
- 포지션
- 팀
- style similarity
- mentor fit badge
- 배울 수 있는 훈련 방향
- 주의할 점
- fallback 기준 사용 여부

[Selected Mentor / Next Action Panel]
- 선택한 멘토 요약
- Career Simulation으로 이동
- Evidence & Advisory Report로 이동
- Player Dossier로 이동
```

---

## 6. Style Snapshot Panel 요구사항

상단에 현재 선수 스타일 요약 패널을 둔다.

표시:

* 선수 이름
* 포지션
* 나이
* 팀
* 분석 준비도 badge
* FM profile 여부
* style_vector 여부
* style_vector 기반 분석 가능 여부
* 제한 분석이면 명확한 warning card

FM profile 또는 style_vector가 없으면:

* 유사 선수 계산을 실행하지 않는다.
* 다음 문구를 game alert panel로 표시한다.

```text
FM profile 또는 style_vector가 없어 유사 선수/멘토 분석을 실행할 수 없습니다.
Scouting Board에서 분석 가능한 선수를 선택하거나 Manual Prospect로 보완하세요.
```

CTA:

* Scouting Board로 돌아가기
* Player Dossier로 돌아가기
* Manual Prospect로 보완하기

---

## 7. Similarity Candidates 요구사항

유사 선수 후보를 기본 Streamlit 표처럼 보여주지 말고 카드 grid로 보여준다.

각 카드 표시:

* 이름
* 나이
* 포지션
* 팀
* similarity score
* style similarity badge
* 데이터 출처 badge
* 유사한 이유
* 다른 점
* CTA: 이 선수 보기 또는 비교 대상으로 선택

디자인:

* `game-scout-card` 또는 유사 card 재사용
* hover 효과
* score/progress bar
* compact typography
* dark panel

주의:

* similarity score를 새로운 방식으로 계산하지 말 것
* 기존 반환 데이터만 시각화 개선
* 후보가 없으면 empty state card 표시

---

## 8. Mentor Candidates 요구사항

멘토 후보를 별도 섹션으로 표시한다.

멘토 조건은 기존 구현 유지:

* 자기 자신 제외
* 나이 없음/0세 제외
* 기본 기준: `max(28, target_age + 5)`
* 완화 기준: `max(26, target_age + 3)`
* 완화 기준 사용 시 안내 표시

각 멘토 카드 표시:

* 이름
* 나이
* 포지션
* 팀
* style similarity
* mentor fit badge
* 멘토 적합 이유
* 배울 수 있는 훈련 방향
* 리스크/주의할 점
* 기준: 기본/완화 여부

CTA:

* 이 멘토 선택
* 이 멘토 기준 훈련 방향 보기
* Career Simulation으로 이동

주의:

* 멘토 후보를 “레전드”라고 과장하지 말 것
* 실제 레전드 DB가 아니라 현재 DB/FM proxy 기반 유사 선수/멘토 후보임을 명확히 표시
* 데이터 출처 badge 표시

---

# PART B. My Scouting Notes UI 개편

## 9. 목표

`views/scouting_notes.py`를 game-style scouting archive로 개편한다.

현재 기능은 유지한다.

유지해야 할 것:

* 저장된 notes 조회
* note_type
* entity_type
* report_generation_mode
* player_snapshot
* profile_snapshot
* growth_insight
* ceiling_growth_insight
* qualitative_evidence
* gemini_advisory
* generated_report_text
* legacy fallback
* 개발자용 JSON expander

절대 변경 금지:

* scouting_notes DB schema
* 기존 JSONB key 삭제
* legacy fallback 삭제
* 저장 payload 구조 변경
* Notes 저장 흐름 제거

---

## 10. Notes 화면 구조

권장 구조:

```text
[Page Title: Scouting Archive / Notes]

[Archive Summary Strip]
- 전체 노트 수
- DB 선수 노트 수
- Manual Prospect 노트 수
- Gemini 사용 노트 수
- 정성 텍스트 포함 노트 수

[Filter Panel]
- 선수명 검색
- note_type
- entity_type
- report_generation_mode
- Gemini 사용 여부
- 정성 텍스트 포함 여부

[Notes List]
- note card list
- 저장 시점
- 선수 이름
- note_type
- entity_type
- report_generation_mode
- Growth Score
- Final Growth Score
- badges

[Selected Note Detail Panel]
- 선수 snapshot
- Data Coverage
- Growth/Ceiling 결과
- 정성 텍스트 근거
- Gemini 보조 추천
- 최종 리포트
- developer JSON expander
```

---

## 11. Notes List Card 요구사항

기본 dataframe처럼 보이면 안 된다.

각 노트 카드는 다음을 표시한다.

* 선수 이름
* 저장 시점
* note_type
* entity_type
* report_generation_mode
* Growth Score
* Final Growth Score
* Gemini 사용 badge
* 정성 텍스트 badge
* Manual/DB badge
* CTA: 노트 상세 보기

디자인:

* game archive card
* compact typography
* badges
* selected card highlight
* hover effect

---

## 12. Note Detail Panel 요구사항

선택된 노트 상세를 report room처럼 표시한다.

섹션:

1. Saved Player Snapshot
2. Data Coverage at Save Time
3. Growth / Ceiling Result
4. Qualitative Evidence
5. Gemini Advisory
6. Final Scouting Report
7. Developer JSON

표시 원칙:

* 없는 데이터는 숨기지 말고 “저장 당시 없음”으로 표시
* Gemini 없으면 “rule-based only” badge
* qualitative text 없으면 “정성 텍스트 없음” 표시
* legacy note는 legacy fallback으로 표시
* 개발자용 JSON은 기본 접힘 expander 유지

주의:

* Notes 화면은 조회 전용이다.
* 새 유망주 생성 폼을 넣지 않는다.
* Manual Prospect 생성은 Manual Prospect 화면에서만 한다.

---

# PART C. 공통 CSS/컴포넌트 확장

## 13. 추가/개선할 컴포넌트

가능하면 기존 components를 확장한다.

권장 추가:

* mentor_card_html
* similarity_card_html
* archive_note_card_html
* note_detail_panel_html
* empty_state_panel_html
* compact_badge_row
* score_bar_html

가능한 위치:

* `components/cards.py`
* `components/badges.py`
* `components/attribute_panels.py`
* 필요 시 `components/reports.py`
* `styles/game_ui.css`

주의:

* components가 너무 커지면 기능별로 분리
* app.py에 긴 HTML 넣지 말 것
* CSS class 이름은 `game-` prefix 사용 권장

---

## 14. 디자인 요구사항

CSS에서 다음 스타일을 추가/정리한다.

* game-mentor-lab
* game-style-snapshot
* game-similarity-grid
* game-mentor-card
* game-mentor-fit
* game-archive
* game-note-card
* game-note-detail
* game-note-section
* game-empty-state

기본 톤:

* dark navy
* thin border
* compact font
* badge
* score/progress bar
* hover
* selected highlight
* muted missing data state

---

## 15. 기능 보존 요구사항

반드시 보존:

* Supabase DB 연결
* 검색 기능
* 선수 선택 기능
* session_state 흐름
* style_vector similarity
* mentor age filter
* style_vector 없는 선수 gating
* Notes 조회
* Notes legacy fallback
* Growth/Ceiling/Gemini 저장 payload
* Manual Prospect 흐름

선수 변경 시 stale state 초기화 흐름 유지:

* growth
* ceiling
* report
* qualitative_signals
* gemini_advisory

---

## 16. 문서 업데이트

작업 후 아래 문서를 업데이트한다.

* `CLAUDE_PROGRESS_SUMMARY.md`
* `ACTIVE_FUNCTION_MAP.md`
* `REAL_MODEL_PLAN.md`
* `AGENTS.md`

섹션명:

```text
v19 UI Redesign Phase C: Style & Mentor Lab and Scouting Notes styling
```

문서에 포함:

* Style & Mentor Lab UI 변경
* Notes UI 변경
* 기존 pgvector/mentor 로직 보존
* 기존 Notes payload/legacy fallback 보존
* 새/확장 컴포넌트
* 아직 개편하지 않은 화면
* 수동 확인 화면

주의:

* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않는다.

---

## 17. 테스트 요구사항

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

## 18. 절대 금지

* DB 스키마 변경 금지
* `create_and_upload_db.py` 수정 금지
* `secrets.toml` 내용 출력 금지
* `.env` 내용 출력 금지
* API key 값 출력/저장/문서화 금지
* 원본 CSV 수정 금지
* 뉴스 자동 크롤링 구현 금지
* 10x10 Grid 구현 금지
* Growth/Ceiling 공식 변경 금지
* existing JSONB key 삭제 금지
* legacy fallback 삭제 금지
* Gemini에게 점수 계산 맡기기 금지
* Gemini가 없는 사실을 지어내게 하기 금지
* app.py 대형화 금지
* Football Manager 고유 로고/이미지/에셋 복제 금지
* UI 작업 범위를 전 화면으로 확대 금지
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md` 수정 금지
* 기존 session_state key 삭제 금지

---

## 19. 완료 보고 형식

완료 후 아래 형식으로 보고한다.

1. 수정한 코드 파일
2. 새로 만든 코드 파일
3. 수정한 문서 파일
4. Style & Mentor Lab UI 변경 내용
5. My Scouting Notes UI 변경 내용
6. 새/확장 컴포넌트
7. CSS/theme 변경 내용
8. 기존 similarity/mentor 로직 보존 여부
9. Notes payload/legacy fallback 보존 여부
10. session_state 영향 여부
11. 테스트 결과
12. Streamlit health check 결과
13. 사용자가 직접 확인해야 할 화면
14. 아직 개편하지 않은 화면
15. 다음 Phase 추천
16. 남은 문제
