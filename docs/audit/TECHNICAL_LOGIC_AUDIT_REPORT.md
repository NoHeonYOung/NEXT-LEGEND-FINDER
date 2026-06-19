# TECHNICAL_LOGIC_AUDIT_REPORT.md
# 구현 로직 기술 검증 보고서

> 작성 기준: 현재 코드에 실제 구현된 내용만. 코드 근거(파일:라인) 표기. 미구현 기능 명시.  
> 작성일: 2026-06-19

---

## 1. 전체 요약

| 분석 영역 | 구현 방식 | 핵심 파일 |
|-----------|-----------|-----------|
| 강점/약점 판단 | rule-based 점수 임계값 (≥0.6 강점, <0.4 약점) | `explanation_engine.py`, `analysis_helpers.py` |
| 멘탈리티 분석 | FM proxy mentality_jsonb 평균 (MENTALITY_KEYS 13종) | `growth_model.py`, `analysis_helpers.py` |
| Growth Score | 6개 feature 가중평균 (0-100) + risk penalty 차감 | `growth_model.py` |
| Career Simulation | rule-based scenario 조정 ±15점 (예측 모델 아님) | `growth_model.py`, `views/career_simulation.py` |
| 멘토 추천 | pgvector cosine distance (<=> 연산자), 24차원 | `services/db.py`, `views/legend_matching.py` |
| style_vector | FM 능력치 24차원 벡터 (정규화 후 pgvector 저장) | `create_and_upload_db.py`, `services/db.py` |
| Gemini | 정성 텍스트 신호 추출 + 보조 추천만. 점수 계산 안 함 | `gemini_client.py`, `services/qualitative_evidence.py` |
| Data Coverage | Full/Partial/Limited 규칙 기반 분류 | `player_coverage.py` |
| Scouting Notes | JSONB 페이로드 저장, legacy fallback 체인 | `scouting_note_payload.py`, `views/scouting_notes.py` |

---

## 2. 실제 구현된 분석 로직 목록

- **Growth Score 계산**: 6개 feature 가중평균 → risk penalty 차감 → 0-100 점수
- **Ceiling Scenario 조정**: 훈련강도·출전기회·리그난이도·리스크·커리어선택 → ±15점 조정
- **능력치 그룹 평균**: 5개 그룹(공격/패스/피지컬/멘탈/수비) 평균 계산 및 시각화
- **멘탈리티 지표 평균**: 13개 FM proxy 멘탈 키 평균 (MENTALITY_KEYS)
- **pgvector 유사도 검색**: `<=>` 연산자로 cosine distance, 상위 80개 반환
- **멘토 나이 필터**: target_age + 5 이상, 최소 28세 (완화 시 +3, 최소 26세)
- **qualitative signal 추출**: Gemini 호출 → 6개 신호 구조화 (점수에 미반영)
- **Data Coverage 분류**: Full/Partial/Limited 3단계 (player_coverage.py)
- **Scouting Note 저장**: env_settings + simulation_result JSONB 구조
- **Legacy fallback 복원**: 구 형식 노트 데이터 chain 재구성

---

## 3. 강점/약점 판단 로직

### 3-1. 판단 데이터 소스

강점/약점은 두 레이어에서 판단됩니다:

**레이어 1 — Growth Feature 점수 (explanation_engine.py)**  
`build_strengths_with_meta(features)` (explanation_engine.py:207)
- score ≥ 0.6 → 강점 목록에 추가
- score < 0.4 → 리스크(약점) 목록에 추가
- 대상 feature: market_momentum, playing_opportunity, contribution_score, age_potential, attribute_strength, mentality_strength

**레이어 2 — 능력치 그룹 분석 (analysis_helpers.py)**  
`top_attributes(attributes, keys, limit, reverse)` (analysis_helpers.py:176)  
`summary_scores(attributes, mentality)` (analysis_helpers.py:185)

### 3-2. ATTRIBUTE_GROUPS 정의 (analysis_helpers.py:68-74)

```python
ATTRIBUTE_GROUPS = {
    "공격 능력":   ["Fin", "OtB", "Cmp", "Lon"],
    "패스/창의성": ["Pas", "Vis", "Tec", "Fir"],
    "피지컬":      ["Acc", "Pac", "Sta", "Str", "Jum", "Agi", "Bal"],
    "멘탈/활동량": ["Det", "Wor", "Tea", "Ant", "Dec"],
    "수비 능력":   ["Mar", "Tck", "Pos"],
}
```

