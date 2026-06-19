import streamlit as st

from analysis_helpers import format_percent, parse_json_field, readable_setting
from components.badges import coverage_badge_html, source_badge_html
from components.cards import (
    archive_note_card_html,
    empty_state_panel_html,
    game_alert_html,
    list_panel_html,
    panel_html,
    stat_grid_html,
)
from components.layout import render_game_page_title
from manual_prospect_helpers import safe_text
from scouting_note_payload import extract_structured_note_result
from services.db import get_scouting_notes
from ui_components import render_page_actions


NOTE_TYPE_LABELS = {
    "ai_report": "규칙 기반 리포트 저장",
    "career_simulation": "커리어 시뮬레이션 저장",
    "manual_custom_prospect": "직접 입력 선수 노트",
    "legacy_note": "이전 형식 노트",
}

SOURCE_LABELS = {
    "ai_report": "규칙 기반 리포트",
    "career_simulation": "커리어 시뮬레이션",
    "manual_note": "직접 입력 분석",
    "legacy": "이전 저장 데이터",
}

ENTITY_TYPE_LABELS = {
    "matched": "실제 DB + FM 매칭 선수",
    "transfermarkt_only": "실제 DB 선수",
    "fm_profile_only": "FM 프로필 선수",
    "manual_note": "직접 입력 선수",
    "manual_prospect": "직접 입력 유망주",
    "db_player": "실제 DB 선수",
}

REPORT_MODE_LABELS = {
    "rule_based": "데이터 기반 분석",
    "rule_based_with_gemini": "데이터 기반 + AI 보조",
}

COACHING_SECTION_KEYS = [
    ("추천 훈련 방향", "training_directions"),
    ("기대 장점", "expected_benefits"),
    ("소홀히 했을 때의 단점", "neglect_risks"),
    ("리스크 경고", "risk_warnings"),
    ("추천 커리어 전략", "career_strategy"),
]


_SIGNAL_VALUE_LABELS = {
    "positive": "긍정적", "negative": "부정적", "unknown": "정보 없음",
    "high": "높음", "medium": "보통", "low": "낮음",
    "yes": "있음", "no": "없음",
}


def _fmt_signal(value):
    if not value or value == "unknown":
        return None
    return _SIGNAL_VALUE_LABELS.get(str(value).lower(), str(value))


def _qual_signal_html(sig):
    if not isinstance(sig, dict):
        return f'<div class="game-muted">{str(sig)}</div>'

    parts = []

    summary = sig.get("qualitative_summary") or ""
    if summary:
        parts.append(f'<div style="margin-bottom:10px;font-weight:500;">{summary}</div>')

    strengths = sig.get("strength_mentions") or []
    if isinstance(strengths, list) and strengths:
        items_html = "".join(f"<li>{s}</li>" for s in strengths)
        parts.append(f'<div class="game-note-section"><div class="game-note-section-label">강점</div><ul style="margin:4px 0 0 16px;padding:0;">{items_html}</ul></div>')

    weaknesses = sig.get("weakness_mentions") or []
    if isinstance(weaknesses, list) and weaknesses:
        items_html = "".join(f"<li>{s}</li>" for s in weaknesses)
        parts.append(f'<div class="game-note-section"><div class="game-note-section-label">보완점</div><ul style="margin:4px 0 0 16px;padding:0;">{items_html}</ul></div>')

    focus = sig.get("recommended_focus") or []
    if isinstance(focus, list) and focus:
        items_html = "".join(f"<li>{s}</li>" for s in focus)
        parts.append(f'<div class="game-note-section"><div class="game-note-section-label">추천 훈련 포커스</div><ul style="margin:4px 0 0 16px;padding:0;">{items_html}</ul></div>')

    meta_rows = []
    for label, key in [("멘탈 신호", "mentality_signal"), ("개발 가능성", "development_signal"),
                       ("출전 시간", "playing_time_signal"), ("부상 위험", "injury_risk_signal")]:
        v = _fmt_signal(sig.get(key))
        if v:
            meta_rows.append(f'<span style="margin-right:16px;"><b>{label}:</b> {v}</span>')
    if meta_rows:
        parts.append(f'<div class="game-note-section" style="font-size:0.85em;">{"".join(meta_rows)}</div>')

    quotes = sig.get("evidence_quotes") or []
    if isinstance(quotes, list) and quotes:
        items_html = "".join(f'<li style="color:var(--text-muted,#aaa);">{q}</li>' for q in quotes)
        parts.append(f'<div class="game-note-section"><div class="game-note-section-label">근거 발췌</div><ul style="margin:4px 0 0 16px;padding:0;">{items_html}</ul></div>')

    return "".join(parts) if parts else '<div class="game-muted">분석 내용 없음</div>'


