# FINAL IMPLEMENTATION ROADMAP

NEXT-LEGEND FINDER 프로젝트의 "제출용 프로토타입"과 "원래 기획했던 기술 요소" 사이의
간극을 정리하고, 이번 세션에서 작동 가능한 축소판으로 구현한 범위 및 향후 개발로
남길 범위를 명확히 구분하기 위한 문서입니다.

---

## 1. 현재 구현 완료된 기능

### 1.1 데이터/조회 계층
- Supabase/Postgres 연결 및 쿼리 헬퍼 (`services/db.py`: `query_df`, `query_one`,
  `execute_one`, `get_player`, `get_profile_by_player_id`, `get_player_profile`,
  `get_similar_players`, `get_valuations`, `get_appearances`,
  `get_prospect_diagnostics`, `insert_scouting_note`, `get_scouting_notes` 등)
- pgvector 기반 FM proxy `style_vector`(24차원) 코사인 유사도 검색 (`get_similar_players`)

### 1.2 선수 선택/컨텍스트 관리
- `app.py`의 `resolve_selected_player_context()` 기반 `selected_player_id` /
  `selected_profile_id` / `entity_type` 결정 로직
- `entity_type` 4종: `matched`, `fm_profile_only`, `transfermarkt_only`,
  `manual_note` (`state.py`의 `ENTITY_TYPE_LABELS`, `DATA_MODE_BADGE_CLASS`)

### 1.3 화면 (views/*.py, app.py 라우팅)
- 홈 / 서비스 소개
- 유망주 검색 (`views/prospect_search.py`)
- 유망주 통합 분석 대시보드 (`views/dashboard.py`)
- 유사 선수 후보 / 멘토 매칭 (`views/legend_matching.py`, FM proxy `style_vector` 기반)
- 커리어 시뮬레이션 (`views/career_simulation.py`, `analysis_helpers.build_simulation_result`)
- AI 스카우팅 리포트 (`views/ai_report.py`, 템플릿 기반 텍스트 생성)
- 내 스카우팅 노트 (`views/scouting_notes.py`, `insert_scouting_note`/`get_scouting_notes`)
- DB 상태 확인 (`views/db_status.py`)

### 1.4 분석 헬퍼
- `analysis_helpers.py`: 능력치 파싱/그룹화/요약 (`parse_json_field`, `attributes_long_df`,
  `summary_scores`, `group_analysis`), 강점/약점 문장 생성, 멘토 유사도 설명
  (`generate_similarity_reason`, `generate_mentor_guide`), 커리어 시뮬레이션 결과 생성
  (`build_simulation_result`)

### 1.5 테스트
- `test_state_refactor.py`, `test_analysis_helpers_split.py`, `test_prospect_search_split.py`:
  AppTest 기반 헤드리스 회귀 테스트 (홈/대시보드/멘토 매칭/시뮬레이션/리포트/노트 전체 플로우,
  matched/transfermarkt_only/manual_note 데이터 타입별 시나리오)

---

## 2. 아직 구현되지 않은 원래 기획 기능

원래 기획(`archive/docs/CLAUDE_TASK_FULL.md` 35장 "데이터 엔지니어링 확장 설계") 기준으로,
다음 기능들은 **이번 세션 이전까지 전혀 구현되지 않았던** 항목입니다.

1. **실제 10x10 Grid 기반 플레이스타일 벡터(100차원)**
   - 실제 경기 위치 이벤트(x, y 좌표) 수집 → `player_grid_vectors`(vector(100),
     `vector_type='10x10_event_grid'`, `grid_size=10`) 테이블 적재 → pgvector 유사도 검색
2. **기사/스카우팅 리포트 기반 mentality evidence**
   - 대량 기사 크롤링 → `player_article_sources` 적재 → Gemini 기반 9개 category
     evidence 추출 → `player_mentality_evidence` 테이블 적재
3. **Gemini API 실제 연동**
   - `GEMINI_API_KEY` 기반 실제 LLM 호출로 AI 스카우팅 리포트, evidence 추출,
     멘토링 가이드 등을 생성
4. **Career Simulation 고도화 (실제 ML 기반)**
   - 실제 성장 예측 모델(통계/ML)을 활용한 성장 곡선, 성공률, 부상 리스크 산출
5. **Supabase Auth / RLS**
   - 사용자별 로그인, 역할(스카우트/관리자 등) 기반 행 단위 접근 제어
6. **대규모 이벤트 데이터 수집**
   - 전체 선수 대상 경기 이벤트 데이터 파이프라인 (외부 API/크롤링)
7. **대규모 기사 크롤링**
   - 다수 매체에서 선수 관련 기사를 자동 수집/저장하는 파이프라인

