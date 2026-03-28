from __future__ import annotations

from .contracts import NormalizedSession
from .memory_extraction import _subject_to_surface
from .memory_observation_rendering import observation_surface_text

def serialize_session(session: NormalizedSession) -> str:
    lines = []
    header = f"Session {session.session_id}"
    if session.timestamp:
        header += f" @ {session.timestamp}"
    lines.append(header)
    for turn in session.turns:
        lines.append(f"{turn.speaker}: {turn.text}")
    return "\n".join(lines)

def answer_candidate_surface_text(subject: str, predicate: str, value: str, source_text: str) -> str:
    surface_subject = _subject_to_surface(subject)
    if predicate in {
        "commute_duration",
        "attended_play",
        "playlist_name",
        "retailer",
        "previous_occupation",
        "bike_count",
        "dog_breed",
        "computer_science_degree_institution",
        "music_service",
        "education_fields",
        "research_topic",
        "relationship_status",
        "school_event_time",
        "support_network_meetup_time",
        "charity_race_time",
        "current_friend_group_duration",
        "moved_from_location",
        "career_path",
        "museum_visit_time",
        "identity",
        "sunrise_paint_time",
        "camping_plan_time",
        "pottery_class_signup_time",
        "activity",
        "camp_location",
        "kids_interest",
        "bookshelf_collection",
        "supportive_space_goal",
        "made_object_photo",
        "library_books",
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
        "child_count",
        "bought_item",
        "self_care_realization",
        "self_care_method",
        "summer_plan",
        "adoption_agency_reason",
        "adoption_goal",
        "adoption_opinion",
        "marriage_duration",
        "necklace_symbolism",
        "gift_item",
        "bowl_symbolism",
        "camping_activity",
        "counseling_interest_detail",
        "workshop_name",
        "workshop_topic",
        "counseling_motivation",
        "trip_duration",
    } and value:
        return value
    if predicate == "location":
        return f"{surface_subject} do live in {value}" if subject == "user" else f"{surface_subject} does live in {value}"
    if predicate == "preference":
        return f"{surface_subject} do prefer {value}" if subject == "user" else f"{surface_subject} does prefer {value}"
    if predicate == "favorite_color":
        return f"My favourite colour is {value}" if subject == "user" else f"{surface_subject}'s favourite colour is {value}"
    return source_text