def _render_qualitative_evidence_panel(qual):
    signals_raw = qual.get("extracted_signals") if isinstance(qual, dict) else None
    if not signals_raw:
        st.markdown(
            panel_html("정성 텍스트 분석", '<div class="game-muted">저장 당시 정성 텍스트 없음</div>', kicker="QUALITATIVE"),
            unsafe_allow_html=True,
        )
        return

    signals = signals_raw if isinstance(signals_raw, list) else [signals_raw]
    body_parts = [_qual_signal_html(s) for s in signals]
    st.markdown(
        panel_html("정성 텍스트 분석", "".join(body_parts), kicker="QUALITATIVE"),
        unsafe_allow_html=True,
    )


def _safe_label(value, labels, fallback):
    return labels.get(value, fallback)


# Public aliases kept for test compatibility
def saved_note_label(value, labels, fallback):
    return labels.get(value, fallback)


def saved_coaching_sections(coaching, fallback_summary):
    coaching = coaching if isinstance(coaching, dict) else {}
    sections = [
        ("종합 평가", coaching.get("coaching_summary") or coaching.get("ceiling_summary") or fallback_summary),
    ]
    for label, key in COACHING_SECTION_KEYS:
        items = coaching.get(key)
        if isinstance(items, (list, tuple)) and items:
            sections.append((label, list(items)))
        elif isinstance(items, str) and items.strip():
            sections.append((label, items.strip()))
    return sections


def saved_report_original(note, structured):
    return _saved_report_original(note, structured)


def _note_display_title(note):
    env = parse_json_field(note.get("env_settings")) if note is not None else {}
    if isinstance(env, dict):
        manual_player = env.get("manual_player") if isinstance(env.get("manual_player"), dict) else {}
        manual_name = safe_text(manual_player.get("name"), None)
        if manual_name:
            return manual_name
        player_name = safe_text(env.get("player_name"), None)
        if player_name:
            return player_name
    db_name = safe_text(note.get("player_name"), None) if note is not None else None
    if db_name:
        return db_name
    selected_name = safe_text(st.session_state.get("selected_player_name"), None)
    if selected_name:
        return selected_name
    return "이름 없는 노트"


def _extract_note_data(note):
    """노트 row에서 표시에 필요한 데이터를 추출한다."""
    env = parse_json_field(note.get("env_settings")) or {}
    sim = parse_json_field(note.get("simulation_result")) or {}
    structured = extract_structured_note_result(sim)

    stored_growth = structured["ceiling_growth_insight"] or structured["growth_insight"]
    stored_explanation = structured["ceiling_growth_explanation"] or structured["growth_explanation"]
    coaching = stored_explanation.get("ceiling_explanation") if isinstance(stored_explanation, dict) else {}
    coaching = coaching if isinstance(coaching, dict) else {}

    manual_player = env.get("manual_player") if isinstance(env, dict) and isinstance(env.get("manual_player"), dict) else {}
    legacy_player = env.get("player") if isinstance(env, dict) and isinstance(env.get("player"), dict) else {}
    saved_player = env.get("player_snapshot") if isinstance(env, dict) and isinstance(env.get("player_snapshot"), dict) else {}
    player_snapshot = saved_player or manual_player or legacy_player
    if not player_snapshot and note.get("player_name"):
        player_snapshot = {
            "name": safe_text(note.get("player_name"), "이름 없는 노트"),
            "age": env.get("age"),
            "position": env.get("position"),
            "club": env.get("club"),
            "nationality": env.get("nationality"),
        }

    ceiling_model = stored_growth.get("ceiling_model") if isinstance(stored_growth, dict) else {}
    ceiling_model = ceiling_model if isinstance(ceiling_model, dict) else {}
    growth_score = stored_growth.get("growth_score", sim.get("prototype_growth_score")) if isinstance(stored_growth, dict) else sim.get("prototype_growth_score")
    final_growth_score = ceiling_model.get("final_growth_score")
    injury_risk = sim.get("prototype_injury_risk")

    note_type = env.get("note_type") or "legacy_note"
    source = env.get("source") or "legacy"
    entity_type = env.get("entity_type") or ("manual_note" if manual_player else "db_player")
    report_mode = env.get("report_generation_mode") or "rule_based"
    has_gemini = report_mode == "rule_based_with_gemini"
    has_qualitative = bool(
        isinstance(structured.get("qualitative_evidence"), dict)
        and structured["qualitative_evidence"].get("extracted_signals")
    )

    stored_summary = stored_explanation.get("summary") if isinstance(stored_explanation, dict) else None
    env_summary = (
        f"훈련강도 {readable_setting('training_intensity', env.get('training_intensity', 0))}, "
        f"출전 {readable_setting('playing_time_opportunity', env.get('playing_time_opportunity', 0))}"
    )
    summary = safe_text(
        coaching.get("coaching_summary") or stored_summary or sim.get("overall_summary"),
        env_summary,
    )

    strengths = sim.get("strengths") if isinstance(sim, dict) else []
    weaknesses = sim.get("weaknesses") if isinstance(sim, dict) else []
    if not strengths and isinstance(stored_explanation, dict):
        strengths = stored_explanation.get("strengths") or []
    if not weaknesses and isinstance(stored_explanation, dict):
        weaknesses = stored_explanation.get("risks") or []

    return {
        "env": env,
        "sim": sim,
        "structured": structured,
        "player_snapshot": player_snapshot,
        "growth_score": growth_score,
        "final_growth_score": final_growth_score,
        "injury_risk": injury_risk,
        "note_type": note_type,
        "source": source,
        "entity_type": entity_type,
        "report_mode": report_mode,
        "has_gemini": has_gemini,
        "has_qualitative": has_qualitative,
        "coaching": coaching,
        "summary": summary,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "mentor_name": env.get("selected_mentor_name"),
        "report_original": _saved_report_original(note, structured),
    }


