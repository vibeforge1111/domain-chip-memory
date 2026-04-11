from __future__ import annotations

from .memory_extraction import ObservationEntry, _subject_to_surface


_PROFILE_IDENTITY_PREDICATE_ALIASES = {
    "profile.preferred_name": "preferred_name",
    "preferred_name": "preferred_name",
    "name": "preferred_name",
    "profile.occupation": "occupation",
    "occupation": "occupation",
    "profile.city": "city",
    "city": "city",
    "location": "city",
    "profile.home_country": "home_country",
    "home_country": "home_country",
    "country": "home_country",
    "profile.timezone": "timezone",
    "timezone": "timezone",
    "profile.startup_name": "startup_name",
    "startup_name": "startup_name",
    "profile.founder_of": "founder_of",
    "founder_of": "founder_of",
    "profile.spark_role": "spark_role",
    "spark_role": "spark_role",
    "profile.current_mission": "current_mission",
    "current_mission": "current_mission",
    "profile.hack_actor": "hack_actor",
    "hack_actor": "hack_actor",
}


def _ensure_sentence(text: str) -> str:
    normalized = " ".join(str(text or "").strip().split())
    if not normalized:
        return ""
    if normalized[-1] in ".!?":
        return normalized
    return f"{normalized}."


def _with_indefinite_article(value: str) -> str:
    normalized = " ".join(str(value or "").strip().split())
    if not normalized:
        return ""
    lowered = normalized.lower()
    if lowered.startswith(("a ", "an ")):
        return normalized
    article = "an" if normalized[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
    return f"{article} {normalized}"


def _spark_role_sentence(value: str) -> str:
    normalized = " ".join(str(value or "").strip().split())
    if normalized.lower().startswith("important part"):
        return f"Spark will be an {normalized}"
    return f"Spark will be {normalized}"


def _normalize_profile_identity_predicate(predicate: str) -> str | None:
    normalized = str(predicate or "").strip()
    if not normalized:
        return None
    return _PROFILE_IDENTITY_PREDICATE_ALIASES.get(normalized)


def extract_profile_identity_values(entries: list[ObservationEntry]) -> dict[str, str]:
    value_by_predicate: dict[str, str] = {}
    ordered_entries = sorted(
        entries,
        key=lambda entry: (
            getattr(entry, "timestamp", "") or "",
            getattr(entry, "observation_id", "") or getattr(entry, "event_id", ""),
        ),
    )
    for entry in ordered_entries:
        predicate = _normalize_profile_identity_predicate(entry.predicate)
        if predicate is None:
            continue
        value = str(entry.metadata.get("value") or "").strip()
        if value:
            value_by_predicate[predicate] = value
    return value_by_predicate


def build_profile_fact_answer(predicate: str, value: str) -> str:
    normalized_predicate = _normalize_profile_identity_predicate(predicate) or str(predicate or "").strip()
    clean_value = str(value or "").strip()
    if not clean_value:
        return ""
    mapping = {
        "preferred_name": lambda text: f"Your name is {text}.",
        "occupation": lambda text: f"You're {_with_indefinite_article(text)}.",
        "startup_name": lambda text: f"Your startup is {text}.",
        "founder_of": lambda text: f"You founded {text}.",
        "hack_actor": lambda text: f"{text} hacked you.",
        "current_mission": lambda text: f"Your current mission is to {text}.",
        "spark_role": lambda text: _ensure_sentence(_spark_role_sentence(text)),
        "home_country": lambda text: f"Your country is {text}.",
        "timezone": lambda text: f"Your timezone is {text}.",
        "city": lambda text: f"You live in {text}.",
    }
    renderer = mapping.get(normalized_predicate)
    if renderer is None:
        return _ensure_sentence(clean_value)
    return renderer(clean_value)


def build_profile_identity_summary_answer(entries: list[ObservationEntry]) -> str:
    value_by_predicate = extract_profile_identity_values(entries)

    if not value_by_predicate:
        return ""

    sentences: list[str] = []
    name = value_by_predicate.get("preferred_name")
    occupation = value_by_predicate.get("occupation")
    city = value_by_predicate.get("city")
    if name and occupation and city:
        sentences.append(_ensure_sentence(f"You're {name}, {_with_indefinite_article(occupation)} in {city}"))
    elif name and occupation:
        sentences.append(_ensure_sentence(f"You're {name}, {_with_indefinite_article(occupation)}"))
    elif name and city:
        sentences.append(_ensure_sentence(f"You're {name} in {city}"))
    elif name:
        sentences.append(_ensure_sentence(f"You're {name}"))
    elif occupation and city:
        sentences.append(_ensure_sentence(f"You're {_with_indefinite_article(occupation)} in {city}"))
    elif occupation:
        sentences.append(_ensure_sentence(f"You're {_with_indefinite_article(occupation)}"))
    elif city:
        sentences.append(_ensure_sentence(f"You're in {city}"))

    startup_name = value_by_predicate.get("startup_name")
    founder_of = value_by_predicate.get("founder_of")
    if founder_of:
        sentences.append(_ensure_sentence(f"You founded {founder_of}"))
    elif startup_name:
        sentences.append(_ensure_sentence(f"Your startup is {startup_name}"))
    if startup_name and founder_of and startup_name != founder_of:
        sentences.append(_ensure_sentence(f"Your startup is {startup_name}"))

    hack_actor = value_by_predicate.get("hack_actor")
    if hack_actor:
        sentences.append(_ensure_sentence(f"{hack_actor} hacked you"))

    current_mission = value_by_predicate.get("current_mission")
    if current_mission:
        sentences.append(_ensure_sentence(f"Your current mission is to {current_mission}"))

    spark_role = value_by_predicate.get("spark_role")
    if spark_role:
        sentences.append(_ensure_sentence(_spark_role_sentence(spark_role)))

    home_country = value_by_predicate.get("home_country")
    if home_country:
        if city:
            sentences.append(_ensure_sentence(f"Your country is {home_country}"))
        else:
            sentences.append(_ensure_sentence(f"You're based in {home_country}"))

    timezone = value_by_predicate.get("timezone")
    if timezone:
        sentences.append(_ensure_sentence(f"Your timezone is {timezone}"))

    if sentences:
        return " ".join(sentences)

    first_value = next(iter(value_by_predicate.values()))
    return _ensure_sentence(f"Your saved identity detail is {first_value}")


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
    if predicate == "occupation":
        return f"{surface_subject} am an {value}" if subject == "user" else f"{surface_subject} is a {value}"
    if predicate == "startup_name":
        return f"My startup is {value}" if subject == "user" else f"{surface_subject}'s startup is {value}"
    if predicate == "founder_of":
        return f"I am the founder of {value}" if subject == "user" else f"{surface_subject} is the founder of {value}"
    if predicate == "hack_actor":
        return f"We were hacked by {value}" if subject == "user" else f"{surface_subject} was hacked by {value}"
    if predicate == "current_mission":
        return f"I am trying to {value}" if subject == "user" else f"{surface_subject} is trying to {value}"
    if predicate == "spark_role":
        return f"Spark will be an {value}" if subject == "user" else f"{surface_subject} will be an {value}"
    if predicate == "location":
        return f"{surface_subject} do live in {value}" if subject == "user" else f"{surface_subject} does live in {value}"
    if predicate == "preference":
        return f"{surface_subject} do prefer {value}" if subject == "user" else f"{surface_subject} does prefer {value}"
    if predicate == "favorite_color":
        return f"My favourite colour is {value}" if subject == "user" else f"{surface_subject}'s favourite colour is {value}"
    return source_text
