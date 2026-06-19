# V19_PRODUCT_REDESIGN_TASK.md

## 0. 작업 목적

이 프로젝트는 `c:\Users\nhy81\Desktop\Database_Project`의 NEXT-LEGEND FINDER Streamlit + Supabase 프로젝트이다.

현재 v18.2까지 구현되어 있으나, 기능이 많이 붙으면서 앱 전체가 사용자가 원하는 “Football Manager 스타일 유망주 스카우팅 서비스”처럼 자연스럽게 구성되지 않고 있다.

이번 작업은 두 가지를 함께 수행한다.

1. 긴 `CLAUDE_PROGRESS_SUMMARY.md`를 archive로 보관하고, 현재 상태 중심의 짧은 summary로 재작성한다.
2. 앱 전체 UX, 화면 구성, 분석 흐름, 데이터 흐름, Gemini 역할, 화면 전환 구조를 다시 설계한 `V19_PRODUCT_REDESIGN_SPEC.md`를 작성한다.

중요:
이번 작업은 문서 작업만 수행한다.

코드 수정 금지.
DB 스키마 변경 금지.
기능 구현 금지.
테스트 실행은 필수 아님.

---

## 1. 이번 작업의 산출물

이번 작업이 끝나면 아래 파일이 있어야 한다.

1. `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`

   * 기존 긴 `CLAUDE_PROGRESS_SUMMARY.md` 전체 내용을 보관하는 archive 파일

2. `CLAUDE_PROGRESS_SUMMARY.md`

   * 현재 상태만 담은 짧은 최신 요약본
   * 앞으로 Codex/Claude가 기본적으로 읽을 summary

3. `V19_PRODUCT_REDESIGN_SPEC.md`

   * v19 제품/UX/분석 흐름 재설계 명세서
   * 아직 구현하지 않음
   * 사용자가 확인한 뒤 다음 작업에서 구현 예정

---

## 2. 절대 금지 사항

이번 작업에서는 아래를 절대 하지 않는다.

* 코드 수정 금지
* DB 스키마 변경 금지
* `create_and_upload_db.py` 수정 금지
* `.streamlit/secrets.toml` 내용 출력 금지
* `.env` 내용 출력 금지
* API key 값 출력/저장/문서화 금지
* 원본 CSV 수정 금지
* 뉴스 자동 크롤링 구현 금지
* 10x10 Grid 구현 금지
* Growth/Ceiling 공식 변경 금지
* 기존 JSONB 저장 구조 삭제 금지
* Gemini에게 점수 계산 맡기기 금지
* Gemini가 없는 사실을 지어내게 하기 금지
* Streamlit 기능 구현 금지
* UI 코드 수정 금지

이번 작업에서 허용되는 수정은 문서 파일 수정/생성뿐이다.

---

# PART A. Summary 문서 정리

## A-1. 현재 문제

현재 `CLAUDE_PROGRESS_SUMMARY.md`에 v1~v18.2까지의 긴 기록이 모두 들어 있어 Codex/Claude가 매번 읽기에 너무 길다.

이로 인해 토큰 사용량이 불필요하게 커진다.

따라서 기존 긴 기록은 archive 파일로 보관하고, `CLAUDE_PROGRESS_SUMMARY.md`는 현재 상태만 담은 짧은 최신 요약본으로 교체한다.

---

## A-2. Summary 정리 작업 지시

아래 순서대로 작업한다.

1. 기존 `CLAUDE_PROGRESS_SUMMARY.md`의 전체 내용을 읽는다.
2. 기존 전체 내용을 `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`에 보관한다.

   * archive 파일이 이미 없다면 새로 생성한다.
   * archive 파일이 이미 있다면 기존 archive를 덮어쓰기 전에 현재 내용 보존 여부를 확인하고, 중복이 심하지 않게 정리한다.
3. 기존 `CLAUDE_PROGRESS_SUMMARY.md`는 아래 “새 CLAUDE_PROGRESS_SUMMARY.md 내용”으로 교체한다.
4. 앞으로 일반 작업에서는 archive 파일을 읽지 않는다는 원칙을 summary에 명시한다.

---

## A-3. 새 CLAUDE_PROGRESS_SUMMARY.md 내용

아래 내용으로 `CLAUDE_PROGRESS_SUMMARY.md`를 재작성한다.

