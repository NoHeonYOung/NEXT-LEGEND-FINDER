from streamlit.testing.v1 import AppTest


def test_data_lab_renders_with_grid_and_gemini_status():
    at = AppTest.from_file("app.py")
    at.session_state["nav_page"] = "실험실 (Data Lab)"
    at.run(timeout=30)
    assert not at.exception

    md = "\n".join(m.value for m in at.markdown)
    subheaders = "\n".join(s.value for s in at.subheader)
    assert "Experimental Data Lab" in "\n".join(t.value for t in at.title)
    assert "10x10 Grid Vector Demo" in subheaders
    assert "Article Evidence Demo" in subheaders
    assert "Gemini API / Fallback Status" in subheaders
    assert "Data Engineering Pipeline" in subheaders

    # Gemini key가 없으므로 fallback 안내가 표시되어야 한다.
    assert "Rule-based fallback" in md or "GEMINI_API_KEY" in md

    # 샘플 선수 선택 selectbox가 표시되고 기본값이 채워져 있어야 한다.
    grid_player_select = at.selectbox(key="data_lab_grid_player")
    assert grid_player_select.value
    assert "Sample" in grid_player_select.value

    # 100차원 벡터/heatmap이 altair 차트로 렌더링되어야 한다.
    assert len(at.get("vega_lite_chart")) >= 1


def test_data_lab_evidence_fallback_extraction():
    at = AppTest.from_file("app.py")
    at.session_state["nav_page"] = "실험실 (Data Lab)"
    at.run(timeout=30)
    assert not at.exception

    # text_area는 form 내부에 있으므로 인덱스로 접근한다.
    text_areas = at.text_area
    assert len(text_areas) >= 1
    text_areas[0].set_value(
        "He shows great determination and a fantastic work rate, "
        "and stays composed under pressure in big games."
    )

    submit_buttons = [b for b in at.button if "Evidence" in (b.label or "")]
    assert submit_buttons
    submit_buttons[0].click()

    at.run(timeout=30)
    assert not at.exception

    assert "data_lab_evidence_result" in at.session_state
    result = at.session_state["data_lab_evidence_result"]
    assert result["mode"] == "fallback"
    assert result["scores"]["determination"] > 0
    assert result["scores"]["work_rate"] > 0
    assert result["scores"]["pressure_handling"] > 0

    md = "\n".join(m.value for m in at.markdown)
    assert "추출 모드" in md
    assert "Rule-based fallback" in md


def test_data_lab_does_not_crash_without_gemini_key():
    at = AppTest.from_file("app.py")
    at.session_state["nav_page"] = "실험실 (Data Lab)"
    at.run(timeout=30)
    assert not at.exception

    md = "\n".join(m.value for m in at.markdown)
    assert "GEMINI_API_KEY" in md or "Fallback" in md


if __name__ == "__main__":
    test_data_lab_renders_with_grid_and_gemini_status()
    print("test_data_lab_renders_with_grid_and_gemini_status OK")
    test_data_lab_evidence_fallback_extraction()
    print("test_data_lab_evidence_fallback_extraction OK")
    test_data_lab_does_not_crash_without_gemini_key()
    print("test_data_lab_does_not_crash_without_gemini_key OK")
