"""Core in-memory game engine for HA Card Game."""

from __future__ import annotations

from dataclasses import dataclass, field
from random import choice, shuffle
from typing import Any

from .const import (
    DEFAULT_AUTO_ADVANCE_ENABLED,
    DEFAULT_AUTO_ADVANCE_SECONDS,
    DEFAULT_DECK,
    DEFAULT_HAND_SIZE,
    DEFAULT_PROMPTS,
    DEFAULT_REVEAL_DURATION_MS,
    DEFAULT_REVEAL_SOUND,
    DEFAULT_SUBMISSION_REVEAL_ENABLED,
    DEFAULT_SUBMISSION_REVEAL_STEP_MS,
    DEFAULT_FLIP_STYLE,
    DEFAULT_TICK_SOUND_PACK,
    DEFAULT_THEME_PRESET,
    DEFAULT_WHITE_CARDS,
    ROUND_THEMES,
    REVEAL_SOUNDS,
    THEME_PRESETS,
    FLIP_STYLES,
    TICK_SOUND_PACKS,
    PRESET_EXPORT_KIND,
    PRESET_EXPORT_VERSION,
    STATE_IDLE,
    STATE_JUDGING,
    STATE_LOBBY,
    STATE_RESULTS,
    STATE_SUBMITTING,
)


@dataclass
class Player:
    """Represents one player."""

    name: str
    score: int = 0
    submitted_card: str | None = None
    hand: list[str] = field(default_factory=list)
    team: str = "Solo"