```markdown
# CLAUDE_PROGRESS_SUMMARY.md

## 현재 기준 요약

현재 프로젝트는 NEXT-LEGEND FINDER라는 Streamlit + Supabase 기반 유망주 스카우팅 서비스이다.

현재 v18.2까지 구현되어 있다.

핵심 구현 상태:
- Supabase PostgreSQL 기반 선수 DB 조회
- players / clubs / appearances / player_valuations / player_profiles / scouting_notes 사용
- FM 기반 player_profiles 및 24차원 style_vector 사용
- pgvector cosine similarity 기반 유사 선수 후보
- DB 기반 Growth Model
- Career Simulation 기반 Ceiling Scenario
- 직접 입력 유망주 manual_prospect 플로우
- My Scouting Notes 구조화 저장/조회
- Gemini 기반 정성 텍스트 신호 추출
- Gemini 기반 보조 스카우팅 추천
- 분석 출처 라벨링 정리 완료

현재 가장 큰 문제:
- 기능은 많지만 앱 전체 UX가 Football Manager식 스카우팅 센터처럼 자연스럽게 이어지지 않는다.
- 분석하기 부적합한 선수도 유망주 흐름에 들어온다.
- 데이터 커버리지 상태가 화면에서 충분히 명확하지 않다.
- Dashboard / Mentor / Simulation / Report가 하나의 선수 분석 워크플로우로 이어지는 느낌이 약하다.
- 화면별 역할과 화면 전환 흐름을 제품 수준에서 다시 설계해야 한다.

현재 작업 목표:
- v19에서 제품 수준의 UX/분석 흐름 재설계가 필요하다.
- 먼저 `V19_PRODUCT_REDESIGN_SPEC.md`를 작성하고 사용자가 승인한 뒤 구현한다.

## 현재 기본 작업 원칙

- DB 스키마 변경 금지
- create_and_upload_db.py 수정 금지
- secrets.toml / .env 출력 금지
- API key 값 출력 금지
- 원본 CSV 수정 금지
- 뉴스 자동 크롤링 구현 금지
- 10x10 Grid 구현 금지
- Growth/Ceiling 공식 임의 변경 금지
- 기존 JSONB 저장 구조 삭제 금지
- legacy fallback 삭제 금지
- app.py 대형화 금지
- Gemini는 점수 계산에 관여하지 않음
- Gemini는 정성 텍스트 신호 추출과 보조 추천만 수행
- 문서 최신화 필수

## 자세한 과거 기록

v1~v18.2의 자세한 작업 기록은 `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`를 참고한다.

단, 일반 작업에서는 archive를 읽지 않는다.
필요할 때만 사용자가 명시적으로 요청한 경우 archive를 읽는다.
```

---

# PART B. V19 제품 재설계 명세서 작성

## B-1. 작업 목적

현재 앱은 기능 단위로는 많이 구현되었지만, 사용자가 원하는 “Football Manager 스타일 유망주 스카우팅 서비스”로 자연스럽게 구성되어 있지 않다.

이번 작업에서는 코드를 수정하지 않고, 앱 전체 구조를 다시 설계한 문서 `V19_PRODUCT_REDESIGN_SPEC.md`를 작성한다.

---

## B-2. 먼저 읽을 파일

아래 파일을 읽고 현재 구조를 파악한다.

1. `AGENTS.md`
2. `CLAUDE_PROGRESS_SUMMARY.md`
3. `ACTIVE_FUNCTION_MAP.md`
4. `REAL_MODEL_PLAN.md`
5. `app.py`
6. `state.py`
7. `ui_components.py`
8. `services/db.py`
9. `gemini_client.py`
10. `services/qualitative_evidence.py`
11. `views/prospect_search.py`
12. `views/dashboard.py`
13. `views/legend_matching.py`
14. `views/career_simulation.py`
15. `views/ai_report.py`
16. `views/scouting_notes.py`
17. `views/manual_prospect.py`
18. `growth_model.py`
19. `explanation_engine.py`
20. `manual_prospect_helpers.py`
21. `scouting_note_payload.py`
22. `test_growth_model.py`
23. `test_prospect_search_split.py`

주의:

* archive 파일은 일반적으로 읽지 않는다.
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 사용자가 명시적으로 요청한 경우에만 읽는다.
* 이번 작업에서는 위 코드 파일을 읽기만 하고 수정하지 않는다.

