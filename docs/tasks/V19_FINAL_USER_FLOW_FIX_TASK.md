# V19_FINAL_USER_FLOW_FIX_TASK.md

## 0. 작업 목적

이 프로젝트는 `c:\Users\nhy81\Desktop\Database_Project`의 NEXT-LEGEND FINDER Streamlit + Supabase 기반 축구 유망주 스카우팅 웹앱이다.

현재 v19 UI/폴더정리/가독성 polish까지 대부분 완료되었다.
하지만 실제 화면 캡처 확인 결과, 사용자 관점에서 다음 문제가 남아 있다.

1. Gemini 호출 실패 시 긴 raw API error가 그대로 노출된다.
2. Player Dossier의 멘탈리티 분석이 어떤 근거로 판단되는지 이해하기 어렵다.
3. 사용자가 직접 입력한 정성 텍스트가 멘탈리티/태도/리스크 분석에 자연스럽게 반영되지 않는다.
4. Career Simulation의 훈련강도/출전기회가 숫자 슬라이더라서 사용자가 기준을 이해하기 어렵다.
5. 데이터 타입 안내, 10x10 Grid, proxy, vector 같은 사용자에게 불필요한 기술 문구가 아직 보인다.
6. 유망주 검색에서 FM profile 없는 선수까지 다룰 수 있어 분석 품질이 흔들린다.
7. Style & Mentor Lab에서 유사 선수 후보가 먼저 많이 보이는데, 사용자는 멘토 후보가 더 필요하다.

이번 작업은 새로운 기능 추가가 아니라 최종 사용자 흐름 수정 작업이다.

목표:

* 사용자에게 필요한 정보만 보여주기
* 개발자용 내부 구현 설명은 숨기기
* Gemini 실패를 안전하고 짧게 안내하기
* 멘탈리티 분석 근거를 명확히 하기
* 정성 텍스트 기반 멘탈리티 보조 분석을 추가하기
* Career Simulation 입력을 숫자 대신 설명형 선택지로 바꾸기
* Scouting Board는 기본적으로 FM profile 있는 선수만 보여주기
* Style & Mentor Lab은 멘토 후보 중심으로 단순화하기

---

## 1. 작업 전 확인

먼저 현재 상태를 확인한다.

```bash id="me43n7"
git status
```

주의:

* 기존 변경사항을 임의로 되돌리지 않는다.
* DB 스키마, Growth/Ceiling 공식, pgvector 쿼리, Gemini 점수 계산 로직은 변경하지 않는다.
* `.env`, `.streamlit/secrets.toml`, API key 파일은 읽거나 출력하지 않는다.
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽거나 수정하지 않는다.

---

## 2. 먼저 읽을 파일

아래 파일을 읽고 현재 구조를 파악한다.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `AGENTS.md`
3. `ACTIVE_FUNCTION_MAP.md`
4. `REAL_MODEL_PLAN.md`
5. `app.py`
6. `ui_components.py`
7. `components/cards.py`
8. `components/badges.py`
9. `styles/game_ui.css`
10. `views/prospect_search.py`
11. `views/dashboard.py`
12. `views/legend_matching.py`
13. `views/career_simulation.py`
14. `views/ai_report.py`
15. `views/scouting_notes.py`
16. `services/qualitative_evidence.py`
17. `gemini_client.py`
18. `explanation_engine.py`
19. `analysis_helpers.py`
20. `growth_model.py`

---

# PART A. Gemini 오류 처리 개선

## 3. 문제

현재 Gemini quota 초과 또는 API 호출 실패 시 다음과 같은 raw error가 사용자 화면에 그대로 노출된다.

예:

* `RESOURCE_EXHAUSTED`
* `quota exceeded`
* `GenerateRequestsPerDayPerProjectPerModel-FreeTier`
* API URL
* 내부 response object

이 정보는 사용자에게 불필요하고 화면을 망친다.

---

## 4. 수정 요구사항

대상:

* `views/ai_report.py`
* `gemini_client.py`
* `services/qualitative_evidence.py`
* 필요 시 `ui_components.py` 또는 `components/cards.py`

수정:

* Gemini 호출 실패 시 raw error 전체를 사용자 화면에 표시하지 않는다.
* 사용자 화면에는 짧은 안내 카드만 보여준다.
* 자세한 raw error는 개발자용 expander 안에만 둔다.
* API key 값은 절대 출력하지 않는다.