- 각 그룹 점수 = `average_attrs()` → 그룹 내 키의 단순 평균 (analysis_helpers.py:107)
- 가중치 없음 (단순 평균)
- 포지션 기준 비교 없음 (전체 평균만 사용)

### 3-3. 능력치 스케일 기준

`compute_attribute_strength(profile)` (growth_model.py:280-299):
- attributes_jsonb에서 숫자형 값 전체 추출
- max(values) ≤ 20이면 scale=20.0, 아니면 scale=100.0
- score = `clamp(average / scale, 0, 1)`
- **절대값 기준이며 포지션별 비교 없음**

`top_attributes()`: 그룹 내 키들을 값 내림차순 정렬 → 상위 limit개 반환 → 강점 문장 생성  
`weakness_sentence()`: 하위 키들 → 약점 문장 생성 (analysis_helpers.py:227)

### 3-4. 강점 설명 문장 생성 방식

`strength_sentence(rows)` (analysis_helpers.py:220):
```
"{attr1}와 {attr2} 지표가 상대적으로 높아 해당 역할에서 강점으로 해석할 수 있습니다."
```
→ **실제 attributes_jsonb 값 기준 상위 2개 키 라벨**로 생성됨

데이터가 없을 경우: "뚜렷하게 확인되는 강점 데이터가 부족합니다."로 대체

---

## 4. 멘탈리티 분석 로직

### 4-1. 데이터 소스

`MENTALITY_KEYS` (analysis_helpers.py:76):
```python
["Agg", "Amb", "Det", "Ldr", "Loy", "Tea", "Wor", "Cons", "Pres", "Prof", "Sport", "Spor", "Temp"]
```
— FM proxy 멘탈 속성 13종. 이 키들의 값이 `mentality_jsonb.basis` dict에 저장됨.

`mentality_jsonb` 구조 (create_and_upload_db.py:502-505):
- `basis`: {Det, Wor, Tea, Ldr, Prof, Pres, Cons, Temp, Spor, Agg, Loy, Amb} 키-값 dict
- `mentality_score`: 사전 계산된 단일 평균값 (fallback용)

### 4-2. 계산 로직

`compute_mentality_strength(profile)` (growth_model.py:302-329):
1. `profile.mentality_jsonb` → `basis` dict 추출
2. `average_attrs(basis, MENTALITY_KEYS)` → 13개 키 중 존재하는 값의 평균
3. basis가 없으면 `mentality_jsonb.mentality_score` 단일값 fallback
4. scale ≤ 20 → 20-scale; > 20 → 100-scale 자동 감지
5. score = `clamp(average / scale, 0, 1)`

`summary_scores()` (analysis_helpers.py:185):
- MENTALITY_KEYS 평균으로 "멘탈 종합" 수치 생성
- UI에 숫자로 직접 표시됨 (예: 12.4 / 20)

### 4-3. 멘탈리티 해석 레이블 (analysis_helpers.py:52-66)

| 키 | 한국어 레이블 | 설명 |
|---|---|---|
| Det | 집중력 | 어려운 순간에 집중을 유지하는 성향 |
| Wor | 활동량 | 경기 중 활동 반경과 압박 참여도 |
| Tea | 팀워크 | 조직 플레이와 협력 참여 성향 |
| Ldr | 리더십 | 팀 내에서 주도적인 역할을 맡는 성향 |
| Cons | 꾸준함 | 경기력 변동을 줄이는 성향 |
| Pres | 압박 대처 | 부담이 큰 경기에서 버티는 성향 |
| Prof | 프로 의식 | 자기관리와 훈련 태도 |
| Temp | 감정 조절 | 흥분 상황에서 균형을 유지하는 성향 |
| Agg | 공격성 | 신체 접촉과 압박 강도에서의 적극성 |
| Amb | 야망 | 커리어 목표와 도전 의지 |
| Loy | 충성심 | 클럽과 팀에 대한 헌신 성향 |

### 4-4. Gemini와 멘탈리티의 관계