---

## B-3. 현재 구조적 문제 진단

`V19_PRODUCT_REDESIGN_SPEC.md`에는 현재 앱의 구조적 문제를 먼저 정리한다.

반드시 포함할 문제:

1. “유망주 분석 서비스”인데 분석하기 부적합한 선수가 기본 흐름에 들어온다.

   * 예: Bo-kyung Kim 같은 Transfermarkt-only, 고연령, FM profile 없음, style_vector 없음 선수

2. 선수 카드와 Growth Model의 데이터 표현이 일치하지 않는다.

   * 예: 카드에서는 나이가 `-`인데 Growth Insight에서는 나이 36.7세로 계산됨

3. Dashboard / Mentor / Simulation / Report가 하나의 스카우팅 흐름으로 이어지는 느낌이 약하다.

4. 데이터가 부족한 선수와 분석 가능한 선수가 UI에서 명확히 구분되지 않는다.

5. Gemini 기능이 추가되었지만 전체 분석 흐름 안에서 어떤 역할인지 UX상 더 명확해야 한다.

6. Football Manager 스타일의 “스카우팅 센터” 느낌이 약하다.

7. 각 화면에서 사용자가 다음에 무엇을 해야 하는지 명확하지 않다.

---

## B-4. 새 앱 컨셉

앱의 새 컨셉은 다음과 같다.

Football Manager 스타일의 유망주 스카우팅 센터

핵심 흐름:

1. 유망주 찾기
2. 분석 가능성 확인
3. 선수 Dossier 확인
4. 플레이스타일/멘토 분석
5. 성장 시뮬레이션
6. 정성 텍스트 + Gemini 보조 추천
7. 스카우팅 노트 저장

앱은 선택 선수 하나를 중심으로 이어지는 분석 워크플로우처럼 동작해야 한다.

---

# B-5. 새 화면 구조 설계

`V19_PRODUCT_REDESIGN_SPEC.md`에는 다음 화면 구조를 기준으로 설계안을 작성한다.

---

## 5.1 Home / Scouting Center

역할:

* 서비스 시작 화면
* 현재 선택 선수 상태 표시
* 주요 분석 흐름으로 진입하는 로비

보여줄 정보:

* 서비스 이름
* 현재 선택 선수 요약
* 데이터 출처 요약
* 주요 기능 카드

기능 카드:

1. 유망주 검색 시작
2. 직접 입력 유망주 생성
3. 저장된 스카우팅 노트 보기
4. DB 상태 확인

Home은 단순 소개 페이지가 아니라 “Scouting Center 로비”처럼 보여야 한다.

---

## 5.2 Search / Scouting Board

역할:

* 분석 가능한 유망주를 찾는 화면

기본값:

* 분석 가능한 유망주만 보기 ON
* 나이 15~23 또는 15~25 중심
* FM profile 또는 style_vector가 있는 선수 중심
* Transfermarkt-only / 고연령 / profile 없음 선수는 기본 결과에서 제외

단, 사용자가 원하면 전체 DB 선수도 볼 수 있어야 한다.

필터:

* 이름 검색
* 포지션
* 나이 범위
* 시장가치 범위
* 분석 준비도 full / partial / limited
* FM profile 있음
* style_vector 있음
* 전체 DB 선수 포함 여부

선수 카드 표시 정보:

* 이름
* 나이
* 포지션
* 팀
* 국적
* 현재 시장가치
* 최근 출전 수
* FM profile 여부
* style_vector 여부
* 분석 준비도 badge: Full / Partial / Limited / Manual
* 왜 이 선수가 후보인지 한 줄 설명

카드 버튼:

* 이 선수 분석하기
* 데이터 커버리지 보기

중요:
Bo-kyung Kim처럼 FM profile이 없고 고연령인 선수는 기본 검색 결과에 나오면 안 된다.
전체 DB 선수 보기 옵션을 켠 경우에만 제한 분석 카드로 보여야 한다.

---

## 5.3 Player Dossier

기존 Dashboard를 이 역할로 재정의한다.

역할:

* 선택 선수의 메인 분석 허브
* 모든 분석의 출발점
* 현재 이 선수에 대해 무엇을 알고 있고, 무엇을 모르는지 보여주는 화면

화면 구성:

