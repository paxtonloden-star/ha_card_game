"""Storage migrations and compatibility helpers for HA Card Game."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .const import (
    CURRENT_STORAGE_SCHEMA_VERSION,
    DEFAULT_PARENTAL_CONTROLS,
    DEFAULT_REMOTE_BASE_URL,
)
from .moderation import normalize_parental_settings


LEGACY_KEY_MAP: dict[str, str] = {
    "theme": "round_theme",
    "custom_presets": "custom_theme_presets",
    "moderation_queue": "ai_moderation_queue",
    "profiles": "player_profiles",
    "media_scene_config": "scene_media_config",
}


def migrate_storage_payload(payload: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Migrate persisted payloads from older schemas into the current shape."""
    data = deepcopy(payload or {})
    applied: list[str] = []
    version = int(data.get("storage_schema_version", 1))

    data = _rename_legacy_keys(data, applied)
    data = _migrate_parental_controls(data, applied)
    data = _migrate_custom_trivia_packs(data, applied)
    data = _migrate_players(data, applied)
    data = _migrate_trivia_questions(data, applied)
    data = _migrate_remote_invites(data, applied)
    data = _migrate_theme_fields(data, applied)
    data = _migrate_ai_settings(data, applied)

    if version < CURRENT_STORAGE_SCHEMA_VERSION:
        applied.append(f"schema_v{version}_to_v{CURRENT_STORAGE_SCHEMA_VERSION}")
    data["storage_schema_version"] = CURRENT_STORAGE_SCHEMA_VERSION
    data["storage_migration_history"] = list(dict.fromkeys(data.get("storage_migration_history", []) + applied))
    return data, applied


def build_storage_payload(base_payload: dict[str, Any], *, migration_history: list[str] | None = None) -> dict[str, Any]:
    """Attach canonical storage metadata before saving."""
    payload = deepcopy(base_payload)
    payload["storage_schema_version"] = CURRENT_STORAGE_SCHEMA_VERSION
    payload["storage_migration_history"] = list(dict.fromkeys(migration_history or payload.get("storage_migration_history", [])))
    payload.setdefault("compatibility", {})
    payload["compatibility"].update(
        {
            "supports_parental_controls": True,
            "supports_custom_trivia_packs": True,
            "supports_theme_presets": True,
            "supports_remote_invites": True,
        }
    )
    return payload


def _rename_legacy_keys(data: dict[str, Any], applied: list[str]) -> dict[str, Any]:
    for old_key, new_key in LEGACY_KEY_MAP.items():
        if old_key in data and new_key not in data:
            data[new_key] = data.pop(old_key)
            applied.append(f"rename_{old_key}_to_{new_key}")
    return data


def _migrate_parental_controls(data: dict[str, Any], applied: list[str]) -> dict[str, Any]:
    parental = deepcopy(data.get("parental_controls") or DEFAULT_PARENTAL_CONTROLS)
    legacy_mode = data.pop("content_rating", None)
    legacy_remote = data.pop("remote_players_enabled", None)
    legacy_categories = data.pop("trivia_categories_allowed", None)
    if legacy_mode is not None:
        parental["content_mode"] = legacy_mode
        applied.append("content_rating_to_parental_controls")
    if legacy_remote is not None:
        parental["allow_remote_players"] = bool(legacy_remote)
        applied.append("remote_players_enabled_to_parental_controls")
    if legacy_categories is not None:
        parental["allowed_trivia_categories"] = list(legacy_categories)
        applied.append("trivia_categories_allowed_to_parental_controls")
    data["parental_controls"] = normalize_parental_settings(parental)
    if "base_url" in data and "remote_base_url" not in data:
        data["remote_base_url"] = (data.pop("base_url") or DEFAULT_REMOTE_BASE_URL).rstrip("/")
        applied.append("base_url_to_remote_base_url")
    return data


