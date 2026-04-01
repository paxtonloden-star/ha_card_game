"""Config flow for HA Card Game."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_AI_API_KEY,
    CONF_AI_ENABLED,
    CONF_AI_ENDPOINT,
    CONF_AI_MODEL,
    CONF_AI_USE_LOCAL_FALLBACK,
    CONF_ALLOW_REMOTE_PLAYERS,
    CONF_ALLOW_REPEAT_PROMPTS,
    CONF_ALLOWED_TRIVIA_CATEGORIES,
    CONF_CONTENT_MODE,
    CONF_DEFAULT_GAME_MODE,
    CONF_DEFAULT_TRIVIA_SOURCE,
    CONF_ENABLE_PANEL,
    CONF_MAX_ROUNDS,
    CONF_REMOTE_BASE_URL,
    CONF_REQUIRE_AI_APPROVAL,
    DEFAULT_AI_ENABLED,
    DEFAULT_AI_ENDPOINT,
    DEFAULT_AI_MODEL,
    DEFAULT_AI_USE_LOCAL_FALLBACK,
    DEFAULT_ALLOW_REMOTE_PLAYERS,
    DEFAULT_ALLOW_REPEAT_PROMPTS,
    DEFAULT_CONTENT_MODE,
    DEFAULT_DEFAULT_GAME_MODE,
    DEFAULT_DEFAULT_TRIVIA_SOURCE,
    DEFAULT_ENABLE_PANEL,
    DEFAULT_MAX_ROUNDS,
    DEFAULT_REMOTE_BASE_URL,
    DEFAULT_REQUIRE_AI_APPROVAL,
    DEFAULT_TITLE,
    DOMAIN,
    GAME_MODE_CARDS,
    GAME_MODE_TRIVIA,
    PARENTAL_CONTENT_MODES,
    TRIVIA_CATEGORIES,
)


GAME_MODE_OPTIONS = [GAME_MODE_CARDS, GAME_MODE_TRIVIA]
TRIVIA_SOURCE_OPTIONS = ["offline_curated", "ai"]


def _normalize_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise vol.Invalid("invalid_url")
    return value.rstrip("/")


def _normalize_api_key(value: str) -> str:
    return (value or "").strip()


class HACardGameConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Card Game."""

    VERSION = 3

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return HACardGameOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                normalized = _normalize_options(user_input, previous={})
            except vol.Invalid as err:
                errors[err.path[0] if err.path else "base"] = str(err)
            else:
                return self.async_create_entry(title=DEFAULT_TITLE, data=normalized)

        return self.async_show_form(step_id="user", data_schema=_user_schema(user_input), errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Reconfigure the single existing config entry."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if not entries:
            return self.async_abort(reason="no_config_entry")

        existing = entries[0]
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                normalized = _normalize_options(user_input, previous={**existing.data, **existing.options})
            except vol.Invalid as err:
                errors[err.path[0] if err.path else "base"] = str(err)
            else:
                self.hass.config_entries.async_update_entry(
                    existing,
                    data={**existing.data, **normalized},
                    options={**existing.options},
                )
                await self.hass.config_entries.async_reload(existing.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        defaults = {**existing.data, **existing.options}
        return self.async_show_form(step_id="reconfigure", data_schema=_user_schema(defaults), errors=errors)


class HACardGameOptionsFlow(config_entries.OptionsFlow):
    """Manage HA Card Game options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._options: dict[str, Any] = {**config_entry.data, **config_entry.options}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["general", "content", "remote", "ai", "trivia", "finish"],
        )

    async def async_step_general(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self._async_show_and_update("general", _general_schema, user_input)

    async def async_step_content(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self._async_show_and_update("content", _content_schema, user_input)

    async def async_step_remote(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self._async_show_and_update("remote", _remote_schema, user_input)

    async def async_step_ai(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self._async_show_and_update("ai", _ai_schema, user_input)

    async def async_step_trivia(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self._async_show_and_update("trivia", _trivia_schema, user_input)

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        normalized = _normalize_options(self._options, previous={**self._config_entry.data, **self._config_entry.options})
        return self.async_create_entry(title="", data=normalized)

    async def _async_show_and_update(self, step_id: str, schema_factory: Any, user_input: dict[str, Any] | None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                normalized = _normalize_options(user_input, previous=self._options)
            except vol.Invalid as err:
                errors[err.path[0] if err.path else "base"] = str(err)
            else:
                self._options.update(normalized)
                return await self.async_step_init()
        defaults = user_input or self._options
        return self.async_show_form(step_id=step_id, data_schema=schema_factory(defaults), errors=errors)


def _normalize_options(user_input: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    merged = {**previous, **user_input}
    normalized = dict(merged)
    normalized[CONF_MAX_ROUNDS] = int(merged.get(CONF_MAX_ROUNDS, DEFAULT_MAX_ROUNDS))
    normalized[CONF_ENABLE_PANEL] = bool(merged.get(CONF_ENABLE_PANEL, DEFAULT_ENABLE_PANEL))
    normalized[CONF_ALLOW_REPEAT_PROMPTS] = bool(merged.get(CONF_ALLOW_REPEAT_PROMPTS, DEFAULT_ALLOW_REPEAT_PROMPTS))
    normalized[CONF_REQUIRE_AI_APPROVAL] = bool(merged.get(CONF_REQUIRE_AI_APPROVAL, DEFAULT_REQUIRE_AI_APPROVAL))
    normalized[CONF_ALLOW_REMOTE_PLAYERS] = bool(merged.get(CONF_ALLOW_REMOTE_PLAYERS, DEFAULT_ALLOW_REMOTE_PLAYERS))
    normalized[CONF_AI_ENABLED] = bool(merged.get(CONF_AI_ENABLED, DEFAULT_AI_ENABLED))
    normalized[CONF_AI_USE_LOCAL_FALLBACK] = bool(merged.get(CONF_AI_USE_LOCAL_FALLBACK, DEFAULT_AI_USE_LOCAL_FALLBACK))
    normalized[CONF_DEFAULT_GAME_MODE] = merged.get(CONF_DEFAULT_GAME_MODE, DEFAULT_DEFAULT_GAME_MODE)
    normalized[CONF_DEFAULT_TRIVIA_SOURCE] = merged.get(CONF_DEFAULT_TRIVIA_SOURCE, DEFAULT_DEFAULT_TRIVIA_SOURCE)
    normalized[CONF_CONTENT_MODE] = merged.get(CONF_CONTENT_MODE, DEFAULT_CONTENT_MODE)
    normalized[CONF_AI_MODEL] = (merged.get(CONF_AI_MODEL, DEFAULT_AI_MODEL) or DEFAULT_AI_MODEL).strip()
    normalized[CONF_AI_ENDPOINT] = _normalize_url(merged.get(CONF_AI_ENDPOINT, DEFAULT_AI_ENDPOINT))
    normalized[CONF_REMOTE_BASE_URL] = _normalize_url(merged.get(CONF_REMOTE_BASE_URL, DEFAULT_REMOTE_BASE_URL))
    normalized[CONF_AI_API_KEY] = _normalize_api_key(merged.get(CONF_AI_API_KEY, previous.get(CONF_AI_API_KEY, "")))

    if normalized[CONF_MAX_ROUNDS] < 1 or normalized[CONF_MAX_ROUNDS] > 100:
        raise vol.Invalid("round_range", path=[CONF_MAX_ROUNDS])
    if normalized[CONF_DEFAULT_GAME_MODE] not in GAME_MODE_OPTIONS:
        raise vol.Invalid("invalid_game_mode", path=[CONF_DEFAULT_GAME_MODE])
    if normalized[CONF_DEFAULT_TRIVIA_SOURCE] not in TRIVIA_SOURCE_OPTIONS:
        raise vol.Invalid("invalid_trivia_source", path=[CONF_DEFAULT_TRIVIA_SOURCE])
    if normalized[CONF_CONTENT_MODE] not in PARENTAL_CONTENT_MODES:
        raise vol.Invalid("invalid_content_mode", path=[CONF_CONTENT_MODE])

    categories = merged.get(CONF_ALLOWED_TRIVIA_CATEGORIES, previous.get(CONF_ALLOWED_TRIVIA_CATEGORIES, list(TRIVIA_CATEGORIES)))
    if isinstance(categories, dict):
        categories = [key for key, enabled in categories.items() if enabled]
    elif isinstance(categories, str):
        categories = [categories]
    else:
        categories = list(categories)
    categories = [item for item in categories if item in TRIVIA_CATEGORIES]
    normalized[CONF_ALLOWED_TRIVIA_CATEGORIES] = categories or list(TRIVIA_CATEGORIES)

    return {key: normalized[key] for key in user_input.keys() | {
        CONF_ALLOWED_TRIVIA_CATEGORIES,
        CONF_AI_API_KEY,
        CONF_AI_ENDPOINT,
        CONF_REMOTE_BASE_URL,
    } if key in normalized}


def _user_schema(defaults: dict[str, Any] | None) -> vol.Schema:
    values = defaults or {}
    return vol.Schema(
        {
            vol.Optional(CONF_ENABLE_PANEL, default=values.get(CONF_ENABLE_PANEL, DEFAULT_ENABLE_PANEL)): selector.BooleanSelector(),
            vol.Optional(CONF_MAX_ROUNDS, default=values.get(CONF_MAX_ROUNDS, DEFAULT_MAX_ROUNDS)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=100, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_ALLOW_REPEAT_PROMPTS, default=values.get(CONF_ALLOW_REPEAT_PROMPTS, DEFAULT_ALLOW_REPEAT_PROMPTS)): selector.BooleanSelector(),
            vol.Optional(CONF_DEFAULT_GAME_MODE, default=values.get(CONF_DEFAULT_GAME_MODE, DEFAULT_DEFAULT_GAME_MODE)): selector.SelectSelector(
                selector.SelectSelectorConfig(options=GAME_MODE_OPTIONS, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
        }
    )


def _general_schema(defaults: dict[str, Any]) -> vol.Schema:
    return _user_schema(defaults)


def _content_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_CONTENT_MODE, default=defaults.get(CONF_CONTENT_MODE, DEFAULT_CONTENT_MODE)): selector.SelectSelector(
                selector.SelectSelectorConfig(options=PARENTAL_CONTENT_MODES, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
            vol.Optional(CONF_REQUIRE_AI_APPROVAL, default=defaults.get(CONF_REQUIRE_AI_APPROVAL, DEFAULT_REQUIRE_AI_APPROVAL)): selector.BooleanSelector(),
            vol.Optional(CONF_ALLOW_REMOTE_PLAYERS, default=defaults.get(CONF_ALLOW_REMOTE_PLAYERS, DEFAULT_ALLOW_REMOTE_PLAYERS)): selector.BooleanSelector(),
        }
    )


def _remote_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_REMOTE_BASE_URL, default=defaults.get(CONF_REMOTE_BASE_URL, DEFAULT_REMOTE_BASE_URL)): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            ),
        }
    )


def _ai_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_AI_ENABLED, default=defaults.get(CONF_AI_ENABLED, DEFAULT_AI_ENABLED)): selector.BooleanSelector(),
            vol.Optional(CONF_AI_USE_LOCAL_FALLBACK, default=defaults.get(CONF_AI_USE_LOCAL_FALLBACK, DEFAULT_AI_USE_LOCAL_FALLBACK)): selector.BooleanSelector(),
            vol.Optional(CONF_AI_MODEL, default=defaults.get(CONF_AI_MODEL, DEFAULT_AI_MODEL)): selector.TextSelector(),
            vol.Optional(CONF_AI_ENDPOINT, default=defaults.get(CONF_AI_ENDPOINT, DEFAULT_AI_ENDPOINT)): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            ),
            vol.Optional(CONF_AI_API_KEY, default=defaults.get(CONF_AI_API_KEY, "")): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
        }
    )


def _trivia_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_DEFAULT_TRIVIA_SOURCE, default=defaults.get(CONF_DEFAULT_TRIVIA_SOURCE, DEFAULT_DEFAULT_TRIVIA_SOURCE)): selector.SelectSelector(
                selector.SelectSelectorConfig(options=TRIVIA_SOURCE_OPTIONS, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
            vol.Optional(CONF_ALLOWED_TRIVIA_CATEGORIES, default=defaults.get(CONF_ALLOWED_TRIVIA_CATEGORIES, list(TRIVIA_CATEGORIES))): selector.SelectSelector(
                selector.SelectSelectorConfig(options=TRIVIA_CATEGORIES, multiple=True, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
        }
    )
