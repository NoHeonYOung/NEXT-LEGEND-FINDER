# NEXT-LEGEND FINDER 웹 DB 응용 기본틀 명세서

## 1. 프로젝트 개요

- 프로젝트명: NEXT-LEGEND FINDER
- 개발 단계: Project Homework #5 웹 DB 응용 기본틀 만들기
- 개발 목적:
  - HW#4에서 구축한 Supabase PostgreSQL 데이터베이스와 기존 Streamlit 코드를 기반으로, NEXT-LEGEND FINDER의 웹 DB 응용 기본 화면 흐름을 구축한다.
  - 단순히 DB 테이블을 조회하는 화면이 아니라, 실제 서비스 사용자가 유망주를 검색하고, 분석 대시보드를 확인하고, 시뮬레이션 조건을 설정하고, AI 스카우팅 리포트 초안을 저장하는 흐름을 구현한다.
  - 이번 단계에서는 완성형 AI 분석 서비스가 아니라, 향후 세부 기능을 붙일 수 있는 기본 UI 구조와 기본 DB 연동 흐름을 만드는 것을 목표로 한다.

## 2. 기존 프로젝트 진행 상황 요약

### 2.1 HW#2 기획 단계

초기 기획에서는 기존 축구 정보 서비스가 선수의 현재 스탯, 시장가치, 능력치처럼 정적인 정보 제공에 집중한다는 한계를 문제로 보았다.

NEXT-LEGEND FINDER는 다음과 같은 기능을 목표로 기획되었다.

- 유망주의 정량적 경기 데이터와 정성적 데이터를 통합한 선수 프로필 제공
- 과거 레전드 선수와 현재 유망주의 플레이스타일 비교
- 이적, 잔류, 훈련 강도, 출전 기회 등에 따른 커리어 시뮬레이션
- AI 기반 스카우팅 리포트 생성
- 생성된 분석 결과를 개인 스카우팅 노트에 저장

### 2.2 HW#3 개발계획 단계

HW#3에서는 Streamlit, Supabase, PostgreSQL, pgvector, JSONB, Gemini API를 활용한 웹 DB 응용 구조를 설계하였다.

초기 사용자 흐름은 다음과 같았다.

1. 사용자가 분석할 유망주를 검색한다.
2. 선택한 선수의 기본 정보, 경기 기록, 시장가치, 멘탈리티 정보를 통합 대시보드에서 확인한다.
3. 플레이스타일 벡터를 활용해 유사 선수 또는 레전드 선수와 비교한다.
4. 훈련 강도, 리그 난이도, 출전 기회, 이적/잔류 여부를 조절하여 커리어 시뮬레이션을 수행한다.
5. 시뮬레이션 결과를 바탕으로 AI 스카우팅 리포트를 생성한다.
6. 생성된 리포트를 scouting_notes 테이블에 저장한다.

### 2.3 HW#4 DB 구축 단계

HW#4에서는 실제 확보한 CSV 데이터셋을 기반으로 Supabase에 초기 데이터베이스를 구축하였다.

사용한 데이터셋은 다음과 같다.

- clubs.csv
- players.csv
- appearances.csv
- player_valuations.csv
- merged_players.csv
- fm2023.csv

최종적으로 Supabase에는 다음 6개 테이블을 생성하였다.

- clubs
- players
- appearances
- player_valuations
- player_profiles
- scouting_notes

초기 기획에서는 10x10 Grid 기반 위치 이벤트 데이터와 뉴스/스카우팅 리포트 원문 기반 정성 데이터를 활용하려고 했으나, 실제 확보한 CSV에는 해당 데이터가 포함되어 있지 않았다.

따라서 HW#4에서는 다음과 같이 현실적으로 설계를 조정하였다.

- 10x10 Grid 기반 vector(100) 대신 FM 능력치 기반 proxy style_vector(24)를 사용한다.
- 뉴스/자서전/스카우팅 원문 기반 정성 분석 대신 FM 멘탈 속성 기반 mentality_jsonb를 사용한다.
- pgvector와 JSONB를 사용할 수 있는 구조는 유지한다.
- 향후 실제 위치 이벤트 데이터와 텍스트 근거 데이터가 확보되면 확장할 수 있도록 한다.

