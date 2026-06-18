# V19_PRODUCT_REDESIGN_SPEC.md

## 1. 목적

v19의 목표는 NEXT-LEGEND FINDER를 기능 모음이 아니라 **Football Manager 스타일의 유망주 스카우팅 센터**로 재구성하는 것이다.

이번 문서는 구현 명세가 아니라 제품/UX/분석 흐름 재설계 명세다. 코드, DB 스키마, Growth/Ceiling 공식, secrets, 원본 데이터는 이 단계에서 수정하지 않는다.

## 2. 현재 구조 진단

현재 앱은 v18.3 기준으로 핵심 기능이 많이 구현되어 있다. 선수 검색, Growth 분석, style_vector 기반 유사 선수/멘토, Career Simulation, 규칙 기반 리포트, Gemini 정성 신호 추출, Notes 저장/조회, manual_prospect 흐름이 존재한다.

하지만 제품 경험 관점에서는 다음 문제가 크다.

1. 분석 가능한 유망주와 제한 분석 선수의 기본 진입 흐름이 아직 충분히 분리되지 않는다. Transfermarkt-only, 고연령, FM profile/style_vector 없음 선수는 기본 스카우팅 서비스의 중심 대상이 아니어야 한다.
2. 선수 카드와 Growth Model의 데이터 표현이 한때 불일치했던 것처럼, 데이터 커버리지와 분석 가능성이 화면의 첫 번째 정보로 더 강하게 드러나야 한다.
3. Dashboard / Mentor / Simulation / Report가 기능별 페이지로 느껴지고, 하나의 스카우팅 워크플로우로 이어지는 감각이 약하다.
4. Gemini 기능은 구현되어 있지만 전체 분석 흐름 안에서 “정성 텍스트 근거를 구조화하고 보조 추천을 붙이는 역할”이 더 명확히 배치되어야 한다.
5. Football Manager식 스카우팅 센터의 정보 밀도, dossier 중심 구조, 다음 행동 CTA가 부족하다.

## 3. v19 제품 컨셉

제품 컨셉은 **선수 하나를 중심으로 이어지는 Scouting Dossier Workflow**다.

기본 흐름:

```text
Scouting Board
-> Player Dossier
-> Style & Mentor Lab
-> Career Simulation
-> Evidence & Advisory Report
-> My Scouting Notes
```

직접 입력 유망주 흐름:

```text
Manual Prospect
-> Player Dossier
-> Career Simulation
-> Evidence & Advisory Report
-> My Scouting Notes
```

제한 분석 선수 흐름:

```text
Scouting Board에서 Limited badge 표시
-> Player Dossier에서 데이터 부족 안내
-> Style & Mentor Lab 진입 제한
-> Manual Prospect 보완 또는 Scouting Board 복귀 유도
```

## 4. 메뉴 구조

권장 메뉴명:

- Home
- Scouting Board
- Player Dossier
- Style & Mentor Lab
- Career Simulation
- Evidence & Advisory Report
- Notes
- Manual Prospect
- DB Status

기존 구현명과의 대응:

| 현재 화면 | v19 권장명 | 역할 |
|---|---|---|
| Home | Home / Scouting Center | 스카우팅 로비 |
| Prospect Search | Scouting Board | 분석 가능한 유망주 탐색 |
| Dashboard | Player Dossier | 선택 선수의 중심 분석 허브 |
| Legend Matching | Style & Mentor Lab | 유사 선수/멘토 분석 |
| Career Simulation | Career Simulation | 성장 시나리오 실험 |
| AI Report | Evidence & Advisory Report | 규칙 기반 리포트 + 정성/Gemini 보조 |
| My Scouting Notes | Notes | 저장 노트 조회 |
| 직접 입력 유망주 | Manual Prospect | DB 외 유망주 생성 |

## 5. 화면별 명세

### 5.1 Home / Scouting Center

역할:
- 서비스 시작 화면
- 현재 선택 선수 상태 표시
- 주요 워크플로우 진입 로비

필수 정보:
- 서비스명
- 현재 선택 선수 요약
- 데이터 출처 요약
- 최근/현재 작업 상태
- 주요 기능 카드