---

## 3. 이번 세션(최종 버전)에서 실제 구현한 기능 — "작동 가능한 축소판"

원래 기획 항목을 **샘플 데이터 / 사용자 입력 기반의 작동 가능한 축소판**으로
구현했습니다. 모든 기능은 새 화면 **"실험실 (Data Lab)"** (`views/experimental_data_lab.py`)
에서 확인할 수 있습니다.

### 3.1 10x10 Grid Vector 샘플 파이프라인 (`grid_pipeline.py`)
- `data_samples/event_grid_sample.csv`: 샘플 선수 5명(가상 이름/팀)의 이벤트
  좌표(x, y, event_type, minute) 165건
- `normalize_coordinate`, `get_grid_index`, `build_grid_vector`,
  `normalize_grid_vector`, `grid_vector_to_heatmap`, `summarize_grid_style`,
  `list_sample_players` 등 순수 함수로 100차원 벡터 생성/정규화/요약
- Data Lab 화면에서 샘플 선수 선택 → 10x10 heatmap (Altair) → Top 5 활동 구역 →
  100차원 벡터 원본 값(JSON) 표시
- "유사 선수 후보"의 24차원 FM proxy `style_vector`와 100차원 grid vector가
  서로 다른 데이터임을 화면에 명시

### 3.2 기사/스카우팅 문장 기반 Mentality Evidence (`evidence_extractor.py`)
- 입력: `player_name`, `source_title`, `source_url`, `snippet_or_text` (모두 사용자 입력)
- 9개 category: `determination`, `work_rate`, `professionalism`,
  `pressure_handling`, `leadership`, `teamwork`, `injury_concern`,
  `discipline`, `adaptability`
- Gemini 미사용/실패 시 rule-based 키워드 매칭(영/한)으로 category별
  score/confidence(낮음) + `evidence_summary` 생성
- Gemini 사용 시 동일 스키마의 JSON을 LLM에 요청, 파싱 실패 시 자동 fallback
- DB 저장 없음 (session_state + 화면 표시만)

### 3.3 Gemini API Optional 연동 구조 (`gemini_client.py`)
- `get_gemini_api_key()`: `st.secrets["GEMINI_API_KEY"]` →
  `st.secrets["GOOGLE_API_KEY"]` → 환경변수 `GEMINI_API_KEY` →
  환경변수 `GOOGLE_API_KEY` 순으로 탐색 (값은 출력하지 않음)
- `is_gemini_available()`: key 존재 + `google-generativeai` 설치 여부 확인
- `generate_gemini_content(prompt)`: 1회 호출, 실패 시 `success=False` + 사유 반환
  (호출부가 fallback 수행)
- 현재 `.streamlit/secrets.toml`에는 `SUPABASE_DB_URL`만 있어 Gemini는 항상
  fallback 경로로 동작 — Data Lab "Gemini API / Fallback Status" 섹션에서 확인 가능

### 3.4 Career Simulation 설명력 강화 (`analysis_helpers.build_simulation_breakdown`)
- 성장 점수(45 + 훈련 강도 + 출전 기회 + 리그 난이도 보정 + 커리어 선택 보정 +
  리스크 성향 보정) 구성 요소를 표로 표시
- 기회/리스크 요약 문장 (`opportunity_text`, `risk_text`)
- 멘토 선택 시(`selected_mentor_name`) 멘토 유사도 참고 설명 (시뮬레이션 계산에는
  직접 반영되지 않음을 명시)
- `entity_type`(matched/fm_profile_only/transfermarkt_only/manual_note)별
  데이터 해석 제한 안내 (`ENTITY_TYPE_SIMULATION_NOTES`)

### 3.5 Experimental Data Lab 화면 (`views/experimental_data_lab.py`)
- 1. 10x10 Grid Vector Demo
- 2. Article Evidence Demo
- 3. Gemini API / Fallback Status
- 4. Data Engineering Pipeline 설명 (원래 기획 vs 이번 구현 비교 표)
- `app.py` 메뉴("실험실 (Data Lab)") + `ui_components.py`의 `NAV_TARGETS`/
  `NAV_CHIP_LABELS`("Lab")에 등록되어 사이드바/네비게이션 칩에서 접근 가능

---

## 4. 향후 개발로 남길 기능

다음 항목들은 이번 세션 범위(Supabase 스키마 변경 금지, 크롤링 금지, 대량 API
호출 금지)를 벗어나며, 별도 세션에서 스키마 설계/승인을 거쳐 진행해야 합니다.

