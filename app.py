import json
import tomllib
from pathlib import Path

import altair as alt
import pandas as pd
import psycopg
import streamlit as st

from services.db import get_prospect_diagnostics, get_scouting_notes, insert_scouting_note, query_df, query_one, show_db_error, table_count, preview_table, search_players, search_players_with_modes, get_distinct_positions, get_player, get_valuations, get_profile_by_player_id, get_profile_by_name, get_player_profile, get_similar_players, money
from ui.components import apply_theme as apply_ui_theme, render_feature_card, render_metric_cards, render_status_banner, safe_text
from ui.navigation import init_navigation_state, navigate_to, render_app_header
from views.db_status import render_db_status as render_db_status_view
from views.home import render_home as render_home_view
from views.prospect_search import render_prospect_search as render_prospect_search_view


BASE_DIR = Path(__file__).resolve().parent
SECRETS_PATH = BASE_DIR / ".streamlit" / "secrets.toml"

TABLES = [
    "clubs",
    "players",
    "appearances",
    "player_valuations",
    "player_profiles",
    "scouting_notes",
]

PAGES = [
    "Home / Service Intro",
    "Prospect Search",
    "Integrated Analysis Dashboard",
    "Legend Matching",
    "Career Simulation",
    "AI Scouting Report",
    "My Scouting Notes",
    "DB Status",
]


st.set_page_config(page_title="NEXT-LEGEND FINDER", layout="wide")


def load_db_url():
    if "SUPABASE_DB_URL" in st.secrets:
        return st.secrets["SUPABASE_DB_URL"]

    with open(SECRETS_PATH, "rb") as f:
        secrets = tomllib.load(f)

    return secrets["SUPABASE_DB_URL"]


@st.cache_resource
def get_connection(db_url):
    return psycopg.connect(db_url, connect_timeout=10)


def query_df(sql, params=None):
    conn = get_connection(load_db_url())

    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        columns = [desc.name for desc in cur.description]

    return pd.DataFrame(rows, columns=columns)


def query_one(sql, params=None):
    conn = get_connection(load_db_url())

    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        row = cur.fetchone()

        if row is None:
            return None

        columns = [desc.name for desc in cur.description]
        return dict(zip(columns, row))


def execute_one(sql, params=None):
    conn = get_connection(load_db_url())

    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        row = cur.fetchone()
        columns = [desc.name for desc in cur.description] if cur.description else []

    conn.commit()

    if row is None:
        return None

    return dict(zip(columns, row))


def show_db_error(action, exc):
    message = str(exc)
    lowered = message.lower()
    st.error(f"{action} 중 DB 연결 또는 조회 오류가 발생했습니다.")

    if "tenant/user" in lowered and "not found" in lowered:
        st.warning(
            "Supabase Pooler가 연결 문자열의 프로젝트 참조값을 찾지 못했습니다. "
            "Supabase Dashboard에서 현재 프로젝트를 연 뒤 Connect > Session pooler 연결 문자열을 "
            "다시 복사하여 `.streamlit/secrets.toml`의 `SUPABASE_DB_URL`을 교체하고 앱을 재시작해 주세요."
        )
    elif "password authentication failed" in lowered:
        st.warning(
            "DB 비밀번호 인증에 실패했습니다. Supabase Dashboard의 현재 DB 비밀번호를 확인하거나 "
            "비밀번호를 재설정한 뒤 `SUPABASE_DB_URL`을 갱신해 주세요."
        )
    else:
        st.info("Supabase 프로젝트 상태와 `.streamlit/secrets.toml`의 `SUPABASE_DB_URL`을 확인해 주세요.")

    with st.expander("개발자용 DB 오류 보기"):
        st.code(message)


def table_count(table_name):
    if table_name not in TABLES:
        raise ValueError("허용되지 않은 테이블입니다.")

    result = query_one(f"select count(*) as count from {table_name}")
    return result["count"]


def preview_table(table_name, limit=50):
    if table_name not in TABLES:
        raise ValueError("허용되지 않은 테이블입니다.")

    limit = max(1, min(int(limit), 100))
    return query_df(f"select * from {table_name} limit {limit}")


def search_players(keyword="", position="", nationality="", club="", max_age=23):
    player_name = "coalesce(p.name, pp.name)"
    conditions = []
    params = []

    if max_age is not None:
        conditions.append("(pp.age is null or pp.age <= %s)")
        params.append(max_age)

    if keyword:
        conditions.append(f"{player_name} ilike %s")
        params.append(f"%{keyword}%")

    if position and position != "All":
        conditions.append("p.position = %s")
        params.append(position)

    if nationality:
        conditions.append("p.country_of_citizenship ilike %s")
        params.append(f"%{nationality}%")

    if club:
        conditions.append("p.current_club_name ilike %s")
        params.append(f"%{club}%")

    sql = f"""
        select
            p.player_id,
            pp.profile_id,
            {player_name} as name,
            pp.age,
            p.current_club_name,
            p.country_of_citizenship,
            p.position,
            p.sub_position,
            p.market_value_in_eur,
            p.image_url
        from players p
        left join player_profiles pp
            on pp.player_id = p.player_id
        where {" and ".join(conditions) if conditions else "1=1"}
        order by p.market_value_in_eur desc nulls last
        limit 100
    """

    return query_df(sql, tuple(params))


def search_players_with_modes(keyword="", position="", nationality="", club="", max_age=23):
    matched = search_players(keyword=keyword, position=position, nationality=nationality, club=club, max_age=max_age)
    matched = matched.copy()
    matched["search_mode"] = "matched"
    matched["source_label"] = "통합 분석 가능 후보"

    conditions = ["pp.age is not null", "pp.age <= %s"]
    params = [max_age]

    if keyword:
        conditions.append("pp.name ilike %s")
        params.append(f"%{keyword}%")
    if position and position != "All":
        conditions.append("pp.position = %s")
        params.append(position)
    if nationality:
        conditions.append("pp.nationality ilike %s")
        params.append(f"%{nationality}%")
    if club:
        conditions.append("pp.club ilike %s")
        params.append(f"%{club}%")

    fm_only_sql = f"""
        select
            'fm_profile_only' as search_mode,
            null::bigint as player_id,
            pp.profile_id,
            pp.name,
            pp.age,
            pp.club as current_club_name,
            pp.nationality as country_of_citizenship,
            pp.position,
            null::text as sub_position,
            null::bigint as market_value_in_eur,
            null::text as image_url,
            'FM 프로필 기반 후보' as source_label
        from player_profiles pp
        left join players p on p.player_id = pp.player_id
        where p.player_id is null
          and {" and ".join(conditions)}
        order by pp.age asc nulls last, pp.name asc
        limit 100
    """
    fm_only = query_df(fm_only_sql, tuple(params))

    transfermarkt_conditions = ["p.player_id is not null"]
    transfermarkt_params = []
    if keyword:
        transfermarkt_conditions.append("p.name ilike %s")
        transfermarkt_params.append(f"%{keyword}%")
    if position and position != "All":
        transfermarkt_conditions.append("p.position = %s")
        transfermarkt_params.append(position)
    if nationality:
        transfermarkt_conditions.append("p.country_of_citizenship ilike %s")
        transfermarkt_params.append(f"%{nationality}%")
    if club:
        transfermarkt_conditions.append("p.current_club_name ilike %s")
        transfermarkt_params.append(f"%{club}%")
    if max_age is not None:
        transfermarkt_conditions.append("(p.date_of_birth is null or age(p.date_of_birth) < interval '23 years' or age(p.date_of_birth) <= interval '%s years')")
        transfermarkt_params.append(f"{max_age}")

    transfermarkt_sql = f"""
        select
            'transfermarkt_only' as search_mode,
            p.player_id,
            null::bigint as profile_id,
            p.name,
            null::integer as age,
            p.current_club_name,
            p.country_of_citizenship,
            p.position,
            p.sub_position,
            p.market_value_in_eur,
            p.image_url,
            'Transfermarkt 기반 후보' as source_label
        from players p
        left join player_profiles pp on pp.player_id = p.player_id
        where pp.player_id is null
          and {" and ".join(transfermarkt_conditions)}
        order by p.market_value_in_eur desc nulls last
        limit 100
    """
    transfermarkt = query_df(transfermarkt_sql, tuple(transfermarkt_params))

    combined = pd.concat([matched, fm_only, transfermarkt], ignore_index=True, sort=False)
    combined = combined.where(pd.notna(combined), None)
    return combined


def get_distinct_positions(max_age=23):
    sql = """
        select distinct p.position
        from players p
        left join player_profiles pp
            on pp.player_id = p.player_id
        where p.position is not null
          and p.position <> ''
          and (pp.age is null or pp.age <= %s)
        order by p.position
    """
    df = query_df(sql, (max_age,))
    return ["All"] + df["position"].dropna().tolist()


def get_player(player_id):
    sql = """
        select *
        from players
        where player_id = %s
        limit 1
    """

    return query_one(sql, (player_id,))


def get_valuations(player_id):
    sql = """
        select
            date,
            market_value_in_eur,
            current_club_name
        from player_valuations
        where player_id = %s
        order by date
        limit 300
    """

    return query_df(sql, (player_id,))


def get_appearances(player_id, limit=20):
    sql = """
        select
            date,
            competition_id,
            goals,
            assists,
            yellow_cards,
            red_cards,
            minutes_played
        from appearances
        where player_id = %s
        order by date desc
        limit %s
    """

    return query_df(sql, (player_id, limit))


def get_profile_by_player_id(player_id):
    sql = """
        select *
        from player_profiles
        where player_id = %s
        limit 1
    """

    return query_one(sql, (player_id,))


def get_profile_by_name(name):
    sql = """
        select *
        from player_profiles
        where name ilike %s
        order by age asc nulls last
        limit 1
    """

    return query_one(sql, (f"%{name}%",))


def get_profile_by_name_nationality_position(name, nationality=None, position=None):
    if not name:
        return None

    conditions = ["name ilike %s"]
    params = [f"%{name}%"]

    if nationality:
        conditions.append("nationality ilike %s")
        params.append(f"%{nationality}%")

    if position:
        conditions.append("position = %s")
        params.append(position)

    sql = f"""
        select *
        from player_profiles
        where {" and ".join(conditions)}
        order by age asc nulls last
        limit 1
    """

    return query_one(sql, tuple(params))


def get_player_profile(player):
    if not player:
        return None

    try:
        profile = get_profile_by_player_id(player["player_id"])

        if profile is None:
            profile = get_profile_by_name(player["name"])
    except Exception:
        st.error("선수 프로필을 DB에서 조회하는 중 오류가 발생했습니다.")
        return None

    return profile


def get_similar_players(profile_id):
    sql = """
        select
            p.profile_id,
            p.player_id,
            p.name,
            p.age,
            p.club,
            p.nationality,
            p.position,
            round((1 - (p.style_vector <=> q.style_vector))::numeric, 4) as similarity
        from player_profiles p
        join player_profiles q
            on q.profile_id = %s
        where p.profile_id <> q.profile_id
          and p.style_vector is not null
          and q.style_vector is not null
        order by p.style_vector <=> q.style_vector
        limit 10
    """

    return query_df(sql, (profile_id,))


def insert_scouting_note(player_id, profile_id, env_settings, simulation_result, report):
    sql = """
        insert into scouting_notes (
            user_id,
            player_id,
            profile_id,
            matched_profile_id,
            env_settings,
            simulation_result,
            gemini_report
        )
        values (
            null,
            %s,
            %s,
            null,
            %s::jsonb,
            %s::jsonb,
            %s
        )
        returning note_id, created_at
    """

    return execute_one(
        sql,
        (
            player_id,
            profile_id,
            json.dumps(env_settings, ensure_ascii=False),
            json.dumps(simulation_result, ensure_ascii=False),
            report,
        ),
    )


def get_scouting_notes(limit=20):
    sql = """
        select
            n.note_id,
            n.user_id,
            n.player_id,
            p.name as player_name,
            n.profile_id,
            n.env_settings,
            n.simulation_result,
            n.gemini_report,
            n.created_at
        from scouting_notes n
        left join players p on p.player_id = n.player_id
        order by n.created_at desc
        limit %s
    """

    return query_df(sql, (limit,))


def get_prospect_diagnostics():
    players_total = query_one("select count(*) as count from players")
    profiles_total = query_one("select count(*) as count from player_profiles")
    matched_total = query_one("""
        select count(*) as count
        from players p
        join player_profiles pp on pp.player_id = p.player_id
    """)
    players_without_profiles = query_one("""
        select count(*) as count
        from players p
        left join player_profiles pp on pp.player_id = p.player_id
        where pp.player_id is null
    """)
    profiles_without_players = query_one("""
        select count(*) as count
        from player_profiles pp
        left join players p on p.player_id = pp.player_id
        where p.player_id is null
    """)
    age_covered = query_one("""
        select count(*) as count
        from player_profiles
        where age is not null
    """)
    young_players_from_dob = query_one("""
        select count(*) as count
        from players
        where date_of_birth is not null
          and age(date_of_birth) < interval '23 years'
    """)
    young_profiles = query_one("""
        select count(*) as count
        from player_profiles
        where age is not null
          and age <= 23
    """)

    players_total = int(players_total["count"]) if players_total else 0
    profiles_total = int(profiles_total["count"]) if profiles_total else 0
    matched_total = int(matched_total["count"]) if matched_total else 0
    players_without_profiles = int(players_without_profiles["count"]) if players_without_profiles else 0
    profiles_without_players = int(profiles_without_players["count"]) if profiles_without_players else 0
    age_covered = int(age_covered["count"]) if age_covered else 0
    young_players_from_dob = int(young_players_from_dob["count"]) if young_players_from_dob else 0
    young_profiles = int(young_profiles["count"]) if young_profiles else 0

    coverage_ratio = (matched_total / players_total) if players_total else 0.0
    profile_coverage_ratio = (age_covered / profiles_total) if profiles_total else 0.0

    return {
        "players_total": players_total,
        "profiles_total": profiles_total,
        "matched_total": matched_total,
        "players_without_profiles": players_without_profiles,
        "profiles_without_players": profiles_without_players,
        "age_covered": age_covered,
        "young_players_from_dob": young_players_from_dob,
        "young_profiles": young_profiles,
        "coverage_ratio": coverage_ratio,
        "profile_coverage_ratio": profile_coverage_ratio,
    }


def money(value):
    if value is None or pd.isna(value):
        return "-"

    try:
        return f"EUR {int(value):,}"
    except Exception:
        return str(value)


def resolve_selected_player_context():
    """현재 세션에 선택된 선수의 player_id/profile_id/entity_type을
    실제 DB 매칭 상태와 일치하도록 정리해서 반환한다.

    - player_id와 profile_id가 모두 있으면 matched
    - profile_id만 있으면 fm_profile_only
    - player_id만 있고 profile_id가 없으면, name/nationality/position 기반으로
      player_profiles 보조 매칭을 한 번 시도한다. 매칭되면 matched로 승격하고
      session_state의 selected_profile_id를 채워준다. 매칭되지 않으면
      transfermarkt_only로 처리한다.
    """
    raw_player_id = st.session_state.get("selected_player_id")
    raw_profile_id = st.session_state.get("selected_profile_id")

    player_id = int(raw_player_id) if raw_player_id is not None else None
    profile_id = int(raw_profile_id) if raw_profile_id is not None else None
    fallback_note = None

    if player_id is not None and profile_id is None:
        try:
            profile = get_profile_by_player_id(player_id)
        except Exception:
            profile = None

        if profile is None:
            try:
                player = get_player(player_id)
            except Exception:
                player = None

            if player:
                try:
                    profile = get_profile_by_name_nationality_position(
                        player.get("name"),
                        player.get("country_of_citizenship"),
                        player.get("position"),
                    )
                except Exception:
                    profile = None

                if profile is not None:
                    fallback_note = (
                        "player_id 직접 매칭은 아니지만 이름/국적/포지션 기반으로 "
                        "FM 프로필을 보조 연결했습니다."
                    )

        if profile is not None and profile.get("profile_id") is not None:
            profile_id = profile["profile_id"]
            st.session_state["selected_profile_id"] = profile_id

    if profile_id is not None and player_id is not None:
        entity_type = "matched"
    elif profile_id is not None:
        entity_type = "fm_profile_only"
    elif player_id is not None:
        entity_type = "transfermarkt_only"
    else:
        entity_type = None

    if entity_type is not None:
        st.session_state["selected_entity_type"] = entity_type

    st.session_state["selected_profile_fallback_note"] = fallback_note

    return {
        "player_id": player_id,
        "profile_id": profile_id,
        "entity_type": entity_type,
        "fallback_note": fallback_note,
    }


def selected_player_id():
    return resolve_selected_player_context()["player_id"]


def selected_profile_id():
    return resolve_selected_player_context()["profile_id"]


def selected_entity_type():
    return resolve_selected_player_context()["entity_type"] or "matched"


def selected_profile():
    ctx = resolve_selected_player_context()
    profile_id = ctx["profile_id"]

    if profile_id:
        return query_one("select * from player_profiles where profile_id = %s limit 1", (profile_id,))

    return None


def selected_player():
    ctx = resolve_selected_player_context()

    if ctx["entity_type"] == "fm_profile_only":
        profile = selected_profile()
        if profile:
            return {
                "player_id": None,
                "name": profile.get("name") or "FM 프로필 기반 후보",
                "current_club_name": profile.get("club") or "-",
                "country_of_citizenship": profile.get("nationality") or "-",
                "position": profile.get("position") or "-",
                "sub_position": None,
                "foot": None,
                "height_in_cm": None,
                "market_value_in_eur": None,
                "highest_market_value_in_eur": None,
                "image_url": None,
            }

    player_id = ctx["player_id"]

    if player_id is None:
        return None

    try:
        return get_player(player_id)
    except Exception:
        st.error("선택 선수 정보를 DB에서 조회하는 중 오류가 발생했습니다.")
        return None


def require_selected_player():
    player = selected_player()

    if player is None:
        st.warning("먼저 Prospect Search 화면에서 분석할 선수를 선택해 주세요.")
        return None

    return player


def show_selected_player_banner():
    player = selected_player()

    if player is None:
        st.info("현재 선택된 선수가 없습니다.")
        return

    st.success(
        f"선택된 선수: {player['name']} | "
        f"{player.get('current_club_name') or '-'} | "
        f"{player.get('position') or '-'}"
    )


ENTITY_TYPE_LABELS = {
    "matched": "FM 프로필 + Transfermarkt 통합 데이터",
    "fm_profile_only": "FM 프로필 기반 후보",
    "transfermarkt_only": "Transfermarkt 기반 후보",
    "manual_note": "직접 입력 기반 분석",
    None: "선택 선수 없음",
}

DATA_MODE_BADGE_CLASS = {
    "matched": "data-mode-badge data-mode-matched",
    "fm_profile_only": "data-mode-badge data-mode-fm",
    "transfermarkt_only": "data-mode-badge data-mode-tm",
    "manual_note": "data-mode-badge data-mode-manual",
    None: "data-mode-badge data-mode-none",
}

# 메인 메뉴(사이드바 radio)의 옵션 라벨과 반드시 일치해야 하는 nav target 목록.
NAV_TARGETS = [
    "홈 / 서비스 소개",
    "유망주 검색",
    "유망주 통합 분석",
    "유사 선수 후보",
    "커리어 시뮬레이션",
    "AI 스카우팅 리포트",
    "내 스카우팅 노트",
    "DB 상태 확인",
]

NAV_CHIP_LABELS = {
    "홈 / 서비스 소개": "Home",
    "유망주 검색": "Search",
    "유망주 통합 분석": "Analysis",
    "유사 선수 후보": "Mentor",
    "커리어 시뮬레이션": "Simulation",
    "AI 스카우팅 리포트": "Report",
    "내 스카우팅 노트": "Notes",
    "DB 상태 확인": "DB",
}


def go_to(nav_target):
    """nav_page_request를 통해 다음 렌더링에서 main()이 sidebar.radio 값을 갱신하도록 한다."""
    st.session_state["nav_page_request"] = nav_target
    st.rerun()


def render_nav_chips(active_page):
    st.markdown('<div class="nav-chip-row">', unsafe_allow_html=True)
    cols = st.columns(len(NAV_TARGETS))
    for col, target in zip(cols, NAV_TARGETS):
        with col:
            is_active = target == active_page
            if st.button(
                NAV_CHIP_LABELS.get(target, target),
                key=f"navchip_{target}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
                disabled=is_active,
            ):
                go_to(target)
    st.markdown('</div>', unsafe_allow_html=True)


def render_page_actions(actions, title="다음 단계"):
    """화면 하단 '다음 단계' 버튼 그룹. actions: [(label, nav_target, type), ...]"""
    if not actions:
        return
    st.markdown("---")
    st.markdown(f'<div class="next-step-title">{title}</div>', unsafe_allow_html=True)
    cols = st.columns(len(actions))
    for col, action in zip(cols, actions):
        label, target = action[0], action[1]
        button_type = action[2] if len(action) > 2 else "secondary"
        with col:
            if st.button(label, key=f"pageaction_{target}_{label}", use_container_width=True, type=button_type):
                go_to(target)


def get_selected_player_status():
    """Home 화면/공통 헤더에 표시할 선택 선수 상태 요약. 기존 선택 로직(selected_player 등)을 그대로 사용."""
    player = selected_player()

    if player is None:
        return {
            "has_player": False,
            "name": None,
            "club": None,
            "position": None,
            "entity_type": None,
            "entity_label": None,
            "mentor_name": st.session_state.get("selected_mentor_name"),
        }

    entity_type = selected_entity_type()

    return {
        "has_player": True,
        "name": player.get("name") or "-",
        "club": player.get("current_club_name") or "-",
        "position": player.get("position") or "-",
        "entity_type": entity_type,
        "entity_label": ENTITY_TYPE_LABELS.get(entity_type, entity_type),
        "mentor_name": st.session_state.get("selected_mentor_name"),
    }


