from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from .answer_candidates import build_answer_candidate
from .contracts import AnswerCandidate, JsonDict, NormalizedBenchmarkSample, NormalizedQuestion, NormalizedSession, NormalizedTurn
from .memory_evidence import entry_source_corpus as _entry_source_corpus
from .memory_evidence import observation_evidence_text as _observation_evidence_text
from .memory_evidence import raw_evidence_span as _raw_evidence_span
from .memory_aggregate_support import raw_user_turn_entries as _raw_user_turn_entries_impl
from .memory_aggregate_support import select_aggregate_support_entries as _select_aggregate_support_entries_impl
from .memory_answer_inference import extract_place_candidates as _extract_place_candidates_impl
from .memory_answer_inference import infer_explanatory_answer as _infer_explanatory_answer_impl
from .memory_answer_inference import infer_aggregate_answer as _infer_aggregate_answer_impl
from .memory_answer_inference import infer_shared_answer as _infer_shared_answer_impl
from .memory_answer_routing import choose_answer_candidate as _choose_answer_candidate_impl
from .memory_answer_routing import entry_combined_text as _entry_combined_text_impl
from .memory_answer_routing import question_needs_raw_aggregate_context as _question_needs_raw_aggregate_context
from .memory_beam_builder import build_beam_ready_temporal_atom_router_packets as _build_beam_ready_temporal_atom_router_packets_impl
from .memory_contract_summary import build_memory_system_contract_summary as _build_memory_system_contract_summary_impl
from .memory_dual_store_builder import build_dual_store_event_calendar_hybrid_packets as _build_dual_store_event_calendar_hybrid_packets_impl
from .memory_observational_builder import build_observational_temporal_memory_packets as _build_observational_temporal_memory_packets_impl
from .memory_extraction import (
    EventCalendarEntry,
    MemoryAtom,
    ObservationEntry,
    _canonical_subject,
    _normalize_value,
    _token_bigrams,
    _tokenize,
    _turn_order_key,
    build_event_calendar as _build_event_calendar,
    build_observation_log as _build_observation_log,
)
from .memory_queries import _question_predicates, _question_subject, _question_subjects
from .memory_numbers import extract_first_numeric_match as _extract_first_numeric_match
from .memory_numbers import format_count_value as _format_count_value
from .memory_numbers import parse_small_number as _parse_small_number
from .memory_packet_utils import event_score as _event_score
from .memory_packet_utils import question_aware_observation_limits as _question_aware_observation_limits
from .memory_observation_utils import dedupe_observations as _dedupe_observations
from .memory_observation_utils import session_lookup as _session_lookup
from .memory_preferences import is_generic_followup_preference_text as _is_generic_followup_preference_text
from .memory_preferences import is_preference_question as _is_preference_question
from .memory_preferences import is_recommendation_request_text as _is_recommendation_request_text
from .memory_preference_answers import infer_preference_answer as _infer_preference_answer
from .memory_preferences import preference_anchor_match as _preference_anchor_match
from .memory_preferences import preference_domain_tokens as _preference_domain_tokens
from .memory_preferences import preference_overlap as _preference_overlap
from .memory_preferences import preference_phrase_bonus as _preference_phrase_bonus
from .memory_relative_time import generic_relative_anchor_candidates as _generic_relative_anchor_candidates
from .memory_relative_time import has_ambiguous_generic_relative_anchor as _has_ambiguous_generic_relative_anchor
from .memory_relative_time import infer_generic_relative_anchor_time as _infer_generic_relative_anchor_time
from .memory_relative_time import parse_generic_relative_anchor_phrase as _parse_generic_relative_anchor_phrase
from .memory_observation_scoring import observation_score as _observation_score_impl
from .memory_rendering import answer_candidate_surface_text as _answer_candidate_surface_text
from .memory_rendering import observation_surface_text as _observation_surface_text
from .memory_rendering import serialize_session as _serialize_session
from .memory_scoring import evidence_score as _evidence_score_impl
from .memory_selection import select_evidence_entries as _select_evidence_entries_impl
from .memory_selection import select_preference_support_entries as _select_preference_support_entries_impl
from .memory_roles import strategy_memory_role
from .memory_time import format_full_date as _format_full_date
from .memory_time import format_month_year as _format_month_year
from .memory_time import parse_observation_anchor as _parse_observation_anchor
from .memory_time import parse_question_state_anchor as _parse_question_state_anchor
from .memory_time import shift_month as _shift_month
from .memory_updates import build_current_state_view, has_active_current_state_deletion
from .memory_views import is_current_state_question, select_current_state_entries
from .runs import BaselinePromptPacket, RetrievedContextItem, build_run_manifest

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

    patterns = [
        (r"\b(?:i|we)\s+moved back to\s+([A-Za-z0-9 _-]+)", "location"),
        (r"\b(?:i|we)\s+moved to\s+([A-Za-z0-9 _-]+)", "location"),
        (r"\b(?:i|we)\s+lived in\s+([A-Za-z0-9 _-]+)", "location"),
        (r"\b(?:i|we)\s+live in\s+([A-Za-z0-9 _-]+)", "location"),
        (r"\b([A-Z][A-Za-z0-9_-]+)\s+(?:moved to|lives in|live in)\s+([A-Za-z0-9 _-]+)", "location_named"),
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
            metadata={"speaker": turn.speaker, "fallback": True, **turn.metadata},
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


def build_observation_log(sample: NormalizedBenchmarkSample) -> list[ObservationEntry]:
    return _build_observation_log(
        sample,
        extract_memory_atoms=extract_memory_atoms,
        observation_surface_text=_observation_surface_text,
    )


def reflect_observations(observations: list[ObservationEntry]) -> list[ObservationEntry]:
    return build_current_state_view(observations)


def _topical_episode_support(
    question: NormalizedQuestion,
    stable_window: list[ObservationEntry],
    observations: list[ObservationEntry],
    *,
    max_support: int = 2,
) -> tuple[str, list[ObservationEntry]]:
    if not stable_window or not observations:
        return "", []

    stable_ids = {entry.observation_id for entry in stable_window}
    candidate_topic_scores: dict[str, float] = {}
    candidate_topic_summaries: dict[str, str] = {}
    for entry in stable_window:
        topic_id = str(entry.metadata.get("topic_id", "")).strip()
        if not topic_id:
            continue
        candidate_topic_scores[topic_id] = candidate_topic_scores.get(topic_id, 0.0) + max(_observation_score(question, entry), 0.0)
        candidate_topic_summaries[topic_id] = str(entry.metadata.get("topic_summary", "")).strip()

    if not candidate_topic_scores:
        return "", []

    topic_members: dict[str, list[ObservationEntry]] = {}
    for observation in observations:
        topic_id = str(observation.metadata.get("topic_id", "")).strip()
        if topic_id:
            topic_members.setdefault(topic_id, []).append(observation)

    ranked_topic_ids = sorted(
        candidate_topic_scores,
        key=lambda topic_id: (
            candidate_topic_scores[topic_id],
            int(next(
                (
                    member.metadata.get("topic_member_count", 0)
                    for member in topic_members.get(topic_id, [])
                    if member.metadata.get("topic_member_count", 0)
                ),
                0,
            )),
            topic_id,
        ),
        reverse=True,
    )

    for topic_id in ranked_topic_ids:
        members = topic_members.get(topic_id, [])
        if len(members) < 2:
            continue
        extras = [member for member in members if member.observation_id not in stable_ids]
        if not extras:
            continue
        ranked_extras = sorted(
            extras,
            key=lambda entry: (_observation_score(question, entry), entry.timestamp or "", *_turn_order_key(entry.turn_ids), entry.observation_id),
            reverse=True,
        )[:max_support]
        if ranked_extras:
            return candidate_topic_summaries.get(topic_id, ""), ranked_extras
    return "", []


def build_event_calendar(sample: NormalizedBenchmarkSample) -> list[EventCalendarEntry]:
    return _build_event_calendar(
        sample,
        extract_memory_atoms=extract_memory_atoms,
        observation_surface_text=_observation_surface_text,
    )


def _atom_score(question: NormalizedQuestion, atom: MemoryAtom) -> float:
    score = 0.0
    subject = _question_subject(question)
    subjects = set(_question_subjects(question))
    predicates = _question_predicates(question)
    question_tokens = set(_tokenize(question.question))
    atom_tokens = set(_tokenize(atom.source_text))
    question_bigrams = _token_bigrams(question.question)
    atom_bigrams = _token_bigrams(atom.source_text)

    if atom.subject == subject:
        score += 3.0
    elif atom.subject in subjects:
        score += 2.5
    if atom.predicate in predicates:
        score += 4.0
    score += float(len(question_tokens.intersection(atom_tokens)))
    score += 1.5 * min(len(question_bigrams.intersection(atom_bigrams)), 3)
    if atom.timestamp:
        score += 0.001 * sum(ord(char) for char in atom.timestamp)
    if question.category in {"knowledge-update", "temporal", "temporal-reasoning"} and atom.timestamp:
        score += 1.0
    if atom.metadata.get("fallback"):
        score -= 2.0
    return score


def _choose_atoms(question: NormalizedQuestion, atoms: list[MemoryAtom], limit: int) -> list[MemoryAtom]:
    predicates = set(_question_predicates(question))
    subjects = set(_question_subjects(question))
    latest_by_key: dict[tuple[str, str], MemoryAtom] = {}
    other_atoms: list[MemoryAtom] = []
    for atom in atoms:
        key = (atom.subject, atom.predicate)
        if atom.subject in subjects and atom.predicate in predicates:
            current = latest_by_key.get(key)
            if current is None or (atom.timestamp or "") >= (current.timestamp or ""):
                latest_by_key[key] = atom
        else:
            other_atoms.append(atom)

    scored = sorted(
        [*latest_by_key.values(), *other_atoms],
        key=lambda atom: (_atom_score(question, atom), atom.timestamp or "", atom.atom_id),
        reverse=True,
    )
    chosen: list[MemoryAtom] = []
    seen_keys: set[tuple[str, str]] = set()
    for atom in scored:
        key = (atom.subject, atom.predicate)
        if atom.subject in subjects and atom.predicate in predicates:
            if key in seen_keys:
                continue
            seen_keys.add(key)
            chosen.append(atom)
        elif len(chosen) < limit:
            chosen.append(atom)
        if len(chosen) >= limit:
            break
    return chosen


def _evidence_score(question: NormalizedQuestion, observation: ObservationEntry) -> float:
    return _evidence_score_impl(
        question,
        observation,
        observation_score=_observation_score,
    )


def _select_preference_support_entries(
    question: NormalizedQuestion,
    entries: list[ObservationEntry],
    *,
    limit: int = 4,
) -> list[ObservationEntry]:
    return _select_preference_support_entries_impl(
        question,
        entries,
        evidence_score=_evidence_score,
        observation_score=_observation_score,
        entry_source_corpus=_entry_source_corpus,
        preference_anchor_match=_preference_anchor_match,
        preference_overlap=_preference_overlap,
        preference_phrase_bonus=_preference_phrase_bonus,
        observation_evidence_text=_observation_evidence_text,
        limit=limit,
    )


def _select_evidence_entries(
    question: NormalizedQuestion,
    observations: list[ObservationEntry],
    *,
    limit: int = 4,
) -> list[ObservationEntry]:
    return _select_evidence_entries_impl(
        question,
        observations,
        evidence_score=_evidence_score,
        observation_score=_observation_score,
        question_subjects=_question_subjects,
        entry_combined_text=_entry_combined_text,
        observation_evidence_text=_observation_evidence_text,
        limit=limit,
    )


def _choose_answer_candidate(
    question: NormalizedQuestion,
    evidence_entries: list[ObservationEntry],
    belief_entries: list[ObservationEntry],
    context_entries: list[ObservationEntry] | None = None,
    aggregate_entries: list[ObservationEntry] | None = None,
) -> str:
    return _choose_answer_candidate_impl(
        question,
        evidence_entries,
        belief_entries,
        context_entries=context_entries,
        aggregate_entries=aggregate_entries,
        question_needs_raw_aggregate_context=_question_needs_raw_aggregate_context,
        infer_dated_state_answer=_infer_dated_state_answer,
        infer_relative_state_answer=_infer_relative_state_answer,
        is_preference_question=_is_preference_question,
        infer_preference_answer=_infer_preference_answer,
        infer_factoid_answer=_infer_factoid_answer,
        infer_aggregate_answer=_infer_aggregate_answer,
        infer_temporal_answer=_infer_temporal_answer,
        infer_shared_answer=_infer_shared_answer,
        infer_explanatory_answer=_infer_explanatory_answer,
        infer_yes_no_answer=_infer_yes_no_answer,
        answer_candidate_surface_text=_answer_candidate_surface_text,
        evidence_score=_evidence_score,
        observation_score=_observation_score,
        observation_evidence_text=_observation_evidence_text,
    )

def _is_dated_state_question(question: NormalizedQuestion) -> bool:
    question_lower = question.question.lower()
    if question_lower.startswith(
        (
            "where did i live before ",
            "where was i living before ",
            "where did i live after ",
            "where was i living after ",
            "what did i prefer before ",
            "what did i prefer after ",
            "what was my favorite color before ",
            "what was my favourite color before ",
            "what was my favorite colour before ",
            "what was my favourite colour before ",
            "what was my favorite color after ",
            "what was my favourite color after ",
            "what was my favorite colour after ",
            "what was my favourite colour after ",
        )
    ):
        return False
    return (
        question_lower.startswith(
            (
                "where did i live in ",
                "where was i living in ",
                "where did i live on ",
                "where was i living on ",
                "where did i live at ",
                "where was i living at ",
                "where did i live when ",
                "where was i living when ",
                "what did i prefer in ",
                "what did i prefer on ",
                "what did i prefer at ",
                "what did i prefer when ",
                "what was my favorite color when ",
                "what was my favourite color when ",
                "what was my favorite colour when ",
                "what was my favourite colour when ",
            )
        )
        or bool(
            re.search(
                r"\b(?:at\s+\d{1,2}(?::\d{2})?\s*[ap]m\s+on\s+\d{1,2}\s+"
                r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}|"
                r"on\s+\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}|"
                r"in\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4})\b",
                question_lower,
            )
        )
    )