1. 선수 헤더 카드

   * 사진
   * 이름
   * 나이
   * 포지션
   * 팀
   * 국적
   * 데이터 타입
   * 분석 준비도 badge
   * 현재 시장가치
   * 최고 시장가치

2. Data Coverage Panel

   * 선수 기본정보 있음
   * 나이 있음
   * 시장가치 데이터 있음
   * 출전 기록 있음
   * FM profile 있음
   * style_vector 있음
   * FM 멘탈 속성 proxy 있음
   * 정성 텍스트 분석 있음
   * Gemini 보조 추천 있음

각 항목을 check / warning / missing 형태로 표시한다.

3. Growth Insight

   * Growth Score
   * 구성 요소별 기여도
   * 점수가 높거나 낮은 이유
   * 제한 분석인 경우 명확한 안내

4. Player Identity

   * 포지션/역할 요약
   * FM 능력치 기반 강점
   * FM 멘탈 속성 proxy
   * 데이터 부족 항목

5. Next Action Panel

   * Style & Mentor Lab으로 이동
   * Career Simulation으로 이동
   * Evidence & Advisory Report로 이동
   * My Scouting Notes로 이동

Player Dossier는 “이 선수를 계속 분석할지 말지 판단하는 화면”이어야 한다.

---

## 5.4 Style & Mentor Lab

역할:

* pgvector 기반 유사 선수/멘토 추천
* 현재 선수의 플레이스타일과 유사한 선수를 보여줌
* 어린 유망주에게 적합한 멘토를 추천

필수 조건:

* style_vector가 있어야 함
* FM profile이 있어야 함
* 없으면 분석 실행하지 말고 안내 표시

화면 구성:

1. 현재 선수 스타일 요약

   * 주요 포지션
   * style_vector 기반 플레이스타일
   * 강점 영역
   * 보완 영역

2. 유사 선수 후보 카드

   * 이름
   * 나이
   * 포지션
   * 팀
   * similarity score
   * 유사한 이유
   * 다른 점
   * 데이터 출처

3. 멘토 후보 카드

   * 이름
   * 나이
   * 포지션
   * 팀
   * style similarity
   * 멘토 적합 이유
   * 배울 수 있는 훈련 방향
   * 주의할 점

멘토 조건:

* 자기 자신 제외
* 나이 없음 제외
* 기본 기준: max(28, 대상 선수 나이 + 5)
* fallback 기준: max(26, 대상 선수 나이 + 3)
* 너무 어린 선수 제외

다음 이동:

* 이 멘토를 기준으로 훈련 추천 보기
* Career Simulation으로 이동
* Evidence & Advisory Report로 이동

---

## 5.5 Career Simulation

역할:

* 현재 선수의 Growth baseline을 바탕으로 성장 시나리오 실험
* 사용자가 조건을 바꾸면 Final Growth Score와 리스크 설명이 변함

화면 구성:

1. Baseline Summary

   * 현재 Growth Score
   * 데이터 기반 장점
   * 데이터 기반 리스크

2. Scenario Controls

   * 훈련 강도
   * 출전 기회
   * 리그 수준
   * 리스크 성향

3. Scenario Result

   * Baseline Growth Score
   * Scenario Adjustment
   * Final Growth Score
   * 상승/하락 이유
   * 리스크 경고

4. Coaching Recommendation

   * 추천 훈련 방향
   * 출전 관리 전략
   * 리그 이동/잔류 판단
   * 리스크 관리

5. 다음 이동

   * Evidence & Advisory Report로 이동
   * 현재 시뮬레이션을 노트에 저장

Career Simulation은 점수만 보여주는 화면이 아니라 “어떤 선택이 성장에 어떤 영향을 주는지” 설명해야 한다.

---

## 5.6 Evidence & Advisory Report

기존 AI Report 화면을 이 역할로 재정의한다.

역할:

* 최종 스카우팅 리포트 생성 화면
* DB/FΜ proxy/rule-based 분석과 사용자가 제공한 정성 텍스트를 결합
* Gemini가 정성 신호 추출 + 보조 추천 생성

화면 구성:

1. Rule-based Report Summary

   * Growth/Ceiling 기반 분석 리포트 초안
   * 데이터 출처 명확히 표시

2. Qualitative Text Input

   * 사용자가 기사, 스카우팅 리포트, 감독 인터뷰, 관찰 메모를 붙여넣음
   * 입력 예시 expander 제공
   * 텍스트가 없으면 기존 DB/FΜ proxy 분석만 사용

