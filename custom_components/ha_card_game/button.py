"""Buttons for HA Card Game."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CardGameCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CardGameCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SimpleActionButton(coordinator, "Next Round", "mdi:skip-next", coordinator.engine.next_round),
            SimpleActionButton(coordinator, "Reset Game", "mdi:restart", coordinator.engine.reset),
        ]
    )


class SimpleActionButton(CoordinatorEntity[CardGameCoordinator], ButtonEntity):
    """Trigger simple engine actions."""

    def __init__(self, coordinator: CardGameCoordinator, name: str, icon: str, callback) -> None:
        super().__init__(coordinator)
        self._attr_name = f"HA Card Game {name}"
        self._attr_unique_id = f"ha_card_game_{name.lower().replace(' ', '_')}"
        self._attr_icon = icon
        self._callback = callback

    async def async_press(self) -> None:
        self._callback()
        await self.coordinator.async_refresh_from_engine()