1. **전체 선수 대상 이벤트 데이터 수집 및 `player_grid_vectors`(vector(100)) 테이블 적재**
   - 외부 이벤트 데이터 제공처 계약/수집 파이프라인 필요
2. **대규모 기사 크롤링 및 `player_article_sources` 테이블 적재**
   - 크롤링 정책/저작권 검토 필요
3. **Gemini 기반 자동 mentality evidence 추출 파이프라인 + `player_mentality_evidence` 적재**
   - 현재 `evidence_extractor.py`의 추출 함수는 그대로 재사용 가능,
     "자동 배치 호출 + DB 저장" 부분만 추가 필요
4. **실제 ML 기반 성장 예측 모델**
   - 과거 유망주 → 성인 선수 성장 데이터셋 구축 및 모델 학습 필요
5. **Supabase Auth / RLS 및 사용자별 권한 분리**
   - 로그인/세션 관리, 역할별 정책(RLS) 설계 필요
6. **Football Manager 자산을 사용하지 않는 범위 내에서 grid vector ↔ FM proxy
   style_vector 통합 유사도 모델**

---

## 5. 구현 우선순위 (이번 세션 기준)

1. `grid_pipeline.py` + `data_samples/event_grid_sample.csv` (10x10 Grid 샘플)
2. `gemini_client.py` (Gemini optional wrapper — 다른 기능의 의존성)
3. `evidence_extractor.py` (Gemini wrapper에 의존)
4. `views/experimental_data_lab.py` + `app.py`/`ui_components.py` 라우팅
5. `analysis_helpers.build_simulation_breakdown` + `views/career_simulation.py` 개선
6. 테스트 (`test_experimental_data_lab.py` 추가, 기존 회귀 테스트 재실행)
7. 문서 갱신 (`CLAUDE_PROGRESS_SUMMARY.md`, `ACTIVE_FUNCTION_MAP.md`,
   본 로드맵 문서)

---

## 6. 필요한 파일 구조 (이번 세션에서 추가/변경된 파일)

```
Database_Project/
├── data_samples/
│   └── event_grid_sample.csv          (신규: 10x10 grid 샘플 이벤트 데이터)
├── grid_pipeline.py                    (신규: 10x10 grid 변환 순수 함수)
├── gemini_client.py                    (신규: Gemini optional wrapper)
├── evidence_extractor.py               (신규: mentality evidence 추출)
├── views/
│   ├── experimental_data_lab.py        (신규: Experimental Data Lab 화면)
│   └── career_simulation.py            (수정: breakdown 표시 추가)
├── analysis_helpers.py                 (수정: build_simulation_breakdown 추가)
├── ui_components.py                    (수정: NAV_TARGETS/NAV_CHIP_LABELS에 Lab 추가)
├── app.py                              (수정: Data Lab 라우팅 + 시뮬레이션 entity_type 전달)
├── test_experimental_data_lab.py       (신규: Data Lab AppTest)
└── FINAL_IMPLEMENTATION_ROADMAP.md     (신규: 본 문서)
```

---

## 7. 테스트 계획

### 7.1 정적/회귀 테스트 (이번 세션에서 실행 완료)
- `python -m compileall .` — 전체 모듈 컴파일 확인
- `python test_state_refactor.py` — 3개 테스트 OK
- `python test_analysis_helpers_split.py` — 4개 테스트 OK
- `python test_prospect_search_split.py` — 2개 테스트 OK
- `streamlit run app.py` 헤드리스 기동 확인 — 에러 없이 기동

### 7.2 신규 Data Lab 테스트 (`test_experimental_data_lab.py`, 실행 완료)
- Data Lab 화면 진입 시 4개 섹션(subheader) 모두 렌더링되는지 확인
- 샘플 이벤트 데이터 로드 및 샘플 선수 selectbox 기본값 확인
- 10x10 heatmap(Altair `vega_lite_chart`) 렌더링 확인
- Article Evidence Demo: 텍스트 입력 → "Evidence 추출 실행" 버튼 클릭 →
  rule-based fallback 결과(determination/work_rate/pressure_handling score > 0) 확인
- Gemini API key가 없는 현재 환경에서도 앱이 크래시 없이 fallback 상태를 표시하는지 확인

### 7.3 향후 추가 테스트 (다음 세션 권장)
- Gemini API key가 설정된 환경에서 `extract_mentality_evidence(use_gemini=True)`의
  JSON 파싱/필드 매핑 단위 테스트 (현재는 key가 없어 fallback 경로만 검증됨)
- 실제 이벤트 데이터/기사 데이터가 추가될 경우, `grid_pipeline`/`evidence_extractor`의
  대규모 입력에 대한 성능/정확도 테스트
