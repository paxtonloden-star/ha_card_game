"""The HA Card Game integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError

from .api import async_register_api
from .const import (
    CONF_ENABLE_PANEL,
    DOMAIN,
    PLATFORMS,
    SERVICE_ADD_PLAYER,
    SERVICE_NEXT_ROUND,
    SERVICE_PICK_WINNER,
    SERVICE_RELOAD_DECKS,
    SERVICE_RESET_GAME,
    SERVICE_SET_DECK,
    SERVICE_START_GAME,
    SERVICE_SUBMIT_CARD,
)
from .panel import async_register_panel
from .repairs import ISSUE_DUPLICATE_ENTRIES, async_sync_repairs
from .trivia_core_coordinator import TriviaCoreCoordinator

SERVICE_PLAYER_NAME = "player_name"
SERVICE_CARD_TEXT = "card_text"
SERVICE_DECK_NAME = "deck_name"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    domain_entries = hass.config_entries.async_entries(DOMAIN)
    if len(domain_entries) > 1:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key=ISSUE_DUPLICATE_ENTRIES,
        )

    coordinator = TriviaCoreCoordinator(hass)

    await coordinator.async_load()

    coordinator.base_url = str(
        entry.options.get("remote_base_url", entry.data.get("remote_base_url", ""))
    ).strip().rstrip("/")

    await coordinator.async_apply_options({**entry.data, **entry.options})

    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    if entry.options.get(CONF_ENABLE_PANEL, entry.data.get(CONF_ENABLE_PANEL, True)):
        await async_register_panel(hass)

    await async_register_api(hass, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_register_services(hass, coordinator)
    await async_sync_repairs(hass, entry, coordinator)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if not hass.data.get(DOMAIN):
            hass.data.pop(DOMAIN, None)
        entry.runtime_data = None
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator: TriviaCoreCoordinator | None = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return
    panel_enabled = entry.options.get(CONF_ENABLE_PANEL, entry.data.get(CONF_ENABLE_PANEL, True))

    coordinator.base_url = str(
        entry.options.get("remote_base_url", entry.data.get("remote_base_url", ""))
    ).strip().rstrip("/")

    await coordinator.async_apply_options({**entry.data, **entry.options})
    if panel_enabled:
        await async_register_panel(hass)
    await async_sync_repairs(hass, entry, coordinator)


async def _async_register_services(hass: HomeAssistant, coordinator: TriviaCoreCoordinator) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_START_GAME):
        return

    async def start_game(call: ServiceCall) -> None:
        await coordinator.async_start_game(call.data.get(SERVICE_DECK_NAME, coordinator.engine.state.deck_name))

    async def add_player(call: ServiceCall) -> None:
        _protect(lambda: coordinator.engine.add_player(call.data[SERVICE_PLAYER_NAME]))
        await coordinator.async_refresh_from_engine()

    async def submit_card(call: ServiceCall) -> None:
        _protect(lambda: coordinator.engine.submit_card(call.data[SERVICE_PLAYER_NAME], call.data[SERVICE_CARD_TEXT]))
        await coordinator.async_refresh_from_engine()

    async def pick_winner(call: ServiceCall) -> None:
        _protect(lambda: coordinator.engine.pick_winner(call.data[SERVICE_PLAYER_NAME]))
        await coordinator.async_refresh_from_engine()

    async def next_round(call: ServiceCall) -> None:
        _protect(coordinator.engine.next_round)
        await coordinator.async_refresh_from_engine()

    async def reset_game(call: ServiceCall) -> None:
        await coordinator.async_reset_lobby()

    async def set_deck(call: ServiceCall) -> None:
        await coordinator.async_set_deck(call.data[SERVICE_DECK_NAME])

    async def reload_decks(call: ServiceCall) -> None:
        await coordinator.async_reload_decks()

    hass.services.async_register(DOMAIN, SERVICE_START_GAME, start_game, schema=vol.Schema({vol.Optional(SERVICE_DECK_NAME): str}))
    hass.services.async_register(DOMAIN, SERVICE_ADD_PLAYER, add_player, schema=vol.Schema({vol.Required(SERVICE_PLAYER_NAME): str}))
    hass.services.async_register(DOMAIN, SERVICE_SUBMIT_CARD, submit_card, schema=vol.Schema({vol.Required(SERVICE_PLAYER_NAME): str, vol.Required(SERVICE_CARD_TEXT): str}))
    hass.services.async_register(DOMAIN, SERVICE_PICK_WINNER, pick_winner, schema=vol.Schema({vol.Required(SERVICE_PLAYER_NAME): str}))
    hass.services.async_register(DOMAIN, SERVICE_NEXT_ROUND, next_round)
    hass.services.async_register(DOMAIN, SERVICE_RESET_GAME, reset_game)
    hass.services.async_register(DOMAIN, SERVICE_SET_DECK, set_deck, schema=vol.Schema({vol.Required(SERVICE_DECK_NAME): str}))
    hass.services.async_register(DOMAIN, SERVICE_RELOAD_DECKS, reload_decks)


def _protect(callback) -> Any:
    try:
        return callback()
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err
