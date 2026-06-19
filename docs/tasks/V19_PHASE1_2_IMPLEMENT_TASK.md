# V19_PHASE1_2_IMPLEMENT_TASK.md

## 0. 작업 목적

이 프로젝트는 `c:\Users\nhy81\Desktop\Database_Project`의 NEXT-LEGEND FINDER Streamlit + Supabase 프로젝트이다.

현재 `V19_PRODUCT_REDESIGN_SPEC.md` 작성이 완료되었다.

이번 작업은 v19 전체 구현이 아니다.

이번 작업의 범위는 v19 Phase 1~2만 구현하는 것이다.

목표:

1. Scouting Board를 분석 가능한 유망주 중심 화면으로 정리
2. Player Dossier를 선택 선수 중심 분석 허브로 재구성
3. Data Coverage badge/panel을 공통화
4. Limited 선수와 Full/Partial 선수를 UI에서 명확히 구분
5. 화면 전환 CTA를 정리
6. 기존 Growth/Ceiling/Gemini/Notes 흐름을 깨뜨리지 않음

---

## 1. 현재 기준

현재 프로젝트 기준:

* v18.3까지 구현 완료
* `V19_PRODUCT_REDESIGN_SPEC.md` 작성 완료
* `CLAUDE_PROGRESS_SUMMARY.md`는 현재 상태 중심의 짧은 요약본
* 기존 긴 기록은 `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`에 보관
* 일반 작업에서는 archive를 읽지 않음

v18.3에서 이미 구현된 것:

* `player_coverage.py` 신규 추가
* `resolve_player_age()` 추가
* `build_data_coverage()` 추가
* 선수 나이 표시를 일부 공통 resolver로 정리
* Prospect Search에 analyze_only 기본값 적용
* Transfermarkt-only 선수 제한 분석 경고 일부 추가
* FM profile/style_vector 없는 선수의 Mentor 분석 조기 차단
* v18.3 테스트 통과

이번 v19 Phase 1~2는 v18.3 기능을 제품 UX 수준으로 확장/정리하는 작업이다.

---

## 2. 사용자 결정사항

이번 작업에서는 아래 결정을 따른다.

1. 기본 유망주 나이 기준은 15~25로 한다.
2. FM profile 없는 선수는 기본 검색에서 숨긴다.
3. 전체 DB 선수 포함 옵션을 켠 경우에만 Limited 선수도 표시한다.
4. Scouting Board 기본 결과에는 Full + Partial 선수를 포함한다.
5. Limited 선수는 기본 검색 결과에서 제외한다.
6. Dashboard 화면은 사용자 UI에서 Player Dossier 성격으로 변경한다.
7. 내부 nav key 변경이 위험하면 내부 key는 유지하고, 화면 제목/라벨만 Player Dossier로 바꾼다.
8. AI Report / Evidence & Advisory Report 전체 개편은 이번 작업에서 하지 않는다.
9. UI는 Football Manager식 dark cockpit 느낌을 강화하되, 과도한 장식보다 정보 밀도와 가독성을 우선한다.
10. Limited 선수에게는 “직접 입력 유망주로 보완하기” 또는 “분석 가능한 선수 다시 검색하기” CTA를 제공한다.
11. 개발자 JSON expander는 기본 접힘 상태로 유지한다.

---

## 3. 먼저 읽을 파일

작업 전 아래 파일을 읽는다.

1. `V19_PRODUCT_REDESIGN_SPEC.md`
2. `CLAUDE_PROGRESS_SUMMARY.md`
3. `AGENTS.md`
4. `ACTIVE_FUNCTION_MAP.md`
5. `REAL_MODEL_PLAN.md`
6. `app.py`
7. `state.py`
8. `ui_components.py`
9. `player_coverage.py`
10. `views/prospect_search.py`
11. `views/dashboard.py`
12. `views/legend_matching.py`
13. `views/career_simulation.py`
14. `views/ai_report.py`
15. `views/scouting_notes.py`
16. `views/manual_prospect.py`
17. `test_prospect_search_split.py`
18. `test_growth_model.py`

주의:

* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽지 않는다.
* archive는 사용자가 명시적으로 요청한 경우에만 읽는다.

---

## 4. 구현 범위

이번 작업에서 구현할 범위:

* Scouting Board 정리
* Player Dossier 재구성
* Data Coverage badge/panel 공통화
* Limited 선수 처리 UX 개선
* Next Action CTA 정리
* 관련 테스트 보강
* 문서 최신화

이번 작업에서 하지 않는 것:

