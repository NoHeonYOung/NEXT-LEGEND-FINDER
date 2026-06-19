import altair as alt
import pandas as pd
import streamlit as st

from analysis_helpers import (
    ATTRIBUTE_GROUPS,
    MENTALITY_KEYS,
    attr_bar_chart,
    attributes_long_df,
    average_attrs,
    group_analysis,
    parse_json_field,
    render_metric_cards,
    score_text,
    strength_sentence,
    summary_scores,
    top_attributes,
    weakness_sentence,
)
from components.attribute_panels import render_attribute_snapshot
from components.badges import source_badge_html
from components.layout import render_game_page_title
from explanation_engine import build_growth_explanation, build_risks_with_meta, build_strengths_with_meta, explain_feature_score
from growth_model import FEATURE_LABELS, build_growth_insight, build_manual_growth_insight
from manual_prospect_helpers import manual_player_profile_panel_inputs
from player_coverage import build_data_coverage
from services.db import get_appearances, get_player, get_profile_by_player_id, get_valuations
from ui_components import render_data_coverage_panel, render_page_actions, render_player_profile_panel


# FEATURE_LABELS의 "FM 능력치"를 사용자 친화 표현으로 덮어씁니다.
_FEATURE_LABEL_FRIENDLY = {**FEATURE_LABELS, "attribute_strength": "능력치 점수"}

# 직접 입력 유망주 구성요소 표시 정보
_MANUAL_COMP_INFO = [
    ("age_potential",       "나이 잠재력",  None),
    ("playing_opportunity", "출전 기회",    "playing_opportunity"),
    ("training_intensity",  "훈련 강도",    "training_intensity"),
    ("league_level",        "리그 수준",    "league_level"),
    ("self_attribute",      "능력치 점수",  None),
]

_PROVENANCE_TEXT = (
    "현재 분석은 DB에 저장된 선수 기본 정보, 시장가치/출전 기록, 능력치 프로필, "
    "Growth/Ceiling 규칙 모델을 바탕으로 생성됩니다. 멘탈/성향 판단은 저장된 능력치 프로필의 "
    "멘탈 항목을 참고하며, 사용자가 입력한 정성 메모는 보조 근거로만 표시됩니다."
)

_PROVENANCE_TABLE = """| 항목 | 출처 |
|---|---|
| 선수 기본 정보 | DB |
| 시장가치/출전 기록 | DB |
| 능력치/멘탈 성향 | 능력치 프로필 |
| 성장 점수 | rule-based Growth/Ceiling Model |
| 정성 텍스트 근거 | 사용자 직접 입력 |
| Gemini 역할 | 정성 텍스트 보조 해석 |
"""


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


