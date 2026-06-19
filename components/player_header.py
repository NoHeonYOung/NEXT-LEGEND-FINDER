from html import escape

import streamlit as st

from components.badges import coverage_badge_html
from player_coverage import build_data_coverage, resolve_player_age
from services.db import money


def _initials(name):
    parts = [part for part in str(name or "-").replace("-", " ").split() if part]
    if not parts:
        return "-"
    return "".join(part[0].upper() for part in parts[:2])


def _age_text(player, profile):
    age = resolve_player_age(player or {}, profile)
    if age is None:
        return "No age data"
    return str(int(age)) if age == int(age) else f"{age:.1f}"


def _avatar_html(player):
    image_url = str(player.get("image_url") or "").strip()
    initials = escape(_initials(player.get("name")))
    if image_url:
        return (
            f'<img class="game-avatar-img" src="{escape(image_url)}" alt="{initials}" loading="lazy" '
            f'onerror="this.style.display=\'none\';document.getElementById(\'avatar-fallback-{initials}\').style.display=\'flex\';" />'
            f'<div class="game-avatar" id="avatar-fallback-{initials}" style="display:none">{initials}</div>'
        )
    return f'<div class="game-avatar">{initials}</div>'


def render_player_header(player, profile=None, entity_type=None):
    player = player or {}
    if entity_type == "scouting_board_pick":
        level = "full"
        data_mode = "DB 연동 분석"
        main_badge = '<span class="game-badge badge-full">선발 선수</span>'
    elif entity_type == "manual_prospect":
        level = "full"
        data_mode = "직접 입력 기반 분석"
        main_badge = '<span class="game-badge badge-full">직접 입력 선수</span>'
    else:
        level = build_data_coverage(player, profile).get("analysis_level")
        data_mode = "종합 분석" if level == "full" else str(entity_type or "-")
        main_badge = coverage_badge_html(level)
    badges = [
        main_badge,
        f'<span class="game-badge badge-neutral">{escape(str(player.get("position") or "-"))}</span>',
        f'<span class="game-badge badge-neutral">{escape(str(player.get("country_of_citizenship") or "-"))}</span>',
    ]
    st.markdown(
        f"""
        <div class="game-player-header">
            {_avatar_html(player)}
            <div>
                <div class="game-muted">선택된 유망주</div>
                <h2>{escape(str(player.get("name") or "-"))}</h2>
                <div class="game-player-meta">
                    {escape(str(player.get("current_club_name") or "-"))} | {escape(str(player.get("sub_position") or player.get("position") or "-"))}
                </div>
                <div class="game-card-row">{''.join(badges)}</div>
            </div>
            <div class="game-player-facts">
                <div class="game-fact"><div class="label">나이</div><div class="value">{escape(_age_text(player, profile))}</div></div>
                <div class="game-fact"><div class="label">시장가치</div><div class="value">{escape(money(player.get("market_value_in_eur")))}</div></div>
                <div class="game-fact"><div class="label">최고가치</div><div class="value">{escape(money(player.get("highest_market_value_in_eur")))}</div></div>
                <div class="game-fact"><div class="label">분석 유형</div><div class="value">{escape(data_mode)}</div></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
