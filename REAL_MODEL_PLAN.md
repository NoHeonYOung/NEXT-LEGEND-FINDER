# REAL_MODEL_PLAN.md — 실 DB 기반 성장 예측 모델 + 설명 가능한 성장 분석 UI

이 문서는 `players`, `appearances`, `player_valuations`, `player_profiles` 4개의 실제 Supabase 테이블만을
사용해 만든 Growth Model(`growth_model.py`)과 Explanation Engine(`explanation_engine.py`)의 설계를 정리한다.
샘플 데이터/CSV를 새로 만들지 않았으며, 기존 `services/db.py`의 `get_valuations` / `get_appearances` /
`get_player` / `get_profile_by_player_id`를 그대로 재사용한다.

## 1. 사용 가능한 DB 데이터

- `players`: `player_id`, `name`, `date_of_birth`, `position`, `current_club_name` 등 (Transfermarkt 기반)
- `appearances`: `player_id` 기준 `date`, `competition_id`, `goals`, `assists`, `yellow_cards`, `red_cards`,
  `minutes_played` (최근 출전 기록, `get_appearances`로 날짜 내림차순 조회)
- `player_valuations`: `player_id` 기준 `date`, `market_value_in_eur`, `current_club_name` (시계열, `get_valuations`로
  날짜 오름차순 조회)
- `player_profiles`: `profile_id`, `player_id`, `age`, `position`, `attributes_jsonb`(FM 1~20 proxy 능력치),
  `mentality_jsonb`(`basis` + `mentality_score`), `style_vector`

`growth_model.py`는 위 데이터를 **인자로 전달받아 계산만 수행**하며, 자체적으로 DB를 조회하거나
`app.py`를 import하지 않는다.

## 2. 모델의 목적

- 선수의 시장가치 흐름·출전 기회·기여도·나이·능력치·멘탈리티를 종합해 0~100점의 `Growth Score`를 산출한다.
- 데이터가 부족한 항목은 제외하고 남은 항목의 weight를 재정규화해, 매칭 상태(entity_type)가 달라도
  항상 일관된 방식으로 점수를 계산한다.
- 점수와 함께 "왜 이 점수가 나왔는지", "강점/리스크/추천 방향"을 설명하는 rule-based 텍스트를 생성한다.

## 3. Feature 목록과 weight

| feature | weight | 설명 |
| --- | --- | --- |
| market_momentum | 0.30 | 최근 valuation 대비 약 6개월~1년 전 valuation의 로그 성장률 |
| playing_opportunity | 0.20 | 최근 10경기 출전 시간(없으면 출전 횟수) |
| contribution_score | 0.15 | 90분당 (골+어시스트), 포지션별 baseline과 비교 |
| age_potential | 0.15 | 21세 기준 나이 성장 곡선 |
| attribute_strength | 0.10 | `attributes_jsonb` 평균 (1~20 또는 0~100 스케일 자동 감지) |
| mentality_strength | 0.10 | `mentality_jsonb.basis` 평균 (또는 `mentality_score`) |

## 4. Growth Score 공식

```
weighted_score = sum(weight_i * score_i) for available features
available_score = weighted_score / sum(available_weight_i)   # 재정규화
final_growth_score = clamp(available_score * 100 - risk_penalty, 0, 100)
```

- 모든 feature가 unavailable이면 `growth_score = None`, `growth_status = "unavailable"`.
- `risk_penalty`(0~15)는 시장가치 하락(-5), 낮은 출전 기회(-5), 데이터 부족(1개 이상 -2, 3개 이상 -5)을 합산한 값이다.

## 5. Fallback 처리

- `compute_market_momentum`: valuation이 2개 미만이면 unavailable.
- `compute_playing_opportunity`: appearances가 없으면 unavailable. `minutes_played`가 전부 비어있으면
  출전 횟수 기반으로 fallback.
- `compute_contribution_score`: appearances가 없으면 unavailable. position이 없으면 `unknown` baseline(0.35) 사용.
- `compute_age_potential`: `player_profiles.age` 우선, 없으면 `players.date_of_birth`로 계산. 둘 다 없으면 unavailable.
- `compute_attribute_strength` / `compute_mentality_strength`: `player_profiles`가 없거나 jsonb가 비어있으면 unavailable.
- 위 항목이 unavailable일 때는 `compute_growth_score`에서 해당 weight를 제외하고 남은 weight로 재정규화한다.

