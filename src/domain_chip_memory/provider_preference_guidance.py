from __future__ import annotations


def looks_like_preference_guidance_question(question: str) -> bool:
    question_lower = question.lower()
    first_person_question = question_lower.startswith(("i ", "i'", "i’m", "i'm", "ive", "im ")) or any(
        marker in question_lower for marker in (" i ", " my ", " i've", " i'm", " ive", " im ")
    )
    if question_lower.startswith(("can you recommend", "can you suggest", "what should i serve")):
        return True
    if (
        any(token in question_lower for token in ("recommend", "suggest"))
        and first_person_question
        and not question_lower.startswith(("what did", "which", "who", "when", "where"))
    ):
        return True
    if any(
        phrase in question_lower
        for phrase in (
            "any tips",
            "any advice",
            "any suggestions",
            "any ideas",
            "any recommendations",
            "helpful tips",
            "what do you think",
            "do you think",
            "could there be a reason",
        )
    ):
        return True
    return False