## 3. 이번 HW#5의 개발 목표

이번 단계의 목표는 새로운 DB를 다시 구축하는 것이 아니다.

이번 단계의 목표는 다음과 같다.

1. HW#4에서 구축한 Supabase DB 구조를 그대로 유지한다.
2. 기존 Streamlit 코드를 기반으로 실제 서비스 흐름에 가까운 화면 구조를 만든다.
3. 사용자가 유망주를 검색하고, 통합 분석 대시보드에서 정보를 확인할 수 있게 한다.
4. 레전드 매칭, 커리어 시뮬레이션, AI 리포트 생성 기능은 완성형 알고리즘이 아니라 기본 UI 틀로 구현한다.
5. 사용자가 선택한 선수, 시뮬레이션 설정값, 리포트 초안을 scouting_notes 테이블에 저장하는 기본 INSERT 기능을 구현한다.
6. Supabase Auth와 RLS는 이번 단계에서 구현하지 않는다.
7. user_id는 현재 null로 저장하고, 향후 Supabase Auth를 붙일 때 실제 사용자 ID와 연결한다.

## 4. 기술 스택

- Python
- Streamlit
- Supabase PostgreSQL
- Pandas
- JSONB
- pgvector
- GPT Codex
- VS Code

## 5. 데이터베이스 스키마

이번 단계에서는 기존 Supabase DB 스키마를 변경하지 않는다.

아래 6개 테이블을 그대로 사용한다.

### 5.1 clubs

구단 기본 정보를 저장하는 테이블이다.

주요 컬럼:

- club_id
- name
- domestic_competition_id
- squad_size
- average_age
- stadium_name
- url

### 5.2 players

선수의 기본 프로필 정보를 저장하는 중심 테이블이다.

주요 컬럼:

- player_id
- name
- current_club_id
- current_club_name
- country_of_citizenship
- date_of_birth
- position
- sub_position
- foot
- height_in_cm
- image_url
- market_value_in_eur
- highest_market_value_in_eur
- url

### 5.3 appearances

선수의 경기별 출전 기록을 저장하는 테이블이다.

주요 컬럼:

- appearance_id
- game_id
- player_id
- date
- player_name
- competition_id
- goals
- assists
- yellow_cards
- red_cards
- minutes_played

### 5.4 player_valuations

선수의 시장가치 변화를 날짜별로 저장하는 테이블이다.

주요 컬럼:

- valuation_id
- player_id
- date
- market_value_in_eur
- current_club_name
- current_club_id

### 5.5 player_profiles

FM 기반 분석 프로필을 저장하는 핵심 테이블이다.

주요 컬럼:

- profile_id
- player_id
- fm_uid
- name
- age
- club
- nationality
- position
- media_description
- attributes_jsonb
- mentality_jsonb
- style_vector
- source_file
- created_at

### 5.6 scouting_notes

사용자가 생성한 스카우팅 노트, 시뮬레이션 설정값, 리포트 초안을 저장하기 위한 테이블이다.

주요 컬럼:

- note_id
- user_id
- player_id
- profile_id
- matched_profile_id
- env_settings
- simulation_result
- gemini_report
- created_at

이번 단계에서는 Supabase Auth를 구현하지 않으므로 user_id는 null로 저장한다.

## 6. 전체 화면 구성

이번 HW#5의 화면은 DB 테이블 조회 중심이 아니라, NEXT-LEGEND FINDER의 서비스 사용자 흐름 중심으로 구성한다.

전체 화면 흐름은 다음과 같다.

1. Home / Service Intro
2. Prospect Search
3. Integrated Analysis Dashboard
4. Legend Matching
5. Career Simulation
6. AI Scouting Report
7. My Scouting Notes
8. DB Status

DB Status는 개발 확인용 보조 화면이며, 서비스의 중심 화면은 아니다.

## 7. 화면별 기능 요구사항

### 7.1 Home / Service Intro