## 6. Dashboard 표시 내용 (Growth Insight 섹션)

`views/dashboard.py`의 `render_dashboard_view`에서 `entity_type != "manual_note"`인 경우 표시:

- Growth Score (메트릭 + progress bar)
- 6개 feature 점수 (각 feature label은 `FEATURE_LABELS` 사용, unavailable이면 회색 텍스트로 "데이터 부족" 표시)
- risk_penalty가 0보다 크면 `st.warning`으로 패널티와 사유 표시
- "왜 이 점수가 나왔나요?" (score_reason), summary, strengths, risks, recommendations, data_limitations
- 개발자용 expander로 `growth_insight`/`growth_explanation` 원본 JSON 확인 가능
- 결과는 `st.session_state["growth_insight"]`, `st.session_state["growth_explanation"]`에 저장되어
  Career Simulation/AI Report에서 재사용된다.

## 7. Career Simulation 표시 내용 (Real Data Growth Baseline)

`views/career_simulation.py`에서 기존 `simulation_result`(프로토타입 시뮬레이션)는 그대로 유지하고,
선수가 실제 `player_id`를 가지고 있으며 `entity_type != "manual_note"`인 경우 별도 섹션을 추가한다:

- 프로토타입 성장 점수 vs 실제 데이터 기반 Growth Score를 나란히 표시
- 두 점수의 차이를 해석하는 문장 (비슷함 / 실제가 더 높음 / 실제가 더 낮음)
- 6개 feature 점수 요약
- summary, recommendations, 데이터 커버리지(`data_limitations`)
- 결과는 `st.session_state["growth_insight"]`, `st.session_state["growth_explanation"]`에 저장(덮어쓰기)되며,
  기존 `env_settings`/`simulation_result` 키는 변경하지 않는다.

manual_note 또는 `player_id`가 없는 경우에는 "Real Data Growth Baseline은 매칭된 선수에서만 표시됩니다"라는
안내만 표시한다.

## 8. Manual Note(직접 입력) 입력 해석

`views/scouting_notes.py`의 직접 입력 폼에서 각 슬라이더/선택값을 4단계(또는 3단계)로 분류해 설명을 보여준다
(`growth_model.classify_*` 함수 + `LEVEL_DESCRIPTIONS`):

- 훈련 강도(0.5~2.0) → 낮음/보통/높음/매우 높음
- 리그/팀 수준(low/medium/high/elite) → 낮음/보통/높음/매우 높음
- 출전 기회(0.0~1.0) → 낮음/보통/높음/매우 높음
- 리스크 성향(safe/normal/aggressive) → 안정형/균형형/도전형

각 항목 아래에 `st.caption`으로 레벨과 설명을 표시한다.

### manual_growth_score 공식

```
manual_growth_score = 0.25*age_potential + 0.20*playing_opportunity_score
                     + 0.20*training_intensity_score + 0.20*league_level_score
                     + 0.15*self_attribute_score - manual_risk_penalty (+ risk 보너스)
```

- 매핑 테이블: `TRAINING_INTENSITY_SCORES`, `LEAGUE_LEVEL_SCORES`, `PLAYING_OPPORTUNITY_SCORES`
  (낮음=0.35/0.30, 보통=0.55, 높음=0.75/0.78, 매우 높음=0.90/0.92)
- `RISK_TENDENCY_PENALTY` (안정형=2, 균형형=5, 도전형=8), 리그 난이도가 높음/매우높음이고 도전형이면 +3
- `RISK_TENDENCY_GROWTH_BONUS`: 도전형은 +3점 보너스(패널티도 함께 증가)
- 능력치 입력값이 없으면 `self_attribute` 항목을 제외하고 재정규화

제출 시 `build_manual_growth_insight` + `build_growth_explanation` 결과를 `st.session_state["growth_insight"]`,
`st.session_state["growth_explanation"]`에 저장하고, "직접 입력 기반 prototype"이라는 경고 문구로 실제 DB 기반
모델과 구분해 표시한다.

