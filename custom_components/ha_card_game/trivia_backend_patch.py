"""Runtime patch helpers for enhanced trivia automation."""

from __future__ import annotations

import asyncio
import math
import time
from types import MethodType
from typing import Any

from .const import GAME_MODE_TRIVIA, TRIVIA_DIFFICULTY_BY_AGE
from .moderation import moderate_trivia_questions
from .trivia_manager import get_curated_trivia_questions


def apply_trivia_backend_patch(coordinator) -> None:
    """Attach enhanced trivia automation helpers to a coordinator instance."""
    if getattr(coordinator, "_enhanced_trivia_patch_applied", False):
        return

    coordinator._enhanced_trivia_patch_applied = True
    coordinator.trivia_answer_seconds = int(getattr(coordinator, "trivia_answer_seconds", 15) or 15)
    coordinator.trivia_reveal_seconds = int(getattr(coordinator, "trivia_reveal_seconds", 5) or 5)
    coordinator.trivia_auto_cycle_enabled = bool(getattr(coordinator, "trivia_auto_cycle_enabled", True))
    coordinator._trivia_cycle_task = None

    def _cancel_trivia_cycle_task(self) -> None:
        task = getattr(self, "_trivia_cycle_task", None)
        if task and not task.done():
            task.cancel()
        self._trivia_cycle_task = None

    def _questions_remaining_after_current(self) -> bool:
        return int(getattr(self.trivia, "current_index", -1)) < (len(getattr(self.trivia, "questions", [])) - 1)

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
            if getattr(self, "_trivia_cycle_task", None) is current:
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
            if getattr(self, "_trivia_cycle_task", None) is current:
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
            and bool(getattr(self, "trivia_auto_cycle_enabled", True))
            and int(getattr(self, "trivia_reveal_seconds", 5) or 5) > 0
            and self._questions_remaining_after_current()
        ):
            self._trivia_cycle_task = self.hass.async_create_task(
                self._async_trivia_next_question_runner(
                    self.engine.state.round_number,
                    getattr(self.trivia, "current_index", -1),
                    float(int(getattr(self, "trivia_reveal_seconds", 5) or 5)),
                )
            )

    coordinator._cancel_trivia_cycle_task = MethodType(_cancel_trivia_cycle_task, coordinator)
    coordinator._questions_remaining_after_current = MethodType(_questions_remaining_after_current, coordinator)
    coordinator._async_trivia_timeout_runner = MethodType(_async_trivia_timeout_runner, coordinator)
    coordinator._async_trivia_next_question_runner = MethodType(_async_trivia_next_question_runner, coordinator)
    coordinator._sync_trivia_cycle = MethodType(_sync_trivia_cycle, coordinator)

    original_refresh = coordinator.async_refresh_from_engine

    async def async_refresh_from_engine_wrapper(self, *args, **kwargs):
        result = await original_refresh(*args, **kwargs)
        self._sync_trivia_cycle()
        return result

    coordinator.async_refresh_from_engine = MethodType(async_refresh_from_engine_wrapper, coordinator)

    original_reset_lobby = coordinator.async_reset_lobby

    async def async_reset_lobby_wrapper(self, *args, **kwargs):
        self._cancel_trivia_cycle_task()
        return await original_reset_lobby(*args, **kwargs)

    coordinator.async_reset_lobby = MethodType(async_reset_lobby_wrapper, coordinator)

    original_start_trivia_round = coordinator.async_start_trivia_round

    async def async_start_trivia_round_wrapper(self, *args, **kwargs):
        self._cancel_trivia_cycle_task()
        result = await original_start_trivia_round(*args, **kwargs)
        seconds = max(1, int(getattr(self, "trivia_answer_seconds", 15) or 15))
        self.engine.set_round_timer(seconds, time.time() + seconds)
        await original_refresh()
        self._sync_trivia_cycle()
        return result

    coordinator.async_start_trivia_round = MethodType(async_start_trivia_round_wrapper, coordinator)

    original_grade_trivia_round = coordinator.async_grade_trivia_round

    async def async_grade_trivia_round_wrapper(self, *args, **kwargs):
        self._cancel_trivia_cycle_task()
        result = await original_grade_trivia_round(*args, **kwargs)
        self._sync_trivia_cycle()
        return result

    coordinator.async_grade_trivia_round = MethodType(async_grade_trivia_round_wrapper, coordinator)

    original_set_trivia_settings = coordinator.async_set_trivia_settings

    async def async_set_trivia_settings_wrapper(
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
        await original_set_trivia_settings(
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
        self._sync_trivia_cycle()

    coordinator.async_set_trivia_settings = MethodType(async_set_trivia_settings_wrapper, coordinator)

    original_prepare_trivia = coordinator.async_prepare_trivia

    async def async_prepare_trivia_wrapper(
        self,
        *,
        category: str = "fun_facts",
        categories: list[str] | None = None,
        age_range: str,
        difficulty: str | None = None,
        question_count: int = 10,
        source: str = "ai",
    ) -> None:
        category_list = [str(item).strip() for item in (categories or []) if str(item).strip()]
        if not category_list:
            category_list = [str(category or "fun_facts").strip() or "fun_facts"]
        category_list = list(dict.fromkeys(category_list))

        if len(category_list) == 1:
            await original_prepare_trivia(
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

        if source_value != "offline_curated" and self.parental_controls.get("enabled") and self.parental_controls.get("require_ai_approval"):
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
            await original_refresh()
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
        await original_refresh()

    coordinator.async_prepare_trivia = MethodType(async_prepare_trivia_wrapper, coordinator)
