# CLAUDE_PROGRESS_SUMMARY.md

## v19 Final Functional QA: notes save, mentor empty state, Gemini fallback, and end-to-end flow (2026-06-19)

기능 추가 없이 실제 사용자 흐름에서 발생하는 버그를 발견하고 수정했다.

핵심 수정:
- **Critical bugfix — Notes 저장 전면 수정**: `scouting_note_payload.py`의 `_build_note_payload`에서 `ceiling_growth_insight`, `ceiling_growth_explanation`, `ceiling_growth_context`, `entity_type` 4개 파라미터가 required임에도 호출부 4곳(`career_simulation.py` 2곳, `ai_report.py` 2곳) 모두 전달하지 않아 Notes 저장 버튼이 항상 `TypeError`로 실패하던 문제를 수정했다. `_build_note_payload` 파라미터에 `None` 기본값을 추가하고 모든 호출부에 실제 ceiling/entity 값을 명시적으로 전달했다.
- **Mentor 빈 상태 UX**: `views/legend_matching.py`의 `_render_mentor_section`에서 멘토 후보가 없을 때 CTA 없이 안내만 표시하던 문제를 수정했다. 사용자 친화 문구와 "Scouting Board로 돌아가기" / "커리어 시뮬레이션으로 이동" 버튼을 추가했다.
- **session_state 초기화**: `views/prospect_search.py`의 `_ANALYSIS_STATE_KEYS`에 `archive_selected_idx`를 추가해 선수 변경 시 Archive 노트 선택 상태도 초기화되도록 했다.
- **새 테스트 추가**: `test_final_functional_flows.py` — 11개 테스트 전부 통과. payload 직렬화, NaN sanitize, Gemini fallback, mentor empty state, state 초기화, manual prospect 저장 흐름 검증.

테스트 결과: 총 102 passed (기존 91 + 신규 11), 0 failed. compileall 오류 없음.

보존 사항:
- DB 스키마, secrets, env, 원본 CSV, Growth/Ceiling 공식 미변경.
- `insert_scouting_note` SQL 및 테이블 구조 미변경.
- Gemini client 구조 미변경 (이미 올바른 fallback 설계).

---

## v19 UX Readability Polish: 가독성·사용자 문구 전면 정비 (2026-06-18)

기능 로직·DB 스키마 변경 없이 사용자 관점 가독성과 문구를 전면 정비했다.

변경 요약:
- **PART A — CSS 타이포그래피**: `styles/game_ui.css` — 전체 base font 14px→15px, line-height 1.55, h1/h2/h3 rem 상향, 사이드바 네비게이션 레이블/배지/카드 폰트 증가.
- **PART B — 개발자 용어 제거**: `views/legend_matching.py`, `views/dashboard.py`, `ui_components.py` — `FM proxy`, `style_vector`, `attributes_jsonb`, `mentality_jsonb`, `pgvector`, `10x10 Grid`, `cosine similarity`, `fallback`, `unavailable` → 사용자 친화 한국어로 전환. 기술 상세는 `st.expander()` 안으로 이동.
- **PART C — Altair 차트 다크 테마 픽스**: `analysis_helpers.py::attr_bar_chart`, `views/career_simulation.py`, `views/dashboard.py` — 흰 배경 제거, `configure_view(fill="transparent")`, 다크 색상 축/그리드 레이블 적용.
- **PART D — 유사 선수/멘토 카드 문구**: `analysis_helpers.py::generate_similarity_reason`, `generate_mentor_guide` — pgvector/proxy/JSONB 언급 제거, 사용자 관점 패턴 비교 문구로 재작성. `explanation_engine.py` — 배지 레이블 및 추천 텍스트 정비.
- **PART E/F/G — 나머지 뷰 정비**: `views/ai_report.py`, `views/career_simulation.py`, `views/prospect_search.py` — "FM proxy", "style_vector", "DB/FM proxy" 등 잔여 개발자 표현 전부 사용자 친화 문구로 교체.

테스트 결과: test_growth_model.py 전체 통과, test_prospect_search_split.py 통과. EXIT code 0.

보존 사항:
- DB 스키마, secrets, env, 원본 CSV, Growth/Ceiling 공식, style_vector 계산, pgvector 쿼리 미변경.
- Gemini는 정성 텍스트 추출/자문 역할만 유지. 점수 계산 미사용.
- legacy fallback 로직 유지. 기존 JSONB key 삭제 없음.

---

## v19 Final Folder Organization: docs archive and root cleanup