def _migrate_custom_trivia_packs(data: dict[str, Any], applied: list[str]) -> dict[str, Any]:
    packs = data.get("custom_trivia_packs")
    legacy_packs = data.pop("trivia_packs", None)
    source = packs if packs is not None else legacy_packs
    normalized: dict[str, Any] = {}
    if isinstance(source, list):
        for item in source:
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug") or item.get("name") or "custom_pack").strip().lower().replace(" ", "_")
            normalized[slug] = {
                "slug": slug,
                "name": item.get("name", slug.replace("_", " ").title()),
                "description": item.get("description", ""),
                "questions": list(item.get("questions", [])),
            }
        if legacy_packs is not None:
            applied.append("trivia_packs_list_to_dict")
    elif isinstance(source, dict):
        for slug, item in source.items():
            if not isinstance(item, dict):
                continue
            clean_slug = str(item.get("slug") or slug).strip().lower().replace(" ", "_")
            normalized[clean_slug] = {
                "slug": clean_slug,
                "name": item.get("name", clean_slug.replace("_", " ").title()),
                "description": item.get("description", ""),
                "questions": list(item.get("questions", [])),
            }
    data["custom_trivia_packs"] = normalized
    return data


def _migrate_players(data: dict[str, Any], applied: list[str]) -> dict[str, Any]:
    players = []
    changed = False
    for player in data.get("players", []):
        if not isinstance(player, dict):
            continue
        item = dict(player)
        if "team_name" in item and "team" not in item:
            item["team"] = item.pop("team_name")
            changed = True
        item.setdefault("team", "Solo")
        item.setdefault("hand", [])
        item.setdefault("score", 0)
        players.append(item)
    if changed:
        applied.append("player_team_name_to_team")
    if players:
        data["players"] = players
    profiles = data.get("player_profiles", {})
    if isinstance(profiles, list):
        normalized_profiles: dict[str, Any] = {}
        for item in profiles:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            normalized_profiles[item["name"]] = {k: v for k, v in item.items() if k != "name"}
        data["player_profiles"] = normalized_profiles
        applied.append("player_profiles_list_to_dict")
    return data


def _migrate_trivia_questions(data: dict[str, Any], applied: list[str]) -> dict[str, Any]:
    questions = []
    changed = False
    for question in data.get("trivia_questions", []):
        if not isinstance(question, dict):
            continue
        item = dict(question)
        if item.get("answer") and not item.get("correct_answer"):
            item["correct_answer"] = item.pop("answer")
            changed = True
        correct = str(item.get("correct_answer", "")).strip()
        accepted = item.get("accepted_answers")
        if not isinstance(accepted, list):
            item["accepted_answers"] = [correct] if correct else []
            changed = True
        elif correct and correct not in accepted:
            item["accepted_answers"] = [correct, *accepted]
            changed = True
        item.setdefault("choices", [])
        item.setdefault("difficulty", "medium")
        item.setdefault("age_range", "18_plus")
        questions.append(item)
    if changed:
        applied.append("normalize_trivia_questions")
    if questions:
        data["trivia_questions"] = questions
    return data


def _migrate_remote_invites(data: dict[str, Any], applied: list[str]) -> dict[str, Any]:
    invites = data.get("remote_invites", {})
    if isinstance(invites, list):
        normalized = {}
        for item in invites:
            if not isinstance(item, dict):
                continue
            token = item.get("token")
            player_name = item.get("player_name") or item.get("name")
            if not token or not player_name:
                continue
            normalized[player_name] = {
                "player_name": player_name,
                "token": token,
                "invite_url": item.get("invite_url", ""),
            }
        data["remote_invites"] = normalized
        applied.append("remote_invites_list_to_dict")
    return data


def _migrate_theme_fields(data: dict[str, Any], applied: list[str]) -> dict[str, Any]:
    if "theme_preset_name" in data and "theme_preset" not in data:
        data["theme_preset"] = data.pop("theme_preset_name")
        applied.append("theme_preset_name_to_theme_preset")
    if "round_theme" not in data and "theme" in data:
        data["round_theme"] = data.get("theme")
        applied.append("theme_to_round_theme")
    data.setdefault("custom_theme_presets", [])
    return data


def _migrate_ai_settings(data: dict[str, Any], applied: list[str]) -> dict[str, Any]:
    settings = deepcopy(data.get("ai_settings") or {})
    if "local_fallback" in settings and "use_local_fallback" not in settings:
        settings["use_local_fallback"] = bool(settings.pop("local_fallback"))
        applied.append("ai_local_fallback_to_use_local_fallback")
    data["ai_settings"] = settings
    return data
