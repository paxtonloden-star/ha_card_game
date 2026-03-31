"""Diagnostics support for HA Card Game."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

REDACTED = "**REDACTED**"
_REDACT_KEYS = {
    "admin_token",
    "player_tokens",
    "session_token",
    "api_key",
    "remote_invites",
    "join_url",
    "join_code",
    "remote_base_url",
}


def redact_mapping(value: Any) -> Any:
    """Recursively redact secrets from nested mappings and lists."""
    if isinstance(value, dict):
        return {
            key: (REDACTED if key in _REDACT_KEYS else redact_mapping(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_mapping(item) for item in value]
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = getattr(entry, "runtime_data", None) or hass.data[DOMAIN][entry.entry_id]
    player_state = coordinator.player_state(None)
    diagnostics = {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": redact_mapping(dict(entry.data)),
            "options": redact_mapping(dict(entry.options)),
        },
        "runtime": {
            "options_summary": redact_mapping(coordinator.options_summary()),
            "state": redact_mapping(player_state),
            "scene_media": redact_mapping(dict(coordinator.scene_media_config)),
            "tournament": redact_mapping(dict(coordinator.tournament)),
            "ai_queue_size": len(coordinator.ai_moderation_queue),
            "custom_trivia_pack_count": len(coordinator.custom_trivia_packs),
            "custom_deck_count": len(coordinator.deck_manager.custom_decks),
            "available_decks": coordinator.deck_manager.list_decks(),
            "player_profile_count": len(coordinator.player_profiles),
            "websocket_client_count": len(getattr(coordinator, "_sockets", set())),
        },
        "storage_snapshot": redact_mapping(
            {
                "join_code_present": bool(coordinator.join_code),
                "admin_token_present": bool(coordinator.admin_token),
                "remote_invite_count": len(coordinator.remote_invites),
                "current_mode": coordinator.game_mode,
                "current_deck": coordinator.engine.state.deck_name,
                "trivia_category": getattr(coordinator.trivia, "category", None),
            }
        ),
    }
    return diagnostics
