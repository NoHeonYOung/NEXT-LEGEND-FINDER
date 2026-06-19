def coverage_label(level):
    labels = {
        "full": "Full",
        "partial": "Partial",
        "limited": "Limited",
        "manual_prospect": "Full",
    }
    return labels.get(level, str(level or "-").title())


def coverage_badge_html(level, prefix="Analysis Readiness"):
    label = coverage_label(level)
    class_name = {
        "full": "badge-full",
        "partial": "badge-partial",
        "limited": "badge-limited",
        "manual_prospect": "badge-full",
    }.get(level, "badge-neutral")
    return f'<span class="game-badge {class_name}">{prefix} {label}</span>'


def source_badge_html(label, status="neutral"):
    class_name = {
        "ok": "badge-full",
        "warning": "badge-partial",
        "missing": "badge-limited",
        "manual": "badge-manual",
    }.get(status, "badge-neutral")
    return f'<span class="game-badge {class_name}">{label}</span>'