- Gemini는 `mentality_signal` (positive/neutral/negative/unknown) 신호를 추출함 (qualitative_evidence.py:28-37)
- **이 신호는 mentality_strength 점수를 직접 바꾸지 않음**
- 보조 추천 텍스트(coaching advice)와 리스크 경고에 반영됨
- 정성 텍스트 저장 위치: scouting_notes.simulation_result.qualitative_evidence
- 표시 위치: views/scouting_notes.py 노트 상세 화면의 "정성 분석 신호" 섹션

---

## 5. Growth Score 계산 로직

### 5-1. 구조 (growth_model.py:23-408)

```
Growth Score = [가중평균(6개 feature 점수)] × 100 − risk_penalty
```

**Rule-based 지표. 머신러닝 모델 아님.**

### 5-2. Feature 가중치

```python
GROWTH_WEIGHTS = {
    "market_momentum":    0.30,   # 시장가치 흐름 (Transfermarkt)
    "playing_opportunity":0.20,   # 출전 기회 (Transfermarkt)
    "contribution_score": 0.15,   # 공격/수비 기여도 (Transfermarkt)
    "age_potential":      0.15,   # 나이 잠재력 (DB)
    "attribute_strength": 0.10,   # FM 능력치 (attributes_jsonb)
    "mentality_strength": 0.10,   # 멘탈리티 (mentality_jsonb)
}
```

### 5-3. 각 Feature 계산

| Feature | 계산 방식 | 데이터 소스 |
|---------|----------|------------|
| market_momentum | log(현재값/과거값), 180일 기준. `clamp((growth+0.5)/1.0, 0, 1)` | Transfermarkt valuations |
| playing_opportunity | 최근 10경기 분 합계 / 900분. 분 없으면 경기수/10 fallback | Transfermarkt appearances |
| contribution_score | (골+도움)/최대(분/90, 1). 포지션별 baseline: 공격 0.5, 수비 0.25, 기타 0.35 | Transfermarkt appearances |
| age_potential | `clamp(1 - abs(age-21)/8, 0, 1)`. 21세 peak | DB/player_profiles.age |
| attribute_strength | attributes_jsonb 전체 숫자값 평균 / scale(20 or 100) | attributes_jsonb |
| mentality_strength | MENTALITY_KEYS 평균 / scale(20 or 100) | mentality_jsonb.basis |

### 5-4. 데이터 누락 처리

- 데이터 없는 feature: `"status": "unavailable"` 로 표시
- 가중합 계산 시 unavailable feature 제외, 남은 weight를 재정규화
- unavailable_count ≥ 3: risk_penalty += 5
- unavailable_count ≥ 1: risk_penalty += 2
- 점수 범위: clamp(0, 100)

### 5-5. Risk Penalty (growth_model.py:332-356)

```
market_momentum < 0.35 → +5.0
playing_opportunity < 0.2 → +5.0
unavailable_count ≥ 3 → +5.0
unavailable_count ≥ 1 → +2.0
최대 penalty: clamp(0, 15)
```

---

## 6. Career Simulation 계산 로직

### 6-1. 구조

**조건별 비교 시뮬레이션. 실제 예측 모델 아님.**

사용자가 환경 조건 선택 → 기존 Growth Score에 scenario_adjustment 가산 → Final Growth Score

### 6-2. 파라미터 매핑 (growth_model.py:564-683)

**훈련 강도 → training_multiplier:**
- 낮음(회복 중심): 1.0
- 보통(균형 유지): 1.25
- 높음(성장 집중): 1.6
- 매우 높음(단기 집중): 2.0

**출전 기회 → alpha(α):**
- 벤치/간헐: 0.1
- 교체 중심: 0.45
- 로테이션: 0.7
- 주전급: 0.9
- 과다: 0.7 (혹사 리스크 별도 표시)

**리그 난이도 → gamma(γ):**
- 낮음: 0.5 / 보통: 1.0 / 높음: 1.25 / 매우 높음(엘리트): 1.5

**리스크 성향 → beta(β):**
- 안정형: 0.10 / 균형형: 0.25 / 도전형: 0.40

**커리어 선택 → Δleague:**
- 잔류 + 높은 출전: balanced_growth = 7
- 잔류 + 기타: stable_stay = 4
- 임대/이적 + 낮은 출전: risky_challenge = 6 (extra_risk_flag)
- 임대/이적 + 높은 리그: league_challenge = 10
- 임대/이적 + 기타: balanced_growth = 7

