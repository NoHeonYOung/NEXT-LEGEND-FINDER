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
    md = "\n".join(m.value for m in at.markdown)
    assert "Transfermarkt" in md
    assert at.session_state["selected_entity_type"] == "transfermarkt_only"

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

    sim_buttons = [b for b in at.button if "시뮬레이션" in (b.label or "")]
    if sim_buttons:
        sim_buttons[0].click().run(timeout=30)
        assert not at.exception

    at.session_state["nav_page"] = "AI 스카우팅 리포트"
    at.run(timeout=30)
    assert not at.exception

    report_buttons = [b for b in at.button if "리포트" in (b.label or "")]
    if report_buttons:
        report_buttons[0].click().run(timeout=30)
        assert not at.exception

    at.session_state["nav_page"] = "내 스카우팅 노트"
    at.run(timeout=30)
    assert not at.exception


def test_manual_note_submission():
    at = AppTest.from_file("app.py")
    at.session_state["nav_page"] = "내 스카우팅 노트"
    at.run(timeout=30)
    assert not at.exception

    name_inputs = [t for t in at.text_input if "이름" in (t.label or "")]
    assert name_inputs, "유망주 이름 입력 필드를 찾을 수 없습니다."
    name_inputs[0].set_value("Custom Prospect A").run(timeout=30)

    submit_buttons = [b for b in at.button if "생성" in (b.label or "") or "제출" in (b.label or "")]
    assert submit_buttons, "제출 버튼을 찾을 수 없습니다."
    submit_buttons[0].click().run(timeout=30)
    assert not at.exception


if __name__ == "__main__":
    test_home_renders()
    print("test_home_renders OK")
    test_vinicius_dashboard_and_legend_matching()
    print("test_vinicius_dashboard_and_legend_matching OK")
    test_matched_player_full_flow()
    print("test_matched_player_full_flow OK")
    test_manual_note_submission()
    print("test_manual_note_submission OK")
