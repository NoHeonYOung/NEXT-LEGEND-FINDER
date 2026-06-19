import streamlit as st


WORKFLOW_STEPS = [
    (1, "Search", "분석에 필요한 핵심 데이터가 갖춰진 유망주를 검색하고 선택합니다.", "유망주 검색"),
    (2, "Analyze", "선수의 성장 점수, 능력치, 멘탈/성향 근거를 Player Dossier에서 확인합니다.", "유망주 통합 분석"),
    (3, "Match Mentor", "나이와 경험이 더 앞선 멘토 후보를 찾아 어떤 점을 배울 수 있는지 확인합니다.", "유사 선수 후보"),
    (4, "Simulate Career", "훈련, 출전 기회, 리그 난이도에 따른 성장 시나리오를 비교합니다.", "커리어 시뮬레이션"),
    (5, "Generate Report", "정량 분석과 정성 메모를 바탕으로 스카우팅 리포트 초안을 만듭니다.", "AI 스카우팅 리포트"),
    (6, "Save Notes", "분석 결과를 My Scouting Notes에 저장하고 다시 확인합니다.", "내 스카우팅 노트"),
]

DATA_MODE_GUIDE = [
    ("matched", "종합 분석 가능 선수", "시장가치, 출전 기록, 능력치, 멘탈/성향, 멘토 비교를 함께 볼 수 있습니다."),
    ("fm_profile_only", "능력치 기반 분석 선수", "능력치와 멘토 비교는 가능하지만 시장가치/출전 기록은 제한될 수 있습니다."),
    ("manual_prospect", "직접 입력 선수", "직접 입력한 능력치를 바탕으로 실험적인 분석 흐름을 체험합니다."),
]


def go_to(nav_target):
    st.session_state["nav_page_request"] = nav_target
    st.rerun()


def render_home(status, feature_cards):
    render_hero(status)
    render_scouting_context(status)
    render_workflow()
    render_quick_actions()
    render_data_mode_guide(status)
    render_feature_grid(feature_cards)


def render_hero(status):
    st.markdown(
        """
        <div class="hero-cta">
            <h1>NEXT-LEGEND FINDER</h1>
            <p>유망주를 찾고, 성장 가능성을 해석하고, 멘토와 커리어 시나리오까지 이어 보는 스카우팅 워크룸입니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("유망주 검색 시작", type="primary", width="stretch"):
            go_to("유망주 검색")
    with c2:
        if st.button("직접 입력 유망주", width="stretch"):
            go_to("직접 입력 유망주")
    with c3:
        if st.button("DB 상태 확인", width="stretch"):
            go_to("DB 상태 확인")


def render_scouting_context(status):
    st.subheader("Current Scouting Context")

    if not status["has_player"]:
        st.markdown(
            """
            <div class="scout-panel">
                <h3 style="margin-top: 0;">아직 선택된 선수가 없습니다</h3>
                <p>Scouting Board에서 분석할 선수를 선택하면 Dossier, Mentor Lab, Career Simulation, Report가 이어집니다.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    entity_type = status["entity_type"]
    can_mentor = entity_type in ("matched", "fm_profile_only")
    mentor_line = ""
    if status.get("mentor_name"):
        mentor_line = f'<div><b>선택 멘토</b> {status["mentor_name"]}</div>'

    st.markdown(
        f"""
        <div class="scout-panel">
            <h3 style="margin-top: 0;">현재 선택 선수</h3>
            <div class="badge-row">
                <span class="scout-badge">{status['name']}</span>
                <span class="scout-badge">{status['club']}</span>
                <span class="scout-badge">{status['position']}</span>
                <span class="scout-badge">{status['entity_label']}</span>
            </div>
            {mentor_line}
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Player Dossier로 이동", width="stretch", type="primary"):
            go_to("유망주 통합 분석")
    with c2:
        if st.button("멘토 후보 찾기", width="stretch", disabled=not can_mentor):
            go_to("유사 선수 후보")


def render_workflow():
    st.subheader("Scouting Workflow")
    st.caption("아래 순서대로 진행하면 검색부터 리포트 저장까지 자연스럽게 이어집니다.")

    for step_no, title, description, target in WORKFLOW_STEPS:
        cols = st.columns([5, 1])
        with cols[0]:
            st.markdown(
                f"""
                <div class="workflow-step">
                    <b>{step_no}. {title}</b>
                    <div class="muted">{description}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with cols[1]:
            if st.button("이동", key=f"workflow_step_{step_no}", width="stretch"):
                go_to(target)


def render_quick_actions():
    st.subheader("Quick Actions")
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("**DB 상태 확인**")
            st.write("Supabase 연결과 데이터 상태를 확인합니다.")
            if st.button("DB 상태 보기", key="quick_db_status", width="stretch"):
                go_to("DB 상태 확인")
    with c2:
        with st.container(border=True):
            st.markdown("**My Scouting Notes**")
            st.write("저장된 스카우팅 노트를 조회합니다.")
            if st.button("노트 조회", key="quick_notes", width="stretch"):
                go_to("내 스카우팅 노트")
    with c3:
        with st.container(border=True):
            st.markdown("**직접 입력 유망주**")
            st.write("DB에 없는 선수를 직접 입력해 분석 흐름을 체험합니다.")
            if st.button("직접 입력 시작", key="quick_manual", width="stretch"):
                go_to("직접 입력 유망주")


def render_data_mode_guide(status):
    st.subheader("분석 데이터 안내")
    st.caption("현재 검색은 기본적으로 모든 핵심 분석 데이터가 있는 선수만 보여주도록 설정되어 있습니다.")

    active_entity = status.get("entity_type")
    for entity_type, title, description in DATA_MODE_GUIDE:
        active_class = " active" if entity_type == active_entity else ""
        st.markdown(
            f"""
            <div class="data-mode-card{active_class}">
                <b>{title}</b>
                <div class="muted">{description}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_feature_grid(feature_cards):
    st.subheader("전체 메뉴")
    st.caption("아래 카드에서 원하는 화면으로 바로 이동할 수 있습니다.")

    cols = st.columns(3)
    for index, card in enumerate(feature_cards):
        with cols[index % 3]:
            with st.container(border=True):
                st.markdown(f"**{card['title']}**")
                st.write(card["description"])
                if st.button(card["button_label"], key=f"home_nav_{card['nav_target']}", width="stretch"):
                    go_to(card["nav_target"])

    st.info("Football Manager 고유 로고나 에셋을 복제하지 않고, 스포츠 매니지먼트 UI의 정보 구조만 참고한 독립 프로젝트입니다.")