기능 카드:
- Scouting Board 열기
- Manual Prospect 생성
- Notes 보기
- DB Status 확인

Home은 소개 페이지가 아니라 “스카우팅 센터 로비”처럼 동작해야 한다.

### 5.2 Scouting Board

역할:
- 분석 가능한 유망주를 찾는 기본 화면
- 제한 분석 선수는 기본 검색 결과에서 최대한 배제

기본값:
- 분석 가능한 유망주만 보기 ON
- 권장 나이 범위는 15~23 또는 15~25 중 사용자 결정 필요
- FM profile 또는 style_vector가 있는 선수 중심
- Transfermarkt-only / 고연령 / profile 없음 선수는 기본 결과에서 제외

필터:
- 이름
- 포지션
- 나이 범위
- 시장가치 범위
- 분석 준비도: Full / Partial / Limited
- FM profile 있음
- style_vector 있음
- 전체 DB 선수 포함

선수 카드:
- 이름
- 나이
- 포지션
- 팀
- 국적
- 현재 시장가치
- 최근 출전 정보
- FM profile 여부
- style_vector 여부
- 분석 준비도 badge
- 왜 이 선수가 후보인지 설명

카드 CTA:
- 이 선수 분석하기
- 데이터 커버리지 보기

### 5.3 Player Dossier

역할:
- 선택 선수의 메인 분석 허브
- 현재 무엇을 알고 있고 무엇을 모르는지 보여주는 화면
- 다음 분석으로 넘어갈지 판단하는 화면

구성:

1. 선수 헤더 카드
   - 사진 또는 placeholder
   - 이름
   - 나이
   - 포지션
   - 팀
   - 국적
   - 데이터 모드
   - 분석 준비도 badge
   - 현재 시장가치
   - 최고 시장가치

2. Data Coverage Panel
   - 선수 기본정보
   - 나이
   - 시장가치 데이터
   - 출전 기록
   - FM profile
   - style_vector
   - FM 멘탈 속성 proxy
   - 정성 텍스트 분석
   - Gemini 보조 추천

3. Growth Insight
   - Growth Score
   - 구성 요소별 기여도
   - 점수가 높은/낮은 이유
   - 제한 분석인 경우 명확한 안내

4. Player Identity
   - 포지션 역할 요약
   - FM 능력치 기반 강점
   - FM 기반 멘탈 지표 proxy
   - 데이터 부족 항목

5. Next Action Panel
   - Style & Mentor Lab으로 이동
   - Career Simulation으로 이동
   - Evidence & Advisory Report로 이동
   - Notes로 이동

### 5.4 Style & Mentor Lab

역할:
- 24D style_vector와 pgvector cosine similarity 기반 유사 선수/멘토 후보를 보여준다.
- 어린 유망주에게 적합한 멘토를 추천한다.

진입 조건:
- FM profile 필요
- style_vector 필요
- 없으면 유사도 계산을 실행하지 않고 안내만 표시

구성:
- 현재 선수 스타일 요약
- 유사 선수 후보 카드
- 멘토 후보 카드
- 멘토 선택 후 다음 행동 CTA

멘토 후보 규칙:
- 자기 자신 제외
- 나이 없음/0세 제외
- 기본 기준: `max(28, target_age + 5)`
- 완화 기준: `max(26, target_age + 3)`
- 완화 기준 사용 시 “조건을 완화해 표시한 후보입니다.” 안내

### 5.5 Career Simulation

역할:
- Growth baseline 위에 커리어 시나리오를 적용해 Final Growth Score를 보여준다.
- 단순 점수 화면이 아니라 선택의 영향과 리스크를 설명하는 화면이어야 한다.

구성:

1. Baseline Summary
   - 현재 Growth Score
   - 데이터 기반 강점
   - 데이터 기반 리스크

2. Scenario Controls
   - 훈련 강도
   - 출전 기회
   - 리그 수준
   - 리스크 성향
   - 커리어 선택

3. Scenario Result
   - Baseline Growth Score
   - Scenario Adjustment
   - Final Growth Score
   - 상승/하락 이유
   - 리스크 경고

4. Coaching Recommendation
   - 추천 훈련 방향
   - 출전 관리 전략
   - 리그 이동/잔류 판단
   - 리스크 관리

