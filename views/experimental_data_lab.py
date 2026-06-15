"""Experimental Data Lab: 원래 기획했던 데이터 엔지니어링 확장 기능의 "작동 가능한 축소판".

이 화면은 세 가지 실험을 보여준다.

1. 10x10 Grid Vector Demo: 샘플 이벤트 좌표(x, y) -> 100차원 grid vector ->
   heatmap / Top 5 활동 구역. (``grid_pipeline.py``)
2. Article Evidence Demo: 사용자가 입력한 기사/스카우팅 문장에서 9개
   mentality category에 대한 evidence를 추출한다. (``evidence_extractor.py``)
3. Gemini API / Fallback Status: Gemini API key 유무와 fallback 동작을 보여준다.
   (``gemini_client.py``)

이 화면은 sample CSV / 사용자 입력 텍스트만 사용하며, Supabase에는 아무것도
쓰지 않는다. app.py를 import하지 않는다.
"""

import os

import altair as alt
import pandas as pd
import streamlit as st

from evidence_extractor import (
    CATEGORY_LABELS,
    EVIDENCE_CATEGORIES,
    extract_mentality_evidence,
)
from gemini_client import DEFAULT_GEMINI_MODEL, get_gemini_api_key, is_gemini_available
from grid_pipeline import (
    build_grid_vector,
    grid_vector_to_heatmap,
    list_sample_players,
    normalize_grid_vector,
    summarize_grid_style,
)

SAMPLE_EVENT_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data_samples",
    "event_grid_sample.csv",
)


@st.cache_data
def _load_sample_events():
    if not os.path.exists(SAMPLE_EVENT_CSV_PATH):
        return pd.DataFrame(columns=["player_name", "team_name", "match_id", "event_type", "x", "y", "minute"])
    return pd.read_csv(SAMPLE_EVENT_CSV_PATH)


