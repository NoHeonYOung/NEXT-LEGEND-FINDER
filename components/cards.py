from html import escape


def panel_html(title, body, subtitle=None, kicker=None):
    kicker_html = f'<div class="kicker">{escape(str(kicker))}</div>' if kicker else ""
    subtitle_html = f'<div class="game-muted">{escape(str(subtitle))}</div>' if subtitle else ""
    return (
        '<div class="game-panel">'
        f"{kicker_html}<h3>{escape(str(title))}</h3>{subtitle_html}"
        f'<div>{body}</div>'
        "</div>"
    )


def stat_grid_html(stats):
    items = []
    for label, value in stats:
        items.append(
            '<div class="game-stat">'
            f'<div class="label">{escape(str(label))}</div>'
            f'<div class="value">{escape(str(value))}</div>'
            "</div>"
        )
    return '<div class="game-stat-grid">' + "".join(items) + "</div>"


def scout_card_html(name, meta_items, badges, reason, missing, level="partial"):
    safe_level = level if level in {"full", "partial", "limited"} else "partial"
    meta = " | ".join(str(item) for item in meta_items if item not in (None, ""))
    return f"""
    <div class="game-scout-card {safe_level}">
        <h3>{escape(str(name or "-"))}</h3>
        <div class="game-muted">{escape(meta or "-")}</div>
        <div class="game-card-row">{''.join(badges)}</div>
        <div><b>Scout read</b> {escape(str(reason or "-"))}</div>
        <div class="game-muted"><b>Data gap</b> {escape(str(missing or "-"))}</div>
    </div>
    """


def report_panel_html(title, rows, badge_html=""):
    row_html = "".join(f"<li>{escape(str(row))}</li>" for row in rows if row)
    return (
        '<div class="game-panel">'
        f'<div class="game-card-row">{badge_html}</div>'
        f"<h3>{escape(str(title))}</h3>"
        f"<ul>{row_html}</ul>"
        "</div>"
    )


def score_card_html(title, value, subtitle="", badge_html="", progress=None):
    progress_html = ""
    if progress is not None:
        try:
            pct = max(0, min(100, int(round(float(progress)))))
        except (TypeError, ValueError):
            pct = 0
        progress_html = f'<div class="game-progress"><span style="--value:{pct}%"></span></div>'
    subtitle_html = f'<div class="game-muted">{escape(str(subtitle))}</div>' if subtitle else ""
    return (
        '<div class="game-score-card">'
        f'<div class="game-card-row">{badge_html}</div>'
        f'<div class="label">{escape(str(title))}</div>'
        f'<div class="game-score-value">{escape(str(value))}</div>'
        f"{subtitle_html}{progress_html}"
        "</div>"
    )


def delta_badge_html(value):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    status = "positive" if numeric > 0 else "negative" if numeric < 0 else "neutral"
    return f'<span class="game-delta-badge {status}">{numeric:+.1f}</span>'


def game_alert_html(title, body, level="info"):
    safe_level = level if level in {"info", "warning", "danger"} else "info"
    return (
        f'<div class="game-alert {safe_level}">'
        f"<b>{escape(str(title))}</b><br>{escape(str(body))}"
        "</div>"
    )


def list_panel_html(title, items, kicker=None, empty="-"):
    visible = list(items or [])
    row_html = "".join(f"<li>{escape(str(item))}</li>" for item in visible)
    if not row_html:
        row_html = f"<li>{escape(str(empty))}</li>"
    kicker_html = f'<div class="kicker">{escape(str(kicker))}</div>' if kicker else ""
    return (
        '<div class="game-panel game-report-section">'
        f"{kicker_html}<h3>{escape(str(title))}</h3>"
        f"<ul>{row_html}</ul>"
        "</div>"
    )


def signal_grid_html(signals):
    cards = []
    for label, value, status in signals:
        cards.append(
            f'<div class="game-signal-card {escape(str(status or "neutral"))}">'
            f'<div class="label">{escape(str(label))}</div>'
            f'<div class="value">{escape(str(value))}</div>'
            "</div>"
        )
    return '<div class="game-signal-grid">' + "".join(cards) + "</div>"


# ---- Phase C components ----

def score_bar_html(label, value, max_value=1.0, suffix=""):
    try:
        num = float(value)
        pct = max(0, min(100, int(round(num / float(max_value) * 100))))
        value_text = f"{num:.4f}" if max_value <= 1 else f"{num:.1f}"
    except (TypeError, ValueError):
        pct = 0
        value_text = "-"
    return (
        '<div class="game-score-bar">'
        '<div class="bar-label">'
        f'<span>{escape(str(label))}</span>'
        f'<span class="bar-value">{escape(value_text)}{escape(str(suffix))}</span>'
        "</div>"
        f'<div class="game-progress"><span style="--value:{pct}%"></span></div>'
        "</div>"
    )


