# V19_FINAL_FUNCTIONAL_QA_AND_BUGFIX_TASK.md

## 0. 작업 목적

이 프로젝트는 `c:\Users\nhy81\Desktop\Database_Project`의 NEXT-LEGEND FINDER Streamlit + Supabase 기반 축구 유망주 스카우팅 웹앱이다.

현재 UI, 폴더 정리, 기술 로직 정리는 대부분 완료되었지만, 실제 사용 흐름에서 다음과 같은 기능 오류 가능성이 남아 있다.

예상 문제:

1. Scouting Notes 저장 시 오류 발생
2. Mentor Matching에서 후보가 없다고만 표시됨
3. Gemini 호출 실패 시 기능 전체가 불안정해짐
4. 선택한 선수가 바뀌었을 때 이전 분석 상태가 꼬임
5. FM profile/style_vector 없는 선수에서 화면이 깨짐
6. Manual Prospect로 생성한 선수의 후속 분석 흐름이 끊김
7. Career Simulation 결과가 Notes/Report로 제대로 이어지지 않음

이번 작업은 기능 추가가 아니라 최종 기능 QA 및 bugfix 작업이다.

목표:

* 사용자가 실제로 누르는 핵심 흐름을 끝까지 검증한다.
* 오류가 발생하는 지점을 재현하고 수정한다.
* Gemini 실패, 멘토 없음, 데이터 부족 상황에서도 앱이 죽지 않게 한다.
* 기능이 없으면 “에러”가 아니라 사용자 친화적인 대체 안내를 보여준다.
* 기존 DB 스키마와 Growth/Ceiling 공식은 변경하지 않는다.
* 모든 수정 후 회귀 테스트와 health check를 수행한다.

---

## 1. 작업 전 확인

먼저 현재 상태를 확인한다.

```bash id="zimv0x"
git status
```

주의:

* 기존 변경사항을 임의로 되돌리지 않는다.
* 기능을 대규모로 새로 추가하지 않는다.
* DB 스키마를 변경하지 않는다.
* Growth/Ceiling 공식은 변경하지 않는다.
* Gemini 실제 API 호출은 자동 테스트에서 수행하지 않는다.
* `.env`, `.streamlit/secrets.toml`, API key 값은 출력하지 않는다.
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않는다.

---

## 2. 먼저 읽을 파일

아래 파일을 읽고 현재 구조와 함수 흐름을 파악한다.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `AGENTS.md`
3. `ACTIVE_FUNCTION_MAP.md`
4. `REAL_MODEL_PLAN.md`
5. `TECHNICAL_LOGIC_AUDIT_REPORT.md`가 있으면 읽기
6. `app.py`
7. `state.py`
8. `services/db.py`
9. `player_coverage.py`
10. `scouting_note_payload.py`
11. `growth_model.py`
12. `explanation_engine.py`
13. `analysis_helpers.py`
14. `gemini_client.py`
15. `services/qualitative_evidence.py`
16. `views/prospect_search.py`
17. `views/dashboard.py`
18. `views/legend_matching.py`
19. `views/career_simulation.py`
20. `views/ai_report.py`
21. `views/scouting_notes.py`
22. `views/manual_prospect.py`
23. `components/cards.py`
24. `styles/game_ui.css`
25. 기존 `test_*.py` 파일 전부

---

# PART A. 핵심 사용자 흐름 QA

## 3. 반드시 검증할 전체 흐름

아래 흐름을 실제 코드 기준으로 확인한다.

### Flow 1. 기본 DB 선수 분석 흐름

```text id="q9yilw"
Scouting Board
→ FM profile 있는 선수 선택
→ Player Dossier 확인
→ Mentor Matching 확인
→ Career Simulation 실행
→ Evidence & Advisory Report 생성
→ Scouting Notes 저장
→ Scouting Archive에서 저장 결과 조회
```

검증할 것:

* 선수 선택이 session_state에 저장되는가
* Player Dossier에서 선수 정보가 깨지지 않는가
* Mentor Matching에서 멘토 후보가 나오거나, 없으면 정상 안내가 나오는가
* Career Simulation 결과가 생성되는가
* Report 화면에서 rule-based report가 생성되는가
* Save to Notes가 성공하는가
* Notes 화면에서 방금 저장한 노트가 보이는가
* Developer JSON expander가 있더라도 사용자 화면이 깨지지 않는가

