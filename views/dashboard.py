import altair as alt
import pandas as pd
import streamlit as st

from analysis_helpers import (
    ATTRIBUTE_GROUPS,
    MENTALITY_KEYS,
    attr_bar_chart,
    attributes_long_df,
    group_analysis,
    parse_json_field,
    render_metric_cards,
    score_text,
    strength_sentence,
    summary_scores,
    top_attributes,
    weakness_sentence,
)
from explanation_engine import build_growth_explanation
from growth_model import FEATURE_LABELS, build_growth_insight
from services.db import get_appearances, get_valuations
from ui_components import render_page_actions, render_player_profile_panel


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


def render_dashboard_view(player, profile, ctx, entity_type):
    """Dashboard 화면 본문. app.py의 render_dashboard()가 선택 선수/프로필/
    선택 컨텍스트(resolve_selected_player_context/selected_entity_type/
    selected_player/selected_profile)를 조회한 뒤 이 함수에 전달한다
    (선택 로직은 app.py에 그대로 유지)."""
    st.title("유망주 통합 분석 대시보드")

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

    valuations = None
    appearances = None
    if has_player_id:
        valuations = get_valuations(player["player_id"])
        appearances = get_appearances(player["player_id"], limit=20)

    if entity_type in ("matched", "transfermarkt_only") and has_player_id:
        st.subheader("시장가치 변화와 최근 출전 기록")
        c1, c2 = st.columns([1.1, 1])
        with c1:
            if valuations.empty:
                st.info("시장가치 데이터가 없습니다.")
            else:
                valuations_chart = valuations.copy()
                valuations_chart["date"] = pd.to_datetime(valuations_chart["date"])
                valuations_chart["market_value_in_eur"] = pd.to_numeric(valuations_chart["market_value_in_eur"], errors="coerce")
                clean = valuations_chart.dropna(subset=["market_value_in_eur"])
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
            if appearances.empty:
                st.info("최근 출전 기록이 없습니다.")
            else:
                st.caption("최근 10경기 기준 출전 기록입니다.")
                st.dataframe(korean_appearances(appearances.head(10)), use_container_width=True, hide_index=True)
    else:
        st.info("Transfermarkt 데이터와 매칭되지 않아 시장가치 변화와 최근 출전 기록 영역은 표시할 수 없습니다.")

    if entity_type != "manual_note":
        st.subheader("Growth Insight (실제 DB 기반 성장 분석)")
        st.caption(
            "players / appearances / player_valuations / player_profiles 데이터를 바탕으로 계산한 "
            "Growth Score(0~100)와 그 근거를 보여줍니다. 데이터가 부족한 항목은 제외하고 남은 항목의 "
            "비중을 재정규화해 계산합니다."
        )

        growth_insight = build_growth_insight(player, profile, appearances=appearances, valuations=valuations, entity_type=entity_type)
        growth_explanation = build_growth_explanation(
            growth_insight,
            player_context={"name": player.get("name") if player else None, "position": growth_insight.get("position_used")},
        )
        st.session_state["growth_insight"] = growth_insight
        st.session_state["growth_explanation"] = growth_explanation

        growth_score = growth_insight["growth_score"]
        if growth_score is None:
            st.warning("현재 데이터로는 Growth Score를 계산할 수 없습니다.")
        else:
            st.metric("Growth Score", f"{growth_score:.1f} / 100")
            st.progress(int(round(growth_score)))

        feature_cols = st.columns(3)
        for index, (feature_name, feature_result) in enumerate(growth_insight["features"].items()):
            col = feature_cols[index % 3]
            label = FEATURE_LABELS.get(feature_name, feature_name)
            with col:
                if feature_result["status"] == "ok":
                    st.metric(label, f"{feature_result['score'] * 100:.0f}점")
                    st.progress(int(feature_result["score"] * 100))
                else:
                    st.markdown(f"<div class='muted'><b>{label}</b><br>데이터 부족 (unavailable)</div>", unsafe_allow_html=True)

        if growth_insight["risk_penalty"]["penalty"] > 0:
            st.warning(f"리스크 패널티: -{growth_insight['risk_penalty']['penalty']:.0f}점 · " + " ".join(growth_insight["risk_penalty"]["notes"]))

        st.markdown(f"<div class='scout-panel'><b>왜 이 점수가 나왔나요?</b><br>{growth_explanation['score_reason']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='section-note'>{growth_explanation['summary']}</div>", unsafe_allow_html=True)

        gcols = st.columns(2)
        with gcols[0]:
            st.markdown("<div class='scout-panel'><b>강점</b><br>" + "<br>".join(f"• {item}" for item in growth_explanation["strengths"]) + "</div>", unsafe_allow_html=True)
            st.markdown("<div class='scout-panel'><b>추천 성장 방향</b><br>" + "<br>".join(f"• {item}" for item in growth_explanation["recommendations"]) + "</div>", unsafe_allow_html=True)
        with gcols[1]:
            st.markdown("<div class='scout-panel'><b>리스크</b><br>" + "<br>".join(f"• {item}" for item in growth_explanation["risks"]) + "</div>", unsafe_allow_html=True)
            st.markdown("<div class='scout-panel'><b>데이터 부족 안내</b><br>" + "<br>".join(f"• {item}" for item in growth_explanation["data_limitations"]) + "</div>", unsafe_allow_html=True)

        with st.expander("개발자용 Growth Insight 원본 데이터 보기"):
            st.json({"growth_insight": growth_insight, "growth_explanation": growth_explanation})

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
