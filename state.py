"""세션 상태 기반 표시(display) helper 모음.

app.py를 import하지 않는다(순환 import 방지). selected_player_id/profile_id/
entity_type 판정 로직(resolve_selected_player_context 등)은 그대로 app.py에
남아있으며, 이 모듈은 그 결과(player dict, entity_type)를 인자로 받아 표시용
요약 정보를 만드는 순수 helper만 담는다.
"""

import streamlit as st


ENTITY_TYPE_LABELS = {
    "matched": "FM 프로필 + Transfermarkt 통합 데이터",
    "fm_profile_only": "FM 프로필 기반 후보",
    "transfermarkt_only": "Transfermarkt 기반 후보",
    "manual_note": "직접 입력 기반 분석",
    "manual_prospect": "직접 입력 선수",
    None: "선택 선수 없음",
}

DATA_MODE_BADGE_CLASS = {
    "matched": "data-mode-badge data-mode-matched",
    "fm_profile_only": "data-mode-badge data-mode-fm",
    "transfermarkt_only": "data-mode-badge data-mode-tm",
    "manual_note": "data-mode-badge data-mode-manual",
    "manual_prospect": "data-mode-badge data-mode-manual",
    None: "data-mode-badge data-mode-none",
}


def build_selected_player_status(player, entity_type):
    """Home 화면/공통 헤더에 표시할 선택 선수 상태 요약.

    player/entity_type은 app.py의 selected_player()/selected_entity_type()
    판정 결과를 그대로 전달받는다(판정 로직 자체는 변경하지 않음).
    """
    if player is not None and st.session_state.get("selected_entity_type") == "manual_prospect":
        entity_type = "manual_prospect"

    if player is None:
        manual_title = st.session_state.get("selected_manual_note_title")
        if st.session_state.get("selected_entity_type") == "manual_note" and manual_title:
            manual_payload = st.session_state.get("selected_manual_note_payload") or {}
            manual_player = manual_payload.get("manual_player", {})
            return {
                "has_player": True,
                "name": manual_title,
                "club": manual_player.get("club") or "-",
                "position": manual_player.get("position") or "-",
                "entity_type": "manual_note",
                "entity_label": ENTITY_TYPE_LABELS.get("manual_note"),
                "mentor_name": st.session_state.get("selected_mentor_name"),
            }

        return {
            "has_player": False,
            "name": None,
            "club": None,
            "position": None,
            "entity_type": None,
            "entity_label": None,
            "mentor_name": st.session_state.get("selected_mentor_name"),
        }

    return {
        "has_player": True,
        "name": player.get("name") or "-",
        "club": player.get("current_club_name") or "-",
        "position": player.get("position") or "-",
        "entity_type": entity_type,
        "entity_label": ENTITY_TYPE_LABELS.get(entity_type, entity_type),
        "mentor_name": st.session_state.get("selected_mentor_name"),
    }