## 9. Explanation Engine 설계 (`explanation_engine.py`)

- `explain_feature_score(feature_name, feature_result)`: feature 1개에 대한 한 문장 설명
- `build_strengths(features)` / `build_risks(features, risk_penalty)` / `build_recommendations(features, player_context)`
- `_build_data_driven_explanation` (matched/transfermarkt_only/fm_profile_only) /
  `_build_manual_explanation` (manual_note) — `build_growth_explanation`이 `growth_insight["mode"]`에 따라 분기
- 출력 구조: `{summary, score_reason, strengths, risks, recommendations, data_limitations, gemini_ready_payload}`
- `ENTITY_TYPE_CONTEXT_NOTES`로 entity_type별 설명 톤을 구분

## 10. 향후 Gemini 연동 구조

- `build_gemini_ready_payload(growth_insight, explanation, player_context)`가 player_context, mode, entity_type,
  growth_score, features, levels/scores, risk_penalty, rule_based_explanation, instructions_for_gemini를
  포함한 구조화된 dict를 반환한다.
- 이 dict는 `explanation["gemini_ready_payload"]`로 항상 함께 생성되지만, 이번 세션에서는 어떤 화면에서도
  Gemini API를 호출하지 않는다. 추후 이 payload를 그대로 Gemini API에 전달하면, 점수/사실은 유지하면서
  설명 문체만 자연스럽게 다듬은 리포트를 생성할 수 있다.

## 11. AI Report 연동

`views/ai_report.py`의 `get_report_sections`는 `growth_insight`/`growth_explanation`이 `session_state`에
있으면 "Growth Model Insight" 섹션을 추가로 생성한다(Gemini 호출 없이 템플릿 텍스트). 없으면 기존과 동일하게
동작하며 기존 리포트 구조/저장 로직은 변경되지 않았다.

## 12. 제한사항

- `market_momentum`은 valuation 2개 이상, `playing_opportunity`/`contribution_score`는 appearances 1개 이상이
  필요하다. fm_profile_only 선수는 이 두 데이터가 없어 항상 unavailable로 처리되고 attribute/mentality 중심으로만
  평가된다.
- `attribute_strength`/`mentality_strength`는 `player_profiles`가 없는 transfermarkt_only 선수에서는 unavailable이다.
- manual_note의 `manual_growth_score`는 실제 데이터 기반 예측이 아닌 prototype이며, UI에서 항상 이를 명시한다.
- 모든 설명은 rule-based 템플릿이며, Gemini 연동 전까지는 문장 다양성에 한계가 있다.

## 13. 테스트 계획

- `python -m compileall .` — 신규/수정 파일 구문 검사
- `test_state_refactor.py`, `test_analysis_helpers_split.py`, `test_prospect_search_split.py` — 기존 화면 흐름 회귀 테스트
- `test_growth_model.py` (신규) — `growth_model`/`explanation_engine` 단위 테스트 + Dashboard/Scouting Notes AppTest
- `streamlit run app.py --server.headless true` 헬스 체크

---

## 14. Ceiling Model 시나리오 보정 레이어 (v12)

이번 세션에서는 v11에서 구현한 Real Data Growth Score(= `growth_score`)를 다시 만들지 않고,
그 위에 **초기 기획(`archive/docs/CLAUDE_TASK_FULL.md`)의 Ceiling Model 공식**을 보정 레이어로
추가했다.

### 14.1 초기 기획 공식

```
Potential_final = Potential_base + Σ(Δleague × (α × γ - β))
```

- `Potential_base`: 기본 잠재력/성장 점수
- `Δleague`: 리그 이동·환경 변화로 인한 성장 변화량
- `α`: 출전 확률/출전 기회
- `γ`: 리그 난이도
- `β`: 부상 위험/적응 실패 리스크
- `training_multiplier`: 훈련 강도에 따른 성장 속도(곡선 기울기) 배수 — 초기 기획의 "훈련 강도" 항을
  공식에 명시적으로 곱하는 형태로 확장

### 14.2 3단 구조: Real Data Growth Baseline → Ceiling Scenario Adjustment → Final Growth Score