---

### Flow 2. Mentor Matching 예외 흐름

```text id="qzmt29"
FM profile/style_vector 있는 선수 선택
→ Mentor Matching 진입
→ 멘토 후보 확인
```

검증할 것:

* 멘토 후보가 없을 때 화면이 에러처럼 보이지 않는가
* 기본 조건에서 후보가 없으면 완화 기준을 적용하는가
* 완화 기준에도 후보가 없으면 이유를 설명하는가
* “분석 가능한 멘토 후보가 부족합니다” 같은 사용자 친화 안내를 보여주는가
* raw query result나 개발자용 용어가 메인 화면에 노출되지 않는가

수정 요구:

* 후보가 없다고 기능이 끝나면 안 된다.
* 가능한 경우 완화 기준으로 다시 찾는다.
* 그래도 없으면 다음 안내를 보여준다.

예시 문구:

```text id="plb8k8"
현재 조건에 맞는 멘토 후보를 찾지 못했습니다.
비슷한 포지션과 능력치 패턴을 가진 경험 많은 선수가 충분하지 않기 때문입니다.
다른 선수를 선택하거나 Scouting Board에서 분석 가능한 선수를 다시 선택해보세요.
```

주의:

* 없는 멘토를 지어내지 않는다.
* similarity query나 age filter 기준을 무리하게 바꾸지 않는다.
* 멘토 후보가 없어도 앱이 멈추면 안 된다.

---

### Flow 3. Scouting Notes 저장 흐름

```text id="9h6wts"
Player Dossier
→ Career Simulation
→ Evidence & Advisory Report
→ Save to Notes
→ Scouting Archive 조회
```

검증할 것:

* Save 버튼 클릭 시 DB insert 오류가 없는가
* scouting_notes 테이블 실제 컬럼과 insert payload가 맞는가
* 없는 컬럼에 insert하려고 하지 않는가
* JSONB payload가 직렬화 가능한가
* datetime/object/NaN 때문에 저장이 실패하지 않는가
* player_id/profile_id가 없을 때도 안전하게 처리하는가
* 저장 성공 후 note_id 또는 성공 메시지가 표시되는가
* 저장 실패 시 raw DB error를 그대로 노출하지 않고 개발자용 expander로 보관하는가

수정 요구:

* DB 스키마를 변경하지 말고, 현재 scouting_notes 테이블에 맞춰 insert payload를 안전하게 구성한다.
* 저장 전에 payload를 sanitize한다.
* NaN, numpy 타입, Timestamp, Decimal 등이 있으면 JSON serializable 형태로 변환한다.
* 저장 실패 시 전체 앱이 멈추지 않게 한다.

---

### Flow 4. Gemini 실패 흐름

```text id="cvy1pz"
Evidence & Advisory Report
→ 정성 텍스트 입력
→ Gemini 보조 분석 실행
→ quota 초과 / key 없음 / 네트워크 실패 상황
```

검증할 것:

* Gemini 실패가 전체 report 생성 실패로 이어지지 않는가
* raw API error가 메인 화면에 노출되지 않는가
* Rule-based report는 계속 표시되는가
* Save to Notes는 Gemini 없이도 가능한가
* Gemini 결과가 없을 때 `NoneType` 오류가 발생하지 않는가
* 자동 테스트에서 실제 Gemini API를 호출하지 않는가

수정 요구:

* Gemini는 선택형 보조 기능으로 유지한다.
* quota 초과, key 없음, timeout, invalid response를 모두 안전하게 처리한다.
* 실제 API 호출 실패 시 아래처럼 표시한다.

```text id="efpi02"
현재 Gemini 보조 분석을 실행할 수 없습니다.
선수 데이터 기반 분석과 리포트 저장 기능은 정상적으로 사용할 수 있습니다.
```

개발자용 상세:

* raw error는 expander 안에만 표시
* API key 값은 절대 표시 금지

---

### Flow 5. Manual Prospect 흐름