def _render_grid_vector_section():
    st.subheader("1. 10x10 Grid Vector Demo")
    st.markdown(
        "원래 기획은 실제 경기 위치 이벤트(패스/슈팅/태클 등의 x, y 좌표)를 "
        "모아 선수별 100차원(10x10) 행동 빈도 벡터를 만들고 pgvector에 저장하는 것이었습니다. "
        "이번 축소판에서는 `data_samples/event_grid_sample.csv`의 샘플 이벤트 데이터로 "
        "동일한 변환 로직을 직접 실행해 봅니다."
    )

    events_df = _load_sample_events()

    if events_df.empty:
        st.warning("샘플 이벤트 데이터(data_samples/event_grid_sample.csv)를 찾을 수 없습니다.")
        return

    players = list_sample_players(events_df)
    selected_player = st.selectbox("샘플 선수 선택", players, key="data_lab_grid_player")

    player_events = events_df[events_df["player_name"] == selected_player]
    if not player_events.empty:
        team_name = player_events.iloc[0]["team_name"]
        st.caption(f"{selected_player} · {team_name} · 샘플 이벤트 {len(player_events)}건")

    raw_vector = build_grid_vector(events_df, selected_player)
    normalized_vector = normalize_grid_vector(raw_vector)

    heatmap_df = grid_vector_to_heatmap(normalized_vector)

    chart = (
        alt.Chart(heatmap_df)
        .mark_rect()
        .encode(
            x=alt.X("grid_x:O", title="가로 grid (자기 진영 0 → 상대 진영 9)"),
            y=alt.Y("grid_y:O", title="세로 grid (왼쪽 0 → 오른쪽 9)", sort="descending"),
            color=alt.Color("value:Q", title="비율", scale=alt.Scale(scheme="oranges")),
            tooltip=["grid_index", "grid_x", "grid_y", "value"],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)

    summary = summarize_grid_style(normalized_vector)
    c1, c2 = st.columns(2)
    c1.metric("활동 구역 수 (100개 중)", summary["active_zone_count"])
    c2.metric("정규화 벡터 합계", round(sum(normalized_vector), 3))

    st.markdown("**Top 5 활동 구역**")
    if summary["top_zones"]:
        top_zones_df = pd.DataFrame(summary["top_zones"])[["grid_index", "zone_label", "value", "share"]]
        top_zones_df.columns = ["grid_index", "구역", "비율(value)", "전체 대비 비중"]
        st.dataframe(top_zones_df, use_container_width=True, hide_index=True)
    else:
        st.info("해당 선수의 샘플 이벤트가 없습니다.")

    with st.expander("100차원 grid vector 원본 값 보기"):
        st.json({"raw_vector": raw_vector, "normalized_vector": normalized_vector})

    st.markdown(
        '<div class="section-note">'
        "이 100차원 grid vector는 '유사 선수 후보' 화면에서 사용하는 24차원 FM proxy "
        "<code>style_vector</code>와는 완전히 다른 데이터입니다. style_vector는 FM 능력치 기반 "
        "플레이스타일 근사값이고, grid vector는 실제 경기 위치 이벤트 기반 활동 분포입니다. "
        "현재 Supabase에는 grid vector를 저장하는 테이블이 없으며, 이 화면은 샘플 CSV로만 동작합니다."
        "</div>",
        unsafe_allow_html=True,
    )


def _render_evidence_section():
    st.subheader("2. Article Evidence Demo")
    st.markdown(
        "원래 기획은 선수 관련 기사를 대량으로 수집해 Gemini로 9개 mentality category에 "
        "대한 evidence를 추출하고 DB에 누적하는 것이었습니다. 이번 축소판에서는 **사용자가 "
        "직접 입력한 기사/스카우팅 문장 1건**에 대해서만 추출을 실행하며, 결과는 DB에 "
        "저장되지 않고 화면에만 표시됩니다."
    )

    with st.form("evidence_form"):
        player_name = st.text_input("선수 이름", value="Sample Player")
        source_title = st.text_input("기사/노트 제목 (선택)", value="")
        source_url = st.text_input("출처 URL (선택, 메타데이터로만 표시됨)", value="")
        snippet_text = st.text_area(
            "기사/스카우팅 문장 (영어 또는 한국어)",
            height=140,
            placeholder=(
                "예: He is known for his incredible work rate and composure under pressure, "
                "always the first to press and the calmest on the ball in big games."
            ),
        )
        use_gemini = st.checkbox(
            "Gemini API 사용 시도 (key가 없으면 자동으로 fallback)",
            value=False,
        )
        submitted = st.form_submit_button("Evidence 추출 실행")

    if not submitted:
        return

    if not snippet_text.strip():
        st.warning("기사/스카우팅 문장을 입력해 주세요.")
        return

    result = extract_mentality_evidence(
        player_name=player_name or "Sample Player",
        source_title=source_title,
        source_url=source_url,
        text=snippet_text,
        use_gemini=use_gemini,
    )
    st.session_state["data_lab_evidence_result"] = result

    result = st.session_state.get("data_lab_evidence_result")
    if not result:
        return

    mode_label = "Gemini" if result["mode"] == "gemini" else "Rule-based fallback"
    st.markdown(f"**추출 모드:** {mode_label}")

    if result.get("fallback_reason"):
        st.info(f"Fallback 사유: {result['fallback_reason']}")

    if result.get("source_title") or result.get("source_url"):
        st.caption(f"출처 메타데이터: {result.get('source_title') or '-'} / {result.get('source_url') or '-'}")

    rows = []
    for category in EVIDENCE_CATEGORIES:
        rows.append(
            {
                "category": CATEGORY_LABELS[category],
                "score": result["scores"][category],
                "confidence": result["confidence"][category],
                "matched_keywords": ", ".join(result.get("matched_keywords", {}).get(category, [])),
            }
        )
    evidence_df = pd.DataFrame(rows)
    evidence_df.columns = ["Category", "Score (0~1)", "Confidence (0~1)", "매칭 키워드"]
    st.dataframe(evidence_df, use_container_width=True, hide_index=True)

    st.markdown("**Evidence Summary**")
    st.markdown(f'<div class="section-note">{result["evidence_summary"]}</div>', unsafe_allow_html=True)

    if result.get("risk_note"):
        st.markdown(f'<div class="warning-note">위험 신호 노트: {result["risk_note"]}</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="warning-note">'
        "이 결과는 사용자가 입력한 텍스트 1건에 대한 데모이며, 실제 대량 기사 수집/분석 결과가 "
        "아닙니다. confidence가 낮은 항목은 참고용으로만 활용해야 합니다."
        "</div>",
        unsafe_allow_html=True,
    )


def _render_gemini_status_section():
    st.subheader("3. Gemini API / Fallback Status")

    available = is_gemini_available()
    has_key = get_gemini_api_key() is not None

    if available:
        st.success(f"Gemini API 사용 가능 (model: {DEFAULT_GEMINI_MODEL})")
    elif has_key:
        st.warning(
            "GEMINI_API_KEY는 설정되어 있지만 `google-generativeai` 패키지가 설치되어 있지 않습니다. "
            "Rule-based fallback이 사용됩니다."
        )
    else:
        st.info(
            "GEMINI_API_KEY / GOOGLE_API_KEY가 설정되어 있지 않습니다. "
            "모든 evidence 추출은 Rule-based fallback으로 동작합니다."
        )

    st.markdown(
        """
**Key 탐색 순서**: `st.secrets["GEMINI_API_KEY"]` → `st.secrets["GOOGLE_API_KEY"]` →
환경변수 `GEMINI_API_KEY` → 환경변수 `GOOGLE_API_KEY`

**동작 원칙**
- API key가 없거나 호출에 실패하면 항상 rule-based fallback으로 전환됩니다.
- Gemini 호출은 위 Article Evidence Demo의 "추출 실행" 버튼을 누를 때만 1회 발생하며,
  자동/반복 호출은 없습니다.
- API key 값은 화면에 출력되지 않습니다.
- `google-generativeai` 패키지가 설치되어 있지 않아도 앱은 정상 동작합니다 (import는
  버튼 클릭 시점에만 시도됩니다).
        """
    )


def _render_pipeline_overview_section():
    st.subheader("4. Data Engineering Pipeline 설명")
    st.markdown(
        """
이 화면에서 실행한 두 가지 데모는 원래 기획했던 데이터 파이프라인의 일부를
**작동 가능한 축소판**으로 구현한 것입니다.

| 단계 | 원래 기획 | 이번 세션 구현 |
| --- | --- | --- |
| 이벤트 데이터 수집 | 외부 이벤트 데이터 API에서 전체 선수 대상 대량 수집 | `data_samples/event_grid_sample.csv` (샘플 5명) |
| Grid Vector 생성 | 100차원 vector를 `player_grid_vectors` (pgvector) 테이블에 저장 | `grid_pipeline.py`로 즉석 계산, DB 저장 없음 |
| 기사 수집 | 대량 크롤링 + `player_article_sources` 테이블 | 사용자가 직접 입력한 1건의 텍스트 |
| Mentality Evidence | Gemini로 자동 추출 후 `player_mentality_evidence` 테이블에 저장 | `evidence_extractor.py`로 즉석 추출, 화면 표시만 |
| LLM 연동 | Gemini 기반 리포트 자동 생성 | `gemini_client.py` optional wrapper + rule-based fallback |

이 구조는 이후 실제 데이터 수집/저장이 가능해지면, 동일한 변환 함수
(`build_grid_vector`, `extract_mentality_evidence` 등)를 그대로 재사용해
Supabase 테이블에 적재하는 방식으로 확장할 수 있도록 설계되었습니다.
        """
    )


def render_experimental_data_lab_view():
    st.title("Experimental Data Lab")
    st.markdown(
        '<div class="section-note">'
        "이 화면은 원래 기획했던 데이터 엔지니어링 확장 기능(10x10 Grid Vector, 기사 기반 "
        "Mentality Evidence, Gemini API 연동)을 샘플 데이터/사용자 입력 기반으로 체험해보는 "
        "실험 공간입니다. 실제 서비스 데이터와는 분리되어 있습니다."
        "</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    _render_grid_vector_section()
    st.divider()
    _render_evidence_section()
    st.divider()
    _render_gemini_status_section()
    st.divider()
    _render_pipeline_overview_section()
