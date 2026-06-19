import streamlit as st

from analysis_helpers import generate_mentor_guide, parse_json_field, safe_float
from components.badges import source_badge_html
from components.cards import empty_state_panel_html, game_alert_html, panel_html, stat_grid_html
from components.layout import render_game_page_title
from components.player_header import render_player_header
from manual_prospect_helpers import (
    filter_mentor_candidates_by_age,
    manual_player_profile_panel_inputs,
    manual_similarity_candidates,
)
from player_coverage import build_data_coverage
from services.db import get_similar_players, query_one
from ui_components import render_page_actions


def get_profile_by_profile_id(profile_id):
    return query_one("select * from player_profiles where profile_id = %s limit 1", (profile_id,))


def _mentor_fit_label(similarity):
    score = safe_float(similarity, None)
    if score is None:
        return "판정 보류"
    if score >= 0.92:
        return "매우 높은 적합도"
    if score >= 0.84:
        return "높은 적합도"
    if score >= 0.75:
        return "참고 가능한 적합도"
    return "보조 참고"


def _mentor_card(row, guide, is_selected=False, used_fallback=False):
    profile_id = row.get("profile_id")
    similarity = safe_float(row.get("similarity"), None)
    if similarity is None:
        sim_pct = 0
        sim_text = "-"
    elif similarity > 1:
        sim_pct = max(0.0, min(99.9, similarity))
        sim_text = f"{sim_pct:.1f}%"
    else:
        sim_pct = max(0.0, min(99.9, similarity * 100))
        sim_text = f"{sim_pct:.0f}%"
    selected_class = " selected" if is_selected else ""
    fallback_line = (
        "<div class='game-muted'>기본 나이 조건을 만족하는 후보가 부족해 가장 가까운 선배형 후보까지 함께 표시했습니다.</div>"
        if used_fallback
        else ""
    )
    badges = (
        source_badge_html("선배 멘토 후보", "ok")
        + source_badge_html(_mentor_fit_label(similarity), "neutral")
    )
    return f"""
    <div class="game-mentor-card{selected_class}">
        <h4>{row.get('name') or '-'}</h4>
        <div class="game-muted">{row.get('age') or '-'}세 · {row.get('position') or '-'} · {row.get('club') or '-'}</div>
        <div class="game-card-row">{badges}</div>
        <div class="game-score-bar">
            <div class="bar-label"><span>멘토 적합도</span><span class="bar-value">{sim_text}</span></div>
            <div class="game-progress"><span style="--value:{sim_pct}%"></span></div>
        </div>
        <div class="game-note-section">
            <div class="game-note-section-label">왜 이 선수를 멘토로 보는가</div>
            <div>{guide.get('similarity_reason') or guide.get('mentor_summary') or '-'}</div>
        </div>
        <div class="game-note-section">
            <div class="game-note-section-label">이 선수에게서 배울 점</div>
            <div>{guide.get('improvement_points') or '-'}</div>
        </div>
        <div class="game-note-section">
            <div class="game-note-section-label">훈련 활용법</div>
            <div>{guide.get('training_recommendation') or '-'}</div>
        </div>
        <div class="game-note-section">
            <div class="game-note-section-label">주의할 커리어 리스크</div>
            <div>{guide.get('career_advice') or '-'}</div>
        </div>
        {fallback_line}
    </div>
    """


def _sort_mentor_records(records):
    return sorted(
        records,
        key=lambda row: (
            safe_float(row.get("age"), 0) or 0,
            safe_float(row.get("similarity"), 0) or 0,
        ),
        reverse=True,
    )


