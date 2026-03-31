"""Config flow for HA Card Game."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ALLOW_REPEAT_PROMPTS,
    CONF_ENABLE_PANEL,
    CONF_MAX_ROUNDS,
    DEFAULT_ALLOW_REPEAT_PROMPTS,
    DEFAULT_ENABLE_PANEL,
    DEFAULT_MAX_ROUNDS,
    DEFAULT_TITLE,
    DOMAIN,
)


class HACardGameConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Card Game."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title=DEFAULT_TITLE, data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(CONF_ENABLE_PANEL, default=DEFAULT_ENABLE_PANEL): bool,
                vol.Optional(CONF_MAX_ROUNDS, default=DEFAULT_MAX_ROUNDS): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=100)
                ),
                vol.Optional(
                    CONF_ALLOW_REPEAT_PROMPTS, default=DEFAULT_ALLOW_REPEAT_PROMPTS
                ): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