@dataclass
class GameState:
    """Serializable game state."""

    state: str = STATE_IDLE
    round_number: int = 0
    judge_index: int = 0
    current_prompt: str | None = None
    winner: str | None = None
    winner_card: str | None = None
    winner_submission_id: str | None = None
    deck_name: str = DEFAULT_DECK
    allow_free_text: bool = False
    hand_size: int = DEFAULT_HAND_SIZE
    players: list[Player] = field(default_factory=list)
    prompts_remaining: list[str] = field(default_factory=lambda: list(DEFAULT_PROMPTS))
    white_cards_remaining: list[str] = field(default_factory=lambda: list(DEFAULT_WHITE_CARDS))
    reveal_order: list[str] = field(default_factory=list)
    available_decks: list[dict[str, Any]] = field(default_factory=list)
    round_timer_duration: int = 0
    round_timer_ends_at: float | None = None
    reveal_duration_ms: int = DEFAULT_REVEAL_DURATION_MS
    reveal_sound: str = DEFAULT_REVEAL_SOUND
    auto_advance_enabled: bool = DEFAULT_AUTO_ADVANCE_ENABLED
    auto_advance_seconds: int = DEFAULT_AUTO_ADVANCE_SECONDS
    submission_reveal_enabled: bool = DEFAULT_SUBMISSION_REVEAL_ENABLED
    submission_reveal_step_ms: int = DEFAULT_SUBMISSION_REVEAL_STEP_MS
    flip_style: str = DEFAULT_FLIP_STYLE
    tick_sound_pack: str = DEFAULT_TICK_SOUND_PACK
    theme_preset: str = DEFAULT_THEME_PRESET
    round_theme: dict[str, Any] = field(default_factory=lambda: dict(ROUND_THEMES[0]))
    custom_theme_presets: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        reveal_active = self.state == STATE_RESULTS and bool(self.winner)
        reveal_started_at = (self.round_timer_ends_at or 0)  # preserved for backwards compatibility consumers
        return {
            "state": self.state,
            "round_number": self.round_number,
            "judge_index": self.judge_index,
            "current_prompt": self.current_prompt,
            "winner": self.winner,
            "winner_card": self.winner_card,
            "winner_submission_id": self.winner_submission_id,
            "deck_name": self.deck_name,
            "allow_free_text": self.allow_free_text,
            "hand_size": self.hand_size,
            "players": [
                {
                    "name": player.name,
                    "score": player.score,
                    "submitted_card": player.submitted_card,
                    "hand_count": len(player.hand),
                    "team": player.team,
                }
                for player in self.players
            ],
            "prompts_remaining": list(self.prompts_remaining),
            "white_cards_remaining": len(self.white_cards_remaining),
            "judge": self.current_judge,
            "submissions": self.submissions,
            "public_submissions": self.public_submissions,
            "leaderboard": self.leaderboard,
            "team_leaderboard": self.team_leaderboard,
            "available_decks": list(self.available_decks),
            "round_timer_duration": self.round_timer_duration,
            "round_timer_ends_at": self.round_timer_ends_at,
            "theme": dict(self.round_theme),
            "reveal": {
                "active": reveal_active,
                "duration_ms": self.reveal_duration_ms,
                "sound": self.reveal_sound,
                "sound_options": list(REVEAL_SOUNDS),
                "started_at": reveal_started_at,
                "ends_at": None,
                "auto_advance_enabled": self.auto_advance_enabled,
                "auto_advance_seconds": self.auto_advance_seconds,
                "submission_reveal_enabled": self.submission_reveal_enabled,
                "submission_reveal_step_ms": self.submission_reveal_step_ms,
                "flip_style": self.flip_style,
                "flip_style_options": list(FLIP_STYLES),
                "tick_sound_pack": self.tick_sound_pack,
                "tick_sound_pack_options": list(TICK_SOUND_PACKS),
                "theme_preset": self.theme_preset,
                "theme_preset_options": [
                    {"slug": preset["slug"], "name": preset["name"], "description": preset.get("description", ""), "is_custom": False}
                    for preset in THEME_PRESETS
                ] + [
                    {"slug": preset["slug"], "name": preset["name"], "description": preset.get("description", ""), "is_custom": True}
                    for preset in self.custom_theme_presets
                ] + [{"slug": "custom", "name": "Custom", "description": "Manual reveal/theme mix.", "is_custom": False}],
                "submission_sequence": self.public_submissions,
                "winner": self.winner,
                "winner_card": self.winner_card,
                "winner_submission_id": self.winner_submission_id,
                "theme": dict(self.round_theme),
                "custom_theme_presets": [
                    {"slug": preset["slug"], "name": preset["name"], "description": preset.get("description", ""), "is_custom": True}
                    for preset in self.custom_theme_presets
                ],
            },
        }

    @property
    def current_judge(self) -> str | None:
        if not self.players:
            return None
        if self.judge_index >= len(self.players):
            self.judge_index = 0
        return self.players[self.judge_index].name

    @property
    def submissions(self) -> list[dict[str, str]]:
        return [
            {"player": player.name, "card": player.submitted_card}
            for player in self.players
            if player.submitted_card
        ]

    @property
    def public_submissions(self) -> list[dict[str, str]]:
        cards_by_player = {
            player.name: player.submitted_card
            for player in self.players
            if player.submitted_card
        }
        return [
            {"id": f"sub_{index+1}", "card": cards_by_player[player_name]}
            for index, player_name in enumerate(self.reveal_order)
            if cards_by_player.get(player_name)
        ]

    @property
    def leaderboard(self) -> list[dict[str, Any]]:
        return sorted(
            [{"name": p.name, "score": p.score} for p in self.players],
            key=lambda item: (-item["score"], item["name"].lower()),
        )

    @property
    def team_leaderboard(self) -> list[dict[str, Any]]:
        totals: dict[str, int] = {}
        for player in self.players:
            team = (player.team or "Solo").strip() or "Solo"
            totals[team] = totals.get(team, 0) + int(player.score)
        return sorted(
            [{"name": name, "score": score} for name, score in totals.items()],
            key=lambda item: (-item["score"], item["name"].lower()),
        )


