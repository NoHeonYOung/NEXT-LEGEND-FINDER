import streamlit as st

from services.db import get_distinct_positions, search_players_with_modes, show_selected_player_banner


def render_prospect_search():
    st.title("유망주 검색")
    st.caption("분석할 유망주를 검색하고 선택합니다. 선택한 후보는 다른 화면에서 FM/Transfermarkt 매칭 상태와 함께 재사용됩니다.")
    st.info("유망주 기준: FM 데이터 기준 만 23세 이하. 후보는 matched / fm_profile_only / transfermarkt_only 상태를 함께 확인할 수 있습니다.")

    max_age = st.slider("최대 나이", min_value=16, max_value=30, value=23, step=1)
    try:
        positions = get_distinct_positions(max_age=max_age)
    except Exception:
        positions = ["All"]

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        keyword = st.text_input("선수 이름", placeholder="예: Bellingham, Yamal, Son")
    with c2:
        position = st.selectbox("포지션", positions)
    with c3:
        nationality = st.text_input("국적", placeholder="예: Korea")
    with c4:
        club = st.text_input("소속팀", placeholder="예: Dortmund")

    try:
        results = search_players_with_modes(keyword=keyword, position=position, nationality=nationality, club=club, max_age=max_age)
    except Exception as exc:
        st.error("선수 검색 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)
        return

    if results.empty:
        st.info("검색 결과가 없습니다. 현재 검색은 candidate pool에서 matched / FM-only / Transfermarkt-only 후보를 함께 확인합니다.")
        return

    st.subheader("검색 결과")
    st.caption("표시된 후보는 DB의 매칭 상태에 따라 통합 분석 가능 여부가 다를 수 있습니다.")

    for _, row in results.iterrows():
        mode = row.get("search_mode") or "matched"
        label = row.get("source_label") or "후보"
        name = row.get("name") or "-"
        age = row.get("age") if row.get("age") not in (None, "") else "-"
        club_name = row.get("current_club_name") or "-"
        position_name = row.get("position") or "-"
        market_value = "-"
        player_id = row.get("player_id")
        profile_id = row.get("profile_id")

        try:
            from services.db import money
            market_value = money(row.get("market_value_in_eur")) if row.get("market_value_in_eur") not in (None, "") else "-"
        except Exception:
            market_value = "-"

        st.markdown(
            f"""
            <div class="scout-panel">
                <h3 style="margin-top:0;">{name}</h3>
                <div class="badge-row">
                    <span class="scout-badge">모드 {mode}</span>
                    <span class="scout-badge">{label}</span>
                    <span class="scout-badge">나이 {age}</span>
                    <span class="scout-badge">{position_name}</span>
                </div>
                <p style="margin-bottom:0;"><b>소속팀</b> {club_name} · <b>현재 시장가치</b> {market_value}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("이 후보 선택", key=f"select_mode_candidate_{mode}_{player_id or profile_id or row.name}", type="primary"):
            st.session_state["selected_player_id"] = int(player_id) if player_id not in (None, "") else None
            st.session_state["selected_profile_id"] = int(profile_id) if profile_id not in (None, "") else None
            st.session_state["selected_entity_type"] = mode
            st.session_state["selected_player_name"] = name
            st.session_state["selected_search_mode"] = mode

            for key in [
                "selected_mentor_profile_id",
                "selected_mentor_name",
                "mentor_summary",
                "manual_selected_mentor_profile_id",
                "manual_selected_mentor_name",
                "manual_mentor_summary",
                "manual_analysis_result",
                "manual_report_text",
                "env_settings",
                "simulation_result",
                "generated_report_sections",
                "generated_report",
            ]:
                st.session_state.pop(key, None)

            st.success(f"{name} 후보를 선택했습니다. 현재 모드: {mode}")
            st.info("홈/분석/유사 선수 화면에서 선택 결과를 이어서 확인할 수 있습니다.")

    show_selected_player_banner()