```
Real Data Growth Baseline = growth_model.build_growth_insight(...)["growth_score"]
                             (manual_note는 build_manual_growth_insight(...)["growth_score"])

Ceiling Scenario Adjustment = Δleague × ((α × γ × training_multiplier) - β)
                               (-15 ~ +15로 clamp)

Final Growth Score = clamp(Real Data Growth Baseline + Ceiling Scenario Adjustment, 0, 100)
```

`Real Data Growth Baseline`은 기존 Growth Score 계산 로직(시장가치 30% + 출전기회 20% +
기여도 15% + 나이 잠재력 15% + FM 능력치 10% + 멘탈리티 10% - risk_penalty)을 그대로
`Potential_base`로 사용한다. 기존 weight/risk_penalty 로직은 1바이트도 변경하지 않았다.

### 14.3 α, γ, β, training_multiplier, Δleague 정의/매핑

`growth_model.py`의 `classify_*` 결과(낮음/보통/높음/매우 높음, 안정형/균형형/도전형)를
재사용해 다음 4개 mapping 함수로 변환한다:

| 함수 | 의미 | 매핑 |
| --- | --- | --- |
| `map_league_difficulty(value)` | γ(리그 난이도) | 낮음=0.5, 보통=1.0, 높음=1.25, 매우 높음=1.5 |
| `map_playing_opportunity(value)` | α(출전 확률/기회) | 낮음=0.1, 보통=0.45, 높음=0.7, 매우 높음=0.9 |
| `map_training_intensity(value)` | training_multiplier | 낮음=1.0, 보통=1.25, 높음=1.6, 매우 높음=2.0 |
| `map_risk_tendency(value)` | β(부상/적응 리스크) | 안정형=0.10, 균형형=0.25, 도전형=0.40 |

각 함수는 `(level_label, numeric_value)` 튜플을 반환한다.

`compute_delta_league(career_choice, league_level, playing_opportunity)`는 커리어 선택
(`stay`/`loan`/`transfer`)과 리그난이도/출전기회 레벨 조합으로 Δleague와 시나리오 라벨을
결정한다:

| 시나리오 | Δleague | 조건 |
| --- | --- | --- |
| 안정적 잔류 성장 시나리오 | 4 | 잔류 + 출전기회 낮음/보통 |
| 균형형 성장 환경 시나리오 | 7 | 잔류 + 출전기회 높음/매우 높음, 또는 이적/임대 + 리그난이도 낮음/보통 + 출전기회 높음/매우 높음 |
| 상위 리그 도전형 성장 시나리오 | 10 | 이적/임대 + 리그난이도 높음/매우 높음 + 출전기회 높음/매우 높음 |
| 무리한 도전/출전 부족 시나리오 | 6 | 이적/임대 + 출전기회 낮음/보통 (β 추가 증가) |

이적/임대 + 출전기회가 낮음/보통이면 β가 +0.10 추가되며, 여기에 리그난이도가 "매우 높음"이고
리스크성향이 "도전형"이면 β가 다시 +0.10 추가된다(최대 1.0으로 clamp).

### 14.4 Scenario Adjustment / Final Growth Score 공식

```python
raw_adjustment = delta_league * ((alpha * gamma * training_multiplier) - beta)
scenario_adjustment = clamp(raw_adjustment, -15, 15)
final_growth_score = clamp(potential_base + scenario_adjustment, 0, 100)
```

- `compute_ceiling_scenario_adjustment(env_settings)`: env_settings(`training_intensity`,
  `playing_time_opportunity`, `league_difficulty`, `career_choice`, `risk_level`)로
  α/γ/β/training_multiplier/Δleague와 `scenario_adjustment`, `scenario_label`, `notes`를 계산.
- `apply_ceiling_adjustment(growth_insight, env_settings)`: `growth_insight["growth_score"]`(또는
  manual_note의 `growth_score`)를 `potential_base`로 사용해 `growth_insight["ceiling_model"]`
  key를 추가한다. 기존 key는 변경하지 않는다(append-only).

### 14.5 Manual Note 적용 방식