이번 작업은 기능 추가 없이 루트 폴더 구조를 최종 제출/유지보수용으로 정리했다.

변경 요약:
- `docs/specs/`, `docs/tasks/`, `docs/reports/`, `docs/archive/` 폴더 구조 생성.
- task 문서 10개를 `docs/tasks/`로 이동 (CODEX_TASK_V16_*.md, V19_*_TASK.md, OLDER_ORGANIZATION_TASV19_FINAL_FK.md).
- spec 문서 1개를 `docs/specs/`로 이동 (V19_PRODUCT_REDESIGN_SPEC.md).
- report 문서 2개를 `docs/reports/`로 이동 (DB_HELPER_DIFF.md, FINAL_IMPLEMENTATION_ROADMAP.md).
- archive 문서 4개를 `docs/archive/`로 이동 (CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md, CLAUDE_NEXT_SESSION_UI_TASK.md, CLAUDE_TASK_FULL.md, project_hw5.md).
- `CLAUDE_PROGRESS_SUMMARY.md`, `AGENTS.md`, `ACTIVE_FUNCTION_MAP.md`의 archive/report 경로 참조 업데이트.
- 실제 import되는 Python 파일(evidence_extractor.py, grid_pipeline.py 등)은 루트에 유지.
- 테스트 파일은 루트에 유지 (import 경로 안전성).
- `FOLDER_ORGANIZATION_REPORT.md` 생성.

테스트 결과: 91 passed (test_growth_model.py 82 + test_state_refactor.py + test_prospect_search_split.py + test_analysis_helpers_split.py), 0 failed.  
Streamlit health check: `import app` OK.

루트에 남긴 핵심 파일: app.py, requirements.txt, .gitignore, AGENTS.md, CLAUDE_PROGRESS_SUMMARY.md, ACTIVE_FUNCTION_MAP.md, REAL_MODEL_PLAN.md, CLEANUP_AUDIT_REPORT.md, 모든 실제 import Python 모듈.

남은 후보: `ui/` 폴더 삭제 (미사용), `archive/backups/` 정리, `__pycache__` 정리 (이번 작업 범위 외).

---

## v19 Final Polish and Cleanup: repository hygiene, selector inputs, and evidence-based explanations

이번 단계는 v19 Phase C 완료 이후의 최종 마무리 작업이다.

변경 요약:
- **PART A — Repository hygiene**: views/ tmp 파일 23개 삭제. code audit 수행: 중복 import 없음, app.py 426줄 적정 수준, use_container_width 사용 2곳 모두 유효. `theme.py` vs `styles/theme.py` 역할 분리 확인 (중복 없음). `CLEANUP_AUDIT_REPORT.md` 작성.
- **PART B — Input UI 개선**: `services/db.py`에 `get_distinct_nationalities()`, `get_distinct_clubs()` 추가. `ui_components.py`에 `POSITION_OPTIONS`, `FOOT_OPTIONS`, `build_position_options()`, `build_nationality_options()`, `build_club_options()` 추가. `views/manual_prospect.py` — position/sub_position/nationality/club/foot 모두 text_input → selectbox + "기타 / 직접 입력" fallback 패턴으로 전환.
- **PART C — 근거 기반 설명 강화**: `explanation_engine.py` — 6개 성장 feature 각각에 4-part 구조화 텍스트(핵심/근거/해석/방향) + 소스 배지 메타데이터 추가. `views/dashboard.py` — `_render_strength_risk_panels()` 헬퍼 추가해 강점/리스크/추천 패널에 배지 표시. `views/career_simulation.py` — Ceiling Scenario / Growth Model / Rule-based 배지 + "다음에 관찰할 지표" 섹션 추가. `views/ai_report.py` — 8섹션 구조 + FM proxy / Rule-based / style_vector 명시 라벨 추가. `analysis_helpers.py` — 유사 선수/멘토 가이드에 FM proxy / style_vector 출처 라벨링 및 5-part 구조화 텍스트 적용.

테스트 결과: 91 passed (test_growth_model.py 82 + test_state_refactor.py + test_prospect_search_split.py + test_analysis_helpers_split.py), 0 failed.

보존 사항:
- DB 스키마, secrets, env, 원본 CSV, Growth/Ceiling 공식은 변경하지 않았다.
- Gemini는 정성 텍스트 추출/자문 역할만 유지했다. 점수 계산에 사용하지 않았다.
- FM proxy / style_vector를 실제 경기 데이터처럼 표현하지 않았다.

---

## v19 UI Redesign Phase A: Game-style shell, Scouting Board, and Player Dossier

