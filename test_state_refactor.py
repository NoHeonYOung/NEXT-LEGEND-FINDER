from streamlit.testing.v1 import AppTest


def test_home_renders():
    at = AppTest.from_file("app.py")
    at.run(timeout=30)
    assert not at.exception
    md = "\n".join(m.value for m in at.markdown)
    assert "#07111F" in md or "NEXT-LEGEND FINDER" in md


def test_vinicius_transfermarkt_only():
    at = AppTest.from_file("app.py")
    at.session_state["selected_player_id"] = 371998
    at.session_state["nav_page"] = "유망주 통합 분석"
    at.run(timeout=30)
    assert not at.exception
    md = "\n".join(m.value for m in at.markdown)
    assert "Transfermarkt" in md
    assert at.session_state["selected_entity_type"] == "transfermarkt_only"


def test_manual_note_status():
    at = AppTest.from_file("app.py")
    at.session_state["selected_entity_type"] = "manual_note"
    at.session_state["selected_manual_note_title"] = "Custom Prospect A"
    at.session_state["selected_manual_note_payload"] = {
        "manual_player": {"club": "Test FC", "position": "FW"}
    }
    at.session_state["nav_page"] = "홈 / 서비스 소개"
    at.run(timeout=30)
    assert not at.exception
    md = "\n".join(m.value for m in at.markdown)
    assert "Custom Prospect A" in md
    assert "직접 입력 기반 분석" in md


if __name__ == "__main__":
    test_home_renders()
    print("test_home_renders OK")
    test_vinicius_transfermarkt_only()
    print("test_vinicius_transfermarkt_only OK")
    test_manual_note_status()
    print("test_manual_note_status OK")
