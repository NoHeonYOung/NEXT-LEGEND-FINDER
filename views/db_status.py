import pandas as pd
import streamlit as st

from services.db import TABLES, get_prospect_diagnostics, preview_table, show_db_error, table_count


def render_db_status():
    st.title("DB 상태 확인")
    try:
        counts = pd.DataFrame([{"테이블": table, "행 수": table_count(table)} for table in TABLES])
    except Exception as exc:
        show_db_error("Supabase 연결 또는 테이블 조회", exc)
        return

    st.success("Supabase 연결 성공")
    st.dataframe(counts, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("유망주 데이터 진단 (Developer Diagnostics)")
    diagnostics = get_prospect_diagnostics()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 players 수", diagnostics["players_total"])
    c2.metric("전체 player_profiles 수", diagnostics["profiles_total"])
    c3.metric("매칭되는 선수 수", diagnostics["matched_total"])
    c4.metric("profile age 보유 수", diagnostics["age_covered"])

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("profiles 없는 players", diagnostics["players_without_profiles"])
    c6.metric("players 없는 profiles", diagnostics["profiles_without_players"])
    c7.metric("DOB 기준 23세 미만 선수", diagnostics["young_players_from_dob"])
    c8.metric("profile age ≤ 23인 수", diagnostics["young_profiles"])

    coverage_pct = diagnostics["coverage_ratio"] * 100
    age_pct = diagnostics["profile_coverage_ratio"] * 100

    st.info(
        "이 진단은 Prospect Search가 왜 후보가 적게 보이는지 확인하기 위한 SELECT 기반 확인용입니다. "
        "실제 DB 구조나 CSV는 수정하지 않고, 현재 저장된 데이터만으로 후보 풀과 profile 커버리지를 확인합니다."
    )

    st.caption(
        f"players 대비 player_profiles 매칭 비율: {coverage_pct:.1f}% | "
        f"player_profiles 중 age 정보가 있는 비율: {age_pct:.1f}%"
    )

    if diagnostics["players_total"] > 0 and diagnostics["matched_total"] < diagnostics["players_total"]:
        st.warning(
            "현재 DB에는 player_profiles와 매칭되지 않는 선수들이 있습니다. "
            "이 경우 Prospect Search에서 후보 수가 적게 보일 수 있습니다."
        )

    if diagnostics["profiles_total"] == 0:
        st.warning("현재 player_profiles 데이터가 전혀 없습니다. 이 경우 검색 대상이 크게 줄어들 수 있습니다.")
    else:
        st.write("- player_profiles.age가 있는 선수 수를 보면, age 필터를 적용했을 때 후보가 얼마나 줄어드는지 확인할 수 있습니다.")

    if diagnostics["young_players_from_dob"] == 0:
        st.info("DOB 기준으로 보면 아직 23세 미만 유망주 후보가 충분하지 않을 수 있습니다. 이후 검색 로직을 수정할 때 이 숫자를 함께 참고하세요.")
    else:
        st.write("- DOB 기준으로 23세 미만 선수가 존재하므로, 검색 범위가 너무 좁지 않다면 후보 풀은 충분할 가능성이 있습니다.")

    st.divider()
    table_name = st.selectbox("미리 볼 테이블", TABLES)
    limit = st.slider("조회 행 수", 5, 100, 30, 5)
    try:
        st.dataframe(preview_table(table_name, limit=limit), use_container_width=True, hide_index=True)
    except Exception as exc:
        show_db_error("테이블 미리보기", exc)
