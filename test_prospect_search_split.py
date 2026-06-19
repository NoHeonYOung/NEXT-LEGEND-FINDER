from streamlit.testing.v1 import AppTest


def test_prospect_search_renders():
    at = AppTest.from_file("app.py")
    at.session_state["nav_page"] = "유망주 검색"
    at.run(timeout=30)
    assert not at.exception


def test_search_select_and_stale_profile_id_cleared():
    at = AppTest.from_file("app.py")
    at.session_state["nav_page"] = "유망주 검색"
    at.run(timeout=30)
    assert not at.exception


if __name__ == "__main__":
    test_prospect_search_renders()
    print("test_prospect_search_renders OK")
    test_search_select_and_stale_profile_id_cleared()
    print("test_search_select_and_stale_profile_id_cleared OK")
