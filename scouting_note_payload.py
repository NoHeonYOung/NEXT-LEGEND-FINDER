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
    qualitative_evidence_source=None,
    report_generation_mode="rule_based",
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
        "qualitative_evidence_source": json_safe(qualitative_evidence_source or "none"),
        "report_generation_mode": json_safe(report_generation_mode or "rule_based"),
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
    qualitative_evidence=None,
    gemini_advisory=None,
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
        "qualitative_evidence": json_safe(qualitative_evidence or {}),
        "gemini_advisory": json_safe(gemini_advisory or {}),
    })
    return result


def _build_note_payload(
    *,
    note_type,
    source,
    entity_type=None,
    player,
    profile,
    env_settings,
    simulation_result,
    growth_insight,
    growth_explanation,
    ceiling_growth_insight=None,
    ceiling_growth_explanation=None,
    ceiling_growth_context=None,
    report_sections,
    report_text,
    qualitative_evidence=None,
    gemini_advisory=None,
):
    has_gemini = bool(
        isinstance(qualitative_evidence, dict) and qualitative_evidence.get("extracted_signals")
        or isinstance(gemini_advisory, dict) and gemini_advisory.get("advisory_summary")
    )
    report_generation_mode = "rule_based_with_gemini" if has_gemini else "rule_based"
    qualitative_source = (
        (qualitative_evidence or {}).get("source", "none")
        if isinstance(qualitative_evidence, dict)
        else "none"
    )
    safe_player = player if isinstance(player, dict) else {}
    safe_profile = profile if isinstance(profile, dict) else {}
    return {
        "player_id": json_safe(safe_player.get("player_id")),
        "profile_id": json_safe(safe_profile.get("profile_id")),
        "player_name": json_safe(safe_player.get("name") or safe_profile.get("name")),
        "env_settings": _build_env_settings(
            env_settings,
            note_type,
            source,
            entity_type,
            player,
            profile,
            ceiling_growth_context,
            qualitative_evidence_source=qualitative_source,
            report_generation_mode=report_generation_mode,
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
            qualitative_evidence=qualitative_evidence,
            gemini_advisory=gemini_advisory,
        ),
        "report": json_safe(report_text or ""),
    }


def build_ai_report_note_payload(**kwargs):
    return _build_note_payload(note_type="ai_report", source="ai_report", **kwargs)


def build_career_simulation_note_payload(**kwargs):
    return _build_note_payload(note_type="career_simulation", source="career_simulation", **kwargs)


def _manual_report_text(report_sections):
    if not isinstance(report_sections, dict) or not report_sections:
        return ""
    lines = ["직접 입력 유망주 분석 리포트"]
    for title, content in report_sections.items():
        lines.extend(["", str(title), str(content)])
    return "\n".join(lines)


def build_manual_note_payload(**kwargs):
    source = kwargs.pop("source", "manual_note")
    source_player = kwargs.pop("player", {}) or {}
    source_profile = kwargs.pop("profile", {}) or {}
    kwargs.pop("entity_type", None)
    raw_env_settings = kwargs.pop("env_settings", {})
    env_settings = raw_env_settings if isinstance(raw_env_settings, dict) else {}
    manual_player = kwargs.pop("manual_player", None)
    if not isinstance(manual_player, dict) or not manual_player:
        manual_player = env_settings.get("manual_player") if isinstance(env_settings.get("manual_player"), dict) else {}
    if not manual_player:
        manual_player = source_player if isinstance(source_player, dict) else {}
    manual_attributes = kwargs.pop("manual_attributes", None)
    if not isinstance(manual_attributes, dict):
        manual_attributes = env_settings.get("manual_attributes") if isinstance(env_settings.get("manual_attributes"), dict) else {}
    manual_career_settings = kwargs.pop("manual_career_settings", None)
    if not isinstance(manual_career_settings, dict):
        manual_career_settings = env_settings.get("manual_career_settings") if isinstance(env_settings.get("manual_career_settings"), dict) else {}
    report_sections = kwargs.get("report_sections") if isinstance(kwargs.get("report_sections"), dict) else {}
    report_text = kwargs.pop("report_text", None) or _manual_report_text(report_sections)

    player_id = manual_player.get("estimated_from_player_id")
    if player_id is None and isinstance(source_player, dict):
        player_id = source_player.get("player_id")
    player = {
        "player_id": player_id,
        "name": manual_player.get("name"),
        "age": manual_player.get("age"),
        "position": manual_player.get("position"),
        "sub_position": manual_player.get("sub_position"),
        "club": manual_player.get("club"),
        "current_club_name": manual_player.get("club"),
        "nationality": manual_player.get("nationality"),
        "country_of_citizenship": manual_player.get("nationality"),
    }
    if isinstance(source_player, dict):
        for key in ("name", "age", "position", "sub_position", "club", "current_club_name", "nationality", "country_of_citizenship"):
            if player.get(key) is None:
                player[key] = source_player.get(key)
    profile = {
        "profile_id": source_profile.get("profile_id") if isinstance(source_profile, dict) else None,
        "name": manual_player.get("name"),
        "age": manual_player.get("age"),
        "position": manual_player.get("position"),
        "sub_position": manual_player.get("sub_position"),
        "club": manual_player.get("club"),
        "nationality": manual_player.get("nationality"),
        "attributes_jsonb": manual_attributes,
        "mentality_jsonb": manual_attributes,
    }
    if isinstance(source_player, dict):
        profile["name"] = profile.get("name") or source_player.get("name")
        profile["age"] = profile.get("age") or source_player.get("age")
        profile["position"] = profile.get("position") or source_player.get("position")
        profile["club"] = profile.get("club") or source_player.get("club") or source_player.get("current_club_name")
    env_settings = dict(env_settings)
    env_settings.setdefault("manual_player", manual_player)
    env_settings.setdefault("manual_attributes", manual_attributes)
    env_settings.setdefault("manual_career_settings", manual_career_settings)

    payload = _build_note_payload(
        note_type="manual_custom_prospect",
        source=source,
        entity_type="manual_prospect",
        player=player,
        profile=profile,
        env_settings=env_settings,
        report_text=report_text,
        **kwargs,
    )
    payload["env_settings"]["manual_player"] = json_safe(manual_player)
    payload["env_settings"]["manual_attributes"] = json_safe(manual_attributes)
    payload["env_settings"]["manual_career_settings"] = json_safe(manual_career_settings)
    payload["simulation_result"]["manual_player"] = json_safe(manual_player)
    payload["simulation_result"]["manual_attributes"] = json_safe(manual_attributes)
    payload["simulation_result"]["manual_career_settings"] = json_safe(manual_career_settings)
    return payload


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
        "qualitative_evidence": simulation_result.get("qualitative_evidence") if isinstance(simulation_result.get("qualitative_evidence"), dict) else {},
        "gemini_advisory": simulation_result.get("gemini_advisory") if isinstance(simulation_result.get("gemini_advisory"), dict) else {},
    }
