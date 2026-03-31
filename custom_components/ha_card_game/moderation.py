
"""Simple parental controls and AI moderation helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re
import time

from .const import PARENTAL_CONTENT_MODES, TRIVIA_CATEGORIES

BANNED_TERMS_BY_MODE = {
    "family_safe": {
        "sex", "sexual", "porn", "nude", "vibrator", "dildo", "drug", "drugs", "cocaine", "meth",
        "kill", "murder", "suicide", "racist", "slur", "blood", "boob", "penis", "vagina", "fart"
    },
    "teen": {
        "porn", "nude", "vibrator", "dildo", "cocaine", "meth", "suicide", "slur"
    },
    "adult": set(),
}

@dataclass
class ModerationResult:
    allowed: bool
    cleaned_text: str
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "cleaned_text": self.cleaned_text, "reasons": list(self.reasons)}

def normalize_parental_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    settings = dict(settings or {})
    mode = str(settings.get("content_mode") or "family_safe").strip().lower()
    if mode not in PARENTAL_CONTENT_MODES:
        mode = "family_safe"
    allowed = settings.get("allowed_trivia_categories")
    if not isinstance(allowed, list) or not allowed:
        allowed = list(TRIVIA_CATEGORIES)
    allowed = [item for item in allowed if item in TRIVIA_CATEGORIES]
    if not allowed:
        allowed = list(TRIVIA_CATEGORIES)
    return {
        "enabled": bool(settings.get("enabled", True)),
        "content_mode": mode,
        "require_ai_approval": bool(settings.get("require_ai_approval", True)),
        "allow_remote_players": bool(settings.get("allow_remote_players", False)),
        "allowed_trivia_categories": allowed,
    }

def moderate_text(text: str, *, content_mode: str = "family_safe") -> ModerationResult:
    cleaned = str(text or "").strip()
    mode = content_mode if content_mode in PARENTAL_CONTENT_MODES else "family_safe"
    banned = BANNED_TERMS_BY_MODE.get(mode, set())
    lowered = cleaned.lower()
    reasons: list[str] = []
    for term in sorted(banned):
        if re.search(r"\b" + re.escape(term) + r"\b", lowered):
            reasons.append(f"Contains blocked term: {term}")
    return ModerationResult(allowed=not reasons, cleaned_text=cleaned, reasons=reasons)

def moderate_deck_payload(payload: dict[str, Any], *, content_mode: str = "family_safe") -> dict[str, Any]:
    prompts, white_cards, issues = [], [], []
    for item in payload.get("prompts", []):
        result = moderate_text(str(item), content_mode=content_mode)
        if result.allowed:
            prompts.append(result.cleaned_text)
        else:
            issues.append({"type": "prompt", "text": str(item), "reasons": result.reasons})
    for item in payload.get("white_cards", []):
        result = moderate_text(str(item), content_mode=content_mode)
        if result.allowed:
            white_cards.append(result.cleaned_text)
        else:
            issues.append({"type": "white_card", "text": str(item), "reasons": result.reasons})
    return {
        **payload,
        "prompts": prompts,
        "white_cards": white_cards,
        "moderation": {
            "content_mode": content_mode,
            "removed_count": len(issues),
            "issues": issues,
            "filtered_at": int(time.time()),
        },
    }

def moderate_trivia_questions(questions: list[dict[str, Any]], *, content_mode: str = "family_safe") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cleaned, issues = [], []
    for item in questions:
        fields = [str(item.get("question", "")), str(item.get("correct_answer", "")), str(item.get("explanation", ""))]
        field_results = [moderate_text(field, content_mode=content_mode) for field in fields if field]
        if all(result.allowed for result in field_results):
            cleaned.append(item)
        else:
            reasons = []
            for result in field_results:
                reasons.extend(result.reasons)
            issues.append({"question": item.get("question", ""), "reasons": sorted(set(reasons))})
    return cleaned, issues
