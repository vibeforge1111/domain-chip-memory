from __future__ import annotations

import re
from dataclasses import dataclass

from .contracts import NormalizedBenchmarkSample, NormalizedSession, NormalizedTurn


_CONVERSATIONAL_TIME_PATTERN = re.compile(
    r"\b(a few years ago|few years ago|last year|yesterday|today|(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+days?\s+ago|in (?:19|20)\d{2})\b",
    re.IGNORECASE,
)

_FUTURE_TIME_PATTERN = re.compile(
    r"\b(this month|next month|this week|next week|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|on\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|tomorrow|later today|in (?:19|20)\d{2})\b",
    re.IGNORECASE,
)

_RELATIONSHIP_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("mother", re.compile(r"\b(?:my|her|his|our)\s+(?:mother|mom)\b", re.IGNORECASE)),
    ("father", re.compile(r"\b(?:my|her|his|our)\s+(?:father|dad)\b", re.IGNORECASE)),
    ("sister", re.compile(r"\b(?:my|her|his|our)\s+sister(?:\s+([A-Za-z]+))?\b", re.IGNORECASE)),
    ("brother", re.compile(r"\b(?:my|her|his|our)\s+brother(?:\s+([A-Za-z]+))?\b", re.IGNORECASE)),
    ("friend", re.compile(r"\b(?:my|her|his|our)\s+friend(?:\s+([A-Za-z]+))?\b", re.IGNORECASE)),
    ("partner", re.compile(r"\b(?:my|her|his|our)\s+partner\b", re.IGNORECASE)),
)

_SUPPORT_TRIGGER_PATTERNS = (
    "helped me",
    "helps me",
    "help me",
    "support",
    "supported",
    "find peace",
    "gives me peace",
    "gives her peace",
    "gives him peace",
    "grateful",
    "thankful",
    "means a lot to me",
    "feel close",
)

_COMMITMENT_TRIGGER_PATTERNS = (
    "i'm going to",
    "i am going to",
    "i'll",
    "we'll",
    "sounds like a plan",
    "keep ya posted",
    "keep you posted",
    "planning to",
)

_NEGATION_CUE_PATTERN = re.compile(
    r"\b(never|nope|not|haven't|hasn't|hadn't|didn't|can't|cannot|won't|wouldn't)\b",
    re.IGNORECASE,
)

_REPORTED_SPEECH_PATTERN = re.compile(
    r"\b(?P<verb>said|told(?:\s+(?:me|us|him|her|them))?)\b(?P<content>.+)",
    re.IGNORECASE,
)

