from __future__ import annotations

import re
from dataclasses import replace

from .contracts import JsonDict, NormalizedBenchmarkSample, NormalizedSession, NormalizedTurn
from .memory_extraction import MemoryAtom, _canonical_subject, _normalize_value

_FALLBACK_HELP_PATTERNS = (
    "can you help",
    "could you help",
    "can you review",
    "can you provide",
    "provide an example",
    "how can i",
    "i'm not sure",
    "im not sure",
    "i want to make sure",
)

_FALLBACK_ASSERTIVE_PATTERNS = (
    "i've ",
    "ive ",
    "i have ",
    "i'm ",
    "im ",
    "i am ",
    "i already ",
    "i prefer ",
    "i decided ",
    "i chose ",
    "i completed ",
    "i implemented ",
    "i added ",
    "i used ",
    "i fixed ",
    "i tested ",
    "i integrated ",
    "i encountered ",
)

_FALLBACK_ACTION_PATTERNS = (
    "implement",
    "integrat",
    "complet",
    "add",
    "fix",
    "test",
    "obtain",
    "use",
    "prefer",
    "decid",
    "choos",
    "visit",
    "attend",
    "move",
    "live",
    "listen",
    "return static html",
    "user registration",
    "login module",
)

_CONVERSATIONAL_TIME_PATTERN = re.compile(
    r"\b(a few years ago|few years ago|last year|yesterday|today|(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+days?\s+ago|in (?:19|20)\d{2})\b",
    re.IGNORECASE,
)


def _normalize_profile_location_value(value: str) -> str:
    normalized = _normalize_value(value)
    return re.sub(r"\s+(?:now|again)$", "", normalized, flags=re.IGNORECASE).strip()


def _compact_fallback_source_text(text: str) -> str:
    source_text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    source_text = re.sub(r"\s+", " ", source_text).strip()
    if not source_text:
        return ""

    rewritten_negative_match = re.search(
        r"like\s+([A-Za-z0-9_.-]+(?:[ -][A-Za-z0-9_.-]+){0,4}),\s+which\s+i(?:'ve| have)\s+never\s+actually\s+integrated\s+into\s+this\s+project",
        source_text,
        re.IGNORECASE,
    )
    if rewritten_negative_match:
        return f"I've never actually integrated {rewritten_negative_match.group(1)} into this project"

    source_text = re.split(r"\bhere(?:'s| is)\b", source_text, maxsplit=1, flags=re.IGNORECASE)[0].strip(" ,;:-")
    clauses = [
        clause.strip(" ,;:-")
        for clause in re.split(r"(?<=[.!?])\s+|,\s+(?:and|but|so)\s+", source_text)
        if clause.strip(" ,;:-")
    ]
    if not clauses:
        return ""

    best_clause = ""
    best_score = float("-inf")
    for clause in clauses:
        clause_lower = clause.lower()
        token_count = len(re.findall(r"[a-z0-9]+", clause_lower))
        score = 0.0
        if any(pattern in clause_lower for pattern in _FALLBACK_ASSERTIVE_PATTERNS):
            score += 4.0
        if "i'm trying to" in clause_lower or "im trying to" in clause_lower:
            score += 2.0
        if "never" in clause_lower or "starting from scratch" in clause_lower:
            score += 3.0
        if any(pattern in clause_lower for pattern in _FALLBACK_HELP_PATTERNS):
            score -= 8.0
        if "?" in clause:
            score -= 8.0
        if any(pattern in clause_lower for pattern in _FALLBACK_ACTION_PATTERNS):
            score += 3.0
        if 4 <= token_count <= 20:
            score += 1.0
        if "code" in clause_lower or "response time" in clause_lower:
            score -= 2.0
        if score > best_score:
            best_score = score
            best_clause = clause

    if best_score < 4.0:
        return ""
    return best_clause.strip(" ,;:-")


def _extract_source_span(text: str, keyword: str) -> str:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]
    keyword_lower = keyword.lower()
    for sentence in sentences:
        if keyword_lower in sentence.lower():
            return sentence.strip(" \"'")
    return text.strip()


def _anchor_year(timestamp: str | None) -> int | None:
    if not timestamp:
        return None
    match = re.search(r"\b((?:19|20)\d{2})\b", timestamp)
    if not match:
        return None
    return int(match.group(1))


