# V19_FINAL_POLISH_AND_CLEANUP_TASK.md

## 0. 작업 목적

이 프로젝트는 `c:\Users\nhy81\Desktop\Database_Project`의 NEXT-LEGEND FINDER Streamlit + Supabase 기반 축구 유망주 스카우팅 웹앱이다.

현재 v18.3, v19 Phase 1~2, v19 UI Redesign Phase A/A.1/B/C까지 진행되었다.

현재 완료된 주요 작업:

* Scouting Board UI 개편
* Player Dossier UI 개편
* Career Simulation UI 개편
* Evidence & Advisory Report UI 개편
* Style & Mentor Lab UI 개편
* My Scouting Notes / Scouting Archive UI 개편
* components/와 styles/ 기반 dark sports management UI 도입
* Data Coverage / Limited 선수 처리 / Age Resolver / Mentor gating 적용
* Growth/Ceiling/Gemini/Notes 주요 흐름 유지

이번 작업은 새로운 대형 기능을 추가하는 것이 아니라, 최종 마무리 전 polish와 cleanup을 수행하는 작업이다.

핵심 목표:

1. repository cleanup / code audit
2. tmp/중복/작업용 파일 정리
3. 포지션/국적/팀/주발 입력을 직접 텍스트 입력이 아닌 선택형 UI로 개선
4. 강점/약점/추천 훈련 텍스트를 실제 데이터 근거 기반으로 더 의미 있게 개선
5. Manual Prospect는 전체 재설계가 아니라 입력 UX와 설명 품질 중심으로 최소 polish
6. use_container_width warning 잔여 여부 확인
7. 전체 테스트 및 Streamlit health check
8. `CLEANUP_AUDIT_REPORT.md` 생성

---

## 1. 작업 전 반드시 확인

먼저 아래 명령을 실행해 현재 상태를 확인한다.

```bash
git status
```

작업 전 상태를 `CLEANUP_AUDIT_REPORT.md`에 기록한다.

주의:

* 사용자가 아직 commit하지 않은 변경사항을 임의로 되돌리지 않는다.
* Codex/Claude가 만든 최근 변경을 임의로 삭제하지 않는다.
* 삭제가 애매한 파일은 삭제하지 말고 `CLEANUP_AUDIT_REPORT.md`에 후보로 남긴다.
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않는다.

---

## 2. 먼저 읽을 파일

아래 파일을 읽고 현재 구조를 파악한다.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `AGENTS.md`
3. `ACTIVE_FUNCTION_MAP.md`
4. `REAL_MODEL_PLAN.md`
5. `V19_PRODUCT_REDESIGN_SPEC.md`
6. `app.py`
7. `theme.py`
8. `ui_components.py`
9. `player_coverage.py`
10. `components/`
11. `styles/`
12. `views/prospect_search.py`
13. `views/dashboard.py`
14. `views/legend_matching.py`
15. `views/career_simulation.py`
16. `views/ai_report.py`
17. `views/scouting_notes.py`
18. `views/manual_prospect.py`
19. `views/db_status.py`
20. `services/db.py`
21. `scouting_note_payload.py`
22. `growth_model.py`
23. `explanation_engine.py`
24. `manual_prospect_helpers.py`
25. `test_growth_model.py`
26. `test_prospect_search_split.py`
27. `test_state_refactor.py`
28. `test_analysis_helpers_split.py`

주의:

* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않는다.
* `.env`, `.streamlit/secrets.toml`, API key 파일은 열람하지 않는다.

---

# PART A. Repository Cleanup / Code Audit

## 3. 파일 정리 정책

### 3.1 정리 가능한 후보

다음 유형은 실제 import 여부를 확인한 뒤 정리한다.

* `*.tmp`
* `*.tmp.*`
* `__pycache__/`
* `.pytest_cache/`
* 중복으로 생성된 임시 Python 파일
* 오래된 task 문서 중 이미 완료된 것
* 루트에 흩어진 작업용 md 파일
* 오래된 diff/report 파일 중 현재 문서에 반영된 것

삭제 전 확인:

* Python 파일은 import/reference 검색
* 삭제 후 `python -m compileall .`
* 애매하면 삭제하지 말고 보고서에 후보로 남김

예상 후보:

* `dashboard.py.tmp...`
* `legend_matching.py.tmp...`
* `prospect_search.py.tmp...`
* `scouting_notes.py.tmp...`
* `manual_prospect.py.tmp...`
* 완료된 `CODEX_TASK_*.md`
* 완료된 `V19_*_TASK.md`