#### 목적

사용자가 NEXT-LEGEND FINDER가 어떤 서비스인지 이해할 수 있도록 한다.

#### 화면 구성

- 프로젝트 제목
- 서비스 한 줄 소개
- 기존 서비스의 한계
- 본 서비스의 핵심 아이디어
- 현재 HW#5 개발 범위 안내
- 사용 기술 스택 안내

#### 표시 내용

- 기존 축구 정보 서비스는 선수의 현재 수치나 시장가치 제공에 집중한다.
- NEXT-LEGEND FINDER는 유망주의 현재 데이터, 경기 기록, 시장가치 변화, FM 기반 능력치와 멘탈리티 데이터를 통합하여 향후 성장 분석으로 확장하는 웹 DB 응용이다.
- 이번 단계에서는 완성형 예측 모델이 아니라 웹 DB 응용의 기본 UI 흐름과 DB 저장 흐름을 구축한다.

### 7.2 Prospect Search

#### 목적

사용자가 분석할 유망주를 검색하고 선택할 수 있도록 한다.

#### 입력

- 선수 이름 검색어
- 선택 사항:
  - 포지션 필터
  - 국적 필터
  - 소속팀 필터

#### 동작 로직

- players 테이블의 name 컬럼을 기준으로 선수 이름을 검색한다.
- 검색 결과는 기본 선수 정보 중심으로 표시한다.
- 사용자가 특정 선수를 선택하면 해당 선수의 player_id를 Streamlit session_state에 저장한다.
- 이후 Integrated Analysis Dashboard, Legend Matching, Career Simulation, AI Scouting Report 화면에서 선택된 선수를 사용할 수 있도록 한다.

#### 출력 컬럼

- player_id
- name
- current_club_name
- country_of_citizenship
- position
- sub_position
- foot
- height_in_cm
- market_value_in_eur
- highest_market_value_in_eur

#### 화면 UI

- 검색창
- 필터 영역
- 검색 결과 테이블 또는 카드
- 선수 선택 버튼
- 선택된 선수 요약 표시

### 7.3 Integrated Analysis Dashboard

#### 목적

선택한 유망주의 기본 정보, 시장가치, 경기 기록, FM 기반 능력치, 멘탈리티 정보를 하나의 대시보드에서 보여준다.

#### 사용하는 테이블

- players
- player_profiles
- player_valuations
- appearances

#### 화면 구성

1. Player Profile Card
2. Ability / Style Summary
3. Mentality Analysis Card
4. Market Value Summary
5. Recent Appearances Summary

#### 동작 로직

- session_state에 저장된 player_id를 기준으로 데이터를 조회한다.
- players 테이블에서 선수 기본 정보를 조회한다.
- player_profiles 테이블에서 FM 기반 분석 프로필을 조회한다.
- player_valuations 테이블에서 시장가치 변화 데이터를 조회한다.
- appearances 테이블에서 최근 출전 기록 일부를 조회한다.
- 큰 테이블을 조회할 때는 반드시 LIMIT을 사용한다.

#### Player Profile Card

표시 항목:

- 선수 이름
- 국적
- 소속팀
- 포지션
- 세부 포지션
- 주발
- 키
- 현재 시장가치
- 최고 시장가치
- 선수 이미지

image_url이 존재하면 st.image로 표시한다.

#### Ability / Style Summary

표시 항목:

- media_description
- attributes_jsonb의 주요 능력치 일부
- style_vector 존재 여부
- style_vector 차원 수 또는 일부 샘플 값

주의사항:

- 현재 style_vector는 실제 10x10 Grid 기반 벡터가 아니라 FM 능력치 기반 proxy style_vector(24)이다.
- 따라서 화면에는 “FM 기반 Proxy Style Summary”라고 표시한다.
- style_vector 전체를 길게 출력하지 않는다.

#### Mentality Analysis Card

표시 항목:

- mentality_jsonb의 주요 멘탈 속성
- Determination, Work Rate, Teamwork 등 확인 가능한 주요 값
- mentality_jsonb 안의 해석 문구가 있다면 일부 표시