_UNKNOWN_CUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("can't_remember", re.compile(r"\b(?:i\s+)?can't remember\b", re.IGNORECASE)),
    ("not_sure", re.compile(r"\b(?:i(?:'m| am)\s+)?not sure\b", re.IGNORECASE)),
    ("dont_know", re.compile(r"\b(?:i\s+)?do(?:n't| not)\s+know\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class ConversationalIndexEntry:
    entry_id: str
    entry_type: str
    subject: str
    predicate: str
    text: str
    session_id: str
    turn_id: str
    timestamp: str | None
    metadata: dict[str, object]


def _canonical_subject(turn: NormalizedTurn) -> str:
    speaker = turn.speaker.strip().lower()
    if speaker in {"user", "speaker_a", "speaker_a:", "speaker b", "speaker_b", "speaker_b:"}:
        return "user"
    return speaker


def _extract_source_span(text: str, keyword: str) -> str:
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
    keyword_lower = keyword.lower()
    for sentence in sentences:
        if keyword_lower in sentence.lower():
            return sentence.strip(" \"'")
    return text.strip()


def _text_spans(text: str) -> list[str]:
    spans: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        stripped = sentence.strip()
        if not stripped:
            continue
        for clause in re.split(r"(?<=;)\s+", stripped):
            clause_stripped = clause.strip()
            if clause_stripped:
                spans.append(clause_stripped)
    return spans


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


def _extract_alias_binding(
    text: str,
    *,
    speaker_name: str,
    candidate_names: list[str],
) -> tuple[str, str, str] | None:
    greeting_match = re.match(r"^\s*(?:hey|hi)\s+([A-Za-z]+)\b", text, re.IGNORECASE)
    alias_matches: list[tuple[str, str]] = []
    if greeting_match is not None:
        alias_matches.append((greeting_match.group(1).strip(), greeting_match.group(0).strip()))
    for pattern in (
        re.compile(r"\b(?:you can )?call me\s+([A-Za-z]+)\b", re.IGNORECASE),
        re.compile(r"\b(?:everyone|people)\s+calls?\s+me\s+([A-Za-z]+)\b", re.IGNORECASE),
    ):
        match = pattern.search(text)
        if match is not None:
            alias_matches.append((match.group(1).strip(), match.group(0).strip()))
    for alias, source_span in alias_matches:
        if len(alias) < 2:
            continue
        alias_lower = alias.lower()
        for candidate in candidate_names:
            candidate_clean = candidate.strip()
            if not candidate_clean or candidate_clean.lower() == speaker_name.lower():
                continue
            candidate_lower = candidate_clean.lower()
            if alias_lower == candidate_lower:
                continue
            if candidate_lower.startswith(alias_lower):
                return alias, candidate_clean, source_span
        return alias, speaker_name.strip() or "user", source_span
    return None


def _extract_commitment_event(text: str) -> tuple[str, str, str] | None:
    lower = text.lower()
    for trigger in _COMMITMENT_TRIGGER_PATTERNS:
        index = lower.find(trigger)
        if index == -1:
            continue
        source_span = _extract_source_span(text, trigger)
        time_match = _FUTURE_TIME_PATTERN.search(lower)
        time_expression_raw = time_match.group(1).lower() if time_match else ""
        return trigger, source_span, time_expression_raw
    action_match = re.search(
        r"\b(?:i|we|[a-z]+\s+and\s+i)\s+(?:mailed|sent|delivered|posted|are\s+presenting)\b",
        lower,
        re.IGNORECASE,
    )
    if action_match is None:
        return None
    time_match = _FUTURE_TIME_PATTERN.search(lower) or _CONVERSATIONAL_TIME_PATTERN.search(lower)
    if time_match is None:
        return None
    trigger = action_match.group(0).strip()
    source_span = _extract_source_span(text, trigger)
    time_expression_raw = time_match.group(1).lower()
    return trigger, source_span, time_expression_raw


def _extract_negation_record(text: str) -> tuple[str, str] | None:
    for span in _text_spans(text):
        match = _NEGATION_CUE_PATTERN.search(span)
        if match is None:
            continue
        cue = match.group(1).lower()
        return cue, span.strip(" \"'")
    return None


def _extract_reported_speech(text: str) -> tuple[str, str, str] | None:
    for span in _text_spans(text):
        match = _REPORTED_SPEECH_PATTERN.search(span)
        if match is None:
            continue
        speech_verb = match.group("verb").lower().strip()
        reported_content = match.group("content").strip(" -:,.!?\"'")
        if len(reported_content.split()) < 2:
            continue
        return speech_verb, span.strip(" \"'"), reported_content
    return None


def _extract_unknown_record(text: str) -> tuple[str, str] | None:
    for span in _text_spans(text):
        for cue_name, pattern in _UNKNOWN_CUE_PATTERNS:
            if pattern.search(span) is None:
                continue
            return cue_name, span.strip(" \"'")
    return None


def _infer_relationship_context(text: str, lower: str) -> tuple[str, str]:
    if any(token in lower for token in ("my mother", "my mom", "her mother", "her mom", "our mother", "our mom")):
        return "mother", "mother"
    if any(token in lower for token in ("my father", "my dad", "her father", "her dad", "our father", "our dad")):
        return "father", "father"
    friend_match = re.search(r"\b(?:my|her|his|our)\s+friend\s+([A-Za-z]+)\b", text, re.IGNORECASE)
    if friend_match:
        return "friend", friend_match.group(1).strip().title()
    return "", ""


def _extract_relationship_mentions(text: str) -> list[tuple[str, str, str]]:
    mentions: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for relation_type, pattern in _RELATIONSHIP_PATTERNS:
        for match in pattern.finditer(text):
            source_span = match.group(0).strip()
            named_entity = ""
            if match.lastindex:
                named_entity = (match.group(1) or "").strip()
                if named_entity and named_entity.isalpha():
                    named_entity = named_entity.title()
            relation_surface = named_entity or relation_type
            key = (relation_type, relation_surface, source_span)
            if key in seen:
                continue
            seen.add(key)
            mentions.append(key)
    named_relation_pattern = re.compile(
        r"\b([A-Za-z]+)\s+is\s+my\s+(mother|mom|father|dad|sister|brother|friend|partner|project partner)\b",
        re.IGNORECASE,
    )
    for match in named_relation_pattern.finditer(text):
        named_entity = match.group(1).strip().title()
        relation_surface = match.group(2).strip().lower()
        relation_type = {
            "mom": "mother",
            "dad": "father",
        }.get(relation_surface, relation_surface)
        source_span = match.group(0).strip()
        key = (relation_type, named_entity, source_span)
        if key in seen:
            continue
        seen.add(key)
        mentions.append(key)
    return mentions


def build_conversational_index(sample: NormalizedBenchmarkSample) -> list[ConversationalIndexEntry]:
    entries: list[ConversationalIndexEntry] = []
    recent_relation_by_speaker: dict[str, tuple[str, str]] = {}
    speaker_names = sorted({turn.speaker.strip() for session in sample.sessions for turn in session.turns if turn.speaker.strip()})

    for session in sample.sessions:
        for turn in session.turns:
            subject = _canonical_subject(turn)
            text = turn.text.strip()
            lower = text.lower()
            timestamp = turn.timestamp or session.timestamp
            speaker_key = turn.speaker.strip().lower()

            entries.append(
                ConversationalIndexEntry(
                    entry_id=f"{turn.turn_id}:turn",
                    entry_type="turn",
                    subject=subject,
                    predicate="turn",
                    text=text,
                    session_id=session.session_id,
                    turn_id=turn.turn_id,
                    timestamp=timestamp,
                    metadata={"speaker": turn.speaker, **turn.metadata},
                )
            )

            relation_type, other_entity = _infer_relationship_context(text, lower)
            if not (relation_type or other_entity):
                relation_type, other_entity = recent_relation_by_speaker.get(speaker_key, ("", ""))
            elif relation_type or other_entity:
                recent_relation_by_speaker[speaker_key] = (relation_type, other_entity)

            for mention_relation, mention_surface, source_span in _extract_relationship_mentions(text):
                recent_relation_by_speaker[speaker_key] = (mention_relation, mention_surface)
                entries.append(
                    ConversationalIndexEntry(
                        entry_id=f"{turn.turn_id}:typed:relationship_edge:{len(entries)}",
                        entry_type="typed_atom",
                        subject=subject,
                        predicate="relationship_edge",
                        text=text,
                        session_id=session.session_id,
                        turn_id=turn.turn_id,
                        timestamp=timestamp,
                        metadata={
                            "speaker": turn.speaker,
                            "relation_type": mention_relation,
                            "other_entity": mention_surface if mention_surface != mention_relation else "",
                            "source_span": source_span,
                        },
                    )
                )

            alias_binding = _extract_alias_binding(
                text,
                speaker_name=turn.speaker,
                candidate_names=speaker_names,
            )
            if alias_binding is not None:
                alias, canonical_name, source_span = alias_binding
                entries.append(
                    ConversationalIndexEntry(
                        entry_id=f"{turn.turn_id}:typed:alias_binding",
                        entry_type="typed_atom",
                        subject=subject,
                        predicate="alias_binding",
                        text=text,
                        session_id=session.session_id,
                        turn_id=turn.turn_id,
                        timestamp=timestamp,
                        metadata={
                            "speaker": turn.speaker,
                            "alias": alias,
                            "canonical_name": canonical_name,
                            "source_span": source_span,
                        },
                    )
                )

            if "passed away" in lower:
                time_match = _CONVERSATIONAL_TIME_PATTERN.search(lower)
                time_expression_raw = time_match.group(1).lower() if time_match else ""
                time_normalized = _normalize_conversational_time_expression(time_expression_raw, timestamp) if time_expression_raw else ""
                entries.append(
                    ConversationalIndexEntry(
                        entry_id=f"{turn.turn_id}:typed:loss_event",
                        entry_type="typed_atom",
                        subject=subject,
                        predicate="loss_event",
                        text=text,
                        session_id=session.session_id,
                        turn_id=turn.turn_id,
                        timestamp=timestamp,
                        metadata={
                            "speaker": turn.speaker,
                            "relation_type": relation_type,
                            "other_entity": other_entity,
                            "source_span": _extract_source_span(text, "passed away"),
                            "time_expression_raw": time_expression_raw,
                            "time_normalized": time_normalized,
                        },
                    )
                )

            if any(token in lower for token in ("pendant", "necklace")) and any(
                token in lower for token in ("gave me", "gave it to me", "gifted me", "bought me", "bought this", "got me")
            ):
                item_type = "pendant" if "pendant" in lower else "necklace"
                year_match = re.search(r"\bin\s+((?:19|20)\d{2})\b", lower)
                time_expression_raw = f"in {year_match.group(1)}" if year_match else ""
                time_normalized = _normalize_conversational_time_expression(time_expression_raw, timestamp) if time_expression_raw else ""
                entries.append(
                    ConversationalIndexEntry(
                        entry_id=f"{turn.turn_id}:typed:gift_event",
                        entry_type="typed_atom",
                        subject=subject,
                        predicate="gift_event",
                        text=text,
                        session_id=session.session_id,
                        turn_id=turn.turn_id,
                        timestamp=timestamp,
                        metadata={
                            "speaker": turn.speaker,
                            "relation_type": relation_type,
                            "other_entity": other_entity,
                            "item_type": item_type,
                            "source_span": _extract_source_span(text, item_type),
                            "time_expression_raw": time_expression_raw,
                            "time_normalized": time_normalized,
                        },
                    )
                )

            support_trigger = next((token for token in _SUPPORT_TRIGGER_PATTERNS if token in lower), "")
            if support_trigger:
                entries.append(
                    ConversationalIndexEntry(
                        entry_id=f"{turn.turn_id}:typed:support_event",
                        entry_type="typed_atom",
                        subject=subject,
                        predicate="support_event",
                        text=text,
                        session_id=session.session_id,
                        turn_id=turn.turn_id,
                        timestamp=timestamp,
                        metadata={
                            "speaker": turn.speaker,
                            "relation_type": relation_type,
                            "other_entity": other_entity,
                            "source_span": _extract_source_span(text, support_trigger),
                            "support_kind": "place" if "peace" in lower else "support",
                        },
                    )
                )

            commitment_event = _extract_commitment_event(text)
            if commitment_event is not None:
                trigger, source_span, time_expression_raw = commitment_event
                time_normalized = (
                    _normalize_conversational_time_expression(time_expression_raw, timestamp)
                    if time_expression_raw
                    else ""
                )
                entries.append(
                    ConversationalIndexEntry(
                        entry_id=f"{turn.turn_id}:typed:commitment_event",
                        entry_type="typed_atom",
                        subject=subject,
                        predicate="commitment_event",
                        text=text,
                        session_id=session.session_id,
                        turn_id=turn.turn_id,
                        timestamp=timestamp,
                        metadata={
                            "speaker": turn.speaker,
                            "commitment_trigger": trigger,
                            "source_span": source_span,
                            "time_expression_raw": time_expression_raw,
                            "time_normalized": time_normalized,
                        },
                    )
                )

            negation_record = _extract_negation_record(text)
            if negation_record is not None:
                negation_cue, source_span = negation_record
                entries.append(
                    ConversationalIndexEntry(
                        entry_id=f"{turn.turn_id}:typed:negation_record",
                        entry_type="typed_atom",
                        subject=subject,
                        predicate="negation_record",
                        text=text,
                        session_id=session.session_id,
                        turn_id=turn.turn_id,
                        timestamp=timestamp,
                        metadata={
                            "speaker": turn.speaker,
                            "negation_cue": negation_cue,
                            "claim_text": source_span,
                            "source_span": source_span,
                        },
                    )
                )

            reported_speech = _extract_reported_speech(text)
            if reported_speech is not None:
                speech_verb, source_span, reported_content = reported_speech
                entries.append(
                    ConversationalIndexEntry(
                        entry_id=f"{turn.turn_id}:typed:reported_speech",
                        entry_type="typed_atom",
                        subject=subject,
                        predicate="reported_speech",
                        text=text,
                        session_id=session.session_id,
                        turn_id=turn.turn_id,
                        timestamp=timestamp,
                        metadata={
                            "speaker": turn.speaker,
                            "speech_verb": speech_verb,
                            "reported_content": reported_content,
                            "source_span": source_span,
                        },
                    )
                )

            unknown_record = _extract_unknown_record(text)
            if unknown_record is not None:
                uncertainty_cue, source_span = unknown_record
                entries.append(
                    ConversationalIndexEntry(
                        entry_id=f"{turn.turn_id}:typed:unknown_record",
                        entry_type="typed_atom",
                        subject=subject,
                        predicate="unknown_record",
                        text=text,
                        session_id=session.session_id,
                        turn_id=turn.turn_id,
                        timestamp=timestamp,
                        metadata={
                            "speaker": turn.speaker,
                            "uncertainty_cue": uncertainty_cue,
                            "claim_text": source_span,
                            "source_span": source_span,
                        },
                    )
                )

    return entries
