import streamlit as st

from analysis_helpers import (
    generate_mentor_guide,
    generate_similarity_reason,
    parse_json_field,
    safe_float,
)
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
    st.markdown(f"""<div class="scout-panel"><h3 style="margin-top:0;">A. 왜 이 선수가 유사 후보인가</h3><p>{guide['similarity_reason']}</p><h3>B. 후보 선수와 비교했을 때 보완할 점</h3><p>{guide['improvement_points']}</p><h3>C. 추천 훈련 방향</h3><p>{guide['training_recommendation']}</p><h3>D. 커리어 선택 조언</h3><p>{guide['career_advice']}</p><h3>E. AI 리포트로 넘기기</h3><p>이 멘토링 내용을 AI 스카우팅 리포트 초안에 반영할 수 있습니다.</p></div>""", unsafe_allow_html=True)


def render_legend_matching_view(player, profile, ctx):
    """Legend Matching 화면 본문. app.py의 render_legend_matching()이
    선택 선수/프로필/선택 컨텍스트(require_selected_player/selected_profile/
    resolve_selected_player_context)를 조회한 뒤 이 함수에 전달한다
    (선택 로직은 app.py에 그대로 유지)."""
    st.title("유사 선수 후보")
    render_player_profile_panel(player, profile)
    st.info("현재 매칭은 실제 10x10 Grid 데이터가 아니라 FM 기반 proxy style_vector(24차원)를 활용한 pgvector 유사 선수 후보입니다. 향후 실제 레전드 성장 궤적 데이터와 10x10 Grid 데이터가 확보되면 고도화 예정입니다.")
    if ctx["fallback_note"]:
        st.info(ctx["fallback_note"])
    if profile is None or profile.get("profile_id") is None:
        st.warning("FM 프로필이 없어 유사 선수 후보를 조회할 수 없습니다.")
        render_page_actions([
            ("📈 커리어 시뮬레이션으로 이동", "커리어 시뮬레이션", "primary"),
            ("📝 My Scouting Notes로 이동", "내 스카우팅 노트"),
        ], title="FM 프로필 없음 · 다음 단계")
        return
    try:
        similar = get_similar_players(profile["profile_id"])
    except Exception as exc:
        st.error("유사 선수 후보 조회 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)
        return
    if similar.empty:
        st.info("유사 선수 후보가 없습니다.")
        return
    mentor_rows = {}
    for row in similar.to_dict("records"):
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