`views/scouting_notes.py`에서 `build_manual_growth_insight(...)`로 만든
`manual_growth_score`를 `Potential_base`로 사용해 동일하게 `apply_ceiling_adjustment`를
적용한다. UI에서는 다음과 같이 명명해 실제 DB 기반 모델과 구분한다:

```
Manual Prototype Baseline = manual_growth_score
Ceiling Scenario Adjustment = (위와 동일한 공식)
Manual Final Growth Score = clamp(Manual Prototype Baseline + Scenario Adjustment, 0, 100)
```

### 14.6 UI 표시 방식

- `views/career_simulation.py`: `has_player_id and entity_type != "manual_note"`일 때
  "1. Real Data Growth Baseline" → "2. Ceiling Scenario Adjustment (초기 기획 수식 반영)" →
  "3. Final Growth Score" 3단 섹션으로 표시. 2번 섹션에서 α/γ/β/training_multiplier/Δleague
  값과 +/- 보정 방향, 강점/리스크/추천 전략을 표시. 3번 섹션은 Final Growth Score
  metric+progress bar와 프로토타입 시뮬레이션 점수와의 비교 문장을 표시.
- `views/scouting_notes.py`: manual_note 미리보기의 "Growth Insight (직접 입력 기반 prototype)"
  섹션 내에 Manual Prototype Baseline → Ceiling Scenario Adjustment → Manual Final Growth Score를
  같은 구조로 표시. 항상 "직접 입력 기반 prototype + 시나리오 보정"이라는 라벨로 실제 DB 모델과
  구분.
- `views/ai_report.py`: `growth_explanation["ceiling_explanation"]`이 있으면 "Ceiling Scenario
  Insight" 섹션을 추가(Real Data Growth Baseline/Scenario Adjustment/Final Growth Score,
  α/γ/β 설명, 주요 강점/리스크/추천 전략).

### 14.7 Explanation Engine 확장

- `explain_ceiling_variables(ceiling_model)`: α/γ/β/training_multiplier/Δleague가 각각
  무엇을 의미하는지 문장으로 설명.
- `build_scenario_strengths/risks/recommendations(ceiling_model)`: 어떤 선택값이 점수를
  올렸는지/리스크를 키웠는지/추천 전략은 무엇인지 정리.
- `build_ceiling_explanation(growth_insight)`: 위 함수들을 묶어
  `{ceiling_summary, scenario_variables, variable_explanations, scenario_adjustment,
  final_growth_score, scenario_strengths, scenario_risks, scenario_recommendations}`을 생성.
  `growth_insight["ceiling_model"]`이 없으면 `None`.
- `build_growth_explanation`은 결과에 `ceiling_explanation` key를 추가하고,
  `gemini_ready_payload`에도 `ceiling_model`/`ceiling_explanation`을 포함한다.

### 14.8 한계점

- Δleague 매핑(4/7/10/6)과 추가 β 증가(+0.10) 규칙은 초기 기획 문서의 정성적 설명을
  바탕으로 한 수치화이며, 실제 통계적 근거는 아니다. 추후 실 데이터 기반 보정이 필요하다.
- `scenario_adjustment`는 ±15로 clamp되므로, α×γ×training_multiplier가 매우 큰 조합(예:
  α=0.9, γ=1.5, training_multiplier=2.0)에서도 Final Growth Score에 미치는 영향은 제한적이다.
- Ceiling Model은 여전히 rule-based 보정이며, Gemini 연동 전까지는 시나리오 설명 문장의
  다양성에 한계가 있다.

---

## 15. Ceiling 결과 session_state 보존 구조 (v13)

Ceiling Model의 계산식과 결과 구조는 v12를 그대로 유지한다. v13은 화면 이동 과정에서 Ceiling
결과가 기본 Growth 결과에 의해 덮어써지지 않도록 session_state 저장 영역과 context 판정을 분리한다.

### 15.1 저장 key

```python
st.session_state["growth_insight"]
st.session_state["growth_explanation"]

st.session_state["ceiling_growth_insight"]
st.session_state["ceiling_growth_explanation"]
st.session_state["ceiling_growth_context"]
```

