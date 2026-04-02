"""Simple panel registration for HA Card Game."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PANEL_REGISTERED_KEY = f"{DOMAIN}_panel_registered"
STATIC_REGISTERED_KEY = f"{DOMAIN}_static_registered"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the panel only once."""
    panel_path = f"/local/{DOMAIN}/index.html"
    static_dir = Path(__file__).parent / "frontend"

    if not hass.data.get(STATIC_REGISTERED_KEY):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(f"/local/{DOMAIN}", str(static_dir), cache_headers=False)]
        )
        hass.data[STATIC_REGISTERED_KEY] = True

    if hass.data.get(PANEL_REGISTERED_KEY):
        return

    async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title="Card Game",
        sidebar_icon="mdi:cards-playing-outline",
        frontend_url_path=DOMAIN,
        config={"url": panel_path},
        require_admin=False,
    )

    hass.data[PANEL_REGISTERED_KEY] = True
