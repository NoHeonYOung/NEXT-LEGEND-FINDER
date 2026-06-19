# CLEANUP_AUDIT_REPORT.md
Generated: 2026-06-18 | V19 Final Polish & Cleanup

## v19 Final User Flow Fix Addendum

This follow-up changed user-facing flow and labels, not data infrastructure.

- Gemini raw API errors are no longer shown directly in the default UI; raw details are limited to a developer expander.
- Player Dossier now explains mentality evidence and shares user-entered qualitative text with the Evidence & Advisory Report flow.
- Career Simulation uses descriptive choices for training intensity and playing time while preserving the existing numeric env_settings contract.
- Scouting Board defaults to ability-profile candidates; Limited/basic-info candidates are advanced options.
- Mentor Matching Lab is mentor-first, with similarity references hidden in an expander.
- DB schema, secrets/env, original CSVs, Growth/Ceiling formulas, style_vector calculation, pgvector query, and Notes payload contracts were not changed.

---

## 1. Repository Hygiene — Files Deleted

### views/ tmp files (deleted during PART A)
All 23 `.tmp.*` backup files that had accumulated in `views/` were deleted before this session by prior v19 phase work. As of this session, `views/` contains only active source files:
- `ai_report.py`, `career_simulation.py`, `dashboard.py`, `db_status.py`
- `experimental_data_lab.py`, `home.py`, `legend_matching.py`, `manual_prospect.py`
- `prospect_search.py`, `scouting_notes.py`

---

## 2. Root-level Task/Planning Files — Safe to Archive (NOT auto-deleted)

These files served as AI task specifications. They are no longer actively used but are NOT deleted because:
- They document design decisions
- They may be referenced for regression checks

| File | Status | Note |
|------|--------|------|
| `V19_PHASE1_2_IMPLEMENT_TASK.md` | Complete | Phase 1/2 of v19 UI redesign |
| `V19_PRODUCT_REDESIGN_TASK.md` | Complete | v19 initial redesign spec |
| `V19_UI_REDESIGN_PHASE_A_TASK.md` | Complete | Phase A implementation |
| `V19_UI_REDESIGN_PHASE_A1_QA_POLISH_TASK.md` | Complete | Phase A1 QA |
| `V19_UI_REDESIGN_PHASE_B_TASK.md` | Complete | Phase B implementation |
| `V19_UI_REDESIGN_PHASE_C_TASK.md` | Complete | Phase C implementation |
| `V19_FINAL_POLISH_AND_CLEANUP_TASK.md` | Complete (this session) | Final polish spec |
| `CODEX_TASK_V16_1_PERSISTENCE_QA.md` | Complete | v16.1 persistence QA |
| `CODEX_TASK_V16_2_SAVED_NOTE_UI.md` | Complete | v16.2 saved note UI |
| `FINAL_IMPLEMENTATION_ROADMAP.md` | Superseded | Pre-v19 roadmap |
| `DB_HELPER_DIFF.md` | Reference | DB helper migration notes |

**Recommendation**: Move all `V19_*.md`, `CODEX_TASK_*.md`, `FINAL_IMPLEMENTATION_ROADMAP.md`, `DB_HELPER_DIFF.md` to `archive/docs/` when the project is stable.

---

## 3. archive/ Directory Audit

### archive/backups/ — Python backup files
These are point-in-time snapshots created before major refactors. Safe to delete once confirmed stable, but kept for rollback reference.

| Pattern | Count | Safe to delete? |
|---------|-------|-----------------|
| `app_backup_before_*.py` | ~10 | Yes, after stability confirmed |
| `ai_report_backup_*.py` | 1 | Yes |
| `analysis_helpers_backup_*.py` | 1 | Yes |
| `career_simulation_backup_*.py` | 1 | Yes |
| `home_backup_*.py` | 3 | Yes |

### archive/docs/ — Markdown docs
- `CLAUDE_NEXT_SESSION_UI_TASK.md` — superseded task file, safe to delete
- `CLAUDE_TASK_FULL.md` — old full task spec, safe to delete

### archive/logs/
- `streamlit.err.log`, `streamlit.out.log` — stale run logs, safe to delete

---

## 4. Code Duplication Audit

### theme.py vs styles/theme.py
- `theme.py` (root): thin wrapper — imports and re-exports from `styles/theme.py`. **No duplication issue.**
- `styles/theme.py`: canonical source of CSS/HTML theme utilities.
- **Decision**: No change needed. Existing import paths in views/ expect `from theme import ...`; wrapper preserves compatibility.

### ui_components.py vs components/
- `ui_components.py`: shared widget/layout helpers + new `POSITION_OPTIONS`, `FOOT_OPTIONS`, `build_*_options()` helpers added this session.
- `components/`: specialized card renderers (`cards.py`), badge utilities (`badges.py`), scouting notes UI (`scouting_notes_ui.py`).
- **No meaningful overlap detected.** The split is logical (generic UI helpers vs. domain-specific card/badge components).

---

## 5. Import Audit

### Unused imports removed / confirmed
- `app.py`: all imports actively used by router; no dead imports found.
- `views/dashboard.py`: added `source_badge_html`, `FEATURE_SOURCE_BADGES`, `build_strengths_with_meta`, `build_risks_with_meta` — all used.
- `views/manual_prospect.py`: added `FOOT_OPTIONS`, `build_club_options`, `build_nationality_options`, `build_position_options` — all used.
- `views/ai_report.py`: existing imports confirmed active.
- `explanation_engine.py`: all helpers used by dashboard and ai_report.

---

## 6. app.py Size Check

- Line count: 426 lines (as of v19 phase C completion).
- **Assessment**: Appropriate for a top-level Streamlit router/bootstrap. No logic creep detected.
- All view rendering is delegated to `views/*.py` modules.

---

## 7. use_container_width Audit

Two remaining uses in active code:
| Location | Usage | Status |
|----------|-------|--------|
| `analysis_helpers.py:169` | `st.altair_chart(..., use_container_width=True)` | Valid — chart needs responsive width |
| `app.py:272` | `st.button(..., use_container_width=True)` | Valid — navigation button should fill column |

No deprecated or warning-generating uses found.

---

## 8. V19 Final Polish Changes Summary

### PART B: Input UI Improvements
- `services/db.py`: Added `get_distinct_nationalities()`, `get_distinct_clubs()`
- `ui_components.py`: Added `POSITION_OPTIONS`, `FOOT_OPTIONS`, `build_position_options()`, `build_nationality_options()`, `build_club_options()`
- `views/manual_prospect.py`: All position/nationality/club/foot text inputs replaced with `selectbox` + "기타 / 직접 입력" fallback

### PART C: Evidence-Based Explanation Enhancement
- `explanation_engine.py`: 4-part structured text (핵심/근거/해석/방향) for all 6 growth features; source badge metadata
- `views/dashboard.py`: `_render_strength_risk_panels()` with badge display
- `views/career_simulation.py`: Source badges (Ceiling Scenario / Growth Model / Rule-based) in coaching panels
- `views/ai_report.py`: 8-section report structure with explicit data source labels and FM proxy disclaimers
- `analysis_helpers.py`: FM proxy/style_vector source labeling in similarity and mentor guide text

---

## 9. Test Results

```
test_growth_model.py:           82 passed, 2 warnings  (49s)
test_state_refactor.py:          4 passed               (part of 9-test run)
test_prospect_search_split.py:   3 passed               (part of 9-test run)
test_analysis_helpers_split.py:  2 passed               (part of 9-test run)
Total: 91 passed, 0 failed
```