```text id="1dnq5u"
Manual Prospect
→ 직접 선수 생성
→ Player Dossier 또는 Career Simulation 이동
→ Report 저장
→ Notes 조회
```

검증할 것:

* 포지션/국적/팀/주발 선택형 UI가 정상 작동하는가
* “기타 / 직접 입력” fallback이 정상 작동하는가
* manual prospect 생성 후 session_state가 정상 설정되는가
* manual prospect는 DB player_id가 없어도 화면이 깨지지 않는가
* Manual badge가 표시되는가
* Career Simulation으로 이어지는가
* Notes 저장 시 player_id/profile_id null 처리 때문에 오류가 나지 않는가

---

### Flow 6. 선수 변경 state 초기화

검증할 것:

* A 선수 분석 후 B 선수를 선택했을 때 이전 성장 결과/리포트/Gemini 결과가 남지 않는가
* session_state clear 흐름이 정상인지 확인
* 특히 아래 key들이 선수 변경 시 적절히 초기화되는지 확인

  * growth
  * ceiling
  * report
  * qualitative_signals
  * gemini_advisory
  * selected mentor
  * note detail selected index

---

# PART B. 기능별 bugfix 요구사항

## 4. Scouting Notes 저장 오류 수정

대상:

* `scouting_note_payload.py`
* `views/ai_report.py`
* `views/scouting_notes.py`
* `services/db.py`

점검:

* insert 함수가 현재 DB 스키마와 맞는지
* payload가 JSON 직렬화 가능한지
* report_generation_mode, entity_type, note_type 같은 필드가 DB에 없는데 insert하려고 하지 않는지
* DB에 없는 확장 필드는 JSONB 안에 넣는 구조인지 확인
* legacy fallback이 깨지지 않았는지 확인

필요 시:

* `sanitize_for_json()` 같은 helper 추가 또는 기존 helper 개선
* insert 직전 payload validation 추가
* 저장 실패 시 사용자용 메시지 + 개발자용 상세 expander 분리

---

## 5. Mentor Matching 안정화

대상:

* `views/legend_matching.py`
* `services/db.py`
* `components/cards.py`

점검:

* get_similar_players()가 빈 결과일 때 안전한가
* mentor age filter가 너무 빡세서 항상 후보가 없는지 확인
* 기본 기준 실패 시 완화 기준을 적용하는지 확인
* 완화 기준도 실패할 때 empty state가 잘 보이는지 확인
* selected mentor session_state가 없는 상태에서도 패널이 깨지지 않는지 확인
* manual prospect mentor flow와 DB player mentor flow가 모두 안전한지 확인

수정:

* 후보 없음은 에러가 아니라 정상 empty state로 처리
* 사용자에게 “왜 후보가 없는지” 간단히 설명
* 다음 행동 CTA 제공

  * Scouting Board로 돌아가기
  * 다른 선수 선택
  * Career Simulation으로 이동

---

## 6. Gemini 안정화

대상:

* `gemini_client.py`
* `services/qualitative_evidence.py`
* `views/ai_report.py`

점검:

* quota exceeded
* key missing
* invalid response
* network error
* JSON parse failure
* empty output

수정:

* 모든 실패를 safe result object로 반환
* 예외를 그대로 raise해서 UI를 깨지 않게 함
* UI에서는 `status: unavailable`, `reason: quota_exceeded`, `message` 같은 구조로 처리
* raw error는 debug expander에만 표시

자동 테스트:

* 실제 Gemini API 호출 금지
* mock/stub으로 quota exceeded와 success case를 확인

---

## 7. Career Simulation 안정화

대상:

* `views/career_simulation.py`
* `growth_model.py`
* `explanation_engine.py`

점검:

* selected player가 없을 때 안전한 안내
* manual prospect일 때 안전한 계산
* Growth baseline이 없을 때 fallback 안내
* 선택형 입력값이 내부 numeric value로 정상 매핑되는지
* scenario result가 Notes/Report로 전달되는지

수정:

* 숫자 계산 실패 시 사용자용 안내
* None/NaN 방어
* 저장용 context 생성 시 JSON serializable 보장

---

## 8. Data Coverage / 검색 안정화

대상:

* `player_coverage.py`
* `views/prospect_search.py`
* `views/dashboard.py`

점검:

* Scouting Board 기본 검색에서 FM profile 있는 선수만 나오는지
* Limited 선수가 기본 검색에 나오지 않는지
* FM profile 없는 선수 선택 시 Dossier/Mentor가 깨지지 않는지
* profile_id 없는 경우 안전한 안내가 나오는지

---

# PART C. 테스트 요구사항

## 9. 기존 테스트 실행

반드시 실행:

```bash id="fkkk1u"
python -m compileall .
python test_state_refactor.py
python test_analysis_helpers_split.py
python test_prospect_search_split.py
python test_growth_model.py
```

---

## 10. 새 기능 QA 테스트 추가 권장

가능하면 아래 테스트 파일을 새로 만들거나 기존 테스트에 추가한다.

파일명 예시:

```text id="jn82v7"
test_final_functional_flows.py
```

테스트할 것:

1. scouting note payload가 JSON serializable인지
2. Gemini quota exceeded mock 결과가 UI/logic에서 안전하게 처리되는지
3. Mentor candidates가 빈 리스트일 때도 render helper가 깨지지 않는지
4. selected player 변경 시 stale state가 clear되는지
5. manual prospect payload가 Notes 저장 구조와 충돌하지 않는지

주의:

* 실제 Supabase insert를 자동 테스트에서 수행하지 않아도 된다.
* 실제 Gemini API 호출은 금지한다.
* DB가 필요한 테스트는 mock 또는 safe dry-run 형태로 작성한다.

---

## 11. Streamlit 수동 health check

다음도 확인한다.

```bash id="9g9w4m"
streamlit run app.py
```

브라우저에서 최소 수동 확인:

* Scouting Board에서 선수 선택
* Player Dossier 진입
* Mentor Lab 진입
* Career Simulation 실행
* Evidence Report 생성
* Save to Notes
* Scouting Archive 조회

---

# PART D. 최종 산출물

## 12. FUNCTIONAL_QA_REPORT.md 생성

작업 후 다음 파일을 생성한다.

```text id="q9uc0s"
FUNCTIONAL_QA_REPORT.md
```

보고서에는 다음을 포함한다.

1. 작업 전 git status 요약
2. 발견한 기능 오류 목록
3. 수정한 기능 오류 목록
4. 수정하지 않은 이유가 있는 항목
5. Scouting Notes 저장 흐름 점검 결과
6. Mentor Matching 흐름 점검 결과
7. Gemini 실패 처리 점검 결과
8. Career Simulation → Report → Notes 연결 점검 결과
9. Manual Prospect 흐름 점검 결과
10. session_state 초기화 점검 결과
11. 추가한 테스트
12. 기존 테스트 결과
13. Streamlit health check 결과
14. 사용자가 다시 확인해야 할 화면
15. 남은 리스크

---

## 13. 문서 업데이트

작업 후 아래 문서를 업데이트한다.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `ACTIVE_FUNCTION_MAP.md`
3. `REAL_MODEL_PLAN.md`
4. `AGENTS.md`

섹션명:

```text id="iqltrs"
v19 Final Functional QA: notes save, mentor empty state, Gemini fallback, and end-to-end flow
```

포함 내용:

* 수정한 버그
* 안전하게 처리한 예외
* 추가한 테스트
* 남은 리스크

---

## 14. 완료 보고 형식

완료 후 아래 형식으로 보고한다.

1. 수정한 코드 파일
2. 새로 만든 코드 파일
3. 수정한 문서 파일
4. 새로 만든 문서 파일
5. 발견한 기능 오류
6. 수정한 기능 오류
7. Scouting Notes 저장 오류 수정 내용
8. Mentor Matching 안정화 내용
9. Gemini 실패 처리 개선 내용
10. Career Simulation 연결 안정화 내용
11. Manual Prospect 연결 안정화 내용
12. session_state 초기화 점검 결과
13. 추가한 테스트
14. 기존 테스트 결과
15. Streamlit health check 결과
16. FUNCTIONAL_QA_REPORT.md 주요 내용
17. 사용자가 직접 다시 확인해야 할 화면
18. 남은 문제
