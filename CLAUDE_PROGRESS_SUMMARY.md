# CLAUDE_PROGRESS_SUMMARY.md

## 현재 기준 요약

현재 프로젝트는 **NEXT-LEGEND FINDER**라는 Streamlit + Supabase 기반 유망주 스카우팅 서비스다.

현재 구현 기준은 v18.3이다.

핵심 구현 상태:
- v19 Phase 1~2 Scouting Board / Player Dossier UX 정리
- Supabase PostgreSQL 기반 선수 DB 조회
- `players`, `clubs`, `appearances`, `player_valuations`, `player_profiles`, `scouting_notes` 사용
- FM 기반 `player_profiles`와 24차원 `style_vector` 사용
- pgvector cosine similarity 기반 유사 선수/멘토 후보 조회
- DB 기반 Growth Model
- Career Simulation 기반 Ceiling Scenario
- 직접 입력 유망주(`manual_prospect`) 흐름
- My Scouting Notes 구조화 저장/조회
- Gemini 기반 정성 텍스트 신호 추출
- Gemini 기반 보조 스카우팅 추천
- 데이터 출처/분석 근거 라벨링 정리
- 데이터 커버리지 gating 및 나이 계산 일관화

## v19 Phase 1~2: Scouting Board and Player Dossier redesign

이번 단계는 v19 전체 구현이 아니라 Scouting Board, Player Dossier, Data Coverage 표시 정리만 수행했다.

변경 요약:
- Scouting Board 화면 제목과 기본 정책을 v19 기준으로 정리했다.
- 기본 유망주 나이 기준을 15~25로 설정했다.
- 기본 검색은 분석 가능한 유망주 중심이며 Full + Partial을 우선 노출하고 Limited는 기본 제외한다.
- `analyze_only`를 끄거나 전체 DB/Limited 옵션을 켜면 Limited 선수도 볼 수 있다.
- 검색 결과 카드에 분석 준비도 badge, FM profile 여부, style_vector 여부, 데이터 부족 이유, 후보 판단 문구를 표시한다.
- Player Dossier 화면 제목을 사용자 UI에서 `Player Dossier`로 변경했다. 내부 nav key는 안정성을 위해 유지한다.
- Dossier 상단에 공통 Data Coverage Panel을 추가했다.
- `ui_components.py`에 Full / Partial / Limited / Manual badge와 coverage panel 표시 helper를 추가했다.
- FM profile 없는 Transfermarkt-only 선수는 v19 UI에서 Limited로 분류하고, 직접 입력 유망주 보완/분석 가능한 선수 재검색 CTA를 제공한다.
- Growth/Ceiling 공식, Gemini 역할, Notes 저장 구조, DB 스키마는 변경하지 않았다.

현재 가장 큰 문제:
- Style & Mentor Lab / Career Simulation / Evidence & Advisory Report / Notes 전체 개편은 아직 남아 있다.
- 메뉴 내부 key는 기존 값을 유지하고 있어 사용자-facing 라벨과 내부 key가 완전히 같지는 않다.
- Scouting Board의 Full 판정은 검색 결과에 포함된 profile/style_vector 가용성 컬럼을 기반으로 한다.
- Dashboard / Mentor / Simulation / Report 전체가 아직 완전한 v19 워크플로우로 재배치되지는 않았다.
- 각 화면에서 사용자가 다음에 무엇을 해야 하는지 제품 수준에서 더 명확해야 한다.

현재 작업 목표:
- v19에서 제품 수준의 UX/분석 흐름 재설계가 필요하다.
- 먼저 `V19_PRODUCT_REDESIGN_SPEC.md`를 작성하고 사용자 승인 후 구현한다.

## 현재 기본 작업 원칙

- DB 스키마 변경 금지
- `create_and_upload_db.py` 수정 금지
- `.streamlit/secrets.toml` / `.env` 출력 또는 수정 금지
- API key 값 출력 금지
- 원본 CSV 및 `Database_Project_Dataset/` 수정 금지
- 뉴스 자동 크롤링 구현 금지
- 10x10 Grid 구현 금지
- Growth/Ceiling 공식 임의 변경 금지
- 기존 JSONB 저장 구조 삭제 금지
- legacy fallback 삭제 금지
- `app.py` 대형화 금지
- Gemini는 점수 계산에 관여하지 않음
- Gemini는 정성 텍스트 신호 추출과 보조 추천만 수행
- 문서 최신화 필수

## 상세 과거 기록

v1~v18.3의 상세 작업 기록은 `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`를 참고한다.

일반 작업에서는 archive를 기본적으로 읽지 않는다. 사용자가 명시적으로 요청하거나, 과거 구현 맥락이 반드시 필요할 때만 archive를 확인한다.
