"""10x10 Grid 기반 플레이스타일 벡터 샘플 파이프라인.

원래 기획은 실제 경기 위치 이벤트 데이터(x, y)를 수집해 선수별 100차원
(10x10) 행동 빈도 벡터를 만들고 pgvector에 저장하는 것이었다. 이번 세션에서는
대규모 실제 데이터 수집 대신 ``data_samples/event_grid_sample.csv`` 샘플
데이터를 사용해 동일한 변환 로직을 "작동 가능한 축소판"으로 구현한다.

이 모듈은 DB/streamlit에 의존하지 않는 순수 함수만 담는다. heatmap은
시각화 라이브러리에 바로 넘길 수 있는 pandas DataFrame으로 반환한다.

좌표 가정: 경기장 좌표는 0~100 범위(가로 x: 자기 진영 0 -> 상대 진영 100,
세로 y: 왼쪽 터치라인 0 -> 오른쪽 터치라인 100).
"""

import pandas as pd

GRID_SIZE = 10
VECTOR_LENGTH = GRID_SIZE * GRID_SIZE


def normalize_coordinate(x, y):
    """좌표를 0~100(미만) 범위로 clamp한다."""
    nx = max(0.0, min(99.999, float(x)))
    ny = max(0.0, min(99.999, float(y)))
    return nx, ny


def get_grid_index(x, y):
    """(x, y) 좌표를 0~99 grid_index로 변환한다.

    grid_x = min(int(x // 10), 9)
    grid_y = min(int(y // 10), 9)
    grid_index = grid_y * 10 + grid_x
    """
    nx, ny = normalize_coordinate(x, y)
    grid_x = min(int(nx // 10), 9)
    grid_y = min(int(ny // 10), 9)
    return grid_y * GRID_SIZE + grid_x


def build_grid_vector(events_df, player_name):
    """events_df에서 player_name의 이벤트만 골라 100차원 빈도 벡터를 만든다."""
    vector = [0.0] * VECTOR_LENGTH

    if events_df is None or events_df.empty:
        return vector

    player_events = events_df[events_df["player_name"] == player_name]

    for _, row in player_events.iterrows():
        try:
            index = get_grid_index(row["x"], row["y"])
        except (TypeError, ValueError):
            continue
        vector[index] += 1.0

    return vector


def normalize_grid_vector(vector):
    """빈도 벡터를 합계 1이 되도록 정규화한다 (합계가 0이면 0 벡터)."""
    total = sum(vector)

    if total <= 0:
        return [0.0] * len(vector)

    return [round(value / total, 4) for value in vector]


def grid_vector_to_heatmap(vector):
    """100차원 벡터를 (grid_x, grid_y, value) 형태의 DataFrame으로 변환한다.

    Altair `rect` 마크 등으로 바로 10x10 heatmap을 그릴 수 있다.
    """
    if not vector or len(vector) != VECTOR_LENGTH:
        vector = [0.0] * VECTOR_LENGTH

    rows = []
    for index, value in enumerate(vector):
        grid_y, grid_x = divmod(index, GRID_SIZE)
        rows.append({"grid_index": index, "grid_x": grid_x, "grid_y": grid_y, "value": value})

    return pd.DataFrame(rows, columns=["grid_index", "grid_x", "grid_y", "value"])


def zone_label(grid_x, grid_y):
    """grid 좌표를 축구 용어("공격 3분의1 · 오른쪽" 등)로 설명한다."""
    if grid_x <= 2:
        third = "수비 3분의1"
    elif grid_x <= 6:
        third = "중간 3분의1"
    else:
        third = "공격 3분의1"

    if grid_y <= 2:
        side = "왼쪽"
    elif grid_y <= 6:
        side = "중앙"
    else:
        side = "오른쪽"

    return f"{third} · {side}"


def summarize_grid_style(vector, top_n=5):
    """100차원 벡터에서 주요 활동 구역 Top N과 요약 정보를 만든다."""
    if not vector or len(vector) != VECTOR_LENGTH:
        vector = [0.0] * VECTOR_LENGTH

    total = sum(vector)
    active_zone_count = sum(1 for value in vector if value > 0)

    indexed = [(index, value) for index, value in enumerate(vector) if value > 0]
    indexed.sort(key=lambda item: item[1], reverse=True)

    top_zones = []
    for index, value in indexed[:top_n]:
        grid_y, grid_x = divmod(index, GRID_SIZE)
        top_zones.append(
            {
                "grid_index": index,
                "grid_x": grid_x,
                "grid_y": grid_y,
                "value": value,
                "share": round(value / total, 3) if total else 0.0,
                "zone_label": zone_label(grid_x, grid_y),
            }
        )

    return {
        "total_actions": total,
        "active_zone_count": active_zone_count,
        "top_zones": top_zones,
    }


def list_sample_players(events_df):
    """샘플 이벤트 데이터에 등장하는 선수 이름 목록을 반환한다."""
    if events_df is None or events_df.empty or "player_name" not in events_df.columns:
        return []

    return sorted(events_df["player_name"].dropna().unique().tolist())