주의사항:

- 현재 mentality_jsonb는 뉴스 기사나 스카우팅 리포트 원문 기반 분석이 아니다.
- FM 멘탈 속성을 활용한 proxy mentality data로 표시한다.

#### Market Value Summary

표시 항목:

- 날짜별 시장가치 변화 일부
- 가능하면 line chart로 시각화
- 구현이 복잡하면 st.dataframe으로 표시

#### Recent Appearances Summary

표시 항목:

- 최근 경기 날짜
- competition_id
- goals
- assists
- minutes_played
- yellow_cards
- red_cards

최근 10개 또는 20개만 조회한다.

### 7.4 Legend Matching

#### 목적

선택한 유망주와 유사 선수 또는 레전드 후보를 비교하는 화면의 기본틀을 만든다.

#### 현재 단계의 구현 범위

- 실제 10x10 Grid 기반 레전드 매칭 알고리즘은 구현하지 않는다.
- 실제 레전드 데이터셋이 완성되어 있지 않으므로 완성형 매칭 기능은 구현하지 않는다.
- 대신 현재 player_profiles의 FM 기반 proxy style_vector를 활용할 수 있는 구조만 보여준다.
- 유사 선수 후보를 실제로 조회할 수 있으면 같은 포지션 또는 유사한 FM 프로필을 가진 선수 몇 명을 후보로 표시한다.
- 구현이 어렵다면 더미 후보 영역과 향후 구현 예정 안내를 표시한다.

#### 화면 구성

- 선택한 유망주 카드
- 매칭 후보 카드
- 유사도 점수 표시 영역
- 능력치 비교 영역
- 향후 pgvector 기반 유사도 검색 고도화 안내

#### 주의사항

- 화면에 “10x10 Grid 기반 매칭 완료”라고 표시하지 않는다.
- 현재는 “FM 기반 proxy vector를 활용한 매칭 UI 기본틀”이라고 표시한다.
- 실제 10x10 Grid 기반 vector(100)는 향후 구현 항목으로 둔다.

### 7.5 Career Simulation

#### 목적

사용자가 훈련 강도, 출전 기회, 리그 난이도, 이적/잔류 여부 등을 설정하여 향후 성장 시뮬레이션 기능의 입력 흐름을 체험할 수 있도록 한다.

#### 현재 단계의 구현 범위

- 실제 성장 예측 모델은 구현하지 않는다.
- 사용자가 입력한 값을 env_settings JSON 형태로 구성한다.
- 간단한 더미 simulation_result를 생성한다.
- 입력값에 따라 간단한 성공 가능성, 성장 점수, 리스크 점수 등을 계산해도 된다.
- 단, 실제 예측 결과처럼 과장해서 표현하지 않는다.

#### 입력 UI

- 훈련 강도 slider
- 출전 기회 slider
- 리그 난이도 selectbox
- 이적/잔류 선택 radio 또는 button
- 부상 위험도 또는 리스크 수준 선택

#### 출력 UI

- 입력값 요약 카드
- env_settings JSON 미리보기
- simulation_result JSON 미리보기
- 간단한 성장 곡선 더미 chart
- “현재는 프로토타입 결과이며 실제 예측 모델은 향후 구현 예정” 안내

#### env_settings 예시

다음과 같은 구조로 생성한다.

    {
      "training_intensity": 1.5,
      "playing_time_opportunity": 0.7,
      "league_difficulty": "medium",
      "career_choice": "stay",
      "risk_level": "normal"
    }

#### simulation_result 예시

다음과 같은 구조로 생성한다.

    {
      "prototype_growth_score": 72,
      "prototype_success_probability": 0.64,
      "prototype_injury_risk": 0.22,
      "message": "현재 결과는 실제 예측 모델이 아니라 UI 흐름 검증을 위한 프로토타입 결과입니다."
    }

### 7.6 AI Scouting Report

#### 목적

선택한 선수와 시뮬레이션 설정값을 바탕으로 AI 스카우팅 리포트 초안을 생성하고, scouting_notes 테이블에 저장할 수 있도록 한다.

