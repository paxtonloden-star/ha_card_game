"""Coordinator for HA Card Game."""

from __future__ import annotations

import asyncio
import logging
import secrets
import string
import time
from typing import Any
from copy import deepcopy

from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ADMIN_TOKEN_LENGTH, AI_QUEUE_MAX_ITEMS, CONF_AI_API_KEY, CONF_AI_ENABLED, CONF_AI_ENDPOINT, CONF_AI_MODEL, CONF_AI_USE_LOCAL_FALLBACK, CONF_ALLOW_REMOTE_PLAYERS, CONF_ALLOWED_TRIVIA_CATEGORIES, CONF_CONTENT_MODE, CONF_DEFAULT_GAME_MODE, CONF_DEFAULT_TRIVIA_SOURCE, CONF_MAX_ROUNDS, CONF_REMOTE_BASE_URL, CONF_REQUIRE_AI_APPROVAL, DEFAULT_AUTO_ADVANCE_ENABLED, DEFAULT_AUTO_ADVANCE_SECONDS, DEFAULT_DECK, DEFAULT_FLIP_STYLE, DEFAULT_PARENTAL_CONTROLS, DEFAULT_REMOTE_BASE_URL, DEFAULT_REVEAL_DURATION_MS, DEFAULT_REVEAL_SOUND, DEFAULT_SUBMISSION_REVEAL_ENABLED, DEFAULT_SUBMISSION_REVEAL_STEP_MS, DEFAULT_TICK_SOUND_PACK, DEFAULT_THEME_PRESET, DOMAIN, JOIN_CODE_LENGTH, PLAYER_TOKEN_LENGTH, STORAGE_KEY, STORAGE_VERSION, WS_EVENT_STATE, GAME_MODE_CARDS, GAME_MODE_TRIVIA, TRIVIA_DIFFICULTY_BY_AGE, TRIVIA_CATEGORIES
from .deck_manager import DeckManager
from .game_engine import CardGameEngine, GameState, Player
from .ai_generator import AIGenerator, AISettings
from .trivia_manager import TriviaSession, get_curated_trivia_questions
from .moderation import moderate_deck_payload, moderate_trivia_questions, normalize_parental_settings

_LOGGER = logging.getLogger(__name__)
_ALPHABET = string.ascii_uppercase + string.digits


class CardGameCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Keep a single authoritative game state."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.engine = CardGameEngine()
        self.deck_manager = DeckManager(hass)
        self.store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data = self.engine.state.as_dict()
        self.join_code = self._generate_join_code()
        self.admin_token = self._generate_token(ADMIN_TOKEN_LENGTH)
        self.player_tokens: dict[str, str] = {}
        self.base_url = ""
        self._sockets: set[web.WebSocketResponse] = set()
        self._auto_advance_task: asyncio.Task | None = None
        self.game_mode = GAME_MODE_CARDS
        self.ai_generator = AIGenerator(AISettings())
        self.trivia = TriviaSession()
        self.last_trivia_results = []
        self.remote_invites: dict[str, dict[str, str]] = {}
        self.trivia_team_mode = False
        self.last_trivia_results: list[dict[str, Any]] = []
        self.trivia_buzzer_mode = False
        self.trivia_buzz_bonus = 1
        self.trivia_steal_enabled = False
        self.trivia_buzz_owner: str | None = None
        self.trivia_buzz_team: str | None = None
        self.trivia_steal_active = False
        self.trivia_steal_team: str | None = None
        self.trivia_steal_from_player: str | None = None
        self.parental_controls = normalize_parental_settings(DEFAULT_PARENTAL_CONTROLS)
        self.ai_moderation_queue: list[dict[str, Any]] = []
        self.player_profiles: dict[str, dict[str, Any]] = {}
        self.scene_media_config: dict[str, Any] = {
            "enabled": False,
            "start_scene": "",
            "reveal_scene": "",
            "winner_scene": "",
            "media_player": "",
            "start_sound": "",
            "reveal_sound_media": "",
            "winner_sound": "",
            "volume_level": 0.55,
            "last_event": None,
        }
        self.tournament: dict[str, Any] = {
            "enabled": False,
            "name": "House Tournament",
            "target_score": 10,
            "history": [],
            "champion": None,
            "started_at": None,
            "completed_at": None,
        }
        self.custom_trivia_packs: dict[str, dict[str, Any]] = {}
        self.entry_options: dict[str, Any] = {}

    async def async_load(self) -> None:
        await self.deck_manager.async_load()
        self.deck_manager.write_example_decks()
        saved = await self.store.async_load()
        if saved:
            state = GameState(
                state=saved.get("state", "idle"),
                round_number=saved.get("round_number", 0),
                judge_index=saved.get("judge_index", 0),
                current_prompt=saved.get("current_prompt"),
                winner=saved.get("winner"),
                deck_name=saved.get("deck_name", DEFAULT_DECK),
                allow_free_text=saved.get("allow_free_text", False),
                hand_size=saved.get("hand_size", 7),
                players=[
                    Player(
                        name=item["name"],
                        score=item.get("score", 0),
                        submitted_card=item.get("submitted_card"),
                        hand=item.get("hand", []),
                        team=item.get("team", "Solo"),
                    )
                    for item in saved.get("players", [])
                ],
                prompts_remaining=saved.get("prompts_remaining", []),
                white_cards_remaining=saved.get("white_cards_remaining", []),
                reveal_order=saved.get("reveal_order", []),
                round_timer_duration=saved.get("round_timer_duration", 0),
                round_timer_ends_at=saved.get("round_timer_ends_at"),
                reveal_duration_ms=saved.get("reveal_duration_ms", DEFAULT_REVEAL_DURATION_MS),
                reveal_sound=saved.get("reveal_sound", DEFAULT_REVEAL_SOUND),
                auto_advance_enabled=saved.get("auto_advance_enabled", DEFAULT_AUTO_ADVANCE_ENABLED),
                auto_advance_seconds=saved.get("auto_advance_seconds", DEFAULT_AUTO_ADVANCE_SECONDS),
                submission_reveal_enabled=saved.get("submission_reveal_enabled", DEFAULT_SUBMISSION_REVEAL_ENABLED),
                submission_reveal_step_ms=saved.get("submission_reveal_step_ms", DEFAULT_SUBMISSION_REVEAL_STEP_MS),
                flip_style=saved.get("flip_style", DEFAULT_FLIP_STYLE),
                tick_sound_pack=saved.get("tick_sound_pack", DEFAULT_TICK_SOUND_PACK),
                theme_preset=saved.get("theme_preset", DEFAULT_THEME_PRESET),
                round_theme=saved.get("theme") or saved.get("round_theme") or {},
                winner_card=saved.get("winner_card"),
                winner_submission_id=saved.get("winner_submission_id"),
                custom_theme_presets=saved.get("custom_theme_presets", []),
            )
            self.engine._state = state
            self.join_code = saved.get("join_code") or self._generate_join_code()
            self.admin_token = saved.get("admin_token") or self._generate_token(ADMIN_TOKEN_LENGTH)
            self.player_tokens = saved.get("player_tokens", {})
            self.game_mode = saved.get("game_mode", GAME_MODE_CARDS)
            self.remote_invites = saved.get("remote_invites", {})
            self.parental_controls = normalize_parental_settings(saved.get("parental_controls", DEFAULT_PARENTAL_CONTROLS))
            self.ai_moderation_queue = list(saved.get("ai_moderation_queue", []))[:AI_QUEUE_MAX_ITEMS]
            self.player_profiles = dict(saved.get("player_profiles", {}))
            self.scene_media_config = {**self.scene_media_config, **dict(saved.get("scene_media_config", {}))}
            self.tournament = {**self.tournament, **dict(saved.get("tournament", {}))}
            self.custom_trivia_packs = dict(saved.get("custom_trivia_packs", {}))
            self.trivia_team_mode = bool(saved.get("trivia_team_mode", False))
            self.last_trivia_results = list(saved.get("last_trivia_results", []))
            self.trivia_buzzer_mode = bool(saved.get("trivia_buzzer_mode", False))
            self.trivia_buzz_bonus = max(0, int(saved.get("trivia_buzz_bonus", 1)))
            self.trivia_steal_enabled = bool(saved.get("trivia_steal_enabled", False))
            self.trivia_buzz_owner = saved.get("trivia_buzz_owner")
            self.trivia_buzz_team = saved.get("trivia_buzz_team")
            self.trivia_steal_active = bool(saved.get("trivia_steal_active", False))
            self.trivia_steal_team = saved.get("trivia_steal_team")
            self.trivia_steal_from_player = saved.get("trivia_steal_from_player")
            self.trivia.load_questions(saved.get("trivia_questions", []), category=saved.get("trivia_category", "fun_facts"), age_range=saved.get("trivia_age_range", "18_plus"), difficulty=saved.get("trivia_difficulty", "medium"), source=saved.get("trivia_source", "ai"))
            self.trivia.current_index = int(saved.get("trivia_current_index", -1))
            ai_saved = saved.get("ai_settings", {})
            self.ai_generator.update_settings(enabled=bool(ai_saved.get("enabled", False)), endpoint=ai_saved.get("endpoint") or self.ai_generator.settings.endpoint, model=ai_saved.get("model") or self.ai_generator.settings.model, use_local_fallback=bool(ai_saved.get("use_local_fallback", True)))
            if ai_saved.get("api_key"):
                self.ai_generator.update_settings(api_key=ai_saved.get("api_key"))
        self.engine.state.available_decks = self.deck_manager.list_decks()
        self.data = self.engine.state.as_dict()

    async def async_save(self) -> None:
        self.engine.state.available_decks = self.deck_manager.list_decks()
        self.data = self.engine.state.as_dict()
        payload = {
            **self.data,
            "join_code": self.join_code,
            "admin_token": self.admin_token,
            "player_tokens": self.player_tokens,
            "reveal_duration_ms": self.engine.state.reveal_duration_ms,
            "reveal_sound": self.engine.state.reveal_sound,
            "auto_advance_enabled": self.engine.state.auto_advance_enabled,
            "auto_advance_seconds": self.engine.state.auto_advance_seconds,
            "submission_reveal_enabled": self.engine.state.submission_reveal_enabled,
            "submission_reveal_step_ms": self.engine.state.submission_reveal_step_ms,
            "flip_style": self.engine.state.flip_style,
            "tick_sound_pack": self.engine.state.tick_sound_pack,
            "theme_preset": self.engine.state.theme_preset,
            "theme": self.engine.state.round_theme,
            "custom_theme_presets": list(self.engine.state.custom_theme_presets),
            "winner_card": self.engine.state.winner_card,
            "winner_submission_id": self.engine.state.winner_submission_id,
            "reveal_order": list(self.engine.state.reveal_order),
            "white_cards_remaining": list(self.engine.state.white_cards_remaining),
            "game_mode": self.game_mode,
            "ai_settings": {**self.ai_generator.settings.as_dict(), "api_key": self.ai_generator.settings.api_key},
            "remote_invites": self.remote_invites,
            "parental_controls": dict(self.parental_controls),
            "ai_moderation_queue": list(self.ai_moderation_queue)[:AI_QUEUE_MAX_ITEMS],
            "player_profiles": deepcopy(self.player_profiles),
            "scene_media_config": dict(self.scene_media_config),
            "tournament": deepcopy(self.tournament),
            "custom_trivia_packs": deepcopy(self.custom_trivia_packs),
            "trivia_questions": list(self.trivia.questions),
            "trivia_source": self.trivia.source,
            "trivia_current_index": self.trivia.current_index,
            "trivia_category": self.trivia.category,
            "trivia_age_range": self.trivia.age_range,
            "trivia_difficulty": self.trivia.difficulty,
            "trivia_team_mode": self.trivia_team_mode,
            "trivia_buzzer_mode": self.trivia_buzzer_mode,
            "trivia_buzz_bonus": self.trivia_buzz_bonus,
            "trivia_steal_enabled": self.trivia_steal_enabled,
            "trivia_buzz_owner": self.trivia_buzz_owner,
            "trivia_buzz_team": self.trivia_buzz_team,
            "trivia_steal_active": self.trivia_steal_active,
            "trivia_steal_team": self.trivia_steal_team,
            "trivia_steal_from_player": self.trivia_steal_from_player,
            "last_trivia_results": list(self.last_trivia_results),
            "players": [
                {
                    "name": player.name,
                    "score": player.score,
                    "submitted_card": player.submitted_card,
                    "hand": list(player.hand),
                    "team": player.team,
                }
                for player in self.engine.state.players
            ],
        }
        await self.store.async_save(payload)
        self.async_update_listeners()
        await self.async_broadcast_state()
        self._sync_auto_advance()

    async def async_refresh_from_engine(self) -> None:
        self._prune_tokens()
        await self.async_save()

    async def async_reset_lobby(self) -> None:
        self.engine.reset()
        self.engine.state.available_decks = self.deck_manager.list_decks()
        self.join_code = self._generate_join_code()
        self.admin_token = self._generate_token(ADMIN_TOKEN_LENGTH)
        self.player_tokens = {}
        self.remote_invites = {}
        self.game_mode = GAME_MODE_CARDS
        self.trivia = TriviaSession()
        self.last_trivia_results = []
        self._reset_trivia_buzzer_state()
        self.trivia_buzzer_mode = False
        self.trivia_buzz_bonus = 1
        self.trivia_steal_enabled = False
        self._clear_active_tournament_if_complete(reset_only=True)
        await self.async_refresh_from_engine()

    async def async_start_game(self, deck_name: str | None = None, game_mode: str | None = None) -> None:
        self.game_mode = game_mode or self.game_mode or GAME_MODE_CARDS
        if self.game_mode == GAME_MODE_TRIVIA:
            await self.async_start_trivia_round()
            return
        deck = self.deck_manager.get_deck(deck_name or self.engine.state.deck_name)
        self.engine.start_game(
            deck_name=deck.slug,
            prompts=list(deck.prompts),
            white_cards=list(deck.white_cards),
            allow_free_text=deck.allow_free_text,
            hand_size=deck.hand_size,
        )
        for player in self.engine.state.players:
            self._ensure_profile(player.name)["games_played"] += 1
        await self.async_trigger_scene_media_event("game_start")
        await self.async_refresh_from_engine()

    async def async_set_deck(self, deck_name: str) -> None:
        deck = self.deck_manager.get_deck(deck_name)
        self.engine.state.deck_name = deck.slug
        self.engine.state.allow_free_text = deck.allow_free_text
        self.engine.state.hand_size = deck.hand_size
        self.engine.state.available_decks = self.deck_manager.list_decks()
        await self.async_refresh_from_engine()

    async def async_reload_decks(self) -> None:
        await self.deck_manager.async_load()
        self.engine.state.available_decks = self.deck_manager.list_decks()
        await self.async_refresh_from_engine()

    async def async_join_player(self, player_name: str) -> dict[str, str]:
        player = self._find_player(player_name)
        if player is None:
            self.engine.add_player(player_name)
            player_name = player_name.strip()
            assigned_team = self._default_team_for_new_player()
            created_player = self._find_player(player_name)
            if created_player is not None:
                created_player.team = assigned_team
        self._ensure_profile(player_name)
        token = self.player_tokens.get(player_name) or self._generate_token(PLAYER_TOKEN_LENGTH)
        self.player_tokens[player_name] = token
        await self.async_refresh_from_engine()
        return {"player_name": player_name, "session_token": token, "join_code": self.join_code}

    async def async_submit_for_token(self, token: str, card_text: str) -> None:
        player_name = self.player_name_for_token(token)
        if self.game_mode == GAME_MODE_TRIVIA and self.engine.state.state == "submitting":
            if self.trivia_buzzer_mode:
                if not self.trivia_buzz_owner:
                    raise ValueError("Buzz in first before answering")
                if self.trivia_steal_active:
                    if not self._can_player_answer_trivia(player_name):
                        raise ValueError("Only the steal team can answer right now")
                elif player_name != self.trivia_buzz_owner:
                    raise ValueError("Only the buzz owner can answer right now")
        self.engine.submit_card(player_name, card_text)
        if self.game_mode == GAME_MODE_TRIVIA and self.engine.state.state == "submitting":
            if self.trivia_buzzer_mode:
                result = await self.async_grade_trivia_round()
                if result.get("steal_available"):
                    return
                return
            active_players = [player for player in self.engine.state.players]
            if active_players and all((player.submitted_card or "").strip() for player in active_players):
                await self.async_grade_trivia_round()
                return
        await self.async_refresh_from_engine()

    async def async_pick_submission_for_token(self, token: str, submission_id: str) -> None:
        player_name = self.player_name_for_token(token)
        if self.engine.state.current_judge != player_name:
            raise ValueError("Only the current judge can pick the winner")
        self.engine.pick_winner_submission(submission_id)
        self._record_card_round_winner(self.engine.state.winner)
        self._update_tournament_progress(self.engine.state.winner)
        await self.async_trigger_scene_media_event("winner", self.engine.state.winner)
        await self.async_refresh_from_engine()


    async def async_buzz_for_token(self, token: str) -> dict[str, Any]:
        if self.game_mode != GAME_MODE_TRIVIA or self.engine.state.state != "submitting":
            raise ValueError("Trivia buzzer is not active")
        if not self.trivia_buzzer_mode:
            raise ValueError("Buzzer mode is disabled")
        player_name = self.player_name_for_token(token)
        if not self._can_player_buzz(player_name):
            if self.trivia_steal_active and self.trivia_steal_team:
                raise ValueError(f"Only {self.trivia_steal_team} can buzz for the steal")
            raise ValueError("Another player already has control of this question")
        self.trivia_buzz_owner = player_name
        player = self._find_player(player_name)
        self.trivia_buzz_team = player.team if player else None
        self._ensure_profile(player_name)["buzzes"] += 1
        await self.async_refresh_from_engine()
        return {"buzz_owner": self.trivia_buzz_owner, "buzz_team": self.trivia_buzz_team, "steal_active": self.trivia_steal_active}

    async def async_remove_player(self, player_name: str) -> None:
        self.engine.remove_player(player_name)
        await self.async_refresh_from_engine()

    async def async_set_reveal_config(self, duration_ms: int | None = None, sound: str | None = None, auto_advance_enabled: bool | None = None, auto_advance_seconds: int | None = None, submission_reveal_enabled: bool | None = None, submission_reveal_step_ms: int | None = None, flip_style: str | None = None, tick_sound_pack: str | None = None, theme_preset: str | None = None) -> None:
        self.engine.set_reveal_config(
            duration_ms=duration_ms,
            sound=sound,
            auto_advance_enabled=auto_advance_enabled,
            auto_advance_seconds=auto_advance_seconds,
            submission_reveal_enabled=submission_reveal_enabled,
            submission_reveal_step_ms=submission_reveal_step_ms,
            flip_style=flip_style,
            tick_sound_pack=tick_sound_pack,
            theme_preset=theme_preset,
        )
        await self.async_refresh_from_engine()

    async def async_save_custom_theme_preset(self, name: str, description: str = "") -> None:
        self.engine.save_custom_theme_preset(name, description)
        await self.async_refresh_from_engine()

    async def async_delete_custom_theme_preset(self, preset_slug: str) -> None:
        self.engine.delete_custom_theme_preset(preset_slug)
        await self.async_refresh_from_engine()


    async def async_export_theme_presets(self, include_builtin: bool = False) -> dict[str, Any]:
        return self.engine.export_theme_presets(include_builtin=include_builtin)

    async def async_import_theme_presets(self, payload: dict[str, Any], mode: str = "merge") -> None:
        self.engine.import_theme_presets(payload, mode=mode)
        await self.async_refresh_from_engine()


    async def async_export_decks(self, include_builtin: bool = False) -> dict[str, Any]:
        return self.deck_manager.export_decks(include_builtin=include_builtin)

    async def async_import_decks(self, payload: dict[str, Any], mode: str = "merge") -> None:
        await self.deck_manager.async_import_decks(payload, mode=mode)
        self.engine.state.available_decks = self.deck_manager.list_decks()
        if self.engine.state.deck_name not in {deck["slug"] for deck in self.engine.state.available_decks}:
            fallback = self.deck_manager.get_deck(None)
            self.engine.state.deck_name = fallback.slug
            self.engine.state.allow_free_text = fallback.allow_free_text
            self.engine.state.hand_size = fallback.hand_size
        await self.async_refresh_from_engine()

    async def async_set_round_timer(self, seconds: int) -> None:
        if seconds < 0:
            raise ValueError("Timer seconds must be 0 or greater")
        if seconds == 0:
            self.engine.clear_round_timer()
        else:
            self.engine.set_round_timer(seconds, time.time() + seconds)
        await self.async_refresh_from_engine()

    def player_name_for_token(self, token: str) -> str:
        for player_name, player_token in self.player_tokens.items():
            if secrets.compare_digest(player_token, token):
                return player_name
        raise ValueError("Invalid player session")

    def player_state(self, token: str | None) -> dict[str, Any]:
        player_name = None
        if token:
            try:
                player_name = self.player_name_for_token(token)
            except ValueError:
                player_name = None

        state = self.data.copy()
        state["join_code"] = self.join_code
        state["game_mode"] = self.game_mode
        state["trivia"] = {
            **self.trivia.as_dict(),
            "team_mode": self.trivia_team_mode,
            "results": list(self.last_trivia_results),
            "team_leaderboard": list(self.engine.state.team_leaderboard),
            "buzzer_mode": self.trivia_buzzer_mode,
            "buzz_bonus": self.trivia_buzz_bonus,
            "steal_enabled": self.trivia_steal_enabled,
            "buzz_owner": self.trivia_buzz_owner,
            "buzz_team": self.trivia_buzz_team,
            "steal_active": self.trivia_steal_active,
            "steal_team": self.trivia_steal_team,
            "steal_from_player": self.trivia_steal_from_player,
            "source_options": ["ai", "offline_curated"],
            "offline_pack_categories": self._available_offline_trivia_categories(),
            "custom_packs": self._custom_trivia_pack_summaries(),
        }
        state["remote_join_url"] = self.join_url
        state["remote_enabled"] = bool(self.base_url)
        state["ai"] = self.ai_generator.settings.as_dict()
        state["profiles"] = self._profiles_summary()
        state["scene_media"] = dict(self.scene_media_config)
        state["tournament"] = self._tournament_state()
        state["parental_controls"] = dict(self.parental_controls)
        state["ai_moderation_queue"] = [
            {
                "id": item.get("id"),
                "kind": item.get("kind"),
                "name": item.get("name"),
                "summary": item.get("summary"),
                "created_at": item.get("created_at"),
                "content_mode": item.get("content_mode"),
                "issue_count": len(item.get("moderation_issues", [])),
            }
            for item in self.ai_moderation_queue
        ]
        state["join_url"] = self.join_url
        state["qr_url"] = f"/api/{DOMAIN}/join_qr.svg"
        state["player_name"] = player_name
        state["is_joined"] = player_name is not None
        state["is_judge"] = player_name is not None and player_name == self.engine.state.current_judge
        state["has_submitted"] = False
        state["hand"] = []
        state["team"] = None
        state["team_score"] = None
        if player_name:
            for player in self.engine.state.players:
                if player.name == player_name:
                    state["has_submitted"] = bool(player.submitted_card)
                    state["hand"] = list(player.hand)
                    state["team"] = player.team
                    team_scores = {item["name"]: item["score"] for item in self.engine.state.team_leaderboard}
                    state["team_score"] = team_scores.get(player.team, 0)
                    break
        return state

    async def async_set_parental_controls(self, *, enabled: bool | None = None, content_mode: str | None = None, require_ai_approval: bool | None = None, allow_remote_players: bool | None = None, allowed_trivia_categories: list[str] | None = None) -> None:
        settings = dict(self.parental_controls)
        if enabled is not None:
            settings["enabled"] = bool(enabled)
        if content_mode is not None:
            settings["content_mode"] = str(content_mode).strip().lower()
        if require_ai_approval is not None:
            settings["require_ai_approval"] = bool(require_ai_approval)
        if allow_remote_players is not None:
            settings["allow_remote_players"] = bool(allow_remote_players)
        if allowed_trivia_categories is not None:
            settings["allowed_trivia_categories"] = list(allowed_trivia_categories)
        self.parental_controls = normalize_parental_settings(settings)
        await self.async_refresh_from_engine()

    def _queue_ai_item(self, kind: str, name: str, payload: dict[str, Any], summary: str, moderation_issues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        item = {
            "id": self._generate_token(12),
            "kind": kind,
            "name": name,
            "payload": payload,
            "summary": summary,
            "created_at": int(time.time()),
            "content_mode": self.parental_controls.get("content_mode", "family_safe"),
            "moderation_issues": list(moderation_issues or []),
        }
        self.ai_moderation_queue = ([item] + list(self.ai_moderation_queue))[:AI_QUEUE_MAX_ITEMS]
        return item

    async def async_approve_ai_queue_item(self, item_id: str) -> dict[str, Any]:
        for index, item in enumerate(self.ai_moderation_queue):
            if item.get("id") != item_id:
                continue
            self.ai_moderation_queue.pop(index)
            payload = item.get("payload", {})
            if item.get("kind") == "deck":
                merge_slug = payload.get("merge_into_slug")
                if merge_slug:
                    deck = await self.deck_manager.async_extend_deck(merge_slug, prompts=payload.get("prompts", []), white_cards=payload.get("white_cards", []))
                else:
                    deck = await self.deck_manager.save_deck(payload, source="ai_approved")
                self.engine.state.available_decks = self.deck_manager.list_decks()
                await self.async_refresh_from_engine()
                return {"kind": "deck", "deck": deck.as_dict()}
            if item.get("kind") == "trivia":
                self.trivia.load_questions(payload.get("questions", []), category=payload.get("category", "fun_facts"), age_range=payload.get("age_range", "18_plus"), difficulty=payload.get("difficulty", "medium"), source=payload.get("source", "ai"))
                self.game_mode = GAME_MODE_TRIVIA
                self.last_trivia_results = []
                self._reset_trivia_buzzer_state()
                await self.async_refresh_from_engine()
                return {"kind": "trivia", "question_count": len(self.trivia.questions)}
            raise ValueError("Unknown AI moderation item type")
        raise ValueError("Unknown moderation queue item")

    async def async_reject_ai_queue_item(self, item_id: str) -> None:
        before = len(self.ai_moderation_queue)
        self.ai_moderation_queue = [item for item in self.ai_moderation_queue if item.get("id") != item_id]
        if len(self.ai_moderation_queue) == before:
            raise ValueError("Unknown moderation queue item")
        await self.async_refresh_from_engine()

    async def async_set_ai_settings(self, *, enabled: bool | None = None, endpoint: str | None = None, model: str | None = None, api_key: str | None = None, use_local_fallback: bool | None = None) -> None:
        self.ai_generator.update_settings(enabled=enabled, endpoint=endpoint, model=model, api_key=api_key, use_local_fallback=use_local_fallback)
        await self.async_refresh_from_engine()

    async def async_generate_ai_deck(self, *, theme: str, prompt_count: int = 12, white_count: int = 40, age_range: str = "18_plus", family_friendly: bool = True, merge_into_slug: str | None = None) -> dict[str, Any]:
        payload = await self.ai_generator.generate_pack(theme=theme, prompt_count=prompt_count, white_count=white_count, family_friendly=family_friendly, age_range=age_range)
        moderation = moderate_deck_payload(payload, content_mode=self.parental_controls.get("content_mode", "family_safe")) if self.parental_controls.get("enabled") else payload
        cleaned_payload = dict(moderation)
        moderation_meta = cleaned_payload.pop("moderation", {"issues": []})
        cleaned_payload["allow_free_text"] = payload.get("allow_free_text", True)
        cleaned_payload["hand_size"] = payload.get("hand_size", 7)
        if len(cleaned_payload.get("prompts", [])) < 1 or len(cleaned_payload.get("white_cards", [])) < 3:
            raise ValueError("AI content was filtered by parental controls and no longer has enough cards to save")
        if self.parental_controls.get("enabled") and self.parental_controls.get("require_ai_approval"):
            queued = self._queue_ai_item(
                "deck",
                cleaned_payload.get("name") or theme,
                {**cleaned_payload, "merge_into_slug": merge_into_slug},
                f"{len(cleaned_payload.get('prompts', []))} prompts, {len(cleaned_payload.get('white_cards', []))} white cards",
                moderation_meta.get("issues", []),
            )
            await self.async_refresh_from_engine()
            return {"queued": True, "queue_id": queued["id"], "name": queued["name"], "summary": queued["summary"]}
        if merge_into_slug:
            deck = await self.deck_manager.async_extend_deck(merge_into_slug, prompts=cleaned_payload.get("prompts", []), white_cards=cleaned_payload.get("white_cards", []))
        else:
            deck = await self.deck_manager.save_deck(cleaned_payload, source="ai")
        self.engine.state.available_decks = self.deck_manager.list_decks()
        await self.async_refresh_from_engine()
        return deck.as_dict()

    async def async_prepare_trivia(self, *, category: str, age_range: str, difficulty: str | None = None, question_count: int = 10, source: str = "ai") -> None:
        difficulty = difficulty or TRIVIA_DIFFICULTY_BY_AGE.get(age_range, "medium")
        if self.parental_controls.get("enabled"):
            allowed_categories = set(self.parental_controls.get("allowed_trivia_categories", []))
            if category not in allowed_categories and category not in self.custom_trivia_packs:
                raise ValueError("That trivia category is blocked by parental controls")
        source = (source or "ai").strip().lower()
        if source == "offline_curated":
            if category in self.custom_trivia_packs:
                questions = self._get_custom_trivia_questions(category=category, age_range=age_range, difficulty=difficulty, question_count=question_count)
            else:
                questions = get_curated_trivia_questions(category=category, age_range=age_range, difficulty=difficulty, question_count=question_count)
        else:
            questions = await self.ai_generator.generate_trivia(category=category, age_range=age_range, difficulty=difficulty, question_count=question_count)
        moderation_issues: list[dict[str, Any]] = []
        if self.parental_controls.get("enabled"):
            questions, moderation_issues = moderate_trivia_questions(questions, content_mode=self.parental_controls.get("content_mode", "family_safe"))
        if not questions:
            raise ValueError("AI trivia was filtered by parental controls and no usable questions remain")
        if source != "offline_curated" and self.parental_controls.get("enabled") and self.parental_controls.get("require_ai_approval"):
            self._queue_ai_item("trivia", f"{category.title()} trivia", {"questions": questions, "category": category, "age_range": age_range, "difficulty": difficulty}, f"{len(questions)} questions in {category}", moderation_issues)
            await self.async_refresh_from_engine()
            return
        self.trivia.load_questions(questions, category=category, age_range=age_range, difficulty=difficulty, source=source)
        self.game_mode = GAME_MODE_TRIVIA
        self.last_trivia_results = []
        self._reset_trivia_buzzer_state()
        await self.async_refresh_from_engine()

    async def async_start_trivia_round(self) -> None:
        q = self.trivia.next_question()
        self.game_mode = GAME_MODE_TRIVIA
        self.engine.state.round_number += 1
        self.engine.state.state = "submitting"
        self.engine.state.current_prompt = q.get("question")
        self.engine.state.allow_free_text = True
        self.engine.state.winner = None
        self.engine.state.winner_card = None
        self.engine.state.winner_submission_id = None
        self.engine.state.reveal_order = []
        self.engine.clear_round_timer()
        self.last_trivia_results = []
        self._reset_trivia_buzzer_state()
        for player in self.engine.state.players:
            player.submitted_card = None
        await self.async_refresh_from_engine()

    async def async_grade_trivia_round(self) -> dict[str, Any]:
        if self.game_mode != GAME_MODE_TRIVIA or not self.trivia.current_question:
            raise ValueError("Trivia mode is not active")

        q = self.trivia.current_question
        reveal_order: list[str] = []
        results: list[dict[str, Any]] = []
        correct_players: list[str] = []
        steal_available = False

        if self.trivia_buzzer_mode:
            answerer_names: list[str] = []
            if self.trivia_steal_active:
                answerer_names = [player.name for player in self.engine.state.players if player.submitted_card and self._player_matches_steal_window(player.name)]
            elif self.trivia_buzz_owner:
                owner = self._find_player(self.trivia_buzz_owner)
                if owner and owner.submitted_card:
                    answerer_names = [owner.name]
            if not answerer_names:
                raise ValueError("No buzz answer has been submitted yet")
            for player_name in answerer_names:
                player = self._find_player(player_name)
                if player is None or not player.submitted_card:
                    continue
                reveal_order.append(player.name)
                is_correct = self.trivia.grade(player.submitted_card)
                awarded = 0
                if is_correct:
                    awarded = 1 + max(0, int(self.trivia_buzz_bonus or 0))
                    player.score += awarded
                    correct_players.append(player.name)
                results.append({
                    "player": player.name,
                    "team": player.team,
                    "answer": player.submitted_card,
                    "correct": is_correct,
                    "buzz_owner": player.name == self.trivia_buzz_owner,
                    "steal_attempt": self.trivia_steal_active,
                    "points_awarded": awarded,
                })
                if (not is_correct) and self.trivia_steal_enabled and (not self.trivia_steal_active):
                    steal_available = self._activate_trivia_steal(player)
            if steal_available:
                self.last_trivia_results = results
                self.engine.state.reveal_order = []
                await self.async_refresh_from_engine()
                return {
                    "correct_players": [],
                    "correct_answer": q.get("correct_answer"),
                    "explanation": q.get("explanation", ""),
                    "steal_available": True,
                    "steal_team": self.trivia_steal_team,
                }
        else:
            for player in self.engine.state.players:
                if player.submitted_card:
                    reveal_order.append(player.name)
                    is_correct = self.trivia.grade(player.submitted_card)
                    if is_correct:
                        player.score += 1
                        correct_players.append(player.name)
                    results.append({"player": player.name, "team": player.team, "answer": player.submitted_card, "correct": is_correct, "points_awarded": 1 if is_correct else 0})

        self.engine.state.reveal_order = reveal_order
        self.engine.state.state = "results"
        self.last_trivia_results = results
        if self.trivia_team_mode:
            round_team_scores: dict[str, int] = {}
            for item in results:
                if item["correct"]:
                    round_team_scores[item["team"]] = round_team_scores.get(item["team"], 0) + int(item.get("points_awarded", 1))
            if round_team_scores:
                best_team = max(sorted(round_team_scores), key=lambda name: round_team_scores[name])
                self.engine.state.winner = f"{best_team} leads this round"
            else:
                self.engine.state.winner = "No correct answers"
        else:
            self.engine.state.winner = ", ".join(correct_players) if correct_players else "No correct answers"
        self.engine.state.winner_card = q.get("correct_answer")
        self.engine.state.winner_submission_id = None
        self._record_trivia_results_in_profiles(results)
        self._update_tournament_progress(self.engine.state.winner)
        self._reset_trivia_buzzer_state()
        await self.async_trigger_scene_media_event("winner", self.engine.state.winner)
        await self.async_refresh_from_engine()
        return {"correct_players": correct_players, "correct_answer": q.get("correct_answer"), "explanation": q.get("explanation", ""), "steal_available": False}



    async def async_set_trivia_settings(self, *, team_mode: bool | None = None, buzzer_mode: bool | None = None, buzz_bonus: int | None = None, steal_enabled: bool | None = None) -> None:
        if team_mode is not None:
            self.trivia_team_mode = bool(team_mode)
            if self.trivia_team_mode:
                for index, player in enumerate(self.engine.state.players):
                    player.team = "Team A" if index % 2 == 0 else "Team B"
            else:
                for player in self.engine.state.players:
                    player.team = "Solo"
        if buzzer_mode is not None:
            self.trivia_buzzer_mode = bool(buzzer_mode)
        if buzz_bonus is not None:
            self.trivia_buzz_bonus = max(0, int(buzz_bonus))
        if steal_enabled is not None:
            self.trivia_steal_enabled = bool(steal_enabled)
        self._reset_trivia_buzzer_state()
        await self.async_refresh_from_engine()

    async def async_assign_player_team(self, player_name: str, team_name: str) -> None:
        player = self._find_player(player_name)
        if player is None:
            raise ValueError("Unknown player")
        team_name = (team_name or "").strip()
        if not team_name:
            raise ValueError("Team name is required")
        player.team = team_name
        await self.async_refresh_from_engine()

    async def async_create_remote_invite(self, player_name: str) -> dict[str, str]:
        joined = await self.async_join_player(player_name)
        url = f"{self.join_url}&name={player_name.replace(' ', '%20')}&token={joined['session_token']}"
        self.remote_invites[player_name] = {"player_name": player_name, "url": url, "session_token": joined["session_token"]}
        await self.async_refresh_from_engine()
        return {"player_name": player_name, "url": url}

    async def async_set_scene_media_config(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if value is None or key not in self.scene_media_config:
                continue
            self.scene_media_config[key] = value
        if "volume_level" in self.scene_media_config:
            try:
                self.scene_media_config["volume_level"] = max(0.0, min(1.0, float(self.scene_media_config["volume_level"])))
            except Exception:
                self.scene_media_config["volume_level"] = 0.55
        await self.async_refresh_from_engine()

    async def async_trigger_scene_media_event(self, event_name: str, winner: str | None = None) -> None:
        self.scene_media_config["last_event"] = {"event": event_name, "winner": winner, "at": int(time.time())}
        services = getattr(self.hass, "services", None)
        if not services or not self.scene_media_config.get("enabled"):
            await self.async_refresh_from_engine()
            return
        event_map = {
            "game_start": self.scene_media_config.get("start_scene"),
            "reveal": self.scene_media_config.get("reveal_scene"),
            "winner": self.scene_media_config.get("winner_scene"),
        }
        scene_entity = event_map.get(event_name) or ""
        media_player = self.scene_media_config.get("media_player") or ""
        sound_map = {
            "game_start": self.scene_media_config.get("start_sound"),
            "reveal": self.scene_media_config.get("reveal_sound_media"),
            "winner": self.scene_media_config.get("winner_sound"),
        }
        media_content_id = sound_map.get(event_name) or ""
        if scene_entity and hasattr(services, "async_call"):
            try:
                await services.async_call("scene", "turn_on", {"entity_id": scene_entity}, blocking=False)
            except Exception:
                pass
        if media_player and media_content_id and hasattr(services, "async_call"):
            try:
                await services.async_call("media_player", "volume_set", {"entity_id": media_player, "volume_level": self.scene_media_config.get("volume_level", 0.55)}, blocking=False)
                await services.async_call("media_player", "play_media", {"entity_id": media_player, "media_content_id": media_content_id, "media_content_type": "music"}, blocking=False)
            except Exception:
                pass
        await self.async_refresh_from_engine()

    async def async_start_tournament(self, name: str = "House Tournament", target_score: int = 10, reset_scores: bool = True) -> None:
        self.tournament = {
            "enabled": True,
            "name": (name or "House Tournament").strip(),
            "target_score": max(1, int(target_score)),
            "history": [],
            "champion": None,
            "started_at": int(time.time()),
            "completed_at": None,
        }
        if reset_scores:
            for player in self.engine.state.players:
                player.score = 0
        self._ensure_profiles_for_players()
        await self.async_refresh_from_engine()

    async def async_end_tournament(self) -> None:
        self._clear_active_tournament_if_complete(force=True)
        await self.async_refresh_from_engine()

    async def async_update_profile(self, player_name: str, updates: dict[str, Any]) -> dict[str, Any]:
        profile = self._ensure_profile(player_name)
        allowed_int_fields = {"games_played", "card_round_wins", "trivia_correct", "trivia_answered", "buzzes", "steal_wins", "tournament_wins", "total_points"}
        for field in allowed_int_fields:
            if field in updates and updates[field] is not None:
                profile[field] = max(0, int(updates[field]))
        if updates.get("last_seen") is not None:
            profile["last_seen"] = max(0, int(updates["last_seen"]))
        await self.async_refresh_from_engine()
        return {"name": player_name, **profile}

    async def async_reset_profile(self, player_name: str) -> None:
        if player_name not in self.player_profiles:
            raise ValueError("Unknown profile")
        self.player_profiles.pop(player_name, None)
        self._ensure_profile(player_name)
        await self.async_refresh_from_engine()

    async def async_delete_profile(self, player_name: str) -> None:
        if player_name not in self.player_profiles:
            raise ValueError("Unknown profile")
        self.player_profiles.pop(player_name, None)
        await self.async_refresh_from_engine()

    async def async_update_tournament_settings(self, *, name: str | None = None, target_score: int | None = None, enabled: bool | None = None) -> None:
        if name is not None:
            clean_name = str(name).strip() or "House Tournament"
            self.tournament["name"] = clean_name
        if target_score is not None:
            self.tournament["target_score"] = max(1, int(target_score))
        if enabled is not None:
            self.tournament["enabled"] = bool(enabled)
            if enabled and not self.tournament.get("started_at"):
                self.tournament["started_at"] = int(time.time())
            if not enabled and not self.tournament.get("completed_at"):
                self.tournament["completed_at"] = int(time.time())
        await self.async_refresh_from_engine()

    async def async_clear_tournament_history(self) -> None:
        self.tournament["history"] = []
        self.tournament["champion"] = None
        self.tournament["completed_at"] = None
        await self.async_refresh_from_engine()

    async def async_save_custom_trivia_pack(self, *, slug: str, name: str, questions: list[dict[str, Any]], description: str = "") -> dict[str, Any]:
        clean_slug = self._slugify_pack_name(slug or name)
        if not clean_slug:
            raise ValueError("Trivia pack name is required")
        normalized_questions = self._normalize_custom_trivia_questions(questions, category=clean_slug)
        if len(normalized_questions) < 1:
            raise ValueError("Trivia pack must contain at least one valid question")
        pack = {
            "slug": clean_slug,
            "name": (name or clean_slug.replace("_", " ").title()).strip(),
            "description": (description or "").strip(),
            "question_count": len(normalized_questions),
            "updated_at": int(time.time()),
            "questions": normalized_questions,
        }
        self.custom_trivia_packs[clean_slug] = pack
        await self.async_refresh_from_engine()
        return {k: v for k, v in pack.items() if k != "questions"}

    async def async_delete_custom_trivia_pack(self, slug: str) -> None:
        clean_slug = self._slugify_pack_name(slug)
        if clean_slug not in self.custom_trivia_packs:
            raise ValueError("Unknown trivia pack")
        self.custom_trivia_packs.pop(clean_slug, None)
        await self.async_refresh_from_engine()

    @property
    def join_url(self) -> str:
        if not self.base_url:
            return f"/local/{DOMAIN}/index.html?join={self.join_code}"
        return f"{self.base_url}/local/{DOMAIN}/index.html?join={self.join_code}"

    async def async_register_socket(self, ws: web.WebSocketResponse) -> None:
        self._sockets.add(ws)
        await ws.send_json({"event": WS_EVENT_STATE, "state": self.player_state(None)})

    async def async_unregister_socket(self, ws: web.WebSocketResponse) -> None:
        self._sockets.discard(ws)

    async def async_broadcast_state(self) -> None:
        if not self._sockets:
            return
        to_remove: list[web.WebSocketResponse] = []
        for ws in self._sockets:
            if ws.closed:
                to_remove.append(ws)
                continue
            try:
                await ws.send_json({"event": WS_EVENT_STATE, "state": self.player_state(None)})
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            self._sockets.discard(ws)

    def _available_offline_trivia_categories(self) -> list[str]:
        categories = list(TRIVIA_CATEGORIES)
        for slug in sorted(self.custom_trivia_packs):
            if slug not in categories:
                categories.append(slug)
        return categories

    def _custom_trivia_pack_summaries(self) -> list[dict[str, Any]]:
        packs = []
        for slug, pack in self.custom_trivia_packs.items():
            packs.append({
                "slug": slug,
                "name": pack.get("name", slug.replace("_", " ").title()),
                "description": pack.get("description", ""),
                "question_count": int(pack.get("question_count", len(pack.get("questions", [])))),
                "updated_at": pack.get("updated_at"),
                "questions": list(pack.get("questions", [])),
            })
        packs.sort(key=lambda item: item["name"].lower())
        return packs

    def _slugify_pack_name(self, value: str) -> str:
        clean = "".join(ch.lower() if ch.isalnum() else "_" for ch in (value or "").strip())
        while "__" in clean:
            clean = clean.replace("__", "_")
        return clean.strip("_")[:64]

    def _normalize_custom_trivia_questions(self, questions: list[dict[str, Any]], *, category: str) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in questions or []:
            question = str(item.get("question") or "").strip()
            correct_answer = str(item.get("correct_answer") or "").strip()
            if not question or not correct_answer:
                continue
            choices = [str(x).strip() for x in item.get("choices", []) if str(x).strip()]
            accepted_answers = [str(x).strip() for x in item.get("accepted_answers", []) if str(x).strip()]
            if correct_answer not in accepted_answers:
                accepted_answers.insert(0, correct_answer)
            difficulty = str(item.get("difficulty") or "medium").strip().lower()
            if difficulty not in {"easy", "medium", "hard", "easy_medium", "medium_hard"}:
                difficulty = "medium"
            age_range = str(item.get("age_range") or "18_plus").strip()
            normalized.append({
                "question": question,
                "correct_answer": correct_answer,
                "accepted_answers": accepted_answers,
                "choices": choices[:6],
                "explanation": str(item.get("explanation") or "").strip(),
                "category": category,
                "age_range": age_range,
                "difficulty": difficulty,
                "source": "custom_curated",
            })
        return normalized

    def _get_custom_trivia_questions(self, *, category: str, age_range: str, difficulty: str, question_count: int) -> list[dict[str, Any]]:
        pack = self.custom_trivia_packs.get(category, {})
        source = [dict(item) for item in pack.get("questions", [])]
        if not source:
            raise ValueError("That custom trivia pack has no questions")
        wanted_levels = {difficulty}
        if difficulty in {"easy_medium", "medium_hard"}:
            wanted_levels = set(difficulty.split("_"))
        filtered = [item for item in source if item.get("difficulty", "medium") in wanted_levels]
        if not filtered:
            filtered = source
        exact_age = [item for item in filtered if item.get("age_range") in {age_range, "all", "any", ""}]
        if exact_age:
            filtered = exact_age
        results: list[dict[str, Any]] = []
        while len(results) < max(1, question_count):
            for item in filtered:
                copy = dict(item)
                copy["category"] = category
                results.append(copy)
                if len(results) >= question_count:
                    break
        return results[:question_count]

    def _profiles_summary(self) -> list[dict[str, Any]]:
        summaries = []
        for name, profile in self.player_profiles.items():
            summaries.append({
                "name": name,
                **profile,
                "accuracy": round((profile.get("trivia_correct", 0) / profile.get("trivia_answered", 1)) * 100, 1) if profile.get("trivia_answered", 0) else 0.0,
            })
        return sorted(summaries, key=lambda item: (-int(item.get("total_points", 0)), item["name"].lower()))

    def _tournament_state(self) -> dict[str, Any]:
        standings = [{"name": p.name, "score": p.score, "team": p.team} for p in self.engine.state.players]
        standings.sort(key=lambda item: (-item["score"], item["name"].lower()))
        return {**self.tournament, "standings": standings}

    def _ensure_profile(self, player_name: str) -> dict[str, Any]:
        key = player_name.strip()
        if key not in self.player_profiles:
            self.player_profiles[key] = {
                "games_played": 0,
                "card_round_wins": 0,
                "trivia_correct": 0,
                "trivia_answered": 0,
                "buzzes": 0,
                "steal_wins": 0,
                "tournament_wins": 0,
                "total_points": 0,
                "last_seen": int(time.time()),
            }
        self.player_profiles[key]["last_seen"] = int(time.time())
        return self.player_profiles[key]

    def _ensure_profiles_for_players(self) -> None:
        for player in self.engine.state.players:
            self._ensure_profile(player.name)

    def _record_card_round_winner(self, winner_name: str | None) -> None:
        if not winner_name:
            return
        profile = self._ensure_profile(winner_name)
        profile["card_round_wins"] += 1

    def _record_trivia_results_in_profiles(self, results: list[dict[str, Any]]) -> None:
        for item in results:
            profile = self._ensure_profile(item.get("player", ""))
            if not item.get("player"):
                continue
            profile["trivia_answered"] += 1
            if item.get("correct"):
                profile["trivia_correct"] += 1
            if item.get("steal_attempt") and item.get("correct"):
                profile["steal_wins"] += 1

    def _refresh_profile_totals(self) -> None:
        self._ensure_profiles_for_players()
        score_map = {player.name: int(player.score) for player in self.engine.state.players}
        for name, profile in self.player_profiles.items():
            if name in score_map:
                profile["total_points"] = score_map[name]

    def _update_tournament_progress(self, winner_name: str | None = None) -> None:
        self._refresh_profile_totals()
        if not self.tournament.get("enabled"):
            return
        entry = {
            "at": int(time.time()),
            "mode": self.game_mode,
            "round_number": self.engine.state.round_number,
            "winner": winner_name or self.engine.state.winner,
            "scoreboard": [{"name": p.name, "score": p.score} for p in self.engine.state.players],
        }
        history = list(self.tournament.get("history", []))
        history.append(entry)
        self.tournament["history"] = history[-100:]
        standings = sorted(self.engine.state.players, key=lambda p: (-p.score, p.name.lower()))
        if standings and standings[0].score >= int(self.tournament.get("target_score", 10)):
            top_score = standings[0].score
            leaders = [p for p in standings if p.score == top_score]
            if len(leaders) == 1:
                champion = leaders[0].name
                self.tournament["champion"] = champion
                self.tournament["completed_at"] = int(time.time())
                self.tournament["enabled"] = False
                self._ensure_profile(champion)["tournament_wins"] += 1

    def _clear_active_tournament_if_complete(self, force: bool = False, reset_only: bool = False) -> None:
        if force or self.tournament.get("champion"):
            self.tournament["enabled"] = False
            if force:
                self.tournament["completed_at"] = int(time.time())
        if reset_only:
            self.tournament["champion"] = None
            self.tournament["history"] = []
            self.tournament["completed_at"] = None

    def _sync_auto_advance(self) -> None:
        state = self.engine.state
        if state.state == "results" and state.winner and state.auto_advance_enabled and state.auto_advance_seconds > 0:
            if self._auto_advance_task is None or self._auto_advance_task.done():
                self._auto_advance_task = self.hass.async_create_task(self._async_auto_advance_after_delay(state.round_number, state.winner, state.auto_advance_seconds))
        elif self._auto_advance_task and not self._auto_advance_task.done():
            self._auto_advance_task.cancel()
            self._auto_advance_task = None

    async def _async_auto_advance_after_delay(self, round_number: int, winner: str, seconds: int) -> None:
        try:
            await asyncio.sleep(seconds)
            state = self.engine.state
            if state.state == "results" and state.round_number == round_number and state.winner == winner:
                self.engine.next_round()
                await self.async_refresh_from_engine()
        except asyncio.CancelledError:
            raise
        finally:
            current = asyncio.current_task()
            if self._auto_advance_task is current:
                self._auto_advance_task = None


    def _reset_trivia_buzzer_state(self) -> None:
        self.trivia_buzz_owner = None
        self.trivia_buzz_team = None
        self.trivia_steal_active = False
        self.trivia_steal_team = None
        self.trivia_steal_from_player = None

    def _activate_trivia_steal(self, player: Player) -> bool:
        eligible_team = None
        if self.trivia_team_mode and player.team in {"Team A", "Team B"}:
            eligible_team = "Team B" if player.team == "Team A" else "Team A"
            if not any((p.team == eligible_team) for p in self.engine.state.players):
                return False
        self.trivia_steal_active = True
        self.trivia_steal_team = eligible_team
        self.trivia_steal_from_player = player.name
        self.trivia_buzz_owner = None
        self.trivia_buzz_team = eligible_team
        for current in self.engine.state.players:
            current.submitted_card = None
        return True

    def _player_matches_steal_window(self, player_name: str) -> bool:
        player = self._find_player(player_name)
        if player is None:
            return False
        if self.trivia_steal_active and self.trivia_steal_team:
            return player.team == self.trivia_steal_team
        if self.trivia_steal_active and self.trivia_steal_from_player:
            return player.name.lower() != self.trivia_steal_from_player.lower()
        return player.name == self.trivia_buzz_owner

    def _can_player_answer_trivia(self, player_name: str) -> bool:
        if not self.trivia_buzzer_mode:
            return True
        player = self._find_player(player_name)
        if player is None:
            return False
        if self.trivia_steal_active:
            if self.trivia_steal_team:
                return player.team == self.trivia_steal_team and self.trivia_buzz_owner == player_name
            return self.trivia_buzz_owner == player_name and player.name.lower() != (self.trivia_steal_from_player or '').lower()
        return self.trivia_buzz_owner == player_name

    def _can_player_buzz(self, player_name: str) -> bool:
        player = self._find_player(player_name)
        if player is None or player.submitted_card:
            return False
        if self.trivia_buzz_owner:
            return self.trivia_buzz_owner == player_name
        if self.trivia_steal_active:
            if self.trivia_steal_team:
                return player.team == self.trivia_steal_team
            if self.trivia_steal_from_player:
                return player.name.lower() != self.trivia_steal_from_player.lower()
        return True

    def _find_player(self, player_name: str) -> Player | None:
        for player in self.engine.state.players:
            if player.name.lower() == player_name.strip().lower():
                return player
        return None

    def _default_team_for_new_player(self) -> str:
        if not self.trivia_team_mode:
            return "Solo"
        team_a = sum(1 for player in self.engine.state.players if player.team == "Team A")
        team_b = sum(1 for player in self.engine.state.players if player.team == "Team B")
        return "Team A" if team_a <= team_b else "Team B"


    async def async_apply_options(self, options: dict[str, Any]) -> None:
        """Apply config-entry options to runtime state."""
        self.entry_options = dict(options)

        self.parental_controls = normalize_parental_settings({
            **self.parental_controls,
            "content_mode": options.get(CONF_CONTENT_MODE, self.parental_controls.get("content_mode")),
            "require_ai_approval": options.get(CONF_REQUIRE_AI_APPROVAL, self.parental_controls.get("require_ai_approval")),
            "allow_remote_players": options.get(CONF_ALLOW_REMOTE_PLAYERS, self.parental_controls.get("allow_remote_players")),
            "allowed_trivia_categories": options.get(CONF_ALLOWED_TRIVIA_CATEGORIES, self.parental_controls.get("allowed_trivia_categories")),
        })

        self.game_mode = options.get(CONF_DEFAULT_GAME_MODE, self.game_mode)
        self.base_url = (options.get(CONF_REMOTE_BASE_URL, self.base_url or DEFAULT_REMOTE_BASE_URL) or "").rstrip("/")
        self.ai_generator.update_settings(
            enabled=bool(options.get(CONF_AI_ENABLED, self.ai_generator.settings.enabled)),
            endpoint=options.get(CONF_AI_ENDPOINT, self.ai_generator.settings.endpoint),
            model=options.get(CONF_AI_MODEL, self.ai_generator.settings.model),
            api_key=options.get(CONF_AI_API_KEY, self.ai_generator.settings.api_key),
            use_local_fallback=bool(options.get(CONF_AI_USE_LOCAL_FALLBACK, self.ai_generator.settings.use_local_fallback)),
        )
        self.trivia.source = options.get(CONF_DEFAULT_TRIVIA_SOURCE, getattr(self.trivia, "source", "offline_curated"))
        await self.async_refresh_from_engine()

    def options_summary(self) -> dict[str, Any]:
        """Return a sanitized runtime summary of entry options."""
        return {
            "max_rounds": int(self.entry_options.get(CONF_MAX_ROUNDS, 10)),
            "content_mode": self.parental_controls.get("content_mode"),
            "require_ai_approval": bool(self.parental_controls.get("require_ai_approval", True)),
            "allow_remote_players": bool(self.parental_controls.get("allow_remote_players", False)),
            "allowed_trivia_categories": list(self.parental_controls.get("allowed_trivia_categories", [])),
            "default_game_mode": self.entry_options.get(CONF_DEFAULT_GAME_MODE, GAME_MODE_CARDS),
            "default_trivia_source": self.entry_options.get(CONF_DEFAULT_TRIVIA_SOURCE, "offline_curated"),
            "ai": {
                "enabled": bool(self.ai_generator.settings.enabled),
                "model": self.ai_generator.settings.model,
                "endpoint": self.ai_generator.settings.endpoint,
                "use_local_fallback": bool(self.ai_generator.settings.use_local_fallback),
                "has_api_key": bool(self.ai_generator.settings.api_key),
            },
        }

    def _prune_tokens(self) -> None:
        active_names = {player.name for player in self.engine.state.players}
        self.player_tokens = {
            name: token for name, token in self.player_tokens.items() if name in active_names
        }

    def _generate_join_code(self) -> str:
        return "".join(secrets.choice(_ALPHABET) for _ in range(JOIN_CODE_LENGTH))

    def _generate_token(self, length: int) -> str:
        return secrets.token_urlsafe(length)