### 6-3. 최종 공식

```
scenario_adjustment = Δleague × (α × γ × training_multiplier − β)
Final Growth Score = clamp(Growth Score + scenario_adjustment, 0, 100)
adjustment 범위: clamp(−15, 15)
```

### 6-4. 사용자 화면 구성 (views/career_simulation.py)

UI 카드 3개:
1. `{entity_label} Growth Baseline` = 실제 데이터 기반 Growth Score
2. `Scenario Adjustment` = ±조정값
3. `Final Growth Score` = 기준점 + 시나리오 조정

---

## 7. Mentor Matching 로직

### 7-1. 유사 선수 검색 (services/db.py:397-418)

```sql
SELECT
    p.profile_id, p.player_id, p.name, p.age, p.club, p.nationality, p.position,
    round((1 - (p.style_vector <=> q.style_vector))::numeric, 4) AS similarity
FROM player_profiles p
JOIN player_profiles q ON q.profile_id = %s
WHERE p.profile_id <> q.profile_id
  AND p.style_vector IS NOT NULL
  AND q.style_vector IS NOT NULL
ORDER BY p.style_vector <=> q.style_vector
LIMIT 80
```

- **`<=>` 연산자**: pgvector cosine distance
- **similarity = 1 − cosine_distance** (0-1 범위, 높을수록 유사)
- 자기 자신(`p.profile_id <> q.profile_id`) 자동 제외
- 반환 수: 최대 80개

### 7-2. 멘토 나이 필터 (manual_prospect_helpers.py, views/legend_matching.py:272-276)

`filter_mentor_candidates_by_age(records, target_age, exclude_ids)`:
- Primary filter: mentor_age ≥ max(28, target_age + 5)
- 결과 < 3개이면 Fallback: mentor_age ≥ max(26, target_age + 3)
- `exclude_ids`로 자기 profile_id 추가 제외

### 7-3. 진입 조건 (views/legend_matching.py:253-261)

```python
if profile is None or profile.get("profile_id") is None:
    # 능력치 프로필 없음 → 차단
if not profile.get("style_vector"):
    # style_vector 없음 → 차단
```
- FM profile 없는 선수, style_vector 없는 선수 → 멘토 분석 불가

### 7-4. 적합도 표시 (views/legend_matching.py:22-46)

```python
sim_pct = max(0, min(99.9, similarity * 100))  # → "%"로 변환
if similarity >= 0.92: "매우 높은 적합도"
if similarity >= 0.84: "높은 적합도"
if similarity >= 0.75: "참고 가능한 적합도"
else: "보조 참고"
```

### 7-5. 기본 표시 정책

- 유사 선수 후보(전체 80개)는 상세보기 expander 안에 숨김
- 멘토 후보(나이 필터 적용 결과)를 우선 표시

---

## 8. style_vector / pgvector 사용 여부

### 8-1. style_vector 정의 (create_and_upload_db.py:488-492)

24차원 벡터, 구성 능력치:
```
["Acc","Pac","Sta","Str","Agi","Bal","Dri","Fir",
 "Fin","Pas","Vis","OtB","Tec","Wor","Tea","Det",
 "Dec","Ant","Cmp","Pos","Tck","Mar","Ldr","Agg"]
```

**이 24개는 FM proxy 능력치 (Football Manager 게임 데이터).  
실제 경기 위치 이벤트 데이터 기반 벡터 아님.**

정규화: `normalize_1_to_20(value)` → 0-1 범위로 변환 (1-20 스케일 기준)

### 8-2. DB 스키마 (create_and_upload_db.py:205, 228)

```sql
style_vector vector(24)
-- 인덱스:
USING ivfflat (style_vector vector_cosine_ops)
```

### 8-3. pgvector 실제 호출 여부

`get_similar_players()` (services/db.py:397): **실제 `<=>` 연산자 사용. 구현됨.**

### 8-4. 10x10 Grid 벡터와의 차이

- `views/experimental_data_lab.py`에 100차원 Grid Vector 개념이 언급됨
- **메인 분석 흐름에서는 사용되지 않음 — 별도 실험 페이지 설명 텍스트만 존재**
- 실제 경기 좌표 데이터 수집·계산 파이프라인 구현 없음

---

## 9. Gemini / 정성 텍스트 반영 방식