#### 현재 단계의 구현 범위

- Gemini API 또는 외부 LLM API를 실제 호출하지 않는다.
- 템플릿 기반의 더미 리포트 또는 프로토타입 리포트를 생성한다.
- 사용자가 Save to Scouting Notes 버튼을 클릭하면 scouting_notes 테이블에 저장한다.

#### 입력 데이터

- 선택된 player_id
- 가능하면 profile_id
- Career Simulation 화면에서 만든 env_settings
- Career Simulation 화면에서 만든 simulation_result
- 템플릿 기반 gemini_report

#### 저장 대상 테이블

- scouting_notes

#### 저장 컬럼

- user_id: null
- player_id: 선택한 선수의 player_id
- profile_id: 선택한 선수의 profile_id, 없으면 null
- matched_profile_id: 현재 단계에서는 null
- env_settings: 시뮬레이션 입력값 JSON
- simulation_result: 프로토타입 시뮬레이션 결과 JSON
- gemini_report: 템플릿 기반 AI 리포트 초안
- created_at: 현재 시각 또는 DB 기본값 사용

#### 화면 UI

- 선택된 선수 정보 요약
- 시뮬레이션 설정값 요약
- Generate Prototype Report 버튼
- 리포트 출력 카드
- Save to Scouting Notes 버튼
- 저장 성공 시 st.success 메시지
- 저장 실패 시 st.error 메시지

#### 리포트 내용 예시

- 선수의 현재 강점
- 보완이 필요한 부분
- 훈련 방향 제안
- 이적/잔류 선택에 대한 코멘트
- 현재 리포트는 실제 Gemini API 결과가 아니라 프로토타입 템플릿이라는 안내

#### 주의사항

- “Gemini API가 실제로 분석했다”고 표현하지 않는다.
- 화면에는 “Prototype AI Report” 또는 “Template-based Scouting Report”라고 표시한다.
- 향후 Gemini API를 연결하면 gemini_report 컬럼에 실제 LLM 리포트를 저장할 수 있도록 구조를 유지한다.

### 7.7 My Scouting Notes

#### 목적

scouting_notes 테이블에 저장된 리포트 초안을 다시 조회할 수 있도록 한다.

#### 현재 단계의 구현 범위

- Supabase Auth가 없으므로 사용자별 필터링은 구현하지 않는다.
- user_id가 null인 테스트 노트 또는 전체 노트 일부를 조회한다.
- 최근 저장된 노트가 위에 오도록 created_at 기준 내림차순으로 조회한다.
- 너무 많은 데이터를 불러오지 않도록 LIMIT을 사용한다.

#### 화면 구성

- 저장된 노트 목록
- 선수 ID 또는 선수 이름
- 생성일
- 리포트 일부 미리보기
- env_settings 요약
- simulation_result 요약
- 상세 보기 expander

#### 주의사항

- 현재는 사용자별 보안 저장 기능이 아니다.
- Supabase Auth와 RLS를 적용하면 user_id 기준으로 본인의 노트만 조회하도록 확장할 예정이다.
- 화면에 이 한계를 명확히 안내한다.

### 7.8 DB Status

#### 목적

Supabase DB 연결 상태와 기본 테이블 상태를 확인하는 보조 화면이다.

#### 현재 단계의 역할

- 이 화면은 서비스 중심 화면이 아니라 개발 확인용 화면이다.
- HW#4에서 구축한 DB가 HW#5 Streamlit 앱과 정상적으로 연결되는지 확인하기 위해 제공한다.

#### 기능

- DB 연결 성공 여부 표시
- 6개 테이블 row count 확인
- 각 테이블의 간단한 설명 표시

#### 대상 테이블

- clubs
- players
- appearances
- player_valuations
- player_profiles
- scouting_notes

## 8. 이번 단계에서 구현할 기능

이번 HW#5에서 구현할 기능은 다음과 같다.