* Style & Mentor Lab 전체 개편
* Career Simulation 전체 개편
* Evidence & Advisory Report 전체 개편
* Notes 전체 개편
* Gemini 기능 확장
* 뉴스 크롤링
* 10x10 Grid
* DB 스키마 변경

---

## 5. Scouting Board 구현 요구사항

`views/prospect_search.py`를 v19 Scouting Board 역할에 맞게 정리한다.

### 5.1 기본 검색 정책

기본값:

* 분석 가능한 유망주만 보기 ON
* 나이 기준 15~25
* Full + Partial 선수 기본 노출
* Limited 선수 기본 제외
* FM profile 없는 선수 기본 제외

Limited 선수 표시:

* “전체 DB 선수 포함” 또는 “Limited 선수 포함” 옵션을 켠 경우에만 표시

Bo-kyung Kim 같은 조건의 선수:

* 고연령
* Transfermarkt-only
* FM profile 없음
* style_vector 없음

위와 같은 선수는 기본 검색 결과에 나오면 안 된다.

---

### 5.2 필터 UI

Scouting Board에는 아래 필터가 있어야 한다.

* 이름 검색
* 포지션
* 나이 범위
* 분석 가능한 유망주만 보기
* 전체 DB 선수 포함
* 분석 준비도 Full / Partial / Limited
* FM profile 있음
* style_vector 있음

필터가 너무 복잡하면 일부는 expander 안에 넣어도 된다.

---

### 5.3 선수 카드 표시 정보

선수 카드 또는 검색 결과 항목에는 아래 정보를 보여준다.

* 이름
* 나이
* 포지션
* 팀
* 국적
* 현재 시장가치
* 최근 출전 정보 또는 데이터 없음 표시
* FM profile 여부
* style_vector 여부
* 분석 준비도 badge: Full / Partial / Limited / Manual
* 데이터 부족 이유
* 왜 이 선수가 분석 후보인지 한 줄 설명

---

### 5.4 Scouting Board CTA

기본 선수:

* 이 선수 분석하기
* 데이터 커버리지 보기

Limited 선수:

* 제한 분석 안내
* 직접 입력 유망주로 보완하기
* 분석 가능한 선수 다시 검색하기

---

## 6. Data Coverage badge/panel 공통화

`player_coverage.build_data_coverage()` 결과를 UI에서 일관되게 보여주는 helper를 추가하거나 기존 helper를 개선한다.

권장 위치:

* `ui_components.py`

필수 표시:

* Full / Partial / Limited / Manual badge
* has_age
* has_valuation
* has_appearances
* has_fm_profile
* has_style_vector
* has_mentality
* missing_reasons

UI 원칙:

* 화면 상단에는 badge와 핵심 missing reason만 간결히 표시
* 자세한 정보는 expander에 표시
* 데이터 부족을 숨기지 않음
* 같은 선수의 나이/분석준비도/데이터 타입이 화면마다 다르게 보이면 안 됨

---

## 7. Player Dossier 구현 요구사항

`views/dashboard.py`를 Player Dossier 역할로 재구성한다.

### 7.1 화면 제목

사용자에게 보이는 제목은 다음 중 하나로 변경한다.

권장:

* Player Dossier
* 선수 분석 Dossier
* 선수 분석 허브

내부 nav key 변경이 위험하면 내부 key는 유지하고 화면 제목만 바꾼다.

---

### 7.2 선수 헤더 카드

화면 상단에 선택 선수 헤더를 표시한다.

필수 정보:

* 이름
* 나이
* 포지션
* 팀
* 국적
* 데이터 모드
* 분석 준비도 badge
* 현재 시장가치
* 최고 시장가치

이 헤더는 가능하면 공통 helper로 구성한다.

---

### 7.3 Data Coverage Panel

Player Dossier 상단부에 Data Coverage Panel을 추가한다.

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

표시 방식:

* check / warning / missing 형태
* Full / Partial / Limited / Manual badge
* missing_reasons 표시
* Limited 선수는 경고를 먼저 보여줌

---

### 7.4 Growth Insight

기존 Growth Score 로직은 유지한다.

추가 요구사항:

* 점수 구성 요소를 보여준다.
* 데이터 부족으로 제외된 항목을 보여준다.
* 제한 분석이면 점수보다 데이터 한계를 먼저 설명한다.
* 25세 이상 선수는 “유망주 잠재력”보다 “현재 데이터 기반 성장 여지” 표현을 사용한다.
* Growth/Ceiling 공식은 변경하지 않는다.