사용자용 문구 예시:

```text id="14jsws"
현재 Gemini 호출 한도가 초과되어 정성 텍스트 분석을 실행할 수 없습니다.
저장된 선수 데이터 기반 분석은 계속 사용할 수 있습니다.
잠시 후 다시 시도하거나 Gemini API 사용량/요금제 설정을 확인해주세요.
```

Gemini key 없음 문구 예시:

```text id="x20x7a"
Gemini API 키가 설정되어 있지 않아 정성 텍스트 보조 분석은 비활성화되어 있습니다.
기본 선수 데이터 기반 리포트는 계속 사용할 수 있습니다.
```

주의:

* Gemini 실패가 전체 리포트 실패로 이어지면 안 된다.
* Rule-based report는 계속 표시되어야 한다.
* Save to Notes 흐름은 유지한다.

---

# PART B. 멘탈리티 분석 근거 명확화 + 정성 텍스트 반영

## 5. 문제

Player Dossier에서 멘탈리티 관련 항목이 나오지만 사용자는 다음을 이해하기 어렵다.

* 어떤 데이터로 멘탈리티를 판단했는지
* FM 능력치인지, Growth Model인지, 사용자가 입력한 텍스트인지
* “좋다/나쁘다”가 어떤 기준인지
* 정성 텍스트를 넣으면 이 분석에 반영되는지

---

## 6. 수정 방향

멘탈리티 분석은 아래 3가지 근거를 구분해 표시한다.

1. 능력치 기반 멘탈/성향 데이터

   * 기존 `mentality_jsonb` 또는 관련 FM-derived fields 사용
   * 사용자 화면에서는 “능력치 기반 멘탈/성향 분석”이라고 표현

2. 성장 모델 기반 리스크/안정성

   * Growth Score 구성요소 중 멘탈/활동량/리스크 관련 항목
   * 사용자 화면에서는 “성장 모델 기반 안정성 평가”라고 표현

3. 사용자가 입력한 정성 텍스트

   * 코치 메모, 기사, 스카우팅 메모 등
   * Gemini가 가능하면 신호 추출
   * Gemini가 불가능하면 저장된 텍스트는 “정성 메모 입력됨”으로만 표시하고 분석 실패 안내

---

## 7. Player Dossier에 정성 텍스트 기반 멘탈리티 보조 분석 추가

대상:

* `views/dashboard.py`
* `views/ai_report.py`
* `services/qualitative_evidence.py`
* `explanation_engine.py`
* `scouting_note_payload.py` 필요 시 확인

요구사항:

* Player Dossier 또는 Evidence Report에 “정성 메모로 멘탈/태도 보완 분석” 영역을 둔다.
* 사용자가 텍스트를 넣으면 Gemini가 가능한 경우 다음 신호를 추출한다.

  * 훈련 태도
  * 코치 신뢰
  * 경기 집중도
  * 압박 상황 판단
  * 부상/피로 리스크
  * 멘탈 안정성
  * 성장 의지
  * 출전 시간 변화
* 추출 결과는 “멘탈리티 보조 분석”으로 표시한다.
* 기존 능력치 기반 멘탈리티 분석과 Gemini 보조 분석을 섞지 말고 구분한다.

사용자용 표현 예시:

```text id="n2e04v"
능력치 기반으로는 활동량과 경기 집중도는 긍정적으로 보입니다.
다만 사용자가 입력한 정성 메모에서는 강한 압박 상황에서 판단이 늦어질 수 있다는 내용이 있어, 실제 경기에서의 압박 대응은 추가 확인이 필요합니다.
```

주의:

* Gemini가 실패했을 때 멘탈리티 분석 전체가 사라지면 안 된다.
* Gemini 분석은 “보조 분석”임을 명확히 한다.
* 정성 텍스트가 없으면 “정성 메모 없음”으로 표시한다.
* 정성 텍스트가 없는데 기사/코치 메모가 있다고 말하지 않는다.

---

## 8. 멘탈리티 설명 UI 구조

Player Dossier의 멘탈리티 관련 설명은 다음 구조로 표시한다.