class CardGameEngine:
    """Game engine for a simple judge-based party card game."""

    def __init__(self) -> None:
        self._state = GameState()

    @property
    def state(self) -> GameState:
        return self._state

    def reset(self) -> GameState:
        self._state = GameState(state=STATE_LOBBY)
        return self._state

    def set_reveal_config(
        self,
        *,
        duration_ms: int | None = None,
        sound: str | None = None,
        auto_advance_enabled: bool | None = None,
        auto_advance_seconds: int | None = None,
        submission_reveal_enabled: bool | None = None,
        submission_reveal_step_ms: int | None = None,
        flip_style: str | None = None,
        tick_sound_pack: str | None = None,
        theme_preset: str | None = None,
    ) -> GameState:
        if duration_ms is not None:
            if duration_ms < 1000:
                raise ValueError("Reveal duration must be at least 1000 ms")
            self._state.reveal_duration_ms = duration_ms
        if sound is not None:
            if sound not in REVEAL_SOUNDS:
                raise ValueError("Unknown reveal sound")
            self._state.reveal_sound = sound
        if auto_advance_enabled is not None:
            self._state.auto_advance_enabled = auto_advance_enabled
        if auto_advance_seconds is not None:
            if auto_advance_seconds < 0:
                raise ValueError("Auto-advance seconds cannot be negative")
            self._state.auto_advance_seconds = auto_advance_seconds
        if submission_reveal_enabled is not None:
            self._state.submission_reveal_enabled = submission_reveal_enabled
        if submission_reveal_step_ms is not None:
            if submission_reveal_step_ms < 500:
                raise ValueError("Submission reveal step must be at least 500 ms")
            self._state.submission_reveal_step_ms = submission_reveal_step_ms
        if flip_style is not None:
            if flip_style not in FLIP_STYLES:
                raise ValueError("Unknown flip style")
            self._state.flip_style = flip_style
        if tick_sound_pack is not None:
            if tick_sound_pack not in TICK_SOUND_PACKS:
                raise ValueError("Unknown tick sound pack")
            self._state.tick_sound_pack = tick_sound_pack
        if theme_preset is not None:
            self.apply_theme_preset(theme_preset)
            return self._state
        if any(value is not None for value in (duration_ms, sound, auto_advance_enabled, auto_advance_seconds, submission_reveal_enabled, submission_reveal_step_ms, flip_style, tick_sound_pack)):
            self._state.theme_preset = "custom"
        return self._state

    def apply_theme_preset(self, preset_slug: str) -> GameState:
        preset_slug = (preset_slug or "").strip()
        preset = self._find_theme_preset(preset_slug)
        if preset is None:
            raise ValueError("Unknown theme preset")
        self._state.theme_preset = preset_slug
        self._state.reveal_duration_ms = int(preset.get("reveal_duration_ms", self._state.reveal_duration_ms))
        self._state.reveal_sound = str(preset.get("reveal_sound", self._state.reveal_sound))
        self._state.auto_advance_enabled = bool(preset.get("auto_advance_enabled", self._state.auto_advance_enabled))
        self._state.auto_advance_seconds = int(preset.get("auto_advance_seconds", self._state.auto_advance_seconds))
        self._state.submission_reveal_enabled = bool(preset.get("submission_reveal_enabled", self._state.submission_reveal_enabled))
        self._state.submission_reveal_step_ms = int(preset.get("submission_reveal_step_ms", self._state.submission_reveal_step_ms))
        self._state.flip_style = str(preset.get("flip_style", self._state.flip_style))
        self._state.tick_sound_pack = str(preset.get("tick_sound_pack", self._state.tick_sound_pack))
        self._state.round_theme = dict(preset.get("theme") or self._state.round_theme)
        return self._state


    def save_custom_theme_preset(self, name: str, description: str = "") -> GameState:
        preset_name = (name or "").strip()
        if not preset_name:
            raise ValueError("Preset name is required")
        slug = self._slugify_preset_name(preset_name)
        if slug == "custom":
            raise ValueError("Preset name cannot resolve to reserved slug 'custom'")
        preset = {
            "slug": slug,
            "name": preset_name,
            "description": (description or "").strip() or f"Custom preset saved from host controls.",
            "reveal_sound": self._state.reveal_sound,
            "flip_style": self._state.flip_style,
            "tick_sound_pack": self._state.tick_sound_pack,
            "auto_advance_enabled": self._state.auto_advance_enabled,
            "auto_advance_seconds": self._state.auto_advance_seconds,
            "submission_reveal_enabled": self._state.submission_reveal_enabled,
            "submission_reveal_step_ms": self._state.submission_reveal_step_ms,
            "reveal_duration_ms": self._state.reveal_duration_ms,
            "theme": dict(self._state.round_theme),
        }
        for index, item in enumerate(self._state.custom_theme_presets):
            if item["slug"] == slug:
                self._state.custom_theme_presets[index] = preset
                break
        else:
            self._state.custom_theme_presets.append(preset)
        self._state.theme_preset = slug
        return self._state

    def delete_custom_theme_preset(self, preset_slug: str) -> GameState:
        preset_slug = (preset_slug or "").strip()
        if not preset_slug:
            raise ValueError("Preset slug is required")
        original_len = len(self._state.custom_theme_presets)
        self._state.custom_theme_presets = [item for item in self._state.custom_theme_presets if item["slug"] != preset_slug]
        if len(self._state.custom_theme_presets) == original_len:
            raise ValueError("Unknown custom preset")
        if self._state.theme_preset == preset_slug:
            self._state.theme_preset = "custom"
        return self._state


    def export_theme_presets(self, include_builtin: bool = False) -> dict[str, Any]:
        presets = [dict(item) for item in self._state.custom_theme_presets]
        if include_builtin:
            presets = [dict(item, is_custom=False) for item in THEME_PRESETS] + [dict(item, is_custom=True) for item in presets]
        else:
            presets = [dict(item, is_custom=True) for item in presets]
        return {
            "kind": PRESET_EXPORT_KIND,
            "version": PRESET_EXPORT_VERSION,
            "theme_preset": self._state.theme_preset,
            "exported_at_round": self._state.round_number,
            "presets": presets,
        }

    def import_theme_presets(self, payload: dict[str, Any], mode: str = "merge") -> GameState:
        if not isinstance(payload, dict):
            raise ValueError("Preset import payload must be an object")
        if payload.get("kind") != PRESET_EXPORT_KIND:
            raise ValueError("Unsupported preset import file")
        presets = payload.get("presets")
        if not isinstance(presets, list):
            raise ValueError("Preset import file is missing presets")
        mode = (mode or "merge").strip().lower()
        if mode not in {"merge", "replace"}:
            raise ValueError("Import mode must be merge or replace")

        imported: list[dict[str, Any]] = []
        for item in presets:
            if not isinstance(item, dict):
                raise ValueError("Invalid preset entry in import file")
            if item.get("is_custom") is False:
                continue
            preset_name = str(item.get("name", "")).strip()
            slug = str(item.get("slug", "")).strip() or self._slugify_preset_name(preset_name)
            if not preset_name:
                raise ValueError("Imported preset is missing a name")
            if slug == "custom":
                raise ValueError("Imported preset cannot use reserved slug 'custom'")
            reveal_sound = str(item.get("reveal_sound", self._state.reveal_sound))
            flip_style = str(item.get("flip_style", self._state.flip_style))
            tick_sound_pack = str(item.get("tick_sound_pack", self._state.tick_sound_pack))
            if reveal_sound not in REVEAL_SOUNDS:
                raise ValueError(f"Imported preset '{preset_name}' has unknown reveal sound")
            if flip_style not in FLIP_STYLES:
                raise ValueError(f"Imported preset '{preset_name}' has unknown flip style")
            if tick_sound_pack not in TICK_SOUND_PACKS:
                raise ValueError(f"Imported preset '{preset_name}' has unknown tick sound pack")
            reveal_duration_ms = int(item.get("reveal_duration_ms", self._state.reveal_duration_ms))
            submission_reveal_step_ms = int(item.get("submission_reveal_step_ms", self._state.submission_reveal_step_ms))
            auto_advance_seconds = int(item.get("auto_advance_seconds", self._state.auto_advance_seconds))
            if reveal_duration_ms < 1000:
                raise ValueError(f"Imported preset '{preset_name}' has invalid reveal duration")
            if submission_reveal_step_ms < 500:
                raise ValueError(f"Imported preset '{preset_name}' has invalid submission reveal step")
            if auto_advance_seconds < 0:
                raise ValueError(f"Imported preset '{preset_name}' has invalid auto-advance seconds")
            theme = item.get("theme")
            if not isinstance(theme, dict):
                raise ValueError(f"Imported preset '{preset_name}' is missing theme settings")
            imported.append({
                "slug": slug,
                "name": preset_name,
                "description": str(item.get("description", "")).strip() or "Imported custom preset",
                "reveal_sound": reveal_sound,
                "flip_style": flip_style,
                "tick_sound_pack": tick_sound_pack,
                "auto_advance_enabled": bool(item.get("auto_advance_enabled", False)),
                "auto_advance_seconds": auto_advance_seconds,
                "submission_reveal_enabled": bool(item.get("submission_reveal_enabled", True)),
                "submission_reveal_step_ms": submission_reveal_step_ms,
                "reveal_duration_ms": reveal_duration_ms,
                "theme": dict(theme),
            })

        if mode == "replace":
            self._state.custom_theme_presets = imported
        else:
            merged = {item["slug"]: dict(item) for item in self._state.custom_theme_presets}
            for item in imported:
                merged[item["slug"]] = item
            self._state.custom_theme_presets = list(merged.values())

        if self._state.theme_preset != "custom" and self._find_theme_preset(self._state.theme_preset) is None:
            self._state.theme_preset = "custom"
        return self._state

    def _find_theme_preset(self, preset_slug: str) -> dict[str, Any] | None:
        return next((item for item in [*THEME_PRESETS, *self._state.custom_theme_presets] if item["slug"] == preset_slug), None)

    @staticmethod
    def _slugify_preset_name(name: str) -> str:
        slug_chars = [ch.lower() if ch.isalnum() else "_" for ch in name.strip()]
        slug = "".join(slug_chars)
        while "__" in slug:
            slug = slug.replace("__", "_")
        return slug.strip("_") or "preset"

    def set_round_timer(self, seconds: int, ends_at: float | None) -> GameState:
        if seconds < 0:
            raise ValueError("Timer seconds cannot be negative")
        self._state.round_timer_duration = seconds
        self._state.round_timer_ends_at = ends_at if seconds else None
        return self._state

    def clear_round_timer(self) -> GameState:
        self._state.round_timer_duration = 0
        self._state.round_timer_ends_at = None
        return self._state

    def add_player(self, player_name: str) -> GameState:
        player_name = player_name.strip()
        if not player_name:
            raise ValueError("Player name cannot be empty")
        if any(p.name.lower() == player_name.lower() for p in self._state.players):
            raise ValueError(f"Player '{player_name}' already exists")
        player = Player(name=player_name)
        self._refill_hand(player)
        self._state.players.append(player)
        if self._state.state == STATE_IDLE:
            self._state.state = STATE_LOBBY
        return self._state

    def remove_player(self, player_name: str) -> GameState:
        player_name = player_name.strip()
        if not player_name:
            raise ValueError("Player name cannot be empty")

        index = next((idx for idx, player in enumerate(self._state.players) if player.name.lower() == player_name.lower()), None)
        if index is None:
            raise ValueError(f"Unknown player '{player_name}'")

        removed = self._state.players.pop(index)
        self._state.reveal_order = [name for name in self._state.reveal_order if name.lower() != removed.name.lower()]

        if not self._state.players:
            return self.reset()

        if index < self._state.judge_index:
            self._state.judge_index -= 1
        elif index == self._state.judge_index and self._state.judge_index >= len(self._state.players):
            self._state.judge_index = 0

        if self._state.state in {STATE_SUBMITTING, STATE_JUDGING}:
            judge = self._state.current_judge
            non_judges = [p for p in self._state.players if p.name != judge]
            if len(self._state.players) < 3:
                self._state.state = STATE_LOBBY
                self._state.current_prompt = None
                self._state.winner = None
                self._state.winner_card = None
                self._state.winner_submission_id = None
                self._clear_submissions()
                self._state.reveal_order = []
                self.clear_round_timer()
            elif non_judges and all(p.submitted_card for p in non_judges):
                self._prepare_judging_round()

        if self._state.state == STATE_RESULTS and self._state.winner and self._state.winner.lower() == removed.name.lower():
            self._state.winner = None
            self._state.winner_card = None
            self._state.winner_submission_id = None

        if self._state.state == STATE_IDLE:
            self._state.state = STATE_LOBBY
        return self._state

    def start_game(self, deck_name: str = DEFAULT_DECK, prompts: list[str] | None = None, white_cards: list[str] | None = None, allow_free_text: bool = False, hand_size: int = DEFAULT_HAND_SIZE) -> GameState:
        if len(self._state.players) < 3:
            raise ValueError("At least 3 players are required to start the game")
        self._state.deck_name = deck_name
        self._state.allow_free_text = allow_free_text
        self._state.hand_size = hand_size
        self._state.round_number = 1
        self._state.judge_index = 0
        self._state.prompts_remaining = list(prompts or DEFAULT_PROMPTS)
        shuffle(self._state.prompts_remaining)
        self._state.white_cards_remaining = list(white_cards or DEFAULT_WHITE_CARDS)
        shuffle(self._state.white_cards_remaining)
        self._state.winner = None
        self._state.winner_card = None
        self._state.winner_submission_id = None
        self._state.reveal_order = []
        self._apply_round_theme()
        self.clear_round_timer()
        self._clear_submissions()
        for player in self._state.players:
            player.hand = []
            self._refill_hand(player)
        self._state.current_prompt = self._draw_prompt()
        self._state.state = STATE_SUBMITTING
        return self._state

    def next_round(self) -> GameState:
        if len(self._state.players) < 3:
            raise ValueError("At least 3 players are required")
        self._state.round_number += 1
        self._state.judge_index = (self._state.judge_index + 1) % len(self._state.players)
        self._state.winner = None
        self._state.winner_card = None
        self._state.winner_submission_id = None
        self._state.reveal_order = []
        self._apply_round_theme()
        self.clear_round_timer()
        self._clear_submissions()
        for player in self._state.players:
            self._refill_hand(player)
        self._state.current_prompt = self._draw_prompt()
        self._state.state = STATE_SUBMITTING
        return self._state

    def submit_card(self, player_name: str, card_text: str) -> GameState:
        if self._state.state not in {STATE_SUBMITTING, STATE_JUDGING}:
            raise ValueError("Game is not accepting submissions")
        if not card_text.strip():
            raise ValueError("Card text cannot be empty")

        judge = self._state.current_judge
        if judge and judge.lower() == player_name.lower():
            raise ValueError("The judge cannot submit a card this round")

        player = self._get_player(player_name)
        if player.submitted_card:
            raise ValueError("Player already submitted this round")

        selected = card_text.strip()
        if player.hand:
            try:
                player.hand.remove(selected)
            except ValueError:
                if not self._state.allow_free_text:
                    raise ValueError("Selected card is not in the player's hand")
        elif not self._state.allow_free_text and self._state.white_cards_remaining:
            raise ValueError("This deck requires choosing a white card from the hand")

        player.submitted_card = selected

        non_judges = [p for p in self._state.players if p.name != judge]
        if non_judges and all(p.submitted_card for p in non_judges):
            self._prepare_judging_round()

        return self._state

    def pick_winner(self, player_name: str) -> GameState:
        player = self._get_player(player_name)
        return self._award_winner(player)

    def pick_winner_submission(self, submission_id: str) -> GameState:
        if self._state.state not in {STATE_JUDGING, STATE_SUBMITTING}:
            raise ValueError("No round is ready to be judged")

        if not self._state.reveal_order:
            self._prepare_judging_round()

        try:
            index = int(submission_id.replace("sub_", "")) - 1
            player_name = self._state.reveal_order[index]
        except (ValueError, IndexError) as err:
            raise ValueError("Unknown submission") from err

        player = self._get_player(player_name)
        state = self._award_winner(player)
        state.winner_submission_id = submission_id
        return state

    def submission_id_for_player(self, player_name: str) -> str | None:
        for index, current_player in enumerate(self._state.reveal_order, start=1):
            if current_player.lower() == player_name.lower():
                return f"sub_{index}"
        return None

    def shuffled_submissions(self) -> list[dict[str, str]]:
        submissions = self._state.public_submissions[:]
        shuffle(submissions)
        return submissions

    def _prepare_judging_round(self) -> None:
        judge = self._state.current_judge
        reveal_order = [p.name for p in self._state.players if p.name != judge and p.submitted_card]
        shuffle(reveal_order)
        self._state.reveal_order = reveal_order
        self._state.state = STATE_JUDGING

    def _award_winner(self, player: Player) -> GameState:
        if self._state.state not in {STATE_JUDGING, STATE_SUBMITTING}:
            raise ValueError("No round is ready to be judged")
        if not player.submitted_card:
            raise ValueError("Winning player must have a submitted card")
        player.score += 1
        self._state.winner = player.name
        self._state.winner_card = player.submitted_card
        self._state.winner_submission_id = self.submission_id_for_player(player.name)
        self._state.state = STATE_RESULTS
        self.clear_round_timer()
        return self._state

    def _get_player(self, player_name: str) -> Player:
        for player in self._state.players:
            if player.name.lower() == player_name.lower():
                return player
        raise ValueError(f"Unknown player '{player_name}'")

    def _clear_submissions(self) -> None:
        for player in self._state.players:
            player.submitted_card = None

    def _draw_prompt(self) -> str:
        if not self._state.prompts_remaining:
            self._state.prompts_remaining = list(DEFAULT_PROMPTS)
            shuffle(self._state.prompts_remaining)
        return self._state.prompts_remaining.pop() if self._state.prompts_remaining else choice(DEFAULT_PROMPTS)

    def _draw_white_card(self) -> str:
        if not self._state.white_cards_remaining:
            self._state.white_cards_remaining = list(DEFAULT_WHITE_CARDS)
            shuffle(self._state.white_cards_remaining)
        return self._state.white_cards_remaining.pop() if self._state.white_cards_remaining else choice(DEFAULT_WHITE_CARDS)

    def _refill_hand(self, player: Player) -> None:
        while len(player.hand) < self._state.hand_size:
            player.hand.append(self._draw_white_card())

    def _apply_round_theme(self) -> None:
        if self._state.theme_preset and self._state.theme_preset != "custom":
            preset = self._find_theme_preset(self._state.theme_preset)
            if preset and preset.get("theme"):
                self._state.round_theme = dict(preset["theme"])
                return
        index = max(self._state.round_number - 1, 0) % len(ROUND_THEMES)
        self._state.round_theme = dict(ROUND_THEMES[index])
