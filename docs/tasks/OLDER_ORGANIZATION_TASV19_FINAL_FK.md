# V19_FINAL_FOLDER_ORGANIZATION_TASK.md

## 0. 작업 목적

이 프로젝트는 `c:\Users\nhy81\Desktop\Database_Project`의 NEXT-LEGEND FINDER Streamlit + Supabase 기반 축구 유망주 스카우팅 웹앱이다.

현재 v19 Final Polish and Cleanup까지 완료되었고, 주요 기능과 UI 리디자인은 거의 마무리되었다.

하지만 프로젝트 루트에 작업 지시서, 임시 파일, 오래된 보고서, task 문서, diff 문서 등이 많이 남아 있어 폴더가 복잡해 보인다.

이번 작업의 목적은 기능 추가가 아니라 최종 제출/유지보수용 파일 구조 정리이다.

목표:

1. 루트 디렉터리를 깔끔하게 정리한다.
2. 실제 실행에 필요한 파일과 문서/작업 파일을 분리한다.
3. task 문서, 오래된 보고서, archive 문서를 docs/ 아래로 이동한다.
4. 실제 앱 import에 사용되는 Python 파일은 함부로 이동하지 않는다.
5. 테스트와 Streamlit health check를 통해 기능이 깨지지 않았는지 확인한다.

---

## 1. 작업 전 확인

먼저 현재 상태를 확인한다.

```bash
git status
```

주의:

* 현재 변경사항을 임의로 되돌리지 않는다.
* 사용자가 commit하지 않은 변경사항을 삭제하지 않는다.
* 삭제가 애매한 파일은 삭제하지 말고 이동하거나 `FOLDER_ORGANIZATION_REPORT.md`에 후보로 남긴다.
* `.env`, `.streamlit/secrets.toml`, API key 관련 파일은 열람하거나 출력하지 않는다.

---

## 2. 먼저 읽을 파일

아래 파일만 읽는다.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `AGENTS.md`
3. `ACTIVE_FUNCTION_MAP.md`
4. `REAL_MODEL_PLAN.md`
5. `CLEANUP_AUDIT_REPORT.md`
6. `app.py`
7. `views/`
8. `components/`
9. `styles/`
10. `services/`
11. `test_growth_model.py`
12. `test_prospect_search_split.py`
13. `test_state_refactor.py`
14. `test_analysis_helpers_split.py`

주의:

* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽지 않는다.
* secrets/env/API key 파일은 읽지 않는다.

---

## 3. 최종 목표 폴더 구조

가능하면 다음 구조로 정리한다.

```text
Database_Project/
  app.py
  requirements.txt
  .gitignore

  AGENTS.md
  CLAUDE_PROGRESS_SUMMARY.md
  ACTIVE_FUNCTION_MAP.md
  REAL_MODEL_PLAN.md
  CLEANUP_AUDIT_REPORT.md

  views/
  components/
  styles/
  services/

  docs/
    specs/
    tasks/
    reports/
    archive/
```

---

## 4. 루트에 남길 파일

루트에는 다음 유형만 남긴다.

### 4.1 실행/환경 파일

* `app.py`
* `requirements.txt`
* `.gitignore`
* 필요한 경우 Streamlit 실행에 직접 필요한 설정 파일

### 4.2 핵심 운영 문서

* `AGENTS.md`
* `CLAUDE_PROGRESS_SUMMARY.md`
* `ACTIVE_FUNCTION_MAP.md`
* `REAL_MODEL_PLAN.md`
* `CLEANUP_AUDIT_REPORT.md`

### 4.3 실제 코드 폴더

* `views/`
* `components/`
* `styles/`
* `services/`

### 4.4 핵심 Python 모듈

실제로 import되는 root-level Python 파일은 유지한다.

예:

* `theme.py`
* `ui_components.py`
* `player_coverage.py`
* `growth_model.py`
* `explanation_engine.py`
* `analysis_helpers.py`
* `gemini_client.py`
* `scouting_note_payload.py`
* `manual_prospect_helpers.py`
* 기타 실제 import되는 파일