def _saved_report_original(note, structured):
    report = note.get("gemini_report") if hasattr(note, "get") else None
    if isinstance(report, str) and report.strip():
        return report.strip()
    generated = structured.get("generated_report_text") if isinstance(structured, dict) else None
    return generated.strip() if isinstance(generated, str) else ""


def _archive_strip_html(notes_list):
    total = len(notes_list)
    db_count = sum(1 for d in notes_list if d["entity_type"] in ("matched", "transfermarkt_only", "fm_profile_only", "db_player"))
    manual_count = sum(1 for d in notes_list if d["entity_type"] in ("manual_note", "manual_prospect"))
    gemini_count = sum(1 for d in notes_list if d["has_gemini"])
    qual_count = sum(1 for d in notes_list if d["has_qualitative"])
    stats = [
        ("Total Notes", str(total)),
        ("DB Player", str(db_count)),
        ("Manual", str(manual_count)),
        ("Gemini Used", str(gemini_count)),
        ("Qualitative", str(qual_count)),
    ]
    items = "".join(
        f'<div class="game-archive-stat">'
        f'<div class="value">{v}</div>'
        f'<div class="label">{l}</div>'
        "</div>"
        for l, v in stats
    )
    return f'<div class="game-archive-strip">{items}</div>'


def _note_badges(data):
    badges = []
    entity = data["entity_type"]
    if entity in ("matched", "db_player", "transfermarkt_only", "fm_profile_only"):
        badges.append(source_badge_html("DB", "ok"))
    elif entity in ("manual_note", "manual_prospect"):
        badges.append(source_badge_html("Manual", "manual"))
    if data["has_gemini"]:
        badges.append('<span class="game-badge badge-partial">Gemini</span>')
    else:
        badges.append('<span class="game-badge badge-neutral">데이터 기반 분석</span>')
    if data["has_qualitative"]:
        badges.append('<span class="game-badge badge-full">Qualitative</span>')
    return badges


