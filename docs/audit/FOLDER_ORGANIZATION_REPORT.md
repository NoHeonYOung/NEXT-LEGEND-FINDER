# FOLDER_ORGANIZATION_REPORT.md

작업일: 2026-06-18  
작업 기준: V19_FINAL_FOLDER_ORGANIZATION_TASK (docs/tasks/OLDER_ORGANIZATION_TASV19_FINAL_FK.md)

---

## 1. 작업 전 git status 요약

**Modified (not staged):**
- ACTIVE_FUNCTION_MAP.md, AGENTS.md, CLAUDE_PROGRESS_SUMMARY.md, REAL_MODEL_PLAN.md
- analysis_helpers.py, app.py, explanation_engine.py, services/db.py
- test_growth_model.py, test_prospect_search_split.py, theme.py, ui_components.py
- views/ai_report.py, views/career_simulation.py, views/dashboard.py,
  views/legend_matching.py, views/manual_prospect.py, views/prospect_search.py, views/scouting_notes.py

**Untracked (이번 작업 대상):**
- CLEANUP_AUDIT_REPORT.md, CODEX_TASK_V16_1_PERSISTENCE_QA.md, CODEX_TASK_V16_2_SAVED_NOTE_UI.md
- DB_HELPER_DIFF.md, FINAL_IMPLEMENTATION_ROADMAP.md, OLDER_ORGANIZATION_TASV19_FINAL_FK.md
- V19_FINAL_POLISH_AND_CLEANUP_TASK.md, V19_PHASE1_2_IMPLEMENT_TASK.md
- V19_PRODUCT_REDESIGN_TASK.md, V19_UI_REDESIGN_PHASE_A1_QA_POLISH_TASK.md
- V19_UI_REDESIGN_PHASE_A_TASK.md, V19_UI_REDESIGN_PHASE_B_TASK.md
- V19_UI_REDESIGN_PHASE_C_TASK.md, archive/, components/, styles/

기존 변경사항은 임의로 되돌리지 않았다.

---

## 2. 최종 폴더 구조

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
  FOLDER_ORGANIZATION_REPORT.md  (신규)

  analysis_helpers.py
  evidence_extractor.py
  explanation_engine.py
  gemini_client.py
  grid_pipeline.py
  growth_model.py
  manual_prospect_helpers.py
  player_coverage.py
  scouting_note_payload.py
  state.py
  theme.py
  ui_components.py
  create_and_upload_db.py

  test_growth_model.py
  test_state_refactor.py
  test_prospect_search_split.py
  test_analysis_helpers_split.py
  test_experimental_data_lab.py

  views/
  components/
  styles/
  services/

  docs/
    specs/
      V19_PRODUCT_REDESIGN_SPEC.md
    tasks/
      CODEX_TASK_V16_1_PERSISTENCE_QA.md
      CODEX_TASK_V16_2_SAVED_NOTE_UI.md
      OLDER_ORGANIZATION_TASV19_FINAL_FK.md
      V19_FINAL_POLISH_AND_CLEANUP_TASK.md
      V19_PHASE1_2_IMPLEMENT_TASK.md
      V19_PRODUCT_REDESIGN_TASK.md
      V19_UI_REDESIGN_PHASE_A1_QA_POLISH_TASK.md
      V19_UI_REDESIGN_PHASE_A_TASK.md
      V19_UI_REDESIGN_PHASE_B_TASK.md
      V19_UI_REDESIGN_PHASE_C_TASK.md
    reports/
      DB_HELPER_DIFF.md
      FINAL_IMPLEMENTATION_ROADMAP.md
    archive/
      CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md
      CLAUDE_NEXT_SESSION_UI_TASK.md  (archive/docs에서 이동)
      CLAUDE_TASK_FULL.md             (archive/docs에서 이동)
      project_hw5.md

  archive/
    backups/  (Python 백업 파일 다수)
    logs/     (streamlit.err.log, streamlit.out.log)

  Database_Project_Dataset/
  data_samples/