주의:
실제 import되는 Python 파일은 폴더 이동하지 않는다.
이동하려면 모든 import 수정과 테스트가 필요하므로 이번 작업에서는 하지 않는다.

---

## 5. docs/로 이동할 파일

### 5.1 docs/specs/

제품 설계/명세 문서 이동.

대상 예시:

* `V19_PRODUCT_REDESIGN_SPEC.md`
* 기타 최종 설계 문서

주의:
`REAL_MODEL_PLAN.md`은 현재 Claude/Codex가 자주 읽는 핵심 문서라면 루트에 유지한다.

---

### 5.2 docs/tasks/

작업 지시서 이동.

대상 예시:

* `CODEX_TASK_*.md`
* `V19_*_TASK.md`
* `V19_PHASE*.md`
* `V19_UI_REDESIGN*.md`
* 현재 완료된 task 문서

주의:
현재 진행 중인 task 파일은 루트에 남겨도 된다.
완료된 task 파일만 이동한다.

---

### 5.3 docs/reports/

보고서/검토 결과/diff 문서 이동.

대상 예시:

* `FINAL_*.md`
* `REGRESSION*.md`
* `DB_HELPER_DIFF*.md`
* `CLEANUP_AUDIT_REPORT.md`의 보조 보고서
* 기타 완료 보고서

주의:
`CLEANUP_AUDIT_REPORT.md`는 사용자가 루트에서 자주 확인할 수 있으므로 루트에 남겨도 된다.
보조 보고서만 docs/reports로 이동한다.

---

### 5.4 docs/archive/

긴 과거 기록 또는 archive 문서 이동.

대상 예시:

* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`
* 오래된 progress archive
* 더 이상 일반 작업에서 읽지 않는 큰 문서

주의:
`CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 읽지 말고 파일 이동만 가능하면 이동한다.
이동 시 `CLAUDE_PROGRESS_SUMMARY.md`에서 archive 경로를 `docs/archive/CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`로 업데이트한다.

단, `.gitignore`의 `CLAUDE*.md` 규칙 때문에 archive 파일이 ignored 상태일 수 있다. 이 경우 Git 반영 여부를 보고서에 명시한다.

---

## 6. 삭제 후보

삭제는 매우 보수적으로 한다.

삭제 가능 후보:

* `*.tmp`
* `*.tmp.*`
* `__pycache__/`
* `.pytest_cache/`
* 명백한 임시 백업 파일
* 실제 import되지 않는 중복 view 임시 파일

삭제 전 반드시 확인:

* import/reference 검색
* 삭제 후 compileall
* 테스트 실행

애매한 파일은 삭제하지 말고 `FOLDER_ORGANIZATION_REPORT.md`에 “삭제 후보”로 남긴다.

---

## 7. 테스트 파일 처리 정책

현재 테스트 파일은 루트에 남겨도 된다.

예:

* `test_growth_model.py`
* `test_prospect_search_split.py`
* `test_state_refactor.py`
* `test_analysis_helpers_split.py`

이번 작업에서는 테스트 파일을 `tests/`로 이동하지 않는다.

이유:

* 테스트 실행 명령이 이미 루트 기준으로 고정되어 있다.
* import 경로가 깨질 수 있다.
* 최종 마무리 단계에서 불필요한 리스크를 줄이기 위함.

단, 보고서에는 “추후 개선 시 tests/ 폴더로 이동 가능”이라고 남긴다.

---

## 8. 코드 구조 점검

이번 작업에서는 파일 이동뿐 아니라 구조 점검도 한다.

확인할 것:

1. app.py가 비대해졌는지
2. theme.py와 styles/theme.py 역할이 명확한지
3. ui_components.py와 components/ 역할이 중복되지 않는지
4. components/cards.py가 과도하게 커졌는지
5. styles/game_ui.css가 중복 class를 많이 포함하는지
6. use_container_width warning 잔여 여부
7. 실제 앱에서 import되지 않는 Python 파일이 루트에 남아 있는지

