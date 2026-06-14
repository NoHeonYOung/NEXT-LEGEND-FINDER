def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def format_percent(value):
    try:
        number = float(value) * 100
        return f"{number:.0f}%"
    except Exception:
        return "0%"
