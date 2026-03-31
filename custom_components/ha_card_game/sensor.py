"""Sensors for HA Card Game."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
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
            GameStateSensor(coordinator, "Game State", "state"),
            GameStateSensor(coordinator, "Round", "round_number"),
            GameStateSensor(coordinator, "Judge", "judge"),
            GameStateSensor(coordinator, "Prompt", "current_prompt"),
            GameStateSensor(coordinator, "Winner", "winner"),
            GameStateSensor(coordinator, "Leaderboard", "leaderboard"),
        ]
    )


class GameStateSensor(CoordinatorEntity[CardGameCoordinator], SensorEntity):
    """Expose game state fields as sensors."""

    def __init__(self, coordinator: CardGameCoordinator, label: str, key: str) -> None:
        super().__init__(coordinator)
        self._attr_name = f"HA Card Game {label}"
        self._attr_unique_id = f"ha_card_game_{key}"
        self._key = key

    @property
    def native_value(self):
        value = self.coordinator.data.get(self._key)
        if isinstance(value, (dict, list)):
            return str(value)
        return value

    @property
    def extra_state_attributes(self):
        return {
            "raw": self.coordinator.data.get(self._key),
            "players": self.coordinator.data.get("players", []),
        }