### 9-1. Gemini 호출 위치

- `services/qualitative_evidence.py::extract_qualitative_signals()` — 정성 텍스트에서 6개 신호 추출
- `services/qualitative_evidence.py::generate_gemini_advisory()` — 보조 추천 생성
- `views/ai_report.py::_render_qualitative_section()` — UI에서 호출

### 9-2. Gemini 역할 명시 (qualitative_evidence.py:136-172 프롬프트)

```
"점수를 계산하지 마세요. Growth/Ceiling 점수를 변경하거나 대체하지 마세요."
```

- Growth Score, Ceiling Score 계산 불가
- 정성 텍스트 기반 신호 6종 구조화 후 반환
- 추천 텍스트 생성만 가능

### 9-3. 추출 신호 스키마

```python
{
    "playing_time_signal":  positive|neutral|negative|unknown,
    "injury_risk_signal":   positive|neutral|negative|unknown,
    "coach_trust_signal":   positive|neutral|negative|unknown,
    "development_signal":   positive|neutral|negative|unknown,
    "transfer_rumor_signal":high|medium|low|unknown,
    "mentality_signal":     positive|neutral|negative|unknown,
}
```

### 9-4. 반복 호출 방지 (session_state)

- `st.session_state["qualitative_signals"]` — 분석 결과 캐시
- `st.session_state["gemini_advisory"]` — 추천 결과 캐시
- 선수 변경 시(`selected_player_id` 변경) 자동 초기화 (`_ANALYSIS_STATE_KEYS` 목록)

### 9-5. Gemini 없음 처리

- API 키 없음: `make_fallback_signals("no_api_key")` → confidence="low"로 대체
- SDK 미설치: SDK 설치 안내 표시
- API 오류: `make_fallback_signals("api_error")` + 오류 메시지 (스택 트레이스 미노출)

### 9-6. Gemini 결과 저장

- `scouting_notes.simulation_result.qualitative_evidence` → extracted_signals, text_snapshot (500자)
- `scouting_notes.simulation_result.gemini_advisory` → advisory_summary, training/career/risk/mentor/monitoring 추천
- `report_generation_mode`: `"rule_based"` 또는 `"rule_based_with_gemini"`

---

## 10. Scouting Notes 저장 구조

### 10-1. DB 테이블 (services/db.py:421-453)

```sql
scouting_notes(
    note_id, user_id, player_id, profile_id, matched_profile_id,
    env_settings::jsonb, simulation_result::jsonb, gemini_report,
    created_at
)
```

### 10-2. 페이로드 구조 (scouting_note_payload.py:151-210)

**env_settings:**
```json
{
  "note_type": "ai_report|career_simulation|manual_custom_prospect",
  "source": "ai_report|career_simulation|manual_note",
  "entity_type": "matched|manual_prospect|...",
  "player_snapshot": {이름/나이/포지션/클럽/시장가치 등},
  "profile_snapshot": {profile_id/age/position},
  "ceiling_growth_context": {career_settings, entity_type},
  "career_settings": {훈련강도/출전기회/리그난이도/커리어선택/리스크},
  "report_generation_mode": "rule_based|rule_based_with_gemini"
}
```

**simulation_result:**
```json
{
  "growth_insight": {features, growth_score, risk_penalty, ...},
  "growth_explanation": {summary, strengths, risks, recommendations, ...},
  "ceiling_growth_insight": {growth_score, ceiling_model, features, ...},
  "ceiling_growth_explanation": {ceiling_explanation: {coaching_summary, training_directions, ...}},
  "ceiling_growth_context": {...},
  "report_sections": {1-8개 섹션 텍스트},
  "generated_report_text": "최종 리포트 전문",
  "qualitative_evidence": {extracted_signals, text_snapshot, confidence},
  "gemini_advisory": {advisory_summary, training, career, risk, mentor, monitoring}
}
```

### 10-3. legacy fallback 체인 (views/scouting_notes.py:103-159)

```
ceiling_growth_insight → growth_insight (fallback)
ceiling_growth_explanation → growth_explanation (fallback)
player_snapshot → manual_player → legacy env["player"] (fallback)
→ note.player_name + env fields 재구성 (최종 fallback)
```

---

## 11. 실제 구현되지 않은 기능 목록 (향후 확장 항목)

