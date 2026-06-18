from analysis_helpers import format_percent, parse_json_field, readable_setting
from manual_prospect_helpers import safe_text
from scouting_note_payload import extract_structured_note_result
from services.db import get_scouting_notes
from ui_components import render_page_actions
import streamlit as st


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

COACHING_SECTION_KEYS = [
    ("추천 훈련 방향", "training_directions"),
    ("기대 장점", "expected_benefits"),
    ("소홀히 했을 때의 단점", "neglect_risks"),
    ("리스크 경고", "risk_warnings"),
    ("추천 커리어 전략", "career_strategy"),
]


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
    report = note.get("gemini_report") if hasattr(note, "get") else None
    if isinstance(report, str) and report.strip():
        return report.strip()
    generated = structured.get("generated_report_text") if isinstance(structured, dict) else None
    return generated.strip() if isinstance(generated, str) else ""


def note_summary_text(note):
    env = parse_json_field(note.get("env_settings"))
    sim = parse_json_field(note.get("simulation_result"))
    return (
        f"훈련 강도 {readable_setting('training_intensity', env.get('training_intensity', 0))}, "
        f"출전 기회 {readable_setting('playing_time_opportunity', env.get('playing_time_opportunity', 0))}, "
        f"커리어 선택 {readable_setting('career_choice', env.get('career_choice'))}, "
        f"성공 가능성 {format_percent(sim.get('prototype_success_probability'))}"
    )


def note_display_title(note):
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

    return "이름 없는 직접 입력 노트"


_PROVENANCE_TABLE = """| 항목 | 출처 |
|---|---|
| 선수 기본 정보 | DB |
| 시장가치/출전 기록 | DB |
| 능력치/멘탈 속성 | FM proxy profile |
| 성장 점수 | rule-based Growth/Ceiling Model |
| 정성 텍스트 근거 | 입력 없음 |
| Gemini 분석 | 미사용 |
"""