def render_app_header(page_label):
    """모든 화면 상단에 표시되는 공통 헤더: 브랜드, 현재 위치, 선택 선수 상태, 데이터 타입, navigation."""
    status = get_selected_player_status()
    entity_type = status["entity_type"]
    data_mode_label = ENTITY_TYPE_LABELS.get(entity_type, entity_type or "선택 선수 없음")
    badge_class = DATA_MODE_BADGE_CLASS.get(entity_type, DATA_MODE_BADGE_CLASS[None])

    if status["has_player"]:
        status_text = (
            f"선택 선수: <b>{status['name']}</b> · {status['club']} · {status['position']}"
        )
        if status["mentor_name"]:
            status_text += f" · 멘토: <b>{status['mentor_name']}</b>"
    else:
        status_text = "선택 선수: 아직 없음 · 유망주 검색에서 분석할 선수를 선택해 주세요."

    st.markdown(
        f"""
        <div class="app-header">
            <div>
                <div class="app-header-brand">NEXT-LEGEND FINDER</div>
                <div class="app-header-page">Scouting Center · 현재 위치: {page_label}</div>
            </div>
            <div class="app-header-status">
                {status_text}<br/>
                <span class="{badge_class}">데이터 타입: {data_mode_label}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    home_col, _ = st.columns([1, 7])
    with home_col:
        if page_label != "홈 / 서비스 소개":
            if st.button("🏠 Home", key="header_home_button", use_container_width=True):
                go_to("홈 / 서비스 소개")

    render_nav_chips(page_label)


def parse_json_field(value):
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    try:
        return json.loads(value)
    except Exception:
        return {}


def render_home():
    st.title("NEXT-LEGEND FINDER")
    st.caption("HW#5 DB 적용 기본 서비스 프로토타입")

    st.subheader("서비스 개요")
    st.write(
        "NEXT-LEGEND FINDER는 축구 유망주의 기본 정보, 시장가치 변화, "
        "출전 기록, FM 기반 proxy 능력치와 멘탈리티 데이터를 한 화면에서 "
        "확인하고 향후 성장 분석 서비스로 확장하기 위한 DB 활용 앱입니다."
    )

    st.subheader("이번 HW#5 구현 범위")
    st.write(
        "이번 단계에서는 완성된 예측 모델이나 실제 Gemini API 호출을 구현하지 않습니다. "
        "HW#4에서 만든 Supabase PostgreSQL 데이터베이스를 유지하면서, Streamlit에서 "
        "서비스형 화면 흐름과 기본 저장 흐름을 구현합니다."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Core DB Tables", "6")
        st.write("players, appearances, player_profiles 등 기존 테이블을 그대로 사용합니다.")

    with col2:
        st.metric("Matching Vector", "24D")
        st.write("10x10 Grid가 아니라 FM 기반 proxy style_vector(24차원)를 사용합니다.")

    with col3:
        st.metric("Report Type", "Template")
        st.write("실제 LLM 호출 전 단계의 template-based scouting report입니다.")

    st.subheader("기술 스택")
    st.write("Python, Streamlit, Supabase PostgreSQL, Pandas, JSONB, pgvector, Altair")


def render_dashboard():
    st.title("Integrated Analysis Dashboard")
    player = require_selected_player()

    if player is None:
        return

    profile = get_player_profile(player)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Player Profile")
        if player.get("image_url"):
            st.image(player["image_url"], width=180)

        st.write(f"이름: {player.get('name')}")
        st.write(f"국적: {player.get('country_of_citizenship') or '-'}")
        st.write(f"소속팀: {player.get('current_club_name') or '-'}")
        st.write(f"포지션: {player.get('position') or '-'}")
        st.write(f"세부 포지션: {player.get('sub_position') or '-'}")
        st.write(f"주발: {player.get('foot') or '-'}")
        st.write(f"키: {player.get('height_in_cm') or '-'} cm")
        st.write(f"현재 시장가치: {money(player.get('market_value_in_eur'))}")
        st.write(f"최고 시장가치: {money(player.get('highest_market_value_in_eur'))}")

    with col2:
        st.subheader("Market Value Summary")
        valuations = get_valuations(player["player_id"])

        if valuations.empty:
            st.info("시장가치 데이터가 없습니다.")
        else:
            valuations["date"] = pd.to_datetime(valuations["date"])
            valuations["market_value_in_eur"] = pd.to_numeric(
                valuations["market_value_in_eur"],
                errors="coerce",
            )
            chart = (
                alt.Chart(valuations)
                .mark_line(point=True)
                .encode(
                    x="date:T",
                    y="market_value_in_eur:Q",
                    tooltip=["date:T", "market_value_in_eur:Q", "current_club_name:N"],
                )
            )
            st.altair_chart(chart, use_container_width=True)

    st.divider()

    pcol1, pcol2 = st.columns(2)

    with pcol1:
        st.subheader("FM Proxy Style Summary")

        if profile is None:
            st.warning("연결된 player_profiles 데이터가 없습니다.")
        else:
            st.write(f"FM 이름: {profile.get('name')}")
            st.write(f"FM 클럽: {profile.get('club') or '-'}")
            st.write(f"FM 포지션: {profile.get('position') or '-'}")
            st.write(f"Media Description: {profile.get('media_description') or '-'}")
            st.info("style_vector는 10x10 Grid가 아니라 FM 능력치 기반 24차원 proxy vector입니다.")

            attributes = parse_json_field(profile.get("attributes_jsonb"))
            important = {
                key: attributes.get(key)
                for key in ["Acc", "Pac", "Sta", "Dri", "Fin", "Pas", "Vis", "Wor", "Tea", "Det"]
                if key in attributes
            }
            st.json(important)

    with pcol2:
        st.subheader("Mentality Analysis")

        if profile is None:
            st.warning("멘탈리티 proxy 데이터가 없습니다.")
        else:
            mentality = parse_json_field(profile.get("mentality_jsonb"))
            st.info("현재 멘탈리티 데이터는 기사/스카우팅 원문 분석이 아니라 FM 속성 기반 proxy data입니다.")
            st.json(mentality)

    st.subheader("Recent Appearances")
    appearances = get_appearances(player["player_id"], limit=20)

    if appearances.empty:
        st.info("최근 출전 기록이 없습니다.")
    else:
        st.dataframe(appearances, use_container_width=True, hide_index=True)


def render_legend_matching():
    st.title("Legend Matching")
    player = require_selected_player()

    if player is None:
        return

    profile = get_player_profile(player)

    st.info(
        "현재 화면은 FM 기반 proxy style_vector(24차원)를 활용한 유사 선수 후보 UI입니다. "
        "10x10 Grid 기반 레전드 매칭은 이번 HW#5 범위에서 제외되며 향후 고도화 예정입니다."
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Selected Prospect")
        st.write(f"이름: {player.get('name')}")
        st.write(f"소속팀: {player.get('current_club_name') or '-'}")
        st.write(f"포지션: {player.get('position') or '-'}")

        if profile:
            st.write(f"Profile ID: {profile.get('profile_id')}")
            st.write(f"FM 설명: {profile.get('media_description') or '-'}")

    with col2:
        st.subheader("Similar Player Candidates")

        if profile is None:
            st.warning("player_profiles 데이터가 없어 유사 후보를 조회할 수 없습니다.")
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
        else:
            st.dataframe(similar, use_container_width=True, hide_index=True)


def build_simulation_result(env_settings):
    training = env_settings["training_intensity"]
    playing_time = env_settings["playing_time_opportunity"]
    difficulty = env_settings["league_difficulty"]
    risk_level = env_settings["risk_level"]

    difficulty_factor = {
        "low": 8,
        "medium": 0,
        "high": -8,
        "elite": -14,
    }[difficulty]

    choice_factor = {
        "stay": 4,
        "loan": 8,
        "transfer": 2,
    }[env_settings["career_choice"]]

    risk_factor = {
        "safe": -4,
        "normal": 0,
        "aggressive": 5,
    }[risk_level]

    growth_score = round(
        45 + training * 12 + playing_time * 25 + difficulty_factor + choice_factor + risk_factor
    )
    growth_score = max(0, min(100, growth_score))

    injury_risk = round(0.08 + training * 0.06 + {"safe": -0.02, "normal": 0.04, "aggressive": 0.1}[risk_level], 2)
    injury_risk = max(0.01, min(0.75, injury_risk))

    success_probability = round((growth_score / 100) * (1 - injury_risk), 2)

    return {
        "prototype_growth_score": growth_score,
        "prototype_success_probability": success_probability,
        "prototype_injury_risk": injury_risk,
        "message": (
            "현재 결과는 실제 예측 모델이 아니라 UI 흐름 검증을 위한 "
            "프로토타입 시뮬레이션 결과입니다."
        ),
    }


def render_career_simulation():
    st.title("Career Simulation")
    player = require_selected_player()

    if player is None:
        return

    st.caption("입력값을 env_settings JSON으로 구성하고, 간단한 prototype simulation_result를 생성합니다.")

    col1, col2 = st.columns(2)

    with col1:
        training = st.slider("훈련 강도", 0.5, 2.0, 1.2, 0.1)
        playing_time = st.slider("출전 기회", 0.0, 1.0, 0.6, 0.05)
        league_difficulty = st.selectbox(
            "리그 난이도",
            ["low", "medium", "high", "elite"],
            index=1,
        )

    with col2:
        career_choice = st.radio("커리어 선택", ["stay", "loan", "transfer"], horizontal=True)
        risk_level = st.radio("리스크 성향", ["safe", "normal", "aggressive"], horizontal=True, index=1)

    env_settings = {
        "training_intensity": training,
        "playing_time_opportunity": playing_time,
        "league_difficulty": league_difficulty,
        "career_choice": career_choice,
        "risk_level": risk_level,
    }

    simulation_result = build_simulation_result(env_settings)

    st.session_state["env_settings"] = env_settings
    st.session_state["simulation_result"] = simulation_result

    st.subheader("Simulation Preview")
    c1, c2, c3 = st.columns(3)
    c1.metric("Growth Score", simulation_result["prototype_growth_score"])
    c2.metric("Success Probability", simulation_result["prototype_success_probability"])
    c3.metric("Injury Risk", simulation_result["prototype_injury_risk"])

    chart_data = pd.DataFrame(
        {
            "stage": ["Now", "Year 1", "Year 2", "Year 3"],
            "score": [
                max(20, simulation_result["prototype_growth_score"] - 18),
                max(25, simulation_result["prototype_growth_score"] - 9),
                simulation_result["prototype_growth_score"],
                min(100, simulation_result["prototype_growth_score"] + 5),
            ],
        }
    )
    st.line_chart(chart_data, x="stage", y="score")

    col_json1, col_json2 = st.columns(2)
    with col_json1:
        st.write("env_settings")
        st.json(env_settings)

    with col_json2:
        st.write("simulation_result")
        st.json(simulation_result)


def generate_template_report(player, profile, env_settings, simulation_result):
    profile_name = profile.get("name") if profile else player.get("name")
    mentality = parse_json_field(profile.get("mentality_jsonb")) if profile else {}
    mentality_score = mentality.get("mentality_score", "N/A")

    return f"""
Prototype AI Scouting Report

Player: {player.get('name')} ({profile_name})
Club: {player.get('current_club_name') or '-'}
Position: {player.get('position') or '-'} / {player.get('sub_position') or '-'}

Current Strengths:
- Current market value and appearance history are available in the connected Supabase DB.
- FM proxy attributes can be used as an early style and mentality signal.
- Mentality proxy score: {mentality_score}

Development Focus:
- Training intensity: {env_settings.get('training_intensity')}
- Playing time opportunity: {env_settings.get('playing_time_opportunity')}
- League difficulty: {env_settings.get('league_difficulty')}
- Career choice: {env_settings.get('career_choice')}
- Risk level: {env_settings.get('risk_level')}

Prototype Simulation Summary:
- Growth score: {simulation_result.get('prototype_growth_score')}
- Success probability: {simulation_result.get('prototype_success_probability')}
- Injury risk: {simulation_result.get('prototype_injury_risk')}

Recommendation:
This is a template-based scouting report for the HW#5 prototype. It does not call Gemini API yet.
Future versions can replace this text generator with an actual LLM while keeping the same scouting_notes DB storage flow.
""".strip()


def render_ai_report():
    st.title("AI Scouting Report")
    player = require_selected_player()

    if player is None:
        return

    profile = get_player_profile(player)
    env_settings = st.session_state.get("env_settings")
    simulation_result = st.session_state.get("simulation_result")

    if env_settings is None or simulation_result is None:
        st.warning("먼저 Career Simulation 화면에서 시뮬레이션 설정을 생성해 주세요.")
        return

    st.info(
        "현재 리포트는 실제 Gemini API 결과가 아니라 template-based prototype report입니다. "
        "향후 Gemini API를 연결하면 같은 gemini_report 컬럼에 실제 LLM 리포트를 저장할 수 있습니다."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Selected Player")
        st.write(f"이름: {player.get('name')}")
        st.write(f"소속팀: {player.get('current_club_name') or '-'}")
        st.write(f"포지션: {player.get('position') or '-'}")

    with col2:
        st.subheader("Simulation Settings")
        st.json(env_settings)

    if st.button("Generate Prototype Report", type="primary"):
        st.session_state["generated_report"] = generate_template_report(
            player,
            profile,
            env_settings,
            simulation_result,
        )

    report = st.session_state.get("generated_report")

    if report:
        st.subheader("Template-based Scouting Report")
        st.text_area("Report Draft", report, height=360)

        if st.button("Save to Scouting Notes"):
            try:
                saved = insert_scouting_note(
                    player_id=player["player_id"],
                    profile_id=profile.get("profile_id") if profile else None,
                    env_settings=env_settings,
                    simulation_result=simulation_result,
                    report=report,
                )
                st.success(f"스카우팅 노트가 저장되었습니다. note_id: {saved['note_id']}")
            except Exception as exc:
                st.error("스카우팅 노트 저장 중 오류가 발생했습니다.")
                st.info(
                    "현재 과제 범위에서는 테이블 구조를 변경하지 않습니다. "
                    "만약 user_id null 제약 때문에 실패한다면 임시 테스트용 UUID 사용을 대안으로 검토할 수 있습니다."
                )
                with st.expander("개발 확인용 오류"):
                    st.exception(exc)


def render_my_notes():
    st.title("My Scouting Notes")
    st.info(
        "현재는 Supabase Auth가 연결되지 않은 프로토타입 단계이므로 사용자별 필터링은 적용되지 않습니다. "
        "향후 Auth와 RLS를 적용하면 user_id 기준으로 본인의 스카우팅 노트만 조회하도록 확장할 예정입니다."
    )

    try:
        notes = get_scouting_notes(limit=20)
    except Exception as exc:
        st.error("스카우팅 노트 조회 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)
        return

    if notes.empty:
        st.info("저장된 스카우팅 노트가 없습니다.")
        return

    for _, note in notes.iterrows():
        title = f"{note.get('player_name') or note.get('player_id')} | {note.get('created_at')}"
        with st.expander(title):
            st.write(f"note_id: {note.get('note_id')}")
            st.write(f"player_id: {note.get('player_id')}")
            st.write(f"profile_id: {note.get('profile_id')}")
            st.write("env_settings")
            st.json(parse_json_field(note.get("env_settings")))
            st.write("simulation_result")
            st.json(parse_json_field(note.get("simulation_result")))
            st.write("report")
            st.text(note.get("gemini_report") or "")


def render_prospect_search():
    st.title("유망주 검색")

    selected_name = st.session_state.get("selected_player_name")
    if selected_name:
        st.success(f"현재 선택된 선수: {selected_name}")
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
                ]:
                    st.session_state.pop(key, None)
            st.success("선수가 선택되었습니다. 유망주 통합 분석 화면에서 확인할 수 있습니다.")
            st.info("왼쪽 메뉴에서 '유망주 통합 분석'으로 이동하세요.")


def render_db_status():
    st.title("DB Status")
    st.caption("HW#4에서 구축한 Supabase DB가 HW#5 앱과 정상 연결되는지 확인하는 보조 화면입니다.")

    try:
        count_data = []
        for table in TABLES:
            count_data.append({"table_name": table, "row_count": table_count(table)})

        st.success("Supabase 연결 성공")
        st.dataframe(pd.DataFrame(count_data), use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error("Supabase 연결 또는 테이블 조회 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)
        return

    table_name = st.selectbox("미리 볼 테이블", TABLES)
    limit = st.slider("조회 행 수", 5, 100, 30, 5)

    try:
        df = preview_table(table_name, limit=limit)
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error("테이블 미리보기 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)


def render_prospect_search():
    st.title("Prospect Search")
    st.caption("분석할 유망주를 검색하고 선택합니다. 선택 결과는 다른 화면에서 재사용됩니다.")
    st.info("유망주 기준: FM 데이터 기준 만 23세 이하")

    max_age = st.slider("최대 나이", min_value=16, max_value=30, value=23, step=1)

    try:
        positions = get_distinct_positions(max_age=max_age)
    except Exception:
        positions = ["All"]

    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

    with col1:
        keyword = st.text_input("선수 이름", placeholder="예: Bellingham, Yamal, Son")

    with col2:
        position = st.selectbox("포지션", positions)

    with col3:
        nationality = st.text_input("국적", placeholder="예: Korea")

    with col4:
        club = st.text_input("소속팀", placeholder="예: Dortmund")

    try:
        results = search_players(
            keyword=keyword,
            position=position,
            nationality=nationality,
            club=club,
            max_age=max_age,
        )
    except Exception as exc:
        st.error("선수 검색 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)
        return

    if results.empty:
        st.warning("검색 결과가 없습니다. 현재 Prospect Search는 player_profiles.age가 있는 선수만 조회합니다.")
        return

    display_cols = [
        "player_id",
        "name",
        "age",
        "current_club_name",
        "country_of_citizenship",
        "position",
        "sub_position",
        "market_value_in_eur",
    ]

    st.dataframe(results[display_cols], use_container_width=True, hide_index=True)

    labels = {}
    for _, row in results.iterrows():
        label = (
            f"{row['name']} | age {row.get('age') or '-'} | "
            f"{row.get('current_club_name') or '-'} | "
            f"{row.get('position') or '-'} | ID {row['player_id']}"
        )
        labels[label] = int(row["player_id"])

    selected_label = st.selectbox("분석할 선수 선택", list(labels.keys()))

    if st.button("선택한 선수 저장", type="primary"):
        st.session_state["selected_player_id"] = labels[selected_label]
        st.success("선택한 선수를 저장했습니다. 다른 화면에서 이 선수를 기준으로 분석합니다.")

    show_selected_player_banner()


ATTRIBUTE_LABELS = {
    "Acc": ("가속도", "순간적으로 속도를 끌어올리는 능력"),
    "Pac": ("주력", "최고 속도와 전력 질주 능력"),
    "Sta": ("지구력", "경기 내내 활동량을 유지하는 능력"),
    "Str": ("힘", "몸싸움과 버티는 힘"),
    "Agi": ("민첩성", "방향 전환과 몸놀림"),
    "Bal": ("균형감", "접촉 상황에서 자세를 유지하는 능력"),
    "Dri": ("드리블", "공을 몰고 전진하는 능력"),
    "Fir": ("퍼스트 터치", "첫 볼 컨트롤의 안정성"),
    "Fin": ("결정력", "찬스를 득점으로 연결하는 능력"),
    "OtB": ("오프더볼", "공이 없을 때 공간을 찾는 움직임"),
    "Cmp": ("침착성", "압박 상황에서 판단을 유지하는 능력"),
    "Pas": ("패스", "동료에게 공을 전달하는 정확도"),
    "Vis": ("시야", "전진 패스와 기회 창출을 보는 능력"),
    "Tec": ("기술", "볼을 다루는 전반적인 세련도"),
    "Wor": ("활동량", "수비와 공격을 오가며 뛰는 성향"),
    "Tea": ("팀워크", "전술과 동료 움직임에 맞추는 능력"),
    "Det": ("의지력", "성장과 경기 몰입을 버티는 성향"),
    "Dec": ("판단력", "상황에 맞는 선택을 하는 능력"),
    "Ant": ("예측력", "다음 장면을 먼저 읽는 능력"),
    "Pos": ("위치선정", "수비 위치와 공간 점유 능력"),
    "Tck": ("태클", "공을 빼앗는 능력"),
    "Mar": ("마킹", "상대 선수를 추적하는 능력"),
    "Ldr": ("리더십", "팀을 이끄는 성향"),
    "Agg": ("적극성", "경합과 압박에 참여하는 성향"),
    "Amb": ("야망", "높은 목표를 추구하는 성향"),
    "Loy": ("충성심", "소속팀과 관계를 유지하는 성향"),
    "Cons": ("꾸준함", "경기력 변동을 줄이는 성향"),
    "Pres": ("압박 대처", "부담이 큰 경기에서 버티는 성향"),
    "Prof": ("프로의식", "자기관리와 훈련 태도"),
    "Spor": ("스포츠맨십", "페어플레이와 경기 태도"),
    "Temp": ("감정 조절", "흥분 상황에서 균형을 유지하는 성향"),
    "Jum": ("점프력", "공중볼 상황의 도약 능력"),
    "Hea": ("헤더", "머리로 공을 처리하는 능력"),
}

ATTRIBUTE_GROUPS = {
    "공격/마무리": ["Fin", "OtB", "Cmp", "Dri", "Fir"],
    "스피드/피지컬": ["Acc", "Pac", "Sta", "Str", "Agi", "Bal", "Jum"],
    "패스/창의성": ["Pas", "Vis", "Tec", "Tea", "Dec"],
    "멘탈/수비 기여": ["Det", "Wor", "Ant", "Pos", "Tck", "Mar", "Agg"],
}

MENTALITY_KEYS = ["Det", "Wor", "Tea", "Ldr", "Prof", "Pres", "Cons", "Temp", "Spor", "Agg", "Loy", "Amb"]


def apply_theme():
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(17, 94, 89, 0.18), transparent 32rem),
                linear-gradient(135deg, #071014 0%, #0b1720 48%, #07131a 100%);
            color: #e5eef2;
        }
        section[data-testid="stSidebar"] {
            background: #071014;
            border-right: 1px solid rgba(45, 212, 191, 0.18);
        }
        h1, h2, h3 {
            color: #eef8f6;
            letter-spacing: 0;
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, rgba(15, 118, 110, 0.28), rgba(15, 23, 42, 0.72));
            border: 1px solid rgba(45, 212, 191, 0.24);
            border-radius: 8px;
            padding: 14px 16px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.22);
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 8px;
            overflow: hidden;
        }
        .scout-panel {
            background: rgba(15, 23, 42, 0.78);
            border: 1px solid rgba(45, 212, 191, 0.22);
            border-radius: 8px;
            padding: 16px;
            margin: 8px 0 14px 0;
            box-shadow: 0 18px 42px rgba(0, 0, 0, 0.26);
        }
        .profile-card {
            display: flex;
            gap: 18px;
            align-items: center;
        }
        .profile-photo {
            width: 132px;
            height: 132px;
            object-fit: cover;
            border-radius: 8px;
            border: 1px solid rgba(45, 212, 191, 0.38);
            background: #0f172a;
        }
        .badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        .scout-badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 5px 10px;
            background: rgba(20, 184, 166, 0.13);
            border: 1px solid rgba(45, 212, 191, 0.28);
            color: #ccfbf1;
            font-size: 0.85rem;
            white-space: nowrap;
        }
        .muted {
            color: #94a3b8;
            font-size: 0.92rem;
        }
        .section-note {
            color: #b6c7ce;
            margin-bottom: 8px;
        }
        .report-block {
            background: rgba(2, 6, 23, 0.42);
            border-left: 3px solid #14b8a6;
            border-radius: 6px;
            padding: 14px 16px;
            margin-bottom: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def attr_label(key, with_code=True):
    label = ATTRIBUTE_LABELS.get(key, (key, ""))[0]
    return f"{label} ({key})" if with_code else label


def attr_description(key):
    return ATTRIBUTE_LABELS.get(key, (key, "FM proxy attribute"))[1]


def numeric_attr(attributes, key):
    try:
        value = attributes.get(key)
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def average_attrs(attributes, keys):
    values = [numeric_attr(attributes, key) for key in keys]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def score_level(value):
    if value is None:
        return "데이터 없음"
    if value >= 15:
        return "상"
    if value >= 11:
        return "중"
    return "보완 필요"


def attributes_long_df(attributes, groups=None):
    rows = []
    groups = groups or ATTRIBUTE_GROUPS
    for group, keys in groups.items():
        for key in keys:
            value = numeric_attr(attributes, key)
            if value is not None:
                rows.append(
                    {
                        "group": group,
                        "attribute": attr_label(key),
                        "value": value,
                        "description": attr_description(key),
                    }
                )
    return pd.DataFrame(rows)


def attr_bar_chart(df, title=None, height=260):
    if df.empty:
        st.info("표시할 속성 데이터가 없습니다.")
        return

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("value:Q", scale=alt.Scale(domain=[0, 20]), title="proxy score"),
            y=alt.Y("attribute:N", sort="-x", title=None),
            color=alt.Color("group:N", legend=alt.Legend(title="그룹")),
            tooltip=["group:N", "attribute:N", "value:Q", "description:N"],
        )
        .properties(height=height, title=title)
    )
    st.altair_chart(chart, use_container_width=True)


def summary_scores(attributes, mentality):
    mentality_basis = mentality.get("basis", {}) if isinstance(mentality, dict) else {}
    return {
        "공격 지수": average_attrs(attributes, ["Fin", "OtB", "Dri", "Fir", "Cmp"]),
        "창의성 지수": average_attrs(attributes, ["Pas", "Vis", "Tec", "Dec", "Tea"]),
        "피지컬 지수": average_attrs(attributes, ["Acc", "Pac", "Sta", "Str", "Agi", "Bal"]),
        "멘탈 점수": mentality.get("mentality_score") if isinstance(mentality, dict) else average_attrs(mentality_basis, MENTALITY_KEYS),
    }


def top_attributes(attributes, keys=None, limit=3):
    keys = keys or list(ATTRIBUTE_LABELS.keys())
    rows = []
    for key in keys:
        value = numeric_attr(attributes, key)
        if value is not None:
            rows.append((key, value))
    rows = sorted(rows, key=lambda item: item[1], reverse=True)
    return rows[:limit]


def template_player_sentence(attributes, mentality):
    tops = top_attributes(attributes, ["Fin", "Acc", "Pac", "Dri", "Pas", "Vis", "Wor", "Tea", "Det"])
    if not tops:
        return "template-based explanation: 표시할 주요 proxy 속성이 부족합니다."

    labels = [attr_label(key, with_code=False) for key, _ in tops[:2]]
    mentality_score = mentality.get("mentality_score") if isinstance(mentality, dict) else None
    mental_text = f" 멘탈 proxy 점수는 {mentality_score}점으로 요약됩니다." if mentality_score is not None else ""
    return f"template-based explanation: 이 선수는 {', '.join(labels)}이 돋보이는 유형으로 요약됩니다.{mental_text}"


def render_player_profile_panel(player, profile=None):
    age = profile.get("age") if profile else None
    image_url = player.get("image_url") or ""
    photo_html = (
        f'<img class="profile-photo" src="{image_url}" />'
        if image_url
        else '<div class="profile-photo"></div>'
    )
    badges = [
        player.get("position"),
        player.get("sub_position"),
        player.get("foot"),
        player.get("country_of_citizenship"),
        f"Age {age}" if age is not None else None,
    ]
    badge_html = "".join(f'<span class="scout-badge">{badge}</span>' for badge in badges if badge)
    st.markdown(
        f"""
        <div class="scout-panel profile-card">
            {photo_html}
            <div>
                <div class="muted">Selected Prospect</div>
                <h2 style="margin: 0 0 4px 0;">{player.get('name') or '-'}</h2>
                <div>{player.get('current_club_name') or '-'}</div>
                <div class="badge-row">{badge_html}</div>
                <div class="muted" style="margin-top: 10px;">
                    현재 시장가치 {money(player.get('market_value_in_eur'))} · 최고 {money(player.get('highest_market_value_in_eur'))}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(scores):
    cols = st.columns(len(scores))
    for col, (label, value) in zip(cols, scores.items()):
        display = "-" if value is None else value
        col.metric(label, display, score_level(value))


def readable_setting(label, value):
    maps = {
        "training_intensity": "높음" if value >= 1.4 else "중간" if value >= 0.9 else "낮음",
        "playing_time_opportunity": "높음" if value >= 0.7 else "중간" if value >= 0.35 else "낮음",
        "league_difficulty": {"low": "낮음", "medium": "중간", "high": "높음", "elite": "최상위"}.get(value, value),
        "career_choice": {"stay": "잔류", "loan": "임대", "transfer": "이적"}.get(value, value),
        "risk_level": {"safe": "안정형", "normal": "균형형", "aggressive": "공격형"}.get(value, value),
    }
    return maps.get(label, value)


def get_report_sections(player, profile, env_settings, simulation_result):
    attributes = parse_json_field(profile.get("attributes_jsonb")) if profile else {}
    mentality = parse_json_field(profile.get("mentality_jsonb")) if profile else {}
    scores = summary_scores(attributes, mentality)
    tops = top_attributes(attributes, limit=3)
    strengths = [f"{attr_label(key)}: {value:g}/20" for key, value in tops] or ["연결된 FM proxy 속성이 부족합니다."]
    weak_rows = []
    for key, value in sorted(
        [(key, numeric_attr(attributes, key)) for key in ATTRIBUTE_LABELS],
        key=lambda item: 99 if item[1] is None else item[1],
    ):
        if value is not None:
            weak_rows.append(f"{attr_label(key)}: {value:g}/20")
        if len(weak_rows) == 3:
            break

    return {
        "Overall Summary": (
            f"{player.get('name')}은 현재 {player.get('position') or '-'} 포지션의 유망주로, "
            f"proxy summary 기준 공격 {scores.get('공격 지수') or '-'}, "
            f"창의성 {scores.get('창의성 지수') or '-'}, 피지컬 {scores.get('피지컬 지수') or '-'}로 요약됩니다."
        ),
        "Strengths": strengths,
        "Weaknesses": weak_rows or ["보완점 산출을 위한 속성 데이터가 부족합니다."],
        "Development Recommendation": (
            f"훈련 강도는 {readable_setting('training_intensity', env_settings.get('training_intensity'))}, "
            f"출전 기회는 {readable_setting('playing_time_opportunity', env_settings.get('playing_time_opportunity'))}로 설정되어 있습니다. "
            "template-based explanation 기준으로 경기 경험과 핵심 강점 강화의 균형이 중요합니다."
        ),
        "Career Advice": (
            f"커리어 선택은 {readable_setting('career_choice', env_settings.get('career_choice'))}, "
            f"리스크 성향은 {readable_setting('risk_level', env_settings.get('risk_level'))}입니다. "
            f"prototype 성공 확률은 {simulation_result.get('prototype_success_probability')}로 계산되었습니다."
        ),
        "Note": "이 리포트는 실제 Gemini API 결과가 아닌 template-based prototype report입니다.",
    }


def sections_to_report_text(sections):
    lines = ["Prototype AI Scouting Report"]
    for title, content in sections.items():
        lines.append("")
        lines.append(title)
        if isinstance(content, list):
            lines.extend(f"- {item}" for item in content)
        else:
            lines.append(str(content))
    return "\n".join(lines)


def render_dashboard():
    st.title("Integrated Analysis Dashboard")
    player = require_selected_player()
    if player is None:
        return

    profile = get_player_profile(player)
    render_player_profile_panel(player, profile)

    if profile is None:
        st.warning("연결된 player_profiles 데이터가 없어 FM proxy summary를 표시할 수 없습니다.")
        return

    attributes = parse_json_field(profile.get("attributes_jsonb"))
    mentality = parse_json_field(profile.get("mentality_jsonb"))
    scores = summary_scores(attributes, mentality)

    st.subheader("Proxy Summary")
    st.caption("공식 FM 평가가 아니라 현재 CSV/FM proxy attribute를 요약한 prototype summary입니다.")
    render_metric_cards(scores)
    st.markdown(f'<div class="section-note">{template_player_sentence(attributes, mentality)}</div>', unsafe_allow_html=True)

    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("FM Proxy Style Summary")
        st.caption("축약어 원문 대신 사용자 친화적인 라벨과 그룹별 막대 차트로 재구성했습니다.")
        attr_bar_chart(attributes_long_df(attributes), height=360)

    with right:
        st.subheader("Mentality Analysis")
        st.caption("FM 멘탈 속성 기반 proxy data입니다. 기사/스카우팅 원문 분석 결과가 아닙니다.")
        mentality_basis = mentality.get("basis", {}) if isinstance(mentality, dict) else {}
        mental_df = attributes_long_df(mentality_basis, {"멘탈리티": MENTALITY_KEYS})
        attr_bar_chart(mental_df, height=300)
        interpretations = mentality.get("interpretation", []) if isinstance(mentality, dict) else []
        if interpretations:
            st.markdown('<div class="scout-panel"><b>Template-based note</b><br>' + "<br>".join(interpretations[:3]) + "</div>", unsafe_allow_html=True)

    st.divider()
    c1, c2 = st.columns([1.15, 1])
    with c1:
        st.subheader("Market Value Trend")
        valuations = get_valuations(player["player_id"])
        if valuations.empty:
            st.info("시장가치 데이터가 없습니다.")
        else:
            valuations["date"] = pd.to_datetime(valuations["date"])
            valuations["market_value_in_eur"] = pd.to_numeric(valuations["market_value_in_eur"], errors="coerce")
            chart = (
                alt.Chart(valuations)
                .mark_area(line={"color": "#2dd4bf"}, color=alt.Gradient(gradient="linear", stops=[
                    alt.GradientStop(color="rgba(45,212,191,0.45)", offset=0),
                    alt.GradientStop(color="rgba(15,23,42,0.08)", offset=1),
                ]))
                .encode(
                    x=alt.X("date:T", title=None),
                    y=alt.Y("market_value_in_eur:Q", title="Market value EUR"),
                    tooltip=["date:T", "market_value_in_eur:Q", "current_club_name:N"],
                )
                .properties(height=260)
            )
            st.altair_chart(chart, use_container_width=True)

    with c2:
        st.subheader("Recent Appearances")
        appearances = get_appearances(player["player_id"], limit=10)
        if appearances.empty:
            st.info("최근 출전 기록이 없습니다.")
        else:
            st.dataframe(appearances, use_container_width=True, hide_index=True)

    with st.expander("상세 데이터 보기"):
        st.write("attributes_jsonb")
        st.json(attributes)
        st.write("mentality_jsonb")
        st.json(mentality)


def render_legend_matching():
    st.title("Legend Matching")
    player = require_selected_player()
    if player is None:
        return

    profile = get_player_profile(player)
    render_player_profile_panel(player, profile)
    st.info("FM 기반 proxy style_vector(24차원)를 활용한 pgvector 유사 선수 후보입니다. 10x10 Grid 기반 레전드 매칭은 향후 고도화 범위입니다.")

    if profile is None:
        st.warning("player_profiles 데이터가 없어 유사 후보를 조회할 수 없습니다.")
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

    st.subheader("Similar Player Cards")
    rows = similar.to_dict("records")
    for start in range(0, len(rows), 2):
        cols = st.columns(2)
        for col, row in zip(cols, rows[start:start + 2]):
            with col:
                strength = "style_vector 근접도"
                st.markdown(
                    f"""
                    <div class="scout-panel">
                        <div class="muted">Similarity Candidate</div>
                        <h3 style="margin: 2px 0 8px 0;">{row.get('name') or '-'}</h3>
                        <div class="badge-row">
                            <span class="scout-badge">{row.get('position') or '-'}</span>
                            <span class="scout-badge">{row.get('club') or '-'}</span>
                            <span class="scout-badge">Age {row.get('age') or '-'}</span>
                        </div>
                        <h2 style="margin: 12px 0 0 0; color: #5eead4;">{row.get('similarity')}</h2>
                        <div class="muted">유사도 점수</div>
                        <p style="margin-top: 10px;">주요 강점: {strength}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with st.expander("테이블로 보기"):
        st.dataframe(similar, use_container_width=True, hide_index=True)


def render_career_simulation():
    st.title("Career Simulation")
    player = require_selected_player()
    if player is None:
        return

    profile = get_player_profile(player)
    render_player_profile_panel(player, profile)
    st.caption("실제 예측 모델이 아니라 HW#5 UI 흐름 검증을 위한 prototype simulation입니다.")

    left, right = st.columns([1, 1.25])
    with left:
        st.subheader("Scenario Controls")
        training = st.slider("훈련 강도", 0.5, 2.0, 1.2, 0.1)
        playing_time = st.slider("출전 기회", 0.0, 1.0, 0.6, 0.05)
        league_difficulty = st.selectbox("리그 난이도", ["low", "medium", "high", "elite"], index=1)
        career_choice = st.radio("커리어 선택", ["stay", "loan", "transfer"], horizontal=True)
        risk_level = st.radio("리스크 성향", ["safe", "normal", "aggressive"], horizontal=True, index=1)

    env_settings = {
        "training_intensity": training,
        "playing_time_opportunity": playing_time,
        "league_difficulty": league_difficulty,
        "career_choice": career_choice,
        "risk_level": risk_level,
    }
    simulation_result = build_simulation_result(env_settings)
    st.session_state["env_settings"] = env_settings
    st.session_state["simulation_result"] = simulation_result

    with right:
        st.subheader("Scenario Summary")
        summary_cols = st.columns(3)
        summary_cols[0].metric("성장 점수", simulation_result["prototype_growth_score"])
        summary_cols[1].metric("성공 확률", simulation_result["prototype_success_probability"])
        summary_cols[2].metric("부상 리스크", simulation_result["prototype_injury_risk"])

        setting_df = pd.DataFrame(
            [
                {"항목": "훈련 강도", "설정": readable_setting("training_intensity", training), "원값": training},
                {"항목": "출전 기회", "설정": readable_setting("playing_time_opportunity", playing_time), "원값": playing_time},
                {"항목": "리그 난이도", "설정": readable_setting("league_difficulty", league_difficulty), "원값": league_difficulty},
                {"항목": "커리어 선택", "설정": readable_setting("career_choice", career_choice), "원값": career_choice},
                {"항목": "리스크 성향", "설정": readable_setting("risk_level", risk_level), "원값": risk_level},
            ]
        )
        st.dataframe(setting_df, use_container_width=True, hide_index=True)

    chart_data = pd.DataFrame(
        {
            "stage": ["Now", "Year 1", "Year 2", "Year 3"],
            "score": [
                max(20, simulation_result["prototype_growth_score"] - 18),
                max(25, simulation_result["prototype_growth_score"] - 9),
                simulation_result["prototype_growth_score"],
                min(100, simulation_result["prototype_growth_score"] + 5),
            ],
        }
    )
    chart = (
        alt.Chart(chart_data)
        .mark_line(point=alt.OverlayMarkDef(size=90), color="#2dd4bf", strokeWidth=3)
        .encode(
            x=alt.X("stage:N", title=None),
            y=alt.Y("score:Q", scale=alt.Scale(domain=[0, 100]), title="prototype score"),
            tooltip=["stage:N", "score:Q"],
        )
        .properties(height=280)
    )
    st.subheader("Prototype Growth Path")
    st.altair_chart(chart, use_container_width=True)
    st.markdown('<div class="section-note">template-based explanation: 현재 시뮬레이션은 입력 조건에 따라 성장 가능성과 리스크를 단순 점수화한 프로토타입입니다.</div>', unsafe_allow_html=True)

    with st.expander("상세 JSON 보기"):
        st.write("env_settings")
        st.json(env_settings)
        st.write("simulation_result")
        st.json(simulation_result)


def render_ai_report():
    st.title("AI Scouting Report")
    player = require_selected_player()
    if player is None:
        return

    profile = get_player_profile(player)
    env_settings = st.session_state.get("env_settings")
    simulation_result = st.session_state.get("simulation_result")
    if env_settings is None or simulation_result is None:
        st.warning("먼저 Career Simulation 화면에서 시뮬레이션 설정을 생성해 주세요.")
        return

    render_player_profile_panel(player, profile)
    st.info("현재 리포트는 실제 Gemini API 결과가 아니라 template-based prototype report입니다.")

    if st.button("Generate Prototype Report", type="primary"):
        sections = get_report_sections(player, profile, env_settings, simulation_result)
        st.session_state["generated_report_sections"] = sections
        st.session_state["generated_report"] = sections_to_report_text(sections)

    sections = st.session_state.get("generated_report_sections")
    report = st.session_state.get("generated_report")

    if sections:
        st.subheader("Template-based Scouting Report")
        for title in ["Overall Summary", "Strengths", "Weaknesses", "Development Recommendation", "Career Advice", "Note"]:
            content = sections.get(title)
            if not content:
                continue
            if isinstance(content, list):
                body = "<br>".join(f"- {item}" for item in content)
            else:
                body = str(content)
            st.markdown(f'<div class="report-block"><b>{title}</b><br>{body}</div>', unsafe_allow_html=True)

        with st.expander("리포트 원문 보기"):
            st.text(report)
            st.write("env_settings")
            st.json(env_settings)
            st.write("simulation_result")
            st.json(simulation_result)

        st.markdown('<div class="scout-panel">', unsafe_allow_html=True)
        if st.button("Save to Scouting Notes"):
            try:
                saved = insert_scouting_note(
                    player_id=player["player_id"],
                    profile_id=profile.get("profile_id") if profile else None,
                    env_settings=env_settings,
                    simulation_result=simulation_result,
                    report=report,
                )
                st.success(f"스카우팅 노트가 저장되었습니다. note_id: {saved['note_id']}")
            except Exception as exc:
                st.error("스카우팅 노트 저장 중 오류가 발생했습니다.")
                st.info("현재 과제 범위에서는 테이블 구조를 변경하지 않습니다. user_id null 저장이 실패하면 임시 테스트용 UUID 사용을 대안으로 검토할 수 있습니다.")
                with st.expander("개발 확인용 오류"):
                    st.exception(exc)
        st.markdown("</div>", unsafe_allow_html=True)


def apply_theme():
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(135deg, #101820 0%, #13202a 50%, #0f1a24 100%);
            color: #f1f5f9;
        }
        section[data-testid="stSidebar"] {
            background: #0b131b;
            border-right: 1px solid rgba(20, 184, 166, 0.22);
        }
        h1, h2, h3 {
            color: #f8fafc;
            letter-spacing: 0;
        }
        p, li, span, div {
            color: inherit;
        }
        div[data-testid="stMetric"] {
            background: #182633;
            border: 1px solid rgba(45, 212, 191, 0.22);
            border-radius: 8px;
            padding: 14px 16px;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 8px;
            overflow: hidden;
        }
        .scout-panel {
            background: #182633;
            border: 1px solid rgba(45, 212, 191, 0.20);
            border-radius: 8px;
            padding: 18px;
            margin: 10px 0 16px 0;
        }
        .profile-card {
            display: flex;
            gap: 20px;
            align-items: center;
        }
        .profile-photo {
            width: 138px;
            height: 138px;
            object-fit: cover;
            border-radius: 8px;
            border: 1px solid rgba(45, 212, 191, 0.35);
            background: #0f172a;
            flex: 0 0 auto;
        }
        .badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        .scout-badge {
            display: inline-flex;
            border-radius: 999px;
            padding: 5px 10px;
            background: rgba(20, 184, 166, 0.15);
            border: 1px solid rgba(45, 212, 191, 0.28);
            color: #ccfbf1;
            font-size: 0.86rem;
            white-space: nowrap;
        }
        .muted {
            color: #b7c4cf;
            font-size: 0.92rem;
        }
        .section-note {
            color: #d5e2ea;
            background: rgba(15, 23, 42, 0.42);
            border-left: 3px solid #14b8a6;
            border-radius: 6px;
            padding: 12px 14px;
            margin: 8px 0 14px 0;
        }
        .report-block {
            background: #182633;
            border-left: 3px solid #14b8a6;
            border-radius: 8px;
            padding: 15px 17px;
            margin-bottom: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


ATTRIBUTE_LABELS.update(
    {
        None: ("알 수 없음", "정의되지 않은 능력치"),
        "Str": ("몸싸움", "몸싸움과 버티는 힘"),
        "Jum": ("점프력", "공중볼 상황의 도약 능력"),
        "Bal": ("균형감각", "접촉 상황에서 자세를 유지하는 능력"),
        "Tec": ("개인기", "공을 다루는 전반적인 기술"),
        "Bra": ("적극성", "위험을 감수하고 경합에 참여하는 성향"),
        "Cro": ("크로스", "측면에서 공을 투입하는 능력"),
        "Lon": ("중거리슛", "먼 거리에서 슈팅하는 능력"),
        "Sport": ("스포츠맨십", "페어플레이와 경기 태도"),
    }
)

ATTRIBUTE_GROUPS = {
    "공격 능력": ["Fin", "OtB", "Dri", "Fir", "Cmp", "Lon"],
    "패스/창의성": ["Pas", "Vis", "Tec", "Dec", "Tea", "Cro"],
    "피지컬": ["Acc", "Pac", "Sta", "Str", "Jum", "Agi", "Bal"],
    "멘탈/활동량": ["Det", "Wor", "Ant", "Ldr", "Agg", "Amb"],
    "수비 능력": ["Mar", "Tck", "Pos"],
}

MENTALITY_KEYS = ["Agg", "Amb", "Det", "Ldr", "Loy", "Tea", "Wor", "Cons", "Pres", "Prof", "Sport", "Spor", "Temp"]


def attr_label(key, with_code=False):
    if key is None:
        return "알 수 없음"
    label = ATTRIBUTE_LABELS.get(key, (str(key), ""))[0]
    return f"{label} ({key})" if with_code and key else label


def attr_description(key):
    if key is None:
        return "정의되지 않은 능력치입니다."
    return ATTRIBUTE_LABELS.get(key, (str(key), "설명 정보가 없는 proxy 능력치입니다."))[1]


def numeric_attr(attributes, key):
    if not isinstance(attributes, dict) or key is None:
        return None
    try:
        value = attributes.get(key)
        if value is None or value == "":
            return None
        value = float(value)
        if pd.isna(value):
            return None
        return value
    except Exception:
        return None


def average_attrs(attributes, keys):
    values = [numeric_attr(attributes, key) for key in keys]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def attributes_long_df(attributes, groups=None):
    if not isinstance(attributes, dict):
        return pd.DataFrame(columns=["group", "attribute", "value", "description"])

    rows = []
    groups = groups or ATTRIBUTE_GROUPS
    for group, keys in groups.items():
        safe_group = group or "기타"
        for key in keys:
            value = numeric_attr(attributes, key)
            if value is None:
                continue
            rows.append(
                {
                    "group": safe_group,
                    "attribute": attr_label(key) or "알 수 없음",
                    "value": value,
                    "description": attr_description(key) or "설명 없음",
                }
            )

    return pd.DataFrame(rows, columns=["group", "attribute", "value", "description"])


def attr_bar_chart(df, title=None, height=260):
    if df is None or df.empty:
        st.info("표시할 능력치 데이터가 없습니다.")
        return

    work = df.copy()
    for col in ["group", "attribute", "description"]:
        if col not in work.columns:
            work[col] = "알 수 없음"
        work[col] = work[col].fillna("알 수 없음").replace("", "알 수 없음")

    if "value" not in work.columns:
        st.info("표시할 능력치 데이터가 없습니다.")
        return

    work["value"] = pd.to_numeric(work["value"], errors="coerce")
    work = work.dropna(subset=["value"])

    if work.empty:
        st.info("표시할 능력치 데이터가 없습니다.")
        return

    chart = (
        alt.Chart(work)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("value:Q", scale=alt.Scale(domain=[0, 20]), title="점수"),
            y=alt.Y("attribute:N", sort="-x", title=None),
            color=alt.Color("group:N", legend=alt.Legend(title="그룹")),
            tooltip=[
                alt.Tooltip("group:N", title="그룹"),
                alt.Tooltip("attribute:N", title="능력치"),
                alt.Tooltip("value:Q", title="점수"),
                alt.Tooltip("description:N", title="설명"),
            ],
        )
    )

    properties = {"height": height}
    if title:
        properties["title"] = str(title)
    chart = chart.properties(**properties)
    st.altair_chart(chart, use_container_width=True)


def summary_scores(attributes, mentality):
    mentality_basis = mentality.get("basis", {}) if isinstance(mentality, dict) else {}
    mental_score = mentality.get("mentality_score") if isinstance(mentality, dict) else None
    if mental_score is None:
        mental_score = average_attrs(mentality_basis, MENTALITY_KEYS)

    return {
        "공격 능력": average_attrs(attributes, ATTRIBUTE_GROUPS["공격 능력"]),
        "패스/창의성": average_attrs(attributes, ATTRIBUTE_GROUPS["패스/창의성"]),
        "피지컬": average_attrs(attributes, ATTRIBUTE_GROUPS["피지컬"]),
        "멘탈 종합 점수": mental_score,
    }


def top_attributes(attributes, keys=None, limit=3):
    if not isinstance(attributes, dict):
        return []
    keys = keys or [key for group in ATTRIBUTE_GROUPS.values() for key in group]
    rows = []
    for key in keys:
        value = numeric_attr(attributes, key)
        if value is not None:
            rows.append((key, value))
    return sorted(rows, key=lambda item: item[1], reverse=True)[:limit]


def score_level(value):
    if value is None:
        return "데이터 없음"
    try:
        value = float(value)
    except Exception:
        return "데이터 없음"
    if value >= 15:
        return "강점"
    if value >= 11:
        return "보통"
    return "보완 필요"


def render_metric_cards(scores):
    cols = st.columns(len(scores))
    for col, (label, value) in zip(cols, scores.items()):
        display = "-" if value is None else round(float(value), 1)
        col.metric(label, display, score_level(value))


def format_percent(value):
    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return "-"


def korean_appearances(df):
    rename = {
        "date": "경기일",
        "competition_id": "대회",
        "goals": "득점",
        "assists": "도움",
        "yellow_cards": "경고",
        "red_cards": "퇴장",
        "minutes_played": "출전 시간",
    }
    return df.rename(columns=rename)


def korean_notes(df):
    rename = {
        "note_id": "노트 ID",
        "player_id": "선수 ID",
        "player_name": "선수명",
        "profile_id": "프로필 ID",
        "created_at": "저장 시각",
    }
    return df.rename(columns=rename)


def template_player_sentence(attributes, mentality):
    tops = top_attributes(attributes, ["Fin", "Acc", "Pac", "Dri", "Pas", "Vis", "Wor", "Tea", "Det"])
    if not tops:
        return "템플릿 기반 설명: 표시할 주요 대체 지표가 부족합니다."

    labels = [attr_label(key) for key, _ in tops[:2]]
    mentality_score = mentality.get("mentality_score") if isinstance(mentality, dict) else None
    mental_text = f" 멘탈 종합 점수는 {mentality_score}점으로 요약됩니다." if mentality_score is not None else ""
    return f"템플릿 기반 설명: 이 선수는 {', '.join(labels)}이 돋보이는 유형으로 요약됩니다.{mental_text}"


def render_player_profile_panel(player, profile=None):
    age = profile.get("age") if isinstance(profile, dict) else None
    image_url = player.get("image_url") or ""
    photo_html = (
        f'<img class="profile-photo" src="{image_url}" />'
        if image_url
        else '<div class="profile-photo"></div>'
    )
    badges = [
        f"나이 {age}" if age is not None else None,
        player.get("position"),
        player.get("sub_position"),
        player.get("foot"),
        player.get("country_of_citizenship"),
    ]
    badge_html = "".join(f'<span class="scout-badge">{badge}</span>' for badge in badges if badge)
    st.markdown(
        f"""
        <div class="scout-panel profile-card">
            {photo_html}
            <div>
                <div class="muted">선택된 유망주</div>
                <h2 style="margin: 0 0 6px 0;">{player.get('name') or '-'}</h2>
                <div><b>소속팀</b> {player.get('current_club_name') or '-'}</div>
                <div><b>국적</b> {player.get('country_of_citizenship') or '-'}</div>
                <div class="badge-row">{badge_html}</div>
                <div class="muted" style="margin-top: 10px;">
                    현재 시장가치 {money(player.get('market_value_in_eur'))} · 최고 시장가치 {money(player.get('highest_market_value_in_eur'))}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard():
    st.title("유망주 통합 분석 대시보드")
    player = require_selected_player()
    if player is None:
        return

    profile = get_player_profile(player)
    render_player_profile_panel(player, profile)

    if profile is None:
        st.warning("연결된 FM 프로필 데이터가 없어 스타일 요약을 표시할 수 없습니다.")
        return

    attributes = parse_json_field(profile.get("attributes_jsonb"))
    mentality = parse_json_field(profile.get("mentality_jsonb"))
    scores = summary_scores(attributes, mentality)

    st.subheader("핵심 대체 지표 요약")
    st.caption("공식 평가가 아니라 현재 CSV/FM 속성을 요약한 prototype summary입니다.")
    render_metric_cards(scores)
    st.markdown(f'<div class="section-note">{template_player_sentence(attributes, mentality)}</div>', unsafe_allow_html=True)

    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("FM 기반 스타일 요약")
        st.caption("FM 원본 축약어를 한국어 라벨로 변환하고, 능력치를 그룹별 막대 차트로 재구성했습니다.")
        for group, keys in ATTRIBUTE_GROUPS.items():
            st.markdown(f"**{group}**")
            group_df = attributes_long_df(attributes, {group: keys})
            attr_bar_chart(group_df, height=180)

    with right:
        st.subheader("멘탈리티 분석")
        st.caption("현재 멘탈리티 평가는 기사 원문 분석이 아닌 FM 속성 기반의 대체 지표입니다.")
        mental_score = mentality.get("mentality_score") if isinstance(mentality, dict) else None
        st.metric("멘탈 종합 점수", "-" if mental_score is None else mental_score)
        mentality_basis = mentality.get("basis", {}) if isinstance(mentality, dict) else {}
        mental_df = attributes_long_df(mentality_basis, {"멘탈리티": MENTALITY_KEYS})
        attr_bar_chart(mental_df, height=300)
        interpretations = mentality.get("interpretation", []) if isinstance(mentality, dict) else []
        if interpretations:
            st.markdown("**해석 메모**")
            for item in interpretations[:4]:
                st.markdown(f"- {item}")

    with st.expander("원본 능력치 데이터 보기"):
        st.json(attributes)
    with st.expander("원본 멘탈리티 JSON 보기"):
        st.json(mentality)

    st.divider()
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.subheader("시장가치 변화")
        valuations = get_valuations(player["player_id"])
        if valuations.empty:
            st.info("시장가치 데이터가 없습니다.")
        else:
            valuations["date"] = pd.to_datetime(valuations["date"])
            valuations["market_value_in_eur"] = pd.to_numeric(valuations["market_value_in_eur"], errors="coerce")
            chart = (
                alt.Chart(valuations.dropna(subset=["market_value_in_eur"]))
                .mark_line(point=True, color="#2dd4bf", strokeWidth=3)
                .encode(
                    x=alt.X("date:T", title="날짜"),
                    y=alt.Y("market_value_in_eur:Q", title="시장가치(EUR)"),
                    tooltip=[
                        alt.Tooltip("date:T", title="날짜"),
                        alt.Tooltip("market_value_in_eur:Q", title="시장가치"),
                        alt.Tooltip("current_club_name:N", title="소속팀"),
                    ],
                )
                .properties(height=260)
            )
            st.altair_chart(chart, use_container_width=True)

    with c2:
        st.subheader("최근 출전 기록")
        appearances = get_appearances(player["player_id"], limit=10)
        if appearances.empty:
            st.info("최근 출전 기록이 없습니다.")
        else:
            st.caption("최근 10경기 기준 출전 기록입니다.")
            st.dataframe(korean_appearances(appearances), use_container_width=True, hide_index=True)


def render_legend_matching():
    st.title("유사 선수 매칭")
    player = require_selected_player()
    if player is None:
        return

    profile = get_player_profile(player)
    render_player_profile_panel(player, profile)
    st.info("현재 매칭은 실제 10x10 Grid 데이터가 아니라 FM 기반 proxy style_vector(24차원)를 활용한 pgvector 유사 선수 후보입니다.")

    if profile is None:
        st.warning("FM 프로필 데이터가 없어 유사 선수 후보를 조회할 수 없습니다.")
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

    rows = similar.to_dict("records")
    for start in range(0, len(rows), 2):
        cols = st.columns(2)
        for col, row in zip(cols, rows[start:start + 2]):
            with col:
                st.markdown(
                    f"""
                    <div class="scout-panel">
                        <div class="muted">유사 선수 후보</div>
                        <h3 style="margin: 2px 0 8px 0;">{row.get('name') or '-'}</h3>
                        <div class="badge-row">
                            <span class="scout-badge">포지션 {row.get('position') or '-'}</span>
                            <span class="scout-badge">소속팀 {row.get('club') or '-'}</span>
                            <span class="scout-badge">나이 {row.get('age') or '-'}</span>
                        </div>
                        <h2 style="margin: 12px 0 0 0; color: #5eead4;">{row.get('similarity') or '-'}</h2>
                        <div class="muted">유사도 점수</div>
                        <p style="margin-top: 10px;">주요 강점: FM proxy style_vector 근접도</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with st.expander("표로 보기"):
        display = similar.rename(
            columns={
                "name": "선수명",
                "age": "나이",
                "club": "소속팀",
                "nationality": "국적",
                "position": "포지션",
                "similarity": "유사도",
            }
        )
        st.dataframe(display, use_container_width=True, hide_index=True)


def readable_setting(label, value):
    maps = {
        "training_intensity": "높음" if value >= 1.4 else "중간" if value >= 0.9 else "낮음",
        "playing_time_opportunity": "높음" if value >= 0.7 else "중간" if value >= 0.35 else "낮음",
        "league_difficulty": {"low": "낮음", "medium": "중간", "high": "높음", "elite": "최상위"}.get(value, value),
        "career_choice": {"stay": "잔류", "loan": "임대", "transfer": "이적"}.get(value, value),
        "risk_level": {"safe": "안정형", "normal": "균형형", "aggressive": "공격형"}.get(value, value),
    }
    return maps.get(label, value)


def render_career_simulation():
    st.title("커리어 시뮬레이션 프로토타입")
    player = require_selected_player()
    if player is None:
        return

    profile = get_player_profile(player)
    render_player_profile_panel(player, profile)

    left, right = st.columns([1, 1.2])
    with left:
        st.subheader("시나리오 설정")
        training = st.slider("훈련 강도", 0.5, 2.0, 1.2, 0.1)
        playing_time = st.slider("출전 기회", 0.0, 1.0, 0.6, 0.05)
        league_difficulty = st.selectbox("리그 난이도", ["low", "medium", "high", "elite"], index=1)
        career_choice = st.radio("커리어 선택", ["stay", "loan", "transfer"], horizontal=True)
        risk_level = st.radio("리스크 성향", ["safe", "normal", "aggressive"], horizontal=True, index=1)

    env_settings = {
        "training_intensity": training,
        "playing_time_opportunity": playing_time,
        "league_difficulty": league_difficulty,
        "career_choice": career_choice,
        "risk_level": risk_level,
    }
    simulation_result = build_simulation_result(env_settings)
    st.session_state["env_settings"] = env_settings
    st.session_state["simulation_result"] = simulation_result

    with right:
        st.subheader("시뮬레이션 결과")
        c1, c2, c3 = st.columns(3)
        c1.metric("성장 점수", simulation_result["prototype_growth_score"])
        c2.metric("성공 가능성", format_percent(simulation_result["prototype_success_probability"]))
        c3.metric("부상 리스크", format_percent(simulation_result["prototype_injury_risk"]))
        setting_df = pd.DataFrame(
            [
                {"항목": "훈련 강도", "설정": readable_setting("training_intensity", training)},
                {"항목": "출전 기회", "설정": readable_setting("playing_time_opportunity", playing_time)},
                {"항목": "리그 난이도", "설정": readable_setting("league_difficulty", league_difficulty)},
                {"항목": "커리어 선택", "설정": readable_setting("career_choice", career_choice)},
                {"항목": "리스크 성향", "설정": readable_setting("risk_level", risk_level)},
            ]
        )
        st.dataframe(setting_df, use_container_width=True, hide_index=True)

    chart_data = pd.DataFrame(
        {
            "성장 단계": ["현재", "1년 후", "2년 후", "3년 후"],
            "점수": [
                max(20, simulation_result["prototype_growth_score"] - 18),
                max(25, simulation_result["prototype_growth_score"] - 9),
                simulation_result["prototype_growth_score"],
                min(100, simulation_result["prototype_growth_score"] + 5),
            ],
        }
    )
    st.subheader("예상 성장 곡선")
    chart = (
        alt.Chart(chart_data)
        .mark_line(point=True, color="#2dd4bf", strokeWidth=3)
        .encode(
            x=alt.X("성장 단계:N", title="성장 단계"),
            y=alt.Y("점수:Q", scale=alt.Scale(domain=[0, 100]), title="점수"),
            tooltip=["성장 단계:N", "점수:Q"],
        )
        .properties(height=280)
    )
    st.altair_chart(chart, use_container_width=True)
    st.markdown('<div class="section-note">현재 결과는 실제 예측 모델이 아니라 UI 흐름 검증을 위한 프로토타입 시뮬레이션 결과입니다.</div>', unsafe_allow_html=True)

    with st.expander("시뮬레이션 원본 JSON 보기"):
        st.write("env_settings")
        st.json(env_settings)
        st.write("simulation_result")
        st.json(simulation_result)


def get_report_sections(player, profile, env_settings, simulation_result):
    attributes = parse_json_field(profile.get("attributes_jsonb")) if profile else {}
    mentality = parse_json_field(profile.get("mentality_jsonb")) if profile else {}
    scores = summary_scores(attributes, mentality)
    strengths = [f"{attr_label(key)} {value:g}/20" for key, value in top_attributes(attributes, limit=3)]
    if not strengths:
        strengths = ["표시할 주요 강점 데이터가 부족합니다."]

    weak_rows = []
    for key in [key for group in ATTRIBUTE_GROUPS.values() for key in group]:
        value = numeric_attr(attributes, key)
        if value is not None:
            weak_rows.append((key, value))
    weak_rows = sorted(weak_rows, key=lambda item: item[1])[:3]
    weaknesses = [f"{attr_label(key)} {value:g}/20" for key, value in weak_rows] or ["보완점 산출을 위한 데이터가 부족합니다."]

    return {
        "종합 평가": (
            f"{player.get('name')}은 {player.get('position') or '-'} 포지션의 유망주입니다. "
            f"대체 지표 기준 공격 능력 {scores.get('공격 능력') or '-'}, "
            f"패스/창의성 {scores.get('패스/창의성') or '-'}, 피지컬 {scores.get('피지컬') or '-'}로 요약됩니다."
        ),
        "강점": strengths,
        "보완점": weaknesses,
        "훈련 제안": (
            f"훈련 강도는 {readable_setting('training_intensity', env_settings.get('training_intensity'))}, "
            f"출전 기회는 {readable_setting('playing_time_opportunity', env_settings.get('playing_time_opportunity'))}로 설정되어 있습니다. "
            "템플릿 기반 초안 기준으로 경기 경험과 핵심 강점 강화의 균형이 중요합니다."
        ),
        "커리어 조언": (
            f"커리어 선택은 {readable_setting('career_choice', env_settings.get('career_choice'))}, "
            f"리스크 성향은 {readable_setting('risk_level', env_settings.get('risk_level'))}입니다. "
            f"프로토타입 성공 가능성은 {format_percent(simulation_result.get('prototype_success_probability'))}입니다."
        ),
        "안내": "현재 리포트는 실제 Gemini API 호출 결과가 아니라 템플릿 기반 초안입니다.",
    }


def sections_to_report_text(sections):
    lines = ["AI 스카우팅 리포트 초안"]
    for title, content in sections.items():
        lines.append("")
        lines.append(title)
        if isinstance(content, list):
            lines.extend(f"- {item}" for item in content)
        else:
            lines.append(str(content))
    return "\n".join(lines)


def render_ai_report():
    st.title("AI 스카우팅 리포트 초안")
    player = require_selected_player()
    if player is None:
        return

    profile = get_player_profile(player)
    env_settings = st.session_state.get("env_settings")
    simulation_result = st.session_state.get("simulation_result")
    if env_settings is None or simulation_result is None:
        st.warning("먼저 커리어 시뮬레이션 화면에서 시뮬레이션 설정을 생성해 주세요.")
        return

    render_player_profile_panel(player, profile)
    st.info("현재 리포트는 실제 Gemini API 호출 결과가 아니라 템플릿 기반 초안입니다.")

    if st.button("리포트 초안 생성", type="primary"):
        sections = get_report_sections(player, profile, env_settings, simulation_result)
        st.session_state["generated_report_sections"] = sections
        st.session_state["generated_report"] = sections_to_report_text(sections)

    sections = st.session_state.get("generated_report_sections")
    report = st.session_state.get("generated_report")

    if not sections:
        return

    for title in ["종합 평가", "강점", "보완점", "훈련 제안", "커리어 조언", "안내"]:
        content = sections.get(title)
        if not content:
            continue
        body = "<br>".join(f"- {item}" for item in content) if isinstance(content, list) else str(content)
        st.markdown(f'<div class="report-block"><b>{title}</b><br>{body}</div>', unsafe_allow_html=True)

    with st.expander("리포트 원문 및 저장 데이터 보기"):
        st.text(report)
        st.write("env_settings")
        st.json(env_settings)
        st.write("simulation_result")
        st.json(simulation_result)

    if st.button("스카우팅 노트에 저장"):
        try:
            saved = insert_scouting_note(
                player_id=player["player_id"],
                profile_id=profile.get("profile_id") if profile else None,
                env_settings=env_settings,
                simulation_result=simulation_result,
                report=report,
            )
            st.success(f"스카우팅 노트가 저장되었습니다. note_id: {saved['note_id']}")
        except Exception as exc:
            st.error("스카우팅 노트 저장 중 오류가 발생했습니다.")
            st.info("현재 과제 범위에서는 테이블 구조를 변경하지 않습니다. user_id null 저장이 실패하면 임시 테스트용 UUID 사용을 대안으로 검토할 수 있습니다.")
            with st.expander("개발 확인용 오류"):
                st.exception(exc)


def render_my_notes():
    st.title("내 스카우팅 노트")
    st.info("현재는 Supabase Auth와 RLS가 연결되지 않은 프로토타입 단계이므로 사용자별 필터링은 적용되지 않습니다. 향후 user_id 기반으로 본인의 노트만 조회하도록 확장할 예정입니다.")

    try:
        notes = get_scouting_notes(limit=20)
    except Exception as exc:
        st.error("스카우팅 노트 조회 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)
        return

    if notes.empty:
        st.info("저장된 스카우팅 노트가 없습니다.")
        return

    summary_cols = ["note_id", "player_name", "player_id", "profile_id", "created_at"]
    st.dataframe(korean_notes(notes[summary_cols]), use_container_width=True, hide_index=True)

    for _, note in notes.iterrows():
        title = f"{note.get('player_name') or note.get('player_id')} | {note.get('created_at')}"
        with st.expander(title):
            st.write("시뮬레이션 설정")
            st.json(parse_json_field(note.get("env_settings")))
            st.write("시뮬레이션 결과")
            st.json(parse_json_field(note.get("simulation_result")))
            st.write("리포트")
            st.text(note.get("gemini_report") or "")


def render_home():
    st.title("NEXT-LEGEND FINDER")
    st.caption("FM 스타일에서 영감을 받은 축구 유망주 스카우팅 대시보드 프로토타입")

    st.markdown(
        """
        <div class="scout-panel">
            <h3 style="margin-top: 0;">서비스 개요</h3>
            NEXT-LEGEND FINDER는 유망주의 기본 정보, 시장가치 변화, 출전 기록,
            FM 기반 대체 능력치와 멘탈리티 지표를 통합해 보여주는 데이터베이스 활용 서비스입니다.
            현재 단계는 완성된 예측 모델이 아니라 HW#5용 프로토타입 UI입니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("DB 테이블", "6개")
    c2.metric("스타일 벡터", "24차원 proxy")
    c3.metric("리포트", "템플릿 기반 초안")

    st.info("공식 Football Manager 자산을 복제하지 않고, 정보 구조와 분위기만 참고한 스카우팅 대시보드입니다.")


def render_prospect_search():
    st.title("유망주 검색")
    st.caption("분석할 유망주를 검색하고 선택합니다. 선택한 선수는 다른 화면에서 공통으로 사용됩니다.")
    st.info("유망주 기준: FM 데이터 기준 만 23세 이하")

    max_age = st.slider("최대 나이", min_value=16, max_value=30, value=23, step=1)

    try:
        positions = get_distinct_positions(max_age=max_age)
    except Exception:
        positions = ["All"]

    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        keyword = st.text_input("선수 이름", placeholder="예: Bellingham, Yamal, Son")
    with col2:
        position = st.selectbox("포지션", positions)
    with col3:
        nationality = st.text_input("국적", placeholder="예: Korea")
    with col4:
        club = st.text_input("소속팀", placeholder="예: Dortmund")

    try:
        results = search_players(
            keyword=keyword,
            position=position,
            nationality=nationality,
            club=club,
            max_age=max_age,
        )
    except Exception as exc:
        st.error("선수 검색 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)
        return

    if results.empty:
        st.info("검색 결과가 없습니다. 현재 검색은 player_profiles.age가 있는 선수만 대상으로 합니다.")
        return

    display = results[
        [
            "player_id",
            "name",
            "age",
            "current_club_name",
            "country_of_citizenship",
            "position",
            "sub_position",
            "market_value_in_eur",
        ]
    ].rename(
        columns={
            "player_id": "선수 ID",
            "name": "선수명",
            "age": "나이",
            "current_club_name": "소속팀",
            "country_of_citizenship": "국적",
            "position": "포지션",
            "sub_position": "세부 포지션",
            "market_value_in_eur": "현재 시장가치",
        }
    )
    st.dataframe(display, use_container_width=True, hide_index=True)

    labels = {}
    for _, row in results.iterrows():
        label = (
            f"{row['name']} | 나이 {row.get('age') or '-'} | "
            f"{row.get('current_club_name') or '-'} | "
            f"{row.get('position') or '-'} | ID {row['player_id']}"
        )
        labels[label] = int(row["player_id"])

    selected_label = st.selectbox("분석할 선수 선택", list(labels.keys()))
    if st.button("선택한 선수 저장", type="primary"):
        st.session_state["selected_player_id"] = labels[selected_label]
        st.success("선택한 선수를 저장했습니다. 다른 화면에서 이 선수를 기준으로 분석합니다.")

    show_selected_player_banner()


def render_db_status():
    st.title("DB 상태 확인")
    st.caption("HW#4에서 구축한 Supabase DB가 현재 앱과 정상 연결되는지 확인하는 보조 화면입니다.")

    try:
        count_data = [{"테이블": table, "행 수": table_count(table)} for table in TABLES]
        st.success("Supabase 연결 성공")
        st.dataframe(pd.DataFrame(count_data), use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error("Supabase 연결 또는 테이블 조회 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)
        return

    table_name = st.selectbox("미리 볼 테이블", TABLES)
    limit = st.slider("조회 행 수", 5, 100, 30, 5)
    try:
        df = preview_table(table_name, limit=limit)
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error("테이블 미리보기 중 오류가 발생했습니다.")
        with st.expander("개발 확인용 오류"):
            st.exception(exc)


def main():
    apply_theme()
    st.sidebar.title("NEXT-LEGEND FINDER")
    menu = {
        "홈 / 서비스 소개": render_home,
        "유망주 검색": render_prospect_search,
        "유망주 통합 분석": render_dashboard,
        "유사 선수 매칭": render_legend_matching,
        "커리어 시뮬레이션": render_career_simulation,
        "AI 스카우팅 리포트": render_ai_report,
        "내 스카우팅 노트": render_my_notes,
        "DB 상태 확인": render_db_status,
    }
    page = st.sidebar.radio("메뉴", list(menu.keys()))
    st.sidebar.divider()
    show_selected_player_banner()
    menu[page]()


def apply_theme():
    st.markdown(
        """
        <style>
        .stApp {
            background: #F5F7FA;
            color: #1F2933;
        }
        section[data-testid="stSidebar"] {
            background: #FFFFFF;
            border-right: 1px solid #E3E8EF;
        }
        h1, h2, h3 {
            color: #17324D;
            letter-spacing: 0;
        }
        p, li, span, div {
            color: inherit;
        }
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #DCE3EA;
            border-radius: 8px;
            padding: 14px 16px;
            box-shadow: 0 8px 22px rgba(23, 50, 77, 0.06);
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid #DCE3EA;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 8px 22px rgba(23, 50, 77, 0.05);
        }
        .scout-panel {
            background: #FFFFFF;
            border: 1px solid #DCE3EA;
            border-radius: 8px;
            padding: 18px;
            margin: 10px 0 16px 0;
            box-shadow: 0 8px 24px rgba(23, 50, 77, 0.07);
        }
        .profile-card {
            display: grid;
            grid-template-columns: 150px 1fr 260px;
            gap: 22px;
            align-items: center;
        }
        .profile-photo {
            width: 150px;
            height: 150px;
            object-fit: cover;
            border-radius: 8px;
            border: 1px solid #C9D5E1;
            background: #EDF2F7;
        }
        .stat-box {
            background: #F8FAFC;
            border: 1px solid #E3E8EF;
            border-radius: 8px;
            padding: 12px;
            margin: 6px 0;
        }
        .badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        .scout-badge {
            display: inline-flex;
            border-radius: 999px;
            padding: 5px 10px;
            background: #E7F6F3;
            border: 1px solid #B7E4DD;
            color: #1F5C4D;
            font-size: 0.88rem;
            white-space: nowrap;
        }
        .muted {
            color: #667085;
            font-size: 0.93rem;
        }
        .section-note {
            color: #1F2933;
            background: #EEF8F6;
            border-left: 4px solid #2A9D8F;
            border-radius: 8px;
            padding: 13px 15px;
            margin: 8px 0 14px 0;
            line-height: 1.55;
        }
        .warning-note {
            color: #1F2933;
            background: #FFF3ED;
            border-left: 4px solid #E76F51;
            border-radius: 8px;
            padding: 13px 15px;
            margin: 8px 0 14px 0;
            line-height: 1.55;
        }
        .report-block {
            background: #FFFFFF;
            border: 1px solid #DCE3EA;
            border-left: 4px solid #2A9D8F;
            border-radius: 8px;
            padding: 16px 18px;
            margin-bottom: 12px;
            line-height: 1.58;
            box-shadow: 0 8px 22px rgba(23, 50, 77, 0.05);
        }
        @media (max-width: 900px) {
            .profile-card {
                grid-template-columns: 1fr;
            }
        }
        .app-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            background: #17324D;
            color: #FFFFFF;
            border-radius: 10px;
            padding: 14px 20px;
            margin: 0 0 18px 0;
            box-shadow: 0 8px 24px rgba(23, 50, 77, 0.18);
        }
        .app-header-brand {
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: 0.02em;
        }
        .app-header-page {
            font-size: 0.9rem;
            color: #CBD8E6;
            margin-top: 2px;
        }
        .app-header-status {
            font-size: 0.92rem;
            color: #E7F6F3;
            text-align: right;
        }
        .app-header-status b {
            color: #FFFFFF;
        }
        .home-hero {
            text-align: center;
            margin: 4px 0 18px 0;
        }
        .home-hero p {
            color: #475467;
            font-size: 1.05rem;
            margin-top: 6px;
        }
        .data-mode-badge {
            display: inline-flex;
            border-radius: 999px;
            padding: 3px 10px;
            font-size: 0.82rem;
            font-weight: 600;
            margin-top: 4px;
            white-space: nowrap;
        }
        .data-mode-matched {
            background: #E0F4F1;
            color: #1F5C4D;
        }
        .data-mode-tm {
            background: #DDEBFF;
            color: #1A4480;
        }
        .data-mode-fm {
            background: #FFF7D6;
            color: #7A5D00;
        }
        .data-mode-manual {
            background: #ECE5FF;
            color: #4A2E9C;
        }
        .data-mode-none {
            background: #E3E8EF;
            color: #475467;
        }
        .nav-chip-row {
            margin-bottom: 6px;
        }
        div[data-testid="stButton"] > button {
            border-radius: 999px;
        }
        .next-step-title {
            color: #17324D;
            font-weight: 700;
            font-size: 1.0rem;
            margin: 4px 0 10px 0;
        }
        .workflow-step {
            background: #FFFFFF;
            border: 1px solid #DCE3EA;
            border-radius: 10px;
            padding: 14px;
            margin-bottom: 10px;
            box-shadow: 0 6px 18px rgba(23, 50, 77, 0.05);
        }
        .workflow-step .step-no {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 26px;
            height: 26px;
            border-radius: 50%;
            background: #17324D;
            color: #FFFFFF;
            font-weight: 700;
            font-size: 0.85rem;
            margin-right: 8px;
        }
        .data-mode-card {
            background: #FFFFFF;
            border: 1px solid #DCE3EA;
            border-left: 4px solid #2A9D8F;
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 10px;
            box-shadow: 0 6px 18px rgba(23, 50, 77, 0.05);
        }
        .data-mode-card.active {
            border-left-color: #17324D;
            background: #F0F6FF;
        }
        .hero-cta {
            background: linear-gradient(135deg, #17324D 0%, #102335 100%);
            color: #FFFFFF;
            border-radius: 12px;
            padding: 22px 24px;
            margin: 4px 0 18px 0;
            box-shadow: 0 10px 28px rgba(16, 35, 53, 0.25);
        }
        .hero-cta h1 {
            color: #FFFFFF;
            margin: 0 0 6px 0;
        }
        .hero-cta p {
            color: #CBD8E6;
            font-size: 1.0rem;
            margin: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


ATTRIBUTE_LABELS = {
    "Acc": ("가속도", "순간적으로 속도를 끌어올리는 능력"),
    "Pac": ("주력", "최고 속도와 전력 질주 능력"),
    "Sta": ("지구력", "경기 내내 활동량을 유지하는 능력"),
    "Dri": ("드리블", "공을 몰고 전진하는 능력"),
    "Fin": ("결정력", "찬스를 득점으로 연결하는 능력"),
    "Pas": ("패스", "동료에게 공을 전달하는 정확도"),
    "Vis": ("시야", "전진 패스와 기회 창출을 보는 능력"),
    "Wor": ("활동량", "전술 수행과 압박에 참여하는 성향"),
    "Tea": ("팀워크", "동료와 전술에 맞춰 움직이는 능력"),
    "Det": ("의지력", "훈련 지속성과 성장 가능성을 뒷받침하는 성향"),
    "Str": ("몸싸움", "경합 상황에서 버티는 힘"),
    "Jum": ("점프력", "공중볼 상황의 도약 능력"),
    "Agi": ("민첩성", "방향 전환과 몸놀림"),
    "Bal": ("균형감각", "접촉 상황에서 자세를 유지하는 능력"),
    "Tec": ("개인기", "공을 다루는 전반적인 기술"),
    "Fir": ("퍼스트 터치", "첫 볼 컨트롤의 안정성"),
    "OtB": ("오프더볼", "공이 없을 때 공간을 찾는 움직임"),
    "Ant": ("예측력", "다음 장면을 먼저 읽는 능력"),
    "Dec": ("판단력", "상황에 맞는 선택을 하는 능력"),
    "Cmp": ("침착성", "압박 상황에서 판단을 유지하는 능력"),
    "Bra": ("적극성", "위험을 감수하고 경합에 참여하는 성향"),
    "Agg": ("적극성", "경합과 압박에 참여하는 성향"),
    "Cro": ("크로스", "측면에서 공을 투입하는 능력"),
    "Lon": ("중거리슛", "먼 거리에서 슈팅하는 능력"),
    "Mar": ("마킹", "상대 선수를 추적하는 능력"),
    "Tck": ("태클", "공을 빼앗는 능력"),
    "Pos": ("위치선정", "수비 위치와 공간 점유 능력"),
    "Amb": ("야망", "높은 목표를 추구하는 성향"),
    "Ldr": ("리더십", "팀을 이끄는 성향"),
    "Loy": ("충성심", "소속팀과 관계를 유지하는 성향"),
    "Cons": ("꾸준함", "경기력 변동을 줄이는 성향"),
    "Pres": ("압박 대처", "부담이 큰 경기에서 버티는 성향"),
    "Prof": ("프로 의식", "자기관리와 훈련 태도"),
    "Sport": ("스포츠맨십", "페어플레이와 경기 태도"),
    "Spor": ("스포츠맨십", "페어플레이와 경기 태도"),
    "Temp": ("감정 조절", "흥분 상황에서 균형을 유지하는 성향"),
}

ATTRIBUTE_GROUPS = {
    "공격 능력": ["Fin", "OtB", "Cmp", "Lon"],
    "패스/창의성": ["Pas", "Vis", "Tec", "Fir"],
    "피지컬": ["Acc", "Pac", "Sta", "Str", "Jum", "Agi", "Bal"],
    "멘탈/활동량": ["Det", "Wor", "Tea", "Ant", "Dec"],
    "수비 능력": ["Mar", "Tck", "Pos"],
}

MENTALITY_KEYS = ["Agg", "Amb", "Det", "Ldr", "Loy", "Tea", "Wor", "Cons", "Pres", "Prof", "Sport", "Spor", "Temp"]


def attr_label(key, with_code=False):
    if key is None:
        return "알 수 없음"
    label = ATTRIBUTE_LABELS.get(key, (str(key), ""))[0]
    return f"{label} ({key})" if with_code else label


def attr_description(key):
    if key is None:
        return "정의되지 않은 능력치입니다."
    return ATTRIBUTE_LABELS.get(key, (str(key), "설명 정보가 없는 proxy 능력치입니다."))[1]


def numeric_attr(attributes, key):
    if not isinstance(attributes, dict) or key is None:
        return None
    try:
        value = attributes.get(key)
        if value is None or value == "":
            return None
        value = float(value)
        if pd.isna(value):
            return None
        return value
    except Exception:
        return None


def average_attrs(attributes, keys):
    values = [numeric_attr(attributes, key) for key in keys]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def attributes_long_df(attributes, groups=None):
    if not isinstance(attributes, dict):
        return pd.DataFrame(columns=["그룹", "능력치", "점수", "설명"])
    rows = []
    for group, keys in (groups or ATTRIBUTE_GROUPS).items():
        for key in keys:
            value = numeric_attr(attributes, key)
            if value is None:
                continue
            rows.append(
                {
                    "그룹": group or "기타",
                    "능력치": attr_label(key) or "알 수 없음",
                    "점수": value,
                    "설명": attr_description(key) or "설명 없음",
                }
            )
    return pd.DataFrame(rows, columns=["그룹", "능력치", "점수", "설명"])


def attr_bar_chart(df, title=None, height=230):
    if df is None or df.empty:
        st.info("표시할 능력치 데이터가 없습니다.")
        return
    work = df.copy()
    for col in ["그룹", "능력치", "설명"]:
        if col not in work.columns:
            work[col] = "알 수 없음"
        work[col] = work[col].fillna("알 수 없음").replace("", "알 수 없음")
    if "점수" not in work.columns:
        st.info("표시할 능력치 데이터가 없습니다.")
        return
    work["점수"] = pd.to_numeric(work["점수"], errors="coerce")
    work = work.dropna(subset=["점수"])
    if work.empty:
        st.info("표시할 능력치 데이터가 없습니다.")
        return
    chart = (
        alt.Chart(work)
        .mark_bar(cornerRadiusEnd=4, color="#2A9D8F")
        .encode(
            x=alt.X("점수:Q", scale=alt.Scale(domain=[0, 20]), title="점수"),
            y=alt.Y("능력치:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("그룹:N", title="그룹"),
                alt.Tooltip("능력치:N", title="능력치"),
                alt.Tooltip("점수:Q", title="점수"),
                alt.Tooltip("설명:N", title="설명"),
            ],
        )
    )
    props = {"height": height}
    if title:
        props["title"] = str(title)
    st.altair_chart(chart.properties(**props), use_container_width=True)


def top_attributes(attributes, keys=None, limit=3, reverse=True):
    if not isinstance(attributes, dict):
        return []
    keys = keys or [key for group in ATTRIBUTE_GROUPS.values() for key in group]
    rows = [(key, numeric_attr(attributes, key)) for key in keys]
    rows = [(key, value) for key, value in rows if value is not None]
    return sorted(rows, key=lambda item: item[1], reverse=reverse)[:limit]


def summary_scores(attributes, mentality):
    basis = mentality.get("basis", {}) if isinstance(mentality, dict) else {}
    mental_score = mentality.get("mentality_score") if isinstance(mentality, dict) else None
    if mental_score is None:
        mental_score = average_attrs(basis, MENTALITY_KEYS)
    return {
        "공격 능력": average_attrs(attributes, ATTRIBUTE_GROUPS["공격 능력"]),
        "패스/창의성": average_attrs(attributes, ATTRIBUTE_GROUPS["패스/창의성"]),
        "피지컬": average_attrs(attributes, ATTRIBUTE_GROUPS["피지컬"]),
        "멘탈 종합": mental_score,
    }


def score_text(value):
    if value is None:
        return "-"
    try:
        return f"{float(value):.1f}"
    except Exception:
        return "-"


def format_percent(value):
    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return "-"


def render_metric_cards(scores):
    cols = st.columns(len(scores))
    for col, (label, value) in zip(cols, scores.items()):
        col.metric(label, score_text(value))


def strength_sentence(rows):
    if not rows:
        return "뚜렷하게 확인되는 강점 데이터가 부족합니다."
    labels = [attr_label(key) for key, _ in rows[:2]]
    return f"{'와 '.join(labels)} 지표가 상대적으로 높아 해당 역할에서 강점으로 해석할 수 있습니다."


def weakness_sentence(rows):
    if not rows:
        return "명확한 보완점 데이터가 부족합니다."
    labels = [attr_label(key) for key, _ in rows[:1]]
    return f"{labels[0]} 지표가 상대적으로 낮아 경기 운영이나 전술 적응 과정에서 보완이 필요할 수 있습니다."


def render_player_profile_panel(player, profile=None):
    age = profile.get("age") if isinstance(profile, dict) else None
    image_url = player.get("image_url") or ""
    photo_html = f'<img class="profile-photo" src="{image_url}" />' if image_url else '<div class="profile-photo"></div>'
    badges = [player.get("position"), player.get("sub_position"), player.get("foot"), player.get("country_of_citizenship")]
    badge_html = "".join(f'<span class="scout-badge">{badge}</span>' for badge in badges if badge)
    st.markdown(
        f"""
        <div class="scout-panel profile-card">
            <div>{photo_html}</div>
            <div>
                <div class="muted">선택된 유망주</div>
                <h2 style="margin: 0 0 8px 0;">{player.get('name') or '-'}</h2>
                <div><b>소속팀</b> {player.get('current_club_name') or '-'}</div>
                <div><b>국적</b> {player.get('country_of_citizenship') or '-'}</div>
                <div class="badge-row">{badge_html}</div>
            </div>
            <div>
                <div class="stat-box"><b>나이</b><br>{age if age is not None else '-'}</div>
                <div class="stat-box"><b>현재 시장가치</b><br>{money(player.get('market_value_in_eur'))}</div>
                <div class="stat-box"><b>최고 시장가치</b><br>{money(player.get('highest_market_value_in_eur'))}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def group_analysis(attributes, group, keys):
    avg = average_attrs(attributes, keys)
    highs = top_attributes(attributes, keys, 2, reverse=True)
    lows = top_attributes(attributes, keys, 1, reverse=False)
    return avg, highs, lows


def render_dashboard():
    st.title("유망주 통합 분석 대시보드")
    ctx = resolve_selected_player_context()
    entity_type = selected_entity_type()
    player = selected_player()
    profile = selected_profile()

    if player is None and profile is None:
        st.warning("먼저 Prospect Search에서 선수를 선택해 주세요.")
        return

    render_player_profile_panel(player, profile)

    if ctx["fallback_note"]:
        st.info(ctx["fallback_note"])

    if entity_type == "matched":
        st.info("matched 모드: players + player_profiles + player_valuations + appearances를 함께 확인할 수 있습니다.")
    elif entity_type == "fm_profile_only":
        st.info("fm_profile_only 모드: FM 프로필 기반 후보입니다. Transfermarkt 시장가치/출전 기록은 매칭되지 않아 표시할 수 없습니다.")
    else:
        st.info("transfermarkt_only 모드: Transfermarkt 기반 후보입니다. FM 스타일·멘탈 분석은 표시할 수 없습니다.")

    has_profile = isinstance(profile, dict) and profile.get("profile_id") is not None
    has_player_id = isinstance(player, dict) and player.get("player_id") is not None

    if entity_type in ("matched", "fm_profile_only") and has_profile:
        attributes = parse_json_field(profile.get("attributes_jsonb"))
        mentality = parse_json_field(profile.get("mentality_jsonb"))

        st.subheader("분석 요약")
        st.caption("아래 지표는 FM 기반 proxy 데이터를 요약한 prototype summary입니다.")
        render_metric_cards(summary_scores(attributes, mentality))

        st.subheader("FM 기반 스타일 요약")
        for group, keys in ATTRIBUTE_GROUPS.items():
            avg, highs, lows = group_analysis(attributes, group, keys)
            c1, c2 = st.columns([0.85, 1.4])
            with c1:
                st.markdown(
                    f"""
                    <div class="scout-panel">
                        <h3 style="margin-top: 0;">{group}</h3>
                        <div class="muted">그룹 평균 점수</div>
                        <h2 style="color:#1F5C4D; margin: 4px 0;">{score_text(avg)}</h2>
                        <b>주요 강점</b><br>{strength_sentence(highs)}<br><br>
                        <b>보완점</b><br>{weakness_sentence(lows)}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with c2:
                attr_bar_chart(attributes_long_df(attributes, {group: keys}), height=190)

        st.subheader("멘탈리티 분석")
        st.info("현재 멘탈리티 평가는 기사/스카우팅 원문 분석이 아닌 FM 속성 기반의 대체 지표입니다.")

        basis = mentality.get("basis", {}) if isinstance(mentality, dict) else {}
        mental_score = mentality.get("mentality_score") if isinstance(mentality, dict) else None
        m1, m2 = st.columns([0.75, 1.45])
        with m1:
            st.metric("멘탈 종합 점수", "-" if mental_score is None else mental_score)
            mental_highs = top_attributes(basis, MENTALITY_KEYS, 3, True)
            mental_lows = top_attributes(basis, MENTALITY_KEYS, 2, False)
            st.markdown('<div class="scout-panel"><b>멘탈 강점</b><br>' + strength_sentence(mental_highs) + '</div>', unsafe_allow_html=True)
            st.markdown('<div class="scout-panel"><b>보완이 필요한 부분</b><br>' + weakness_sentence(mental_lows) + '</div>', unsafe_allow_html=True)
        with m2:
            attr_bar_chart(attributes_long_df(basis, {"멘탈리티": MENTALITY_KEYS}), height=320)

    elif entity_type in ("matched", "fm_profile_only"):
        st.warning("FM 프로필이 없어 스타일/멘탈 분석은 표시할 수 없습니다.")

    if entity_type in ("matched", "transfermarkt_only") and has_player_id:
        st.subheader("시장가치 변화와 최근 출전 기록")
        c1, c2 = st.columns([1.1, 1])
        with c1:
            valuations = get_valuations(player["player_id"])
            if valuations.empty:
                st.info("시장가치 데이터가 없습니다.")
            else:
                valuations["date"] = pd.to_datetime(valuations["date"])
                valuations["market_value_in_eur"] = pd.to_numeric(valuations["market_value_in_eur"], errors="coerce")
                clean = valuations.dropna(subset=["market_value_in_eur"])
                if clean.empty:
                    st.info("표시할 시장가치 데이터가 없습니다.")
                else:
                    chart = (
                        alt.Chart(clean)
                        .mark_line(point=True, color="#2A9D8F", strokeWidth=3)
                        .encode(
                            x=alt.X("date:T", title="날짜"),
                            y=alt.Y("market_value_in_eur:Q", title="시장가치(EUR)"),
                            tooltip=["date:T", "market_value_in_eur:Q", "current_club_name:N"],
                        )
                        .properties(height=260)
                    )
                    st.altair_chart(chart, use_container_width=True)
        with c2:
            appearances = get_appearances(player["player_id"], limit=10)
            if appearances.empty:
                st.info("최근 출전 기록이 없습니다.")
            else:
                st.caption("최근 10경기 기준 출전 기록입니다.")
                st.dataframe(korean_appearances(appearances), use_container_width=True, hide_index=True)
    else:
        st.info("Transfermarkt 데이터와 매칭되지 않아 시장가치 변화와 최근 출전 기록 영역은 표시할 수 없습니다.")

    if has_profile and entity_type == "matched":
        with st.expander("개발자용 원본 데이터 보기"):
            st.json({"attributes_jsonb": parse_json_field(profile.get("attributes_jsonb")), "mentality_jsonb": parse_json_field(profile.get("mentality_jsonb"))})

    if entity_type in ("matched", "fm_profile_only") and has_profile:
        render_page_actions([
            ("🤝 유사 멘토 찾기", "유사 선수 후보", "primary"),
            ("📈 커리어 시뮬레이션 시작", "커리어 시뮬레이션"),
        ])
    else:
        render_page_actions([
            ("📝 My Scouting Notes에서 직접 분석 보완", "내 스카우팅 노트", "primary"),
            ("📈 커리어 시뮬레이션 시작", "커리어 시뮬레이션"),
        ], title="시장가치/출전 기록 기반 · 다음 단계")


def get_profile_by_profile_id(profile_id):
    return query_one("select * from player_profiles where profile_id = %s limit 1", (profile_id,))


def similarity_reason(base_profile, candidate_profile):
    base_attrs = parse_json_field(base_profile.get("attributes_jsonb")) if base_profile else {}
    cand_attrs = parse_json_field(candidate_profile.get("attributes_jsonb")) if candidate_profile else {}
    common = []
    diffs = []
    for key in [key for group in ATTRIBUTE_GROUPS.values() for key in group]:
        b = numeric_attr(base_attrs, key)
        c = numeric_attr(cand_attrs, key)
        if b is None or c is None:
            continue
        if b >= 12 and c >= 12:
            common.append((key, (b + c) / 2))
        diffs.append((key, c - b))
    common = sorted(common, key=lambda x: x[1], reverse=True)[:3]
    diffs = sorted(diffs, key=lambda x: abs(x[1]), reverse=True)[:2]
    common_text = ", ".join(attr_label(k) for k, _ in common) or "스타일 벡터 전반"
    diff_text = ", ".join(f"{attr_label(k)} {'높음' if d > 0 else '낮음'}" for k, d in diffs) or "세부 차이 데이터 부족"
    return (
        f"주요 공통점: 두 선수는 {common_text}에서 유사한 강점을 보입니다.",
        f"차이점: 후보 선수는 선택 선수와 비교해 {diff_text} 경향이 있습니다.",
        "추천 해석: 같은 역할 후보로 참고하되, 세부 능력치 차이에 따라 전술적 활용 방식은 달라질 수 있습니다.",
    )


def render_legend_matching():
    st.title("유사 선수 후보")
    entity_type = selected_entity_type()
    player = selected_player()
    profile = selected_profile()

    if player is None and profile is None:
        st.warning("먼저 Prospect Search에서 선수를 선택해 주세요.")
        return

    render_player_profile_panel(player, profile)
    st.info("현재 매칭은 실제 10x10 Grid 데이터가 아니라 FM 기반 proxy style_vector(24차원)를 활용한 pgvector 유사 선수 후보입니다.")

    if entity_type == "transfermarkt_only" or not isinstance(profile, dict) or profile.get("profile_id") is None:
        st.warning("FM 프로필이 없어 유사 선수 후보를 계산할 수 없습니다. Transfermarkt 기반 후보에서는 FM 벡터 유사도 분석을 제공할 수 없습니다.")
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

    for row in similar.to_dict("records"):
        candidate_profile = get_profile_by_profile_id(row.get("profile_id"))
        common, diff, recommendation = similarity_reason(profile, candidate_profile)
        st.markdown(
            f"""
            <div class="scout-panel">
                <h3 style="margin-top:0;">{row.get('name') or '-'}</h3>
                <div class="badge-row">
                    <span class="scout-badge">나이 {row.get('age') or '-'}</span>
                    <span class="scout-badge">{row.get('position') or '-'}</span>
                    <span class="scout-badge">{row.get('club') or '-'}</span>
                    <span class="scout-badge">유사도 {row.get('similarity') or '-'}</span>
                </div>
                <p>{common}</p>
                <p>{diff}</p>
                <p><b>{recommendation}</b></p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def readable_setting(label, value):
    maps = {
        "training_intensity": "높음" if value >= 1.4 else "중간" if value >= 0.9 else "낮음",
        "playing_time_opportunity": "높음" if value >= 0.7 else "중간" if value >= 0.35 else "낮음",
        "league_difficulty": {"low": "낮음", "medium": "중간", "high": "높음", "elite": "최상위"}.get(value, value),
        "career_choice": {"stay": "잔류", "loan": "임대", "transfer": "이적"}.get(value, value),
        "risk_level": {"safe": "안정형", "normal": "균형형", "aggressive": "공격형"}.get(value, value),
    }
    return maps.get(label, value)


def simulation_comment(env_settings, simulation_result):
    training = readable_setting("training_intensity", env_settings["training_intensity"])
    playing = readable_setting("playing_time_opportunity", env_settings["playing_time_opportunity"])
    choice = readable_setting("career_choice", env_settings["career_choice"])
    risk = readable_setting("risk_level", env_settings["risk_level"])
    choice_text = {
        "stay": "안정적인 출전 기회를 확보하는 시나리오입니다.",
        "loan": "단기 성장 기회를 찾는 시나리오입니다.",
        "transfer": "상위 리그 도전 또는 환경 변화를 선택하는 시나리오입니다.",
    }.get(env_settings["career_choice"], "")
    risk_text = {
        "safe": "안정적 성장을 우선합니다.",
        "normal": "성장과 리스크의 균형을 보는 설정입니다.",
        "aggressive": "높은 성장 가능성과 높은 리스크를 함께 감수하는 설정입니다.",
    }.get(env_settings["risk_level"], "")
    return f"현재 설정은 훈련 강도 {training}, 출전 기회 {playing}, 커리어 선택 {choice}, 리스크 성향 {risk}입니다. {choice_text} {risk_text}"


def render_career_simulation():
    st.title("커리어 시뮬레이션 프로토타입")
    player = require_selected_player()
    if player is None:
        return
    profile = get_player_profile(player)
    render_player_profile_panel(player, profile)
    left, right = st.columns([1, 1.2])
    with left:
        st.subheader("시나리오 설정")
        training = st.slider("훈련 강도", 0.5, 2.0, 1.2, 0.1)
        playing_time = st.slider("출전 기회", 0.0, 1.0, 0.6, 0.05)
        league_difficulty = st.selectbox("리그 난이도", ["low", "medium", "high", "elite"], index=1)
        career_choice = st.radio("커리어 선택", ["stay", "loan", "transfer"], horizontal=True)
        risk_level = st.radio("리스크 성향", ["safe", "normal", "aggressive"], horizontal=True, index=1)
    env_settings = {
        "training_intensity": training,
        "playing_time_opportunity": playing_time,
        "league_difficulty": league_difficulty,
        "career_choice": career_choice,
        "risk_level": risk_level,
    }
    simulation_result = build_simulation_result(env_settings)
    st.session_state["env_settings"] = env_settings
    st.session_state["simulation_result"] = simulation_result
    with right:
        st.subheader("결과 요약")
        c1, c2, c3 = st.columns(3)
        c1.metric("성장 점수", simulation_result["prototype_growth_score"])
        c2.metric("성공 가능성", format_percent(simulation_result["prototype_success_probability"]))
        c3.metric("부상 리스크", format_percent(simulation_result["prototype_injury_risk"]))
        st.markdown(f'<div class="section-note">{simulation_comment(env_settings, simulation_result)}</div>', unsafe_allow_html=True)
    chart_data = pd.DataFrame(
        {
            "성장 단계": ["현재", "1년 후", "2년 후", "3년 후"],
            "점수": [
                max(20, simulation_result["prototype_growth_score"] - 18),
                max(25, simulation_result["prototype_growth_score"] - 9),
                simulation_result["prototype_growth_score"],
                min(100, simulation_result["prototype_growth_score"] + 5),
            ],
        }
    )
    st.subheader("예상 성장 곡선")
    chart = (
        alt.Chart(chart_data)
        .mark_line(point=True, color="#2A9D8F", strokeWidth=3)
        .encode(
            x=alt.X("성장 단계:N", title="성장 단계"),
            y=alt.Y("점수:Q", scale=alt.Scale(domain=[0, 100]), title="점수"),
            tooltip=["성장 단계:N", "점수:Q"],
        )
        .properties(height=280)
    )
    st.altair_chart(chart, use_container_width=True)
    st.markdown('<div class="warning-note">현재 결과는 실제 예측 모델이 아니라 UI 흐름 검증을 위한 프로토타입 시뮬레이션입니다.</div>', unsafe_allow_html=True)
    with st.expander("개발자용 시뮬레이션 원본 데이터 보기"):
        st.json({"env_settings": env_settings, "simulation_result": simulation_result})


def get_report_sections(player, profile, env_settings, simulation_result):
    attributes = parse_json_field(profile.get("attributes_jsonb")) if profile else {}
    mentality = parse_json_field(profile.get("mentality_jsonb")) if profile else {}
    basis = mentality.get("basis", {}) if isinstance(mentality, dict) else {}
    strengths = top_attributes(attributes, limit=3)
    weaknesses = top_attributes(attributes, limit=2, reverse=False)
    mental_highs = top_attributes(basis, MENTALITY_KEYS, 2, True)
    mental_lows = top_attributes(basis, MENTALITY_KEYS, 1, False)
    strength_names = ", ".join(attr_label(k) for k, _ in strengths) or "주요 강점 데이터"
    weakness_names = ", ".join(attr_label(k) for k, _ in weaknesses) or "보완 데이터"
    mental_names = ", ".join(attr_label(k) for k, _ in mental_highs) or "멘탈 강점"
    mental_weak = ", ".join(attr_label(k) for k, _ in mental_lows) or "멘탈 보완점"
    return {
        "종합 평가": f"{player.get('name')}은 현재 데이터 기준 {player.get('position') or '-'} 포지션의 유망주입니다. FM 기반 proxy style_vector를 기준으로 보면 {strength_names}이 돋보이는 유형으로 해석할 수 있습니다.",
        "강점": f"{strength_names}이 상대적으로 높아 현재 역할에서 즉시 활용 가능한 강점으로 볼 수 있습니다. {mental_names} 역시 훈련 지속성과 전술 수행 능력 측면에서 긍정적인 신호입니다.",
        "보완점": f"{weakness_names}은 향후 성장 과정에서 보완이 필요할 수 있습니다. {mental_weak}이 낮게 나타난다면 상위 리그 적응이나 큰 경기 대응에서 리스크가 생길 수 있습니다.",
        "훈련 제안": "단기적으로는 약점을 모두 고치기보다 이미 높은 강점을 극대화하는 훈련이 적절합니다. 이후 패스, 판단력, 연계 플레이를 보완하면 더 다양한 전술 역할을 수행할 수 있습니다.",
        "커리어 조언": f"{simulation_comment(env_settings, simulation_result)} 성공 가능성은 {format_percent(simulation_result.get('prototype_success_probability'))}로 계산되지만, 이는 실제 예측 모델이 아닌 프로토타입 결과입니다.",
        "저장 정보": "저장 시 선수, 시뮬레이션 설정, 프로토타입 결과, 리포트 초안이 scouting_notes 테이블에 INSERT됩니다.",
    }


def sections_to_report_text(sections):
    lines = ["AI 스카우팅 리포트 초안"]
    for title, content in sections.items():
        lines.extend(["", title, str(content)])
    return "\n".join(lines)


def render_ai_report():
    st.title("AI 스카우팅 리포트 초안")
    entity_type = selected_entity_type()
    player = selected_player()
    profile = selected_profile()

    if player is None and profile is None:
        st.warning("먼저 Prospect Search에서 선수를 선택해 주세요.")
        return

    env_settings = st.session_state.get("env_settings")
    simulation_result = st.session_state.get("simulation_result")
    if env_settings is None or simulation_result is None:
        st.warning("먼저 커리어 시뮬레이션 화면에서 시뮬레이션 설정을 생성해 주세요.")
        return

    render_player_profile_panel(player, profile)
    st.info("현재 리포트는 실제 Gemini API 호출 결과가 아니라, 선택 선수와 시뮬레이션 설정값을 바탕으로 생성한 템플릿 기반 초안입니다.")

    if entity_type == "matched":
        st.info("matched 모드: players + player_profiles + 시뮬레이션 결과를 함께 반영한 리포트 초안을 생성합니다.")
    elif entity_type == "fm_profile_only":
        st.info("fm_profile_only 모드: FM 프로필 기반 스타일/멘탈리티를 우선 반영하고, Transfermarkt 값은 제한적으로만 참고합니다.")
    else:
        st.info("transfermarkt_only 모드: Transfermarkt 기본 정보와 시장가치/출전 기록을 중심으로 리포트를 생성합니다. FM 분석은 제한됩니다.")

    if entity_type == "transfermarkt_only":
        st.warning("이 후보는 FM 프로필이 없어 FM 스타일·멘탈 분석은 제외하고, 시장가치·출전 기록과 기본 정보 중심으로만 예시 리포트를 생성합니다.")

    if st.button("리포트 초안 생성", type="primary"):
        sections = get_report_sections(player, profile, env_settings, simulation_result)
        st.session_state["generated_report_sections"] = sections
        st.session_state["generated_report"] = sections_to_report_text(sections)

    sections = st.session_state.get("generated_report_sections")
    report = st.session_state.get("generated_report")
    if not sections:
        return

    for title in ["종합 평가", "강점", "보완점", "훈련 제안", "커리어 조언", "저장 정보"]:
        st.markdown(f'<div class="report-block"><h3 style="margin-top:0;">{title}</h3>{sections.get(title, "")}</div>', unsafe_allow_html=True)

    if st.button("스카우팅 노트에 저장"):
        if not isinstance(player, dict) or player.get("player_id") is None:
            st.warning("해당 후보는 player_id가 없어 스카우팅 노트 저장이 불가능합니다.")
            return
        try:
            saved = insert_scouting_note(
                player_id=player["player_id"],
                profile_id=profile.get("profile_id") if isinstance(profile, dict) else None,
                env_settings=env_settings,
                simulation_result=simulation_result,
                report=report,
            )
            st.success(f"스카우팅 노트가 저장되었습니다. note_id: {saved['note_id']}")
        except Exception as exc:
            st.error("스카우팅 노트 저장 중 오류가 발생했습니다.")
            with st.expander("개발 확인용 오류"):
                st.exception(exc)


def note_summary_text(note):
    env = parse_json_field(note.get("env_settings"))
    sim = parse_json_field(note.get("simulation_result"))
    return (
        f"훈련 강도 {readable_setting('training_intensity', env.get('training_intensity', 0))}, "
        f"출전 기회 {readable_setting('playing_time_opportunity', env.get('playing_time_opportunity', 0))}, "
        f"커리어 선택 {readable_setting('career_choice', env.get('career_choice'))}, "
        f"성공 가능성 {format_percent(sim.get('prototype_success_probability'))}"
    )


def safe_text(value, fallback="이름 없는 직접 입력 노트"):
    if value is None:
        return fallback
    if isinstance(value, float) and pd.isna(value):
        return fallback
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else fallback
    if pd.isna(value):
        return fallback
    return str(value)


def get_career_settings(env_settings):
    if not isinstance(env_settings, dict):
        return {}

    career_settings = env_settings.get("career_settings")
    if isinstance(career_settings, dict):
        return career_settings

    legacy = {}
    for key in ["training_intensity", "playing_time_opportunity", "league_difficulty", "career_choice", "risk_level"]:
        if key in env_settings:
            legacy[key] = env_settings.get(key)

    nested = env_settings.get("env_settings") if isinstance(env_settings.get("env_settings"), dict) else None
    if isinstance(nested, dict):
        nested_career = nested.get("career_settings")
        if isinstance(nested_career, dict):
            return nested_career
        for key in ["training_intensity", "playing_time_opportunity", "league_difficulty", "career_choice", "risk_level"]:
            if key in nested and key not in legacy:
                legacy[key] = nested.get(key)

    return legacy


def normalize_env_settings(env_settings):
    if not isinstance(env_settings, dict):
        return {"note_type": "manual_custom_prospect", "career_settings": {}}

    career_settings = get_career_settings(env_settings)
    normalized = {
        "note_type": env_settings.get("note_type", "manual_custom_prospect"),
        "manual_player": env_settings.get("manual_player") if isinstance(env_settings.get("manual_player"), dict) else {},
        "manual_attributes": env_settings.get("manual_attributes") if isinstance(env_settings.get("manual_attributes"), dict) else {},
        "career_settings": career_settings,
        "selected_mentor_profile_id": env_settings.get("selected_mentor_profile_id"),
        "selected_mentor_name": env_settings.get("selected_mentor_name"),
    }
    return normalized


def setting_summary(key, value):
    if key == "training_intensity":
        number = safe_float(value, None)
        if number is None:
            return "훈련 강도: 정보 없음"
        if number >= 1.4:
            return "훈련 강도: 높음 — 빠른 성장을 기대할 수 있지만 피로 누적과 부상 위험이 증가할 수 있습니다."
        if number >= 0.9:
            return "훈련 강도: 보통 — 성장과 회복의 균형이 좋은 안정적 선택입니다."
        return "훈련 강도: 낮음 — 부상 위험은 낮지만 단기 성장 속도가 느릴 수 있습니다."

    if key == "playing_time_opportunity":
        number = safe_float(value, None)
        if number is None:
            return "출전 기회: 정보 없음"
        if number >= 0.7:
            return "출전 기회: 높음 — 경기 경험을 통해 빠른 성장을 기대할 수 있지만 체력 부담도 커질 수 있습니다."
        if number >= 0.35:
            return "출전 기회: 보통 — 훈련과 실전의 균형이 잡힌 환경입니다."
        return "출전 기회: 낮음 — 실전 경험이 부족해 성장 속도가 제한될 수 있습니다."

    if key == "league_difficulty":
        mapping = {"low": "낮음 — 적응은 쉽지만 성장 자극이 부족할 수 있습니다.",
                   "medium": "보통 — 현재 단계에서 안정적으로 성장하기 좋은 환경입니다.",
                   "high": "높음 — 경쟁 수준이 높아 성장 자극은 크지만 출전 기회가 줄 수 있습니다.",
                   "elite": "매우 높음 — 상위 환경 도전이 크지만 적응 실패와 벤치 리스크가 큽니다."}
        return f"리그/팀 수준: {mapping.get(value, '알 수 없음')}"

    if key == "career_choice":
        mapping = {"stay": "잔류 — 익숙한 환경에서 안정적으로 성장할 수 있습니다.",
                   "loan": "임대 — 출전 시간을 확보해 단기 성장 가능성을 높일 수 있습니다.",
                   "transfer": "이적 — 환경 변화가 큰 성장 자극이 되지만 적응 실패 리스크가 있습니다."}
        return f"커리어 선택: {mapping.get(value, '알 수 없음')}"

    if key == "risk_level":
        mapping = {"safe": "안정형 — 부상과 실패 가능성을 줄이는 대신 성장 속도는 완만할 수 있습니다.",
                   "normal": "균형형 — 성장과 리스크를 적절히 조절하는 선택입니다.",
                   "aggressive": "공격형 — 높은 성장 가능성을 노리지만 부상이나 적응 실패 위험이 커집니다."}
        return f"리스크 성향: {mapping.get(value, '알 수 없음')}"

    return f"{key}: {value}"


def manual_similarity_candidates(manual_player, manual_attributes, limit=5):
    try:
        profiles = query_df("""
            select profile_id, player_id, name, age, club, nationality, position, attributes_jsonb, mentality_jsonb
            from player_profiles
            where attributes_jsonb is not null
            limit 200
        """, ())
    except Exception:
        return []

    mapping = {
        "speed": ["Acc", "Pac", "Agi"],
        "dribble": ["Dri", "Tec", "Fir"],
        "finishing": ["Fin", "Cmp", "OtB"],
        "passing": ["Pas", "Vis", "Dec"],
        "physical": ["Str", "Sta", "Bal", "Jum"],
        "defending": ["Tck", "Mar", "Pos"],
        "work_rate": ["Wor", "Sta"],
        "teamwork": ["Tea"],
        "determination": ["Det"],
        "pressing": ["Pres", "Cmp"],
    }

    manual_position = (manual_player.get("position") or "").lower()
    candidates = []

    for _, row in profiles.iterrows():
        attrs = parse_json_field(row.get("attributes_jsonb")) or {}
        score = 0.0
        common_terms = []
        diff_terms = []
        count = 0

        for label, keys in mapping.items():
            manual_value = safe_float(manual_attributes.get(label), 0)
            values = [numeric_attr(attrs, key) for key in keys]
            values = [value for value in values if value is not None]
            if not values:
                continue
            avg_candidate = sum(values) / len(values)
            diff = abs((manual_value * 2.0) - avg_candidate)
            score += max(0.0, 100.0 - diff * 6.0)
            count += 1
            if diff <= 2.5:
                common_terms.append(attr_label(keys[0], with_code=False))
            else:
                diff_terms.append(attr_label(keys[0], with_code=False))

        if count == 0:
            continue

        score = score / count
        if manual_position and str(row.get("position") or "").lower():
            if manual_position in str(row.get("position") or "").lower() or str(row.get("position") or "").lower() in manual_position:
                score += 6
        if safe_float(manual_attributes.get("growth_potential"), 0) >= 7:
            score += 2

        score = min(99.9, max(0.0, score))
        candidates.append({
            "profile_id": row.get("profile_id"),
            "player_id": row.get("player_id"),
            "name": row.get("name") or "-",
            "age": row.get("age"),
            "club": row.get("club") or "-",
            "position": row.get("position") or "-",
            "nationality": row.get("nationality") or "-",
            "similarity": round(score, 1),
            "common_strengths": ", ".join(common_terms[:3]) or "전반적 스타일 유사성",
            "difference_hint": ", ".join(diff_terms[:3]) or "세부 차이가 제한적입니다.",
            "profile": row,
        })

    candidates = sorted(candidates, key=lambda item: item["similarity"], reverse=True)
    return candidates[:limit]


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


def build_manual_analysis(manual_player, manual_attributes, env_settings, simulation_result):
    manual_position = safe_text(manual_player.get("position"), "포지션 미입력")
    manual_name = safe_text(manual_player.get("name"), "이름 없는 직접 입력 노트")
    manual_age = manual_player.get("age") or "-"
    manual_club = safe_text(manual_player.get("club"), "소속팀 미입력")
    manual_nationality = safe_text(manual_player.get("nationality"), "국적 미입력")

    attr_scores = {
        "속도/기동성": safe_float(manual_attributes.get("speed"), 0),
        "드리블": safe_float(manual_attributes.get("dribble"), 0),
        "결정력": safe_float(manual_attributes.get("finishing"), 0),
        "패스/시야": safe_float(manual_attributes.get("passing"), 0),
        "피지컬": safe_float(manual_attributes.get("physical"), 0),
        "수비력": safe_float(manual_attributes.get("defending"), 0),
        "활동량": safe_float(manual_attributes.get("work_rate"), 0),
        "팀워크": safe_float(manual_attributes.get("teamwork"), 0),
        "의지력": safe_float(manual_attributes.get("determination"), 0),
        "압박 대처": safe_float(manual_attributes.get("pressing"), 0),
        "성장 잠재력": safe_float(manual_attributes.get("growth_potential"), 0),
    }

    strengths = sorted(attr_scores.items(), key=lambda item: item[1], reverse=True)[:3]
    weaknesses = sorted(attr_scores.items(), key=lambda item: item[1])[:2]
    strength_names = ", ".join([name for name, _ in strengths]) or "강점 데이터 부족"
    weakness_names = ", ".join([name for name, _ in weaknesses]) or "보완 데이터 부족"

    position_hint = position_training_hint(manual_position, weakness_names)
    training_recommendations = [
        "3개월: 가장 시급한 약점인 " + weakness_names + "을 중심으로 반복적인 훈련을 설계합니다.",
        "6개월: " + manual_position + " 역할에 꼭 필요한 핵심 능력인 " + strength_names + "을 강화해 실제 경기 적용력과 전술 적응력을 끌어올립니다.",
        "1년: 성장 잠재력과 실행력의 균형을 맞추며, 강점을 확장하는 동시에 약점을 보완하는 로드맵을 진행합니다.",
    ]

    risk_factors = []
    if safe_float(env_settings.get("training_intensity"), 0) >= 1.4:
        risk_factors.append("훈련 강도가 높아 피로 누적과 부상 위험이 커질 수 있습니다.")
    if str(env_settings.get("league_difficulty", "")).lower() in ("high", "elite"):
        risk_factors.append("리그 난이도가 높아 적응 부담과 출전 기회 변수에 민감할 수 있습니다.")
    if str(env_settings.get("risk_level", "")).lower() == "aggressive":
        risk_factors.append("공격형 리스크 성향은 성장 기회는 크지만 적응 실패 가능성도 함께 증가합니다.")

    career_advice = "현재 입력값 기준으로는 " + readable_setting("career_choice", env_settings.get("career_choice")) + "이 가장 적절한 선택지입니다. "
    if env_settings.get("career_choice") == "loan":
        career_advice += "출전 시간이 부족하다면 한 시즌 임대가 성장 속도를 높일 수 있습니다."
    elif env_settings.get("career_choice") == "transfer":
        career_advice += "환경 변화는 성장 자극이 크지만, 현재 피지컬/압박 대처가 낮다면 리스크를 먼저 점검해야 합니다."
    else:
        career_advice += "안정적인 환경에서 현재 강점을 유지하며 성장하는 것이 우선입니다."

    overall = (
        f"{manual_name}은(는) 나이 {manual_age}세, {manual_position}, {manual_club} 소속으로 보이며, "
        f"{strength_names}이 핵심 강점으로 보입니다. 현재 입력값과 시뮬레이션 결과를 종합하면, "
        f"성장 잠재력 {safe_float(manual_attributes.get('growth_potential'), 0)}/10 수준에서 {manual_nationality}의 환경 속에서 안정적인 성장을 기대할 수 있습니다."
    )

    mentor_candidates = manual_similarity_candidates(manual_player, manual_attributes, limit=5)
    mentor_guide = "이 선수는 현재 입력값 기준으로 멘토 후보와의 공통 강점을 바탕으로 성장 루트를 설계할 수 있습니다. " + position_hint

    return {
        "overall_summary": overall,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "strength_names": strength_names,
        "weakness_names": weakness_names,
        "training_recommendations": training_recommendations,
        "career_advice": career_advice,
        "risk_factors": risk_factors,
        "mentor_candidates": mentor_candidates,
        "mentor_guide": mentor_guide,
        "simulation_result": simulation_result,
        "env_settings": env_settings,
        "manual_player": manual_player,
        "manual_attributes": manual_attributes,
    }


def render_my_notes():
    st.title("My Scouting Notes")
    st.info(
        "이 화면은 직접 입력한 유망주 분석, 멘토 추천, 성장 가이드, 저장된 노트를 함께 보는 프로토타입 화면입니다. "
        "실제 Gemini API 호출은 없으며, FM 기반 proxy 능력치와 직접 입력값을 연결해 템플릿 기반 분석을 생성합니다."
    )

    st.subheader("직접 입력 유망주 분석 (prototype)")
    st.caption("선수 이름, 능력치, 메모를 입력하면 성장 잠재력, 강점/보완점, 훈련 방향, 멘토 후보, 멘토 기반 성장 가이드를 미리 확인할 수 있습니다.")

    with st.form("custom_note_form"):
        c1, c2 = st.columns(2)
        with c1:
            custom_name = st.text_input("유망주 이름", placeholder="예: Custom Prospect A")
            custom_age = st.number_input("나이", min_value=14, max_value=35, value=18, step=1)
            custom_position = st.text_input("포지션", placeholder="예: ST / CM / LB")
            custom_sub_position = st.text_input("세부 포지션", placeholder="예: CF / CM")
            custom_club = st.text_input("소속팀 / 학교", placeholder="예: Academy FC")
            custom_nationality = st.text_input("국적", placeholder="예: Korea")
            custom_foot = st.text_input("주발", placeholder="예: 오른발")
        with c2:
            custom_height = st.text_input("키(cm)", placeholder="예: 182")
            custom_note = st.text_area("관찰 메모", placeholder="예: 속도와 돌파는 좋지만 마무리와 수비 전개를 보완할 필요가 있음")
            speed = st.slider("속도/기동성", 1, 10, 7)
            dribble = st.slider("드리블", 1, 10, 6)
            finishing = st.slider("결정력", 1, 10, 5)
            passing = st.slider("패스/시야", 1, 10, 6)
            physical = st.slider("피지컬", 1, 10, 6)
            defending = st.slider("수비력", 1, 10, 5)
            work_rate = st.slider("활동량", 1, 10, 7)
            teamwork = st.slider("팀워크", 1, 10, 7)
            determination = st.slider("의지력", 1, 10, 7)
            pressing = st.slider("압박 대처", 1, 10, 5)
            growth_potential = st.slider("성장 잠재력", 1, 10, 8)

        training_intensity = st.slider("훈련 강도", 0.5, 2.0, 1.2, 0.1)
        playing_time = st.slider("출전 기회", 0.0, 1.0, 0.6, 0.05)
        league_difficulty = st.selectbox("리그/팀 수준", ["low", "medium", "high", "elite"], index=1, format_func=lambda value: readable_setting("league_difficulty", value))
        career_choice = st.radio("커리어 선택", ["stay", "loan", "transfer"], horizontal=True, format_func=lambda value: readable_setting("career_choice", value))
        risk_level = st.radio("리스크 성향", ["safe", "normal", "aggressive"], horizontal=True, index=1, format_func=lambda value: readable_setting("risk_level", value))

        submitted = st.form_submit_button("프로토타입 분석 생성")

    if submitted:
        env_settings = {
            "note_type": "manual_custom_prospect",
            "manual_player": {
                "name": custom_name,
                "age": int(custom_age),
                "position": custom_position,
                "sub_position": custom_sub_position,
                "club": custom_club,
                "nationality": custom_nationality,
                "foot": custom_foot,
                "height": custom_height,
                "observation_note": custom_note,
            },
            "manual_attributes": {
                "speed": float(speed),
                "dribble": float(dribble),
                "finishing": float(finishing),
                "passing": float(passing),
                "physical": float(physical),
                "defending": float(defending),
                "work_rate": float(work_rate),
                "teamwork": float(teamwork),
                "determination": float(determination),
                "pressing": float(pressing),
                "growth_potential": float(growth_potential),
            },
            "career_settings": {
                "training_intensity": float(training_intensity),
                "playing_time_opportunity": float(playing_time),
                "league_difficulty": league_difficulty,
                "career_choice": career_choice,
                "risk_level": risk_level,
            },
            "selected_mentor_profile_id": st.session_state.get("manual_selected_mentor_profile_id"),
            "selected_mentor_name": st.session_state.get("manual_selected_mentor_name"),
        }
        simulation_result = build_simulation_result(env_settings["career_settings"])
        analysis = build_manual_analysis(env_settings["manual_player"], env_settings["manual_attributes"], env_settings["career_settings"], simulation_result)
        simulation_result.update({
            "prototype_growth_score": simulation_result.get("prototype_growth_score"),
            "prototype_success_probability": simulation_result.get("prototype_success_probability"),
            "prototype_injury_risk": simulation_result.get("prototype_injury_risk"),
            "strengths": [name for name, _ in analysis["strengths"]],
            "weaknesses": [name for name, _ in analysis["weaknesses"]],
            "training_recommendations": analysis["training_recommendations"],
            "career_advice": analysis["career_advice"],
            "risk_factors": analysis["risk_factors"],
            "mentor_guide": analysis["mentor_guide"],
            "overall_summary": analysis["overall_summary"],
        })

        report_text = "\n\n".join([
            "AI 스카우팅 리포트 초안 (프로토타입)",
            f"종합 평가\n{analysis['overall_summary']}",
            "핵심 강점\n" + "; ".join([f"{name}({score}/10)" for name, score in analysis['strengths']]),
            "보완점\n" + "; ".join([f"{name}({score}/10)" for name, score in analysis['weaknesses']]),
            "추천 훈련 방향\n" + "\n".join(analysis['training_recommendations']),
            "멘토 기반 성장 가이드\n" + analysis['mentor_guide'],
            "커리어 선택 조언\n" + analysis['career_advice'],
            "장점과 리스크\n" + "\n".join(analysis['risk_factors'] or ["현재 입력값 기준 리스크는 아직 명확하지 않습니다."]),
            "예상 성장 방향\n" + "이 분석은 실제 예측 모델이 아니라 FM 기반 proxy 능력치와 직접 입력값으로 만든 템플릿 기반 가이드입니다.",
        ])

        st.session_state["custom_note_preview"] = {
            "env_settings": env_settings,
            "simulation_result": simulation_result,
            "report": report_text,
            "analysis": analysis,
            "player_name": custom_name,
        }
        st.session_state["manual_analysis_result"] = analysis
        st.session_state["manual_report_text"] = report_text

    preview = st.session_state.get("custom_note_preview")
    if preview:
        st.subheader("생성된 프로토타입 분석 미리보기")
        analysis = preview.get("analysis") or {}
        env_settings = normalize_env_settings(preview.get("env_settings"))
        career_settings = get_career_settings(env_settings)

        c1, c2, c3 = st.columns(3)
        c1.metric("성장 점수", preview["simulation_result"].get("prototype_growth_score", "-"))
        c2.metric("성공 가능성", format_percent(preview["simulation_result"].get("prototype_success_probability")))
        c3.metric("부상 리스크", format_percent(preview["simulation_result"].get("prototype_injury_risk")))

        st.markdown(f"<div class='scout-panel'><b>종합 평가</b><br>{analysis.get('overall_summary', '')}</div>", unsafe_allow_html=True)

        st.markdown(
            "<div class='scout-panel'>" +
            "<b>환경 요약</b><br>" +
            "<br>".join([
                setting_summary('training_intensity', career_settings.get('training_intensity')),
                setting_summary('playing_time_opportunity', career_settings.get('playing_time_opportunity')),
                setting_summary('league_difficulty', career_settings.get('league_difficulty')),
                setting_summary('career_choice', career_settings.get('career_choice')),
                setting_summary('risk_level', career_settings.get('risk_level')),
            ]) +
            "</div>",
            unsafe_allow_html=True,
        )

        cols = st.columns(2)
        with cols[0]:
            st.markdown("<div class='scout-panel'><b>핵심 강점</b><br>" + "<br>".join([f"• {name}: {score}/10" for name, score in analysis.get('strengths', [])]) + "</div>", unsafe_allow_html=True)
            st.markdown("<div class='scout-panel'><b>보완점</b><br>" + "<br>".join([f"• {name}: {score}/10" for name, score in analysis.get('weaknesses', [])]) + "</div>", unsafe_allow_html=True)
        with cols[1]:
            st.markdown("<div class='scout-panel'><b>추천 훈련 방향</b><br>" + "<br>".join([f"• {item}" for item in analysis.get('training_recommendations', [])]) + "</div>", unsafe_allow_html=True)
            st.markdown("<div class='scout-panel'><b>커리어 선택 조언</b><br>" + analysis.get('career_advice', '') + "</div>", unsafe_allow_html=True)

        st.subheader("유사 멘토 후보")
        mentor_candidates = analysis.get("mentor_candidates", [])
        if mentor_candidates:
            for mentor in mentor_candidates:
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
                        <p>이 멘토 후보는 직접 입력 능력치와 FM proxy 능력치를 비교했을 때 참고하기 좋은 형태의 프로토타입 추천입니다.</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("이 멘토 선택", key=f"manual_mentor_{mentor['profile_id']}", type="secondary"):
                    st.session_state["manual_selected_mentor_profile_id"] = mentor['profile_id']
                    st.session_state["manual_selected_mentor_name"] = mentor['name']
                    st.session_state["manual_mentor_summary"] = (
                        f"{mentor['name']}은(는) 현재 직접 입력 능력치와 유사한 강점을 보이는 후보입니다. "
                        f"공통 강점: {mentor['common_strengths']} / 차이점: {mentor['difference_hint']}"
                    )
                    st.success(f"{mentor['name']}을(를) 멘토 후보로 선택했습니다.")
        else:
            st.info("현재 입력값 기준으로 멘토 후보를 생성할 수 없었습니다. 프로필 속성 데이터가 없는 경우에는 기본 가이드만 표시됩니다.")

        mentor_name = st.session_state.get("manual_selected_mentor_name")
        mentor_summary = st.session_state.get("manual_mentor_summary")
        if mentor_name:
            st.markdown(
                f"<div class='scout-panel'><b>멘토 기반 성장 가이드</b><br>선택된 멘토: {mentor_name}<br>{mentor_summary or '선택한 멘토의 성장 가이드를 반영했습니다.'}</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div class='scout-panel'><b>장점과 리스크</b><br>" + "<br>".join(analysis.get('risk_factors', []) or ["현재 입력값 기준 리스크는 아직 충분하지 않습니다."]) + "</div>", unsafe_allow_html=True)

        if st.button("이 노트를 scouting_notes에 저장", type="primary"):
            try:
                saved = insert_scouting_note(
                    player_id=None,
                    profile_id=None,
                    env_settings=normalize_env_settings(preview.get("env_settings")),
                    simulation_result=preview["simulation_result"],
                    report=preview["report"],
                )
                st.success(f"직접 입력 노트가 저장되었습니다. note_id: {saved['note_id']}")
            except Exception as exc:
                st.error("직접 입력 노트 저장 중 오류가 발생했습니다.")
                with st.expander("개발 확인용 오류"):
                    st.exception(exc)

        with st.expander("개발자용 원본 JSON 보기"):
            st.json({"env_settings": preview.get("env_settings"), "simulation_result": preview.get("simulation_result"), "report": preview.get("report")})

        render_page_actions([
            ("🔎 새 유망주 검색", "유망주 검색", "primary"),
            ("📝 새 유망주 직접 입력", "내 스카우팅 노트"),
        ], title="저장 완료 · 다음 단계")

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
        st.info("현재 저장된 노트가 없습니다. 위에서 직접 입력한 커스텀 노트나 기존 저장 리포트를 확인할 수 있습니다.")
        render_page_actions([
            ("🔎 유망주 검색으로 이동", "유망주 검색", "primary"),
            ("📝 새 유망주 직접 입력", "내 스카우팅 노트"),
        ])
        return

    for _, note in notes.iterrows():
        env = parse_json_field(note.get("env_settings")) or {}
        sim = parse_json_field(note.get("simulation_result")) or {}
        manual_player = env.get("manual_player") if isinstance(env, dict) and isinstance(env.get("manual_player"), dict) else {}
        legacy_player = env.get("player") if isinstance(env, dict) and isinstance(env.get("player"), dict) else {}
        player_snapshot = manual_player or legacy_player
        if not player_snapshot and note.get("player_name"):
            player_snapshot = {
                "name": safe_text(note.get("player_name"), "이름 없는 노트"),
                "age": env.get("age"),
                "position": env.get("position"),
                "club": env.get("club"),
                "nationality": env.get("nationality"),
            }
        title = note_display_title(note)
        summary = safe_text(sim.get("overall_summary"), note_summary_text(note))
        strengths = sim.get("strengths") if isinstance(sim, dict) else []
        weaknesses = sim.get("weaknesses") if isinstance(sim, dict) else []
        mentor_name = env.get("selected_mentor_name") or "선택된 멘토 없음"
        growth_score = sim.get("prototype_growth_score", "-")
        injury_risk = sim.get("prototype_injury_risk")
        preview_text = safe_text(note.get("gemini_report"), "")

        st.markdown(
            f"""
            <div class="scout-panel">
                <h3 style="margin-top:0;">{title}</h3>
                <div class="muted">저장일 {note.get('created_at')}</div>
                <p><b>나이 / 포지션 / 소속팀 / 국적</b><br>
                {safe_text(player_snapshot.get('age'), '-') if isinstance(player_snapshot, dict) else '-'}세 ·
                {safe_text(player_snapshot.get('position'), '-') if isinstance(player_snapshot, dict) else '-'} ·
                {safe_text(player_snapshot.get('club'), '-') if isinstance(player_snapshot, dict) else '-'} ·
                {safe_text(player_snapshot.get('nationality'), '-') if isinstance(player_snapshot, dict) else '-'}
                </p>
                <p><b>종합 평가 요약</b><br>{summary}</p>
                <p><b>핵심 강점</b><br>{' · '.join(str(item) for item in strengths[:3]) if strengths else '정보 없음'}</p>
                <p><b>보완점</b><br>{' · '.join(str(item) for item in weaknesses[:2]) if weaknesses else '정보 없음'}</p>
                <p><b>선택한 멘토</b><br>{mentor_name}</p>
                <p><b>성장 가능성 / 부상 리스크</b><br>{growth_score} / {format_percent(injury_risk)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("상세 보기"):
            st.write("### 종합 평가")
            st.write(summary)
            if strengths:
                st.write("### 핵심 강점")
                for item in strengths:
                    st.write("- " + str(item))
            if weaknesses:
                st.write("### 보완점")
                for item in weaknesses:
                    st.write("- " + str(item))
            if env.get("selected_mentor_name"):
                st.write("### 선택한 멘토")
                st.write(env["selected_mentor_name"])
            if preview_text:
                st.write("### 리포트 요약")
                st.text(preview_text[:500])
        with st.expander("개발자용 원본 JSON 보기"):
            st.json({"env_settings": env, "simulation_result": sim, "gemini_report": note.get("gemini_report")})

    render_page_actions([
        ("🔎 새 유망주 검색", "유망주 검색", "primary"),
        ("📝 새 유망주 직접 입력", "내 스카우팅 노트"),
    ], title="다음 작업")


def render_home():
    status = get_selected_player_status()
    feature_cards = [
        {
            "title": "유망주 검색",
            "description": "DB에서 분석할 유망주를 검색하고 선택합니다.",
            "button_label": "유망주 찾기",
            "nav_target": "유망주 검색",
        },
        {
            "title": "통합 분석 대시보드",
            "description": "선택한 선수의 기본 정보, 능력치, 시장가치, 출전 기록을 확인합니다.",
            "button_label": "선수 분석 보기",
            "nav_target": "유망주 통합 분석",
        },
        {
            "title": "유사 선수 / 멘토 매칭",
            "description": "FM 기반 proxy 벡터와 능력치 비교로 유사 후보를 확인합니다.",
            "button_label": "유사 멘토 찾기",
            "nav_target": "유사 선수 후보",
        },
        {
            "title": "커리어 시뮬레이션",
            "description": "훈련 강도, 출전 기회, 리그 수준에 따른 성장 시나리오를 확인합니다.",
            "button_label": "시뮬레이션 시작",
            "nav_target": "커리어 시뮬레이션",
        },
        {
            "title": "AI 스카우팅 리포트",
            "description": "템플릿 기반 스카우팅 리포트 초안을 생성합니다.",
            "button_label": "리포트 생성",
            "nav_target": "AI 스카우팅 리포트",
        },
        {
            "title": "내 스카우팅 노트",
            "description": "직접 입력 유망주 분석, 멘토 추천, 저장된 노트를 확인합니다.",
            "button_label": "노트 작성/조회",
            "nav_target": "내 스카우팅 노트",
        },
        {
            "title": "DB 상태 확인",
            "description": "Supabase 연결과 데이터 상태를 확인합니다.",
            "button_label": "DB 상태 보기",
            "nav_target": "DB 상태 확인",
        },
    ]
    render_home_view(status, feature_cards)


def render_prospect_search():
    render_prospect_search_view()


def render_db_status():
    render_db_status_view()


def main():
    apply_ui_theme()
    init_navigation_state()
    render_app_header()

    page = st.session_state.get("current_page", "home")

    if page == "home":
        render_home_view()
    elif page == "prospect_search":
        render_prospect_search_view()
    elif page == "dashboard":
        render_dashboard()
    elif page == "legend_matching":
        render_legend_matching()
    elif page == "career_simulation":
        render_career_simulation()
    elif page == "ai_report":
        render_ai_report()
    elif page == "scouting_notes":
        render_my_notes()
    elif page == "db_status":
        render_db_status_view()
    else:
        render_home_view()

    st.divider()
    nav_cols = st.columns(4)
    with nav_cols[0]:
        if st.button("🏠 홈으로", use_container_width=True):
            navigate_to("home")
    with nav_cols[1]:
        if st.button("🔎 유망주 찾기", use_container_width=True):
            navigate_to("prospect_search")
    with nav_cols[2]:
        if st.button("📊 분석 보기", use_container_width=True):
            navigate_to("dashboard")
    with nav_cols[3]:
        if st.button("🗂️ DB 상태", use_container_width=True):
            navigate_to("db_status")


def render_prospect_search():
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
                    "selected_profile_id",
                    "selected_profile_fallback_note",
                    "selected_entity_type",
                ]:
                    st.session_state.pop(key, None)
            st.success("선수가 선택되었습니다. 유망주 통합 분석 화면에서 확인할 수 있습니다.")
            st.info("왼쪽 메뉴에서 '유망주 통합 분석'으로 이동하세요.")


def main():
    apply_theme()
    st.sidebar.title("NEXT-LEGEND FINDER")
    st.sidebar.caption("보조 메뉴 · 메인 이동은 상단 navigation chip과 화면 안의 버튼을 이용하세요.")
    menu = {
        "홈 / 서비스 소개": render_home,
        "유망주 검색": render_prospect_search,
        "유망주 통합 분석": render_dashboard,
        "유사 선수 후보": render_legend_matching,
        "커리어 시뮬레이션": render_career_simulation,
        "AI 스카우팅 리포트": render_ai_report,
        "내 스카우팅 노트": render_my_notes,
        "DB 상태 확인": render_db_status,
    }
    if "nav_page_request" in st.session_state:
        st.session_state["nav_page"] = st.session_state.pop("nav_page_request")
    page = st.sidebar.radio("메뉴", list(menu.keys()), key="nav_page")
    st.sidebar.divider()
    render_app_header(page)
    menu[page]()


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def readable_setting(key, value):
    if key == "training_intensity":
        number = safe_float(value, None)
        if number is None:
            return "알 수 없음"
        if number >= 1.4:
            return "높음"
        if number >= 0.9:
            return "보통"
        return "낮음"

    if key == "playing_time_opportunity":
        number = safe_float(value, None)
        if number is None:
            return "알 수 없음"
        if number >= 0.7:
            return "높음"
        if number >= 0.35:
            return "중간"
        return "낮음"

    maps = {
        "league_difficulty": {"low": "낮음", "medium": "중간", "high": "높음", "elite": "최상위"},
        "career_choice": {"stay": "잔류", "loan": "임대", "transfer": "이적"},
        "risk_level": {"safe": "안정형", "normal": "균형형", "aggressive": "공격형"},
    }
    return maps.get(key, {}).get(value, "알 수 없음" if value is None else str(value))


def compare_attributes(selected_attrs, candidate_attrs):
    if not isinstance(selected_attrs, dict) or not isinstance(candidate_attrs, dict):
        return {"common_high": [], "mentor_higher": [], "candidate_higher": [], "selected_higher": []}

    known_keys = [key for group in ATTRIBUTE_GROUPS.values() for key in group]
    keys = list(dict.fromkeys(known_keys + list(selected_attrs) + list(candidate_attrs)))
    common_high = []
    candidate_higher = []
    selected_higher = []

    for key in keys:
        selected_value = numeric_attr(selected_attrs, key)
        candidate_value = numeric_attr(candidate_attrs, key)
        if selected_value is None or candidate_value is None:
            continue
        if selected_value >= 12 and candidate_value >= 12:
            common_high.append((key, round((selected_value + candidate_value) / 2, 1)))
        diff = candidate_value - selected_value
        if diff >= 2:
            candidate_higher.append((key, round(diff, 1)))
        elif diff <= -2:
            selected_higher.append((key, round(abs(diff), 1)))

    return {
        "common_high": sorted(common_high, key=lambda item: item[1], reverse=True)[:3],
        "mentor_higher": sorted(candidate_higher, key=lambda item: item[1], reverse=True)[:3],
        "candidate_higher": sorted(candidate_higher, key=lambda item: item[1], reverse=True)[:3],
        "selected_higher": sorted(selected_higher, key=lambda item: item[1], reverse=True)[:2],
    }


def attr_names(rows):
    return ", ".join(attr_label(key) for key, _ in rows)


def position_training_hint(position, improvement_names):
    text = (position or "").lower()
    if "attack" in text or "forward" in text or "striker" in text:
        return f"공격수 유형이라면 {improvement_names}을 보완해 마무리뿐 아니라 연계와 침투 선택지를 넓히는 방향이 좋습니다."
    if "midfield" in text:
        return f"미드필더 유형이라면 {improvement_names}을 보완해 전개, 압박 회피, 전술 연결 능력을 키우는 방향이 좋습니다."
    if "defender" in text or "back" in text:
        return f"수비수 유형이라면 {improvement_names}을 보완해 수비 위치 선정과 빌드업 안정성을 함께 높이는 방향이 좋습니다."
    if "goalkeeper" in text:
        return f"골키퍼 유형이라면 {improvement_names}을 보완해 안정적인 경기 운영 능력을 키우는 방향이 좋습니다."
    return f"현재 포지션에서는 {improvement_names}을 중심으로 약점을 보완하고, 이미 높은 강점은 유지하는 방향이 적절합니다."


def generate_similarity_reason(selected_player, candidate_player, selected_attrs, candidate_attrs):
    comparison = compare_attributes(selected_attrs, candidate_attrs)
    common_names = attr_names(comparison["common_high"])
    candidate_higher_names = attr_names(comparison["candidate_higher"])
    selected_higher_names = attr_names(comparison["selected_higher"])

    if common_names:
        similarity_reason = (
            f"두 선수는 {common_names}에서 공통으로 높은 수치를 보여 유사한 역할 후보로 해석할 수 있습니다. "
            "pgvector 유사도는 FM 기반 proxy style_vector(24차원) 전반의 가까움을 함께 반영합니다."
        )
        common_strengths = common_names
    else:
        similarity_reason = (
            "공통으로 높게 나타난 세부 능력치는 제한적이지만, FM 기반 proxy style_vector(24차원) "
            "전반의 거리가 가까워 비교 후보로 제시되었습니다."
        )
        common_strengths = "세부 공통 강점 데이터가 부족합니다."

    difference_parts = []
    if candidate_higher_names:
        difference_parts.append(f"후보가 앞선 능력치는 {candidate_higher_names}입니다")
    if selected_higher_names:
        difference_parts.append(f"선택 선수가 앞선 능력치는 {selected_higher_names}입니다")
    differences = ". ".join(difference_parts) + "." if difference_parts else "뚜렷한 능력치 차이 데이터가 부족합니다."

    position = selected_player.get("position") or candidate_player.get("position") or "현재 포지션"
    improvement_names = candidate_higher_names or "세부 능력치"
    tactical_interpretation = (
        f"{position} 역할에서 {common_names or '전반적인 스타일'}을 공통 기반으로 활용할 수 있습니다. "
        f"{position_training_hint(position, improvement_names)}"
    )
    return {
        "comparison": comparison,
        "common_strengths": common_strengths,
        "differences": differences,
        "similarity_reason": similarity_reason,
        "tactical_interpretation": tactical_interpretation,
    }


def generate_mentor_guide(selected_player, mentor_player, selected_attrs, mentor_attrs, simulation_result=None):
    reason = generate_similarity_reason(selected_player, mentor_player, selected_attrs, mentor_attrs)
    comparison = reason["comparison"]
    if not comparison["common_high"] and not comparison["mentor_higher"]:
        limited = "현재 후보 선수의 세부 능력치 데이터가 부족하여 상세 멘토링은 제한적으로 제공됩니다."
        return {
            "similarity_reason": limited,
            "improvement_points": limited,
            "training_recommendation": "우선 선택 선수의 출전 기록과 시장가치 흐름을 함께 확인하며 기본 성장 방향을 설정하는 것이 좋습니다.",
            "career_advice": "현재 단계에서는 무리한 이적보다 안정적인 출전 시간을 확보할 수 있는 환경을 우선 검토하는 전략이 적합합니다.",
            "mentor_summary": limited,
        }

    common_names = attr_names(comparison["common_high"]) or "스타일 벡터 전반"
    improvement_names = attr_names(comparison["mentor_higher"]) or "세부 능력치"
    selected_better = attr_names(comparison["selected_higher"]) or "일부 강점"
    similarity_reason = reason["similarity_reason"]
    improvement_points = f"선택 유망주는 후보 선수와 비교했을 때 {improvement_names}에서 보완 여지가 있습니다. 반대로 {selected_better}에서는 선택 유망주가 이미 경쟁력을 보일 수 있습니다."
    training_recommendation = reason["tactical_interpretation"]
    career_advice = f"현재 유망주의 시장가치는 {money(selected_player.get('market_value_in_eur'))}입니다. 상위 리그 이적보다 안정적인 출전 시간을 확보할 수 있는 팀에서 성장하는 전략을 우선 검토하는 것이 좋습니다."
    if simulation_result:
        career_advice += f" 현재 시뮬레이션 기준 성공 가능성은 {format_percent(simulation_result.get('prototype_success_probability'))}입니다."
    mentor_summary = (
        f"멘토 후보 {mentor_player.get('name') or '-'} 참고 가이드. "
        f"유사 후보 이유: {similarity_reason} "
        f"보완할 점: {improvement_points} "
        f"추천 훈련: {training_recommendation} "
        f"커리어 조언: {career_advice} "
        "이 내용은 실제 레전드 성장 로그가 아니라 FM 기반 proxy 능력치 차이를 활용한 프로토타입 조언입니다."
    )
    return {
        "similarity_reason": similarity_reason,
        "improvement_points": improvement_points,
        "training_recommendation": training_recommendation,
        "career_advice": career_advice,
        "mentor_summary": mentor_summary,
    }


def simulation_comment(env_settings, simulation_result):
    training = readable_setting("training_intensity", env_settings.get("training_intensity"))
    playing = readable_setting("playing_time_opportunity", env_settings.get("playing_time_opportunity"))
    choice = readable_setting("career_choice", env_settings.get("career_choice"))
    risk = readable_setting("risk_level", env_settings.get("risk_level"))
    choice_text = {
        "stay": "잔류는 안정적인 출전 기회를 확보하는 시나리오입니다.",
        "loan": "임대는 단기 성장 기회를 찾는 시나리오입니다.",
        "transfer": "이적은 상위 리그 도전 또는 환경 변화를 선택하는 시나리오입니다.",
    }.get(env_settings.get("career_choice"), "커리어 선택 정보가 제한적입니다.")
    risk_text = {
        "safe": "안정형은 안정적 성장을 우선합니다.",
        "normal": "균형형은 성장과 리스크의 균형을 보는 설정입니다.",
        "aggressive": "공격형은 높은 성장 가능성과 높은 리스크를 함께 감수하는 설정입니다.",
    }.get(env_settings.get("risk_level"), "리스크 성향 정보가 제한적입니다.")
    return f"현재 설정은 훈련 강도 {training}, 출전 기회 {playing}, 커리어 선택 {choice}, 리스크 성향 {risk}입니다. {choice_text} {risk_text}"


def render_career_simulation():
    st.title("커리어 시뮬레이션 프로토타입")
    player = require_selected_player()
    if player is None:
        return
    profile = get_player_profile(player)
    render_player_profile_panel(player, profile)
    left, right = st.columns([1, 1.2])
    with left:
        st.subheader("시나리오 설정")
        training = st.slider("훈련 강도", 0.5, 2.0, 1.2, 0.1)
        playing_time = st.slider("출전 기회", 0.0, 1.0, 0.6, 0.05)
        league_difficulty = st.selectbox("리그 난이도", ["low", "medium", "high", "elite"], index=1, format_func=lambda value: readable_setting("league_difficulty", value))
        career_choice = st.radio("커리어 선택", ["stay", "loan", "transfer"], horizontal=True, format_func=lambda value: readable_setting("career_choice", value))
        risk_level = st.radio("리스크 성향", ["safe", "normal", "aggressive"], horizontal=True, index=1, format_func=lambda value: readable_setting("risk_level", value))
    env_settings = {
        "training_intensity": safe_float(training, 1.2),
        "playing_time_opportunity": safe_float(playing_time, 0.6),
        "league_difficulty": league_difficulty,
        "career_choice": career_choice,
        "risk_level": risk_level,
    }
    simulation_result = build_simulation_result(env_settings)
    st.session_state["env_settings"] = env_settings
    st.session_state["simulation_result"] = simulation_result
    with right:
        st.subheader("결과 요약")
        c1, c2, c3 = st.columns(3)
        c1.metric("성장 점수", simulation_result["prototype_growth_score"])
        c2.metric("성공 가능성", format_percent(simulation_result["prototype_success_probability"]))
        c3.metric("부상 리스크", format_percent(simulation_result["prototype_injury_risk"]))
        st.markdown(f'<div class="section-note">{simulation_comment(env_settings, simulation_result)}</div>', unsafe_allow_html=True)
    chart_data = pd.DataFrame({"성장 단계": ["현재", "1년 후", "2년 후", "3년 후"], "점수": [max(20, simulation_result["prototype_growth_score"] - 18), max(25, simulation_result["prototype_growth_score"] - 9), simulation_result["prototype_growth_score"], min(100, simulation_result["prototype_growth_score"] + 5)]})
    st.subheader("예상 성장 곡선")
    chart = alt.Chart(chart_data).mark_line(point=True, color="#2A9D8F", strokeWidth=3).encode(x=alt.X("성장 단계:N", title="성장 단계"), y=alt.Y("점수:Q", scale=alt.Scale(domain=[0, 100]), title="점수"), tooltip=["성장 단계:N", "점수:Q"]).properties(height=280)
    st.altair_chart(chart, use_container_width=True)
    st.markdown('<div class="warning-note">현재 결과는 실제 예측 모델이 아니라 UI 흐름 검증을 위한 프로토타입 시뮬레이션입니다.</div>', unsafe_allow_html=True)
    with st.expander("개발자용 시뮬레이션 원본 데이터 보기"):
        st.json({"env_settings": env_settings, "simulation_result": simulation_result})

    render_page_actions([
        ("📄 AI 스카우팅 리포트 생성", "AI 스카우팅 리포트", "primary"),
        ("📝 My Scouting Notes에 저장", "내 스카우팅 노트"),
    ])


def render_mentor_guide(selected_player, selected_profile, mentor_row, mentor_profile):
    selected_attrs = parse_json_field(selected_profile.get("attributes_jsonb")) if selected_profile else {}
    mentor_attrs = parse_json_field(mentor_profile.get("attributes_jsonb")) if mentor_profile else {}
    guide = generate_mentor_guide(selected_player, mentor_row, selected_attrs, mentor_attrs, st.session_state.get("simulation_result"))
    st.session_state["mentor_summary"] = guide["mentor_summary"]
    st.subheader("멘토링 가이드")
    st.info("현재 가이드는 실제 레전드 성장 로그가 아니라, 선택 유망주와 유사 선수 후보의 FM 기반 proxy 능력치 차이를 바탕으로 생성한 프로토타입 조언입니다.")
    st.markdown(f"""<div class="scout-panel"><h3 style="margin-top:0;">A. 왜 이 선수가 유사 후보인가</h3><p>{guide['similarity_reason']}</p><h3>B. 후보 선수와 비교했을 때 보완할 점</h3><p>{guide['improvement_points']}</p><h3>C. 추천 훈련 방향</h3><p>{guide['training_recommendation']}</p><h3>D. 커리어 선택 조언</h3><p>{guide['career_advice']}</p><h3>E. AI 리포트로 넘기기</h3><p>이 멘토링 내용을 AI 스카우팅 리포트 초안에 반영할 수 있습니다.</p></div>""", unsafe_allow_html=True)


def render_legend_matching():
    st.title("유사 선수 후보")
    player = require_selected_player()
    if player is None:
        return
    ctx = resolve_selected_player_context()
    profile = selected_profile()
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


def get_report_sections(player, profile, env_settings, simulation_result):
    attributes = parse_json_field(profile.get("attributes_jsonb")) if profile else {}
    mentality = parse_json_field(profile.get("mentality_jsonb")) if profile else {}
    basis = mentality.get("basis", {}) if isinstance(mentality, dict) else {}
    strength_names = attr_names(top_attributes(attributes, limit=3)) or "주요 강점 데이터"
    weakness_names = attr_names(top_attributes(attributes, limit=2, reverse=False)) or "보완 데이터"
    mental_names = attr_names(top_attributes(basis, MENTALITY_KEYS, 2, True)) or "멘탈 강점"
    mental_weak = attr_names(top_attributes(basis, MENTALITY_KEYS, 2, False)) or "멘탈 보완점"
    age = profile.get("age") if isinstance(profile, dict) else None
    player_name = player.get("name") or "선택 선수"
    position = player.get("position") or "포지션 정보 없음"
    club = player.get("current_club_name") or "소속팀 정보 없음"
    growth_score = safe_float(simulation_result.get("prototype_growth_score"), None)
    growth_text = f"{growth_score:.1f}" if growth_score is not None else "-"
    success_text = format_percent(simulation_result.get("prototype_success_probability"))
    injury_text = format_percent(simulation_result.get("prototype_injury_risk"))
    mentor_summary = st.session_state.get("mentor_summary")
    mentor_note = mentor_summary or "선택된 멘토가 없어 이번 초안에는 멘토링 가이드가 반영되지 않았습니다."

    return {
        "종합 평가": (
            f"{player_name}은 나이 {age if age is not None else '-'}, {position}, {club} 소속으로 확인됩니다. "
            f"선택 선수 데이터와 FM 기반 proxy 능력치를 종합하면 {strength_names}이 돋보이는 유형으로 해석할 수 있습니다."
        ),
        "강점": (
            f"높은 능력치는 {strength_names}이며, 멘탈리티 강점은 {mental_names}입니다. "
            "현재 역할에서 강점을 유지하면서 반복적으로 활용할 수 있는 경기 환경이 중요합니다."
        ),
        "보완점": (
            f"낮은 능력치는 {weakness_names}이며, 멘탈리티 보완점은 {mental_weak}입니다. "
            "상위 수준으로 이동하기 전 해당 지표가 실제 경기에서 어떤 제약으로 나타나는지 함께 확인해야 합니다."
        ),
        "훈련 제안": (
            f"{position_training_hint(position, weakness_names)} 단기적으로는 {strength_names}을 유지하고, "
            f"{weakness_names}과 {mental_weak}을 단계적으로 보완하는 훈련 구성이 적절합니다."
        ),
        "커리어 조언": (
            f"{simulation_comment(env_settings, simulation_result)} 시뮬레이션 결과는 성장 점수 {growth_text}, "
            f"성공 가능성 {success_text}, 부상 리스크 {injury_text}입니다. 이는 실제 예측 모델이 아닌 프로토타입 결과입니다."
        ),
        "멘토링 참고사항": mentor_note,
        "저장 정보": (
            "저장 시 선택 선수, 시뮬레이션 설정값, 프로토타입 결과, 템플릿 기반 리포트 초안이 "
            "기존 scouting_notes 테이블에 저장됩니다. 앱은 DB 스키마를 자동 변경하지 않습니다."
        ),
    }


def render_ai_report():
    st.title("AI 스카우팅 리포트 초안")
    player = require_selected_player()
    if player is None:
        return
    profile = get_player_profile(player)
    env_settings = st.session_state.get("env_settings")
    simulation_result = st.session_state.get("simulation_result")
    if env_settings is None or simulation_result is None:
        st.warning("먼저 커리어 시뮬레이션 화면에서 시뮬레이션 설정을 생성해 주세요.")
        render_page_actions([
            ("📈 커리어 시뮬레이션으로 이동", "커리어 시뮬레이션", "primary"),
        ])
        return
    render_player_profile_panel(player, profile)
    st.info("현재 리포트는 실제 Gemini API 호출 결과가 아니라, 선택 선수와 시뮬레이션 설정값을 바탕으로 생성한 템플릿 기반 초안입니다.")
    if st.session_state.get("mentor_summary"):
        st.markdown(f'<div class="section-note"><b>멘토링 반영 예정</b><br>{st.session_state["mentor_summary"]}</div>', unsafe_allow_html=True)
    if st.button("리포트 초안 생성", type="primary"):
        sections = get_report_sections(player, profile, env_settings, simulation_result)
        st.session_state["generated_report_sections"] = sections
        st.session_state["generated_report"] = sections_to_report_text(sections)
    sections = st.session_state.get("generated_report_sections")
    report = st.session_state.get("generated_report")
    if not sections:
        return
    for title, body in sections.items():
        st.markdown(f'<div class="report-block"><h3 style="margin-top:0;">{title}</h3>{body}</div>', unsafe_allow_html=True)
    if st.button("스카우팅 노트에 저장"):
        try:
            saved = insert_scouting_note(player_id=player["player_id"], profile_id=profile.get("profile_id") if profile else None, env_settings=env_settings, simulation_result=simulation_result, report=report)
            st.success(f"스카우팅 노트가 저장되었습니다. note_id: {saved['note_id']}")
        except Exception as exc:
            st.error("스카우팅 노트 저장 중 오류가 발생했습니다.")
            with st.expander("개발 확인용 오류"):
                st.exception(exc)

    render_page_actions([
        ("📝 My Scouting Notes에 저장/조회", "내 스카우팅 노트", "primary"),
        ("🔎 새 유망주 검색", "유망주 검색"),
    ])


if __name__ == "__main__":
    main()
