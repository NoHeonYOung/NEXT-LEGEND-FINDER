import json
import tomllib
from pathlib import Path

import pandas as pd
import psycopg
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent.parent
SECRETS_PATH = BASE_DIR / ".streamlit" / "secrets.toml"

TABLES = [
    "clubs",
    "players",
    "appearances",
    "player_valuations",
    "player_profiles",
    "scouting_notes",
]


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


def selected_player_id():
    return st.session_state.get("selected_player_id")


def selected_profile_id():
    return st.session_state.get("selected_profile_id")


def selected_entity_type():
    return st.session_state.get("selected_entity_type") or "matched"


def selected_profile():
    profile_id = selected_profile_id()
    if profile_id:
        profile = query_one("select * from player_profiles where profile_id = %s limit 1", (profile_id,))
        if profile:
            return profile

    player = selected_player()
    if player:
        return get_player_profile(player)

    return None


def selected_player():
    entity_type = selected_entity_type()

    if entity_type == "fm_profile_only":
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

    player_id = selected_player_id()

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


def parse_json_field(value):
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    try:
        return json.loads(value)
    except Exception:
        return {}