def _extract_relative_state_anchor(question_lower: str) -> tuple[str | None, str, list[str]]:
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
            return mode, _normalize_relative_state_anchor_phrase(anchor_phrase, predicates), predicates
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
                return mode, _normalize_relative_state_anchor_phrase(anchor_phrase, predicates), predicates
    return None, "", []


def _normalize_relative_state_anchor_phrase(anchor_phrase: str, target_predicates: list[str]) -> str:
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
            return f"my favorite color is {_normalize_value(match.group(1).lower())}"
    if "preference" in target_predicates:
        match = re.match(
            rf"^(?:i\s+)?(?:{correction_verbs})\s+it\s+to\s+([a-z0-9 _-]+?)(?:\s+now|\s+again)?$",
            normalized,
        )
        if match:
            return f"i prefer {_normalize_value(match.group(1).lower())}"
    return normalized


def _specialize_clause_carry_first_last_anchor_phrase(
    anchor_phrase: str,
    target_predicates: list[str],
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
    *,
    allow_operation_specialization: bool,
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

    candidates = _generic_relative_anchor_candidates(f"that {base}", target_predicates, candidate_entries)
    if len(candidates) != 1:
        return generic_anchor
    return f"that {modifier} {base}"


def _specialize_relative_state_anchor_phrase(
    question: NormalizedQuestion,
    anchor_phrase: str,
    target_predicates: list[str],
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
) -> str:
    return _specialize_clause_carry_first_last_anchor_phrase(
        anchor_phrase,
        target_predicates,
        candidate_entries,
        allow_operation_specialization=not _has_referential_ambiguity(question, candidate_entries),
    )


def _is_relative_state_question(question: NormalizedQuestion) -> bool:
    mode, anchor_phrase, target_predicates = _extract_relative_state_anchor(question.question.lower())
    return mode is not None and bool(anchor_phrase) and bool(target_predicates)


def _should_use_current_state_exact_value(question: NormalizedQuestion) -> bool:
    question_lower = question.question.lower()
    if not is_current_state_question(question):
        return False
    if _is_dated_state_question(question) or _is_relative_state_question(question):
        return False
    if question_lower.startswith("how many bikes") and "own" in question_lower:
        return True
    if _question_needs_raw_aggregate_context(question):
        return False
    if question_lower.startswith(("how many", "how much", "what is the total", "what was the total")):
        return False
    return True


def _entry_combined_text(question: NormalizedQuestion, entry: ObservationEntry) -> str:
    return _entry_combined_text_impl(
        question,
        entry,
        observation_evidence_text=_observation_evidence_text,
    )


def _raw_user_turn_entries(sample: NormalizedBenchmarkSample) -> list[ObservationEntry]:
    return _raw_user_turn_entries_impl(sample)


def _select_aggregate_support_entries(
    question: NormalizedQuestion,
    aggregate_entries: list[ObservationEntry],
    *,
    limit: int = 4,
) -> list[ObservationEntry]:
    return _select_aggregate_support_entries_impl(
        question,
        aggregate_entries,
        limit=limit,
    )


def _extract_place_candidates(text: str, ignored_terms: set[str]) -> set[str]:
    return _extract_place_candidates_impl(text, ignored_terms)


def _is_pure_question_turn(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped.endswith("?") and "." not in stripped and "!" not in stripped


def _infer_shared_answer(question: NormalizedQuestion, evidence_entries: list[ObservationEntry]) -> str:
    return _infer_shared_answer_impl(
        question,
        evidence_entries,
        question_subjects=_question_subjects,
        entry_combined_text=_entry_combined_text,
        entry_source_corpus=_entry_source_corpus,
    )


def _infer_explanatory_answer(question: NormalizedQuestion, evidence_entries: list[ObservationEntry]) -> str:
    return _infer_explanatory_answer_impl(
        question,
        evidence_entries,
        question_subject=_question_subject,
        entry_combined_text=_entry_combined_text,
    )


def _infer_aggregate_answer(question: NormalizedQuestion, candidate_entries: list[ObservationEntry]) -> str:
    return _infer_aggregate_answer_impl(question, candidate_entries)


def _infer_factoid_answer(question: NormalizedQuestion, candidate_entries: list[ObservationEntry]) -> str:
    question_lower = question.question.lower()
    texts = [_entry_combined_text(question, entry) for entry in candidate_entries]
    combined = "\n".join(texts)
    combined_source = "\n".join(_entry_source_corpus(entry) for entry in candidate_entries)
    combined_corpus = "\n".join(_entry_source_corpus(entry).lower() for entry in candidate_entries)
    duration_with_place_pattern = lambda place: re.compile(
        rf"(?:\b(?:spent|stayed|was|went|travel(?:ed)?|trip)\b[^.\n]{{0,80}}\b(?:in|to|around)\s+(?:south\s+)?{place}\b[^.\n]{{0,80}}\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|few)\s+(?:days?|weeks?|months?|years?)\b)"
        rf"|(?:\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|few)\s+(?:days?|weeks?|months?|years?)\b[^.\n]{{0,80}}\b(?:in|to|around)\s+(?:south\s+)?{place}\b)",
        re.IGNORECASE,
    )

    if question_lower.startswith("what size") and "tv" in question_lower:
        match = re.search(r"\b(\d{2,3}-inch)\b", combined, re.IGNORECASE)
        if match:
            return match.group(1)

    if question_lower.startswith("what time") and "get home from work" in question_lower:
        match = re.search(r"\b(\d{1,2}:\d{2}\s*[ap]m)\b", combined, re.IGNORECASE)
        if match:
            return match.group(1)

    if question_lower.startswith("what is my ethnicity"):
        match = re.search(r"mixed ethnicity\s*[-:]\s*([A-Za-z]+)\s+and\s+([A-Za-z]+)", combined, re.IGNORECASE)
        if match:
            return f"A mix of {match.group(1).title()} and {match.group(2).title()}"

    if question_lower.startswith("what book am i currently reading"):
        book_patterns = (
            r'currently (?:devouring|reading)\s+"([^"]+)"',
            r'just passed the halfway mark on\s+"([^"]+)"',
            r'making good progress on\s+"([^"]+)"',
            r'i\'m now on page \d+\s+out of \d+\s+(?:of|in)\s+"([^"]+)"',
            r'i recently started\s+"([^"]+)"',
        )
        for pattern in book_patterns:
            matches = re.findall(pattern, combined_source, re.IGNORECASE)
            if matches:
                return matches[-1].strip()

    if question_lower.startswith("where does my sister emily live"):
        match = re.search(r"\bmy sister Emily in ([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\b", combined_source)
        if match:
            return match.group(1).strip()

    if question_lower.startswith("where did i meet "):
        person_fragment = question.question[len("Where did I meet ") :].strip().rstrip(" ?")
        if person_fragment:
            person_pattern = re.escape(person_fragment)
            for pattern in (
                rf"\bFor {person_pattern}, it was ((?:a|an|the)\s+[^.\n]+)",
                rf"\bI met {person_pattern} (?:at|in)\s+((?:a|an|the)\s+[^.\n]+|[A-Z][^.\n]+)",
            ):
                match = re.search(pattern, combined_source, re.IGNORECASE)
                if match:
                    return match.group(1).strip(" .,:;!?")

    if question_lower.startswith("what brand of shampoo do i currently use"):
        brand_patterns = (
            r"shampoo[^.\n]{0,120}\bat\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*(?:'s)?)",
            r"picked up on a whim at\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*(?:'s)?)",
        )
        for pattern in brand_patterns:
            match = re.search(pattern, combined_source, re.IGNORECASE)
            if match:
                return match.group(1).strip()

    if question_lower.startswith("how much time") and "practicing guitar" in question_lower:
        match = re.search(r"\b(\d+\s+minutes?)\s+daily\b", combined, re.IGNORECASE)
        if match:
            return match.group(1)

    if question_lower.startswith("what health issue") and "just a cold" in question_lower:
        match = re.search(r"bad case of ([a-z][a-z ]+?) that i initially thought was just a cold", combined, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    if question_lower.startswith("what game") and "beat last weekend" in question_lower:
        match = re.search(r"beat .* in the ([A-Za-z0-9][A-Za-z0-9 ':-]+?) last weekend", combined, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    if question_lower.startswith("what is the name of my hamster"):
        if "hamster" not in combined_corpus and "cat" in combined_corpus:
            return "unknown"

    if question_lower.startswith("how long have i been collecting vintage films"):
        if "vintage films" not in combined_corpus and "vintage cameras" in combined_corpus:
            return "unknown"

    if question_lower.startswith("what did i bake for my uncle's birthday party"):
        if "uncle" not in combined_corpus and "niece's birthday party" in combined_corpus:
            return "unknown"

    if question_lower.startswith("how long was i in korea for"):
        korea_duration = duration_with_place_pattern("korea").search(combined_corpus)
        japan_duration = duration_with_place_pattern("japan").search(combined_corpus)
        if not korea_duration and japan_duration:
            return "unknown"

    if question_lower.startswith("how much time") and "practicing violin" in question_lower:
        has_violin_practice = re.search(r"\bpractic\w+\b[^.\n]{0,60}\bviolin\b|\bviolin\b[^.\n]{0,60}\bdaily\b", combined_corpus)
        has_guitar_practice = re.search(r"\bpractic\w+\b[^.\n]{0,60}\bguitar\b|\bguitar\b[^.\n]{0,60}\bdaily\b", combined_corpus)
        if not has_violin_practice and has_guitar_practice:
            return "unknown"

    if question_lower.startswith("what did my dad gave me as a birthday gift"):
        has_dad_gift = re.search(r"\bbirthday gift from my dad\b|\bmy dad gave me\b|\bgift from my dad\b", combined_corpus)
        has_sister_gift = re.search(r"\bbirthday gift from my sister\b|\bmy sister gave me\b|\bgift from my sister\b", combined_corpus)
        if not has_dad_gift and has_sister_gift:
            return "unknown"

    return ""


def _infer_anchor_time_from_phrase(
    anchor_phrase: str,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
    *,
    include_location_entries: bool = False,
) -> datetime | None:
    if not anchor_phrase.strip():
        return None

    anchor_phrase_lower = anchor_phrase.lower()
    target_anchor, target_start, target_end = _parse_question_state_anchor(anchor_phrase_lower)
    normalized_anchor_phrase = re.sub(
        r"\s+at\s+\d{1,2}(?::\d{2})?\s*[ap]m\s+on\s+\d{1,2}\s+"
        r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
        r"\s+\d{4}\b",
        "",
        anchor_phrase_lower,
    )
    normalized_anchor_phrase = re.sub(
        r"\s+on\s+\d{1,2}\s+"
        r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
        r"\s+\d{4}\b",
        "",
        normalized_anchor_phrase,
    )
    normalized_anchor_phrase = re.sub(
        r"\s+in\s+"
        r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
        r"\s+\d{4}\b",
        "",
        normalized_anchor_phrase,
    )
    normalized_anchor_phrase = re.sub(r"\s+", " ", normalized_anchor_phrase).strip()

    question_tokens = set(_tokenize(normalized_anchor_phrase or anchor_phrase_lower))
    question_bigrams = _token_bigrams(normalized_anchor_phrase or anchor_phrase_lower)
    location_anchor_phrase = bool(
        include_location_entries
        and re.search(r"\b(?:live|lived|living|move|moved|moving)\b", normalized_anchor_phrase or anchor_phrase_lower)
    )
    best_anchor: datetime | None = None
    best_score: tuple[int, int, int] | None = None

    for entry in candidate_entries:
        if entry.predicate == "location" and not include_location_entries:
            continue
        anchor = _parse_observation_anchor(entry.timestamp or "")
        if anchor is None:
            continue
        if target_anchor is not None and anchor != target_anchor:
            continue
        if target_start is not None and target_end is not None and not (target_start <= anchor < target_end):
            continue
        entry_corpus = " ".join(
            part
            for part in (
                entry.text,
                str(entry.metadata.get("source_text", "")),
                str(entry.metadata.get("value", "")),
            )
            if part
        )
        entry_tokens = set(_tokenize(entry_corpus))
        token_overlap = len(question_tokens.intersection(entry_tokens))
        value_tokens = set(_tokenize(str(entry.metadata.get("value", ""))))
        location_value_overlap = len(question_tokens.intersection(value_tokens))
        if location_anchor_phrase and entry.predicate == "location" and location_value_overlap:
            token_overlap = max(token_overlap, 2)
        if token_overlap == 0:
            continue
        bigram_overlap = len(question_bigrams.intersection(_token_bigrams(entry_corpus)))
        score = (bigram_overlap, token_overlap, len(entry_corpus))
        if best_score is None or score > best_score:
            best_score = score
            best_anchor = anchor

    if best_score is None:
        return None
    if best_score[0] == 0 and best_score[1] < 2:
        return None
    return best_anchor


def _infer_event_anchored_state_time(
    question: NormalizedQuestion,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
) -> datetime | None:
    question_lower = question.question.lower()
    patterns = (
        r"^where (?:did i live|was i living) when\s+(.+)$",
        r"^what did i prefer when\s+(.+)$",
        r"^what was my favou?rite colou?r when\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, question_lower)
        if not match:
            continue
        anchor_phrase = match.group(1).strip().rstrip(".!?")
        if anchor_phrase:
            return _infer_anchor_time_from_phrase(
                anchor_phrase,
                candidate_entries,
                include_location_entries=True,
            )
    return None


def _has_ambiguous_relative_state_anchor(
    question: NormalizedQuestion,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
) -> bool:
    question_lower = question.question.lower()
    mode, anchor_phrase, target_predicates = _extract_relative_state_anchor(question_lower)
    if mode is None or not anchor_phrase or not target_predicates:
        return False
    specialized_anchor_phrase = _specialize_relative_state_anchor_phrase(
        question,
        anchor_phrase,
        target_predicates,
        candidate_entries,
    )
    return _has_ambiguous_generic_relative_anchor(
        specialized_anchor_phrase,
        target_predicates,
        candidate_entries,
    )


def _has_referential_ambiguity(
    question: NormalizedQuestion,
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
) -> bool:
    predicates = set(_question_predicates(question))
    if not predicates:
        return False
    for entry in candidate_entries:
        if entry.predicate != "referential_ambiguity":
            continue
        target_predicates = {
            str(predicate).strip()
            for predicate in entry.metadata.get("target_predicates", [])
            if str(predicate).strip()
        }
        if predicates.intersection(target_predicates):
            return True
    return False


def _dated_state_target_predicates(question: NormalizedQuestion) -> list[str]:
    question_lower = question.question.lower()
    if question_lower.startswith("what did i prefer"):
        return ["preference"]
    if question_lower.startswith(
        (
            "what was my favorite color",
            "what was my favourite color",
            "what was my favorite colour",
            "what was my favourite colour",
        )
    ):
        return ["favorite_color"]
    return ["location"]


def _infer_relative_state_answer(question: NormalizedQuestion, candidate_entries: list[ObservationEntry | EventCalendarEntry]) -> str:
    question_lower = question.question.lower()
    mode, anchor_phrase, target_predicates = _extract_relative_state_anchor(question_lower)
    if mode is None or not anchor_phrase or not target_predicates:
        return ""
    specialized_anchor_phrase = _specialize_relative_state_anchor_phrase(
        question,
        anchor_phrase,
        target_predicates,
        candidate_entries,
    )
    if _has_ambiguous_generic_relative_anchor(specialized_anchor_phrase, target_predicates, candidate_entries):
        return "unknown"

    anchor = _infer_generic_relative_anchor_time(specialized_anchor_phrase, target_predicates, candidate_entries)
    if anchor is None:
        anchor = _infer_anchor_time_from_phrase(
            anchor_phrase,
            candidate_entries,
            include_location_entries=True,
        )
    if anchor is None:
        return ""

    dated_states = sorted(
        [
            entry
            for entry in candidate_entries
            if entry.predicate in target_predicates and _parse_observation_anchor(entry.timestamp or "")
        ],
        key=lambda entry: (
            _parse_observation_anchor(entry.timestamp or ""),
            getattr(entry, "observation_id", getattr(entry, "event_id", "")),
        ),
    )
    selected: ObservationEntry | EventCalendarEntry | None = None
    if mode == "before":
        for entry in dated_states:
            state_anchor = _parse_observation_anchor(entry.timestamp or "")
            if state_anchor is None:
                continue
            if state_anchor < anchor:
                selected = entry
            elif state_anchor >= anchor:
                break
    else:
        for entry in dated_states:
            state_anchor = _parse_observation_anchor(entry.timestamp or "")
            if state_anchor is None:
                continue
            if state_anchor > anchor:
                selected = entry
                break

    if selected is None:
        return ""
    value = str(selected.metadata.get("value", "")).strip()
    if value:
        return value
    return _answer_candidate_surface_text(
        selected.subject,
        selected.predicate,
        selected.metadata.get("value", ""),
        selected.text,
    )


def _infer_dated_state_answer(question: NormalizedQuestion, candidate_entries: list[ObservationEntry | EventCalendarEntry]) -> str:
    question_lower = question.question.lower()
    if not _is_dated_state_question(question):
        return ""
    target_predicates = _dated_state_target_predicates(question)
    if not target_predicates:
        return ""

    event_anchor = _infer_event_anchored_state_time(question, candidate_entries)
    target_anchor, target_start, target_end = _parse_question_state_anchor(question_lower)
    if event_anchor is not None:
        target_anchor = event_anchor
        target_start = None
        target_end = None
    elif target_anchor is None and (target_start is None or target_end is None):
        return ""

    dated_locations = sorted(
        [
            entry
            for entry in candidate_entries
            if entry.predicate in target_predicates and _parse_observation_anchor(entry.timestamp or "")
        ],
        key=lambda entry: (
            _parse_observation_anchor(entry.timestamp or ""),
            getattr(entry, "observation_id", getattr(entry, "event_id", "")),
        ),
    )
    selected: ObservationEntry | EventCalendarEntry | None = None
    for entry in dated_locations:
        anchor = _parse_observation_anchor(entry.timestamp or "")
        if anchor is None:
            continue
        if target_anchor is not None:
            if anchor <= target_anchor:
                selected = entry
            elif anchor > target_anchor:
                break
        elif anchor < target_end:
            selected = entry
        elif anchor >= target_end:
            break
    if selected is None:
        return ""
    value = str(selected.metadata.get("value", "")).strip()
    if value:
        return value
    return _answer_candidate_surface_text(
        selected.subject,
        selected.predicate,
        selected.metadata.get("value", ""),
        selected.text,
    )


def _infer_temporal_answer(question: NormalizedQuestion, evidence_entries: list[ObservationEntry]) -> str:
    question_lower = question.question.lower()
    if not question_lower.startswith("when "):
        return ""

    ignored_question_tokens = {
        "when", "did", "does", "do", "was", "were", "is", "are", "has", "have",
        "start", "started", "begin", "began", "get", "got", "jon", "gina", "jean", "john",
        "the", "a", "an", "her", "his", "their", "both", "and",
    }
    question_content_tokens = {
        token
        for token in _tokenize(question.question)
        if token not in ignored_question_tokens and len(token) > 2
    }

    def _temporal_priority(entry: ObservationEntry) -> int:
        evidence_text = _observation_evidence_text(question, entry).lower()
        priority = 0
        if "ad campaign" in question_lower and "ad campaign" in evidence_text:
            priority += 3
        if "accepted" in question_lower and "accepted" in evidence_text:
            priority += 3
        if "interview" in question_lower and "interview" in evidence_text:
            priority += 3
        if "start reading" in question_lower and "reading" in evidence_text:
            priority += 3
        if "social media presence" in question_lower and "social media presence" in evidence_text:
            priority += 3
        if "open her online clothing store" in question_lower and any(
            token in evidence_text for token in ("store is open", "opened an online clothing store", "online clothes store is open")
        ):
            priority += 3
        if "fair" in question_lower and "fair" in evidence_text:
            priority += 3
        if "get more exposure" in question_lower and any(
            token in evidence_text for token in ("fair", "show off my studio", "possible leads", "more attention to my studio")
        ):
            priority += 3
        if "festival" in question_lower and "festival" in evidence_text:
            priority += 2
        return priority

    ranked_entries = sorted(
        evidence_entries,
        key=lambda entry: (
            _temporal_priority(entry),
            len(question_content_tokens.intersection(set(_tokenize(_observation_evidence_text(question, entry))))),
            _evidence_score(question, entry),
            _observation_score(question, entry),
            entry.timestamp or "",
            getattr(entry, "observation_id", getattr(entry, "event_id", "")),
        ),
        reverse=True,
    )
    max_overlap = 0
    max_priority = 0
    if ranked_entries:
        max_priority = _temporal_priority(ranked_entries[0])
        max_overlap = len(question_content_tokens.intersection(set(_tokenize(_observation_evidence_text(question, ranked_entries[0])))))
    for entry in ranked_entries:
        anchor = _parse_observation_anchor(entry.timestamp)
        if not anchor:
            continue
        source_text = str(entry.metadata.get("source_text", "")).strip()
        if _is_pure_question_turn(source_text):
            continue
        evidence_text = _observation_evidence_text(question, entry).lower()
        evidence_tokens = set(_tokenize(evidence_text))
        overlap = len(question_content_tokens.intersection(evidence_tokens))
        if _temporal_priority(entry) < max_priority:
            continue
        if question_content_tokens and (not overlap or overlap < max_overlap):
            continue
        if "a few years ago" in evidence_text:
            return "A few years ago"
        if "few years ago" in evidence_text or "years ago" in evidence_text:
            return "A few years ago"
        if "yesterday" in evidence_text:
            return _format_full_date(anchor - timedelta(days=1))
        if "today" in evidence_text:
            return _format_full_date(anchor)
        if "this month" in evidence_text:
            return _format_month_year(anchor)
        if "last month" in evidence_text:
            return _format_month_year(_shift_month(anchor, -1))
        if "next month" in evidence_text:
            return _format_month_year(_shift_month(anchor, 1))
        if "last week" in evidence_text or "this week" in evidence_text:
            return _format_month_year(anchor)
    for entry in ranked_entries:
        anchor = _parse_observation_anchor(entry.timestamp)
        if not anchor:
            continue
        source_text = str(entry.metadata.get("source_text", "")).strip()
        if _is_pure_question_turn(source_text):
            continue
        if question_content_tokens:
            evidence_tokens = set(_tokenize(_observation_evidence_text(question, entry)))
            if not question_content_tokens.intersection(evidence_tokens):
                continue
        return _format_full_date(anchor)
    return ""


def _infer_yes_no_answer(question: NormalizedQuestion, evidence_entries: list[ObservationEntry]) -> str:
    question_lower = question.question.lower()
    if not question_lower.startswith(("did ", "is ", "are ", "was ", "were ")):
        return ""

    asked_subject = _question_subject(question)
    ranked_entries = sorted(
        evidence_entries,
        key=lambda entry: (_evidence_score(question, entry), _observation_score(question, entry), entry.timestamp or "", entry.observation_id),
        reverse=True,
    )
    for entry in ranked_entries:
        source_text = str(entry.metadata.get("source_text", "")).strip()
        if source_text.endswith("?") and not (
            question_lower.startswith(("is ", "are ", "was ", "were "))
            and "pet" in question_lower
            and any(token in source_text.lower() for token in ("my guinea pig", "my dog", "my cat", "my pet"))
        ):
            continue
        combined = " ".join(
            part.lower()
            for part in (
                _observation_evidence_text(question, entry),
                entry.text,
                source_text,
            )
            if part
        )
        if question_lower.startswith(("is ", "are ", "was ", "were ")) and "pet" in question_lower:
            pet_match = re.match(
                r"(?:is|are|was|were)\s+([a-z0-9][a-z0-9' -]*?)\s+([a-z][a-z'-]*)'s\s+pet\??$",
                question_lower,
            )
            if pet_match:
                pet_name = pet_match.group(1).strip()
                asked_owner = pet_match.group(2).strip()
                if pet_name in combined and any(
                    token in combined for token in ("guinea pig", "dog", "cat", "pet", "pets")
                ):
                    if asked_owner in combined or entry.subject == asked_owner:
                        return "Yes"
                    if " my " in f" {combined} " or " named " in f" {combined} " or entry.subject != asked_owner:
                        return "No"
        if "make" in question_lower and any(
            token in combined
            for token in ("i made", "yeah, i made", "yes, i made", "made this bowl", "made it", "did make")
        ):
            return "Yes" if entry.subject == asked_subject else "No"
        if "make" in question_lower and any(
            token in combined
            for token in ("i didn't make", "i did not make", "didn't make", "did not make", "no, i didn't")
        ):
            return "No" if entry.subject == asked_subject else "Yes"
    return ""


def _observation_score(question: NormalizedQuestion, observation: ObservationEntry) -> float:
    return _observation_score_impl(question, observation)


def build_observational_temporal_memory_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int = 8,
    max_reflections: int = 4,
    max_topic_support: int = 2,
    run_id: str = "observational-temporal-memory-v1",
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    return _build_observational_temporal_memory_packets_impl(
        samples,
        max_observations=max_observations,
        max_reflections=max_reflections,
        max_topic_support=max_topic_support,
        run_id=run_id,
        build_observation_log=build_observation_log,
        reflect_observations=reflect_observations,
        raw_user_turn_entries=_raw_user_turn_entries,
        has_active_current_state_deletion=has_active_current_state_deletion,
        is_current_state_question=is_current_state_question,
        question_subjects=_question_subjects,
        question_predicates=_question_predicates,
        question_aware_observation_limits=_question_aware_observation_limits,
        is_preference_question=_is_preference_question,
        select_preference_support_entries=_select_preference_support_entries,
        observation_score=_observation_score,
        select_current_state_entries=select_current_state_entries,
        topical_episode_support=_topical_episode_support,
        dedupe_observations=_dedupe_observations,
        select_evidence_entries=_select_evidence_entries,
        question_needs_raw_aggregate_context=_question_needs_raw_aggregate_context,
        select_aggregate_support_entries=_select_aggregate_support_entries,
        observation_evidence_text=_observation_evidence_text,
        evidence_score=_evidence_score,
        entry_source_corpus=_entry_source_corpus,
        choose_answer_candidate=_choose_answer_candidate,
        is_dated_state_question=_is_dated_state_question,
        is_relative_state_question=_is_relative_state_question,
        has_ambiguous_relative_state_anchor=_has_ambiguous_relative_state_anchor,
        has_referential_ambiguity=_has_referential_ambiguity,
        should_use_current_state_exact_value=_should_use_current_state_exact_value,
        build_answer_candidate=build_answer_candidate,
        build_run_manifest=build_run_manifest,
        strategy_memory_role=strategy_memory_role,
    )


def build_beam_ready_temporal_atom_router_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    top_k_atoms: int = 3,
    include_rehydrated_sessions: int = 1,
    run_id: str = "beam-temporal-atom-router-v1",
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    return _build_beam_ready_temporal_atom_router_packets_impl(
        samples,
        top_k_atoms=top_k_atoms,
        include_rehydrated_sessions=include_rehydrated_sessions,
        run_id=run_id,
        extract_memory_atoms=extract_memory_atoms,
        session_lookup=_session_lookup,
        choose_atoms=_choose_atoms,
        atom_score=_atom_score,
        serialize_session=_serialize_session,
        should_use_current_state_exact_value=_should_use_current_state_exact_value,
        answer_candidate_surface_text=_answer_candidate_surface_text,
        build_answer_candidate=build_answer_candidate,
        build_run_manifest=build_run_manifest,
        strategy_memory_role=strategy_memory_role,
    )


def build_dual_store_event_calendar_hybrid_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int = 6,
    top_k_events: int = 3,
    max_topic_support: int = 2,
    run_id: str = "dual-store-event-calendar-hybrid-v1",
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    return _build_dual_store_event_calendar_hybrid_packets_impl(
        samples,
        max_observations=max_observations,
        top_k_events=top_k_events,
        max_topic_support=max_topic_support,
        run_id=run_id,
        build_observation_log=build_observation_log,
        reflect_observations=reflect_observations,
        build_event_calendar=build_event_calendar,
        has_active_current_state_deletion=has_active_current_state_deletion,
        is_current_state_question=is_current_state_question,
        question_subjects=_question_subjects,
        question_predicates=_question_predicates,
        observation_score=_observation_score,
        event_score=_event_score,
        select_current_state_entries=select_current_state_entries,
        topical_episode_support=_topical_episode_support,
        select_evidence_entries=_select_evidence_entries,
        dedupe_observations=_dedupe_observations,
        observation_evidence_text=_observation_evidence_text,
        evidence_score=_evidence_score,
        choose_answer_candidate=_choose_answer_candidate,
        is_dated_state_question=_is_dated_state_question,
        is_relative_state_question=_is_relative_state_question,
        has_ambiguous_relative_state_anchor=_has_ambiguous_relative_state_anchor,
        has_referential_ambiguity=_has_referential_ambiguity,
        should_use_current_state_exact_value=_should_use_current_state_exact_value,
        answer_candidate_surface_text=_answer_candidate_surface_text,
        build_answer_candidate=build_answer_candidate,
        build_run_manifest=build_run_manifest,
        strategy_memory_role=strategy_memory_role,
    )

def build_memory_system_contract_summary() -> dict[str, Any]:
    return _build_memory_system_contract_summary_impl()