def _render_note_detail(data, note):
    """선택된 노트의 상세 내용을 report room 스타일로 렌더링."""
    player_snapshot = data["player_snapshot"] or {}
    structured = data["structured"]

    # 1. Saved Player Snapshot
    snap_stats = [
        ("이름", safe_text(player_snapshot.get("name"), "-")),
        ("나이", str(player_snapshot.get("age") or "-") + "세"),
        ("포지션", safe_text(player_snapshot.get("position"), "-")),
        ("소속팀", safe_text(player_snapshot.get("club"), "저장 당시 없음")),
        ("국적", safe_text(player_snapshot.get("nationality"), "저장 당시 없음")),
    ]
    body = stat_grid_html(snap_stats)
    st.markdown(panel_html("Saved Player Snapshot", body, kicker="NOTE DETAIL"), unsafe_allow_html=True)

    # 2. Data Coverage at Save Time
    coverage_items = [
        ("note_type", _safe_label(data["note_type"], NOTE_TYPE_LABELS, data["note_type"])),
        ("entity_type", _safe_label(data["entity_type"], ENTITY_TYPE_LABELS, data["entity_type"])),
        ("report_mode", _safe_label(data["report_mode"], REPORT_MODE_LABELS, data["report_mode"])),
        ("Gemini", "사용" if data["has_gemini"] else "미사용"),
        ("정성 텍스트", "있음" if data["has_qualitative"] else "없음"),
    ]
    coverage_body = stat_grid_html(coverage_items)
    st.markdown(panel_html("Data Coverage at Save Time", coverage_body), unsafe_allow_html=True)

    # 3. Growth / Ceiling Result
    gs = data["growth_score"]
    fgs = data["final_growth_score"]
    ir = data["injury_risk"]
    score_stats = [
        ("기본 성장 점수", str(gs) if gs not in (None, "") else "저장 당시 없음"),
        ("시나리오 반영 성장 점수", str(fgs) if fgs not in (None, "") else "저장 당시 없음"),
        ("부상 리스크", format_percent(ir) if ir is not None else "저장 당시 없음"),
    ]
    score_body = stat_grid_html(score_stats)
    st.markdown(panel_html("Growth / Ceiling Result", score_body), unsafe_allow_html=True)

    # 4. Qualitative Evidence
    qual = structured.get("qualitative_evidence") or {}
    _render_qualitative_evidence_panel(qual)

    # 5. Gemini Advisory
    gemini = structured.get("gemini_advisory") or {}
    if isinstance(gemini, dict) and (gemini.get("advisory_summary") or gemini.get("recommendations")):
        advisory_lines = []
        if gemini.get("advisory_summary"):
            advisory_lines.append(str(gemini["advisory_summary"]))
        recs = gemini.get("recommendations") or []
        if isinstance(recs, list):
            advisory_lines.extend(str(r) for r in recs)
        st.markdown(list_panel_html("Gemini Advisory", advisory_lines, kicker="GEMINI"), unsafe_allow_html=True)
    else:
        mode_badge = source_badge_html("Rule-based Only", "warning") if not data["has_gemini"] else ""
        body_html = f'<div class="game-card-row">{mode_badge}</div><div class="game-muted">Gemini 보조 추천 없음 (rule-based only)</div>'
        st.markdown(panel_html("Gemini Advisory", body_html), unsafe_allow_html=True)

    # 6. Coaching / Ceiling Report
    coaching = data["coaching"]
    summary = data["summary"]
    if coaching:
        coaching_items = []
        coaching_items.append(f"종합 평가: {coaching.get('coaching_summary') or coaching.get('ceiling_summary') or summary}")
        for label, key in COACHING_SECTION_KEYS:
            items = coaching.get(key)
            if isinstance(items, list) and items:
                coaching_items.extend(f"{label} · {item}" for item in items)
            elif isinstance(items, str) and items.strip():
                coaching_items.append(f"{label}: {items.strip()}")
        st.markdown(list_panel_html("저장된 코칭 리포트", coaching_items, kicker="COACHING"), unsafe_allow_html=True)
    else:
        fallback_items = [f"종합 평가: {summary}"]
        if data["strengths"]:
            fallback_items.extend(f"핵심 강점: {item}" for item in data["strengths"])
        if data["weaknesses"]:
            fallback_items.extend(f"보완점: {item}" for item in data["weaknesses"])
        st.markdown(list_panel_html("저장된 코칭 리포트", fallback_items, kicker="COACHING"), unsafe_allow_html=True)

    # Mentor reference
    if data["mentor_name"]:
        st.caption(f"멘토 참고: {data['mentor_name']}의 프로필을 보완 방향 참고용으로 선택했습니다.")

    # 7. Final Scouting Report
    report_original = data["report_original"]
    if report_original:
        with st.expander("저장된 분석 리포트 전문 보기"):
            st.markdown(report_original)

    # 8. Developer JSON (always collapsed)
    with st.expander("개발자용 저장 데이터 보기"):
        st.json({
            "env_settings": data["env"],
            "simulation_result": data["sim"],
            "structured_result": structured,
            "gemini_report": note.get("gemini_report"),
        })