3. Gemini Qualitative Signal Extraction
   Gemini가 다음을 추출:

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

4. Gemini Advisory Report
   Gemini가 다음을 생성:

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

5. Final Report Preview

   * 규칙 기반 분석
   * 정성 텍스트 근거
   * Gemini 보조 추천
   * 근거 부족 항목
   * 최종 스카우팅 코멘트

6. Save to Notes

   * scouting_notes에 저장
   * qualitative_evidence, gemini_advisory, report_generation_mode 포함

중요:

* Gemini는 점수 계산을 하지 않는다.
* Gemini는 Growth/Ceiling 결과를 대체하지 않는다.
* Gemini는 없는 사실을 지어내지 않는다.
* Gemini는 정성 텍스트를 구조화하고 추천을 보조하는 역할이다.

---

## 5.7 My Scouting Notes

역할:

* 저장된 분석 기록 조회 전용
* 선수 생성 기능 없음
* 직접 입력 유망주 생성은 Manual Prospect 화면에서만 수행

보여줄 정보:

* 저장된 노트 목록
* 선수 이름
* 저장 시점
* note_type
* entity_type
* report_generation_mode
* Growth Score
* Final Growth Score
* Gemini 사용 여부
* 정성 텍스트 포함 여부

노트 상세:

* 저장 당시 선수 snapshot
* 저장 당시 Data Coverage
* Growth/Ceiling 결과
* 정성 텍스트 근거
* Gemini 보조 추천
* 최종 리포트
* 개발자용 JSON expander

---

## 5.8 Manual Prospect

역할:

* DB에 없는 유망주를 직접 입력
* 입력 후 실제 DB 선수와 동일한 분석 플로우로 이동

입력 항목:

* 이름
* 나이
* 포지션
* 팀
* 국적
* 주발
* 키/몸무게 optional
* 기본 능력치
* 멘탈 proxy 값
* 현재 리그 수준
* 예상 출전 기회

생성 후:

* selected_entity_type = manual_prospect
* Player Dossier로 이동
* 이후 Career Simulation, Evidence & Advisory Report, Notes 저장 흐름 동일

주의:

* Manual Prospect는 실제 DB 선수와 구분되어야 한다.
* player_id=None, profile_id=None을 명확히 유지한다.

---

# 6. 분석 알고리즘 설계

명세서에는 아래 분석 방법을 반드시 정리한다.

## 6.1 Prospect Eligibility Filter

목적:

* 분석 가능한 유망주만 기본 검색 결과에 노출

기준:

* 나이 15~23 또는 15~25
* profile 있음
* style_vector 있음 또는 FM attribute 있음
* 시장가치/출전 데이터 일부 있음

결과:

* eligible
* limited
* excluded_by_default

---

## 6.2 Data Coverage Classifier

목적:

* 선수마다 분석 가능성 표시

분류:

* full: DB + age + valuation + appearances + FM profile + style_vector
* partial: DB + age + valuation/appearances는 있으나 FM profile/style_vector 일부 부족
* limited: Transfermarkt-only 또는 핵심 데이터 부족
* manual_prospect: 직접 입력 선수

---

## 6.3 Growth Model

현재 구현 유지.

UI에서는 다음을 명확히 표시:

* 점수 구성 요소
* 데이터 부족으로 제외된 항목
* 제한 분석 여부

---

## 6.4 Style Similarity

* FM 기반 24D style_vector 사용
* pgvector cosine similarity 사용
* style_vector 없으면 실행 금지

---

## 6.5 Mentor Recommendation

* similarity score
* 나이 필터
* 자기 자신 제외
* 멘토로 적합한 이유 생성
* 너무 어린 선수 제외

---

## 6.6 Ceiling Simulation

* Growth baseline 유지
* 시나리오 조건으로 보정
* Gemini는 점수 계산에 개입하지 않음

---

## 6.7 Qualitative Evidence Extraction

* 사용자가 입력한 텍스트를 Gemini가 구조화
* 텍스트가 없으면 정성 분석 없음
* 원문 근거 quote 포함

---

## 6.8 Gemini Advisory

* DB/FΜ proxy/Growth/Ceiling/정성 신호를 종합해 추천
* 훈련, 커리어, 리스크, 멘토 활용 방향 제안
* 없는 사실은 unsupported_or_unknown에 넣음

