import streamlit as st

from services.db import query_one, get_player, get_profile_by_player_id, get_player_profile
from theme import apply_theme
from ui_components import go_to, render_nav_chips
from state import ENTITY_TYPE_LABELS, DATA_MODE_BADGE_CLASS, build_selected_player_status
from views.db_status import render_db_status as render_db_status_view
from views.home import render_home as render_home_view
from views.career_simulation import render_career_simulation_view
from views.ai_report import render_ai_report_view
from views.legend_matching import render_legend_matching_view
from views.dashboard import render_dashboard_view
from views.scouting_notes import render_scouting_notes_view
from views.manual_prospect import render_manual_prospect_view
from views.prospect_search import render_prospect_search_view
from views.experimental_data_lab import render_experimental_data_lab_view


PAGES = [
    "Home / Service Intro",
    "Prospect Search",
    "Integrated Analysis Dashboard",
    "Legend Matching",
    "Career Simulation",
    "AI Scouting Report",
    "My Scouting Notes",
    "Manual Prospect",
    "DB Status",
]


st.set_page_config(page_title="NEXT-LEGEND FINDER", layout="wide")


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


def resolve_selected_player_context():
    """Return the selected player/profile context and keep session_state aligned."""
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

    if st.session_state.get("selected_entity_type") == "manual_prospect":
        manual_player = st.session_state.get("manual_player") or {}
        return {
            "player_id": None,
            "name": manual_player.get("name") or "직접 입력 유망주",
            "current_club_name": manual_player.get("club") or "-",
            "country_of_citizenship": manual_player.get("nationality") or "-",
            "position": manual_player.get("position") or "-",
            "sub_position": manual_player.get("sub_position"),
            "foot": manual_player.get("foot"),
            "height_in_cm": None,
            "market_value_in_eur": manual_player.get("market_value_in_eur"),
            "highest_market_value_in_eur": manual_player.get("highest_market_value_in_eur"),
            "image_url": manual_player.get("image_url"),
        }

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


def get_selected_player_status():
    return build_selected_player_status(selected_player(), selected_entity_type())


def render_app_header(page_label):
    status = get_selected_player_status()
    entity_type = status["entity_type"]
    data_mode_label = ENTITY_TYPE_LABELS.get(entity_type, entity_type or "선택 선수 없음")
    badge_class = DATA_MODE_BADGE_CLASS.get(entity_type, DATA_MODE_BADGE_CLASS[None])

    if status["has_player"]:
        status_text = f"선택 선수: <b>{status['name']}</b> · {status['club']} · {status['position']}"
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
            if st.button("Home", key="header_home_button", use_container_width=True):
                go_to("홈 / 서비스 소개")

    render_nav_chips(page_label)


def render_dashboard():
    # manual_prospect 라우팅은 manual_player 데이터가 실제로 있을 때만 활성화
    if (
        st.session_state.get("selected_entity_type") == "manual_prospect"
        and st.session_state.get("manual_player")
    ):
        return render_dashboard_view(selected_player(), None, {"fallback_note": None}, "manual_prospect")
    ctx = resolve_selected_player_context()
    entity_type = selected_entity_type()
    player = selected_player()
    profile = selected_profile()
    return render_dashboard_view(player, profile, ctx, entity_type)


def render_home():
    status = get_selected_player_status()
    feature_cards = [
        {
            "title": "Scouting Board",
            "description": "15~25세 기준으로 분석 준비가 된 유망주를 우선 검색하고 선택합니다.",
            "button_label": "보드 열기",
            "nav_target": "유망주 검색",
        },
        {
            "title": "Player Dossier",
            "description": "선택한 선수의 데이터 준비도, 성장 인사이트, 플레이어 정체성을 확인합니다.",
            "button_label": "Dossier 보기",
            "nav_target": "유망주 통합 분석",
        },
        {
            "title": "Mentor Matching Lab",
            "description": "현재 선수에게 참고가 될 만한 선배 유형과 멘토 후보를 확인합니다.",
            "button_label": "멘토 찾기",
            "nav_target": "유사 선수 후보",
        },
        {
            "title": "Career Simulation",
            "description": "훈련 강도, 출전 기회, 리그 수준에 따른 성장 시나리오를 확인합니다.",
            "button_label": "시뮬레이션 시작",
            "nav_target": "커리어 시뮬레이션",
        },
        {
            "title": "Scouting Report Draft",
            "description": "정량 분석과 사용자가 입력한 정성 근거를 바탕으로 리포트 초안을 생성합니다.",
            "button_label": "리포트 생성",
            "nav_target": "AI 스카우팅 리포트",
        },
        {
            "title": "My Scouting Notes",
            "description": "리포트, 커리어 시뮬레이션, 직접 입력 유망주 분석 등 저장된 노트를 모아봅니다.",
            "button_label": "저장된 노트 보기",
            "nav_target": "내 스카우팅 노트",
        },
        {
            "title": "Manual Prospect",
            "description": "능력치를 직접 입력해 유망주를 만들고, 통합 분석과 리포트 흐름을 체험합니다.",
            "button_label": "직접 입력하기",
            "nav_target": "직접 입력 유망주",
        },
        {
            "title": "Experimental Data Lab",
            "description": "실험 기능과 데이터 파이프라인 상태를 별도 공간에서 점검합니다.",
            "button_label": "실험실 열기",
            "nav_target": "실험실 (Data Lab)",
        },
        {
            "title": "DB Status",
            "description": "Supabase 연결과 데이터 상태를 확인합니다.",
            "button_label": "DB 상태 보기",
            "nav_target": "DB 상태 확인",
        },
    ]
    render_home_view(status, feature_cards)


def render_data_lab():
    render_experimental_data_lab_view()


def render_db_status():
    render_db_status_view()


def render_prospect_search():
    return render_prospect_search_view(show_selected_player_banner)


def render_career_simulation():
    if st.session_state.get("selected_entity_type") == "manual_prospect":
        return render_career_simulation_view(selected_player(), None, "manual_prospect")
    player = require_selected_player()
    if player is None:
        return
    profile = get_player_profile(player)
    entity_type = selected_entity_type()
    return render_career_simulation_view(player, profile, entity_type)


def render_legend_matching():
    if st.session_state.get("selected_entity_type") == "manual_prospect":
        return render_legend_matching_view(selected_player(), None, {"fallback_note": None})
    player = require_selected_player()
    if player is None:
        return
    ctx = resolve_selected_player_context()
    profile = selected_profile()
    return render_legend_matching_view(player, profile, ctx)


def render_ai_report():
    if st.session_state.get("selected_entity_type") == "manual_prospect":
        return render_ai_report_view(selected_player(), None)
    player = require_selected_player()
    if player is None:
        return
    profile = get_player_profile(player)
    return render_ai_report_view(player, profile)


def render_my_notes():
    return render_scouting_notes_view()


def render_manual_prospect():
    return render_manual_prospect_view()


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
        "직접 입력 유망주": render_manual_prospect,
        "실험실 (Data Lab)": render_data_lab,
        "DB 상태 확인": render_db_status,
    }
    if "nav_page_request" in st.session_state:
        st.session_state["nav_page"] = st.session_state.pop("nav_page_request")
    page = st.sidebar.radio("메뉴", list(menu.keys()), key="nav_page")
    st.sidebar.divider()
    render_app_header(page)
    menu[page]()


if __name__ == "__main__":
    main()