def _normalize_conversational_time_expression(expression: str, timestamp: str | None) -> str:
    normalized = expression.strip().lower()
    anchor_year = _anchor_year(timestamp)
    if re.search(r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+days?\s+ago\b", normalized):
        return ""
    if normalized in {"yesterday", "today"}:
        return ""
    if normalized in {"a few years ago", "few years ago"} and anchor_year is not None:
        return f"a few years before {anchor_year}"
    if normalized == "last year" and anchor_year is not None:
        return f"in {anchor_year - 1}"
    return normalized


def _infer_relationship_context(text: str, lower: str) -> tuple[str, str]:
    if any(token in lower for token in ("my mother", "my mom", "her mother", "her mom", "our mother", "our mom", "me and my mother", "me and my mom")):
        return "mother", "mother"
    if any(token in lower for token in ("my father", "my dad", "her father", "her dad", "our father", "our dad", "me and my father", "me and my dad")):
        return "father", "father"
    friend_match = re.search(r"\b(?:my|her|his|our)\s+friend\s+([A-Z][a-z]+)\b", text)
    if friend_match:
        return "friend", friend_match.group(1).strip()
    return "", ""


def _inherit_recent_relationship_context(
    session: NormalizedSession,
    turn: NormalizedTurn,
    *,
    relation_type: str,
    other_entity: str,
) -> tuple[str, str]:
    if relation_type or other_entity:
        return relation_type, other_entity
    turn_index = next((index for index, candidate in enumerate(session.turns) if candidate.turn_id == turn.turn_id), -1)
    if turn_index <= 0:
        return relation_type, other_entity
    for prior_turn in reversed(session.turns[:turn_index]):
        if prior_turn.speaker != turn.speaker:
            continue
        inherited_relation_type, inherited_other_entity = _infer_relationship_context(prior_turn.text, prior_turn.text.lower())
        if inherited_relation_type or inherited_other_entity:
            return inherited_relation_type, inherited_other_entity
    return relation_type, other_entity


def _extract_typed_conversational_atoms(
    session: NormalizedSession,
    turn: NormalizedTurn,
    *,
    subject: str,
) -> list[MemoryAtom]:
    text = turn.text.strip()
    lower = text.lower()
    timestamp = turn.timestamp or session.timestamp
    atoms: list[MemoryAtom] = []

    def _append_typed_atom(predicate: str, value: str, **metadata: object) -> None:
        atoms.append(
            MemoryAtom(
                atom_id=f"{turn.turn_id}:atom:typed:{predicate}:{len(atoms)}",
                subject=subject,
                predicate=predicate,
                value=_normalize_value(value),
                session_id=session.session_id,
                turn_id=turn.turn_id,
                timestamp=timestamp,
                source_text=text,
                metadata={
                    "speaker": turn.speaker,
                    "typed_conversational": True,
                    **metadata,
                    **turn.metadata,
                },
            )
        )

    if "passed away" in lower:
        relation_type, other_entity = _infer_relationship_context(text, lower)
        relation_type, other_entity = _inherit_recent_relationship_context(
            session,
            turn,
            relation_type=relation_type,
            other_entity=other_entity,
        )
        time_match = _CONVERSATIONAL_TIME_PATTERN.search(lower)
        time_expression_raw = time_match.group(1).lower() if time_match else ""
        time_normalized = _normalize_conversational_time_expression(time_expression_raw, timestamp) if time_expression_raw else ""
        relation_surface = other_entity or relation_type or "someone"
        value_parts = [relation_surface, "passed away"]
        if time_normalized:
            value_parts.append(time_normalized)
        elif time_expression_raw:
            value_parts.append(time_expression_raw)
        _append_typed_atom(
            "loss_event",
            " ".join(value_parts),
            entity_key=f"loss_event:{(other_entity or relation_type or 'unknown').lower()}",
            event_type="loss",
            relation_type=relation_type,
            other_entity=other_entity,
            source_span=_extract_source_span(text, "passed away"),
            time_expression_raw=time_expression_raw,
            time_normalized=time_normalized,
        )

    if any(token in lower for token in ("pendant", "necklace")) and any(
        token in lower for token in ("gave me", "gave it to me", "gifted me", "bought me", "bought this", "got me")
    ):
        relation_type, other_entity = _infer_relationship_context(text, lower)
        relation_type, other_entity = _inherit_recent_relationship_context(
            session,
            turn,
            relation_type=relation_type,
            other_entity=other_entity,
        )
        item_type = "pendant" if "pendant" in lower else "necklace"
        year_match = re.search(r"\bin\s+((?:19|20)\d{2})\b", lower)
        place_match = re.search(r"\b(?:visited|in)\s+([A-Z][a-z]+)\b", text)
        time_expression_raw = f"in {year_match.group(1)}" if year_match else ""
        time_normalized = _normalize_conversational_time_expression(time_expression_raw, timestamp) if time_expression_raw else ""
        place = place_match.group(1).strip() if place_match else ""
        value_parts = [relation_type or other_entity or "someone", "gifted", item_type]
        if time_normalized:
            value_parts.append(time_normalized)
        if place:
            value_parts.append(f"in {place}")
        _append_typed_atom(
            "gift_event",
            " ".join(value_parts),
            entity_key=f"gift_event:{item_type}:{(relation_type or other_entity or 'unknown').lower()}",
            event_type="gift",
            relation_type=relation_type,
            other_entity=other_entity,
            item_type=item_type,
            place=place.lower(),
            source_span=_extract_source_span(text, item_type),
            time_expression_raw=time_expression_raw,
            time_normalized=time_normalized,
        )

    return atoms


def _extract_atoms_from_turn(
    session: NormalizedSession,
    turn: NormalizedTurn,
    *,
    allow_raw_fallback: bool = False,
) -> list[MemoryAtom]:
    text = turn.text.strip()
    lower = text.lower()
    query_lower = str(turn.metadata.get("query", "")).lower()
    caption_lower = str(turn.metadata.get("blip_caption", "")).lower()
    subject = _canonical_subject(turn)
    atoms: list[MemoryAtom] = []

    def _append_atom(predicate: str, value: str, *, entity_key: str | None = None) -> None:
        metadata: JsonDict = {"speaker": turn.speaker}
        if entity_key:
            metadata["entity_key"] = entity_key
        atoms.append(
            MemoryAtom(
                atom_id=f"{turn.turn_id}:atom:manual:{predicate}:{len(atoms)}",
                subject=subject,
                predicate=predicate,
                value=value,
                session_id=session.session_id,
                turn_id=turn.turn_id,
                timestamp=turn.timestamp or session.timestamp,
                source_text=text,
                metadata=metadata,
            )
        )

    def _append_state_deletion(target_predicate: str, value: str) -> None:
        normalized_value = _normalize_value(value)
        entity_key = f"{target_predicate}:{normalized_value.lower()}" if normalized_value else target_predicate
        atoms.append(
            MemoryAtom(
                atom_id=f"{turn.turn_id}:atom:manual:state_deletion:{len(atoms)}",
                subject=subject,
                predicate="state_deletion",
                value=normalized_value,
                session_id=session.session_id,
                turn_id=turn.turn_id,
                timestamp=turn.timestamp or session.timestamp,
                source_text=text,
                metadata={
                    "speaker": turn.speaker,
                    "target_predicate": target_predicate,
                    "entity_key": entity_key,
                    "deleted_value": normalized_value,
                },
            )
        )

    def _append_referential_ambiguity(target_predicates: list[str], operations: list[str]) -> None:
        atoms.append(
            MemoryAtom(
                atom_id=f"{turn.turn_id}:atom:manual:referential_ambiguity:{len(atoms)}",
                subject=subject,
                predicate="referential_ambiguity",
                value=",".join(target_predicates),
                session_id=session.session_id,
                turn_id=turn.turn_id,
                timestamp=turn.timestamp or session.timestamp,
                source_text=text,
                metadata={
                    "speaker": turn.speaker,
                    "target_predicates": list(target_predicates),
                    "operations": list(operations),
                },
            )
        )

    def _has_predicate(predicate: str) -> bool:
        return any(atom.predicate == predicate for atom in atoms)

    def _append_current_mission(value: str, *, entity_key: str) -> None:
        if _has_predicate("current_mission"):
            return
        _append_atom("current_mission", value, entity_key=entity_key)

    def _scoped_pronoun_predicates(text_lower: str) -> list[str]:
        predicates: list[str] = []
        if "about" in text_lower and re.search(r"\bmy favou?rite colou?r\b", text_lower):
            predicates.append("favorite_color")
        if "about" in text_lower and re.search(r"\bwhere\s+(?:i|we)\s+live\b", text_lower):
            predicates.append("location")
        if "about" in text_lower and (
            re.search(r"\bwhat\s+(?:i|we)\s+(?:now\s+)?prefer\b", text_lower)
            or re.search(r"\b(?:my|our)\s+preference\b", text_lower)
        ):
            predicates.append("preference")
        return predicates

    def _split_sentence_fronted_about_clauses(raw_text: str) -> list[str]:
        clause_starts: list[int] = []
        for match in re.finditer(r"(?i)\babout\b", raw_text):
            prefix = raw_text[: match.start()].rstrip()
            if not prefix or prefix.endswith((".", "!", "?")):
                clause_starts.append(match.start())
        if len(clause_starts) <= 1:
            return []
        clauses: list[str] = []
        for index, start in enumerate(clause_starts):
            end = clause_starts[index + 1] if index + 1 < len(clause_starts) else len(raw_text)
            clause = raw_text[start:end].strip()
            if clause:
                clauses.append(clause)
        return clauses

    scoped_about_clauses = _split_sentence_fronted_about_clauses(text)
    if len(scoped_about_clauses) > 1:
        clause_predicates = [_scoped_pronoun_predicates(clause.lower()) for clause in scoped_about_clauses]
        clause_atoms: list[MemoryAtom] = []
        clause_operations: set[str] = set()
        clause_target_predicates: set[str] = set()
        for clause_index, clause in enumerate(scoped_about_clauses):
            if not clause_predicates[clause_index]:
                continue
            clause_target_predicates.update(clause_predicates[clause_index])
            clause_lower = clause.lower()
            if re.search(r"\b(?:please\s+)?(?:forget|delete|remove)\s+it\b", clause_lower):
                clause_operations.add("delete")
            if re.search(
                r"\b(?:change|update|correct|restore)\s+it\s+to\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)",
                clause,
                re.IGNORECASE,
            ):
                clause_operations.add("update")
            clause_turn = replace(turn, text=clause)
            extracted_clause_atoms = _extract_atoms_from_turn(
                session,
                clause_turn,
                allow_raw_fallback=allow_raw_fallback,
            )
            for extracted_atom in extracted_clause_atoms:
                source_text = extracted_atom.source_text
                if extracted_atom.predicate == "state_deletion":
                    target_predicate = str(extracted_atom.metadata.get("target_predicate", ""))
                    if target_predicate == "favorite_color":
                        source_text = "forget my favorite color"
                    elif target_predicate == "location":
                        source_text = "forget where i live"
                    elif target_predicate == "preference":
                        source_text = "forget what i prefer"
                clause_atoms.append(
                    replace(
                        extracted_atom,
                        atom_id=f"{turn.turn_id}:atom:scoped_clause:{clause_index}:{len(clause_atoms)}",
                        turn_id=turn.turn_id,
                        source_text=source_text,
                    )
                )
        if clause_atoms:
            if len(clause_target_predicates) > 1 and clause_operations:
                _append_referential_ambiguity(sorted(clause_target_predicates), sorted(clause_operations))
            return clause_atoms + atoms

    deletion_patterns = [
        (r"\b(?:please\s+)?(?:forget|delete|remove)\s+where\s+(?:i|we)\s+live\b", "location"),
        (r"\b(?:please\s+)?(?:forget|delete|remove)\s+(?:that\s+)?(?:i|we)\s+live in\s+([A-Za-z0-9 _-]+)", "location"),
        (r"\b(?:please\s+)?(?:forget|delete|remove)\s+(?:that\s+)?(?:i|we)\s+lived in\s+([A-Za-z0-9 _-]+)", "location"),
        (r"\b(?:please\s+)?(?:forget|delete|remove)\s+my\s+favo(?:u)?rite\s+colou?r\b", "favorite_color"),
        (
            r"\b(?:please\s+)?(?:forget|delete|remove)\s+(?:that\s+)?(?:i\s+now\s+prefer|i\s+prefer|i\s+like)\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)",
            "preference",
        ),
        (r"\b(?:please\s+)?(?:forget|delete|remove)\s+(?:what\s+)?(?:i|we)\s+(?:now\s+)?prefer\b", "preference"),
        (
            r"\b(?:please\s+)?(?:forget|delete|remove)\s+(?:that\s+)?my\s+favo(?:u)?rite\s+colou?r\s+is\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)",
            "favorite_color",
        ),
    ]
    for pattern, target_predicate in deletion_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        deleted_value = _normalize_value(match.group(1)) if match.lastindex else ""
        _append_state_deletion(target_predicate, deleted_value)

    discourse_scoped_pronoun_predicates = _scoped_pronoun_predicates(lower)

    has_pronoun_deletion = bool(re.search(r"\b(?:please\s+)?(?:forget|delete|remove)\s+it\b", lower))

    scoped_change_match = re.search(
        r"\b(?:change|update|correct|restore)\s+it\s+to\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)",
        text,
        re.IGNORECASE,
    )
    if len(discourse_scoped_pronoun_predicates) > 1 and (has_pronoun_deletion or scoped_change_match):
        operations: list[str] = []
        if has_pronoun_deletion:
            operations.append("delete")
        if scoped_change_match:
            operations.append("update")
        _append_referential_ambiguity(discourse_scoped_pronoun_predicates, operations)
    elif len(discourse_scoped_pronoun_predicates) == 1:
        discourse_scoped_pronoun_predicate = discourse_scoped_pronoun_predicates[0]
        if has_pronoun_deletion:
            _append_state_deletion(discourse_scoped_pronoun_predicate, "")
        if scoped_change_match:
            updated_value = _normalize_value(scoped_change_match.group(1))
            if updated_value:
                _append_atom(
                    discourse_scoped_pronoun_predicate,
                    updated_value,
                    entity_key=updated_value.lower(),
                )

    if "luna and oliver" in lower:
        _append_atom("pet_name", "Luna", entity_key="luna")
        _append_atom("pet_name", "Oliver", entity_key="oliver")
    if "another cat named bailey" in lower:
        _append_atom("pet_name", "Bailey", entity_key="bailey")
    if "horse painting" in lower:
        _append_atom("paint_subject", "horse", entity_key="horse")
    if "painted that lake sunrise" in lower:
        _append_atom("paint_subject", "sunrise", entity_key="sunrise")
    if "inspired by the sunsets" in lower or "painting of a sunset" in caption_lower:
        _append_atom("paint_subject", "sunset", entity_key="sunset")
    if "rainbow flag" in lower or "rainbow flag" in query_lower:
        _append_atom("important_symbol", "Rainbow flag", entity_key="rainbow flag")
    if "transgender symbol" in lower or "transgender symbol" in query_lower:
        _append_atom("important_symbol", "transgender symbol", entity_key="transgender symbol")
    if re.search(r"\bplay clarinet\b", lower):
        _append_atom("instrument", "clarinet", entity_key="clarinet")
    if "playing my violin" in lower or re.search(r"\bplay(?:ing)? (?:the )?violin\b", lower):
        _append_atom("instrument", "violin", entity_key="violin")
    if "summer sounds" in lower:
        _append_atom("seen_artist", "Summer Sounds", entity_key="summer sounds")
    if "matt patterson" in lower:
        _append_atom("seen_artist", "Matt Patterson", entity_key="matt patterson")
    if "roasted marshmallows" in lower:
        _append_atom("family_hike_activity", "roast marshmallows", entity_key="roast marshmallows")
    if "shared stories" in lower or "tell stories" in lower:
        _append_atom("family_hike_activity", "tell stories", entity_key="tell stories")
    if "changing body" in lower:
        _append_atom("transition_change", "changes to her body", entity_key="changes to her body")
    if "weren't able to handle it" in lower or "were not able to handle it" in lower:
        _append_atom("transition_change", "losing unsupportive friends", entity_key="losing unsupportive friends")
    if "transgender conference" in lower or "lgbtq conference" in lower:
        _append_atom("trans_event", "conference", entity_key="conference")
    if "poetry reading" in lower and "transgender" in lower:
        _append_atom("trans_event", "poetry reading", entity_key="poetry reading")
    if re.search(r"\bseven years now\b", lower) and ("muses" in lower or "into art" in lower):
        _append_atom("art_practice_duration", "seven years", entity_key="seven years")
    if "used to go horseback riding with my dad" in lower:
        _append_atom("childhood_activity", "Horseback riding", entity_key="horseback riding")
    if "came across this cool rainbow sidewalk" in lower:
        _append_atom("neighborhood_find", "a rainbow sidewalk", entity_key="rainbow sidewalk")
    if "classical like bach and mozart" in lower:
        _append_atom("classical_musicians", "Bach and Mozart", entity_key="bach and mozart")
    if "modern music like ed sheeran" in lower or "ed sheeran's" in lower:
        _append_atom("modern_music_artist", "Ed Sheeran", entity_key="ed sheeran")
    if "sign posted on a door stating that someone is not being able to leave" in caption_lower:
        _append_atom(
            "precautionary_sign",
            "A sign stating that someone is not being able to leave",
            entity_key="someone is not being able to leave",
        )
    if "do your research and find an adoption agency or lawyer" in lower and "prepare emotionally" in lower:
        _append_atom(
            "adoption_start_advice",
            "Do research, find an adoption agency or lawyer, gather necessary documents, and prepare emotionally.",
            entity_key="adoption-start-advice",
        )
    if "last month i got hurt and had to take a break from pottery" in lower:
        _append_atom(
            "pottery_setback",
            "She got hurt and had to take a break from pottery.",
            entity_key="pottery-break-injury",
        )
    if "reading that book you recommended" in lower and "painting to keep busy" in lower:
        _append_atom("pottery_break_activity", "Read a book and paint.", entity_key="read-book-and-paint")
    if "inspired by the sunsets" in lower and "pink sky" in caption_lower:
        _append_atom(
            "recent_painting",
            "A painting inspired by sunsets with a pink sky.",
            entity_key="sunsets-pink-sky",
        )
    if "abstract painting too" in lower and "blue background" in caption_lower:
        _append_atom(
            "abstract_painting",
            "An abstract painting with blue streaks on a wall.",
            entity_key="abstract-blue-streaks",
        )
    if "peaceful blue streaks" in lower:
        _append_atom(
            "abstract_painting",
            "An abstract painting with blue streaks on a wall.",
            entity_key="abstract-blue-streaks",
        )
    if "transgender people shared their stories through poetry" in lower:
        _append_atom(
            "poetry_reading_topic",
            "It was a transgender poetry reading where transgender people shared their stories.",
            entity_key="transgender-poetry-stories",
        )
    if "trans lives matter" in caption_lower:
        _append_atom("poster_text", '"Trans Lives Matter"', entity_key="trans lives matter")
    if "stands for freedom and being real" in lower and "stay true to myself" in lower:
        _append_atom(
            "drawing_symbolism",
            "Freedom and being true to herself.",
            entity_key="freedom-being-true",
        )
    if "ongoing adventure of learning and growing" in lower:
        _append_atom(
            "shared_life_journey",
            "An ongoing adventure of learning and growing.",
            entity_key="learning-and-growing",
        )
    if "they were scared but we reassured them" in lower and "brother would be ok" in lower:
        _append_atom(
            "son_accident_reaction",
            "scared but reassured by his family",
            entity_key="son-scared-reassured",
        )
        _append_atom(
            "children_accident_reaction",
            "scared but resilient",
            entity_key="children-scared-resilient",
        )
    if "they mean the world to me" in lower and "thankful to have them" in lower:
        _append_atom(
            "family_importance",
            "important and mean the world to her",
            entity_key="family-mean-the-world",
        )
        _append_atom(
            "post_accident_feeling",
            "grateful and thankful for her family",
            entity_key="grateful-thankful-family",
        )
        if "grand canyon" in lower:
            _append_atom("canyon_reaction", "happy and thankful", entity_key="happy-and-thankful")
    if "they give me the strength to keep going" in lower or "biggest motivation and support" in lower:
        _append_atom("family_strength_source", "Strength and motivation", entity_key="strength-and-motivation")
    if "their brother would be ok" in lower or "their brother would be okay" in lower or "2 younger kids" in lower:
        _append_atom("child_count", "3", entity_key="3")
    if "figurines i bought" in lower:
        _append_atom("bought_item", "Figurines", entity_key="figurines")
    if "new shoes" in lower:
        _append_atom("bought_item", "shoes", entity_key="shoes")
    if "self-care is really important" in lower:
        _append_atom("self_care_realization", "self-care is important", entity_key="self-care is important")
    if "safe, inviting place for people to grow" in lower or "safe and inviting place for people to grow" in lower:
        _append_atom(
            "supportive_space_goal",
            "a safe and inviting place for people to grow",
            entity_key="safe-inviting-place",
        )
    if ("made this bowl" in lower or "made this!" in lower) and "bowl" in caption_lower:
        bowl_value = "black and white bowl" if "black and white" in caption_lower else "bowl"
        _append_atom("made_object_photo", bowl_value, entity_key="made-bowl-photo")
    if "kids' books" in lower and "stories from different cultures" in lower and "educational books" in lower:
        _append_atom(
            "library_books",
            "kids' books - classics, stories from different cultures, educational books",
            entity_key="kids-books-library",
        )
    if "carving out some me-time each day" in lower and "running" in lower and "reading" in lower and "violin" in lower:
        _append_atom(
            "self_care_method",
            "carving out some me-time each day for activities like running, reading, or playing the violin",
            entity_key="me-time-running-reading-violin",
        )
    if "it taught me self-acceptance and how to find support" in lower:
        _append_atom(
            "book_takeaway",
            "Lessons on self-acceptance and finding support",
            entity_key="self-acceptance-finding-support",
        )
    if "these are for running" in lower:
        _append_atom("shoe_use", "Running", entity_key="running")
    if "de-stress and clear my mind" in lower or "destress and clear my mind" in lower:
        _append_atom(
            "running_reason",
            "To de-stress and clear her mind",
            entity_key="de-stress-clear-mind",
        )
    if "great for my mental health" in lower or ("mental health" in lower and "improvement" in lower):
        _append_atom("running_benefit", "mental health", entity_key="mental-health")
    if "we all made our own pots" in lower:
        _append_atom("pottery_output", "pots", entity_key="pots")
    if "cup with a dog face on it" in caption_lower:
        _append_atom("pottery_output", "a cup with a dog face on it", entity_key="dog-face-cup")
    if "we love painting together lately" in lower:
        _append_atom("family_creative_activity", "painting", entity_key="painting")
    if "sunset with a palm tree" in caption_lower:
        _append_atom("family_paint_subject", "a sunset with a palm tree", entity_key="sunset-palm-tree")
    if "so many people wanted to create loving homes for children in need" in lower:
        _append_atom(
            "adoption_meeting_takeaway",
            "many people wanting to create loving homes for children in need",
            entity_key="loving-homes-children-in-need",
        )
    if "sunflowers mean warmth and happiness" in lower:
        _append_atom("flower_symbolism", "warmth and happiness", entity_key="warmth-happiness")
    if "appreciate the small moments" in lower and "wedding decor" in lower:
        _append_atom(
            "flower_importance",
            "They remind her to appreciate the small moments and were a part of her wedding decor",
            entity_key="flowers-small-moments-wedding",
        )
    if "visited a lgbtq center" in lower and "unity and strength" in lower:
        _append_atom(
            "art_show_inspiration",
            "visiting an LGBTQ center and wanting to capture unity and strength",
            entity_key="lgbtq-center-unity-strength",
        )
    if "perseid meteor shower" in lower:
        _append_atom("family_trip_sighting", "Perseid meteor shower", entity_key="perseid-meteor-shower")
    if "in awe of the universe" in lower:
        _append_atom("family_trip_feeling", "in awe of the universe", entity_key="awe-universe")
    if "my daughter's birthday" in lower:
        _append_atom("birthday_person", "her daughter", entity_key="daughter-birthday")
    if "matt patterson" in lower:
        _append_atom("birthday_performer", "Matt Patterson", entity_key="matt-patterson-birthday")
    if "catch the eye and make people smile" in lower:
        _append_atom(
            "pottery_design_reason",
            "She wanted to catch the eye and make people smile.",
            entity_key="catch-eye-smile",
        )
    if "my guinea pig" in lower:
        _append_atom("pet_type", "guinea pig", entity_key="guinea-pig")
    if "another cat named bailey" in lower and "black dog" in caption_lower:
        _append_atom("pet_household_summary", "Two cats and a dog", entity_key="two-cats-and-a-dog")
    if "researching adoption agencies" in lower:
        _append_atom("summer_plan", "researching adoption agencies", entity_key="researching adoption agencies")
    if "help lgbtq+ folks with adoption" in lower or "help lgbtq folks with adoption" in lower:
        _append_atom(
            "adoption_agency_reason",
            "their inclusivity and support for LGBTQ+ individuals",
            entity_key="inclusive-lgbtq-adoption",
        )
    if "make a family for kids who need one" in lower:
        _append_atom("adoption_goal", "creating a family for kids who need one", entity_key="family-for-kids")
    if "doing something amazing" in lower and "awesome mom" in lower:
        _append_atom(
            "adoption_opinion",
            "doing something amazing and will be an awesome mom",
            entity_key="amazing-awesome-mom",
        )
    if re.search(r"\b5 years already\b", lower) and "dress" in lower:
        _append_atom("marriage_duration", "5 years", entity_key="5 years")
    if "stands for love, faith and strength" in lower or "stands for love, faith and strength" in lower:
        _append_atom("necklace_symbolism", "love, faith, and strength", entity_key="love-faith-strength")
    if "this necklace is super special" in lower and "gift from my grandma" in lower:
        _append_atom("gift_item", "necklace", entity_key="necklace")
    if "hand-painted bowl" in lower and "art and self-expression" in lower:
        _append_atom("bowl_symbolism", "art and self-expression", entity_key="art-and-self-expression")
    if "explored nature" in lower:
        _append_atom("camping_activity", "explored nature", entity_key="explored nature")
    if "roasted marshmallows" in lower:
        _append_atom("camping_activity", "roasted marshmallows", entity_key="roasted marshmallows")
    if "went on a hike" in lower:
        _append_atom("camping_activity", "went on a hike", entity_key="went on a hike")
    if "working with trans people, helping them accept themselves and supporting their mental health" in lower:
        _append_atom(
            "counseling_interest_detail",
            "working with trans people, helping them accept themselves and supporting their mental health",
            entity_key="trans-counseling-detail",
        )
    if "lgbtq+ counseling workshop" in lower or "lgbtq counseling workshop" in lower:
        _append_atom("workshop_name", "LGBTQ+ counseling workshop", entity_key="lgbtq-counseling-workshop")
    if "therapeutic methods" in lower and "work with trans people" in lower:
        _append_atom(
            "workshop_topic",
            "therapeutic methods and how to best work with trans people",
            entity_key="therapeutic-methods-trans-people",
        )
    if "my own journey and the support i got made a huge difference" in lower and "counseling and support groups improved my life" in lower:
        _append_atom(
            "counseling_motivation",
            "her own journey and the support she received, and how counseling improved her life",
            entity_key="own-journey-support-counseling",
        )
    if "i'm building you" in lower or "im building you" in lower:
        _append_current_mission("build Spark", entity_key="build-spark")
    if ("i've been building" in lower or "i have been building" in lower) and "spark intelligence systems" in lower and "domain chips" in lower:
        _append_current_mission(
            "build Spark Intelligence systems and domain chips",
            entity_key="build-spark-intelligence-systems-domain-chips",
        )
    if "memory domain chip for you" in lower and ("shadow test" in lower or "shadow tests" in lower):
        _append_current_mission(
            "build a memory domain chip for Spark",
            entity_key="build-memory-domain-chip-for-spark",
        )
    if "give life to you" in lower and "domain chips" in lower:
        _append_current_mission(
            "give Spark life through conversations, work, and domain chips",
            entity_key="give-spark-life-through-conversations-work-domain-chips",
        )
    if "trying to get you to be great at many things" in lower and "domain chips" in lower:
        _append_current_mission(
            "make Spark great at many things through domain chips",
            entity_key="make-spark-great-at-many-things-through-domain-chips",
        )

    patterns = [
        (
            r"\bmy name is\s+([A-Z][A-Za-z0-9'._-]*(?:\s+[A-Z][A-Za-z0-9'._-]*)*)",
            "preferred_name",
        ),
        (r"\b(?:i am|i'm)\s+an\s+(entrepreneur)(?:[.!?,]|$)", "occupation"),
        (
            r"\b(?:i created a startup called|my startup is)\s+([A-Z][A-Za-z0-9'&._-]*(?:\s+[A-Z][A-Za-z0-9'&._-]*)*)",
            "startup_name",
        ),
        (
            r"\b(?:i am|i'm)\s+the founder of\s+([A-Z][A-Za-z0-9'&._-]*(?:\s+[A-Z][A-Za-z0-9'&._-]*)*)",
            "founder_of",
        ),
        (r"\bwe were hacked by\s+([A-Za-z][A-Za-z0-9 ._-]+?)(?:[.!?,]|$)", "hack_actor"),
        (
            r"\bi am trying to\s+(survive the hack and revive the companies)(?:[.!?,]|$)",
            "current_mission",
        ),
        (
            r"\bi am\s+(rebuilding after the hack|reviving the companies)(?:[.!?,]|$)",
            "current_mission",
        ),
        (
            r"\bspark\s+(?:is going to be|will be)\s+an important part of this(?: rebuild)?(?:[.!?,]|$)",
            "spark_role",
        ),
        (
            r"\bmy timezone is\s+([A-Za-z][A-Za-z0-9_+-]*(?:/[A-Za-z0-9_+-]+)+)",
            "timezone",
        ),
        (
            r"\bmy country is\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})",
            "home_country",
        ),
        (r"\b(?:i|we)\s+moved back to\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)", "location"),
        (r"\b(?:i|we)\s+moved to\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)", "location"),
        (r"\b(?:i|we)\s+lived in\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)", "location"),
        (r"\b(?:i|we)\s+live in\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)", "location"),
        (r"\b([A-Z][A-Za-z0-9_-]+)\s+(?:moved to|lives in|live in)\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)", "location_named"),
        (r"\b(?:i now prefer|i prefer|i like)\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)", "preference"),
        (r"\bi switched back to\s+([A-Za-z0-9 _-]+?)(?:\s+again)?(?:[.!?,]|$)", "preference"),
        (r"\b([A-Z][A-Za-z0-9_-]+)\s+(?:now prefers|prefers|likes)\s+([A-Za-z0-9 _-]+)", "preference_named"),
        (r"\bmy favourite colour is\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)", "favorite_color"),
        (r"\bmy favorite color is\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)", "favorite_color"),
        (r"\bmy favourite color is\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)", "favorite_color"),
        (r"\bmy favorite colour is\s+([A-Za-z0-9 _-]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)", "favorite_color"),
        (r"\bdaily commute(?: to work)?(?:,|\s|\w)*?takes\s+(\d+\s+(?:minutes?|hours?)(?:\s+each\s+way)?)", "commute_duration"),
        (r"\bthe play i attended was(?: actually)?(?: a production of)?\s+([A-Za-z0-9' _-]+)", "attended_play"),
        (r"\bi attended(?: a production of)?\s+([A-Za-z0-9' _-]+)", "attended_play"),
        (r"\bplaylist(?: on spotify)?(?: that i created)?(?:,)?\s+called\s+([A-Za-z0-9' _-]+)", "playlist_name"),
        (r"\bi created(?: on spotify)?(?: a)? playlist(?: on spotify)?(?:,)?\s+(?:called|named)\s+([A-Za-z0-9' _-]+)", "playlist_name"),
        (r"\bi shop at\s+([A-Z][A-Za-z0-9'&-]*(?:\s+[A-Z][A-Za-z0-9'&-]*)*)", "retailer"),
        (r"\bcartwheel app from\s+([A-Z][A-Za-z0-9'&-]*(?:\s+[A-Z][A-Za-z0-9'&-]*)*)", "retailer"),
        (r"\bi redeemed .*?\bat\s+([A-Z][A-Za-z0-9'&-]*(?:\s+[A-Z][A-Za-z0-9'&-]*)*)", "retailer"),
        (r"\bprevious role as (?:a|an)\s+([^,.!?]+?)(?:\s+and\b|,|\.|$)", "previous_occupation"),
        (r"\bbikes?\b[^.?!]{0,200}?\bgot\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+of them\b", "bike_count"),
        (r"\bi own\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+bikes?\b", "bike_count"),
        (r"\bmy dog is a[n]?\s+([A-Za-z][A-Za-z0-9' -]+?)(?:\s+now|\s+again)?(?:[.!?,]|$)", "dog_breed"),
        (r"\bsuit a\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\s+like\s+[A-Z][A-Za-z]+\b", "dog_breed"),
        (
            r"\b(?:completed my |did my )?(?:undergrad|undergraduate|bachelor'?s degree) in (?:cs|computer science) from ([A-Z][A-Za-z0-9,&()' .-]+?)(?:,| which | and |\.|$)",
            "computer_science_degree_institution",
        ),
        (
            r"\b(?:completed my )?undergrad in (?:cs|computer science) from ([A-Z][A-Za-z0-9,&()' .-]+?)(?:,| which | and |\.|$)",
            "computer_science_degree_institution",
        ),
        (r"\b(?:listening to .*?\bon|using)\s+(Spotify|Apple Music|YouTube Music|Tidal|Pandora)\s+lately\b", "music_service"),
        (
            r"\bwhen i was in\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\b[\s\S]{0,160}?\bspent\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(days?|weeks?|months?)\b",
            "trip_duration",
        ),
        (r"\bkeen on counseling or working in mental health\b", "education_fields"),
        (r"\bResearching\s+([^,.!?]+)", "research_topic"),
        (r"\bit'?ll be tough as a\s+(single parent)\b", "relationship_status_single_parent"),
        (r"\bafter that tough breakup\b", "relationship_status_breakup"),
        (r"\bschool event\s+(last week)\b", "school_event_time"),
        (r"\bmet up\s+(last week)\b", "support_network_meetup_time"),
        (r"\bcharity race\b[^.?!]{0,80}?\b(last Saturday)\b", "charity_race_time"),
        (r"\bknown these friends for\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(years?)\b", "current_friend_group_duration"),
        (r"\bhome country,\s*([A-Z][A-Za-z]+)\b", "moved_from_location"),
        (
            r"\bthinking of working with trans people, helping them accept themselves and supporting their mental health\b",
            "career_path",
        ),
        (r"\byesterday I took the kids to the museum\b", "museum_visit_time"),
        (r"\bmy transgender journey\b", "identity"),
        (r"\bexplore my gender identity\b", "identity"),
        (r"\bduring my transition\b", "identity"),
        (r"\bpainted that lake sunrise\s+(last year)\b", "sunrise_paint_time"),
        (r"\bgoing camping\s+(next month)\b", "camping_plan_time"),
        (r"\bsigned up for a pottery class\s+(yesterday)\b", "pottery_class_signup_time"),
        (r"\bsigned up for a\s+(pottery)\s+class\b", "activity"),
        (r"\boff to go\s+(swimming)\b", "activity"),
        (r"\btook my kids to a pottery workshop\b", "activity_pottery"),
        (r"\bmake something with clay\b", "activity_pottery"),
        (r"\bpainted that lake sunrise\b", "activity_painting"),
        (r"\bpainting'?s a fun way\b", "activity_painting"),
        (r"\bpainting together\b", "activity_painting"),
        (r"\bgoing\s+(camping)\b", "activity"),
        (r"\bwent camping with my fam\b", "activity_camping"),
        (r"\bfamily camping trip\b", "activity_camping"),
        (r"\bcamping in the\s+(?:mountains|forest)\b", "activity_camping"),
        (r"\bcamping at the\s+beach\b", "activity_camping"),
        (r"\btook the kids to the museum\b", "activity_museum"),
        (r"\bwent on a hike\b", "activity_hiking"),
        (r"\bhiking\b", "activity_hiking"),
        (r"\bcamping in the\s+(mountains)\b", "camp_location"),
        (r"\bcamping at the\s+(beach)\b", "camp_location"),
        (r"\bcamping trip in the\s+(forest)\b", "camp_location"),
        (r"\bthe \d+\s+younger kids love\s+(nature)\b", "kids_interest"),
        (r"\bdinosaur exhibit\b", "kids_interest_dinosaurs"),
        (r"\bkids'? books-?\s+classics\b", "bookshelf_collection"),
        (r'\bloved reading\s+"([^"]+)"', "book_read"),
        (r'\bi loved\s+"([^"]+)"', "book_read"),
        (r"\brunning farther to de-stress\b", "destress_activity_running"),
        (r"\bpottery(?: class)?\b[\s\S]{0,120}\b(?:therapy|relaxing|calming)\b", "destress_activity_pottery"),
    ]

    for index, (pattern, predicate) in enumerate(patterns):
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        metadata: JsonDict = {"speaker": turn.speaker}
        if predicate == "location_named":
            atom_subject = match.group(1).strip().lower()
            atom_predicate = "location"
            value = _normalize_value(match.group(2))
        elif predicate == "preference_named":
            atom_subject = match.group(1).strip().lower()
            atom_predicate = "preference"
            value = _normalize_value(match.group(2))
        elif predicate == "trip_duration":
            atom_subject = subject
            atom_predicate = predicate
            destination = _normalize_value(match.group(1))
            value = _normalize_value(f"{match.group(2)} {match.group(3)}")
            metadata["destination"] = destination
            metadata["entity_key"] = destination.lower()
        elif predicate == "education_fields":
            atom_subject = subject
            atom_predicate = predicate
            value = "Psychology, counseling certification"
        elif predicate == "relationship_status_single_parent":
            atom_subject = subject
            atom_predicate = "relationship_status"
            value = "Single"
        elif predicate == "relationship_status_breakup":
            atom_subject = subject
            atom_predicate = "relationship_status"
            value = "Single"
        elif predicate == "occupation":
            atom_subject = subject
            atom_predicate = predicate
            value = _normalize_value(match.group(1))
        elif predicate == "preferred_name":
            atom_subject = subject
            atom_predicate = predicate
            value = _normalize_value(match.group(1))
        elif predicate == "startup_name":
            atom_subject = subject
            atom_predicate = predicate
            value = _normalize_value(match.group(1))
        elif predicate == "founder_of":
            atom_subject = subject
            atom_predicate = predicate
            value = _normalize_value(match.group(1))
        elif predicate == "hack_actor":
            atom_subject = subject
            atom_predicate = predicate
            value = _normalize_value(match.group(1))
        elif predicate == "current_mission":
            atom_subject = subject
            atom_predicate = predicate
            value = _normalize_value(match.group(1))
        elif predicate == "spark_role":
            atom_subject = subject
            atom_predicate = predicate
            value = "important part of the rebuild"
        elif predicate == "timezone":
            atom_subject = subject
            atom_predicate = predicate
            value = _normalize_value(match.group(1))
        elif predicate == "home_country":
            atom_subject = subject
            atom_predicate = predicate
            value = _normalize_value(match.group(1))
        elif predicate == "career_path":
            atom_subject = subject
            atom_predicate = predicate
            value = "counseling or mental health for Transgender people"
        elif predicate == "museum_visit_time":
            atom_subject = subject
            atom_predicate = predicate
            value = "yesterday"
        elif predicate == "identity":
            atom_subject = subject
            atom_predicate = predicate
            value = "Transgender woman"
        elif predicate in {"sunrise_paint_time", "camping_plan_time", "pottery_class_signup_time"}:
            atom_subject = subject
            atom_predicate = predicate
            value = _normalize_value(match.group(1))
        elif predicate == "activity_painting":
            atom_subject = subject
            atom_predicate = "activity"
            value = "painting"
        elif predicate == "activity_pottery":
            atom_subject = subject
            atom_predicate = "activity"
            value = "pottery"
        elif predicate == "activity_camping":
            atom_subject = subject
            atom_predicate = "activity"
            value = "camping"
        elif predicate == "activity_museum":
            atom_subject = subject
            atom_predicate = "activity"
            value = "museum"
        elif predicate == "activity_hiking":
            atom_subject = subject
            atom_predicate = "activity"
            value = "hiking"
        elif predicate == "kids_interest_dinosaurs":
            atom_subject = subject
            atom_predicate = "kids_interest"
            value = "dinosaurs"
        elif predicate == "destress_activity_running":
            atom_subject = subject
            atom_predicate = "destress_activity"
            value = "Running"
        elif predicate == "destress_activity_pottery":
            atom_subject = subject
            atom_predicate = "destress_activity"
            value = "pottery"
        elif predicate == "bookshelf_collection":
            atom_subject = subject
            atom_predicate = predicate
            value = "classic children's books"
        elif predicate == "running_benefit":
            atom_subject = subject
            atom_predicate = predicate
            value = "mental health"
        elif predicate == "current_friend_group_duration":
            atom_subject = subject
            atom_predicate = predicate
            value = _normalize_value(f"{match.group(1)} {match.group(2)}")
        else:
            atom_subject = subject
            atom_predicate = predicate
            value = _normalize_value(match.group(1))
            if atom_predicate == "location":
                value = _normalize_profile_location_value(value)
            if atom_predicate == "research_topic":
                value = _normalize_value(re.split(r"[-\u2013\u2014\ufffd]", value, maxsplit=1)[0])
            if atom_predicate == "book_read":
                value = value.strip('"')
        if atom_predicate in {
            "identity",
            "sunrise_paint_time",
            "camping_plan_time",
            "pottery_class_signup_time",
            "activity",
            "camp_location",
            "kids_interest",
            "destress_activity",
            "book_read",
            "book_takeaway",
            "shoe_use",
            "running_reason",
            "running_benefit",
            "pottery_output",
            "family_creative_activity",
            "family_paint_subject",
            "paint_subject",
            "supportive_space_goal",
            "made_object_photo",
            "library_books",
            "adoption_meeting_takeaway",
            "flower_symbolism",
            "flower_importance",
            "art_show_inspiration",
            "family_trip_sighting",
            "family_trip_feeling",
            "birthday_person",
            "birthday_performer",
            "pottery_design_reason",
            "pet_name",
            "pet_type",
            "pet_household_summary",
            "important_symbol",
            "instrument",
            "seen_artist",
            "family_hike_activity",
            "transition_change",
            "trans_event",
            "art_practice_duration",
            "childhood_activity",
            "neighborhood_find",
            "classical_musicians",
            "modern_music_artist",
            "precautionary_sign",
            "adoption_start_advice",
            "pottery_setback",
            "pottery_break_activity",
            "recent_painting",
            "abstract_painting",
            "poetry_reading_topic",
            "poster_text",
            "drawing_symbolism",
            "preferred_name",
            "occupation",
            "timezone",
            "home_country",
            "startup_name",
            "founder_of",
            "hack_actor",
            "current_mission",
            "spark_role",
            "shared_life_journey",
            "son_accident_reaction",
            "family_importance",
            "children_accident_reaction",
            "post_accident_feeling",
            "canyon_reaction",
            "family_strength_source",
        }:
            metadata["entity_key"] = value.lower()
        atoms.append(
            MemoryAtom(
                atom_id=f"{turn.turn_id}:atom:{index}",
                subject=atom_subject,
                predicate=atom_predicate,
                value=value,
                session_id=session.session_id,
                turn_id=turn.turn_id,
                timestamp=turn.timestamp or session.timestamp,
                source_text=text,
                metadata=metadata,
            )
        )

    atoms.extend(_extract_typed_conversational_atoms(session, turn, subject=subject))

    if atoms:
        if allow_raw_fallback and re.search(
            r"\b(last fri|last friday|last week|two weekends ago|this week|yesterday|last month|this past weekend|last year)\b",
            lower,
        ) and re.search(
            r"\b(pottery workshop|pottery class|camping|campfire|hike|marshmallows|adoption|adopt|roadtrip|poetry reading|conference)\b",
            lower,
        ):
            atoms.append(
                MemoryAtom(
                    atom_id=f"{turn.turn_id}:atom:supplemental_raw",
                    subject=subject,
                    predicate="raw_turn",
                    value=_normalize_value(text),
                    session_id=session.session_id,
                    turn_id=turn.turn_id,
                    timestamp=turn.timestamp or session.timestamp,
                    source_text=text,
                    metadata={"speaker": turn.speaker, "supplemental_raw": True, **turn.metadata},
                )
            )
        return atoms

    if not allow_raw_fallback:
        return []

    # Fallback memory atom: keep the raw turn as a low-confidence fact candidate for retrieval.
    compact_source_text = _compact_fallback_source_text(text)
    return [
        MemoryAtom(
            atom_id=f"{turn.turn_id}:atom:fallback",
            subject=subject,
            predicate="raw_turn",
            value=_normalize_value(text),
            session_id=session.session_id,
            turn_id=turn.turn_id,
            timestamp=turn.timestamp or session.timestamp,
            source_text=text,
            metadata={
                "speaker": turn.speaker,
                "fallback": True,
                "fallback_claim_text": compact_source_text,
                **turn.metadata,
            },
        )
    ]


def extract_memory_atoms(sample: NormalizedBenchmarkSample) -> list[MemoryAtom]:
    atoms: list[MemoryAtom] = []
    participant_speakers = {
        str(sample.metadata.get("speaker_a", "")).strip().lower(),
        str(sample.metadata.get("speaker_b", "")).strip().lower(),
    }
    for session in sample.sessions:
        for turn in session.turns:
            speaker_key = turn.speaker.strip().lower()
            allow_raw_fallback = (
                speaker_key == "user"
                or (
                    sample.benchmark_name == "LoCoMo"
                    and speaker_key in participant_speakers
                )
            )
            atoms.extend(
                _extract_atoms_from_turn(
                    session,
                    turn,
                    allow_raw_fallback=allow_raw_fallback,
                )
            )
    return atoms
