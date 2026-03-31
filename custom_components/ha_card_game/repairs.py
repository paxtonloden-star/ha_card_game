"""Repair issue helpers for HA Card Game."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, TRIVIA_CATEGORIES

ISSUE_REMOTE_BASE_URL = "remote_players_without_base_url"
ISSUE_AI_KEY = "ai_enabled_without_key_or_fallback"
ISSUE_NO_TRIVIA_CATEGORIES = "no_trivia_categories_enabled"


def compute_repair_issues(options: dict[str, Any], *, base_url: str, ai_settings: dict[str, Any]) -> set[str]:
    """Return repair issue ids that should be active."""
    issues: set[str] = set()

    if options.get("allow_remote_players") and not (options.get("remote_base_url") or base_url):
        issues.add(ISSUE_REMOTE_BASE_URL)

    ai_enabled = bool(options.get("ai_enabled", ai_settings.get("enabled")))
    has_api_key = bool(options.get("ai_api_key") or ai_settings.get("api_key"))
    use_local_fallback = bool(options.get("ai_use_local_fallback", ai_settings.get("use_local_fallback", True)))
    if ai_enabled and not has_api_key and not use_local_fallback:
        issues.add(ISSUE_AI_KEY)

    categories = list(options.get("allowed_trivia_categories") or [])
    if not [category for category in categories if category in TRIVIA_CATEGORIES]:
        issues.add(ISSUE_NO_TRIVIA_CATEGORIES)

    return issues


async def async_sync_repairs(hass: HomeAssistant, entry: ConfigEntry, coordinator: Any) -> None:
    """Create or clear repair issues based on current runtime state."""
    active = compute_repair_issues(
        {**dict(entry.data), **dict(entry.options)},
        base_url=getattr(coordinator, "base_url", ""),
        ai_settings=coordinator.ai_generator.settings.as_dict() | {"api_key": coordinator.ai_generator.settings.api_key},
    )

    issue_definitions = {
        ISSUE_REMOTE_BASE_URL: {
            "translation_key": ISSUE_REMOTE_BASE_URL,
            "severity": ir.IssueSeverity.WARNING,
            "is_fixable": False,
        },
        ISSUE_AI_KEY: {
            "translation_key": ISSUE_AI_KEY,
            "severity": ir.IssueSeverity.ERROR,
            "is_fixable": False,
        },
        ISSUE_NO_TRIVIA_CATEGORIES: {
            "translation_key": ISSUE_NO_TRIVIA_CATEGORIES,
            "severity": ir.IssueSeverity.WARNING,
            "is_fixable": False,
        },
    }

    for issue_id, meta in issue_definitions.items():
        if issue_id in active:
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=meta["is_fixable"],
                severity=meta["severity"],
                translation_key=meta["translation_key"],
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