이번 단계에서는 기능 로직을 바꾸지 않고 기본 Streamlit 대시보드 느낌을 줄이는 UI 구조를 추가했다.

변경 요약:
- `components/` 구조를 추가해 layout, cards, badges, player_header, attribute_panels를 분리했다.
- `styles/` 구조를 추가해 `styles/game_ui.css`와 `styles/theme.py`로 공통 dark sports management UI를 로드한다.
- 기존 `theme.py`는 새 CSS loader를 호출하며, app.py에는 사이드바 브랜드 렌더만 얇게 연결했다.
- 좌측 사이드바 radio는 유지하되 CSS로 dark navigation rail처럼 보이도록 조정했다.
- Scouting Board는 custom page title, candidate summary stat strip, 새 badge/card 스타일을 적용했다.
- Player Dossier는 custom page title, 공통 top player header, attribute progress bar snapshot을 적용했다.
- Data Coverage badge/panel, Growth Insight, Supabase 조회, 선수 선택, session_state, Gemini, Notes 흐름은 유지했다.

새 구조:
- `components/layout.py`: sidebar brand, game page title
- `components/cards.py`: panel, scout card, stat grid, report panel HTML helper
- `components/badges.py`: Full/Partial/Limited/Manual 및 source badge helper
- `components/player_header.py`: selected player top header
- `components/attribute_panels.py`: attribute progress bar panel
- `styles/theme.py`: CSS loader
- `styles/game_ui.css`: shell, nav, header, card, badge, progress bar style

아직 전체 개편하지 않은 화면:
- Style & Mentor Lab
- Career Simulation
- Evidence & Advisory Report
- My Scouting Notes
- Manual Prospect
- DB Status

