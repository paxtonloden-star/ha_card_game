from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import re


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


@dataclass
class TriviaSession:
    questions: list[dict[str, Any]] = field(default_factory=list)
    current_index: int = -1
    category: str = "fun_facts"
    age_range: str = "18_plus"
    difficulty: str = "medium"

    @property
    def current_question(self) -> dict[str, Any] | None:
        if 0 <= self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    def as_dict(self) -> dict[str, Any]:
        q = self.current_question or {}
        return {
            "category": self.category,
            "age_range": self.age_range,
            "difficulty": self.difficulty,
            "remaining": max(0, len(self.questions) - max(self.current_index + 1, 0)),
            "current_question": {
                "question": q.get("question"),
                "choices": list(q.get("choices", [])),
                "category": q.get("category", self.category),
                "difficulty": q.get("difficulty", self.difficulty),
                "age_range": q.get("age_range", self.age_range),
            } if q else None,
        }

    def load_questions(self, questions: list[dict[str, Any]], *, category: str, age_range: str, difficulty: str) -> None:
        self.questions = list(questions)
        self.current_index = -1
        self.category = category
        self.age_range = age_range
        self.difficulty = difficulty

    def next_question(self) -> dict[str, Any]:
        if not self.questions:
            raise ValueError("No trivia questions loaded")
        self.current_index += 1
        if self.current_index >= len(self.questions):
            raise ValueError("No trivia questions remaining")
        return self.questions[self.current_index]

    def grade(self, answer: str) -> bool:
        q = self.current_question or {}
        norm_answer = _norm(answer)
        accepted = {_norm(x) for x in q.get("accepted_answers", []) if _norm(x)}
        if norm_answer in accepted:
            return True
        choices = [str(x).strip() for x in q.get("choices", []) if str(x).strip()]
        if len(answer.strip()) == 1 and choices:
            idx = ord(answer.strip().upper()) - 65
            if 0 <= idx < len(choices):
                return _norm(choices[idx]) in accepted
        return False
