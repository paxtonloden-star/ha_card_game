"""System health support for HA Card Game."""

from __future__ import annotations

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_register(hass: HomeAssistant, register: system_health.SystemHealthRegistration) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, object]:
    """Return system health info."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        return {"loaded": False}
    coordinator = next(iter(entries.values()))
    return {
        "loaded": True,
        "players": len(coordinator.engine.state.players),
        "deck_count": len(coordinator.deck_manager.list_decks()),
        "custom_deck_count": len(coordinator.deck_manager.custom_decks),
        "custom_trivia_pack_count": len(coordinator.custom_trivia_packs),
        "storage_schema_version": coordinator.data.get("storage_schema_version"),
        "ai_enabled": bool(coordinator.ai_generator.settings.enabled),
        "remote_players_enabled": bool(coordinator.parental_controls.get("allow_remote_players")),
        "websocket_clients": len(getattr(coordinator, "_sockets", set())),
    }
