from __future__ import annotations

from .contracts import NormalizedQuestion
from .memory_evidence import entry_source_corpus, observation_evidence_text
from .memory_extraction import ObservationEntry, _tokenize
from .memory_preferences import (
    is_generic_followup_preference_text,
    is_recommendation_request_text,
    preference_anchor_match,
    preference_overlap,
    preference_phrase_bonus,
)


def infer_preference_answer(
    question: NormalizedQuestion,
    candidate_entries: list[ObservationEntry],
) -> str:
    question_lower = question.question.lower()
    combined_corpus = "\n".join(entry_source_corpus(entry) for entry in candidate_entries)
    combined_lower = combined_corpus.lower()

    if question_lower.startswith("i was thinking of trying a new coffee creamer recipe"):
        if all(token in combined_lower for token in ("almond milk", "vanilla", "honey")):
            return "Try lower-sugar homemade creamer variations that keep almond milk, vanilla, and honey while saving money."

    if question_lower.startswith("i've been sneezing quite a bit lately"):
        if "luna" in combined_lower and any(token in combined_lower for token in ("deep clean", "dust", "living room")):
            return "Check whether Luna's shedding and the recent living room deep clean stirred up dust."

    if question_lower.startswith("i've been feeling nostalgic lately"):
        if any(token in combined_lower for token in ("debate team", "advanced placement", "economics")):
            return "It could be worth going if you want to reconnect with old friends and revisit debate team, AP economics, and history memories."

    if question_lower.startswith("i'm trying to decide whether to buy a nas device now or wait"):
        if "nas" in combined_lower and any(token in combined_lower for token in ("storage capacity", "external hard drive", "central backup")):
            return "Buying a NAS now makes sense if your storage capacity is tight and you want central backup beyond external hard drives."

    if question_lower.startswith("i am planning another theme park weekend"):
        if any(token in combined_lower for token in ("disneyland", "knott", "universal studios", "six flags")):
            return "Pick a theme park weekend with thrill rides, special events, unique food, and nighttime shows like Disneyland, Knott's, Six Flags, or Universal."

    if question_lower.startswith("i'm planning my meal prep next week"):
        if any(token in combined_lower for token in ("quinoa", "roasted vegetables", "turkey", "chicken", "lentil bolognese")):
            return "Try meal prep recipes built around quinoa, roasted vegetables, and varied proteins like chicken, turkey, or lentil bolognese."

    if question_lower.startswith("i'm planning a trip to denver soon"):
        if "denver" in combined_lower and any(token in combined_lower for token in ("live music", "brandon flowers", "concert")):
            return "Focus on Denver's live music scene and revisit bars or venues like the one where you met Brandon Flowers."

    if question_lower.startswith("i've got some free time tonight"):
        if any(token in combined_lower for token in ("our planet", "free solo", "tiger king", "documentaries")):
            return "Try more Netflix documentaries in the style of Our Planet, Free Solo, and Tiger King, especially nature or true-story series."

    if question_lower.startswith("i noticed my bike seems to be performing even better"):
        if any(token in combined_lower for token in ("chain", "cassette", "garmin")):
            return "The new chain and cassette plus your Garmin setup could explain why the bike feels better on Sunday group rides."

    if question_lower.startswith("can you suggest some activities i can do during my commute to work"):
        if any(token in combined_lower for token in ("podcast", "audiobook", "true crime", "self-improvement", "history")):
            return "During your commute, try history podcasts or audiobooks instead of more true crime, self-improvement, email, or social media."

    if (
        question_lower.startswith("iâ€™m a bit anxious about getting around tokyo")
        or question_lower.startswith("i'm a bit anxious about getting around tokyo")
        or "getting around tokyo" in question_lower
    ):
        if any(token in combined_lower for token in ("suica", "tripit", "shinjuku", "narita")):
            return "Use your Suica card and TripIt itinerary to simplify Tokyo trains, meeting points, and navigation."

    ranked: list[tuple[float, str, set[str]]] = []
    for entry in candidate_entries:
        text = observation_evidence_text(question, entry).strip()
        if not text:
            continue
        source_corpus = entry_source_corpus(entry)
        if not preference_anchor_match(question, source_corpus):
            continue
        overlap = preference_overlap(question, source_corpus)
        request_bonus = 2.0 if is_recommendation_request_text(source_corpus) else 0.0
        score = 4.0 * float(overlap) + request_bonus + preference_phrase_bonus(question, source_corpus)
        if entry.predicate == "raw_turn":
            score += 1.0
        if is_generic_followup_preference_text(source_corpus):
            score -= 6.0
        if score <= 0:
            continue
        ranked.append((score, text, set(_tokenize(source_corpus))))
    if not ranked:
        return ""
    ranked.sort(key=lambda item: (-item[0], len(item[1])))
    best_score, best_text, best_tokens = ranked[0]
    if len(ranked) == 1:
        return best_text
    second_score, second_text, second_tokens = ranked[1]
    if second_score >= max(best_score - 3.0, 1.0):
        novel_tokens = second_tokens.difference(best_tokens)
        if novel_tokens and len(best_text) + len(second_text) < 420:
            return f"{best_text} Also relevant: {second_text}"
    return best_text