| 기능 | 상태 | 비고 |
|------|------|------|
| 10x10 Grid 위치 이벤트 기반 벡터 | **미구현** | experimental_data_lab.py에 설명 텍스트만 존재. 실제 수집·계산 파이프라인 없음 |
| 머신러닝 성장 예측 모델 | **미구현** | Growth Score는 전적으로 rule-based |
| 실제 레전드 성장 궤적 비교 | **미구현** | 유사도 비교만 있고 궤적 데이터 없음 |
| TF-IDF 뉴스/기사 분석 | **미구현** | Gemini가 사용자 입력 텍스트 분석 (자동 크롤링 아님) |
| Supabase Auth 로그인 | **미구현** | user_id=NULL로 저장. 사용자 구분 없음 |
| RLS 기반 사용자별 Notes 분리 | **미구현** | 모든 노트가 단일 테이블에 저장, 사용자 분리 없음 |
| 뉴스 자동 크롤링 | **미구현** | 정성 텍스트는 사용자 직접 입력 |
| 실제 경기 좌표 데이터 기반 플레이스타일 분석 | **미구현** | style_vector는 FM proxy 능력치 기반 |
| 포지션별 강점 비교 | **미구현** | 포지션 그룹 정보는 있으나 그룹 내 상대 비교 아님 |

---

## 12. 교수님 예상 질문과 코드 근거 기반 답변

### Q1. 강점과 약점은 어떤 기준으로 판단하나요?

**A.** 두 단계로 판단합니다.

첫째, Growth Feature 6개(시장가치 흐름/출전 기회/기여도/나이/능력치/멘탈) 각각의 0-1 정규화 점수가 **0.6 이상이면 강점, 0.4 미만이면 리스크(약점)** 로 분류합니다 (`explanation_engine.py::build_strengths_with_meta`, `:build_risks_with_meta`).

둘째, attributes_jsonb 데이터를 5개 그룹(공격/패스/피지컬/멘탈활동량/수비)으로 나누어 그룹 평균을 내림차순 정렬하고, 상위 2-3개 키를 강점, 하위 키를 보완점으로 표시합니다 (`analysis_helpers.py::top_attributes`). 이때 포지션별 기준값 비교는 하지 않으며, FM 20점 스케일 내 절대 평균값을 비교합니다.

### Q2. 멘탈리티 분석은 어떤 데이터를 보고 판단하나요?

**A.** Football Manager 게임 데이터(FM proxy)에서 추출한 멘탈 속성 13종(Determination, Work Rate, Teamwork, Leadership, Loyalty, Concentration, Composure, Aggression, Ambition, Professionalism, Sportsmanship, Temperament, Pressure)의 평균값을 사용합니다 (`analysis_helpers.py::MENTALITY_KEYS`). 이 값들은 DB의 `mentality_jsonb.basis` 컬럼에 저장되어 있으며, 없으면 사전 계산된 `mentality_score` scalar를 fallback으로 사용합니다. 점수 범위는 FM 20점 스케일 기준입니다.

사용자가 입력하는 정성 텍스트와 Gemini 분석은 **멘탈리티 점수에 직접 반영되지 않습니다.** Gemini는 `mentality_signal` (positive/neutral/negative/unknown) 신호만 추출하고, 이는 코칭 방향 텍스트와 리스크 경고에만 반영됩니다.

### Q3. Growth Score는 어떤 공식/요소로 계산되나요?

**A.** 6개 지표의 가중평균에 risk penalty를 차감하는 **rule-based 계산 공식**입니다.

```
Growth Score = (가중평균 × 100) − risk_penalty
가중치: 시장가치흐름(30%) + 출전기회(20%) + 기여도(15%) + 나이(15%) + 능력치(10%) + 멘탈(10%)
risk_penalty: 0~15점 (데이터 부족, 시장가치 하락, 출전 기회 부족 시 차감)
최종 범위: 0~100점
```

데이터가 없는 지표는 제외하고 나머지 가중치를 재정규화합니다 (`growth_model.py::compute_growth_score`). **머신러닝 모델이 아닙니다.**

### Q4. Career Simulation은 실제 예측인가요, 조건 비교인가요?

**A.** **조건별 비교 시뮬레이션**입니다. 실제 예측 모델이 아닙니다.

