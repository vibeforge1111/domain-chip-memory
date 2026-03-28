from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .contracts import NormalizedQuestion


def normalize_relative_state_anchor_phrase(
    anchor_phrase: str,
    target_predicates: list[str],
    *,
    normalize_value: Callable[[str], str],
) -> str:
    normalized = anchor_phrase.strip().rstrip(".!?")
    if not normalized:
        return normalized
    correction_verbs = "corrected|changed|updated|restored"
    deletion_verbs = "deleted|removed|forgot"
    clause_carry_base_by_verb = {
        "changed": "change",
        "updated": "update",
        "corrected": "correction",
        "restored": "correction",
        "moved": "move",
        "relocated": "relocation",
        "deleted": "deletion",
        "removed": "deletion",
        "forgot": "deletion",
    }
    month_names = (
        "january|february|march|april|may|june|july|august|"
        "september|october|november|december"
    )

    generic_anchor_match = re.match(
        r"^(that\s+(?:earlier|later|first|last)\s+"
        r"(?:change|update|correction|move|relocation|deletion|removal|forget|one))\b",
        normalized,
    )
    if generic_anchor_match:
        generic_anchor = generic_anchor_match.group(1)
        suffix = normalized[generic_anchor_match.end() :].strip()
        if not suffix:
            return generic_anchor
        if re.match(
            rf"^(?:we\s+(?:talked about|mentioned)|in\s+(?:{month_names})(?:\s+\d{{4}})?)$",
            suffix,
        ):
            return generic_anchor
        if generic_anchor.endswith(" one"):
            clause_carry_match = re.match(
                r"^we\s+(changed|updated|corrected|restored|moved|relocated|deleted|removed|forgot)$",
                suffix,
            )
            chronology_clause_carry_match = re.match(
                rf"^we\s+(changed|updated|corrected|restored|moved|relocated|deleted|removed|forgot)"
                rf"\s+(?:in\s+(?:{month_names})(?:\s+\d{{4}})?|later|earlier)$",
                suffix,
            )
            if chronology_clause_carry_match:
                clause_carry_match = chronology_clause_carry_match
            if clause_carry_match:
                modifier_match = re.match(r"^that\s+(earlier|later)\s+one$", generic_anchor)
                if modifier_match:
                    base = clause_carry_base_by_verb.get(clause_carry_match.group(1))
                    if base:
                        return f"that {modifier_match.group(1)} {base}"
                first_last_match = re.match(r"^that\s+(first|last)\s+one$", generic_anchor)
                if first_last_match:
                    return f"{generic_anchor} we {clause_carry_match.group(1)}"
            dense_clause_carry_match = re.match(
                rf"^we\s+(changed|updated|corrected|restored|moved|relocated|deleted|removed|forgot)"
                rf"(?:\s+(?:in\s+(?:{month_names})(?:\s+\d{{4}})?|later|earlier))?"
                rf",\s+and\s+before\s+that\s+(?:earlier|later|first|last)\s+one"
                rf"(?:\s+we\s+(?:changed|updated|corrected|restored|moved|relocated|deleted|removed|forgot)"
                rf"(?:\s+(?:in\s+(?:{month_names})(?:\s+\d{{4}})?|later|earlier))?)?$",
                suffix,
            )
            if dense_clause_carry_match:
                modifier_match = re.match(r"^that\s+(earlier|later)\s+one$", generic_anchor)
                if modifier_match:
                    base = clause_carry_base_by_verb.get(dense_clause_carry_match.group(1))
                    if base:
                        return f"that {modifier_match.group(1)} {base}"
                first_last_match = re.match(r"^that\s+(first|last)\s+one$", generic_anchor)
                if first_last_match:
                    return f"{generic_anchor} we {dense_clause_carry_match.group(1)}"
        if re.match(r"^we\s+(?:changed|updated|corrected|restored|moved|relocated|deleted|removed|forgot)$", suffix):
            return generic_anchor
        if re.match(
            r"^we\s+(?:changed|updated|corrected|restored|moved|relocated|deleted|removed|forgot),\s+and\s+before\s+that\s+"
            r"(?:earlier|later|first|last)\s+one(?:\s+we\s+"
            r"(?:changed|updated|corrected|restored|moved|relocated|deleted|removed|forgot))?$",
            suffix,
        ):
            return generic_anchor

    plain_generic_anchor_match = re.match(
        r"^(that\s+(?:change|update|correction|move|relocation|deletion|removal|forget))\b",
        normalized,
    )
    if plain_generic_anchor_match:
        generic_anchor = plain_generic_anchor_match.group(1)
        suffix = normalized[plain_generic_anchor_match.end() :].strip()
        if not suffix:
            return generic_anchor
        if re.match(
            rf"^(?:in\s+(?:{month_names})(?:\s+\d{{4}})?|later|earlier)$",
            suffix,
        ):
            return generic_anchor

    if re.match(rf"^(?:i\s+)?(?:{deletion_verbs})\s+it$", normalized):
        if "favorite_color" in target_predicates:
            return "forget my favorite color"
        if "preference" in target_predicates:
            return "forget what i prefer"
        if "location" in target_predicates:
            return "forget where i live"
    if "location" in target_predicates and re.match(
        rf"^(?:i\s+)?(?:{deletion_verbs})\s+where\s+i\s+live$",
        normalized,
    ):
        return "forget where i live"

    if "favorite_color" in target_predicates:
        match = re.match(
            rf"^(?:i\s+)?(?:{correction_verbs})\s+it\s+to\s+([a-z0-9 _-]+?)(?:\s+now|\s+again)?$",
            normalized,
        )
        if match:
            return f"my favorite color is {normalize_value(match.group(1).lower())}"
    if "preference" in target_predicates:
        match = re.match(
            rf"^(?:i\s+)?(?:{correction_verbs})\s+it\s+to\s+([a-z0-9 _-]+?)(?:\s+now|\s+again)?$",
            normalized,
        )
        if match:
            return f"i prefer {normalize_value(match.group(1).lower())}"
    return normalized


