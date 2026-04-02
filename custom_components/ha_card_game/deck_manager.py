"""Deck pack loading and selection for HA Card Game."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DECKS_FOLDER_NAME, DEFAULT_DECK, DEFAULT_HAND_SIZE, DEFAULT_PROMPTS, DEFAULT_WHITE_CARDS, DECK_EXPORT_KIND, DECK_EXPORT_VERSION


@dataclass
class DeckDefinition:
    slug: str
    name: str
    prompts: list[str]
    white_cards: list[str]
    allow_free_text: bool = False
    hand_size: int = DEFAULT_HAND_SIZE
    description: str = ""
    source: str = "builtin"

    def as_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "prompt_count": len(self.prompts),
            "white_card_count": len(self.white_cards),
            "allow_free_text": self.allow_free_text,
            "hand_size": self.hand_size,
            "source": self.source,
        }


BUILTIN_DECKS: dict[str, DeckDefinition] = {
    "default_family": DeckDefinition(
        slug="default_family",
        name="Default Family",
        description="Family-safe starter deck for building and testing the game.",
        prompts=list(DEFAULT_PROMPTS),
        white_cards=list(DEFAULT_WHITE_CARDS),
        allow_free_text=False,
        hand_size=7,
        source="builtin",
    ),
    "party_judge_original": DeckDefinition(
        slug="party_judge_original",
        name="Party Judge Original",
        description="Original judge-style party deck with fill-in-the-blank prompts and punchline answers.",
        prompts=[
            "Family game night was ruined by ____." ,
            "The weirdest thing to bring to a sleepover is ____." ,
            "My smart TV now recommends ____ to everyone." ,
            "The science fair went sideways because of ____." ,
            "The principal called home about ____." ,
            "Nothing says victory like ____." ,
            "The unexpected star of the road trip was ____." ,
        ],
        white_cards=[
            "a suspicious amount of glitter",
            "three raccoons in a trench coat",
            "an emergency dance break",
            "unreasonably dramatic toast",
            "a cursed group chat",
            "mystery slime",
            "one sock with leadership skills",
            "a laser pointer and bad ideas",
            "deep-fried homework",
            "an accidental boss battle",
            "fifty-seven stickers",
            "the loudest kazoo on Earth",
            "Wi-Fi powered confidence",
            "a surprise puppet show",
        ],
        allow_free_text=True,
        hand_size=7,
        source="builtin",
    ),

    "smart_home_chaos": DeckDefinition(
        slug="smart_home_chaos",
        name="Smart Home Chaos",
        description="More technical prompts and answers for smart-home and network humor.",
        prompts=[
            "The outage report blamed ____." ,
            "The real reason the dashboard froze was ____." ,
            "Home Assistant really needs less ____ and more reliability." ,
            "Tonight's maintenance window was destroyed by ____." ,
            "The family stopped trusting my automations after ____." ,
        ],
        white_cards=[
            "BGP in a smart home",
            "a broken entity registry",
            "YAML tabs",
            "an expired SSL certificate",
            "a rogue ESPHome build",
            "an overconfident network engineer",
            "STP recalculation",
            "a half-finished blueprint",
            "thirty-one battery alerts",
            "an accidental factory reset",
            "a noisy UPS",
            "the wrong DNS server",
            "loopback confusion",
            "an API rate limit",
        ],
        allow_free_text=True,
        hand_size=7,
        source="builtin",
    ),
}


class DeckManager:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._decks: dict[str, DeckDefinition] = {}


    async def save_deck(self, payload: dict[str, Any], source: str = "custom") -> DeckDefinition:
        deck = self._from_payload(payload, source=source)
        if len(deck.prompts) < 1:
            raise ValueError("Deck must include at least one prompt")
        if len(deck.white_cards) < 3:
            raise ValueError("Deck must include at least three white cards")
        self.deck_dir.mkdir(parents=True, exist_ok=True)
        path = self.deck_dir / f"{deck.slug}.json"
        path.write_text(json.dumps({
            "slug": deck.slug,
            "name": deck.name,
            "description": deck.description,
            "allow_free_text": deck.allow_free_text,
            "hand_size": deck.hand_size,
            "prompts": deck.prompts,
            "white_cards": deck.white_cards,
        }, indent=2), encoding="utf-8")
        await self.async_load()
        return self.get_deck(deck.slug)

    async def async_extend_deck(self, slug: str, *, prompts: list[str] | None = None, white_cards: list[str] | None = None) -> DeckDefinition:
        deck = self.get_deck(slug)
        payload = {
            "slug": deck.slug,
            "name": deck.name,
            "description": deck.description,
            "allow_free_text": True if deck.allow_free_text or white_cards else deck.allow_free_text,
            "hand_size": deck.hand_size,
            "prompts": list(deck.prompts) + [str(x).strip() for x in (prompts or []) if str(x).strip()],
            "white_cards": list(deck.white_cards) + [str(x).strip() for x in (white_cards or []) if str(x).strip()],
        }
        return await self.save_deck(payload, source="custom")

    @property
    def deck_dir(self) -> Path:
        return Path(self.hass.config.path(DECKS_FOLDER_NAME))

    async def async_load(self) -> None:
        self._decks = dict(BUILTIN_DECKS)
        self.deck_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(self.deck_dir.glob('*.json')):
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
                deck = self._from_payload(payload, source=str(path.name))
            except Exception:
                continue
            self._decks[deck.slug] = deck

    def list_decks(self) -> list[dict[str, Any]]:
        return [deck.as_dict() for deck in sorted(self._decks.values(), key=lambda d: d.name.lower())]

    def get_deck(self, slug: str | None) -> DeckDefinition:
        slug = slug or DEFAULT_DECK
        return self._decks.get(slug) or self._decks[DEFAULT_DECK]

    def write_example_decks(self) -> None:
        self.deck_dir.mkdir(parents=True, exist_ok=True)
        for deck in BUILTIN_DECKS.values():
            path = self.deck_dir / f"{deck.slug}.example.json"
            if not path.exists():
                path.write_text(json.dumps({
                    "slug": deck.slug,
                    "name": deck.name,
                    "description": deck.description,
                    "allow_free_text": deck.allow_free_text,
                    "hand_size": deck.hand_size,
                    "prompts": deck.prompts,
                    "white_cards": deck.white_cards,
                }, indent=2), encoding='utf-8')

    def export_decks(self, include_builtin: bool = False) -> dict[str, Any]:
        decks: list[dict[str, Any]] = []
        for deck in sorted(self._decks.values(), key=lambda d: d.name.lower()):
            if deck.source == "builtin" and not include_builtin:
                continue
            decks.append({
                "slug": deck.slug,
                "name": deck.name,
                "description": deck.description,
                "allow_free_text": deck.allow_free_text,
                "hand_size": deck.hand_size,
                "prompts": list(deck.prompts),
                "white_cards": list(deck.white_cards),
                "is_custom": deck.source != "builtin",
                "source": deck.source,
            })
        return {
            "kind": DECK_EXPORT_KIND,
            "version": DECK_EXPORT_VERSION,
            "decks": decks,
        }

    async def async_import_decks(self, payload: dict[str, Any], mode: str = "merge") -> None:
        if not isinstance(payload, dict):
            raise ValueError("Deck import payload must be an object")
        if payload.get("kind") != DECK_EXPORT_KIND:
            raise ValueError("Unsupported deck import file")
        decks = payload.get("decks")
        if not isinstance(decks, list):
            raise ValueError("Deck import file is missing decks")
        mode = (mode or "merge").strip().lower()
        if mode not in {"merge", "replace"}:
            raise ValueError("Import mode must be merge or replace")

        self.deck_dir.mkdir(parents=True, exist_ok=True)
        imported: list[DeckDefinition] = []
        seen_slugs: set[str] = set()
        for item in decks:
            if not isinstance(item, dict):
                raise ValueError("Invalid deck entry in import file")
            if item.get("is_custom") is False:
                continue
            deck = self._from_payload(item, source="import")
            if not deck.name.strip():
                raise ValueError("Imported deck is missing a name")
            if len(deck.prompts) < 1:
                raise ValueError(f"Imported deck '{deck.name}' must include at least one prompt")
            if len(deck.white_cards) < 3:
                raise ValueError(f"Imported deck '{deck.name}' must include at least three white cards")
            if deck.slug in seen_slugs:
                raise ValueError(f"Duplicate deck slug '{deck.slug}' in import file")
            seen_slugs.add(deck.slug)
            imported.append(deck)

        if mode == "replace":
            for path in self.deck_dir.glob("*.json"):
                try:
                    path.unlink()
                except OSError:
                    continue

        for deck in imported:
            path = self.deck_dir / f"{deck.slug}.json"
            path.write_text(json.dumps({
                "slug": deck.slug,
                "name": deck.name,
                "description": deck.description,
                "allow_free_text": deck.allow_free_text,
                "hand_size": deck.hand_size,
                "prompts": deck.prompts,
                "white_cards": deck.white_cards,
            }, indent=2), encoding="utf-8")

        await self.async_load()

    def _from_payload(self, payload: dict[str, Any], source: str) -> DeckDefinition:
        prompts = [str(item).strip() for item in payload.get('prompts', []) if str(item).strip()]
        white_cards = [str(item).strip() for item in payload.get('white_cards', []) if str(item).strip()]
        if not prompts:
            prompts = list(DEFAULT_PROMPTS)
        return DeckDefinition(
            slug=str(payload.get('slug') or payload.get('name') or source).strip().lower().replace(' ', '_'),
            name=str(payload.get('name') or payload.get('slug') or source),
            description=str(payload.get('description', '')),
            prompts=prompts,
            white_cards=white_cards,
            allow_free_text=bool(payload.get('allow_free_text', False)),
            hand_size=max(1, int(payload.get('hand_size', DEFAULT_HAND_SIZE))),
            source=source,
        )
