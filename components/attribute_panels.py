from html import escape

import streamlit as st


def _safe_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def attribute_bar_html(label, value, max_value=20):
    number = _safe_number(value)
    if number is None:
        value_text = "No data"
        width = 0
    else:
        value_text = f"{number:.1f}".rstrip("0").rstrip(".")
        width = max(0, min(100, int(round(number / max_value * 100))))
    return f"""
    <div class="game-attr-row">
        <div class="game-attr-label"><span>{escape(str(label))}</span><span>{escape(value_text)}</span></div>
        <div class="game-progress"><span style="--value:{width}%"></span></div>
    </div>
    """


def render_attribute_snapshot(title, items, empty_text="No attribute data available."):
    rows = []
    for label, value in items:
        rows.append(attribute_bar_html(label, value))
    body = "".join(rows) if rows else f'<div class="game-muted">{escape(empty_text)}</div>'
    st.markdown(
        f"""
        <div class="game-panel">
            <div class="kicker">주요 능력치</div>
            <h3>{escape(str(title))}</h3>
            {body}
        </div>
        """,
        unsafe_allow_html=True,
    )

