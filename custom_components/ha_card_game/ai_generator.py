"""AI helpers for pack and trivia generation.

Uses an OpenAI-compatible Responses API when configured. Falls back to a local
rule-based generator so the integration still works for offline demos/tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
import re

import aiohttp

from .const import DEFAULT_AI_ENDPOINT, DEFAULT_AI_MODEL, TRIVIA_CATEGORIES, TRIVIA_DIFFICULTY_BY_AGE


@dataclass
class AISettings:
    enabled: bool = False
    api_key: str = ""
    endpoint: str = DEFAULT_AI_ENDPOINT
    model: str = DEFAULT_AI_MODEL
    use_local_fallback: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "endpoint": self.endpoint,
            "model": self.model,
            "use_local_fallback": self.use_local_fallback,
            "has_api_key": bool(self.api_key),
        }


class AIGenerator:
    def __init__(self, settings: AISettings | None = None) -> None:
        self.settings = settings or AISettings()

    def update_settings(self, **kwargs: Any) -> AISettings:
        for key, value in kwargs.items():
            if value is None or not hasattr(self.settings, key):
                continue
            setattr(self.settings, key, value)
        return self.settings

    async def generate_pack(self, *, theme: str, prompt_count: int = 12, white_count: int = 40, family_friendly: bool = True, age_range: str = "18_plus") -> dict[str, Any]:
        if self.settings.enabled and self.settings.api_key:
            try:
                return await self._generate_pack_remote(theme=theme, prompt_count=prompt_count, white_count=white_count, family_friendly=family_friendly, age_range=age_range)
            except Exception:
                if not self.settings.use_local_fallback:
                    raise
        return self._generate_pack_local(theme=theme, prompt_count=prompt_count, white_count=white_count, family_friendly=family_friendly, age_range=age_range)

    async def generate_trivia(self, *, category: str, age_range: str, difficulty: str | None = None, question_count: int = 10) -> list[dict[str, Any]]:
        difficulty = difficulty or TRIVIA_DIFFICULTY_BY_AGE.get(age_range, "medium")
        if self.settings.enabled and self.settings.api_key:
            try:
                return await self._generate_trivia_remote(category=category, age_range=age_range, difficulty=difficulty, question_count=question_count)
            except Exception:
                if not self.settings.use_local_fallback:
                    raise
        return self._generate_trivia_local(category=category, age_range=age_range, difficulty=difficulty, question_count=question_count)

    async def _generate_pack_remote(self, **kwargs: Any) -> dict[str, Any]:
        instructions = (
            "Return JSON with keys slug,name,description,prompts,white_cards,style. "
            "Prompts should be short fill-in-the-blank black cards for a judge-based party card game. White cards should be concise punchlines. Do not copy any existing commercial card text verbatim. Keep content within the requested family_friendly or age_range boundaries and avoid hateful or exploitative content."
        )
        user_text = json.dumps(kwargs)
        payload = {
            "model": self.settings.model,
            "input": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_text},
            ],
        }
        text = await self._post_json(payload)
        data = self._extract_json(text)
        return {
            "slug": data.get("slug") or self._slugify(kwargs.get("theme", "ai_pack")),
            "name": data.get("name") or f"AI {kwargs.get('theme', 'Pack').title()}",
            "description": data.get("description") or f"AI-generated pack for {kwargs.get('theme', 'custom theme')}",
            "prompts": [str(x).strip() for x in data.get("prompts", []) if str(x).strip()],
            "white_cards": [str(x).strip() for x in data.get("white_cards", []) if str(x).strip()],
            "allow_free_text": True,
            "hand_size": 7,
            "style": "judge_party",
        }

    async def _generate_trivia_remote(self, **kwargs: Any) -> list[dict[str, Any]]:
        instructions = (
            "Return JSON as an array of trivia questions. Each item must include question, correct_answer, "
            "accepted_answers, category, age_range, difficulty, choices, explanation."
        )
        payload = {
            "model": self.settings.model,
            "input": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": json.dumps(kwargs)},
            ],
        }
        text = await self._post_json(payload)
        data = self._extract_json(text)
        items = data if isinstance(data, list) else data.get("questions", [])
        return [self._normalize_question(item, kwargs["category"], kwargs["age_range"], kwargs["difficulty"]) for item in items][: kwargs["question_count"]]

    async def _post_json(self, payload: dict[str, Any]) -> str:
        headers = {"Authorization": f"Bearer {self.settings.api_key}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(self.settings.endpoint, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=45)) as resp:
                resp.raise_for_status()
                data = await resp.json()
        # OpenAI-like responses may surface text in output_text or nested content blocks.
        if isinstance(data, dict):
            if data.get("output_text"):
                return str(data["output_text"])
            for item in data.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"} and content.get("text"):
                        return str(content["text"])
        return json.dumps(data)

    def _generate_pack_local(self, *, theme: str, prompt_count: int, white_count: int, family_friendly: bool, age_range: str) -> dict[str, Any]:
        theme_clean = theme.strip() or "Custom"
        prompts = [
            f"The real reason {theme_clean} night got weird was ____. ",
            f"Nobody expected {theme_clean} to involve ____. ",
            f"At our house, {theme_clean} always means ____. ",
            f"The score doubled when someone added ____. ",
            f"The host banned ____ after the last {theme_clean} round. ",
            f"Remote players joined because of ____. ",
            f"The TV mode reveal needed more ____. ",
            f"The funniest thing to pair with {theme_clean} is ____. ",
            f"I lost the round because I underestimated ____. ",
            f"The Home Assistant dashboard lit up for ____. ",
            f"Our custom preset is basically powered by ____. ",
            f"The couch championship trophy was won by ____. ",
        ][:max(1, prompt_count)]
        base = [
            "button mashing", "retro snacks", "a surprise update", "one last round", "bad Wi-Fi", "an overpowered cheat code",
            "movie quotes", "glow sticks", "a speedrun mindset", "lag spikes", "couch co-op", "a golden buzzer",
            f"{theme_clean.lower()} chaos", "a trivia rabbit hole", "friendly trash talk", "a sudden plot twist", "bonus points",
        ]
        if family_friendly:
            base += ["jellybeans", "marshmallow diplomacy", "a dance break"]
        white_cards = []
        while len(white_cards) < max(3, white_count):
            white_cards.extend(base)
        return {
            "slug": self._slugify(f"ai_{theme_clean}"),
            "name": f"AI {theme_clean.title()}",
            "description": f"Locally generated starter pack for {theme_clean} ({age_range}).",
            "prompts": [p.strip() for p in prompts],
            "white_cards": white_cards[:white_count],
            "allow_free_text": True,
            "hand_size": 7,
            "style": "judge_party",
        }

    def _generate_trivia_local(self, *, category: str, age_range: str, difficulty: str, question_count: int) -> list[dict[str, Any]]:
        category = category if category in TRIVIA_CATEGORIES else "fun_facts"
        seeds = {
            "history": [("Which ancient civilization built the pyramids at Giza?", "Egyptians", ["Egyptians", "Ancient Egyptians"], ["Egyptians", "Romans", "Mayans", "Vikings"], "The pyramids at Giza were built by ancient Egyptians." )],
            "fun_facts": [("What animal's fingerprints are so close to humans that they can confuse investigators?", "Koala", ["Koala", "Koalas"], ["Koala", "Panda", "Otter", "Lemur"], "Koala fingerprints are famously similar to human fingerprints.")],
            "geography": [("What is the largest ocean on Earth?", "Pacific Ocean", ["Pacific", "Pacific Ocean"], ["Atlantic Ocean", "Indian Ocean", "Pacific Ocean", "Arctic Ocean"], "The Pacific Ocean is the largest and deepest ocean on Earth.")],
            "movies": [("Which movie features the quote, 'I'll be back'?", "The Terminator", ["The Terminator", "Terminator"], ["Predator", "The Terminator", "Aliens", "Robocop"], "Arnold Schwarzenegger says it in The Terminator.")],
            "1990s": [("Which handheld virtual pet became a huge fad in the late 1990s?", "Tamagotchi", ["Tamagotchi", "Tamagotchis"], ["Game Boy", "Tamagotchi", "Walkman", "Discman"], "Tamagotchi virtual pets exploded in popularity in the late 1990s.")],
            "2000s": [("Which social network launched in 2004 and later became the biggest in the world?", "Facebook", ["Facebook"], ["MySpace", "Facebook", "Friendster", "Bebo"], "Facebook launched in 2004 and rapidly became dominant.")],
            "2010s": [("Which video app known for short clips merged with Musical.ly in 2018?", "TikTok", ["TikTok"], ["Vine", "Snapchat", "TikTok", "Twitch"], "TikTok absorbed Musical.ly and grew rapidly in the late 2010s.")],
            "computer_games": [("In Minecraft, what material do you need to activate a Nether portal frame?", "Flint and steel", ["Flint and steel", "flint & steel"], ["Torch", "Redstone", "Flint and steel", "Lava bucket"], "A Nether portal frame is lit using flint and steel.")],
        }
        base = seeds[category]
        results = []
        while len(results) < max(1, question_count):
            for q in base:
                results.append(self._normalize_question({
                    "question": q[0],
                    "correct_answer": q[1],
                    "accepted_answers": q[2],
                    "choices": q[3],
                    "explanation": q[4],
                }, category, age_range, difficulty))
                if len(results) >= question_count:
                    break
        return results

    def _normalize_question(self, item: dict[str, Any], category: str, age_range: str, difficulty: str) -> dict[str, Any]:
        correct = str(item.get("correct_answer") or "").strip()
        accepted = [str(x).strip() for x in item.get("accepted_answers", []) if str(x).strip()]
        if correct and correct not in accepted:
            accepted.append(correct)
        choices = [str(x).strip() for x in item.get("choices", []) if str(x).strip()]
        return {
            "question": str(item.get("question") or "").strip(),
            "correct_answer": correct,
            "accepted_answers": accepted,
            "choices": choices,
            "explanation": str(item.get("explanation") or "").strip(),
            "category": str(item.get("category") or category),
            "age_range": str(item.get("age_range") or age_range),
            "difficulty": str(item.get("difficulty") or difficulty),
        }

    def _extract_json(self, text: str) -> Any:
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
            if not match:
                raise ValueError("AI response did not contain valid JSON")
            return json.loads(match.group(1))

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        return slug or "ai_generated"