- 기본 key는 현재 화면이 계산한 Growth 결과를 저장한다.
- Ceiling 전용 key는 `ceiling_model`과 `ceiling_explanation`이 포함된 결과를 보존한다.
- `ceiling_growth_context`는 `entity_type`, `player_id`, `profile_id`, `source`로 결과 소유자를 식별한다.

### 15.2 화면별 수명주기

- Dashboard: 기본 Growth 결과만 갱신하며 Ceiling 전용 key를 삭제하거나 덮어쓰지 않는다.
- Career Simulation: Ceiling 결과를 기본 key와 Ceiling 전용 key에 모두 저장하고 현재 선수 context를 저장한다.
- Manual Note: Manual Ceiling 결과와 `entity_type="manual_note"`, `source="manual_note"` context를 저장한다.
- AI Report: 현재 선택 상태와 Ceiling context가 일치하면 Ceiling 결과를 우선 사용한다.
  불일치하거나 불확실하면 기본 Growth 결과로 fallback한다.
- Prospect Search: 다른 선수 선택 시 growth/ceiling/report 관련 key를 clear한다.
  기존 stale `selected_profile_id` 및 `selected_entity_type` 초기화 흐름은 유지한다.

### 15.3 불변 조건

- Growth Model 공식과 Ceiling Model 공식은 변경하지 않는다.
- Dashboard 재방문은 보존된 Ceiling 결과를 제거하지 않는다.
- 다른 선수의 Ceiling 결과는 AI Report에서 사용하지 않는다.
- 선수 변경 시 이전 선수의 Growth/Ceiling/Report session_state를 제거한다.
- Manual Note Ceiling 결과는 일반 선수 Ceiling 결과와 context로 구분한다.

### 15.4 테스트

`test_growth_model.py`는 19개 테스트로 확장되었으며 Ceiling 전용 key 저장, Dashboard 재방문 보존,
AI Report의 `Ceiling Scenario Insight` 유지, 다른 선수 선택 시 이전 Ceiling context 제거를 검증한다.

---

## 16. v14: scoring calibration + coaching-style explanation 개선

### 16.1 점수 보정

Real Data Growth Baseline, Ceiling Model 공식, Final Growth Score clamp 구조는 변경하지 않는다.
다만 `compute_ceiling_scenario_adjustment()`에서 매우 높은 훈련/출전 부하, 매우 높은 리그난이도,
낮은 출전기회, 고위험 이적 조합에 β 위험 가산과 코칭용 risk note를 추가한다.

### 16.2 설명 구조

기존 `ceiling_summary`, `scenario_variables`, `scenario_strengths`, `scenario_risks`,
`scenario_recommendations`는 호환성을 위해 유지한다. 사용자용 설명에는 아래 key를 우선 사용한다.

- `coaching_summary`
- `training_directions`
- `expected_benefits`
- `neglect_risks`
- `risk_warnings`
- `career_strategy`

Career Simulation과 Manual Note는 위 코칭 섹션을 기본 화면에 표시한다. 공식, α/γ/β,
training multiplier, Δleague 및 변수 설명은 `상세 계산 근거` expander 안에 둔다.
AI Report도 동일 코칭 설명을 사용하며 Gemini API를 호출하지 않는다.

`test_growth_model.py`는 v14 위험 조합과 코칭 출력 검증을 포함해 22개 테스트로 확장한다.

### 16.3 불변 조건

- v13 session_state key 분리 및 context 우선 선택 구조를 유지한다.
- 공식과 최종 점수 범위를 변경하지 않는다.
- 위험도 가산 규칙은 rule-based calibration이며 실제 데이터 검증 전까지 예측 모델로 해석하지 않는다.

---

## 17. v16: Scouting Notes structured persistence

### 17.1 저장 컬럼과 payload

DB 스키마는 변경하지 않는다. `scouting_notes.env_settings` JSONB에는 기존 입력값과 함께 아래 메타데이터를 저장한다.

- `note_type`, `source`, `entity_type`
- `player_snapshot`, `profile_snapshot`
- `ceiling_growth_context`
- `career_settings`

`scouting_notes.simulation_result` JSONB는 기존 prototype 최상위 key를 유지하며 아래 구조를 append-only로 추가한다.