삭제/수정이 위험하면 보고서에만 남긴다.

---

## 9. 문서 경로 업데이트

문서를 이동한 경우 아래 문서의 경로 참조를 업데이트한다.

* `CLAUDE_PROGRESS_SUMMARY.md`
* `AGENTS.md`
* `ACTIVE_FUNCTION_MAP.md`
* `REAL_MODEL_PLAN.md`

특히:

* archive 경로
* task 문서 위치
* specs 문서 위치
* cleanup report 위치

주의:
문서 경로 업데이트만 하고, 긴 archive 내용을 읽거나 요약하지 않는다.

---

## 10. 산출물

이번 작업 후 다음 파일을 생성한다.

```text
FOLDER_ORGANIZATION_REPORT.md
```

보고서에는 다음을 포함한다.

1. 작업 전 git status 요약
2. 최종 폴더 구조
3. 루트에 남긴 파일 목록
4. docs/specs로 이동한 파일
5. docs/tasks로 이동한 파일
6. docs/reports로 이동한 파일
7. docs/archive로 이동한 파일
8. 삭제한 파일
9. 삭제하지 않고 남긴 후보 파일
10. 이동하지 않은 이유가 있는 파일
11. 테스트 파일을 루트에 유지한 이유
12. app.py 비대화 여부
13. components/styles 구조 점검 결과
14. use_container_width warning 점검 결과
15. 테스트 결과
16. Streamlit health check 결과
17. 남은 정리 후보

---

## 11. 문서 업데이트

작업 후 아래 문서를 업데이트한다.

1. `CLAUDE_PROGRESS_SUMMARY.md`
2. `ACTIVE_FUNCTION_MAP.md`
3. `REAL_MODEL_PLAN.md`
4. `AGENTS.md`

섹션명:

```text
v19 Final Folder Organization: docs archive and root cleanup
```

포함 내용:

* docs/ 구조 생성 여부
* task/spec/report/archive 문서 이동
* 루트에 남긴 핵심 파일
* 테스트 결과
* 남은 후보

---

## 12. 테스트 요구사항

작업 후 반드시 실행한다.

```bash
python -m compileall .
python test_state_refactor.py
python test_analysis_helpers_split.py
python test_prospect_search_split.py
python test_growth_model.py
```

Streamlit health check도 실행한다.

---

## 13. 절대 금지

* DB 스키마 변경 금지
* `create_and_upload_db.py` 수정 금지
* `.streamlit/secrets.toml` 내용 출력 금지
* `.env` 내용 출력 금지
* API key 값 출력/저장/문서화 금지
* 원본 CSV 수정 금지
* Growth/Ceiling 공식 변경 금지
* 기존 JSONB key 삭제 금지
* legacy fallback 삭제 금지
* 실제 import되는 Python 파일 임의 이동/삭제 금지
* 테스트 파일을 이번 작업에서 tests/로 이동 금지
* `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md` 내용 읽기 금지
* 사용자가 명시적으로 보관 중인 문서 삭제 금지

---

## 14. 완료 보고 형식

완료 후 아래 형식으로 보고한다.

1. 수정한 코드 파일
2. 수정한 문서 파일
3. 새로 만든 폴더
4. 새로 만든 문서 파일
5. 이동한 파일
6. 삭제한 파일
7. 루트에 남긴 주요 파일
8. docs/ 구조 요약
9. 삭제하지 않고 남긴 후보 파일
10. 코드 구조 점검 결과
11. app.py 비대화 여부
12. components/styles 구조 점검 결과
13. use_container_width warning 점검 결과
14. 테스트 결과
15. Streamlit health check 결과
16. FOLDER_ORGANIZATION_REPORT.md 주요 내용
17. 남은 문제
