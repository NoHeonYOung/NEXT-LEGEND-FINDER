import tomllib
from pathlib import Path

import altair as alt
import pandas as pd
import psycopg
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
SECRETS_PATH = BASE_DIR / ".streamlit" / "secrets.toml"

st.set_page_config(
    page_title="NEXT-LEGEND FINDER",
    layout="wide"
)


def load_db_url():
    with open(SECRETS_PATH, "rb") as f:
        secrets = tomllib.load(f)

    return secrets["SUPABASE_DB_URL"]


@st.cache_resource
def get_connection():
    return psycopg.connect(load_db_url())


def query_df(sql, params=None):
    conn = get_connection()

    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        columns = [desc.name for desc in cur.description]

    return pd.DataFrame(rows, columns=columns)


def query_one(sql, params=None):
    conn = get_connection()

    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        row = cur.fetchone()

        if row is None:
            return None

        columns = [desc.name for desc in cur.description]
        return dict(zip(columns, row))


def table_count(table_name):
    result = query_one(f"select count(*) as count from {table_name}")
    return result["count"]


def preview_table(table_name):
    allowed = [
        "clubs",
        "players",
        "appearances",
        "player_valuations",
        "player_profiles",
        "scouting_notes"
    ]

    if table_name not in allowed:
        raise ValueError("허용되지 않은 테이블입니다.")

    return query_df(f"select * from {table_name} limit 100")


def search_players(keyword):
    sql = """
        select
            player_id,
            name,
            current_club_name,
            country_of_citizenship,
            position,
            sub_position,
            market_value_in_eur,
            image_url
        from players
        where name ilike %s
        order by market_value_in_eur desc nulls last
        limit 30
    """

    return query_df(sql, (f"%{keyword}%",))


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
    """

    return query_df(sql, (player_id,))


def get_appearances(player_id):
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
        limit 100
    """

    return query_df(sql, (player_id,))


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


st.title("NEXT-LEGEND FINDER")
st.caption("Supabase 기반 축구 유망주 데이터베이스 구축 확인용 Streamlit 앱")

tab1, tab2, tab3 = st.tabs([
    "DB 구축 확인",
    "선수 검색",
    "테이블 조회"
])


with tab1:
    st.subheader("Supabase 테이블 생성 및 초기 데이터 확인")

    tables = [
        "clubs",
        "players",
        "appearances",
        "player_valuations",
        "player_profiles",
        "scouting_notes"
    ]

    try:
        count_data = []

        for table in tables:
            count_data.append({
                "table_name": table,
                "row_count": table_count(table)
            })

        count_df = pd.DataFrame(count_data)

        st.success("Supabase 연결 성공")
        st.dataframe(count_df, use_container_width=True)

    except Exception as e:
        st.error("Supabase 연결 또는 테이블 조회 중 오류 발생")
        st.exception(e)


with tab2:
    st.subheader("선수 검색 및 프로필 확인")

    keyword = st.text_input(
        "선수 이름을 입력하세요",
        placeholder="예: Messi, Bellingham, Son"
    )

    if keyword:
        results = search_players(keyword)

        if results.empty:
            st.warning("검색 결과가 없습니다.")
        else:
            st.write("검색 결과")
            st.dataframe(results, use_container_width=True)

            options = {}

            for _, row in results.iterrows():
                label = (
                    f"{row['name']} | "
                    f"{row['current_club_name']} | "
                    f"{row['position']} | "
                    f"{row['player_id']}"
                )
                options[label] = row["player_id"]

            selected = st.selectbox("분석할 선수 선택", list(options.keys()))
            player_id = int(options[selected])

            player = get_player(player_id)

            st.divider()

            col1, col2 = st.columns([1, 2])

            with col1:
                st.subheader("선수 기본 정보")

                if player.get("image_url"):
                    st.image(player["image_url"], width=180)

                st.write(f"이름: {player.get('name')}")
                st.write(f"소속팀: {player.get('current_club_name')}")
                st.write(f"국적: {player.get('country_of_citizenship')}")
                st.write(f"포지션: {player.get('position')}")
                st.write(f"세부 포지션: {player.get('sub_position')}")
                st.write(f"주발: {player.get('foot')}")
                st.write(f"키: {player.get('height_in_cm')} cm")
                st.write(f"현재 시장가치: {player.get('market_value_in_eur')}")
                st.write(f"최고 시장가치: {player.get('highest_market_value_in_eur')}")

            with col2:
                st.subheader("시장가치 변화")

                valuations = get_valuations(player_id)

                if valuations.empty:
                    st.info("시장가치 데이터가 없습니다.")
                else:
                    valuations["date"] = pd.to_datetime(valuations["date"])
                    valuations["market_value_in_eur"] = pd.to_numeric(
                        valuations["market_value_in_eur"],
                        errors="coerce"
                    )

                    chart = (
                        alt.Chart(valuations)
                        .mark_line(point=True)
                        .encode(
                            x="date:T",
                            y="market_value_in_eur:Q",
                            tooltip=[
                                "date:T",
                                "market_value_in_eur:Q",
                                "current_club_name:N"
                            ]
                        )
                    )

                    st.altair_chart(chart, use_container_width=True)

            st.subheader("최근 출전 기록")
            appearances = get_appearances(player_id)

            if appearances.empty:
                st.info("출전 기록이 없습니다.")
            else:
                st.dataframe(appearances, use_container_width=True)

            st.divider()

            st.subheader("FM 기반 정성적 프로필")

            profile = get_profile_by_player_id(player_id)

            if profile is None:
                profile = get_profile_by_name(player["name"])

            if profile is None:
                st.warning("연결된 player_profiles 데이터가 없습니다.")
            else:
                pcol1, pcol2 = st.columns(2)

                with pcol1:
                    st.write("프로필 기본 정보")
                    st.json({
                        "profile_id": profile.get("profile_id"),
                        "player_id": profile.get("player_id"),
                        "fm_uid": profile.get("fm_uid"),
                        "name": profile.get("name"),
                        "age": profile.get("age"),
                        "club": profile.get("club"),
                        "nationality": profile.get("nationality"),
                        "position": profile.get("position"),
                        "media_description": profile.get("media_description")
                    })

                with pcol2:
                    st.write("멘탈리티 JSONB")
                    st.json(profile.get("mentality_jsonb"))

                st.write("능력치 JSONB")
                st.json(profile.get("attributes_jsonb"))

                st.subheader("pgvector 기반 유사 선수 TOP 10")

                similar = get_similar_players(profile["profile_id"])

                if similar.empty:
                    st.info("유사 선수 검색 결과가 없습니다.")
                else:
                    st.dataframe(similar, use_container_width=True)


with tab3:
    st.subheader("Supabase 테이블 직접 조회")

    table_name = st.selectbox(
        "조회할 테이블 선택",
        [
            "clubs",
            "players",
            "appearances",
            "player_valuations",
            "player_profiles",
            "scouting_notes"
        ]
    )

    try:
        df = preview_table(table_name)
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error("테이블 조회 중 오류 발생")
        st.exception(e)