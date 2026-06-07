import json
import math
import re
import tomllib
from io import StringIO
from pathlib import Path

import pandas as pd
import psycopg


BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "Database_Project_Dataset"
SECRETS_PATH = BASE_DIR / ".streamlit" / "secrets.toml"

# 처음 테스트할 때 appearances.csv가 너무 크면 True로 바꾸세요.
# 최종 제출용 DB 구축 시에는 False로 두는 것을 추천합니다.
SAMPLE_MODE = False
SAMPLE_ROWS = 5000


def load_db_url():
    if not SECRETS_PATH.exists():
        raise FileNotFoundError(f"secrets.toml 파일이 없습니다: {SECRETS_PATH}")

    with open(SECRETS_PATH, "rb") as f:
        secrets = tomllib.load(f)

    db_url = secrets.get("SUPABASE_DB_URL")

    if not db_url:
        raise ValueError("secrets.toml에 SUPABASE_DB_URL 값이 없습니다.")

    return db_url


def read_csv_file(filename):
    path = DATASET_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {path}")

    if SAMPLE_MODE:
        return pd.read_csv(path, nrows=SAMPLE_ROWS, low_memory=False)

    return pd.read_csv(path, low_memory=False)


def clean_columns(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def to_int(value):
    if pd.isna(value) or value == "":
        return None

    try:
        return int(float(str(value).replace(",", "").strip()))
    except Exception:
        return None


def to_float(value):
    if pd.isna(value) or value == "":
        return None

    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


def to_date(value):
    if pd.isna(value) or value == "":
        return None

    text = str(value).strip()

    try:
        converted = pd.to_datetime(text, errors="raise")
        if pd.isna(converted):
            return None
        return converted.date().isoformat()
    except Exception:
        pass

    # merged_players.csv의 DOB 예: 10/9/2004 (17 years old)
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        day, month, year = match.groups()
        try:
            converted = pd.Timestamp(
                year=int(year),
                month=int(month),
                day=int(day)
            )
            return converted.date().isoformat()
        except Exception:
            return None

    return None


def normalize_name(name):
    if pd.isna(name):
        return ""

    return re.sub(r"\s+", " ", str(name).strip().lower())


def normalize_1_to_20(value):
    if pd.isna(value) or value == "":
        return 0.0

    try:
        v = float(str(value).strip())
        if math.isnan(v):
            return 0.0
        return max(0.0, min(1.0, v / 20.0))
    except Exception:
        return 0.0


def vector_to_pgvector(values):
    return "[" + ",".join(f"{float(v):.6f}" for v in values) + "]"


def create_tables(conn):
    sql = """
    create extension if not exists vector;
    create extension if not exists pgcrypto;

    drop table if exists scouting_notes cascade;
    drop table if exists player_profiles cascade;
    drop table if exists player_valuations cascade;
    drop table if exists appearances cascade;
    drop table if exists players cascade;
    drop table if exists clubs cascade;

    create table clubs (
        club_id bigint primary key,
        name text,
        domestic_competition_id text,
        squad_size integer,
        average_age numeric,
        stadium_name text,
        url text
    );

    create table players (
        player_id bigint primary key,
        name text,
        current_club_id bigint,
        current_club_name text,
        country_of_citizenship text,
        date_of_birth date,
        position text,
        sub_position text,
        foot text,
        height_in_cm integer,
        image_url text,
        market_value_in_eur bigint,
        highest_market_value_in_eur bigint,
        url text
    );

    create table appearances (
        appearance_id text primary key,
        game_id bigint,
        player_id bigint,
        date date,
        player_name text,
        competition_id text,
        goals integer,
        assists integer,
        yellow_cards integer,
        red_cards integer,
        minutes_played integer
    );

    create table player_valuations (
        valuation_id bigserial primary key,
        player_id bigint,
        date date,
        market_value_in_eur bigint,
        current_club_name text,
        current_club_id bigint,
        unique(player_id, date, current_club_id)
    );

    create table player_profiles (
        profile_id bigserial primary key,
        player_id bigint,
        fm_uid bigint,
        name text not null,
        age integer,
        club text,
        nationality text,
        position text,
        media_description text,
        attributes_jsonb jsonb,
        mentality_jsonb jsonb,
        style_vector vector(24),
        source_file text,
        created_at timestamptz default now()
    );

    create table scouting_notes (
        note_id uuid primary key default gen_random_uuid(),
        user_id uuid,
        player_id bigint,
        profile_id bigint,
        matched_profile_id bigint,
        env_settings jsonb,
        simulation_result jsonb,
        gemini_report text,
        created_at timestamptz default now()
    );

    create index idx_players_name on players(name);
    create index idx_appearances_player_id on appearances(player_id);
    create index idx_player_valuations_player_id on player_valuations(player_id);
    create index idx_player_profiles_name on player_profiles(name);
    create index idx_player_profiles_vector
        on player_profiles
        using ivfflat (style_vector vector_cosine_ops)
        with (lists = 100);
    """

    with conn.cursor() as cur:
        cur.execute(sql)

    conn.commit()


def copy_dataframe(conn, table_name, df):
    if df.empty:
        print(f"{table_name}: 입력할 데이터가 없습니다.")
        return

    work = df.copy()

    integer_columns = {
        "club_id",
        "squad_size",
        "player_id",
        "current_club_id",
        "height_in_cm",
        "market_value_in_eur",
        "highest_market_value_in_eur",
        "game_id",
        "goals",
        "assists",
        "yellow_cards",
        "red_cards",
        "minutes_played",
        "fm_uid",
        "age"
    }

    numeric_columns = {
        "average_age"
    }

    def clean_integer_for_copy(value):
        if pd.isna(value) or value == "":
            return ""
        try:
            return str(int(float(value)))
        except Exception:
            return ""

    def clean_numeric_for_copy(value):
        if pd.isna(value) or value == "":
            return ""
        try:
            return str(float(value))
        except Exception:
            return ""

    for col in work.columns:
        if col in integer_columns:
            work[col] = work[col].apply(clean_integer_for_copy)
        elif col in numeric_columns:
            work[col] = work[col].apply(clean_numeric_for_copy)

    work = work.where(pd.notna(work), "")

    buffer = StringIO()
    work.to_csv(buffer, index=False, header=False, na_rep="")
    buffer.seek(0)

    columns = ", ".join(work.columns)

    copy_sql = f"""
        copy {table_name} ({columns})
        from stdin
        with (format csv, header false, null '')
    """

    with conn.cursor() as cur:
        with cur.copy(copy_sql) as copy:
            copy.write(buffer.getvalue())

    conn.commit()
    print(f"{table_name}: {len(work):,}개 행 입력 완료")


def upload_clubs(conn):
    df = read_csv_file("clubs.csv")
    df = clean_columns(df)

    out = pd.DataFrame({
        "club_id": df["club_id"].apply(to_int),
        "name": df["name"],
        "domestic_competition_id": df["domestic_competition_id"],
        "squad_size": df["squad_size"].apply(to_int),
        "average_age": df["average_age"].apply(to_float),
        "stadium_name": df["stadium_name"],
        "url": df["url"]
    })

    out = out.dropna(subset=["club_id"])
    out = out.drop_duplicates(subset=["club_id"])

    copy_dataframe(conn, "clubs", out)


def upload_players(conn):
    df = read_csv_file("players.csv")
    df = clean_columns(df)

    out = pd.DataFrame({
        "player_id": df["player_id"].apply(to_int),
        "name": df["name"],
        "current_club_id": df["current_club_id"].apply(to_int),
        "current_club_name": df["current_club_name"],
        "country_of_citizenship": df["country_of_citizenship"],
        "date_of_birth": df["date_of_birth"].apply(to_date),
        "position": df["position"],
        "sub_position": df["sub_position"],
        "foot": df["foot"],
        "height_in_cm": df["height_in_cm"].apply(to_int),
        "image_url": df["image_url"],
        "market_value_in_eur": df["market_value_in_eur"].apply(to_int),
        "highest_market_value_in_eur": df["highest_market_value_in_eur"].apply(to_int),
        "url": df["url"]
    })

    out = out.dropna(subset=["player_id"])
    out = out.drop_duplicates(subset=["player_id"])

    copy_dataframe(conn, "players", out)


def upload_appearances(conn):
    df = read_csv_file("appearances.csv")
    df = clean_columns(df)

    out = pd.DataFrame({
        "appearance_id": df["appearance_id"],
        "game_id": df["game_id"].apply(to_int),
        "player_id": df["player_id"].apply(to_int),
        "date": df["date"].apply(to_date),
        "player_name": df["player_name"],
        "competition_id": df["competition_id"],
        "goals": df["goals"].apply(to_int),
        "assists": df["assists"].apply(to_int),
        "yellow_cards": df["yellow_cards"].apply(to_int),
        "red_cards": df["red_cards"].apply(to_int),
        "minutes_played": df["minutes_played"].apply(to_int)
    })

    out = out.dropna(subset=["appearance_id"])
    out = out.drop_duplicates(subset=["appearance_id"])

    copy_dataframe(conn, "appearances", out)


def upload_player_valuations(conn):
    df = read_csv_file("player_valuations.csv")
    df = clean_columns(df)

    out = pd.DataFrame({
        "player_id": df["player_id"].apply(to_int),
        "date": df["date"].apply(to_date),
        "market_value_in_eur": df["market_value_in_eur"].apply(to_int),
        "current_club_name": df["current_club_name"],
        "current_club_id": df["current_club_id"].apply(to_int)
    })

    out = out.dropna(subset=["player_id", "date"])
    out = out.drop_duplicates(subset=["player_id", "date", "current_club_id"])

    copy_dataframe(conn, "player_valuations", out)


def build_player_key():
    players = read_csv_file("players.csv")
    players = clean_columns(players)

    key = pd.DataFrame({
        "player_id": players["player_id"].apply(to_int),
        "name_key": players["name"].apply(normalize_name),
        "dob_key": players["date_of_birth"].apply(to_date)
    })

    key = key.dropna(subset=["player_id"])
    key = key.drop_duplicates(subset=["name_key", "dob_key"])

    return key


def make_attributes_json(row, attribute_features):
    data = {}

    for col in attribute_features:
        data[col] = to_int(row.get(col))

    return json.dumps(data, ensure_ascii=False)


def make_mentality_json(row, mentality_features):
    basis = {}

    for col in mentality_features:
        basis[col] = to_int(row.get(col))

    valid_scores = [v for v in basis.values() if v is not None]

    if valid_scores:
        # FM 능력치가 1~20이므로 100점 척도로 변환
        mentality_score = round(sum(valid_scores) / len(valid_scores) * 5, 2)
    else:
        mentality_score = None

    interpretation = []

    if "Det" in basis:
        interpretation.append("Det는 성장 의지와 훈련 지속성을 나타내는 proxy 지표로 사용하였다.")
    if "Wor" in basis:
        interpretation.append("Wor는 활동량과 성실성을 나타내는 proxy 지표로 사용하였다.")
    if "Tea" in basis:
        interpretation.append("Tea는 팀워크와 전술 적응력을 나타내는 proxy 지표로 사용하였다.")
    if "Prof" in basis:
        interpretation.append("Prof는 프로의식과 자기관리 성향을 나타내는 proxy 지표로 사용하였다.")
    if "Pres" in basis:
        interpretation.append("Pres는 압박 상황 대응력을 나타내는 proxy 지표로 사용하였다.")
    if "Cons" in basis:
        interpretation.append("Cons는 경기력의 꾸준함을 나타내는 proxy 지표로 사용하였다.")
    if "Temp" in basis:
        interpretation.append("Temp는 감정 조절 성향을 나타내는 proxy 지표로 사용하였다.")

    data = {
        "source": "merged_players.csv",
        "evidence_type": "fm_attribute_proxy",
        "mentality_score": mentality_score,
        "basis": basis,
        "interpretation": interpretation,
        "confidence": 0.7
    }

    return json.dumps(data, ensure_ascii=False)


def make_style_vector(row, style_features):
    values = []

    for col in style_features:
        values.append(normalize_1_to_20(row.get(col)))

    while len(values) < 24:
        values.append(0.0)

    values = values[:24]

    return vector_to_pgvector(values)


def upload_player_profiles(conn):
    df = read_csv_file("merged_players.csv")
    df = clean_columns(df)

    player_key = build_player_key()

    style_features = [
        "Acc", "Pac", "Sta", "Str", "Agi", "Bal", "Dri", "Fir",
        "Fin", "Pas", "Vis", "OtB", "Tec", "Wor", "Tea", "Det",
        "Dec", "Ant", "Cmp", "Pos", "Tck", "Mar", "Ldr", "Agg"
    ]

    attribute_features = [
        "Acc", "Pac", "Sta", "Str", "Agi", "Bal", "Dri", "Fir",
        "Fin", "Pas", "Vis", "OtB", "Tec", "Wor", "Tea", "Det",
        "Dec", "Ant", "Cmp", "Pos", "Tck", "Mar", "Ldr", "Agg",
        "Prof", "Pres", "Cons", "Temp", "Spor", "Loy", "Amb",
        "Inj Pr", "Dirt", "Cont"
    ]

    mentality_features = [
        "Det", "Wor", "Tea", "Ldr", "Prof", "Pres",
        "Cons", "Temp", "Spor", "Agg", "Loy", "Amb"
    ]

    style_features = [c for c in style_features if c in df.columns]
    attribute_features = [c for c in attribute_features if c in df.columns]
    mentality_features = [c for c in mentality_features if c in df.columns]

    df["name_key"] = df["Name"].apply(normalize_name)
    df["dob_key"] = df["DOB"].apply(to_date)

    df = df.merge(
        player_key,
        on=["name_key", "dob_key"],
        how="left"
    )

    if "Media Description" not in df.columns:
        df["Media Description"] = None

    out = pd.DataFrame({
        "player_id": df["player_id"].apply(to_int),
        "fm_uid": df["UID"].apply(to_int),
        "name": df["Name"],
        "age": df["Age"].apply(to_int),
        "club": df["Club"],
        "nationality": df["Nat"],
        "position": df["Position"],
        "media_description": df["Media Description"],
        "attributes_jsonb": df.apply(
            lambda row: make_attributes_json(row, attribute_features),
            axis=1
        ),
        "mentality_jsonb": df.apply(
            lambda row: make_mentality_json(row, mentality_features),
            axis=1
        ),
        "style_vector": df.apply(
            lambda row: make_style_vector(row, style_features),
            axis=1
        ),
        "source_file": "merged_players.csv"
    })

    out = out.dropna(subset=["name"])
    out = out.drop_duplicates(subset=["fm_uid"])

    copy_dataframe(conn, "player_profiles", out)


def print_table_counts(conn):
    table_names = [
        "clubs",
        "players",
        "appearances",
        "player_valuations",
        "player_profiles",
        "scouting_notes"
    ]

    print("\n테이블별 행 개수")

    with conn.cursor() as cur:
        for table_name in table_names:
            cur.execute(f"select count(*) from {table_name};")
            count = cur.fetchone()[0]
            print(f"- {table_name}: {count:,} rows")


def main():
    print("데이터셋 폴더:", DATASET_DIR)

    if not DATASET_DIR.exists():
        raise FileNotFoundError(f"데이터셋 폴더가 없습니다: {DATASET_DIR}")

    db_url = load_db_url()

    print("Supabase 연결 중...")

    with psycopg.connect(db_url) as conn:
        print("6개 테이블 생성 중...")
        create_tables(conn)

        print("clubs.csv 업로드 중...")
        upload_clubs(conn)

        print("players.csv 업로드 중...")
        upload_players(conn)

        print("appearances.csv 업로드 중...")
        upload_appearances(conn)

        print("player_valuations.csv 업로드 중...")
        upload_player_valuations(conn)

        print("merged_players.csv 기반 player_profiles 업로드 중...")
        upload_player_profiles(conn)

        print_table_counts(conn)

    print("\n완료: Supabase에 6개 테이블 생성 및 초기 데이터 입력 완료")


if __name__ == "__main__":
    main()