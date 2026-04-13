"""Core trivia coordinator overrides for HA Card Game."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN, GAME_MODE_TRIVIA, TRIVIA_DIFFICULTY_BY_AGE
from .coordinator import CardGameCoordinator
from .moderation import moderate_trivia_questions
from .trivia_manager import get_curated_trivia_questions

CONF_TRIVIA_ANSWER_SECONDS = "trivia_answer_seconds"
CONF_TRIVIA_REVEAL_SECONDS = "trivia_reveal_seconds"
CONF_TRIVIA_AUTO_CYCLE_ENABLED = "trivia_auto_cycle_enabled"

_LOGGER = logging.getLogger(__name__)


class TriviaCoreCoordinator(CardGameCoordinator):
    """Coordinator with built-in trivia timing and category support."""

    def __init__(self, hass: HomeAssistant):
        super().__init__(hass)
        self.trivia_answer_seconds = 15
        self.trivia_reveal_seconds = 5
        self.trivia_auto_cycle_enabled = True
        self.trivia_voice_config: dict[str, Any] = {
            "enabled": False,
            "provider_entity": "",
            "speaker_targets": [],
            "voice": "",
            "language": "en-US",
            "announce_answers": True,
            "announce_correct_players": True,
            "start_timer_after_voice": True,
            "speech_rate_wpm": 155,
        }
        self._trivia_cycle_task: asyncio.Task | None = None
        self._trivia_voice_delay_seconds: float = 0.0

    @property
    def join_url(self) -> str:
        if not self.base_url:
            return f"/local/{DOMAIN}/index.modular.html?join={self.join_code}"
        return f"{self.base_url}/local/{DOMAIN}/index.modular.html?join={self.join_code}"

    async def async_load(self) -> None:
        await super().async_load()
        # Pull persisted trivia runtime settings from the storage payload already loaded by the base coordinator.
        self.trivia_answer_seconds = max(3, int(self.data.get("trivia_answer_seconds", 15) or 15))
        self.trivia_reveal_seconds = max(1, int(self.data.get("trivia_reveal_seconds", 5) or 5))
        self.trivia_auto_cycle_enabled = bool(self.data.get("trivia_auto_cycle_enabled", True))
        saved_voice = self.data.get("trivia_voice_config") or {}
        if isinstance(saved_voice, dict):
            self.trivia_voice_config = {**self.trivia_voice_config, **saved_voice}
        self._sync_trivia_cycle()

    async def async_save(self) -> None:
        # Ensure these trivia-only fields are part of self.data before the base player_state consumers read them.
        self.data["trivia_answer_seconds"] = int(self.trivia_answer_seconds)
        self.data["trivia_reveal_seconds"] = int(self.trivia_reveal_seconds)
        self.data["trivia_auto_cycle_enabled"] = bool(self.trivia_auto_cycle_enabled)
        self.data["trivia_voice_config"] = dict(self.trivia_voice_config)
        await super().async_save()
        self._sync_trivia_cycle()

    async def async_refresh_from_engine(self) -> None:
        await super().async_refresh_from_engine()
        self._sync_trivia_cycle()

    async def async_reset_lobby(self) -> None:
        self._cancel_trivia_cycle_task()
        self._trivia_voice_delay_seconds = 0.0
        await super().async_reset_lobby()

    async def async_apply_options(self, options: dict[str, Any]) -> None:
        await super().async_apply_options(options)
        self.trivia_answer_seconds = max(
            3, int(options.get(CONF_TRIVIA_ANSWER_SECONDS, self.trivia_answer_seconds) or 15)
        )
        self.trivia_reveal_seconds = max(
            1, int(options.get(CONF_TRIVIA_REVEAL_SECONDS, self.trivia_reveal_seconds) or 5)
        )
        self.trivia_auto_cycle_enabled = bool(
            options.get(CONF_TRIVIA_AUTO_CYCLE_ENABLED, self.trivia_auto_cycle_enabled)
        )
        self._sync_trivia_cycle()

    def player_state(self, token: str | None) -> dict[str, Any]:
        state = super().player_state(token)
        trivia = dict(state.get("trivia", {}))
        trivia["answer_seconds"] = int(self.trivia_answer_seconds)
        trivia["reveal_seconds"] = int(self.trivia_reveal_seconds)
        trivia["auto_cycle_enabled"] = bool(self.trivia_auto_cycle_enabled)
        trivia["voice"] = dict(self.trivia_voice_config)
        state["trivia"] = trivia
        state["trivia_answer_seconds"] = int(self.trivia_answer_seconds)
        state["trivia_reveal_seconds"] = int(self.trivia_reveal_seconds)
        state["trivia_auto_cycle_enabled"] = bool(self.trivia_auto_cycle_enabled)
        state["trivia_voice_config"] = dict(self.trivia_voice_config)
        return state

    def _cancel_trivia_cycle_task(self) -> None:
        task = self._trivia_cycle_task
        if task and not task.done():
            task.cancel()
        self._trivia_cycle_task = None

    def _questions_remaining_after_current(self) -> bool:
        return int(getattr(self.trivia, "current_index", -1)) < (
            len(getattr(self.trivia, "questions", [])) - 1
        )

    def _hold_for_manual_next(self) -> bool:
        return bool((self.engine.state.round_theme or {}).get("_trivia_hold_for_manual_next"))

    def _build_trivia_question_announcement(self, question: dict[str, Any]) -> str:
        choices = [str(item).strip() for item in question.get("choices", []) if str(item).strip()]
        if choices:
            choice_text = " ".join(
                f"{chr(65 + idx)}. {choice}." for idx, choice in enumerate(choices[:6])
            )
            return f"Trivia question. {question.get('question', '')} Choices are: {choice_text}"
        return f"Trivia question. {question.get('question', '')}"

    def _build_trivia_results_announcement(self, result: dict[str, Any]) -> str:
        if not self.trivia_voice_config.get("announce_answers", True):
            return ""
        correct_answer = str(result.get("correct_answer", "") or "").strip()
        explanation = str(result.get("explanation", "") or "").strip()
        correct_players = [str(item).strip() for item in result.get("correct_players", []) if str(item).strip()]

        parts = []
        if correct_answer:
            parts.append(f"The correct answer is {correct_answer}.")
        if self.trivia_voice_config.get("announce_correct_players", True):
            if correct_players:
                parts.append("Correct players: " + ", ".join(correct_players) + ".")
            else:
                parts.append("No one got it right this round.")
        if explanation:
            parts.append(explanation)
        return " ".join(parts).strip()

    async def _async_trivia_timeout_runner(self, round_number: int, question_index: int, delay: float) -> None:
        try:
            await asyncio.sleep(max(0.0, delay))
            if self.game_mode != GAME_MODE_TRIVIA:
                return
            if self.engine.state.state != "submitting":
                return
            if self.engine.state.round_number != round_number:
                return
            if getattr(self.trivia, "current_index", -1) != question_index:
                return
            await self.async_grade_trivia_round()
        except asyncio.CancelledError:
            raise
        finally:
            current = asyncio.current_task()
            if self._trivia_cycle_task is current:
                self._trivia_cycle_task = None

    async def _async_trivia_next_question_runner(self, round_number: int, question_index: int, delay: float) -> None:
        try:
            await asyncio.sleep(max(0.0, delay))
            if self.game_mode != GAME_MODE_TRIVIA:
                return
            if self.engine.state.state != "results":
                return
            if self.engine.state.round_number != round_number:
                return
            if getattr(self.trivia, "current_index", -1) != question_index:
                return
            if self._hold_for_manual_next():
                return
            if not self._questions_remaining_after_current():
                return
            await self.async_start_trivia_round()
        except asyncio.CancelledError:
            raise
        finally:
            current = asyncio.current_task()
            if self._trivia_cycle_task is current:
                self._trivia_cycle_task = None

    def _sync_trivia_cycle(self) -> None:
        self._cancel_trivia_cycle_task()
        if self.game_mode != GAME_MODE_TRIVIA:
            return

        if self.engine.state.state == "submitting":
            ends_at = float(getattr(self.engine.state, "round_timer_ends_at", 0) or 0)
            if ends_at:
                delay = max(0.0, ends_at - time.time())
                self._trivia_cycle_task = self.hass.async_create_task(
                    self._async_trivia_timeout_runner(
                        self.engine.state.round_number,
                        getattr(self.trivia, "current_index", -1),
                        delay,
                    )
                )
            return

        if (
            self.engine.state.state == "results"
            and self.trivia_auto_cycle_enabled
            and self.trivia_reveal_seconds > 0
            and self._questions_remaining_after_current()
            and not self._hold_for_manual_next()
        ):
            total_delay = float(self.trivia_reveal_seconds) + float(self._trivia_voice_delay_seconds or 0.0)
            self._trivia_cycle_task = self.hass.async_create_task(
                self._async_trivia_next_question_runner(
                    self.engine.state.round_number,
                    getattr(self.trivia, "current_index", -1),
                    total_delay,
                )
            )

    async def async_available_tts_providers(self) -> list[dict[str, Any]]:
        providers: list[dict[str, Any]] = []
        try:
            for state in self.hass.states.async_all():
                entity_id = str(getattr(state, "entity_id", "") or "")
                if entity_id.startswith("tts."):
                    providers.append({
                        "entity_id": entity_id,
                        "name": state.attributes.get("friendly_name", entity_id),
                    })
        except Exception:
            return []
        providers.sort(key=lambda item: item["name"].lower())
        return providers

    async def async_available_speakers(self) -> list[dict[str, Any]]:
        speakers: list[dict[str, Any]] = []
        try:
            for state in self.hass.states.async_all():
                entity_id = str(getattr(state, "entity_id", "") or "")
                if entity_id.startswith("media_player."):
                    speakers.append({
                        "entity_id": entity_id,
                        "name": state.attributes.get("friendly_name", entity_id),
                    })
        except Exception:
            return []
        speakers.sort(key=lambda item: item["name"].lower())
        return speakers

    async def async_set_trivia_voice_config(
        self,
        *,
        enabled: bool | None = None,
        provider_entity: str | None = None,
        speaker_targets: list[str] | None = None,
        voice: str | None = None,
        language: str | None = None,
        announce_answers: bool | None = None,
        announce_correct_players: bool | None = None,
        start_timer_after_voice: bool | None = None,
        speech_rate_wpm: int | None = None,
    ) -> None:
        if enabled is not None:
            self.trivia_voice_config["enabled"] = bool(enabled)
        if provider_entity is not None:
            self.trivia_voice_config["provider_entity"] = str(provider_entity).strip()
        if speaker_targets is not None:
            self.trivia_voice_config["speaker_targets"] = [
                str(item).strip() for item in speaker_targets if str(item).strip()
            ]
        if voice is not None:
            self.trivia_voice_config["voice"] = str(voice).strip()
        if language is not None:
            self.trivia_voice_config["language"] = str(language).strip() or "en-US"
        if announce_answers is not None:
            self.trivia_voice_config["announce_answers"] = bool(announce_answers)
        if announce_correct_players is not None:
            self.trivia_voice_config["announce_correct_players"] = bool(announce_correct_players)
        if start_timer_after_voice is not None:
            self.trivia_voice_config["start_timer_after_voice"] = bool(start_timer_after_voice)
        if speech_rate_wpm is not None:
            self.trivia_voice_config["speech_rate_wpm"] = max(80, min(260, int(speech_rate_wpm)))
        await self.async_refresh_from_engine()

    async def async_speak_trivia_text(self, message: str) -> float:
        if not self.trivia_voice_config.get("enabled"):
            return 0.0
        message = str(message or "").strip()
        if not message:
            return 0.0

        provider_entity = str(self.trivia_voice_config.get("provider_entity", "") or "").strip()
        speaker_targets = [
            str(item).strip()
            for item in self.trivia_voice_config.get("speaker_targets", [])
            if str(item).strip()
        ]
        if not provider_entity or not speaker_targets:
            return 0.0

        estimated_seconds = max(
            0.0,
            min(
                20.0,
                len(message.split()) / max(80, int(self.trivia_voice_config.get("speech_rate_wpm", 155))),
            ),
        ) * 60.0

        services = getattr(self.hass, "services", None)
        if not services or not hasattr(services, "async_call"):
            return estimated_seconds

        for target in speaker_targets:
            try:
                await services.async_call(
                    "tts",
                    "speak",
                    {
                        "entity_id": provider_entity,
                        "media_player_entity_id": target,
                        "message": message,
                        "language": self.trivia_voice_config.get("language") or "en-US",
                        "options": {
                            "voice": self.trivia_voice_config.get("voice") or "",
                        },
                    },
                    blocking=False,
                )
            except Exception:
                _LOGGER.debug("Trivia TTS speak failed for %s -> %s", provider_entity, target, exc_info=True)
        return estimated_seconds

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

            player = self._find_player(player_name)
            if player is None:
                raise ValueError("Unknown player")
            player.submitted_card = str(card_text or "").strip()

            if self.trivia_buzzer_mode:
                result = await self.async_grade_trivia_round()
                if result.get("steal_available"):
                    return
                return

            active_players = [current for current in self.engine.state.players]
            if active_players and all((current.submitted_card or "").strip() for current in active_players):
                await self.async_grade_trivia_round()
                return

            await self.async_refresh_from_engine()
            return

        await super().async_submit_for_token(token, card_text)

    async def async_prepare_trivia(
        self,
        *,
        category: str,
        age_range: str,
        difficulty: str | None = None,
        question_count: int = 10,
        source: str = "ai",
        categories: list[str] | None = None,
    ) -> None:
        category_list = [str(item).strip() for item in (categories or []) if str(item).strip()]
        if not category_list:
            category_list = [str(category or "fun_facts").strip() or "fun_facts"]
        category_list = list(dict.fromkeys(category_list))

        difficulty_value = difficulty or TRIVIA_DIFFICULTY_BY_AGE.get(age_range, "medium")
        source_value = (source or "ai").strip().lower()
        per_category = max(1, math.ceil(int(question_count) / max(1, len(category_list))))
        all_questions: list[dict[str, Any]] = []
        moderation_issues: list[dict[str, Any]] = []

        if self.parental_controls.get("enabled"):
            allowed_categories = set(self.parental_controls.get("allowed_trivia_categories", []))
            for selected_category in category_list:
                if selected_category not in allowed_categories and selected_category not in self.custom_trivia_packs:
                    raise ValueError(f"{selected_category} is blocked by parental controls")

        for selected_category in category_list:
            if source_value == "offline_curated":
                if selected_category in self.custom_trivia_packs:
                    questions = self._get_custom_trivia_questions(
                        category=selected_category,
                        age_range=age_range,
                        difficulty=difficulty_value,
                        question_count=per_category,
                    )
                else:
                    questions = get_curated_trivia_questions(
                        category=selected_category,
                        age_range=age_range,
                        difficulty=difficulty_value,
                        question_count=per_category,
                    )
            else:
                questions = await self.ai_generator.generate_trivia(
                    category=selected_category,
                    age_range=age_range,
                    difficulty=difficulty_value,
                    question_count=per_category,
                )

            if self.parental_controls.get("enabled"):
                questions, category_issues = moderate_trivia_questions(
                    questions,
                    content_mode=self.parental_controls.get("content_mode", "family_safe"),
                )
                moderation_issues.extend(category_issues)

            all_questions.extend(questions)

        all_questions = all_questions[: max(1, int(question_count))]
        if not all_questions:
            raise ValueError("No trivia questions remain after filtering")

        if (
            source_value != "offline_curated"
            and self.parental_controls.get("enabled")
            and self.parental_controls.get("require_ai_approval")
        ):
            self._queue_ai_item(
                "trivia",
                "Mixed trivia",
                {
                    "questions": all_questions,
                    "category": "mixed",
                    "categories": category_list,
                    "age_range": age_range,
                    "difficulty": difficulty_value,
                    "source": source_value,
                },
                f"{len(all_questions)} questions across {', '.join(category_list)}",
                moderation_issues,
            )
            await self.async_refresh_from_engine()
            return

        self.trivia.load_questions(
            all_questions,
            category="mixed" if len(category_list) > 1 else category_list[0],
            age_range=age_range,
            difficulty=difficulty_value,
            source=source_value,
        )
        self.game_mode = GAME_MODE_TRIVIA
        self.last_trivia_results = []
        self._reset_trivia_buzzer_state()
        await self.async_refresh_from_engine()

    async def async_start_trivia_round(self) -> None:
        self._cancel_trivia_cycle_task()
        self._trivia_voice_delay_seconds = 0.0

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
        round_theme = dict(self.engine.state.round_theme or {})
        round_theme.pop("_trivia_hold_for_manual_next", None)
        self.engine.state.round_theme = round_theme
        self.engine.clear_round_timer()
        self.last_trivia_results = []
        self._reset_trivia_buzzer_state()
        for player in self.engine.state.players:
            player.submitted_card = None

        await self.async_refresh_from_engine()

        if self.trivia_voice_config.get("enabled") and self.trivia_voice_config.get("start_timer_after_voice", True):
            message = self._build_trivia_question_announcement(q)
            self._trivia_voice_delay_seconds = await self.async_speak_trivia_text(message)
            if self._trivia_voice_delay_seconds > 0:
                await asyncio.sleep(self._trivia_voice_delay_seconds)

        seconds = max(3, int(self.trivia_answer_seconds or 15))
        self.engine.set_round_timer(seconds, time.time() + seconds)
        await self.async_refresh_from_engine()

    async def async_grade_trivia_round(self) -> dict[str, Any]:
        self._cancel_trivia_cycle_task()
        self._trivia_voice_delay_seconds = 0.0

        result = await super().async_grade_trivia_round()
        self.engine.clear_round_timer()
        await self.async_refresh_from_engine()

        if self.trivia_voice_config.get("enabled"):
            announcement = self._build_trivia_results_announcement(result)
            self._trivia_voice_delay_seconds = await self.async_speak_trivia_text(announcement)
            await self.async_refresh_from_engine()

        return result

    async def async_set_trivia_settings(
        self,
        *,
        team_mode: bool | None = None,
        buzzer_mode: bool | None = None,
        buzz_bonus: int | None = None,
        steal_enabled: bool | None = None,
        answer_seconds: int | None = None,
        reveal_seconds: int | None = None,
        auto_cycle_enabled: bool | None = None,
    ) -> None:
        await super().async_set_trivia_settings(
            team_mode=team_mode,
            buzzer_mode=buzzer_mode,
            buzz_bonus=buzz_bonus,
            steal_enabled=steal_enabled,
        )
        if answer_seconds is not None:
            self.trivia_answer_seconds = max(3, int(answer_seconds))
        if reveal_seconds is not None:
            self.trivia_reveal_seconds = max(1, int(reveal_seconds))
        if auto_cycle_enabled is not None:
            self.trivia_auto_cycle_enabled = bool(auto_cycle_enabled)
        await self.async_refresh_from_engine()