def empty_state_panel_html(title, body):
    return (
        '<div class="game-empty-state">'
        f'<div class="empty-title">{escape(str(title))}</div>'
        f'<div>{escape(str(body))}</div>'
        "</div>"
    )


def similarity_card_html(name, age, position, team, similarity, badges,
                         common_strengths, differences, tactical=None):
    try:
        sim_pct = max(0, min(100, int(round(float(similarity) * 100))))
        sim_text = f"{float(similarity):.4f}"
    except (TypeError, ValueError):
        sim_pct = 0
        sim_text = "-"
    badge_row = "".join(badges) if badges else ""
    tactical_html = (
        f'<div class="game-note-section">'
        f'<div class="game-note-section-label">전술적 해석</div>'
        f'<div>{escape(str(tactical))}</div>'
        "</div>"
    ) if tactical else ""
    return (
        '<div class="game-scout-card partial">'
        f'<h3>{escape(str(name or "-"))}</h3>'
        f'<div class="game-muted">{escape(str(age) if age is not None else "-")}세 · '
        f'{escape(str(position or "-"))} · {escape(str(team or "-"))}</div>'
        f'<div class="game-card-row">{badge_row}</div>'
        '<div class="game-score-bar">'
        '<div class="bar-label"><span>Similarity</span>'
        f'<span class="bar-value">{escape(sim_text)}</span></div>'
        f'<div class="game-progress"><span style="--value:{sim_pct}%"></span></div>'
        "</div>"
        '<div class="game-note-section">'
        '<div class="game-note-section-label">공통 강점</div>'
        f'<div>{escape(str(common_strengths or "-"))}</div>'
        "</div>"
        '<div class="game-note-section">'
        '<div class="game-note-section-label">주요 차이점</div>'
        f'<div>{escape(str(differences or "-"))}</div>'
        "</div>"
        f"{tactical_html}"
        "</div>"
    )


def mentor_card_html(name, age, position, team, similarity, badges,
                     reason, training, risk,
                     is_fallback=False, is_selected=False):
    try:
        sim_pct = max(0, min(100, int(round(float(similarity) * 100))))
        sim_text = f"{float(similarity):.4f}"
    except (TypeError, ValueError):
        sim_pct = 0
        sim_text = "-"
    badge_row = "".join(badges) if badges else ""
    extra_class = " selected" if is_selected else (" fallback" if is_fallback else "")
    fallback_note = (
        '<div class="game-muted" style="font-size:0.78rem;margin-top:8px;">'
        "⚠ 완화 기준 적용 후보</div>"
    ) if is_fallback else ""

    def _section(label, content):
        if not content:
            return ""
        return (
            f'<div class="game-note-section">'
            f'<div class="game-note-section-label">{escape(str(label))}</div>'
            f'<div>{escape(str(content))}</div>'
            "</div>"
        )

    return (
        f'<div class="game-mentor-card{extra_class}">'
        f'<h4>{escape(str(name or "-"))}</h4>'
        f'<div class="game-muted">{escape(str(age) if age is not None else "-")}세 · '
        f'{escape(str(position or "-"))} · {escape(str(team or "-"))}</div>'
        f'<div class="game-card-row">{badge_row}</div>'
        '<div class="game-score-bar">'
        '<div class="bar-label"><span>Style Similarity</span>'
        f'<span class="bar-value">{escape(sim_text)}</span></div>'
        f'<div class="game-progress"><span style="--value:{sim_pct}%"></span></div>'
        "</div>"
        f"{_section('멘토 적합 이유', reason)}"
        f"{_section('추천 훈련 방향', training)}"
        f"{_section('주의점 / 리스크', risk)}"
        f"{fallback_note}"
        "</div>"
    )


def archive_note_card_html(title, saved_at, note_type_label, entity_type_label,
                           report_mode_label, growth_score, final_growth_score,
                           badges, is_selected=False):
    card_class = "game-note-card" + (" selected" if is_selected else "")
    badge_row = "".join(badges) if badges else ""
    gs_text = str(growth_score) if growth_score not in (None, "", "-") else "-"
    fgs_text = str(final_growth_score) if final_growth_score not in (None, "", "-") else "-"

    def _meta(label, value):
        return (
            '<div class="game-note-meta-item">'
            f'<div class="label">{escape(str(label))}</div>'
            f'<div class="value">{escape(str(value or "-"))}</div>'
            "</div>"
        )

    return (
        f'<div class="{card_class}">'
        f'<h4>{escape(str(title or "이름 없는 노트"))}</h4>'
        f'<div class="game-muted" style="font-size:0.8rem;">{escape(str(saved_at or "-"))}</div>'
        f'<div class="game-card-row">{badge_row}</div>'
        '<div class="game-note-meta-row">'
        f'{_meta("Growth", gs_text)}'
        f'{_meta("Final", fgs_text)}'
        f'{_meta("Type", note_type_label)}'
        f'{_meta("Mode", report_mode_label)}'
        "</div>"
        "</div>"
    )