def render_scouting_notes_view():
    st.title("My Scouting Notes")
    st.info(
        "이 화면은 저장된 스카우팅 노트(분석 리포트 초안, 커리어 시뮬레이션, 직접 입력 유망주 분석)를 모아보는 "
        "화면입니다. 실제 Gemini API 호출은 없으며, 저장 시점의 규칙 기반/템플릿 결과를 그대로 보여줍니다."
    )
    with st.expander("분석 근거 안내"):
        st.caption(
            "저장된 노트의 분석은 DB에 저장된 선수 기본 정보, 시장가치/출전 기록, "
            "FM 기반 능력치 및 멘탈 속성 proxy, Growth/Ceiling 규칙 모델을 바탕으로 생성되었습니다. "
            "뉴스 기사, 감독 인터뷰, 스카우팅 텍스트 기반 정성 분석은 아직 입력되지 않았습니다."
        )
        st.markdown(_PROVENANCE_TABLE)
    render_page_actions([
        ("📝 새 유망주 직접 입력", "직접 입력 유망주", "primary"),
        ("🔎 유망주 검색으로 이동", "유망주 검색"),
    ], title="직접 입력 유망주를 만들고 싶다면")

    st.divider()
    st.subheader("저장된 노트 조회")
    try:
        notes = get_scouting_notes(limit=20)
    except Exception as exc:
        st.error("스카우팅 노트 조회 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)
        return

    if notes.empty:
        st.info("현재 저장된 노트가 없습니다. 직접 입력 유망주를 만들거나 기존 저장 리포트를 확인할 수 있습니다.")
        render_page_actions([
            ("🔎 유망주 검색으로 이동", "유망주 검색", "primary"),
            ("📝 새 유망주 직접 입력", "직접 입력 유망주"),
        ])
        return

    for _, note in notes.iterrows():
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
        title = note_display_title(note)
        stored_summary = stored_explanation.get("summary") if isinstance(stored_explanation, dict) else None
        summary = safe_text(coaching.get("coaching_summary") or stored_summary or sim.get("overall_summary"), note_summary_text(note))
        strengths = sim.get("strengths") if isinstance(sim, dict) else []
        weaknesses = sim.get("weaknesses") if isinstance(sim, dict) else []
        if not strengths and isinstance(stored_explanation, dict):
            strengths = stored_explanation.get("strengths") or []
        if not weaknesses and isinstance(stored_explanation, dict):
            weaknesses = stored_explanation.get("risks") or []
        mentor_name = env.get("selected_mentor_name")
        growth_score = stored_growth.get("growth_score", sim.get("prototype_growth_score", "-"))
        ceiling_model = stored_growth.get("ceiling_model") if isinstance(stored_growth.get("ceiling_model"), dict) else {}
        final_growth_score = ceiling_model.get("final_growth_score", "-")
        injury_risk = sim.get("prototype_injury_risk")
        report_original = saved_report_original(note, structured)
        note_type = env.get("note_type") or "legacy_note"
        source = env.get("source") or "legacy"
        entity_type = env.get("entity_type") or ("manual_note" if manual_player else "db_player")
        note_type_label = saved_note_label(note_type, NOTE_TYPE_LABELS, "저장된 분석")
        source_label = saved_note_label(source, SOURCE_LABELS, "저장 출처 정보 없음")
        entity_type_label = saved_note_label(entity_type, ENTITY_TYPE_LABELS, "선수 유형 정보 없음")

        st.markdown(
            f"""
            <div class="scout-panel">
                <h3 style="margin-top:0;">{title}</h3>
                <div class="muted">저장일 {note.get('created_at')}</div>
                <div class="badge-row">
                    <span class="scout-badge">{note_type_label}</span>
                    <span class="scout-badge">{source_label}</span>
                    <span class="scout-badge">{entity_type_label}</span>
                </div>
                <p><b>나이 / 포지션 / 소속팀 / 국적</b><br>
                {safe_text(player_snapshot.get('age'), '-') if isinstance(player_snapshot, dict) else '-'}세 ·
                {safe_text(player_snapshot.get('position'), '-') if isinstance(player_snapshot, dict) else '-'} ·
                {safe_text(player_snapshot.get('club'), '-') if isinstance(player_snapshot, dict) else '-'} ·
                {safe_text(player_snapshot.get('nationality'), '-') if isinstance(player_snapshot, dict) else '-'}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        score_columns = st.columns(3)
        score_columns[0].metric("기본 성장 점수", growth_score)
        score_columns[1].metric("시나리오 반영 성장 점수", final_growth_score)
        score_columns[2].metric("부상 리스크", format_percent(injury_risk))

        st.write("### 저장된 코칭 리포트")
        if coaching:
            for label, content in saved_coaching_sections(coaching, summary):
                st.write(f"#### {label}")
                if isinstance(content, list):
                    for item in content:
                        st.write("- " + str(item))
                else:
                    st.write(content)
        else:
            st.write("#### 종합 평가")
            st.write(summary)
            if strengths:
                st.write("#### 핵심 강점")
                for item in strengths:
                    st.write("- " + str(item))
            if weaknesses:
                st.write("#### 보완점")
                for item in weaknesses:
                    st.write("- " + str(item))

        if mentor_name:
            st.caption(f"멘토 참고: {mentor_name}의 프로필을 보완 방향 참고용으로 선택했습니다.")

        if report_original:
            with st.expander("상세 리포트 원문 보기"):
                st.caption("Gemini API 생성물이 아닌, 저장 시점의 규칙 기반 또는 템플릿 리포트 원문입니다.")
                st.markdown(report_original)

        with st.expander("개발자용 저장 데이터 보기"):
            st.json({"env_settings": env, "simulation_result": sim, "structured_result": structured, "gemini_report": note.get("gemini_report")})

    render_page_actions([
        ("🔎 새 유망주 검색", "유망주 검색", "primary"),
        ("📝 새 유망주 직접 입력", "직접 입력 유망주"),
    ], title="다음 작업")