def _render_mentor_section(player, profile, mentor_records, used_fallback):
    mentor_records = _sort_mentor_records(mentor_records)
    st.markdown(
        '<div class="game-results-heading">'
        f"<h2>멘토 후보</h2><span class='count'>{len(mentor_records)}명</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption("멘토 후보는 현재 선수보다 나이와 경험이 앞선 선배형 후보를 우선 보여줍니다. 능력 패턴과 포지션을 함께 비교해 훈련 참고 방향을 정리합니다.")

    if not mentor_records:
        st.markdown(
            empty_state_panel_html(
                "멘토 후보 없음",
                "현재 조건에 맞는 멘토 후보를 찾지 못했습니다. 비슷한 포지션과 능력치 패턴을 가진 경험 많은 선수가 충분하지 않기 때문입니다. 다른 선수를 선택하거나 Scouting Board에서 다시 선택해보세요.",
            ),
            unsafe_allow_html=True,
        )
        render_page_actions([
            ("Scouting Board로 돌아가기", "유망주 검색", "primary"),
            ("커리어 시뮬레이션으로 이동", "커리어 시뮬레이션"),
        ])
        return {}

    selected_attrs = parse_json_field(profile.get("attributes_jsonb")) if profile else {}
    current_mentor_id = st.session_state.get("selected_mentor_profile_id")
    mentor_rows = {}

    for row in mentor_records:
        profile_id = row.get("profile_id")
        mentor_rows[str(profile_id)] = row
        try:
            candidate_profile = get_profile_by_profile_id(profile_id)
        except Exception:
            candidate_profile = None
        candidate_attrs = parse_json_field(candidate_profile.get("attributes_jsonb")) if candidate_profile else {}
        guide = generate_mentor_guide(player, row, selected_attrs, candidate_attrs)
        is_selected = str(profile_id) == str(current_mentor_id) if current_mentor_id else False
        st.markdown(_mentor_card(row, guide, is_selected=is_selected, used_fallback=used_fallback), unsafe_allow_html=True)

        col_a, _ = st.columns([1, 3])
        with col_a:
            if st.button("멘토 선택", key=f"select_mentor_{profile_id}", type="primary" if is_selected else "secondary"):
                st.session_state["selected_mentor_profile_id"] = profile_id
                st.session_state["selected_mentor_name"] = row.get("name")
                st.session_state["mentor_summary"] = guide.get("mentor_summary", "")
                st.rerun()

    return mentor_rows


def _render_selected_mentor_panel(player, profile, mentor_rows):
    selected_id = st.session_state.get("selected_mentor_profile_id")
    if not selected_id:
        st.info("멘토를 선택하면 Career Simulation과 Report에서 참고할 멘토 가이드가 저장됩니다.")
        return

    mentor_row = mentor_rows.get(str(selected_id))
    try:
        mentor_profile = get_profile_by_profile_id(selected_id)
    except Exception:
        mentor_profile = None
    if mentor_row is None:
        mentor_row = mentor_profile or {"profile_id": selected_id, "name": st.session_state.get("selected_mentor_name")}

    selected_attrs = parse_json_field(profile.get("attributes_jsonb")) if profile else {}
    mentor_attrs = parse_json_field(mentor_profile.get("attributes_jsonb")) if mentor_profile else {}
    guide = generate_mentor_guide(player, mentor_row, selected_attrs, mentor_attrs, st.session_state.get("simulation_result"))
    st.session_state["mentor_summary"] = guide.get("mentor_summary", "")
    mentor_name = st.session_state.get("selected_mentor_name") or mentor_row.get("name") or "-"

    body = (
        stat_grid_html(
            [
                ("멘토", mentor_name),
                ("나이", f"{mentor_row.get('age') or '-'}세"),
                ("포지션", mentor_row.get("position") or "-"),
            ]
        )
        + f'<div class="game-note-section"><div class="game-note-section-label">선정 이유</div><div>{guide.get("similarity_reason", "-")}</div></div>'
        + f'<div class="game-note-section"><div class="game-note-section-label">훈련에 적용할 점</div><div>{guide.get("training_recommendation", "-")}</div></div>'
        + f'<div class="game-note-section"><div class="game-note-section-label">다음 단계에서 쓰이는 방식</div><div>선택한 멘토 요약은 Report의 멘토 가이드와 선택 호출형 보조 추천 입력으로 전달됩니다. Growth/Ceiling 점수 자체는 바꾸지 않습니다.</div></div>'
    )
    st.markdown(panel_html(f"선택된 멘토 · {mentor_name}", body, kicker="MENTOR GUIDE"), unsafe_allow_html=True)
    render_page_actions(
        [
            ("커리어 시뮬레이션으로 이동", "커리어 시뮬레이션", "primary"),
            ("분석 리포트 초안 생성", "AI 스카우팅 리포트"),
            ("Player Dossier로 돌아가기", "유망주 통합 분석"),
        ],
        title="다음 단계",
    )


def _render_similarity_reference(all_records):
    with st.expander("내부 유사도 참고 보기"):
        st.caption("이 목록은 멘토 후보 산정에 사용한 내부 비교 결과입니다. 사용자 판단의 중심은 위의 멘토 가이드입니다.")
        for row in all_records[:30]:
            st.write(f"{row.get('name')} · {row.get('age')}세 · 적합도 {row.get('similarity')}")


def render_manual_prospect_mentors(manual_player):
    manual_attributes = st.session_state.get("manual_attributes") or {}
    _is_scouting_board_pick = bool(manual_player.get("estimated_from_player_id")) and manual_player.get("data_mode") == "full_data"
    candidate_pool = manual_similarity_candidates(manual_player, manual_attributes, limit=200)
    candidates, used_fallback = filter_mentor_candidates_by_age(
        candidate_pool,
        manual_player.get("age"),
        min_results=1,
    )
    candidates = candidates[:12]
    if not candidates:
        st.markdown(
            empty_state_panel_html(
                "멘토 후보 없음",
                "현재 DB에서 이 선수와 비슷한 스타일의 경험 많은 선배형 후보를 찾지 못했습니다. "
                "포지션이나 능력치가 다른 선수를 다시 선택하거나, 커리어 시뮬레이션으로 바로 이동해 분석을 이어갈 수 있습니다.",
            ),
            unsafe_allow_html=True,
        )
        render_page_actions([
            ("Scouting Board로 돌아가기", "유망주 검색", "primary"),
            ("커리어 시뮬레이션으로 이동", "커리어 시뮬레이션"),
        ])
        return

    current_mentor_id = st.session_state.get("selected_mentor_profile_id")
    for mentor in _sort_mentor_records(candidates):
        profile_id = mentor.get("profile_id")
        is_selected = str(profile_id) == str(current_mentor_id) if current_mentor_id else False
        guide = {
            "similarity_reason": f"{mentor.get('name')}은(는) 나이와 경험이 앞선 선배형 후보이며, 입력한 능력치와 겹치는 강점이 있습니다. {mentor.get('common_strengths')}",
            "improvement_points": mentor.get("difference_hint"),
            "training_recommendation": f"{mentor.get('difference_hint')} 이 차이를 줄이는 방향으로 개인 훈련과 역할 숙련도를 점검하세요.",
            "career_advice": (
                "Scouting Board에서 선택한 선수로, DB 시장가치와 출전 기록을 기반으로 분석되었습니다. 멘토는 점수 계산용이 아니라 훈련 방향을 정리하는 참고 기준입니다."
                if _is_scouting_board_pick else
                "직접 입력한 능력치와 환경 설정 기반 분석입니다. 실제 경기/리그 데이터는 별도 확인이 필요합니다. 멘토는 점수 계산용이 아니라 훈련 방향을 정리하는 참고 기준입니다."
            ),
            "mentor_summary": f"{mentor.get('name')}의 강점 패턴과 성장 후 역할을 훈련 참고점으로 사용합니다.",
        }
        st.markdown(_mentor_card(mentor, guide, is_selected=is_selected, used_fallback=used_fallback), unsafe_allow_html=True)
        if st.button("멘토 선택", key=f"manual_prospect_select_mentor_{profile_id}", type="primary" if is_selected else "secondary"):
            st.session_state["selected_mentor_profile_id"] = profile_id
            st.session_state["selected_mentor_name"] = mentor.get("name")
            st.session_state["mentor_summary"] = guide["mentor_summary"]
            st.session_state["nav_page_request"] = "커리어 시뮬레이션"
            st.rerun()

    render_page_actions(
        [
            ("커리어 시뮬레이션으로 이동", "커리어 시뮬레이션", "primary"),
            ("분석 리포트 초안 생성", "AI 스카우팅 리포트"),
        ]
    )


def render_legend_matching_view(player, profile, ctx):
    render_game_page_title(
        "Mentor Matching Lab",
        "나이와 경험이 앞선 선배형 후보를 찾아, 어떤 훈련 방향과 커리어 판단을 참고할지 정리합니다.",
        kicker="MENTOR ANALYSIS",
    )

    manual_player = st.session_state.get("manual_player") if st.session_state.get("selected_entity_type") == "manual_prospect" else None
    if manual_player:
        panel_player, panel_profile = manual_player_profile_panel_inputs(manual_player)
        _is_sb_pick = bool(manual_player.get("estimated_from_player_id")) and manual_player.get("data_mode") == "full_data"
        render_player_header(panel_player, panel_profile, entity_type="scouting_board_pick" if _is_sb_pick else "manual_prospect")
        return render_manual_prospect_mentors(manual_player)

    render_player_header(player, profile, entity_type=st.session_state.get("selected_entity_type"))

    if ctx.get("fallback_note"):
        st.markdown(game_alert_html("데이터 연결 안내", ctx["fallback_note"], "info"), unsafe_allow_html=True)

    if profile is None or profile.get("profile_id") is None:
        st.warning("멘토 후보를 계산하려면 능력치 프로필이 있는 선수가 필요합니다. Scouting Board에서 Full Data 선수를 선택해주세요.")
        render_page_actions([("Scouting Board로 이동", "유망주 검색", "primary")])
        return

    if not profile.get("style_vector"):
        st.warning("멘토 후보를 계산할 비교 데이터가 없습니다. Scouting Board에서 Full Data 선수를 선택해주세요.")
        render_page_actions([("Scouting Board로 이동", "유망주 검색", "primary")])
        return

    try:
        similar_df = get_similar_players(profile["profile_id"])
    except Exception as exc:
        st.error("멘토 후보 조회 중 오류가 발생했습니다.")
        with st.expander("개발자 확인용 오류"):
            st.exception(exc)
        return

    all_records = similar_df.to_dict("records")
    mentor_records, used_fallback = filter_mentor_candidates_by_age(
        all_records,
        profile.get("age"),
        exclude_ids=[profile.get("profile_id")],
    )
    mentor_rows = _render_mentor_section(player, profile, mentor_records, used_fallback)
    st.divider()
    _render_selected_mentor_panel(player, profile, mentor_rows)
    _render_similarity_reference(all_records)