---

### 7.5 Player Identity

FM profile이 있는 경우:

* 포지션/역할 요약
* FM 능력치 기반 강점
* FM 기반 멘탈 지표 proxy
* style_vector 기반 플레이스타일 요약

FM profile이 없는 경우:

* unavailable만 던지지 말고 제한 분석 안내 표시
* FM profile이 없어 능력치/멘탈/style_vector 기반 분석이 제한된다고 설명
* 직접 입력 유망주 보완 CTA 제공

---

### 7.6 Next Action Panel

화면 하단 또는 우측에 다음 행동 CTA를 제공한다.

기본 CTA:

* Style & Mentor Lab으로 이동
* Career Simulation으로 이동
* Evidence & Advisory Report로 이동
* Notes로 이동

Limited 선수 CTA:

* 직접 입력 유망주로 보완하기
* 분석 가능한 선수 다시 검색하기

주의:

* 버튼 클릭 시 기존 session_state 구조를 깨지 않는다.
* selected_player / selected_profile / selected_entity_type 흐름 유지
* 새 선수 선택 시 qualitative_signals / gemini_advisory / growth/ceiling 관련 state 초기화 흐름 유지

---

## 8. 메뉴명 / 화면명 정책

이번 작업에서는 내부 key 변경보다 안정성을 우선한다.

원칙:

* 내부 nav key 변경이 위험하면 하지 않는다.
* 사용자에게 보이는 화면 제목과 버튼 라벨은 v19 컨셉에 맞게 정리한다.
* Dashboard 성격의 화면은 Player Dossier로 보이게 한다.
* Prospect Search 성격의 화면은 Scouting Board로 보이게 한다.

가능하면 app.py 메뉴 label도 정리하되, 연결된 nav 버튼과 테스트를 모두 확인할 수 있을 때만 변경한다.

---

## 9. 테스트 보강

다음 테스트를 추가 또는 수정한다.

1. Bo-kyung Kim 같은 TM-only 또는 profile 없는 선수는 analyze_only 기본 결과에서 제외된다.
2. 전체 DB 포함 옵션 또는 analyze_only 해제 시 Limited 선수도 볼 수 있다.
3. build_data_coverage 결과가 Full / Partial / Limited / Manual을 안정적으로 반환한다.
4. resolve_player_age 결과가 Scouting Board와 Player Dossier에서 일관되게 사용된다.
5. Player Dossier가 FM profile 없는 선수에게 제한 분석 안내를 표시한다.
6. Player Dossier가 FM profile 있는 선수에게 Growth Insight와 Player Identity를 정상 표시한다.
7. Manual Prospect 흐름이 깨지지 않는다.
8. 기존 Gemini v18 기능이 깨지지 않는다.
9. 기존 saved note legacy fallback이 깨지지 않는다.

---

## 10. 문서 업데이트

작업 후 아래 문서를 업데이트한다.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `ACTIVE_FUNCTION_MAP.md`
3. `REAL_MODEL_PLAN.md`
4. `AGENTS.md`

문서에는 다음 섹션으로 기록한다.

`v19 Phase 1~2: Scouting Board and Player Dossier redesign`

문서에 포함할 내용:

* Scouting Board 기본 필터
* 15~25 기준
* Full + Partial 기본 노출
* Limited 기본 제외
* Player Dossier 재구성
* Data Coverage Panel
* 제한 분석 CTA
* 공통 badge/coverage 표시 정책

주의:

* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 일반 작업에서 읽거나 수정하지 말 것
* 긴 archive는 필요할 때만 사용

---

## 11. 실행할 테스트

작업 후 반드시 실행한다.

```bash
python -m compileall .
python test_state_refactor.py
python test_analysis_helpers_split.py
python test_prospect_search_split.py
python test_growth_model.py
```

Streamlit health check도 수행한다.

---

## 12. 절대 금지

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
* V19 전체 Phase를 한 번에 구현 금지
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md` 수정 금지

---

## 13. 완료 보고 형식

완료 후 아래 형식으로 보고한다.

1. 수정한 코드 파일
2. 수정한 문서 파일
3. 추가/수정한 테스트
4. Scouting Board 변경 내용
5. Player Dossier 변경 내용
6. Data Coverage badge/panel 구현 내용
7. Limited 선수 처리 방식
8. 메뉴명/화면명 변경 여부
9. session_state 영향 여부
10. 테스트 결과
11. Streamlit health check 결과
12. 사용자가 직접 확인해야 할 화면
13. 남은 문제
