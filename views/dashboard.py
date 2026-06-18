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
from growth_model import FEATURE_LABELS, build_growth_insight, build_manual_growth_insight
from manual_prospect_helpers import manual_player_profile_panel_inputs
from player_coverage import build_data_coverage, resolve_player_age
from services.db import get_appearances, get_valuations
from ui_components import render_data_coverage_panel, render_page_actions, render_player_profile_panel


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


_PROVENANCE_TEXT = (
    "현재 분석은 DB에 저장된 선수 기본 정보, 시장가치/출전 기록, "
    "FM 기반 능력치 및 멘탈 속성 proxy, Growth/Ceiling 규칙 모델을 바탕으로 생성되었습니다. "
    "뉴스 기사, 감독 인터뷰, 스카우팅 텍스트 기반 정성 분석은 아직 입력되지 않았습니다."
)

_PROVENANCE_TABLE = """| 항목 | 출처 |
|---|---|
| 선수 기본 정보 | DB |
| 시장가치/출전 기록 | DB |
| 능력치/멘탈 속성 | FM proxy profile |
| 성장 점수 | rule-based Growth/Ceiling Model |
| 정성 텍스트 근거 | 입력 없음 |
| Gemini 분석 | 미사용 |
"""


def render_dashboard_view(player, profile, ctx, entity_type):
    """Dashboard 화면 본문. app.py의 render_dashboard()가 선택 선수/프로필/
    선택 컨텍스트(resolve_selected_player_context/selected_entity_type/
    selected_player/selected_profile)를 조회한 뒤 이 함수에 전달한다
    (선택 로직은 app.py에 그대로 유지)."""
    st.title("Player Dossier")
    st.caption("선택 선수의 데이터 준비도, Growth Insight, Player Identity를 한 화면에서 확인하는 분석 허브입니다.")
    with st.expander("분석 근거 안내"):
        st.caption(_PROVENANCE_TEXT)
        st.markdown(_PROVENANCE_TABLE)

    if player is None and profile is None:
        st.warning("먼저 Prospect Search에서 선수를 선택해 주세요.")
        return

    if entity_type == "manual_prospect":
        manual_player = st.session_state.get("manual_player") or {}
        manual_attributes = st.session_state.get("manual_attributes") or {}
        manual_career_settings = st.session_state.get("manual_career_settings") or {}

        panel_player, panel_profile = manual_player_profile_panel_inputs(manual_player)
        render_player_profile_panel(panel_player, panel_profile)
        render_data_coverage_panel(panel_player, panel_profile, entity_type="manual_prospect", title="Data Coverage Panel")
        st.info(
            "직접 입력 유망주 모드: 입력한 능력치와 환경 설정을 기반으로 한 prototype 분석입니다. "
            "Transfermarkt 시장가치 변화나 실제 출전 기록은 매칭되지 않아 표시할 수 없습니다."
        )

        st.subheader("Growth Insight (직접 입력 데이터 기반)")
        st.caption("직접 입력한 능력치와 환경 설정을 바탕으로 계산한 prototype Growth Score(0~100)입니다.")

        growth_insight = build_manual_growth_insight(manual_player, manual_attributes, manual_career_settings)
        growth_explanation = build_growth_explanation(
            growth_insight,
            player_context={"name": manual_player.get("name"), "position": manual_player.get("position")},
        )
        st.session_state["growth_insight"] = growth_insight
        st.session_state["growth_explanation"] = growth_explanation

        growth_score = growth_insight["growth_score"]
        st.metric("Growth Score", f"{growth_score:.1f} / 100")
        st.progress(int(round(growth_score)))

        st.markdown(f"<div class='scout-panel'><b>왜 이 점수가 나왔나요?</b><br>{growth_explanation['score_reason']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='section-note'>{growth_explanation['summary']}</div>", unsafe_allow_html=True)

        gcols = st.columns(2)
        with gcols[0]:
            st.markdown("<div class='scout-panel'><b>강점</b><br>" + "<br>".join(f"• {item}" for item in growth_explanation["strengths"]) + "</div>", unsafe_allow_html=True)
            st.markdown("<div class='scout-panel'><b>추천 성장 방향</b><br>" + "<br>".join(f"• {item}" for item in growth_explanation["recommendations"]) + "</div>", unsafe_allow_html=True)
        with gcols[1]:
            st.markdown("<div class='scout-panel'><b>리스크</b><br>" + "<br>".join(f"• {item}" for item in growth_explanation["risks"]) + "</div>", unsafe_allow_html=True)

        with st.expander("개발자용 Growth Insight 원본 데이터 보기"):
            st.json({"growth_insight": growth_insight, "growth_explanation": growth_explanation})

        render_page_actions([
            ("🤝 유사 선수 후보에서 멘토 찾기", "유사 선수 후보", "primary"),
            ("📈 커리어 시뮬레이션 시작", "커리어 시뮬레이션"),
        ], title="직접 입력 유망주 · 다음 단계")
        return

    render_player_profile_panel(player, profile)
    coverage = render_data_coverage_panel(player, profile, entity_type=entity_type, title="Data Coverage Panel")

    if ctx["fallback_note"]:
        st.info(ctx["fallback_note"])

    if entity_type == "matched":
        st.info("matched 모드: players + player_profiles + player_valuations + appearances를 함께 확인할 수 있습니다.")
    elif entity_type == "fm_profile_only":
        st.info("fm_profile_only 모드: FM 프로필 기반 후보입니다. Transfermarkt 시장가치/출전 기록은 매칭되지 않아 표시할 수 없습니다.")
    else:
        st.warning(
            "⚠ 이 선수는 Transfermarkt 기본 데이터만 연결되어 있어 "
            "FM 능력치, 멘탈 지표, style_vector 기반 유사 선수 분석은 제한됩니다. "
            "정밀 분석을 위해서는 FM profile 매칭 또는 직접 입력 유망주 기능을 사용하세요."
        )
        resolved_age = coverage["resolved_age"]
        if resolved_age is not None and resolved_age != (profile.get("age") if isinstance(profile, dict) else None):
            st.caption(
                f"나이는 생년월일 기반으로 계산된 값입니다 ({resolved_age:.1f}세). "
                "FM 프로필이 없어 정확한 현재 나이와 다를 수 있습니다."
            )
        render_page_actions([
            ("🔍 분석 가능한 선수 다시 검색", "유망주 검색", "primary"),
            ("✏️ 직접 입력 유망주로 보완", "직접 입력 유망주"),
        ], title="Transfermarkt 기반 선수 · 추가 분석 방법")

    has_profile = isinstance(profile, dict) and profile.get("profile_id") is not None
    has_player_id = isinstance(player, dict) and player.get("player_id") is not None

    if entity_type in ("matched", "fm_profile_only") and has_profile:
        attributes = parse_json_field(profile.get("attributes_jsonb"))
        mentality = parse_json_field(profile.get("mentality_jsonb"))

        st.subheader("Player Identity")
        st.caption("FM 기반 proxy 데이터를 활용해 포지션 역할, 능력치 강점, 멘탈 지표를 요약합니다.")
        style_status = "style_vector 연결됨" if profile.get("style_vector") else "style_vector 없음"
        st.markdown(
            f"""
            <div class="scout-panel">
                <b>포지션/역할 요약</b><br>
                {player.get('position') or profile.get('position') or '-'} 역할 후보 · {style_status}
            </div>
            """,
            unsafe_allow_html=True,
        )

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

        st.subheader("FM 기반 멘탈 지표 (proxy)")
        st.info("현재 멘탈리티 수치는 기사/스카우팅 원문 분석이 아닌 FM 멘탈 속성 proxy(FM mental attributes 기반 대체 지표)입니다. 실제 선수 멘탈 특성과 다를 수 있습니다.")

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
        st.subheader("Player Identity")
        st.warning("FM 프로필이 없어 스타일/멘탈 분석은 표시할 수 없습니다.")
        render_page_actions([
            ("✏️ 직접 입력 유망주로 보완", "직접 입력 유망주", "primary"),
            ("🔍 분석 가능한 선수 다시 검색", "유망주 검색"),
        ], title="Player Identity 보완")
    else:
        st.subheader("Player Identity")
        st.warning(
            "FM profile이 없어 능력치, FM 기반 멘탈 지표 proxy, style_vector 기반 플레이스타일 요약을 표시할 수 없습니다."
        )
        render_page_actions([
            ("✏️ 직접 입력 유망주로 보완", "직접 입력 유망주", "primary"),
            ("🔍 분석 가능한 선수 다시 검색", "유망주 검색"),
        ], title="Limited 선수 · Player Identity 보완")

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
        # FM profile 없는 경우 나이 기반 섹션 표현 조정
        coverage = build_data_coverage(player, profile)
        resolved_age = coverage["resolved_age"]
        is_old_player = resolved_age is not None and resolved_age >= 25
        is_tm_only = entity_type == "transfermarkt_only"

        if is_old_player and is_tm_only:
            st.subheader("현재 데이터 기반 성장 분석")
        else:
            st.subheader("Growth Insight (실제 DB 기반 성장 분석)")
        st.caption(
            "players / appearances / player_valuations / player_profiles 데이터를 바탕으로 계산한 "
            "Growth Score(0~100)와 그 근거를 보여줍니다. 데이터가 부족한 항목은 제외하고 남은 항목의 "
            "비중을 재정규화해 계산합니다."
        )
        if is_tm_only:
            st.info(
                "이 분석은 Transfermarkt 기반 제한 분석입니다. "
                "FM profile이 없어 FM 능력치, 멘탈 지표, style_vector 기반 판단은 제외되었습니다."
            )
            st.caption("데이터 한계: " + ", ".join(coverage.get("missing_reasons") or ["추가 부족 항목 없음"]))

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
            ("🤝 Style & Mentor Lab으로 이동", "유사 선수 후보", "primary"),
            ("📈 커리어 시뮬레이션 시작", "커리어 시뮬레이션"),
            ("📄 Evidence & Advisory Report로 이동", "AI 스카우팅 리포트"),
            ("📝 Notes로 이동", "내 스카우팅 노트"),
        ])
    else:
        render_page_actions([
            ("✏️ 직접 입력 유망주로 보완하기", "직접 입력 유망주", "primary"),
            ("🔍 분석 가능한 선수 다시 검색하기", "유망주 검색"),
            ("📈 커리어 시뮬레이션 시작", "커리어 시뮬레이션"),
        ], title="Limited 선수 · 다음 단계")