사용자가 선택한 환경 조건(훈련강도/출전기회/리그난이도/커리어선택/리스크성향)을 rule-based 파라미터(α, γ, β, training_multiplier, Δleague)로 변환해 scenario_adjustment를 계산하고, 기존 Growth Score에 ±최대 15점을 가산합니다 (`growth_model.py::apply_ceiling_adjustment`). "어떤 환경에서 성장 가능성이 높아지는가"를 규칙 기반으로 보여주는 도구입니다.

### Q5. 멘토 후보는 어떤 기준으로 추천되나요?

**A.** 두 단계입니다.

첫째, DB에서 `player_profiles.style_vector`를 기준으로 pgvector `<=>` (cosine distance) 연산자를 사용해 유사도 상위 80명을 조회합니다 (`services/db.py::get_similar_players`).

둘째, Python에서 나이 조건을 적용합니다: 현재 선수보다 **5세 이상 많고 최소 28세**를 만족하는 후보만 멘토로 분류합니다. 이 조건으로 3명 미만이면 **3세 이상, 최소 26세** 조건으로 완화합니다 (`manual_prospect_helpers.py::filter_mentor_candidates_by_age`).

FM profile 또는 style_vector가 없는 선수는 이 분석에서 제외됩니다.

### Q6. Gemini는 점수 계산에 반영되나요?

**A.** **아닙니다.** Gemini의 역할은 사용자가 입력한 정성 텍스트(기사/인터뷰/메모)에서 신호를 구조화하고, 보조적인 코칭 추천 텍스트를 생성하는 것뿐입니다. Gemini에게 전달하는 프롬프트에 명시적으로 "점수를 계산하지 마세요. Growth/Ceiling 점수를 변경하거나 대체하지 마세요."라고 제한이 걸려 있습니다 (`services/qualitative_evidence.py:136-172`). Gemini가 없어도 모든 Growth Score와 Ceiling Score 계산은 정상 작동합니다.

### Q7. 정성 텍스트는 어디에 어떻게 반영되나요?

**A.** 정성 텍스트는 세 단계를 거칩니다:

1. **입력**: AI Report 화면에서 사용자가 직접 붙여넣기
2. **추출**: Gemini API 호출 → 6개 신호 구조화 (playing_time, injury_risk, coach_trust, development, transfer_rumor, mentality)
3. **저장·표시**: `scouting_notes.simulation_result.qualitative_evidence`에 저장. Notes 화면에서 "정성 분석 신호" 섹션으로 표시

Growth Score·Ceiling Score는 변경되지 않습니다. 코칭 방향 추천 텍스트와 리스크 경고에만 반영됩니다.

### Q8. 데이터가 부족한 선수는 어떻게 처리하나요?

**A.** `player_coverage.py::build_data_coverage()`가 커버리지를 판단합니다:

- **Full**: DB + FM profile + style_vector + 나이 모두 있음
- **Partial**: DB + FM profile + 나이는 있지만 style_vector 없음
- **Limited**: FM profile 없거나 나이 없음

Scouting Board 기본 검색은 Full/Partial만 표시하며 Limited는 기본 숨김입니다.

Growth Score 계산 시 데이터 없는 feature는 계산에서 제외하고 나머지를 재정규화합니다. 누락 feature가 3개 이상이면 risk_penalty 5점이 추가 차감됩니다. 멘토/Style Lab 분석은 style_vector 없으면 차단됩니다.

### Q9. 10x10 Grid는 구현되어 있나요?

**A.** **메인 분석 흐름에는 구현되어 있지 않습니다.** `views/experimental_data_lab.py`에 개념 설명 텍스트만 있으며, 실제 경기 위치 이벤트 데이터를 수집하거나 100차원 벡터를 생성·저장하는 파이프라인은 구현되지 않았습니다. 현재 style_vector는 FM proxy 능력치 24개를 정규화한 벡터입니다.

### Q10. 현재 구현의 한계와 향후 확장 방향은 무엇인가요?

**현재 한계:**

1. **데이터 의존성**: Growth Score의 50%를 차지하는 시장가치·출전 기록(Transfermarkt)이 없으면 분석 정확도가 크게 떨어짐
2. **FM proxy 의존**: style_vector와 능력치 분석이 FM 게임 데이터에 의존하므로, FM 매칭 없는 선수는 분석 범위 제한
3. **포지션별 상대 비교 없음**: 능력치 강점/약점 판단이 전체 평균 절대값 기준이므로, 같은 포지션 내 상대 순위 반영 안 됨
4. **사용자 분리 없음**: 로그인/인증 없이 단일 scouting_notes 테이블 공유
5. **정성 분석 선택적**: Gemini API key 없으면 정성 분석 불가

