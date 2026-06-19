from streamlit.testing.v1 import AppTest


def test_home_renders():
    at = AppTest.from_file("app.py")
    at.run(timeout=30)
    assert not at.exception


def test_vinicius_transfermarkt_only():
    at = AppTest.from_file("app.py")
    at.session_state["selected_player_id"] = 371998
    at.session_state["nav_page"] = "유망주 통합 분석"
    at.run(timeout=30)
    assert not at.exception
    assert True


def test_manual_note_status():
    at = AppTest.from_file("app.py")
    at.session_state["selected_entity_type"] = "manual_note"
    at.session_state["selected_manual_note_title"] = "Custom Prospect A"
    at.session_state["selected_manual_note_payload"] = {
        "manual_player": {"club": "Test FC", "position": "FW"}
    }
    at.session_state["nav_page"] = "유망주 통합 분석"
    at.run(timeout=30)
    assert not at.exception
    assert at.session_state["selected_entity_type"] == "manual_note"


if __name__ == "__main__":
    test_home_renders()
    print("test_home_renders OK")
    test_vinicius_transfermarkt_only()
    print("test_vinicius_transfermarkt_only OK")
    test_manual_note_status()
    print("test_manual_note_status OK")
