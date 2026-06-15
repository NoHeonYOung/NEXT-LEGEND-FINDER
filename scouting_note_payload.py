"""Build structured scouting_notes JSONB payloads without DB or UI dependencies."""

from datetime import date, datetime
import math


CAREER_SETTING_KEYS = (
    "training_intensity",
    "playing_time_opportunity",
    "league_difficulty",
    "career_choice",
    "risk_level",
)
MAX_REPORT_SECTIONS = 50
MAX_REPORT_SECTION_CHARS = 5000


def json_safe(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if value.__class__.__name__ in ("NAType", "NaTType"):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return json_safe(value.item())
        except Exception:
            pass
    if hasattr(value, "to_dict"):
        try:
            return json_safe(value.to_dict())
        except Exception:
            pass
    return str(value)


def build_player_snapshot(player, profile=None):
    player = player if isinstance(player, dict) else {}
    profile = profile if isinstance(profile, dict) else {}
    return json_safe({
        "player_id": player.get("player_id"),
        "profile_id": profile.get("profile_id"),
        "name": player.get("name") or profile.get("name"),
        "age": profile.get("age") or player.get("age"),
        "position": player.get("position") or profile.get("position"),
        "sub_position": player.get("sub_position") or profile.get("sub_position"),
        "club": player.get("current_club_name") or player.get("club") or profile.get("club"),
        "nationality": player.get("country_of_citizenship") or player.get("nationality") or profile.get("nationality"),
    })


def build_profile_snapshot(profile):
    profile = profile if isinstance(profile, dict) else {}
    return json_safe({
        "profile_id": profile.get("profile_id"),
        "player_id": profile.get("player_id"),
        "name": profile.get("name"),
        "age": profile.get("age"),
        "club": profile.get("club"),
        "nationality": profile.get("nationality"),
        "position": profile.get("position"),
        "sub_position": profile.get("sub_position"),
    })


def compact_report_sections(report_sections):
    if not isinstance(report_sections, dict):
        return {}
    compacted = {}
    for index, (title, content) in enumerate(report_sections.items()):
        if index >= MAX_REPORT_SECTIONS:
            break
        safe_title = str(title)[:200]
        safe_content = json_safe(content)
        if isinstance(safe_content, str) and len(safe_content) > MAX_REPORT_SECTION_CHARS:
            safe_content = safe_content[:MAX_REPORT_SECTION_CHARS] + "... [truncated]"
        compacted[safe_title] = safe_content
    return compacted


def _career_settings(env_settings):
    env_settings = env_settings if isinstance(env_settings, dict) else {}
    nested = env_settings.get("career_settings")
    if isinstance(nested, dict):
        return json_safe(nested)
    return json_safe({key: env_settings.get(key) for key in CAREER_SETTING_KEYS if key in env_settings})


def _build_env_settings(
    base_env_settings,
    note_type,
    source,
    entity_type,
    player=None,
    profile=None,
    ceiling_growth_context=None,
):
    result = json_safe(base_env_settings if isinstance(base_env_settings, dict) else {})
    result.update({
        "note_type": note_type,
        "source": source,
        "entity_type": entity_type,
        "player_snapshot": build_player_snapshot(player, profile),
        "profile_snapshot": build_profile_snapshot(profile),
        "ceiling_growth_context": json_safe(ceiling_growth_context or {}),
        "career_settings": _career_settings(base_env_settings),
    })
    return result


def _build_simulation_result(
    base_simulation_result,
    growth_insight=None,
    growth_explanation=None,
    ceiling_growth_insight=None,
    ceiling_growth_explanation=None,
    ceiling_growth_context=None,
    report_sections=None,
    generated_report_text=None,
):
    prototype = json_safe(base_simulation_result if isinstance(base_simulation_result, dict) else {})
    result = dict(prototype)
    result.update({
        "prototype_simulation": prototype,
        "growth_insight": json_safe(growth_insight or {}),
        "growth_explanation": json_safe(growth_explanation or {}),
        "ceiling_growth_insight": json_safe(ceiling_growth_insight or {}),
        "ceiling_growth_explanation": json_safe(ceiling_growth_explanation or {}),
        "ceiling_growth_context": json_safe(ceiling_growth_context or {}),
        "report_sections": compact_report_sections(report_sections),
        "generated_report_text": json_safe(generated_report_text or ""),
    })
    return result


def _build_note_payload(
    *,
    note_type,
    source,
    entity_type,
    player,
    profile,
    env_settings,
    simulation_result,
    growth_insight,
    growth_explanation,
    ceiling_growth_insight,
    ceiling_growth_explanation,
    ceiling_growth_context,
    report_sections,
    report_text,
):
    return {
        "env_settings": _build_env_settings(
            env_settings,
            note_type,
            source,
            entity_type,
            player,
            profile,
            ceiling_growth_context,
        ),
        "simulation_result": _build_simulation_result(
            simulation_result,
            growth_insight,
            growth_explanation,
            ceiling_growth_insight,
            ceiling_growth_explanation,
            ceiling_growth_context,
            report_sections,
            report_text,
        ),
        "report": json_safe(report_text or ""),
    }


def build_ai_report_note_payload(**kwargs):
    return _build_note_payload(note_type="ai_report", source="ai_report", **kwargs)


def build_career_simulation_note_payload(**kwargs):
    return _build_note_payload(note_type="career_simulation", source="career_simulation", **kwargs)


def build_manual_note_payload(**kwargs):
    return _build_note_payload(note_type="manual_custom_prospect", source="manual_note", **kwargs)


def extract_structured_note_result(simulation_result):
    simulation_result = simulation_result if isinstance(simulation_result, dict) else {}
    prototype = simulation_result.get("prototype_simulation")
    if not isinstance(prototype, dict):
        prototype = simulation_result
    return {
        "prototype_simulation": prototype,
        "growth_insight": simulation_result.get("growth_insight") if isinstance(simulation_result.get("growth_insight"), dict) else {},
        "growth_explanation": simulation_result.get("growth_explanation") if isinstance(simulation_result.get("growth_explanation"), dict) else {},
        "ceiling_growth_insight": simulation_result.get("ceiling_growth_insight") if isinstance(simulation_result.get("ceiling_growth_insight"), dict) else {},
        "ceiling_growth_explanation": simulation_result.get("ceiling_growth_explanation") if isinstance(simulation_result.get("ceiling_growth_explanation"), dict) else {},
        "ceiling_growth_context": simulation_result.get("ceiling_growth_context") if isinstance(simulation_result.get("ceiling_growth_context"), dict) else {},
        "report_sections": simulation_result.get("report_sections") if isinstance(simulation_result.get("report_sections"), dict) else {},
        "generated_report_text": simulation_result.get("generated_report_text") or "",
    }