**향후 확장 방향:**

1. 실제 경기 위치 이벤트 데이터 기반 10x10 Grid vector 구현 (grid_pipeline.py 기초 작성됨)
2. 포지션별 동일 포지션 선수와의 상대 비교 기준 추가
3. Supabase Auth + RLS로 사용자별 Notes 분리
4. ML 기반 성장 예측 모델 (현재 rule-based를 학습 데이터로 활용 가능)
5. 실시간 시장가치/출전 기록 자동 업데이트

---

## 13. 관련 파일/함수 목록

| 파일 | 핵심 함수 | 역할 |
|------|----------|------|
| `growth_model.py` | `compute_*`, `build_growth_insight`, `apply_ceiling_adjustment` | Growth Score, Ceiling 계산 |
| `explanation_engine.py` | `explain_feature_score`, `build_strengths_with_meta`, `build_risks_with_meta`, `build_recommendations` | 설명 텍스트 생성 |
| `analysis_helpers.py` | `ATTRIBUTE_GROUPS`, `MENTALITY_KEYS`, `summary_scores`, `top_attributes`, `attr_bar_chart` | 능력치 분석·시각화 |
| `player_coverage.py` | `build_data_coverage`, `resolve_player_age` | 커버리지 판단 |
| `services/db.py` | `get_similar_players`, `insert_scouting_note`, `get_scouting_notes` | DB 쿼리·pgvector |
| `views/legend_matching.py` | `render_legend_matching_view`, `_style_snapshot_panel`, `_render_similarity_section` | 멘토/유사도 UI |
| `views/career_simulation.py` | `render_career_simulation_view`, `_render_ceiling_report` | 시뮬레이션 UI |
| `views/dashboard.py` | `_render_strength_risk_panels`, `render_dashboard_view` | Dossier UI |
| `views/ai_report.py` | `render_ai_report_view`, `get_report_sections`, `_render_qualitative_section` | 리포트 UI |
| `views/prospect_search.py` | `render_prospect_search_view`, `_source_badges`, `_candidate_reason` | 검색 UI |
| `gemini_client.py` | `is_gemini_available`, `generate_gemini_content` | Gemini API 래퍼 |
| `services/qualitative_evidence.py` | `extract_qualitative_signals`, `generate_gemini_advisory` | 정성 분석 |
| `scouting_note_payload.py` | `build_career_simulation_note_payload`, `build_ai_report_note_payload`, `extract_structured_note_result` | 저장 페이로드 |
| `views/scouting_notes.py` | `render_scouting_notes_view`, `_extract_note_data` | 노트 표시 |
| `components/attribute_panels.py` | `attribute_bar_html`, `render_attribute_snapshot` | 능력치 바 시각화 |
| `create_and_upload_db.py` | `make_style_vector`, `upload_player_profiles` | 벡터 생성·업로드 (수정 금지) |

---

## 14. 테스트 결과

```
python -m compileall .        → 오류 없음 (전체 파이썬 파일 문법 검사 통과)
python test_growth_model.py   → 전체 통과 (EXIT 0)
python test_prospect_search_split.py → 전체 통과 (EXIT 0)
```

> test_state_refactor.py, test_analysis_helpers_split.py는 본 audit에서 별도 실행 예정

---

## 15. 남은 리스크

1. **포지션별 비교 없음**: `attribute_strength`가 절대 평균값이므로 포지션에 따라 기준이 다를 수 있음 (예: GK와 ST의 능력치 그룹이 동일 기준으로 평가됨)
2. **FM proxy 데이터 편향**: style_vector와 능력치 분석이 FM 게임 속성에 의존하므로, 실제 선수의 플레이스타일과 다를 수 있음
3. **market_momentum 민감도**: 180일 이내 시장가치 변동이 없으면 unavailable 처리 → growth_score 변동 가능
4. **Gemini 결과 비결정성**: 동일 텍스트 입력에도 Gemini 응답이 달라질 수 있음 (캐싱은 session_state 수준만)