```text id="544xx9"
[멘탈/성향 분석]

1. 능력치 기반 평가
- 활동량 / 집중력 / 판단 안정성 / 팀워크 등
- 근거 badge: 능력치 기반

2. 성장 모델 관점
- 현재 성장 리스크 또는 안정성
- 근거 badge: 성장 모델

3. 정성 메모 보조 분석
- 사용자가 입력한 텍스트 기반
- Gemini 가능 시 신호 추출 결과
- Gemini 불가 시 호출 실패 안내
- 근거 badge: 정성 메모 / Gemini 보조
```

---

# PART C. Career Simulation 입력 방식 개선

## 9. 문제

현재 Career Simulation에서 훈련강도와 출전기회가 숫자 슬라이더로 되어 있다.

사용자는 다음을 이해하기 어렵다.

* 훈련강도 1.20이 어느 정도인지
* 출전기회 0.60이 얼마나 적은 출전인지
* 1.5가 무슨 기준인지
* 어떤 선택이 현실적으로 어떤 상황을 의미하는지

---

## 10. 수정 방향

숫자 슬라이더를 사용자 친화적인 선택형 입력으로 바꾼다.

대상:

* `views/career_simulation.py`

기존 내부 계산 값은 유지해도 되지만, 사용자에게는 숫자만 노출하지 않는다.

---

## 11. 훈련강도 선택지

숫자 슬라이더 대신 selectbox/radio/segmented control을 사용한다.

권장 선택지:

```python id="4de83i"
TRAINING_OPTIONS = {
    "낮음 - 회복 중심": {
        "value": 0.90,
        "description": "부상 위험을 낮추고 회복을 우선하는 관리형 훈련입니다."
    },
    "보통 - 균형 유지": {
        "value": 1.00,
        "description": "성장과 컨디션을 균형 있게 가져가는 기본 훈련 강도입니다."
    },
    "높음 - 성장 집중": {
        "value": 1.10,
        "description": "기술/피지컬 향상을 적극적으로 노리는 훈련 강도입니다."
    },
    "매우 높음 - 단기 집중": {
        "value": 1.20,
        "description": "단기 성장 자극은 크지만 피로와 부상 리스크 관리가 필요한 강도입니다."
    }
}
```

주의:

* 기존 공식에서 1.20을 사용하고 있었다면 그대로 연결 가능
* 숫자는 개발자용 상세 또는 tooltip에서만 보이게 한다.
* 메인 화면에는 설명 중심으로 표시한다.

---

## 12. 출전기회 선택지

숫자 슬라이더 대신 selectbox/radio/segmented control을 사용한다.

권장 선택지:

```python id="j9xfo2"
PLAYTIME_OPTIONS = {
    "부족 - 벤치/간헐 출전": {
        "value": 0.60,
        "description": "정기적인 경기 리듬을 만들기 어려운 출전 환경입니다."
    },
    "제한적 - 교체 중심": {
        "value": 0.80,
        "description": "교체 출전이나 일부 컵 대회 중심으로 경험을 쌓는 단계입니다."
    },
    "보통 - 로테이션": {
        "value": 1.00,
        "description": "리그/컵에서 일정 수준의 출전 기회를 받는 환경입니다."
    },
    "충분 - 주전급 출전": {
        "value": 1.15,
        "description": "꾸준한 선발 또는 주요 교체 자원으로 성장 경험을 쌓을 수 있습니다."
    },
    "과다 - 혹사 위험": {
        "value": 0.95,
        "description": "경험은 많지만 피로 누적과 부상 위험을 함께 관리해야 합니다."
    }
}
```

주의:

* “과다”는 무조건 성장에 긍정으로만 처리하지 않는다.
* 기존 공식 변경이 필요하면 하지 말고, 기존 adjustment 범위에 맞춰 value만 매핑한다.
* 사용자 화면에는 value보다 의미 설명을 보여준다.

---

## 13. 리그 난이도 / 리스크 성향 설명 추가

리그 난이도와 리스크 성향도 설명을 붙인다.

예시:

```text id="6nhnbh"
리그 난이도: 높은 리그 수준은 성장 자극을 줄 수 있지만, 출전 시간이 줄어들면 성장 기회가 제한될 수 있습니다.

리스크 성향: 공격적인 선택은 성장 가능성을 높일 수 있지만, 실패 가능성도 함께 커집니다.
```