5. Save / Next
   - Evidence & Advisory Report로 이동
   - 현재 시뮬레이션을 Notes에 저장

### 5.6 Evidence & Advisory Report

역할:
- 최종 스카우팅 리포트 초안을 생성한다.
- DB/FM proxy/rule-based 분석과 사용자가 입력한 정성 텍스트를 결합한다.
- Gemini는 정성 신호 추출과 보조 추천만 수행한다.

구성:

1. Rule-based Report Summary
   - Growth/Ceiling 기반 규칙 리포트 초안
   - 데이터 출처 표시

2. Qualitative Text Input
   - 기사, 스카우팅 메모, 감독 인터뷰, 관찰 메모 입력
   - 입력 예시 expander
   - 입력 없으면 기존 DB/FM proxy 분석만 사용

3. Gemini Qualitative Signal Extraction
   - playing_time_signal
   - injury_risk_signal
   - coach_trust_signal
   - development_signal
   - transfer_rumor_signal
   - mentality_signal
   - strength_mentions
   - weakness_mentions
   - risk_mentions
   - recommended_focus
   - evidence_quotes
   - confidence

4. Gemini Advisory Report
   - advisory_summary
   - player_fit_assessment
   - training_recommendations
   - career_recommendations
   - risk_management
   - mentor_usage_recommendations
   - what_to_monitor_next
   - unsupported_or_unknown
   - final_scouting_comment
   - confidence

5. Final Report Preview
   - 규칙 기반 분석
   - 정성 텍스트 근거
   - Gemini 보조 추천
   - 근거 부족 항목
   - 최종 스카우팅 코멘트

6. Save to Notes
   - `scouting_notes`에 저장
   - `qualitative_evidence`, `gemini_advisory`, `report_generation_mode` 포함

금지:
- Gemini가 Growth/Ceiling 점수를 계산하지 않는다.
- Gemini가 Growth/Ceiling 결과를 대체하지 않는다.
- Gemini가 텍스트에 없는 사실을 만들어내지 않는다.

### 5.7 Notes

역할:
- 저장된 분석 기록 조회 전용
- 새 유망주 생성 폼을 포함하지 않는다.

목록 표시:
- 선수 이름
- 저장 시점
- note_type
- entity_type
- report_generation_mode
- Growth Score
- Final Growth Score
- Gemini 사용 여부
- 정성 텍스트 포함 여부

상세 표시:
- 저장 당시 선수 snapshot
- 저장 당시 Data Coverage
- Growth/Ceiling 결과
- 정성 텍스트 근거
- Gemini 보조 추천
- 최종 리포트
- 개발자용 JSON expander

### 5.8 Manual Prospect

역할:
- DB에 없는 유망주를 직접 입력
- 생성 후 실제 DB 선수와 유사한 분석 흐름으로 이동

입력 항목:
- 이름
- 나이
- 포지션
- 팀
- 국적
- 주발
- 키/몸무게 optional
- 기본 능력치
- 멘탈 proxy 값
- 현재 리그 수준
- 예상 출전 기회

생성 후:
- `selected_entity_type = "manual_prospect"`
- `player_id = None`
- `profile_id = None`
- Player Dossier로 이동
- 이후 Career Simulation, Evidence & Advisory Report, Notes 저장 흐름 사용

## 6. 분석 알고리즘 명세

### 6.1 Prospect Eligibility Filter

목적:
- 기본 검색 결과에서 분석 가능한 유망주를 우선 노출

권장 기준:
- 나이 15~23 또는 15~25
- profile 있음
- style_vector 있음 또는 FM attribute 있음
- 시장가치/출전 데이터 일부 이상 있음

결과 분류:
- `eligible`: 기본 결과 노출
- `limited`: 전체 DB 포함 옵션에서 노출
- `excluded_by_default`: 기본 결과에서 제외

### 6.2 Data Coverage Classifier

분류:

| 등급 | 조건 |
|---|---|
| full | DB + age + valuation + appearances + FM profile + style_vector |
| partial | 일부 핵심 데이터는 있으나 FM profile/style_vector/출전/시장가치 중 일부 부족 |
| limited | Transfermarkt-only 또는 핵심 데이터 부족 |
| manual_prospect | 직접 입력 유망주 |

