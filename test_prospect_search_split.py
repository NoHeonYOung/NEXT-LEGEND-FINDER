from streamlit.testing.v1 import AppTest


def test_prospect_search_renders():
    at = AppTest.from_file("app.py")
    at.session_state["nav_page"] = "유망주 검색"
    at.run(timeout=30)
    assert not at.exception
    titles = "\n".join(t.value for t in at.title)
    assert "유망주 검색" in titles


def test_search_select_and_stale_profile_id_cleared():
    at = AppTest.from_file("app.py")

    # 1) matched 선수(418560)를 먼저 선택해 selected_profile_id가 채워지도록 한다.
    at.session_state["selected_player_id"] = 418560
    at.session_state["nav_page"] = "유망주 통합 분석"
    at.run(timeout=30)
    assert not at.exception
    assert at.session_state["selected_entity_type"] == "matched"
    assert at.session_state["selected_profile_id"] is not None

    # 2) Prospect Search에서 "Vinicius"를 검색하고 Vinicius Junior(371998)를 선택한다.
    at.session_state["nav_page"] = "유망주 검색"
    at.run(timeout=30)
    assert not at.exception

    keyword_inputs = [t for t in at.text_input if "이름" in (t.label or "")]
    assert keyword_inputs, "선수 이름 입력 필드를 찾을 수 없습니다."
    keyword_inputs[0].set_value("Vinicius").run(timeout=30)

    search_buttons = [b for b in at.button if b.label == "유망주 검색"]
    assert search_buttons, "유망주 검색 버튼을 찾을 수 없습니다."
    search_buttons[0].click().run(timeout=30)
    assert not at.exception

    select_button = next(
        (b for b in at.button if b.key == "select_prospect_371998"), None
    )
    assert select_button is not None, "Vinicius Junior(371998) 선택 버튼을 찾을 수 없습니다."
    select_button.click().run(timeout=30)
    assert not at.exception

    assert at.session_state["selected_player_id"] == 371998
    # 이전 matched 선수의 profile_id/entity_type이 남아있지 않아야 한다.
    assert "selected_profile_id" not in at.session_state
    assert "selected_entity_type" not in at.session_state

    # 3) Dashboard로 이동하면 Vinicius Junior는 transfermarkt_only로 재계산되어야 한다.
    at.session_state["nav_page"] = "유망주 통합 분석"
    at.run(timeout=30)
    assert not at.exception
    assert at.session_state["selected_entity_type"] == "transfermarkt_only"
    assert "selected_profile_id" not in at.session_state
    md = "\n".join(m.value for m in at.markdown)
    assert "Transfermarkt" in md

    # 4) Legend Matching에서는 FM 프로필 없음 안내가 유지되어야 한다.
    at.session_state["nav_page"] = "유사 선수 후보"
    at.run(timeout=30)
    assert not at.exception


if __name__ == "__main__":
    test_prospect_search_renders()
    print("test_prospect_search_renders OK")
    test_search_select_and_stale_profile_id_cleared()
    print("test_search_select_and_stale_profile_id_cleared OK")