---

## 14. 시뮬레이션 결과 설명 개선

결과 화면에는 선택한 옵션을 자연어로 요약한다.

예시:

```text id="oujgx3"
현재 설정은 ‘높은 훈련 강도 + 제한적 출전 기회’ 조합입니다.
훈련 자극은 크지만 실제 경기 경험이 부족해 성장 효과가 일부 제한될 수 있습니다.
따라서 단기 훈련 성과보다 출전 기회 확보가 우선 과제로 보입니다.
```

주의:

* 숫자는 숨기거나 developer detail expander에 둔다.
* 결과 해석은 선택 옵션과 모순되면 안 된다.

---

# PART D. 불필요한 데이터 타입 안내 제거

## 15. 문제

화면에 다음과 같은 안내가 보인다.

* 데이터 타입에 따른 해석 제한 안내
* Transfermarkt + FM profile 조합 설명
* 10x10 Grid
* proxy
* vector

사용자는 내부 데이터 구조를 알 필요가 없다.

---

## 16. 수정 방향

대상:

* `views/dashboard.py`
* `views/prospect_search.py`
* `views/legend_matching.py`
* `views/career_simulation.py`
* `views/ai_report.py`
* `ui_components.py`

수정:

* 사용자 메인 화면에서 기술적 데이터 타입 안내를 제거한다.
* 필요한 경우 아래처럼 사용자 친화적인 문구만 남긴다.

대체 문구:

```text id="0moepq"
이 선수는 저장된 선수 정보와 능력치 데이터를 함께 활용해 분석할 수 있습니다.
```

또는

```text id="qj7agv"
현재 데이터가 부족한 항목이 있어 일부 분석은 제한적으로 제공됩니다.
```

개발자용 상세:

* 내부 데이터 조합
* FM profile 여부
* style_vector 여부
* 10x10 Grid 미사용
* DB table 정보

이 정보는 `개발자용 데이터 상세 보기` expander 안으로 이동한다.

---

# PART E. Scouting Board 기본 정책 수정

## 17. 유망주 검색 기본 정책

사용자 요청:

* 유망주 검색에서는 항상 FM profile 있는 선수만 보여주고 싶다.
* FM profile 없는 선수는 기본 검색 결과에서 제외한다.
* Limited 포함 옵션도 최종 사용자 화면에서는 굳이 강조하지 않는다.

대상:

* `views/prospect_search.py`

수정:

* 기본 필터는 항상 FM profile 있는 선수만 보여준다.
* `분석 가능한 유망주만 보기`는 기본 on이고 사용자가 끄기 어렵게 하거나 제거한다.
* `Limited 선수 포함` 옵션은 기본적으로 숨기거나 advanced expander 안에 넣는다.
* 사용자 기본 검색 결과에서는 Full/Partial 중 FM profile 있는 선수만 보여준다.
* FM profile 없는 선수는 Manual Prospect 또는 DB Status/advanced 확인 용도로만 접근하게 한다.

주의:

* 내부 테스트가 기대하는 gating 정책은 깨지지 않게 한다.
* Bo-kyung Kim 같은 Limited 선수는 기본 검색에서 보이면 안 된다.
* DB에는 남겨두되 사용자 기본 검색에서는 숨긴다.

---

## 18. Scouting Board UI 문구 수정

현재:

* Full/Partial/Limited
* FM profile
* profile_id
* style_vector
* 분석 가능성

이런 표현이 너무 기술적으로 보일 수 있다.

사용자용 대체:

* `분석 준비 완료`
* `일부 데이터 기반 분석`
* `추가 데이터 필요`

단, 내부 badge class나 상태 값은 유지해도 된다.
사용자에게 보이는 label만 바꾼다.

---

# PART F. Style & Mentor Lab 단순화

## 19. 유사 선수 후보 숨기기

사용자 요청:

* 유사 선수 후보가 왜 필요한지 모르겠다.
* 멘토 후보만 보여주는 것이 더 낫다.

대상:

* `views/legend_matching.py`

수정:

* 기본 화면에서는 Similarity Candidates 섹션을 숨긴다.
* Mentor Candidates 섹션을 메인으로 올린다.
* 유사 선수 후보는 필요하면 `분석 기준 / 유사 선수 참고 보기` expander 안으로 접어둔다.
* 화면 제목과 설명도 멘토 중심으로 바꾼다.