현재 `player_coverage.build_data_coverage()`와 `resolve_player_age()`를 중심으로 유지한다.

### 6.3 Growth Model

현재 구현을 유지한다.

표시 원칙:
- 점수 구성 요소를 보여준다.
- 데이터 부족으로 제외된 항목을 보여준다.
- 제한 분석이면 점수보다 데이터 한계를 먼저 설명한다.

### 6.4 Style Similarity

현재 구현을 유지한다.

원칙:
- FM 기반 24D `style_vector` 사용
- pgvector cosine similarity 사용
- style_vector가 없으면 실행하지 않는다.

### 6.5 Mentor Recommendation

현재 구현의 나이 필터를 유지한다.

원칙:
- similarity score 기반 후보 정렬
- 자기 자신 제외
- 나이 정보 없는 후보 제외
- 너무 어린 후보 제외
- 완화 기준 적용 여부 표시

### 6.6 Ceiling Simulation

현재 구현을 유지한다.

원칙:
- Growth baseline 유지
- 시나리오 조건으로 보정
- Scenario Adjustment는 ±15 범위 유지
- Final Growth Score는 0~100 범위 유지
- Gemini는 계산에 개입하지 않는다.

### 6.7 Qualitative Evidence Extraction

원칙:
- 사용자가 입력한 텍스트만 Gemini가 구조화한다.
- 텍스트가 없으면 정성 분석 없음으로 표시한다.
- evidence quote와 unsupported 항목을 명확히 둔다.

### 6.8 Gemini Advisory

원칙:
- DB/FM proxy/Growth/Ceiling/정성 신호를 종합해 보조 추천만 생성한다.
- 점수 계산과 사실 판정은 하지 않는다.
- 없는 사실은 `unsupported_or_unknown`에 둔다.

## 7. 데이터 출처 및 라벨링 원칙

- 선수 기본 정보: DB, Transfermarkt 기반
- 시장가치/출전 기록: DB, Transfermarkt 기반
- 능력치: FM proxy profile
- 멘탈 지표: FM 기반 멘탈 속성 proxy
- Growth Score: rule-based Growth Model
- Ceiling 보정: rule-based Ceiling Model
- 리포트 초안: 규칙 기반 리포트 + 선택적 Gemini 보조
- 정성 텍스트 근거: 사용자가 입력한 텍스트가 있을 때만 표시
- Gemini 분석: 실제 호출 성공 시에만 표시

## 8. UI 원칙

- Football Manager식 어두운 스카우팅 센터 톤 유지
- 선택 선수 중심 헤더를 모든 분석 화면 상단에 유지
- Full / Partial / Limited / Manual badge를 일관되게 사용
- 데이터 부족을 숨기지 않는다.
- 기술 용어와 공식은 기본 화면이 아니라 상세 계산 근거 expander에 둔다.
- 각 화면에는 다음 행동 CTA가 있어야 한다.
- 같은 정보는 공통 helper를 통해 일관되게 표시한다.
- “AI Report”보다 “Evidence & Advisory Report” 또는 “분석 리포트 초안” 표현을 우선한다.

## 9. 구현 계획

### Phase 1: Search와 데이터 준비도 정리

예상 파일:
- `player_coverage.py`
- `views/prospect_search.py`
- `ui_components.py`
- 관련 테스트

내용:
- Data Coverage 표시 강화
- Scouting Board 기본 필터 재정리
- Full/Partial/Limited badge 일관화

테스트:
- `python -m compileall .`
- `python test_prospect_search_split.py`
- `python test_growth_model.py`

위험:
- 기본 검색 결과가 너무 좁아질 수 있음

사용자 확인:
- 기본 유망주 나이 기준
- limited 선수 기본 노출 여부

### Phase 2: Player Dossier 재구성

예상 파일:
- `views/dashboard.py`
- `ui_components.py`
- `player_coverage.py`

내용:
- Dashboard를 Player Dossier로 재설계
- Data Coverage Panel 강화
- Next Action Panel 명확화

테스트:
- `python -m compileall .`
- `python test_growth_model.py`

위험:
- 기존 session_state 갱신 규칙 훼손 위험