- `prototype_simulation`
- `growth_insight`, `growth_explanation`
- `ceiling_growth_insight`, `ceiling_growth_explanation`, `ceiling_growth_context`
- `report_sections`, `generated_report_text`

`gemini_report` text에는 Gemini 호출 없이 생성한 template/fallback 리포트 문자열을 저장한다.

### 17.2 화면별 저장

- Career Simulation: `source="career_simulation"` 저장 버튼으로 현재 선수의 시뮬레이션과 코칭 결과를 저장한다.
- AI Report: `source="ai_report"`로 report sections/text와 현재 context에 맞는 Ceiling 결과를 저장한다.
- Manual Note: `source="manual_note"`, `note_type="manual_custom_prospect"`로 직접 입력값과 코칭 결과를 저장한다.

### 17.3 조회 및 legacy fallback

My Scouting Notes는 신규 구조가 있으면 Growth Score, Final Growth Score, 시나리오 총평,
추천 훈련 방향, 기대 장점, 소홀히 했을 때의 단점, 리스크 경고, 추천 커리어 전략을 복원한다.
신규 key가 없는 legacy note는 기존 simulation/result/report 표시 흐름을 유지하며 예외 없이 fallback한다.

### 17.4 불변 조건

- `services/db.py`는 SELECT/INSERT 역할만 유지하고 JSONB payload 조립은 순수 helper에서 수행한다.
- DB 스키마와 기존 `insert_scouting_note()` 시그니처를 변경하지 않는다.
- 저장된 결과는 당시 모델/설명 결과의 스냅샷이며 조회 시 재계산하지 않는다.
- payload 단위 테스트는 JSON 직렬화와 세 source 구분을 검증하며 실제 DB INSERT는 수행하지 않는다.

---

## 18. v16.1: Persistence QA and saved-note UI polish

### 18.1 저장 결과 표시 정책

- 저장된 Growth/Ceiling/Coaching 결과는 저장 시점 스냅샷으로 표시하며 현재 모델로 재계산하지 않는다.
- 사용자 화면에는 한국어 저장 유형/출처/선수 유형 배지, 선수 스냅샷, 기본 성장 점수,
  시나리오 반영 성장 점수, 저장된 코칭 리포트를 표시한다.
- 내부 JSON key와 원본 payload는 개발자용 expander에서만 표시한다.
- 구조화 summary/strengths/risks가 있으면 카드 fallback으로 활용하고, 없으면 legacy 표시를 유지한다.

### 18.2 Payload 안전성 정책

- helper는 Streamlit, DB, app.py를 import하지 않는다.
- datetime, tuple, numpy/pandas scalar, NaN/NA는 JSON 직렬화 가능한 값으로 정규화한다.
- report sections는 최대 50개, 문자열 섹션당 5,000자로 compact한다.
- 신규 key가 없거나 잘못된 타입이어도 `extract_structured_note_result`는 빈 구조와 legacy prototype으로 fallback한다.

### 18.3 실제 DB 수동 검수 절차

1. 실제 선수 선택 후 Career Simulation 결과를 저장하고 `note_id`를 확인한다.
2. My Scouting Notes에서 한국어 배지, 선수 정보, 기본/시나리오 성장 점수와 코칭 리포트를 확인한다.
3. AI Report 저장 후 리포트 문자열과 구조화 Growth/Ceiling 결과가 함께 복원되는지 확인한다.
4. Manual Note 저장 후 직접 입력 선수 배지와 코칭 결과가 일반 DB 선수와 구분되는지 확인한다.
5. legacy note가 예외 없이 기존 정보로 표시되는지 확인한다.

자동 테스트 및 Codex 작업에서는 사용자 명시 확인 없이 실제 DB INSERT를 수행하지 않는다.

### 18.4 QA 테스트 범위

- 세 저장 source payload의 JSON 직렬화 가능 여부
- datetime/tuple/numpy·pandas scalar/NaN/NA 변환
- 큰 report section compact 처리
- payload helper의 UI/DB/app.py 비의존성
- 사용자용 저장 유형 라벨과 신규/legacy 복원
- 저장 버튼 렌더링 및 My Scouting Notes 조회 화면 무예외 실행
