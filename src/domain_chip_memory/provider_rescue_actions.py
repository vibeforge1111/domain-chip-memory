from __future__ import annotations

import re

from .provider_context_text import QUESTION_STOPWORDS


def did_action_yes_answer(question_lower: str, combined_lower: str) -> str | None:
    if not question_lower.startswith("did "):
        return None

    did_match = re.match(r"did\s+([a-z][a-z'-]*)\s+(.+?)\??$", question_lower)
    if not did_match:
        return None

    subject = did_match.group(1)
    action_phrase = did_match.group(2)
    action_tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", action_phrase)
        if token not in QUESTION_STOPWORDS and len(token) > 2
    ]
    irregular_variants = {
        "make": ("made",),
        "go": ("went",),
        "take": ("took",),
        "see": ("saw",),
        "find": ("found",),
        "run": ("ran",),
        "buy": ("bought",),
        "get": ("got",),
        "feel": ("felt",),
        "have": ("had",),
        "leave": ("left",),
        "write": ("wrote",),
    }
    if subject in combined_lower and action_tokens and all(
        token in combined_lower or any(variant in combined_lower for variant in irregular_variants.get(token, ()))
        for token in action_tokens
    ):
        return "Yes"
    return None