예:

* 기존: `Style & Mentor Lab`
* 변경 가능: `Mentor Matching Lab`
* 설명: `현재 선수와 비슷한 성장 경로를 참고할 수 있는 멘토 후보를 찾아줍니다.`

---

## 20. Mentor Candidates 중심 구조

권장 구조:

```text id="pnhhxu"
[선택 선수 요약]

[멘토 추천 요약]
- 이 선수에게 필요한 성장 방향
- 추천 멘토 후보 수
- 멘토 추천 기준

[Mentor Candidates]
- 멘토 카드 목록

[Selected Mentor Guide]
- 선택 멘토
- 배울 점
- 훈련 방향
- 주의할 점
- 다음 단계 CTA
```

멘토 카드에는 다음만 표시한다.

* 이름
* 나이
* 포지션
* 팀
* 멘토 적합도
* 배울 수 있는 점
* 주의할 점
* 선택 버튼

숨기거나 expander로 보낼 것:

* style_vector
* proxy
* pgvector
* raw similarity score
* attributes_jsonb
* 10x10 Grid 관련 문구

---

# PART G. 문서 업데이트

## 21. 문서 업데이트

작업 후 아래 문서를 업데이트한다.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `ACTIVE_FUNCTION_MAP.md`
3. `REAL_MODEL_PLAN.md`
4. `AGENTS.md`
5. `FOLDER_ORGANIZATION_REPORT.md` 또는 `CLEANUP_AUDIT_REPORT.md`에 추가 기록

섹션명:

```text id="o92qgr"
v19 Final User Flow Fix: Gemini handling, mentality evidence, scenario labels, and mentor-first UX
```

포함 내용:

* Gemini 오류 처리 개선
* 멘탈리티 분석 근거 개선
* 정성 텍스트 기반 멘탈리티 보조 분석
* Career Simulation 입력 방식 개선
* 불필요한 데이터 타입 안내 제거
* Scouting Board 기본 FM profile-only 정책
* Mentor-first UX 변경
* 테스트 결과

---

## 22. 테스트 요구사항

작업 후 반드시 실행한다.

```bash id="fas4nm"
python -m compileall .
python test_state_refactor.py
python test_analysis_helpers_split.py
python test_prospect_search_split.py
python test_growth_model.py
```

Streamlit health check도 실행한다.

---

## 23. 절대 금지

* DB 스키마 변경 금지
* `create_and_upload_db.py` 수정 금지
* `.streamlit/secrets.toml` 내용 출력 금지
* `.env` 내용 출력 금지
* API key 값 출력/저장/문서화 금지
* 원본 CSV 수정 금지
* Growth/Ceiling 공식 변경 금지
* style_vector 계산 방식 변경 금지
* pgvector/secrets.toml` 내용 출력 금지
* `.env` 내용 출력 금지
* API key 값 출력/저장/문서화 금 similarity 쿼리 변경 금지
* 기존 JSONB key 삭제 금지
* legacy fallback 삭제 금지
* Gemini에게 점수 계산 맡기기 금지
* Gemini가 없는 사실을 지어내게 하기 금지
* 실제 import되는 Python 파일 임의 이동/삭제 금지
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md` 읽기/수정 금지
* 데이터에 없는 강점/약점을 지어내는 것 금지
* 사용자용 화면에 개발자용 원자료 key를 노출하는 것 금지

---

## 24. 완료 보고 형식

완료 후 아래 형식으로 보고한다.

1. 수정한 코드 파일
2. 수정한 문서 파일
3. Gemini 오류 처리 개선 내용
4. 멘탈리티 분석 근거 개선 내용
5. 정성 텍스트 기반 멘탈리티 보조 분석 내용
6. Career Simulation 입력 방식 개선 내용
7. 시나리오 설명 문구 개선 내용
8. 제거/숨김 처리한 불필요한 데이터 타입 안내
9. Scouting Board FM profile-only 정책 반영 내용
10. Style & Mentor Lab mentor-first 변경 내용
11. 기존 기능 보존 여부
12. session_state 영향 여부
13. 테스트 결과
14. Streamlit health check 결과
15. 사용자가 다시 확인해야 할 화면
16. 남은 문제