```

---

## 3. 루트에 남긴 파일 목록

### 실행/환경 파일
- `app.py`
- `requirements.txt`
- `.gitignore`

### 핵심 운영 문서
- `AGENTS.md`
- `CLAUDE_PROGRESS_SUMMARY.md`
- `ACTIVE_FUNCTION_MAP.md`
- `REAL_MODEL_PLAN.md`
- `CLEANUP_AUDIT_REPORT.md`
- `FOLDER_ORGANIZATION_REPORT.md` (신규)

### 실제 import되는 Python 모듈 (루트)
- `analysis_helpers.py`
- `evidence_extractor.py` (views/experimental_data_lab.py에서 import)
- `explanation_engine.py`
- `gemini_client.py`
- `grid_pipeline.py` (views/experimental_data_lab.py에서 import)
- `growth_model.py`
- `manual_prospect_helpers.py`
- `player_coverage.py`
- `scouting_note_payload.py`
- `state.py`
- `theme.py`
- `ui_components.py`
- `create_and_upload_db.py` (절대 금지 파일 — 건드리지 않음)

### 테스트 파일 (루트 유지)
- `test_growth_model.py`
- `test_state_refactor.py`
- `test_prospect_search_split.py`
- `test_analysis_helpers_split.py`
- `test_experimental_data_lab.py`

### 코드 폴더
- `views/`
- `components/`
- `styles/`
- `services/`

---

## 4. docs/specs/로 이동한 파일

| 파일 | 이유 |
|------|------|
| `V19_PRODUCT_REDESIGN_SPEC.md` | v19 전체 설계 명세 문서 |

---

## 5. docs/tasks/로 이동한 파일

| 파일 | 상태 |
|------|------|
| `CODEX_TASK_V16_1_PERSISTENCE_QA.md` | 완료 |
| `CODEX_TASK_V16_2_SAVED_NOTE_UI.md` | 완료 |
| `OLDER_ORGANIZATION_TASV19_FINAL_FK.md` | 완료 (이번 작업 task 파일) |
| `V19_FINAL_POLISH_AND_CLEANUP_TASK.md` | 완료 |
| `V19_PHASE1_2_IMPLEMENT_TASK.md` | 완료 |
| `V19_PRODUCT_REDESIGN_TASK.md` | 완료 |
| `V19_UI_REDESIGN_PHASE_A1_QA_POLISH_TASK.md` | 완료 |
| `V19_UI_REDESIGN_PHASE_A_TASK.md` | 완료 |
| `V19_UI_REDESIGN_PHASE_B_TASK.md` | 완료 |
| `V19_UI_REDESIGN_PHASE_C_TASK.md` | 완료 |

---

## 6. docs/reports/로 이동한 파일

| 파일 | 이유 |
|------|------|
| `DB_HELPER_DIFF.md` | v8 세션 DB helper 비교 기록 |
| `FINAL_IMPLEMENTATION_ROADMAP.md` | pre-v19 로드맵 (superseded) |

---

## 7. docs/archive/로 이동한 파일

| 파일 | 원래 위치 |
|------|-----------|
| `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md` | 루트 |
| `CLAUDE_NEXT_SESSION_UI_TASK.md` | archive/docs/ |
| `CLAUDE_TASK_FULL.md` | archive/docs/ |
| `project_hw5.md` | 루트 (hw 파일, 더 이상 앱에서 사용되지 않음) |

주의: `CLAUDE_PROGRESS_SUMMARY_ARCHIVE.md`는 내용을 읽지 않고 이동만 수행했다.  
`.gitignore`의 `CLAUDE*.md` 규칙으로 인해 이 파일이 git ignored 상태일 수 있다 — git 반영 여부는 별도로 확인 필요.

---

## 8. 삭제한 파일

없음. 이번 작업에서는 삭제를 수행하지 않았다 (보수적 정책).

---

## 9. 삭제하지 않고 남긴 후보 파일

| 파일/폴더 | 판단 | 이유 |
|-----------|------|------|
| `ui/` 폴더 | 삭제 후보 | `ui/components.py`, `ui/navigation.py`는 현재 app.py에서 import되지 않음. archive 백업 파일에서만 참조됨. 삭제 전 확인 필요. |
| `archive/backups/` | 유지 후보 | Python 백업 파일 36개. 복구 목적. 안정성 확인 후 삭제 가능. |
| `archive/logs/` | 유지 후보 | `streamlit.err.log`, `streamlit.out.log` — 오래된 로그. |
| `streamlit_health.log` | 유지 후보 | 루트의 Streamlit health log. 정기적으로 삭제 가능. |
| `.pytest_cache/` | 삭제 후보 | 테스트 캐시. 언제든 삭제 가능. |
| `__pycache__/` | 삭제 후보 | Python 캐시. 언제든 삭제 가능. |

---

## 10. 이동하지 않은 이유가 있는 파일

| 파일 | 이유 |
|------|------|
| `CLEANUP_AUDIT_REPORT.md` | task 지시에 따라 루트에 유지 (사용자가 자주 확인) |
| `create_and_upload_db.py` | 절대 금지 파일 — 수정/이동 금지 |
| `Database_Project_Dataset/` | 원본 데이터 — 건드리지 않음 |
| `data_samples/` | 샘플 데이터 — 건드리지 않음 |
| `.streamlit/` | Streamlit 설정 — 건드리지 않음 |

---

## 11. 테스트 파일을 루트에 유지한 이유

- 테스트 실행 명령이 루트 기준으로 고정되어 있다.
- import 경로가 루트 기반 모듈(`growth_model`, `analysis_helpers` 등)을 직접 참조한다.
- `tests/`로 이동 시 import 경로 전체 수정 필요 → 최종 마무리 단계의 불필요한 리스크.
- **추후 개선 시 `tests/` 폴더로 이동 가능.**

---

## 12. app.py 비대화 여부

- app.py: **426줄** — 이전 audit 기준 적정 수준 확인.
- app.py는 라우터 역할만 수행하며 view 로직은 모두 `views/*.py`에 위임됨.
- 비대화 없음.

---

## 13. components/styles 구조 점검 결과

| 항목 | 결과 |
|------|------|
| `theme.py` vs `styles/theme.py` | 역할 분리 명확. `theme.py`는 CSS loader entrypoint, `styles/theme.py`는 실제 CSS 로더. 중복 없음. |
| `ui_components.py` vs `components/` | 역할 분리 명확. `ui_components.py`는 nav/badge/coverage helper, `components/`는 HTML 렌더 컴포넌트. 중복 없음. |
| `components/cards.py` | 다양한 card/panel HTML helper 포함. 비대하지만 기능별 분리가 이미 되어 있음. 현재 수준 적정. |
| `styles/game_ui.css` | Phase A~C CSS 누적. 중복 class 여부는 별도 감사 필요 (이번 작업 범위 외). |
| `ui/` 폴더 | 현재 앱에서 import되지 않음 (archive 백업에서만 참조). 삭제 후보로 남김. |

---

## 14. use_container_width warning 점검 결과

`use_container_width=True` 사용 위치:
- `analysis_helpers.py`: altair_chart → 유효
- `app.py`: 홈 버튼 → 유효
- `views/db_status.py`: dataframe → 유효
- `views/experimental_data_lab.py`: altair_chart, dataframe → 유효
- `views/home.py`: 여러 button → 유효
- `ui/navigation.py`: button → 유효 (단, ui/ 폴더 자체가 현재 미사용)

모두 buttons/dataframes/charts에서 정상 사용 중. Streamlit deprecation 경고 없음.

---

## 15. 테스트 결과

```
python -m compileall .             → 0 errors
python test_state_refactor.py      → test_home_renders OK, test_vinicius_transfermarkt_only OK, test_manual_note_status OK
python test_analysis_helpers_split.py → test_home_renders OK, test_vinicius_dashboard_and_legend_matching OK, test_matched_player_full_flow OK, test_manual_prospect_submission OK
python test_prospect_search_split.py  → test_prospect_search_renders OK, test_search_select_and_stale_profile_id_cleared OK
python test_growth_model.py           → 82 tests OK (포함: v19 UI, coverage helpers, scouting board, legend matching 등)
```

총 91 tests — 0 failed.

---

## 16. Streamlit health check 결과

```
python -c "import app"  → app.py import OK (Streamlit bare mode warning만, 정상)
```

모든 모듈 import 이상 없음. 파일 이동으로 인한 import 오류 없음.

---

## 17. 남은 정리 후보

1. **`ui/` 폴더 삭제** — 현재 앱에서 미사용. 안전하게 삭제 가능하나, 사용자가 명시적으로 확인 후 결정 권장.
2. **`archive/backups/` 정리** — 36개 Python 백업. 안정성 확인 후 삭제 가능.
3. **`__pycache__/`, `.pytest_cache/` 정리** — 언제든 삭제 가능.
4. **`streamlit_health.log` 정리** — 정기 삭제 가능.
5. **`styles/game_ui.css` 중복 class 감사** — 이번 작업 범위 외. 향후 개선 시 수행.
6. **테스트 파일 `tests/` 이동** — 향후 개선 시. import 경로 수정 병행 필요.
7. **`CLEANUP_AUDIT_REPORT.md` 최신화** — 이번 폴더 정리 반영 필요.