사용자 확인:
- 메뉴명을 실제로 변경할지 여부

### Phase 3: Style & Mentor Lab 개선

예상 파일:
- `views/legend_matching.py`
- `manual_prospect_helpers.py`

내용:
- 유사 선수와 멘토 후보를 분리해 표시
- 나이 필터와 fallback 안내 강화

테스트:
- `python -m compileall .`
- `python test_growth_model.py`

위험:
- style_vector 없는 선수의 UX가 막힌 것처럼 느껴질 수 있음

### Phase 4: Career Simulation 개선

예상 파일:
- `views/career_simulation.py`
- `explanation_engine.py`

내용:
- Baseline / Scenario / Coaching Recommendation 구조 강화
- 계산 근거 expander 정리

테스트:
- `python -m compileall .`
- `python test_growth_model.py`

위험:
- Growth/Ceiling 공식은 절대 변경하지 않아야 함

### Phase 5: Evidence & Advisory Report 개선

예상 파일:
- `views/ai_report.py`
- `services/qualitative_evidence.py`
- `scouting_note_payload.py`

내용:
- “AI Report” 표현 축소
- 정성 텍스트 입력, Gemini 신호 추출, 보조 추천의 단계 분리
- Final Report Preview 구조 개선

테스트:
- `python -m compileall .`
- `python test_growth_model.py`

위험:
- Gemini 결과가 점수처럼 오해될 수 있음

### Phase 6: Notes UI 개선

예상 파일:
- `views/scouting_notes.py`
- `scouting_note_payload.py`

내용:
- 저장 노트 목록과 상세 구조 개선
- 저장 시점 Data Coverage와 Gemini 사용 여부 표시

테스트:
- `python -m compileall .`
- `python test_growth_model.py`

위험:
- legacy fallback 훼손 위험

### Phase 7: QA와 문서 최신화

실행 테스트:
- `python -m compileall .`
- `python test_state_refactor.py`
- `python test_analysis_helpers_split.py`
- `python test_prospect_search_split.py`
- `python test_growth_model.py`
- Streamlit headless health check

문서:
- `CLAUDE_PROGRESS_SUMMARY.md`
- `ACTIVE_FUNCTION_MAP.md`
- `REAL_MODEL_PLAN.md`
- `AGENTS.md`

## 10. 구현 전 사용자 결정사항

1. 기본 유망주 나이 기준을 15~23으로 할지, 15~25로 할지 결정해야 한다.
2. FM profile 없는 선수를 기본 검색에서 완전히 숨길지, limited로 표시할지 결정해야 한다.
3. 기존 Dashboard 메뉴명을 Player Dossier로 실제 변경할지 결정해야 한다.
4. 기존 AI Report 메뉴명을 Evidence & Advisory Report로 실제 변경할지 결정해야 한다.
5. UI 톤을 지금보다 더 강한 Football Manager식 어두운 cockpit 스타일로 밀지 결정해야 한다.
6. 제한 분석 선수에게 Manual Prospect로 보완 입력하는 흐름을 제공할지 결정해야 한다.
7. Gemini 보조 추천을 최종 리포트에서 어느 정도 강하게 노출할지 결정해야 한다.
8. Scouting Board 기본 결과에서 `partial`을 포함할지, `full`만 노출할지 결정해야 한다.
9. Notes 화면에서 개발자용 JSON expander를 얼마나 숨길지 결정해야 한다.

## 11. 비범위

이번 v19 명세 또는 후속 구현에서 사용자 승인 없이 하지 않는다.

- DB 스키마 변경
- `create_and_upload_db.py` 수정
- `.streamlit/secrets.toml` 또는 `.env` 출력/수정
- 원본 CSV 수정
- Growth/Ceiling 공식 변경
- JSONB 기존 key 삭제
- legacy fallback 삭제
- Gemini 점수 계산
- 뉴스 자동 크롤링
- 10x10 Grid 구현

## 12. 승인 후 구현 방식

사용자가 이 명세를 승인하면 Phase 단위로 구현한다. 각 Phase는 작게 나누어 진행하며, 코드 변경 후 프로젝트 규칙의 필수 테스트와 Streamlit health check를 수행한다.