- Streamlit 사이드바 기반 화면 이동
- Home / Service Intro 화면
- Prospect Search 화면
- 선택 선수 session_state 저장
- Integrated Analysis Dashboard 화면
- players, player_profiles, player_valuations, appearances 조회
- FM 기반 proxy style_vector와 mentality_jsonb 요약 표시
- Legend Matching UI 기본틀
- Career Simulation 입력 UI
- env_settings JSON 생성
- simulation_result JSON 생성
- 템플릿 기반 AI Scouting Report 생성
- Save to Scouting Notes 버튼
- scouting_notes 테이블 INSERT
- user_id는 null로 저장
- My Scouting Notes 화면에서 저장 결과 조회
- DB Status 보조 화면

## 9. 이번 단계에서 제외할 기능

다음 기능은 이번 HW#5에서 실제 구현하지 않는다.

- 실제 10x10 Grid 기반 위치 이벤트 데이터 수집
- 10x10 Grid 기반 vector(100) 생성
- 뉴스 기사, 자서전, 스카우팅 리포트 원문 수집
- TF-IDF 또는 NLP 기반 실제 근거 문장 추출
- Gemini API 실제 호출
- 실제 성장 예측 모델 구현
- 실제 레전드 선수 매칭 알고리즘 완성
- Supabase Auth 로그인 기능
- RLS 정책 기반 사용자별 접근 제어 완성

단, 위 기능들은 폐기하는 것이 아니라 향후 구현 항목으로 남긴다.

## 10. DB 저장 기능 상세 명세

### 10.1 저장 기능의 목적

이번 단계에서는 완성형 사용자별 리포트 저장 기능을 구현하는 것이 아니라, 향후 스카우팅 노트 기능의 기반을 검증하기 위해 기본 INSERT 흐름을 구현한다.

즉, 사용자가 선택한 선수, 시뮬레이션 설정값, 프로토타입 시뮬레이션 결과, 템플릿 기반 리포트 초안을 scouting_notes 테이블에 저장한다.

### 10.2 저장 시점

AI Scouting Report 화면에서 사용자가 Save to Scouting Notes 버튼을 클릭할 때 저장한다.

### 10.3 저장 데이터

scouting_notes 테이블에 저장할 데이터는 다음과 같다.

- user_id: null
- player_id: 선택한 선수의 player_id
- profile_id: player_profiles에서 조회한 profile_id, 없으면 null
- matched_profile_id: 현재 단계에서는 null
- env_settings: Career Simulation 화면에서 생성한 JSON 데이터
- simulation_result: 프로토타입 시뮬레이션 결과 JSON 데이터
- gemini_report: 템플릿 기반 리포트 문자열
- created_at: 현재 시각 또는 DB 기본값

### 10.4 저장 성공 처리

저장에 성공하면 다음 메시지를 표시한다.

- “스카우팅 노트가 저장되었습니다.”

가능하면 저장된 note_id를 표시한다.

### 10.5 저장 실패 처리

저장에 실패하면 st.error를 사용하여 한글 에러 메시지를 표시한다.

예시:

- “스카우팅 노트 저장 중 오류가 발생했습니다.”
- 실제 예외 메시지는 개발 확인용으로 expander 안에 표시한다.

### 10.6 user_id 처리 방식

이번 단계에서는 Supabase Auth를 구현하지 않으므로 user_id는 null로 저장한다.

향후 Supabase Auth를 붙이면 다음과 같이 확장한다.

- 로그인한 사용자의 auth.uid()를 user_id에 저장
- RLS 정책을 적용하여 본인의 scouting_notes만 조회
- My Scouting Notes 화면에서 user_id 기준 필터링 적용

## 11. 예외 처리 및 주의사항

### 11.1 DB 관련 주의사항

- 기존 Supabase 테이블 구조를 변경하지 않는다.
- 기존 DB 구축 코드를 다시 실행하지 않는다.
- create_and_upload_db.py는 초기 DB 구축용 파일이므로 수정하지 않는다.
- DROP TABLE, TRUNCATE, DELETE 같은 위험한 SQL은 작성하지 않는다.
- 저장 기능에는 INSERT만 사용한다.
- UPDATE나 DELETE 기능은 이번 단계에서 구현하지 않는다.
- 대용량 테이블 조회 시 반드시 LIMIT을 사용한다.
- appearances 테이블은 전체 조회하지 않는다.
- DB 접속 정보는 코드에 직접 작성하지 않는다.
- DB 접속 정보는 반드시 .streamlit/secrets.toml 또는 st.secrets를 통해 불러온다.