def render_scouting_notes_view():
    render_game_page_title(
        "Scouting Archive",
        "저장된 스카우팅 노트 조회 · 규칙 기반 분석 결과 · 직접 입력 유망주 기록",
        kicker="MY SCOUTING NOTES",
    )

    # 노트 조회
    try:
        notes_df = get_scouting_notes(limit=50)
    except Exception as exc:
        st.error("스카우팅 노트 조회 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)
        return

    if notes_df.empty:
        st.markdown(
            empty_state_panel_html(
                "저장된 노트 없음",
                "직접 입력 유망주를 만들거나 Career Simulation / AI 리포트를 저장하면 여기에 표시됩니다.",
            ),
            unsafe_allow_html=True,
        )
        render_page_actions([
            ("🔎 유망주 검색으로 이동", "유망주 검색", "primary"),
            ("📝 새 유망주 직접 입력", "직접 입력 유망주"),
        ])
        return

    # 전체 데이터 파싱
    all_data = []
    all_notes = []
    for _, note in notes_df.iterrows():
        data = _extract_note_data(note)
        all_data.append(data)
        all_notes.append(note)

    # Archive Summary Strip
    st.markdown(_archive_strip_html(all_data), unsafe_allow_html=True)

    st.divider()

    # Filter Panel
    with st.expander("필터 · Filter", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            search_name = st.text_input("선수명 검색", placeholder="이름 입력...", key="archive_search_name")
        with col2:
            type_options = ["전체"] + list(NOTE_TYPE_LABELS.values())
            selected_type = st.selectbox("Note Type", type_options, key="archive_filter_type")
        with col3:
            entity_options = ["전체"] + list(set(ENTITY_TYPE_LABELS.values()))
            selected_entity = st.selectbox("Entity Type", entity_options, key="archive_filter_entity")
        col4, col5 = st.columns(2)
        with col4:
            only_gemini = st.checkbox("Gemini 사용 노트만", key="archive_filter_gemini")
        with col5:
            only_qualitative = st.checkbox("정성 텍스트 포함만", key="archive_filter_qual")

    # 필터링
    filtered_pairs = []
    for data, note in zip(all_data, all_notes):
        title = _note_display_title(note)
        if search_name and search_name.lower() not in title.lower():
            continue
        type_label = _safe_label(data["note_type"], NOTE_TYPE_LABELS, data["note_type"])
        if selected_type != "전체" and type_label != selected_type:
            continue
        entity_label = _safe_label(data["entity_type"], ENTITY_TYPE_LABELS, data["entity_type"])
        if selected_entity != "전체" and entity_label != selected_entity:
            continue
        if only_gemini and not data["has_gemini"]:
            continue
        if only_qualitative and not data["has_qualitative"]:
            continue
        filtered_pairs.append((data, note, title))

    if not filtered_pairs:
        st.markdown(
            empty_state_panel_html("필터 조건에 맞는 노트 없음", "필터를 조정하거나 초기화하세요."),
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<div class="game-results-heading"><h2>Notes</h2><span class="count">{len(filtered_pairs)}개</span></div>',
        unsafe_allow_html=True,
    )

    # selected note state
    if "archive_selected_idx" not in st.session_state:
        st.session_state["archive_selected_idx"] = None

    for idx, (data, note, title) in enumerate(filtered_pairs):
        is_selected = st.session_state.get("archive_selected_idx") == idx
        badges = _note_badges(data)
        note_type_label = _safe_label(data["note_type"], NOTE_TYPE_LABELS, data["note_type"])
        report_mode_label = _safe_label(data["report_mode"], REPORT_MODE_LABELS, data["report_mode"])
        entity_type_label = _safe_label(data["entity_type"], ENTITY_TYPE_LABELS, data["entity_type"])

        card_html = archive_note_card_html(
            title=title,
            saved_at=str(note.get("created_at") or "-"),
            note_type_label=note_type_label,
            entity_type_label=entity_type_label,
            report_mode_label=report_mode_label,
            growth_score=data["growth_score"],
            final_growth_score=data["final_growth_score"],
            badges=badges,
            is_selected=is_selected,
        )
        st.markdown(card_html, unsafe_allow_html=True)

        col_btn, _ = st.columns([1, 4])
        with col_btn:
            btn_label = "▼ 상세 닫기" if is_selected else "상세 보기"
            if st.button(btn_label, key=f"archive_note_btn_{idx}"):
                if is_selected:
                    st.session_state["archive_selected_idx"] = None
                else:
                    st.session_state["archive_selected_idx"] = idx
                st.rerun()

        if is_selected:
            with st.container(border=True):
                _render_note_detail(data, note)

    st.divider()
    render_page_actions([
        ("🔎 새 유망주 검색", "유망주 검색", "primary"),
        ("📝 새 유망주 직접 입력", "직접 입력 유망주"),
    ], title="다음 작업")
