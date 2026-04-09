"""Core trivia coordinator overrides for HA Card Game."""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any

from .const import DOMAIN, GAME_MODE_TRIVIA, TRIVIA_DIFFICULTY_BY_AGE
from .coordinator import CardGameCoordinator
from .moderation import moderate_trivia_questions
from .trivia_manager import get_curated_trivia_questions

CONF_TRIVIA_ANSWER_SECONDS = "trivia_answer_seconds"
CONF_TRIVIA_REVEAL_SECONDS = "trivia_reveal_seconds"
CONF_TRIVIA_AUTO_CYCLE_ENABLED = "trivia_auto_cycle_enabled"


class TriviaCoreCoordinator(CardGameCoordinator):
    """Coordinator with built-in trivia timing and category support."""

    def __init__(self, hass):
        super().__init__(hass)
        self.trivia_answer_seconds = 15
        self.trivia_reveal_seconds = 5
        self.trivia_auto_cycle_enabled = True
        self._trivia_cycle_task: asyncio.Task | None = None

    @property
    def join_url(self) -> str:
        if not self.base_url:
            return f"/local/{DOMAIN}/index.modular.html?join={self.join_code}"
        return f"{self.base_url}/local/{DOMAIN}/index.modular.html?join={self.join_code}"

    async def async_save(self) -> None:
        await super().async_save()
        self._sync_trivia_cycle()

    async def async_refresh_from_engine(self) -> None:
        await super().async_refresh_from_engine()
        self._sync_trivia_cycle()

    async def async_reset_lobby(self) -> None:
        self._cancel_trivia_cycle_task()
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
        state["trivia"] = trivia
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
        ):
            self._trivia_cycle_task = self.hass.async_create_task(
                self._async_trivia_next_question_runner(
                    self.engine.state.round_number,
                    getattr(self.trivia, "current_index", -1),
                    float(self.trivia_reveal_seconds),
                )
            )

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

        if len(category_list) == 1:
            await super().async_prepare_trivia(
                category=category_list[0],
                age_range=age_range,
                difficulty=difficulty,
                question_count=question_count,
                source=source,
            )
            return

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
            category="mixed",
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
        seconds = max(1, int(self.trivia_answer_seconds or 15))
        self.engine.set_round_timer(seconds, time.time() + seconds)
        self.last_trivia_results = []
        self._reset_trivia_buzzer_state()
        for player in self.engine.state.players:
            player.submitted_card = None
        await self.async_refresh_from_engine()

    async def async_grade_trivia_round(self) -> dict[str, Any]:
        self._cancel_trivia_cycle_task()
        result = await super().async_grade_trivia_round()
        self.engine.clear_round_timer()
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
