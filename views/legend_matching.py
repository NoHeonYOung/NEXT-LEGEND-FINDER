import streamlit as st

from analysis_helpers import (
    generate_mentor_guide,
    generate_similarity_reason,
    parse_json_field,
    safe_float,
)
from manual_prospect_helpers import (
    filter_mentor_candidates_by_age,
    manual_player_profile_panel_inputs,
    manual_similarity_candidates,
)
from player_coverage import build_data_coverage
from services.db import get_similar_players, query_one
from ui_components import render_page_actions, render_player_profile_panel


def get_profile_by_profile_id(profile_id):
    return query_one("select * from player_profiles where profile_id = %s limit 1", (profile_id,))


def render_mentor_guide(selected_player, selected_profile, mentor_row, mentor_profile):
    selected_attrs = parse_json_field(selected_profile.get("attributes_jsonb")) if selected_profile else {}
    mentor_attrs = parse_json_field(mentor_profile.get("attributes_jsonb")) if mentor_profile else {}
    guide = generate_mentor_guide(selected_player, mentor_row, selected_attrs, mentor_attrs, st.session_state.get("simulation_result"))
    st.session_state["mentor_summary"] = guide["mentor_summary"]
    st.subheader("멘토링 가이드")
    st.info("현재 가이드는 실제 레전드 성장 로그가 아니라, 선택 유망주와 유사 선수 후보의 FM 기반 proxy 능력치 차이를 바탕으로 생성한 프로토타입 조언입니다.")
    st.markdown(f"""<div class="scout-panel"><h3 style="margin-top:0;">A. 왜 이 선수가 유사 후보인가</h3><p>{guide['similarity_reason']}</p><h3>B. 후보 선수와 비교했을 때 보완할 점</h3><p>{guide['improvement_points']}</p><h3>C. 추천 훈련 방향</h3><p>{guide['training_recommendation']}</p><h3>D. 커리어 선택 조언</h3><p>{guide['career_advice']}</p><h3>E. 분석 리포트 초안으로 넘기기</h3><p>이 멘토링 내용을 스카우팅 분석 리포트 초안에 반영할 수 있습니다.</p></div>""", unsafe_allow_html=True)