---

### 3.2 task 문서 정리

루트에 작업 지시서가 너무 많이 쌓여 있으면 `docs/tasks/` 또는 `docs/archive_tasks/`로 이동을 검토한다.

정책:

* 현재 진행 중인 task 파일은 루트에 유지 가능
* 완료된 task 파일은 `docs/tasks/` 또는 `docs/archive_tasks/`로 이동
* 이동이 위험하면 삭제하지 말고 `CLEANUP_AUDIT_REPORT.md`에 제안만 기록
* `V19_PRODUCT_REDESIGN_SPEC.md`는 제품 설계 문서이므로 유지

---

### 3.3 절대 삭제 금지

아래는 삭제하거나 수정하지 않는다.

* `.streamlit/secrets.toml`
* `.env`
* 원본 CSV
* `create_and_upload_db.py`
* Supabase 관련 설정 파일
* DB schema 관련 파일
* 실제 import되는 Python 파일
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`
* 사용자가 명시적으로 보관 중인 문서
* 현재 진행 중인 task 파일

---

## 4. 코드 중복 / 이상 부분 점검

점검 항목:

1. unused import
2. import cycle 가능성
3. 더 이상 사용하지 않는 helper
4. 중복된 helper 함수
5. `ui_components.py`와 `components/`의 역할 중복
6. `theme.py`와 `styles/theme.py`의 역할 중복
7. `styles/game_ui.css`의 중복 class
8. `app.py` 비대화 여부
9. `use_container_width=True` 잔여 여부
10. Phase A/B/C에서 추가된 컴포넌트 중 실제 미사용 함수 여부

주의:

* 테스트가 커버하지 않는 코드는 함부로 삭제하지 않는다.
* 삭제가 애매한 함수는 삭제하지 말고 보고서에 후보로 남긴다.
* app.py는 router/bootstrap 수준을 유지한다.

---

# PART B. 입력 UI 개선

## 5. 포지션/국적/팀/주발 입력 방식 개선

현재 일부 화면에서 포지션, 국적, 팀, 주발 등을 사용자가 직접 텍스트로 입력해야 하는 경우가 있다.

이 방식은 오타가 발생하고 데이터 일관성이 떨어진다.

이번 작업에서는 가능한 범위에서 직접 입력 대신 선택형 UI로 바꾼다.

대상 후보 화면:

* `views/prospect_search.py`
* `views/manual_prospect.py`
* `views/dashboard.py`에서 보완 입력이 있다면 해당 영역
* 기타 포지션/국적/팀/주발을 입력받는 부분

Manual Prospect는 이번에 전체 UI 재설계까지는 하지 않는다.
다만 포지션/국적/팀/주발 입력 UX는 선택형으로 정리한다.

---

## 5.1 포지션 선택

직접 텍스트 입력 대신 selectbox / multiselect / segmented control 형태로 선택하게 한다.

권장 포지션 옵션:

```python
POSITION_OPTIONS = [
    "Goalkeeper",
    "Defender",
    "Centre-Back",
    "Full-Back",
    "Wing-Back",
    "Midfielder",
    "Defensive Midfielder",
    "Central Midfielder",
    "Attacking Midfielder",
    "Winger",
    "Forward",
    "Striker"
]
```

요구사항:

* 직접 입력 기본값을 없애거나 최소화한다.
* 기존 DB에 존재하는 포지션 값을 우선적으로 수집해 옵션에 포함한다.
* 위 기본 옵션 + DB에서 발견한 포지션 옵션을 합쳐 중복 제거 후 정렬한다.
* 검색 필터에서는 multiselect 허용 가능
* Manual Prospect에서는 주 포지션 selectbox + 보조 포지션 multiselect 권장
* 선택값은 기존 저장/분석 로직과 호환되게 유지한다.
* 옵션이 많을 경우 Streamlit dropdown의 스크롤 선택을 활용한다.

---

## 5.2 국적 선택

국적도 직접 텍스트 입력 대신 선택형 UI로 바꾼다.

요구사항:

* DB에 존재하는 국적 목록을 우선 사용
* 기본값은 “선택 안 함” 또는 “Unknown”
* 검색 필터에서는 multiselect 허용 가능
* Manual Prospect에서는 selectbox 권장
* 옵션이 너무 많으면 searchable selectbox를 사용한다.
* Streamlit selectbox/multiselect의 드롭다운 스크롤을 활용한다.
* 직접 입력이 필요하면 `Other / 직접 입력` 옵션을 별도로 두되, 기본은 선택형으로 한다.

주의:

* 국적 이름을 임의로 새로 생성하지 않는다.
* 기존 DB 값과 충돌하지 않게 한다.

---

## 5.3 팀/클럽 선택

팀/클럽 입력이 있는 경우 직접 입력보다 선택형을 우선한다.

요구사항:

* DB clubs 테이블 또는 선수 데이터에서 club_name 목록을 가져와 옵션화
* Manual Prospect에서는 club selectbox + “Other / 직접 입력” fallback 허용
* 검색 필터에서는 club multiselect 허용 가능

---

## 5.4 주발 선택

주발 입력은 selectbox로 고정한다.

옵션:

* `Unknown`
* `Right`
* `Left`
* `Both`

---

## 5.5 공통 옵션 helper

가능하면 옵션 생성 helper를 만든다.

권장 위치:

* `ui_components.py`
* 또는 `components/inputs.py`
* 또는 `services/db.py`에 raw list query 후 UI helper에서 가공

예시 역할:

* `build_position_options(players_df, profiles_df=None)`
* `build_nationality_options(players_df)`
* `build_club_options(players_df, clubs_df=None)`
* `render_position_selector(...)`
* `render_nationality_selector(...)`
* `render_club_selector(...)`
* `render_foot_selector(...)`

주의:

* app.py에 직접 옵션 생성 코드를 길게 넣지 않는다.
* DB query 로직과 UI 렌더링 로직을 과도하게 섞지 않는다.
* 기존 session_state key는 깨지지 않게 한다.

---

# PART C. 강점/약점/추천 텍스트 고도화

## 6. 현재 문제

현재 앱에서 “이 능력치가 좋다”, “이 부분이 안 좋다”, “이런 훈련이 필요하다” 같은 텍스트가 나오지만, 사용자가 보기에는 다음 문제가 있다.

1. 어떤 데이터를 근거로 말하는지 충분히 명확하지 않다.
2. 설명이 짧고 일반론처럼 보일 수 있다.
3. FM proxy 능력치, 멘탈 지표, Growth 구성요소, 출전/시장가치 데이터, Gemini 정성 텍스트가 어떻게 반영됐는지 구분이 약하다.
4. 데이터가 부족한 경우에도 표현이 너무 단정적으로 보일 수 있다.

이번 작업에서는 텍스트 설명을 더 의미 있게 만들되, 없는 사실을 지어내지 않는다.

---

## 7. 설명 생성 원칙

모든 강점/약점/추천 텍스트는 가능한 경우 아래 근거 중 최소 하나 이상을 명시해야 한다.

근거 후보:

1. DB 선수 기본정보
2. 시장가치 흐름
3. 출전 기록
4. FM attributes_jsonb
5. FM mentality_jsonb
6. style_vector 유사도
7. Growth Score 구성요소
8. Ceiling Scenario 설정값
9. qualitative_evidence
10. Gemini advisory

출처 라벨:

* `DB`
* `Transfermarkt`
* `FM proxy`
* `Growth Model`
* `Ceiling Scenario`
* `style_vector`
* `User text`
* `Gemini advisory`
* `Rule-based`

---

## 8. Player Dossier 텍스트 고도화

대상:

* `views/dashboard.py`
* `ui_components.py`
* `explanation_engine.py`
* 필요 시 새 helper 파일

Player Identity / Strength / Weakness 영역에서 다음을 개선한다.

### 8.1 강점 설명

강점은 단순히 “A가 높다”가 아니라 아래 구조로 설명한다.

구조:

1. 핵심 강점 한 줄
2. 근거 데이터
3. 경기/스카우팅 관점 해석
4. 훈련 또는 활용 방향

예시 구조:

* 강점: 전진 패스와 공격 전개 관여도가 높은 유형입니다.
* 근거: FM proxy의 Passing, Vision, Decisions 항목이 상대적으로 높게 나타났고, Growth Model에서도 공격/전개 기여 항목이 긍정적으로 반영되었습니다.
* 해석: 단순히 볼을 안전하게 처리하는 선수라기보다, 2선과 전방을 연결하는 역할에서 장점이 나타날 가능성이 있습니다.
* 활용 방향: 빌드업 상황에서 전진 패스 선택지를 늘리고, 압박 상황에서 판단 속도를 유지하는 훈련이 적합합니다.

주의:

* 실제 문구는 실제 데이터 기반으로 생성해야 한다.
* 데이터가 없으면 예시를 그대로 쓰지 않는다.

---

### 8.2 약점 설명

약점은 단순히 “A가 낮다”가 아니라 아래 구조로 설명한다.

구조:

1. 핵심 약점 한 줄
2. 근거 데이터
3. 경기에서 나타날 수 있는 리스크
4. 보완 방향

예시 구조:

* 보완점: 수비 위치 선정과 압박 대응 안정성은 추가 확인이 필요합니다.
* 근거: FM proxy의 Positioning, Concentration, Composure 관련 값이 강점 항목보다 낮게 나타났습니다.
* 리스크: 높은 압박을 받는 경기에서는 판단이 늦어지거나 수비 전환 타이밍이 흔들릴 수 있습니다.
* 보완 방향: 압박 상황에서의 첫 터치 방향, 주변 시야 확보, 수비 전환 후 위치 회복 훈련이 필요합니다.

---

### 8.3 추천 훈련 방향

추천 훈련은 아래 기준을 함께 고려한다.

근거:

* 포지션
* 낮은 FM attribute
* 낮은 mentality attribute
* Growth Model에서 낮게 나온 항목
* Career Simulation 설정
* Gemini qualitative signal이 있으면 함께 반영

출력 구조:

1. 우선 훈련 목표
2. 왜 필요한지
3. 구체 훈련 방향
4. 관찰해야 할 지표

주의:

* 실제 정성 텍스트가 없으면 “정성 텍스트에서 언급” 같은 표현을 쓰지 않는다.
* 없는 데이터에 기반한 추천을 만들지 않는다.
* 너무 짧은 한 줄 설명으로 끝내지 않는다.

---

## 9. Style & Mentor Lab 설명 고도화

대상:

* `views/legend_matching.py`
* `components/cards.py`
* 필요 시 `explanation_engine.py`

Style & Mentor Lab은 Phase C에서 UI가 개편되었다.

이번 작업에서는 후보 카드의 설명이 데이터 근거를 더 명확히 드러내도록 개선한다.

유사 선수 설명 구조:

1. 유사한 이유
2. style_vector 또는 FM proxy 근거
3. 주의해서 봐야 할 차이
4. 데이터 한계

멘토 추천 설명 구조:

1. 멘토로 적합한 이유
2. 나이 조건 근거
3. style similarity 근거
4. 배울 수 있는 훈련 방향
5. 주의할 점

주의:

* “레전드”라는 표현을 과장해서 쓰지 않는다.
* 실제 레전드 DB가 아니라 현재 DB/FM proxy 기반 유사 선수/멘토 후보임을 명확히 한다.

---

## 10. Career Simulation 설명 고도화

대상:

* `views/career_simulation.py`
* `explanation_engine.py`
* 필요 시 helper

Career Simulation 결과 설명을 더 길고 의미 있게 만든다.

설명 구조:

1. 현재 baseline 해석
2. 선택한 시나리오가 점수에 미친 영향
3. 상승 요인
4. 하락/리스크 요인
5. 추천 커리어 전략
6. 다음에 관찰할 지표

주의:

* 공식은 변경하지 않는다.
* 설명만 고도화한다.
* Scenario Adjustment 계산값과 설명이 모순되면 안 된다.

---

## 11. Evidence & Advisory Report 설명 고도화

대상:

* `views/ai_report.py`
* `services/qualitative_evidence.py`
* `explanation_engine.py`

요구사항:

* Rule-based 분석과 Gemini advisory를 명확히 분리
* Gemini가 말한 내용을 최종 사실처럼 단정하지 않음
* evidence_quotes가 있으면 근거로 표시
* unsupported_or_unknown이 있으면 별도 표시
* 최종 리포트는 짧은 문장 나열이 아니라 스카우팅 코멘트처럼 읽히게 함

최종 리포트 구성 권장:

1. 선수 요약
2. 데이터 기반 강점
3. 데이터 기반 보완점
4. 성장 시나리오 해석
5. 정성 텍스트 근거
6. Gemini 보조 추천
7. 근거 부족/주의점
8. 최종 스카우팅 코멘트

---

## 12. 설명 생성 시 금지사항

* 실제 데이터에 없는 사실을 만들지 말 것
* Gemini 결과를 DB 사실처럼 표현하지 말 것
* FM proxy를 실제 경기 데이터처럼 표현하지 말 것
* style_vector를 실제 위치 이벤트 데이터처럼 표현하지 말 것
* 정성 텍스트가 없는데 “기사에서 언급됨”이라고 쓰지 말 것
* 모든 선수에게 같은 템플릿 문구만 반복하지 말 것
* 너무 짧은 한 줄 설명으로 끝내지 말 것

---

## 13. 설명 근거 표시 UI

강점/약점/추천 텍스트에는 가능한 경우 근거 badge를 함께 표시한다.

예:

* `FM proxy`
* `Growth Model`
* `Transfermarkt`
* `User text`
* `Gemini advisory`
* `style_vector`
* `Rule-based`

UI 방식:

* 카드 상단 또는 문단 하단에 작은 source badge 표시
* 자세한 계산 근거는 expander에 유지
* 메인 설명에는 사용자가 이해할 수 있는 자연어 중심

---

# PART D. 최종 산출물

## 14. CLEANUP_AUDIT_REPORT.md 생성

이번 작업 후 다음 파일을 생성한다.

```text
CLEANUP_AUDIT_REPORT.md
```

보고서에는 다음을 포함한다.

1. 작업 전 git status 요약
2. 정리한 파일 목록
3. 이동한 파일 목록
4. 삭제하지 않고 남긴 후보 파일 목록
5. 실제 앱에서 import되는 핵심 파일 목록
6. 중복/이상 코드 점검 결과
7. UI components/styles 구조 점검 결과
8. app.py 비대화 여부
9. 입력 UI 개선 내용
10. 강점/약점/추천 텍스트 고도화 내용
11. use_container_width warning 정리 여부
12. 테스트 결과
13. Streamlit health check 결과
14. 사용자가 수동으로 확인해야 할 항목
15. 다음 최종 polish 후보

---

## 15. 문서 업데이트

작업 후 아래 문서를 업데이트한다.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `ACTIVE_FUNCTION_MAP.md`
3. `REAL_MODEL_PLAN.md`
4. `AGENTS.md`

섹션명:

```text
v19 Final Polish and Cleanup: repository hygiene, selector inputs, and evidence-based explanations
```

포함 내용:

* 정리한 파일 구조
* 입력 UI 개선
* 포지션/국적/팀/주발 선택형 UI
* 설명 텍스트 근거 기반 고도화
* components/styles 구조 점검
* 테스트 결과
* 남은 cleanup 후보

주의:

* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않는다.

---

## 16. 테스트 요구사항

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

## 17. 절대 금지

* DB 스키마 변경 금지
* `create_and_upload_db.py` 수정 금지
* `secrets.toml` 내용 출력 금지
* `.env` 내용 출력 금지
* API key 값 출력/저장/문서화 금지
* 원본 CSV 수정 금지
* 뉴스 자동 크롤링 구현 금지
* 10x10 Grid 구현 금지
* Growth/Ceiling 공식 변경 금지
* 기존 JSONB key 삭제 금지
* legacy fallback 삭제 금지
* Gemini에게 점수 계산 맡기기 금지
* Gemini가 없는 사실을 지어내게 하기 금지
* app.py 대형화 금지
* Football Manager 고유 로고/이미지/에셋 복제 금지
* 기존 session_state key 삭제 금지
* 실제 import되는 코드 파일 임의 삭제 금지
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md` 수정 금지
* 데이터에 없는 강점/약점을 지어내는 것 금지

---

## 18. 완료 보고 형식

완료 후 아래 형식으로 보고한다.

1. 수정한 코드 파일
2. 삭제한 파일
3. 이동한 파일
4. 새로 만든 문서 파일
5. 수정한 문서 파일
6. 정리하지 않고 남긴 후보 파일
7. 입력 UI 개선 내용
8. 포지션/국적/팀/주발 선택형 UI 구현 내용
9. 강점/약점/추천 텍스트 고도화 내용
10. 설명 근거 표시 방식
11. Style & Mentor Lab 설명 고도화 내용
12. Career Simulation 설명 고도화 내용
13. Evidence & Advisory Report 설명 고도화 내용
14. 코드 중복/이상 부분 점검 결과
15. components/styles 구조 점검 결과
16. app.py 비대화 여부
17. use_container_width warning 정리 여부
18. 기존 기능 보존 여부
19. session_state 영향 여부
20. 테스트 결과
21. Streamlit health check 결과
22. CLEANUP_AUDIT_REPORT.md 주요 내용
23. 사용자가 직접 확인해야 할 항목
24. 남은 문제