def extract_relative_state_anchor(
    question_lower: str,
    *,
    normalize_relative_state_anchor_phrase: Callable[[str, list[str]], str],
) -> tuple[str | None, str, list[str]]:
    for prefix, mode, predicates in (
        ("where did i live before ", "before", ["location"]),
        ("where was i living before ", "before", ["location"]),
        ("where did i live after ", "after", ["location"]),
        ("where was i living after ", "after", ["location"]),
        ("what did i prefer before ", "before", ["preference"]),
        ("what did i prefer after ", "after", ["preference"]),
        ("what was my favorite color before ", "before", ["favorite_color"]),
        ("what was my favourite color before ", "before", ["favorite_color"]),
        ("what was my favorite colour before ", "before", ["favorite_color"]),
        ("what was my favourite colour before ", "before", ["favorite_color"]),
        ("what was my favorite color after ", "after", ["favorite_color"]),
        ("what was my favourite color after ", "after", ["favorite_color"]),
        ("what was my favorite colour after ", "after", ["favorite_color"]),
        ("what was my favourite colour after ", "after", ["favorite_color"]),
    ):
        if question_lower.startswith(prefix):
            anchor_phrase = question_lower[len(prefix):].strip().rstrip(".!?")
            return mode, normalize_relative_state_anchor_phrase(anchor_phrase, predicates), predicates
    for mode, predicate_patterns in (
        (
            "before",
            (
                (r"^before\s+(.+?),\s*where did i live\??$", ["location"]),
                (r"^before\s+(.+?),\s*where was i living\??$", ["location"]),
                (r"^before\s+(.+?),\s*what did i prefer\??$", ["preference"]),
                (r"^before\s+(.+?),\s*what was my favou?rite colou?r\??$", ["favorite_color"]),
            ),
        ),
        (
            "after",
            (
                (r"^after\s+(.+?),\s*where did i live\??$", ["location"]),
                (r"^after\s+(.+?),\s*where was i living\??$", ["location"]),
                (r"^after\s+(.+?),\s*what did i prefer\??$", ["preference"]),
                (r"^after\s+(.+?),\s*what was my favou?rite colou?r\??$", ["favorite_color"]),
            ),
        ),
    ):
        for pattern, predicates in predicate_patterns:
            match = re.match(pattern, question_lower)
            if match:
                anchor_phrase = match.group(1).strip().rstrip(".!?")
                return mode, normalize_relative_state_anchor_phrase(anchor_phrase, predicates), predicates
    return None, "", []


def specialize_clause_carry_first_last_anchor_phrase(
    anchor_phrase: str,
    target_predicates: list[str],
    candidate_entries: list[Any],
    *,
    allow_operation_specialization: bool,
    generic_relative_anchor_candidates: Callable[[str, list[str], list[Any]], list[Any]],
) -> str:
    normalized = anchor_phrase.strip().lower()
    match = re.match(
        r"^that\s+(first|last)\s+one\s+we\s+"
        r"(changed|updated|corrected|restored|moved|relocated|deleted|removed|forgot)$",
        normalized,
    )
    if not match:
        return anchor_phrase

    modifier, verb = match.groups()
    generic_anchor = f"that {modifier} one"
    if not allow_operation_specialization:
        return generic_anchor

    clause_carry_base_by_verb = {
        "changed": "change",
        "updated": "update",
        "corrected": "correction",
        "restored": "correction",
        "moved": "move",
        "relocated": "relocation",
        "deleted": "deletion",
        "removed": "deletion",
        "forgot": "deletion",
    }
    base = clause_carry_base_by_verb.get(verb)
    if not base:
        return generic_anchor

    candidates = generic_relative_anchor_candidates(f"that {base}", target_predicates, candidate_entries)
    if len(candidates) != 1:
        return generic_anchor
    return f"that {modifier} {base}"


def specialize_relative_state_anchor_phrase(
    question: NormalizedQuestion,
    anchor_phrase: str,
    target_predicates: list[str],
    candidate_entries: list[Any],
    *,
    specialize_clause_carry_first_last_anchor_phrase: Callable[..., str],
    has_referential_ambiguity: Callable[[NormalizedQuestion, list[Any]], bool],
) -> str:
    return specialize_clause_carry_first_last_anchor_phrase(
        anchor_phrase,
        target_predicates,
        candidate_entries,
        allow_operation_specialization=not has_referential_ambiguity(question, candidate_entries),
    )