보존 사항:
- DB 스키마, secrets, env, 원본 CSV, Growth/Ceiling 공식은 변경하지 않았다.
- `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않았다.

## 현재 기준 요약

현재 프로젝트는 **NEXT-LEGEND FINDER**라는 Streamlit + Supabase 기반 유망주 스카우팅 서비스다.

현재 구현 기준은 v18.3이다.

핵심 구현 상태:
- v19 Phase 1~2 Scouting Board / Player Dossier UX 정리
- Supabase PostgreSQL 기반 선수 DB 조회
- `players`, `clubs`, `appearances`, `player_valuations`, `player_profiles`, `scouting_notes` 사용
- FM 기반 `player_profiles`와 24차원 `style_vector` 사용
- pgvector cosine similarity 기반 유사 선수/멘토 후보 조회
- DB 기반 Growth Model
- Career Simulation 기반 Ceiling Scenario
- 직접 입력 유망주(`manual_prospect`) 흐름
- My Scouting Notes 구조화 저장/조회
- Gemini 기반 정성 텍스트 신호 추출
- Gemini 기반 보조 스카우팅 추천
- 데이터 출처/분석 근거 라벨링 정리
- 데이터 커버리지 gating 및 나이 계산 일관화

## v19 Phase 1~2: Scouting Board and Player Dossier redesign

이번 단계는 v19 전체 구현이 아니라 Scouting Board, Player Dossier, Data Coverage 표시 정리만 수행했다.

변경 요약:
- Scouting Board 화면 제목과 기본 정책을 v19 기준으로 정리했다.
- 기본 유망주 나이 기준을 15~25로 설정했다.
- 기본 검색은 분석 가능한 유망주 중심이며 Full + Partial을 우선 노출하고 Limited는 기본 제외한다.
- `analyze_only`를 끄거나 전체 DB/Limited 옵션을 켜면 Limited 선수도 볼 수 있다.
- 검색 결과 카드에 분석 준비도 badge, FM profile 여부, style_vector 여부, 데이터 부족 이유, 후보 판단 문구를 표시한다.
- Player Dossier 화면 제목을 사용자 UI에서 `Player Dossier`로 변경했다. 내부 nav key는 안정성을 위해 유지한다.
- Dossier 상단에 공통 Data Coverage Panel을 추가했다.
- `ui_components.py`에 Full / Partial / Limited / Manual badge와 coverage panel 표시 helper를 추가했다.
- FM profile 없는 Transfermarkt-only 선수는 v19 UI에서 Limited로 분류하고, 직접 입력 유망주 보완/분석 가능한 선수 재검색 CTA를 제공한다.
- Growth/Ceiling 공식, Gemini 역할, Notes 저장 구조, DB 스키마는 변경하지 않았다.

현재 가장 큰 문제:
- Style & Mentor Lab / Career Simulation / Evidence & Advisory Report / Notes 전체 개편은 아직 남아 있다.
- 메뉴 내부 key는 기존 값을 유지하고 있어 사용자-facing 라벨과 내부 key가 완전히 같지는 않다.
- Scouting Board의 Full 판정은 검색 결과에 포함된 profile/style_vector 가용성 컬럼을 기반으로 한다.
- Dashboard / Mentor / Simulation / Report 전체가 아직 완전한 v19 워크플로우로 재배치되지는 않았다.
- 각 화면에서 사용자가 다음에 무엇을 해야 하는지 제품 수준에서 더 명확해야 한다.

현재 작업 목표:
- v19에서 제품 수준의 UX/분석 흐름 재설계가 필요하다.
- 먼저 `V19_PRODUCT_REDESIGN_SPEC.md`를 작성하고 사용자 승인 후 구현한다.

## 현재 기본 작업 원칙

- DB 스키마 변경 금지
- `create_and_upload_db.py` 수정 금지
- `.streamlit/secrets.toml` / `.env` 출력 또는 수정 금지
- API key 값 출력 금지
- 원본 CSV 및 `Database_Project_Dataset/` 수정 금지
- 뉴스 자동 크롤링 구현 금지
- 10x10 Grid 구현 금지
- Growth/Ceiling 공식 임의 변경 금지
- 기존 JSONB 저장 구조 삭제 금지
- legacy fallback 삭제 금지
- `app.py` 대형화 금지
- Gemini는 점수 계산에 관여하지 않음
- Gemini는 정성 텍스트 신호 추출과 보조 추천만 수행
- 문서 최신화 필수

## 상세 과거 기록

v1~v18.3의 상세 작업 기록은 `docs/archive/CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`를 참고한다.

일반 작업에서는 archive를 기본적으로 읽지 않는다. 사용자가 명시적으로 요청하거나, 과거 구현 맥락이 반드시 필요할 때만 archive를 확인한다.
## v19 UI Redesign Phase A.1: QA polish

이번 단계는 Phase A의 시각 QA/polish이며, 구현 범위는 Scouting Board와 Player Dossier의 표면 UI 정리에 한정했다.

변경 요약:
- `theme.py`를 shared CSS loader entrypoint로 축소하고, 중복 inline CSS를 `styles/game_ui.css`로 통합했다.
- `styles/game_ui.css`에 filter panel, coverage panel, action panel, Streamlit widget dark styling을 추가했다.
- Scouting Board 검색 조건 패널과 후보 카드가 `game-panel`, `game-filter-panel`, `game-scout-card` 계열 클래스를 쓰도록 정리했다.
- Player Dossier의 player header 호출에 `entity_type`을 전달하고, Data Coverage Panel을 compact status grid 형태로 보강했다.
- `app.py`는 추가로 비대화하지 않았다.

보존한 것:
- DB schema, secrets/env, original CSV, Growth/Ceiling formulas, Supabase queries, Gemini role, Notes persistence flow.
- Style & Mentor Lab, Career Simulation, Evidence & Advisory Report, My Scouting Notes, Manual Prospect, DB Status 전체 개편은 아직 하지 않았다.
- `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않았다.

다음 권장 단계:
- Phase A.2에서 Career Simulation과 Evidence & Advisory Report를 같은 design system으로 확장한다.
- 그 전에 실제 브라우저에서 Scouting Board와 Player Dossier의 desktop/mobile visual QA를 확인한다.
## v19 UI Redesign Phase C: Style & Mentor Lab and Scouting Notes styling

이번 단계는 Style & Mentor Lab과 My Scouting Notes의 UI surface를 Phase A/B 디자인 시스템으로 확장했다.

변경 요약:
- `views/legend_matching.py`를 Style & Mentor Lab으로 재작성했다. game page title, Style Snapshot Panel, Similarity Candidates 카드 grid, Mentor Candidates 카드 grid, Selected Mentor 요약 패널, 다음 단계 CTA를 적용했다.
- `views/scouting_notes.py`를 Scouting Archive로 재작성했다. game page title, Archive Summary Strip(5종 통계), Filter Panel, game archive note card list, Selected Note Detail Panel(7섹션)을 적용했다.
- `components/cards.py`에 `similarity_card_html`, `mentor_card_html`, `archive_note_card_html`, `empty_state_panel_html`, `score_bar_html`을 추가했다.
- `styles/game_ui.css`에 `.game-style-snapshot`, `.game-similarity-grid`, `.game-mentor-card`, `.game-mentor-fit`, `.game-score-bar`, `.game-archive-strip`, `.game-archive-stat`, `.game-note-card`, `.game-note-detail`, `.game-note-section`, `.game-empty-state` 등을 추가했다.
- pgvector style_vector gating, mentor age filter(기본/완화 기준), fallback 안내는 그대로 유지했다.
- Notes 저장 payload, legacy fallback, 개발자용 JSON expander, 공개 helper 함수(saved_note_label, saved_coaching_sections, saved_report_original)는 그대로 유지했다.
- session_state key(archive_selected_idx 추가, 기존 key 변경 없음)