def render_manual_prospect_mentors(manual_player):
    manual_attributes = st.session_state.get("manual_attributes") or {}
    candidates = manual_similarity_candidates(manual_player, manual_attributes, limit=10)
    candidates, used_fallback = filter_mentor_candidates_by_age(candidates, manual_player.get("age"))

    if used_fallback:
        st.info("조건을 완화해 표시한 후보입니다.")

    if not candidates:
        st.info("유사 선수 후보가 없습니다.")
        render_page_actions([
            ("📈 커리어 시뮬레이션으로 이동", "커리어 시뮬레이션", "primary"),
            ("📝 My Scouting Notes로 이동", "내 스카우팅 노트"),
        ], title="다음 단계")
        return

    for mentor in candidates:
        st.markdown(
            f"""
            <div class="scout-panel">
                <h3 style="margin-top:0;">{mentor['name']}</h3>
                <div class="badge-row">
                    <span class="scout-badge">나이 {mentor.get('age') or '-'}</span>
                    <span class="scout-badge">{mentor.get('position') or '-'}</span>
                    <span class="scout-badge">{mentor.get('club') or '-'}</span>
                    <span class="scout-badge">유사도 {mentor.get('similarity', '-')}</span>
                </div>
                <p><b>공통 강점</b><br>{mentor.get('common_strengths', '-')}</p>
                <p><b>주요 차이점</b><br>{mentor.get('difference_hint', '-')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("멘토로 선택", key=f"manual_prospect_select_mentor_{mentor['profile_id']}"):
            st.session_state["selected_mentor_profile_id"] = mentor['profile_id']
            st.session_state["selected_mentor_name"] = mentor['name']
            st.session_state["mentor_summary"] = (
                f"{mentor['name']}은(는) 현재 직접 입력 능력치와 유사한 강점을 보이는 후보입니다. "
                f"공통 강점: {mentor['common_strengths']} / 차이점: {mentor['difference_hint']}"
            )
            st.success(f"{mentor['name']} 선수를 멘토 후보로 선택했습니다.")

    selected_mentor_name = st.session_state.get("selected_mentor_name")
    selected_mentor_profile_id = st.session_state.get("selected_mentor_profile_id")
    if selected_mentor_name and any(str(c['profile_id']) == str(selected_mentor_profile_id) for c in candidates):
        mentor_summary = st.session_state.get("mentor_summary")
        st.markdown(
            f"<div class='scout-panel'><b>멘토 기반 성장 가이드</b><br>선택된 멘토: {selected_mentor_name}<br>{mentor_summary or '선택한 멘토의 성장 가이드를 반영했습니다.'}</div>",
            unsafe_allow_html=True,
        )

    render_page_actions([
        ("📈 커리어 시뮬레이션으로 이동", "커리어 시뮬레이션", "primary"),
        ("📄 스카우팅 리포트 생성", "AI 스카우팅 리포트"),
    ])


def render_legend_matching_view(player, profile, ctx):
    """Legend Matching 화면 본문. app.py의 render_legend_matching()이
    선택 선수/프로필/선택 컨텍스트(require_selected_player/selected_profile/
    resolve_selected_player_context)를 조회한 뒤 이 함수에 전달한다
    (선택 로직은 app.py에 그대로 유지)."""
    st.title("유사 선수 후보")
    manual_player = st.session_state.get("manual_player") if st.session_state.get("selected_entity_type") == "manual_prospect" else None
    if manual_player:
        panel_player, panel_profile = manual_player_profile_panel_inputs(manual_player)
        render_player_profile_panel(panel_player, panel_profile)
    else:
        render_player_profile_panel(player, profile)
    st.info("현재 매칭은 실제 10x10 Grid 데이터가 아니라 FM 기반 proxy style_vector(24차원)를 활용한 pgvector 유사 선수 후보입니다. 향후 실제 레전드 성장 궤적 데이터와 10x10 Grid 데이터가 확보되면 고도화 예정입니다.")
    if ctx["fallback_note"]:
        st.info(ctx["fallback_note"])

    if manual_player:
        return render_manual_prospect_mentors(manual_player)

    if profile is None or profile.get("profile_id") is None:
        coverage = build_data_coverage(player, None)
        st.warning(
            "FM profile 또는 style_vector가 없어 유사 선수 후보를 계산할 수 없습니다. "
            "유사 선수 분석은 FM 기반 style_vector가 있는 선수에게만 제공됩니다."
        )
        if coverage["missing_reasons"]:
            st.caption("부족한 데이터: " + ", ".join(coverage["missing_reasons"]))
        render_page_actions([
            ("🔍 분석 가능한 선수 검색", "유망주 검색", "primary"),
            ("✏️ 직접 입력 유망주로 보완", "직접 입력 유망주"),
            ("📈 커리어 시뮬레이션으로 이동", "커리어 시뮬레이션"),
        ], title="FM 프로필 없음 · 다음 단계")
        return

    # style_vector가 없으면 pgvector 유사도 계산이 불가능하다.
    if not profile.get("style_vector"):
        coverage = build_data_coverage(player, profile)
        st.warning(
            "FM profile 또는 style_vector가 없어 유사 선수 후보를 계산할 수 없습니다. "
            "이 선수의 style_vector가 없어 pgvector 유사도 계산을 수행할 수 없습니다."
        )
        if coverage["missing_reasons"]:
            st.caption("부족한 데이터: " + ", ".join(coverage["missing_reasons"]))
        render_page_actions([
            ("🔍 분석 가능한 선수 검색", "유망주 검색", "primary"),
            ("📈 커리어 시뮬레이션으로 이동", "커리어 시뮬레이션"),
        ], title="style_vector 없음 · 다음 단계")
        return

    try:
        similar = get_similar_players(profile["profile_id"])
    except Exception as exc:
        st.error("유사 선수 후보 조회 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)
        return
    similar_records, used_fallback = filter_mentor_candidates_by_age(
        similar.to_dict("records"),
        profile.get("age"),
        exclude_ids=[profile.get("profile_id")],
    )
    if used_fallback:
        st.info("조건을 완화해 표시한 후보입니다.")
    if not similar_records:
        st.info("유사 선수 후보가 없습니다.")
        return
    mentor_rows = {}
    for row in similar_records:
        profile_id = row.get("profile_id")
        mentor_rows[str(profile_id)] = row
        try:
            candidate_profile = get_profile_by_profile_id(profile_id)
        except Exception:
            candidate_profile = None
            st.error(f"{row.get('name') or '후보 선수'}의 프로필을 DB에서 조회하는 중 오류가 발생했습니다.")
        selected_attrs = parse_json_field(profile.get("attributes_jsonb"))
        candidate_attrs = parse_json_field(candidate_profile.get("attributes_jsonb")) if candidate_profile else {}
        reason = generate_similarity_reason(player, row, selected_attrs, candidate_attrs)
        guide = generate_mentor_guide(player, row, selected_attrs, candidate_attrs)
        similarity = safe_float(row.get("similarity"), None)
        similarity_text = f"{similarity:.4f}" if similarity is not None else "-"
        st.markdown(f"""<div class="scout-panel"><h3 style="margin-top:0;">{row.get('name') or '-'}</h3><div class="badge-row"><span class="scout-badge">나이 {row.get('age') if row.get('age') is not None else '-'}</span><span class="scout-badge">{row.get('position') or '-'}</span><span class="scout-badge">{row.get('club') or '-'}</span><span class="scout-badge">유사도 {similarity_text}</span></div><p><b>공통 강점</b><br>{reason['common_strengths']}</p><p><b>주요 차이점</b><br>{reason['differences']}</p><p><b>전술적 해석</b><br>{reason['tactical_interpretation']}</p><p><b>유사 후보 선정 이유</b><br>{reason['similarity_reason']}</p></div>""", unsafe_allow_html=True)
        if st.button("멘토로 선택", key=f"select_mentor_{profile_id}"):
            st.session_state["selected_mentor_profile_id"] = profile_id
            st.session_state["selected_mentor_name"] = row.get("name")
            st.session_state["mentor_summary"] = guide["mentor_summary"]
            st.success(f"{row.get('name')} 선수를 멘토 후보로 선택했습니다.")
    selected_mentor_profile_id = st.session_state.get("selected_mentor_profile_id")
    if selected_mentor_profile_id:
        mentor_row = mentor_rows.get(str(selected_mentor_profile_id))
        try:
            mentor_profile = get_profile_by_profile_id(selected_mentor_profile_id)
        except Exception:
            st.error("선택한 멘토 프로필을 DB에서 조회하는 중 오류가 발생했습니다.")
            return
        if mentor_row is None:
            mentor_row = mentor_profile or {"profile_id": selected_mentor_profile_id, "name": st.session_state.get("selected_mentor_name")}
        render_mentor_guide(player, profile, mentor_row, mentor_profile)
        render_page_actions([
            ("📈 커리어 시뮬레이션으로 이동", "커리어 시뮬레이션", "primary"),
            ("📄 스카우팅 리포트 생성", "AI 스카우팅 리포트"),
        ])