def _render_valuations_appearances_panel(valuations, appearances):
    st.subheader("시장가치 변화와 최근 출전 기록")
    c1, c2 = st.columns([1.1, 1])
    with c1:
        if valuations is None or valuations.empty:
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
                    .mark_line(point=alt.OverlayMarkDef(color="#6ee7a8"), color="#39d5bd", strokeWidth=3)
                    .encode(
                        x=alt.X("date:T", title="날짜"),
                        y=alt.Y("market_value_in_eur:Q", title="시장가치(EUR)"),
                        tooltip=["date:T", "market_value_in_eur:Q", "current_club_name:N"],
                    )
                    .properties(height=260, background="transparent")
                    .configure_view(fill="transparent", stroke="transparent")
                )
                st.altair_chart(chart, use_container_width=True)
    with c2:
        if appearances is None or appearances.empty:
            st.info("최근 출전 기록이 없습니다.")
        else:
            recent = appearances.head(10)
            total_goals = int(recent["goals"].fillna(0).sum()) if "goals" in recent.columns else 0
            total_assists = int(recent["assists"].fillna(0).sum()) if "assists" in recent.columns else 0
            total_mins = int(recent["minutes_played"].fillna(0).sum()) if "minutes_played" in recent.columns else 0
            st.markdown(
                f'<div class="game-panel"><div class="kicker">최근 출전 요약</div>'
                f'<div class="game-stat-grid">'
                f'<div class="game-stat"><div class="label">경기</div><div class="value">{len(recent)}</div></div>'
                f'<div class="game-stat"><div class="label">득점</div><div class="value">{total_goals}</div></div>'
                f'<div class="game-stat"><div class="label">도움</div><div class="value">{total_assists}</div></div>'
                f'<div class="game-stat"><div class="label">출전시간</div><div class="value">{total_mins}분</div></div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            with st.expander("최근 출전 기록 상세 보기"):
                st.dataframe(korean_appearances(recent), width="stretch", hide_index=True)


def _render_strength_risk_panels(growth_insight, growth_explanation):
    features = growth_insight.get("features") or {}
    risk_penalty = growth_insight.get("risk_penalty")

    if features:
        # DB 선수: feature 점수에서 직접 강점/리스크 도출
        strengths_meta = build_strengths_with_meta(features)
        risks_meta = build_risks_with_meta(features, risk_penalty)
    else:
        # 직접 입력 유망주: explanation에 미리 구성된 강점/리스크 사용
        strengths_meta = [
            (s, ["직접 입력 분석"])
            for s in (growth_explanation.get("strengths") or [])
        ]
        if not strengths_meta:
            strengths_meta = [("현재 입력 조건에서는 뚜렷한 강점 요인이 확인되지 않았습니다.", ["직접 입력 분석"])]
        risks_meta = [
            (r, ["직접 입력 분석"])
            for r in (growth_explanation.get("risks") or [])
        ]
        if risk_penalty:
            for note in risk_penalty.get("notes", []):
                if note not in [r for r, _ in risks_meta]:
                    risks_meta.append((note, ["성장 가능성 모델"]))
        if not risks_meta:
            risks_meta = [("현재 입력 조건에서는 특별한 리스크 요인이 확인되지 않았습니다.", ["직접 입력 분석"])]

    def _badge_row(badges):
        return "".join(source_badge_html(b, "ok" if b in ("Transfermarkt", "능력치 기반", "Growth Model") else "neutral") for b in badges)

    def _items_html(items_with_meta):
        parts = []
        for text, badges in items_with_meta:
            parts.append(
                f'<div style="margin-bottom:10px;">'
                f'<div class="game-card-row" style="margin-bottom:4px;">{_badge_row(badges)}</div>'
                f'<div>- {text}</div>'
                f'</div>'
            )
        return "".join(parts)

    gcols = st.columns(2)
    with gcols[0]:
        st.markdown('<div class="scout-panel"><b>강점</b><br>' + _items_html(strengths_meta) + '</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="scout-panel"><b>추천 성장 방향</b><br>'
            + "<br>".join(f"<div style='margin-bottom:8px;'>- {item}</div>" for item in growth_explanation.get("recommendations", []))
            + source_badge_html("데이터 기반 분석", "neutral")
            + source_badge_html("Growth Model", "ok")
            + "</div>",
            unsafe_allow_html=True,
        )
    with gcols[1]:
        st.markdown('<div class="scout-panel"><b>리스크 / 보완점</b><br>' + _items_html(risks_meta) + '</div>', unsafe_allow_html=True)


def _render_mentality_evidence_panel(profile, mentality, growth_insight=None):
    basis = mentality.get("basis", {}) if isinstance(mentality, dict) else {}
    mental_score = mentality.get("mentality_score") if isinstance(mentality, dict) else None
    if mental_score is None and isinstance(mentality, dict):
        mental_score = summary_scores({}, mentality).get("멘탈 종합")

    feature = {}
    if isinstance(growth_insight, dict):
        feature = (growth_insight.get("features") or {}).get("mentality_strength") or {}

    if feature.get("status") == "ok":
        feature_text = f"Growth Model에는 멘탈/성향 항목이 보조 요소로 반영되었습니다. 항목 점수: {feature.get('score', 0) * 100:.0f}점"
    elif feature.get("status") == "unavailable":
        feature_text = "Growth Model에서는 멘탈/성향 데이터가 부족해 해당 항목을 제외했습니다."
    else:
        feature_text = "Growth Model 반영 여부는 성장 점수 계산 후 확인할 수 있습니다."

    memo = st.text_area(
        "정성 메모 입력",
        value=st.session_state.get("qualitative_text_input", ""),
        height=132,
        placeholder="예: 팀 충성도가 높고 패스 선택이 좋다. 다만 압박을 받으면 긴장하는 장면이 있다.",
        key="dossier_qualitative_text_input",
        help="이 메모는 점수를 바꾸지 않고 멘탈/태도/리스크 보조 해석과 Report의 Gemini 입력으로 사용됩니다.",
    )
    apply_memo = st.button("정성 메모 반영", key="apply_dossier_qualitative_text")
    if apply_memo:
        st.session_state["qualitative_text_input"] = memo
        st.session_state.pop("qualitative_signals", None)
        st.session_state.pop("gemini_advisory", None)
        st.success("정성 메모를 반영했습니다. Growth/Ceiling 점수는 유지되고, 보조 해석과 Report 입력에 연결됩니다.")
    elif memo != st.session_state.get("qualitative_text_input", ""):
        st.caption("입력한 메모를 분석 흐름에 반영하려면 '정성 메모 반영' 버튼을 눌러주세요.")

    signals = st.session_state.get("qualitative_signals") or {}
    fallback_reason = signals.get("_fallback_reason") if isinstance(signals, dict) else None
    has_signals = isinstance(signals, dict) and fallback_reason not in ("no_text_input", "no_api_key", "api_error", "parse_failed")
    if has_signals:
        positive = []
        caution = []
        for key, label in (
            ("mentality_signal", "멘탈/태도"),
            ("coach_trust_signal", "코치 신뢰"),
            ("development_signal", "성장 의지"),
            ("playing_time_signal", "출전 흐름"),
            ("injury_risk_signal", "체력/부상"),
        ):
            value = signals.get(key, "unknown")
            if value == "positive":
                positive.append(label)
            elif value == "negative":
                caution.append(label)
        qualitative_text = (
            "정성 메모는 Growth Score를 직접 변경하지 않습니다. "
            "대신 멘탈리티 해석, 리스크 관리, 추천 훈련 방향, Career Simulation 해석, 리포트 최종 코멘트의 보조 근거로 반영됩니다. "
            f"요약: {signals.get('qualitative_summary', '') or '요약 없음'} "
            f"긍정 신호: {', '.join(positive) if positive else '명확한 긍정 신호 없음'}. "
            f"주의 신호: {', '.join(caution) if caution else '명확한 주의 신호 없음'}."
        )
        risks = signals.get("risk_mentions") or []
        focus = signals.get("recommended_focus") or []
        if risks:
            qualitative_text += " 리스크 언급: " + ", ".join(str(item) for item in risks[:3])
        if focus:
            qualitative_text += " 확인 포인트: " + ", ".join(str(item) for item in focus[:3])
    elif fallback_reason in ("api_error", "no_api_key"):
        qualitative_text = "정성 텍스트 보조 분석을 실행하지 못했지만 기본 분석은 정상 사용 가능합니다. 현재 점수와 멘탈/성향 지표는 저장된 선수 데이터 기반으로 표시됩니다."
    elif memo:
        qualitative_text = (
            "정성 메모가 입력되어 있습니다. Growth Score를 직접 바꾸지는 않으며, Evidence & Advisory Report에서 정성 신호 추출을 실행하면 "
            "멘탈리티 해석, 리스크 관리, 추천 훈련 방향, 최종 스카우팅 코멘트의 보조 근거로 정리됩니다."
        )
    else:
        qualitative_text = "정성 메모 없음 — 현재는 저장된 선수 데이터 기반 분석만 사용 중입니다."

    mental_label = "-" if mental_score is None else mental_score
    basis_count = len(basis) if isinstance(basis, dict) else 0
    st.markdown(
        f"""
        <div class="game-panel game-report-section">
            <div class="kicker">Mentality Evidence</div>
            <h3>멘탈/성향 분석 근거</h3>
            <div class="game-note-section">
                <div class="game-card-row">{source_badge_html("능력치 기반", "warning")}</div>
                <b>1. 능력치 기반 평가</b><br>
                저장된 멘탈/성향 능력치 {basis_count}개 항목을 참고합니다. 현재 종합값: {mental_label}
            </div>
            <div class="game-note-section">
                <div class="game-card-row">{source_badge_html("Growth Model", "ok")}</div>
                <b>2. 성장 모델 관련</b><br>
                {feature_text}
            </div>
            <div class="game-note-section">
                <div class="game-card-row">{source_badge_html("정성 메모", "manual")}</div>
                <b>3. 정성 메모 보조 분석</b><br>
                {qualitative_text}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_player_identity(player, profile, growth_insight=None):
    attributes = parse_json_field(profile.get("attributes_jsonb"))
    mentality = parse_json_field(profile.get("mentality_jsonb"))
    key_attribute_rows = []
    if isinstance(attributes, dict):
        for group_keys in ATTRIBUTE_GROUPS.values():
            for key in group_keys:
                if key in attributes:
                    key_attribute_rows.append((key, attributes.get(key)))
                if len(key_attribute_rows) >= 6:
                    break
            if len(key_attribute_rows) >= 6:
                break

    render_attribute_snapshot("핵심 능력치 분포", key_attribute_rows)
    st.subheader("선수 유형 요약")
    st.caption("저장된 능력치 프로필을 활용해 포지션 역할, 능력치 강점, 멘탈/성향 지표를 요약합니다.")
    style_status = "플레이스타일 비교 가능" if profile.get("style_vector") else "플레이스타일 비교 데이터 준비 전"
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
    render_metric_cards(summary_scores(attributes, mentality))

    st.subheader("능력치 기반 스타일 요약")
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

    st.subheader("멘탈/성향 지표")
    with st.expander("멘탈/성향 지표 안내"):
        st.caption(
            "이 값은 저장된 능력치 프로필의 멘탈 관련 항목에서 계산한 참고 지표입니다. "
            "실제 태도나 성격을 단정하지 않으며, 스카우팅 관찰 기록과 함께 판단해야 합니다."
        )

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
    _render_mentality_evidence_panel(profile, mentality, growth_insight)


def render_dashboard_view(player, profile, ctx, entity_type):
    render_game_page_title(
        "Player Dossier",
        "선택 선수의 데이터 준비도, 성장 전망, 플레이어 정체성을 스카우팅 리포트형 화면에서 확인합니다.",
        kicker="Player Analysis Hub",
    )
    with st.expander("분석 근거 안내"):
        st.caption(_PROVENANCE_TEXT)
        st.markdown(_PROVENANCE_TABLE)

    if st.button("Scouting Board로 돌아가기", key="dossier_back_to_scouting_board"):
        st.session_state["nav_page_request"] = "유망주 검색"
        st.rerun()

    if player is None and profile is None:
        st.warning("먼저 Prospect Search에서 선수를 선택해 주세요.")
        return

    if entity_type == "manual_prospect":
        manual_player = st.session_state.get("manual_player") or {}

        # Guard: stale session state — manual_player must actually exist
        if not manual_player:
            st.warning("직접 입력 유망주 데이터가 없습니다. 유망주 검색에서 선수를 선택해 주세요.")
            return

        manual_attributes = st.session_state.get("manual_attributes") or {}
        manual_career_settings = st.session_state.get("manual_career_settings") or {}

        # Scouting Board에서 선택한 full_data 후보: 실제 DB 데이터로 Growth Score 계산
        estimated_player_id = manual_player.get("estimated_from_player_id")
        is_full_data_with_ref = bool(estimated_player_id) and manual_player.get("data_mode") == "full_data"

        panel_player, panel_profile = manual_player_profile_panel_inputs(manual_player)
        _header_entity = "scouting_board_pick" if is_full_data_with_ref else "manual_prospect"
        render_player_profile_panel(panel_player, panel_profile, entity_type=_header_entity)
        render_data_coverage_panel(panel_player, panel_profile, entity_type="manual_prospect", title="분석 데이터 준비도")

        if is_full_data_with_ref:
            _real_player = get_player(estimated_player_id) or {}
            _real_profile = get_profile_by_player_id(estimated_player_id) or {}
            valuations = get_valuations(estimated_player_id)
            appearances = get_appearances(estimated_player_id, limit=20)

            # FM 능력치 프로필이 없으면 Scouting Board 추정 능력치를 fallback으로 주입
            _profile_for_insight = dict(_real_profile)
            _used_manual_attr_fallback = False
            if manual_attributes and not _profile_for_insight.get("attributes_jsonb"):
                _profile_for_insight["attributes_jsonb"] = manual_attributes
                _used_manual_attr_fallback = True
            if manual_attributes and not _profile_for_insight.get("mentality_jsonb"):
                _mental_keys = ["determination", "teamwork", "work_rate", "pressing"]
                _mental_vals = [manual_attributes[k] for k in _mental_keys if k in manual_attributes]
                if _mental_vals:
                    _mentality_score = sum(_mental_vals) / len(_mental_vals) * 10
                    _profile_for_insight["mentality_jsonb"] = {"mentality_score": _mentality_score}

            if _real_player and _real_profile:
                _ref_entity_type = "matched"
            elif _real_player:
                _ref_entity_type = "transfermarkt_only"
            elif _real_profile:
                _ref_entity_type = "fm_profile_only"
            else:
                _ref_entity_type = "transfermarkt_only"

            growth_insight = build_growth_insight(
                _real_player, _profile_for_insight,
                appearances=appearances,
                valuations=valuations,
                entity_type=_ref_entity_type,
            )
            growth_explanation = build_growth_explanation(
                growth_insight,
                player_context={"name": manual_player.get("name"), "position": growth_insight.get("position_used")},
            )
            if _used_manual_attr_fallback:
                st.session_state["_scouting_attr_fallback"] = True
            else:
                st.session_state.pop("_scouting_attr_fallback", None)
        else:
            valuations = None
            appearances = None
            growth_insight = build_manual_growth_insight(manual_player, manual_attributes, manual_career_settings)
            growth_explanation = build_growth_explanation(
                growth_insight,
                player_context={"name": manual_player.get("name"), "position": manual_player.get("position")},
            )

        st.session_state["growth_insight"] = growth_insight
        st.session_state["growth_explanation"] = growth_explanation

        growth_score = growth_insight["growth_score"]

        # ── Growth Score Summary ───────────────────────────────────────────
        st.subheader("성장 가능성 분석")
        if is_full_data_with_ref:
            st.caption(
                "저장된 선수 데이터와 출전 기록, 시장가치 흐름을 기준으로 Growth Score가 계산되었습니다. "
                "시장가치, 출전 기록, 능력치, 멘탈리티 데이터를 종합해 성장 가능성을 평가했습니다."
            )
        else:
            st.caption(
                "직접 입력한 능력치와 환경 설정을 기준으로 Growth Score가 계산되었습니다. "
                "시장가치와 실제 출전 기록이 없으므로 해당 항목은 제한적으로 반영됩니다."
            )

        if growth_score is None:
            st.warning("현재 데이터로는 Growth Score를 계산할 수 없습니다.")
        else:
            st.metric("Growth Score", f"{growth_score:.1f} / 100")
            st.progress(int(round(growth_score)))

        # ── Growth Score 구성요소 ─────────────────────────────────────────
        st.subheader("Growth Score 구성요소")
        if is_full_data_with_ref:
            # 6개 DB feature 카드
            feature_cols = st.columns(3)
            for index, (feature_name, feature_result) in enumerate(growth_insight.get("features", {}).items()):
                label = _FEATURE_LABEL_FRIENDLY.get(feature_name, feature_name)
                with feature_cols[index % 3]:
                    if feature_result.get("status") == "ok":
                        score_label = f"{feature_result['score'] * 100:.0f}점"
                        st.metric(label, score_label)
                        st.progress(int(feature_result["score"] * 100))
                    else:
                        st.markdown(f"<div class='muted'><b>{label}</b><br>FM 프로필 미연결</div>", unsafe_allow_html=True)

            _rp = growth_insight.get("risk_penalty", {})
            if _rp.get("penalty", 0) > 0:
                st.warning(f"리스크 패널티: -{_rp['penalty']:.0f}점 · " + " ".join(_rp.get("notes", [])))

            with st.expander("각 구성요소가 점수에 어떻게 기여했는지 보기"):
                for feature_name, feature_result in growth_insight.get("features", {}).items():
                    feat_label = _FEATURE_LABEL_FRIENDLY.get(feature_name, feature_name)
                    st.markdown(f"**{feat_label}**")
                    st.caption(explain_feature_score(feature_name, feature_result))
                    st.divider()
        else:
            # 5개 직접 입력 구성요소 카드
            scores = growth_insight.get("scores", {})
            levels = growth_insight.get("levels", {})
            risk_penalty_info = growth_insight.get("risk_penalty", {})

            comp_cols = st.columns(3)
            for idx, (key, label, level_key) in enumerate(_MANUAL_COMP_INFO):
                score = scores.get(key)
                level_text = levels.get(level_key) if level_key else None
                with comp_cols[idx % 3]:
                    if score is not None:
                        display_label = label + (f" ({level_text})" if level_text else "")
                        st.metric(display_label, f"{int(round(score * 100))}점")
                        st.progress(int(round(score * 100)))
                    else:
                        st.markdown(
                            f"<div class='muted'><b>{label}</b><br>현재 입력되지 않음</div>",
                            unsafe_allow_html=True,
                        )

            risk_tendency_label = levels.get("risk_tendency")
            if risk_tendency_label:
                st.caption(f"리스크 성향: {risk_tendency_label}")

            penalty = risk_penalty_info.get("penalty", 0)
            risk_notes = risk_penalty_info.get("notes", [])
            if penalty and penalty > 0:
                st.warning(f"리스크 패널티: -{penalty:.0f}점 · " + " ".join(risk_notes))

        # ── 왜 이 점수가 나왔나요? ────────────────────────────────────────
        st.markdown(
            f"<div class='scout-panel'><b>왜 이 점수가 나왔나요?</b><br>{growth_explanation['score_reason']}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"<div class='section-note'>{growth_explanation['summary']}</div>", unsafe_allow_html=True)

        # ── 강점 / 리스크 / 추천 방향 ────────────────────────────────────
        _render_strength_risk_panels(growth_insight, growth_explanation)

        if growth_explanation.get("data_limitations"):
            with st.expander("데이터 제한 안내"):
                for item in growth_explanation["data_limitations"]:
                    st.caption(f"- {item}")

        # ── 능력치 그룹 분석 ──────────────────────────────────────────────
        if is_full_data_with_ref:
            # 실제 DB 데이터가 있는 경우: FM 속성 기반 전체 선수 분석 패널
            _render_player_identity(_real_player, _profile_for_insight, growth_insight)
        elif manual_attributes:
            st.subheader("능력치 그룹 분석")
            st.caption("직접 입력한 능력치 기반 공격/패스/피지컬/멘탈/수비 그룹별 분석입니다.")
            for group, keys in ATTRIBUTE_GROUPS.items():
                avg, highs, lows = group_analysis(manual_attributes, group, keys)
                if avg is not None:
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
                        attr_bar_chart(attributes_long_df(manual_attributes, {group: keys}), height=190)

            # ── 멘탈/성향 지표 (직접 입력 능력치 기반) ───────────────────
            if any(k in manual_attributes for k in MENTALITY_KEYS):
                st.subheader("멘탈/성향 지표")
                st.caption("직접 입력한 멘탈 관련 능력치를 바탕으로 한 참고 지표입니다.")
                mental_avg = average_attrs(manual_attributes, MENTALITY_KEYS)
                m1, m2 = st.columns([0.75, 1.45])
                with m1:
                    st.metric("멘탈 종합 점수", score_text(mental_avg))
                    mental_highs = top_attributes(manual_attributes, MENTALITY_KEYS, 3, True)
                    mental_lows = top_attributes(manual_attributes, MENTALITY_KEYS, 2, False)
                    st.markdown(
                        '<div class="scout-panel"><b>멘탈 강점</b><br>' + strength_sentence(mental_highs) + '</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        '<div class="scout-panel"><b>보완이 필요한 부분</b><br>' + weakness_sentence(mental_lows) + '</div>',
                        unsafe_allow_html=True,
                    )
                with m2:
                    attr_bar_chart(attributes_long_df(manual_attributes, {"멘탈리티": MENTALITY_KEYS}), height=320)
        else:
            st.info("직접 입력 유망주: 능력치를 입력하면 공격/패스/피지컬/멘탈/수비 그룹별 분석이 표시됩니다.")

        # ── 시장가치 / 출전 기록 ────────────────────────────────────────
        if is_full_data_with_ref:
            _render_valuations_appearances_panel(valuations, appearances)
        elif estimated_player_id:
            _render_valuations_appearances_panel(get_valuations(estimated_player_id), get_appearances(estimated_player_id, limit=20))
        else:
            st.info("직접 입력 유망주: 참조 선수가 연결되지 않아 시장가치/출전 기록은 표시되지 않습니다.")

        render_page_actions(
            [
                ("멘토 후보에서 멘토 찾기", "유사 선수 후보", "primary"),
                ("커리어 시뮬레이션 시작", "커리어 시뮬레이션"),
                ("Evidence & Advisory Report로 이동", "AI 스카우팅 리포트"),
            ],
            title="다음 단계",
        )
        return

    render_player_profile_panel(player, profile, entity_type=entity_type)
    coverage = render_data_coverage_panel(player, profile, entity_type=entity_type, title="분석 데이터 준비도")

    if ctx["fallback_note"]:
        st.info(ctx["fallback_note"])

    if entity_type == "matched":
        st.info("완전 매칭 모드: 기본 정보, 시장가치/출전 기록, 능력치 분석을 함께 확인할 수 있습니다.")
    elif entity_type == "fm_profile_only":
        st.info("능력치 기반 모드: 능력치 분석은 가능하지만 시장가치/출전 기록은 표시되지 않습니다.")
    else:
        st.warning(
            "이 선수는 기본 선수 정보만 연결되어 있어 능력치, 멘탈/성향, 멘토 비교 분석은 제한됩니다. "
            "정밀 분석을 위해서는 직접 입력 유망주 기능을 사용하세요."
        )
        resolved_age = coverage["resolved_age"]
        if resolved_age is not None and resolved_age != (profile.get("age") if isinstance(profile, dict) else None):
            st.caption(f"나이는 생년월일 기반으로 계산된 값입니다 ({resolved_age:.1f}세).")
        render_page_actions(
            [
                ("분석 가능한 선수 다시 검색", "유망주 검색", "primary"),
                ("직접 입력 유망주로 보완", "직접 입력 유망주"),
            ],
            title="제한 분석 선수 · 추가 분석 방법",
        )

    has_profile = isinstance(profile, dict) and profile.get("profile_id") is not None
    has_player_id = isinstance(player, dict) and player.get("player_id") is not None

    valuations = None
    appearances = None
    if has_player_id:
        valuations = get_valuations(player["player_id"])
        appearances = get_appearances(player["player_id"], limit=20)

    growth_insight = None
    growth_explanation = None
    if entity_type != "manual_note":
        st.subheader("성장 가능성 분석")
        st.caption(
            "선수 기본 정보, 출전 기록, 시장가치 흐름, 능력치 프로필을 바탕으로 Growth Score와 그 근거를 보여줍니다. "
            "데이터가 부족한 항목은 제외하고 남은 항목의 비중을 재정규화해 계산합니다."
        )
        if entity_type == "transfermarkt_only":
            st.info("이 분석은 기본 선수 정보 기반 제한 분석입니다. 능력치/멘탈 성향 기반 판단은 제외되었습니다.")
            with st.expander("제외된 항목 상세"):
                st.caption("제외된 항목: " + ", ".join(coverage.get("missing_reasons") or ["추가 부족 항목 없음"]))

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

        st.subheader("Growth Score 구성요소")
        feature_cols = st.columns(3)
        for index, (feature_name, feature_result) in enumerate(growth_insight["features"].items()):
            label = _FEATURE_LABEL_FRIENDLY.get(feature_name, feature_name)
            with feature_cols[index % 3]:
                if feature_result["status"] == "ok":
                    st.metric(label, f"{feature_result['score'] * 100:.0f}점")
                    st.progress(int(feature_result["score"] * 100))
                else:
                    st.markdown(f"<div class='muted'><b>{label}</b><br>현재 입력되지 않음</div>", unsafe_allow_html=True)

        if growth_insight["risk_penalty"]["penalty"] > 0:
            st.warning(f"리스크 패널티: -{growth_insight['risk_penalty']['penalty']:.0f}점 · " + " ".join(growth_insight["risk_penalty"]["notes"]))

        with st.expander("각 구성요소가 점수에 어떻게 기여했는지 보기"):
            for feature_name, feature_result in growth_insight["features"].items():
                feat_label = _FEATURE_LABEL_FRIENDLY.get(feature_name, feature_name)
                st.markdown(f"**{feat_label}**")
                st.caption(explain_feature_score(feature_name, feature_result))
                st.divider()

        st.markdown(f"<div class='scout-panel'><b>왜 이 점수가 나왔나요?</b><br>{growth_explanation['score_reason']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='section-note'>{growth_explanation['summary']}</div>", unsafe_allow_html=True)
        _render_strength_risk_panels(growth_insight, growth_explanation)

        if growth_explanation.get("data_limitations"):
            with st.expander("데이터 부족 안내"):
                for item in growth_explanation["data_limitations"]:
                    st.caption(f"- {item}")


    if has_profile:
        _render_player_identity(player, profile, growth_insight)
        with st.expander("개발자용 원본 데이터 보기"):
            st.json({"attributes_jsonb": parse_json_field(profile.get("attributes_jsonb")), "mentality_jsonb": parse_json_field(profile.get("mentality_jsonb"))})
    else:
        st.subheader("선수 유형 요약")
        st.warning("능력치 프로필이 없어 스타일/멘탈 분석은 표시할 수 없습니다.")

    if entity_type in ("matched", "transfermarkt_only") and has_player_id:
        _render_valuations_appearances_panel(valuations, appearances)
    else:
        st.info("시장가치/출전 기록과 매칭되지 않아 해당 영역은 표시할 수 없습니다.")

    if has_profile:
        render_page_actions(
            [
                ("Style & Mentor Lab으로 이동", "유사 선수 후보", "primary"),
                ("커리어 시뮬레이션 시작", "커리어 시뮬레이션"),
                ("Evidence & Advisory Report로 이동", "AI 스카우팅 리포트"),
                ("Notes로 이동", "내 스카우팅 노트"),
            ]
        )
    else:
        render_page_actions(
            [
                ("직접 입력 유망주로 보완하기", "직접 입력 유망주", "primary"),
                ("분석 가능한 선수 다시 검색하기", "유망주 검색"),
                ("커리어 시뮬레이션 시작", "커리어 시뮬레이션"),
            ],
            title="제한 분석 선수 · 다음 단계",
        )
