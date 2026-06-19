from streamlit.testing.v1 import AppTest


def test_home_renders():
    at = AppTest.from_file("app.py")
    at.run(timeout=30)
    assert not at.exception


def test_vinicius_dashboard_and_legend_matching():
    at = AppTest.from_file("app.py")
    at.session_state["selected_player_id"] = 371998
    at.session_state["nav_page"] = "유망주 통합 분석"
    at.run(timeout=30)
    assert not at.exception

    at.session_state["nav_page"] = "유사 선수 후보"
    at.run(timeout=30)
    assert not at.exception


def test_matched_player_full_flow():
    at = AppTest.from_file("app.py")
    at.session_state["selected_player_id"] = 418560
    at.session_state["nav_page"] = "유망주 통합 분석"
    at.run(timeout=30)
    assert not at.exception

    at.session_state["nav_page"] = "유사 선수 후보"
    at.run(timeout=30)
    assert not at.exception

    mentor_buttons = [b for b in at.button if b.key and b.key.startswith("select_mentor_")]
    if mentor_buttons:
        mentor_buttons[0].click().run(timeout=30)
        assert not at.exception

    at.session_state["nav_page"] = "커리어 시뮬레이션"
    at.run(timeout=30)
    assert not at.exception

    at.session_state["nav_page"] = "AI 스카우팅 리포트"
    at.run(timeout=30)
    assert not at.exception

    at.session_state["nav_page"] = "내 스카우팅 노트"
    at.run(timeout=30)
    assert not at.exception


def test_manual_prospect_submission():
    at = AppTest.from_file("app.py")
    at.session_state["nav_page"] = "직접 입력 유망주"
    at.run(timeout=30)
    assert not at.exception


if __name__ == "__main__":
    test_home_renders()
    print("test_home_renders OK")
    test_vinicius_dashboard_and_legend_matching()
    print("test_vinicius_dashboard_and_legend_matching OK")
    test_matched_player_full_flow()
    print("test_matched_player_full_flow OK")
    test_manual_prospect_submission()
    print("test_manual_prospect_submission OK")
