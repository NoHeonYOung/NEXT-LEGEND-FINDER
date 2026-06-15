import streamlit as st

from services.db import get_distinct_positions, money, search_players, show_db_error
from ui_components import render_page_actions


def render_prospect_search_view(show_selected_player_banner):
    st.title("유망주 검색")

    selected_name = st.session_state.get("selected_player_name")
    if selected_name:
        st.success(f"현재 선택된 선수: {selected_name}")
        render_page_actions([
            ("📊 통합 분석으로 이동", "유망주 통합 분석", "primary"),
            ("🤝 유사 멘토 찾기", "유사 선수 후보"),
        ], title="선수 선택 완료 · 다음 단계")
    else:
        show_selected_player_banner()

    st.markdown(
        """
        <div class="scout-panel">
            <h3 style="margin-top:0;">검색 조건</h3>
            유망주 기준: FM 데이터 기준 최대 나이 이하
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1, 1.4, 1])
    with c1:
        max_age = st.slider("최대 나이", min_value=16, max_value=30, value=21, step=1)
    with c2:
        keyword = st.text_input("선수 이름", placeholder="예: Bellingham, Yamal, Son")
    with c3:
        try:
            positions = get_distinct_positions(max_age=max_age)
        except Exception as exc:
            show_db_error("포지션 목록 조회", exc)
            positions = ["All"]
        position = st.selectbox("포지션", positions)

    c4, c5 = st.columns(2)
    with c4:
        nationality = st.text_input("국적", placeholder="예: Korea")
    with c5:
        club = st.text_input("소속팀", placeholder="예: Dortmund")

    filters = {
        "keyword": keyword,
        "position": position,
        "nationality": nationality,
        "club": club,
        "max_age": max_age,
    }

    if st.button("유망주 검색", type="primary"):
        try:
            results = search_players(
                keyword=keyword,
                position=position,
                nationality=nationality,
                club=club,
                max_age=max_age,
            )
            st.session_state["prospect_results"] = results
            st.session_state["last_search_filters"] = filters
        except Exception as exc:
            show_db_error("유망주 검색", exc)
            return

    if "prospect_results" not in st.session_state:
        st.info("검색 조건을 설정한 뒤 유망주 검색 버튼을 눌러주세요.")
        return

    results = st.session_state["prospect_results"]
    last_filters = st.session_state.get("last_search_filters", {})

    st.subheader("검색 결과")
    st.caption(
        f"최대 나이 {last_filters.get('max_age', '-')}세, "
        f"포지션 {last_filters.get('position', 'All')} 기준으로 조회한 결과입니다."
    )

    if results.empty:
        st.warning("조건에 맞는 유망주가 없습니다. 최대 나이나 검색 조건을 조정해보세요.")
        return

    for _, row in results.iterrows():
        player_id = int(row["player_id"])
        st.markdown(
            f"""
            <div class="scout-panel">
                <h3 style="margin-top:0;">{row.get('name') or '-'}</h3>
                <div class="badge-row">
                    <span class="scout-badge">나이 {row.get('age') or '-'}</span>
                    <span class="scout-badge">{row.get('position') or '-'}</span>
                    <span class="scout-badge">{row.get('sub_position') or '-'}</span>
                    <span class="scout-badge">{row.get('country_of_citizenship') or '-'}</span>
                </div>
                <p style="margin-bottom:0;">
                    <b>소속팀</b> {row.get('current_club_name') or '-'} ·
                    <b>현재 시장가치</b> {money(row.get('market_value_in_eur'))}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("이 선수 선택", key=f"select_prospect_{player_id}"):
            previous_player_id = st.session_state.get("selected_player_id")
            st.session_state["selected_player_id"] = player_id
            st.session_state["selected_player_name"] = row.get("name")
            if previous_player_id != player_id:
                for key in [
                    "selected_mentor_profile_id",
                    "selected_mentor_name",
                    "mentor_summary",
                    "env_settings",
                    "simulation_result",
                    "generated_report_sections",
                    "generated_report",
                    "generated_report_text",
                    "growth_insight",
                    "growth_explanation",
                    "ceiling_growth_insight",
                    "ceiling_growth_explanation",
                    "ceiling_growth_context",
                    "selected_profile_id",
                    "selected_profile_fallback_note",
                    "selected_entity_type",
                ]:
                    st.session_state.pop(key, None)
            st.success("선수가 선택되었습니다. 유망주 통합 분석 화면에서 확인할 수 있습니다.")
            st.info("왼쪽 메뉴에서 '유망주 통합 분석'으로 이동하세요.")