### 11.2 코드 작성 규칙

- app.py 중심으로 수정한다.
- 필요한 경우 requirements.txt만 보완한다.
- 기존 Supabase 연결 방식을 가능한 한 유지한다.
- 함수 단위로 코드를 나누어 가독성을 높인다.
- 화면별 렌더링 함수를 분리한다.
- 중복 SQL 실행을 줄이기 위해 필요한 경우 st.cache_data 또는 st.cache_resource를 사용한다.
- Streamlit 화면에서 오류가 발생하면 st.error로 한글 안내 메시지를 출력한다.
- 데이터가 없을 경우 st.warning 또는 st.info로 안내한다.

### 11.3 보안 및 비밀정보 관리

- DB URL, 비밀번호, Supabase key 등은 코드에 직접 작성하지 않는다.
- secrets.toml 파일 내용은 화면에 출력하지 않는다.
- GitHub에 secrets.toml을 업로드하지 않는다.
- API key나 DB password를 주석으로도 남기지 않는다.

### 11.4 Codex 작업 제한

Codex는 다음 파일을 중심으로 작업한다.

- app.py
- 필요한 경우 requirements.txt

Codex는 다음 파일을 임의로 수정하지 않는다.

- create_and_upload_db.py
- secrets.toml
- 원본 CSV 데이터셋
- Supabase DB의 실제 스키마

Codex는 다음 작업을 수행하지 않는다.

- DB 테이블 삭제
- DB 테이블 재생성
- 대량 데이터 삭제
- 기존 데이터 덮어쓰기
- API key 또는 DB URL 하드코딩
- Supabase Auth 강제 구현
- RLS 정책 강제 변경

## 12. Codex에게 전달할 개발 지시사항

현재 프로젝트는 데이터베이스 과목 HW#5를 위한 NEXT-LEGEND FINDER 프로젝트이다.

HW#4에서 이미 Supabase PostgreSQL에 6개 테이블을 구축했고, Streamlit에서 DB 연결, 테이블 조회, 선수 검색까지 확인한 상태이다.

이번 HW#5의 목표는 완성형 서비스를 만드는 것이 아니라, 기존 DB와 코드를 유지하면서 NEXT-LEGEND FINDER의 웹 DB 응용 기본틀을 만드는 것이다.

다음 조건을 반드시 지켜라.

1. app.py 중심으로 Streamlit UI를 확장한다.
2. create_and_upload_db.py는 수정하지 않는다.
3. Supabase 테이블 구조를 변경하지 않는다.
4. DB 접속 정보는 st.secrets에서 불러온다.
5. DROP, DELETE, TRUNCATE 같은 위험한 SQL을 작성하지 않는다.
6. 저장 기능에는 INSERT만 사용한다.
7. 큰 테이블은 LIMIT을 적용하여 조회한다.
8. 10x10 Grid, 뉴스/스카우팅 원문 분석, Gemini API 실제 호출은 이번 단계에서 제외한다.
9. Supabase Auth와 RLS는 이번 단계에서 구현하지 않는다.
10. scouting_notes.user_id는 null로 저장한다.
11. 선택한 선수, 시뮬레이션 설정값, 프로토타입 결과, 리포트 초안을 scouting_notes 테이블에 저장하는 기본 흐름을 구현한다.

구현할 화면은 다음과 같다.

1. Home / Service Intro
2. Prospect Search
3. Integrated Analysis Dashboard
4. Legend Matching
5. Career Simulation
6. AI Scouting Report
7. My Scouting Notes
8. DB Status

먼저 현재 코드 구조를 분석한 뒤, 어떤 파일을 수정할지 설명하고, 이후 app.py 중심으로 단계적으로 수정하라.