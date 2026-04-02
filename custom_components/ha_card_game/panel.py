"""Simple panel registration for HA Card Game."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register a basic iframe panel pointing to the local HTML app."""
    panel_path = f"/local/{DOMAIN}/index.modular.html"

    static_dir = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(f"/local/{DOMAIN}", str(static_dir), cache_headers=False)]
    )

    async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title="Card Game",
        sidebar_icon="mdi:cards-playing-outline",
        frontend_url_path=DOMAIN,
        config={"url": panel_path},
        require_admin=False,
    )