보존한 것:
- DB schema, secrets/env, original CSV, Growth/Ceiling formulas, Supabase access, pgvector similarity, Gemini role, Notes persistence flow.
- Manual Prospect, DB Status 전체 개편은 하지 않았다.
- `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않았다.

수동 확인 대상:
- Style & Mentor Lab: FM profile 있는 선수 / style_vector 없는 선수 / manual_prospect 진입, 멘토 선택 버튼, Selected Mentor Guide 패널.
- Scouting Archive: 노트 목록 카드, 필터, 상세 보기 토글, Qualitative/Gemini 없는 노트 표시.

## v19 UI Redesign Phase B: Career Simulation and Evidence Report styling

이번 단계는 Career Simulation과 Evidence & Advisory Report의 UI surface를 Phase A 디자인 시스템으로 확장했다.

변경 요약:
- Career Simulation에 `Scenario Lab` page title, scenario control panel, simulation result panel, trajectory panel, score card grid를 적용했다.
- Career Simulation의 Growth/Ceiling 계산, `ceiling_growth_*` session_state, Notes 저장 payload는 그대로 유지했다.
- Evidence & Advisory Report에 `Scouting Report Room` page title, rule-based summary panel, qualitative evidence input panel, Gemini signal/advisory panels, final preview/save panels를 적용했다.
- Gemini는 정성 신호 구조화와 보조 추천 역할만 유지하며 Growth/Ceiling 점수 계산에는 관여하지 않는다.
- `use_container_width=True` 일부를 `width="stretch"`로 정리했다.

보존한 것:
- DB schema, secrets/env, original CSV, Growth/Ceiling formulas, Supabase access, search/selection flow, Gemini fallback, Notes persistence flow.
- Style & Mentor Lab, My Scouting Notes, Manual Prospect, DB Status 전체 개편은 아직 하지 않았다.
- `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않았다.

수동 확인 대상:
- Career Simulation: matched/FM profile/manual prospect/Limited 선수 진입, scenario slider/radio 조작, Final Growth Score 표시, Notes 저장 버튼.
- Evidence & Advisory Report: simulation 없이 진입 시 안내, simulation 이후 report draft 생성, qualitative text input, Gemini key 없음 안내, final preview/save panel.
## v19 Final User Flow Fix: Gemini handling, mentality evidence, scenario labels, and mentor-first UX

이번 단계는 실제 화면 확인 중 드러난 사용자 이해 문제를 수정한 final flow polish다.

변경 요약:
- Gemini 호출 실패 시 raw API error를 기본 화면에 노출하지 않고, 짧은 사용자 안내를 보여준다. 원문 오류는 개발자용 expander 안에만 둔다.
- Player Dossier의 멘탈/성향 분석 근거를 능력치 기반 평가, Growth Model 반영 여부, 정성 메모 보조 분석으로 분리했다.
- 정성 텍스트 입력을 Player Dossier와 Evidence & Advisory Report가 같은 `qualitative_text_input` session_state로 공유한다.
- Career Simulation의 훈련 강도/출전 기회 숫자 slider를 설명형 선택지로 바꾸되, 기존 numeric env_settings 값으로 매핑해 공식은 유지했다.
- 리그 난이도/리스크 성향 선택 아래에 사용자용 설명 문구를 추가했다.
- Scouting Board 기본 검색은 능력치 프로필이 있는 선수만 표시하고, Limited 포함 옵션은 고급 필터로 이동했다.
- Style & Mentor Lab은 Mentor Matching Lab 흐름으로 바꾸어 멘토 후보를 먼저 보여주고, 전체 유사 선수 참고는 expander로 숨겼다.

보존한 것:
- DB schema, secrets/env, original CSV, Growth/Ceiling 공식, style_vector 계산, pgvector query, Supabase 연결, Notes 저장 payload/legacy fallback.
- Gemini는 정성 텍스트 구조화와 보조 추천만 담당하며 점수 계산을 하지 않는다.
- `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않았다.