---

# 7. 화면 전환 흐름

명세서에는 다음 흐름을 Mermaid 또는 텍스트 플로우로 정리한다.

기본 DB 선수 흐름:

```text
Search / Scouting Board
→ Player Dossier
→ Style & Mentor Lab
→ Career Simulation
→ Evidence & Advisory Report
→ My Scouting Notes
```

직접 입력 선수 흐름:

```text
Manual Prospect
→ Player Dossier
→ Career Simulation
→ Evidence & Advisory Report
→ My Scouting Notes
```

제한 분석 선수 흐름:

```text
Search에서 limited badge 표시
→ Player Dossier에서 제한 분석 안내
→ Style & Mentor Lab 진입 제한
→ Manual Prospect로 보완 유도 또는 Search로 복귀
```

---

# 8. UI / 디자인 원칙

명세서에 다음 UI 원칙을 포함한다.

* Football Manager식 어두운 스카우팅 센터 느낌
* 선택 선수 중심의 일관된 헤더 유지
* 각 화면 상단에 현재 선수 상태 표시
* Full / Partial / Limited / Manual badge 사용
* 데이터 부족은 숨기지 않고 명확히 표시
* 기술용어는 expander 안으로 이동
* 사용자가 다음 행동을 쉽게 알 수 있게 CTA 제공
* 같은 정보가 화면마다 다르게 표시되지 않도록 공통 helper 사용
* 나이, 데이터 타입, 분석 준비도는 모든 화면에서 일관되게 표시
* 화면 제목은 사용자가 이해하기 쉬운 명칭 사용

권장 메뉴명:

* Home
* Scouting Board
* Player Dossier
* Style & Mentor Lab
* Career Simulation
* Evidence & Advisory Report
* Notes
* Manual Prospect
* DB Status

---

# 9. 구현 계획 작성

`V19_PRODUCT_REDESIGN_SPEC.md`에는 다음 순서로 구현 계획을 제안한다.

## Phase 1

* Data Coverage Classifier
* Age Resolver
* Prospect Search 기본 필터

## Phase 2

* Player Dossier 재구성
* Analysis readiness badge
* 제한 분석 안내

## Phase 3

* Style & Mentor Lab 재구성
* Mentor card 개선

## Phase 4

* Career Simulation 재구성
* Scenario result 설명 강화

## Phase 5

* Evidence & Advisory Report 재구성
* Gemini 결과 표시 방식 개선

## Phase 6

* My Scouting Notes 저장/조회 UI 개선

## Phase 7

* 테스트/문서/최종 QA

각 Phase별로 다음을 적는다.

* 수정 예상 파일
* 구현 내용
* 테스트 항목
* 위험 요소
* 사용자 확인 필요 사항

---

# 10. 구현 전 사용자 확인 필요 항목

`V19_PRODUCT_REDESIGN_SPEC.md` 마지막에는 구현 전 사용자가 결정해야 할 항목을 따로 정리한다.

반드시 포함할 질문 예시:

1. 기본 유망주 나이 기준을 15~23으로 할지, 15~25로 할지
2. FM profile 없는 선수는 기본 검색에서 완전히 숨길지, limited로 보여줄지
3. 기존 Dashboard 메뉴명을 Player Dossier로 변경할지
4. 기존 AI Report 메뉴명을 Evidence & Advisory Report로 변경할지
5. UI를 어두운 FM 스타일로 더 강하게 바꿀지
6. 제한 분석 선수에게 직접 입력 유망주로 보완하는 흐름을 제공할지
7. Gemini 결과를 최종 리포트에 어느 정도 강하게 반영할지

---

# 11. 완료 보고 형식

작업 완료 후 아래 형식으로 보고한다.

1. 생성/수정한 파일
2. `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md` 생성 여부
3. `CLAUDE_PROGRESS_SUMMARY.md` 단축 여부
4. 작성한 `V19_PRODUCT_REDESIGN_SPEC.md`의 주요 섹션
5. 현재 앱에서 가장 큰 구조적 문제 5개
6. 제안한 새 화면 흐름 요약
7. 제안한 분석 알고리즘 요약
8. 구현 전 사용자가 확인해야 할 결정사항
9. 코드 수정 여부
10. 남은 문제
