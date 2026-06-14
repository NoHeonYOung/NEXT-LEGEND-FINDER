import streamlit as st


WORKFLOW_STEPS = [
    (1, "Search", "DB에서 분석할 유망주를 검색하고 선택합니다.", "유망주 검색"),
    (2, "Analyze", "선택한 선수의 시장가치, 출전 기록, FM 능력치를 통합 분석합니다.", "유망주 통합 분석"),
    (3, "Match Mentor", "FM 기반 proxy 벡터로 유사한 선수(멘토) 후보를 찾습니다.", "유사 선수 후보"),
    (4, "Simulate Career", "훈련 강도, 출전 기회, 리그 수준에 따른 성장 시나리오를 확인합니다.", "커리어 시뮬레이션"),
    (5, "Generate Report", "시뮬레이션 결과를 바탕으로 스카우팅 리포트 초안을 생성합니다.", "AI 스카우팅 리포트"),
    (6, "Save Notes", "분석 결과를 My Scouting Notes에 저장하고 조회합니다.", "내 스카우팅 노트"),
]

DATA_MODE_GUIDE = [
    (
        "matched",
        "Matched (FM + Transfermarkt 통합)",
        "시장가치 · 출전 기록 · FM 능력치/멘탈 분석 · 유사 멘토 매칭이 모두 가능합니다.",
    ),
    (
        "transfermarkt_only",
        "Transfermarkt Only",
        "시장가치와 출전 기록은 확인할 수 있지만, FM 스타일/멘탈 분석과 유사 멘토 매칭은 제한됩니다.",
    ),
    (
        "fm_profile_only",
        "FM Profile Only",
        "FM 능력치/멘탈 분석과 유사 멘토 매칭은 가능하지만, 시장가치와 출전 기록은 제한됩니다.",
    ),
    (
        "manual_note",
        "Manual Note (직접 입력)",
        "My Scouting Notes에서 직접 입력한 능력치를 바탕으로 프로토타입 분석을 진행합니다.",
    ),
]


def go_to(nav_target):
    st.session_state["nav_page_request"] = nav_target
    st.rerun()


def render_home(status, feature_cards):
    render_hero(status)
    render_scouting_context(status)
    render_workflow(status)
    render_quick_actions()
    render_data_mode_guide(status)
    render_feature_grid(feature_cards)


def render_hero(status):
    st.markdown(
        """
        <div class="hero-cta">
            <h1>NEXT-LEGEND FINDER</h1>
            <p>유망주를 검색하고, 통합 분석과 유사 멘토 매칭을 거쳐 커리어 시뮬레이션과
            스카우팅 리포트, 노트 저장까지 이어지는 구단 내부 스카우팅 센터 프로토타입입니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🔎 유망주 검색 시작", type="primary", use_container_width=True):
            go_to("유망주 검색")
    with c2:
        if st.button("📝 직접 노트 작성", use_container_width=True):
            go_to("내 스카우팅 노트")
    with c3:
        if st.button("🗂️ DB 상태 확인", use_container_width=True):
            go_to("DB 상태 확인")


def render_scouting_context(status):
    st.subheader("Current Scouting Context")

    if not status["has_player"]:
        st.markdown(
            """
            <div class="scout-panel">
                <h3 style="margin-top: 0;">아직 선택된 선수가 없습니다</h3>
                <p>유망주 검색에서 선수를 선택하거나, My Scouting Notes에서 직접 입력해보세요.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    entity_type = status["entity_type"]
    can_analyze = entity_type in ("matched", "transfermarkt_only", "fm_profile_only")
    can_mentor = entity_type in ("matched", "fm_profile_only")
    can_report = True

    mentor_line = ""
    if status.get("mentor_name"):
        mentor_line = f'<div><b>선택 멘토</b> {status["mentor_name"]}</div>'

    capability_badges = "".join(
        f'<span class="scout-badge">{label}</span>'
        for label, available in [
            ("통합 분석 가능" if can_analyze else "통합 분석 제한", can_analyze),
            ("유사 멘토 매칭 가능" if can_mentor else "유사 멘토 매칭 제한", can_mentor),
            ("리포트 생성 가능" if can_report else "리포트 생성 제한", can_report),
        ]
    )

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
            <div class="muted" style="margin-top: 10px;">현재 가능한 작업</div>
            <div class="badge-row">{capability_badges}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("📊 통합 분석으로 이동", use_container_width=True, type="primary"):
            go_to("유망주 통합 분석")
    with c2:
        if st.button("🤝 유사 멘토 찾기", use_container_width=True, disabled=not can_mentor):
            go_to("유사 선수 후보")


def render_workflow(status):
    st.subheader("Scouting Workflow")
    st.caption("아래 단계를 순서대로 따라가면 검색부터 노트 저장까지 자연스럽게 이어집니다.")

    for step_no, title, description, target in WORKFLOW_STEPS:
        cols = st.columns([5, 1])
        with cols[0]:
            st.markdown(
                f"""
                <div class="workflow-step">
                    <span class="step-no">{step_no}</span><b>{title}</b>
                    <div class="muted">{description}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with cols[1]:
            if st.button("이동", key=f"workflow_step_{step_no}", use_container_width=True):
                go_to(target)


def render_quick_actions():
    st.subheader("Quick Actions")
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("**DB 상태 확인**")
            st.write("Supabase 연결과 데이터 현황을 확인합니다.")
            if st.button("DB 상태 보기", key="quick_db_status", use_container_width=True):
                go_to("DB 상태 확인")
    with c2:
        with st.container(border=True):
            st.markdown("**My Scouting Notes**")
            st.write("저장된 스카우팅 노트를 조회합니다.")
            if st.button("노트 조회", key="quick_notes", use_container_width=True):
                go_to("내 스카우팅 노트")
    with c3:
        with st.container(border=True):
            st.markdown("**직접 입력 유망주 분석**")
            st.write("DB에 없는 유망주를 직접 입력해 프로토타입 분석을 생성합니다.")
            if st.button("직접 입력 시작", key="quick_manual", use_container_width=True):
                go_to("내 스카우팅 노트")


def render_data_mode_guide(status):
    st.subheader("Data Mode Guide")
    st.caption("선택한 선수의 데이터 타입에 따라 분석 가능한 범위가 달라집니다.")

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
    st.caption("아래 카드를 눌러 원하는 화면으로 바로 이동할 수 있습니다.")

    cols = st.columns(3)
    for index, card in enumerate(feature_cards):
        with cols[index % 3]:
            with st.container(border=True):
                st.markdown(f"**{card['title']}**")
                st.write(card["description"])
                if st.button(card["button_label"], key=f"home_nav_{card['nav_target']}", use_container_width=True):
                    go_to(card["nav_target"])

    st.info("공식 Football Manager 자산을 복제하지 않고, 정보 구조와 분위기만 참고한 스카우팅 대시보드 프로토타입입니다.")
