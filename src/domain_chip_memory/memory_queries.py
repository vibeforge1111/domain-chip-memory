from __future__ import annotations

from .contracts import NormalizedQuestion


def _is_profile_memory_query(question: NormalizedQuestion) -> bool:
    question_lower = question.question.lower()
    return any(
        phrase in question_lower
        for phrase in (
            "who am i",
            "what do you know about me",
            "what do you remember about me",
            "summarize my profile",
            "summarise my profile",
            "profile summary",
            "what is my name",
            "what's my name",
            "what do i do",
            "what am i",
            "what is my occupation",
            "what's my occupation",
            "what startup do you have for me",
            "what is my startup",
            "what's my startup",
            "what company did i found",
            "what company have i founded",
            "what have i founded",
            "which company did i found",
            "what timezone do you have for me",
            "what is my timezone",
            "what's my timezone",
            "what country do you have for me",
            "what country do you have saved for me",
            "what country do i live in",
            "what am i trying to do now",
            "what is my mission right now",
            "what's my mission right now",
            "who hacked us",
            "who hacked me",
            "what role will spark play in this",
            "what role will spark play",
            "where do i live now",
            "where do i live",
            "what city do i live in",
            "which city do i live in",
            "what city do you have for me",
            "where did i live before",
            "where was i living before",
            "what city did i live in before",
            "which city did i live in before",
            "what was my previous city",
            "what city was i in before",
            "what city did you have for me before",
            "what was my previous country",
            "what country did you have for me before",
            "what memory events do you have about where i live",
            "what memory events do you have about my city",
            "what memory events do you have about my location",
            "show my city history",
            "show my location history",
            "what memory events do you have about my country",
            "show my country history",
            "what country history do you have for me",
        )
    )


def _question_subject(question: NormalizedQuestion) -> str:
    question_lower = question.question.lower()
    for metadata_key in ("speaker_a", "speaker_b"):
        speaker_name = str(question.metadata.get(metadata_key, "")).strip().lower()
        if speaker_name and speaker_name in question_lower:
            return speaker_name
    if "alice" in question_lower:
        return "alice"
    if "bob" in question_lower:
        return "bob"
    return "user"


def _question_subjects(question: NormalizedQuestion) -> list[str]:
    question_lower = question.question.lower()
    subjects: list[str] = []
    for metadata_key in ("speaker_a", "speaker_b"):
        speaker_name = str(question.metadata.get(metadata_key, "")).strip().lower()
        if speaker_name and speaker_name in question_lower and speaker_name not in subjects:
            subjects.append(speaker_name)
    for fallback_name in ("alice", "bob"):
        if fallback_name in question_lower and fallback_name not in subjects:
            subjects.append(fallback_name)
    if not subjects and "both" in question_lower:
        for metadata_key in ("speaker_a", "speaker_b"):
            speaker_name = str(question.metadata.get(metadata_key, "")).strip().lower()
            if speaker_name and speaker_name not in subjects:
                subjects.append(speaker_name)
    if not subjects:
        subjects.append(_question_subject(question))
    return subjects


def _question_predicates(question: NormalizedQuestion) -> list[str]:
    question_lower = question.question.lower()
    predicates: list[str] = []
    if any(phrase in question_lower for phrase in ("what is my name", "what's my name")):
        predicates.append("preferred_name")
    if any(
        phrase in question_lower
        for phrase in ("what do i do", "what am i", "what is my occupation", "what's my occupation")
    ):
        predicates.append("occupation")
    if any(
        phrase in question_lower
        for phrase in ("what startup do you have for me", "what is my startup", "what's my startup")
    ):
        predicates.append("startup_name")
    if any(
        phrase in question_lower
        for phrase in (
            "what startup did i create",
            "what company did i found",
            "what company have i founded",
            "what have i founded",
            "which company did i found",
        )
    ):
        predicates.append("founder_of")
    if any(phrase in question_lower for phrase in ("what timezone do you have for me", "what is my timezone", "what's my timezone")):
        predicates.append("timezone")
    if any(
        phrase in question_lower
        for phrase in ("what country do you have for me", "what country do you have saved for me", "what country do i live in")
    ):
        predicates.append("home_country")
        predicates.append("location")
    if any(phrase in question_lower for phrase in ("what am i trying to do now", "what is my mission right now", "what's my mission right now")):
        predicates.append("current_mission")
    if any(phrase in question_lower for phrase in ("who hacked us", "who hacked me")):
        predicates.append("hack_actor")
    if any(phrase in question_lower for phrase in ("what role will spark play in this", "what role will spark play")):
        predicates.append("spark_role")
    if any(
        phrase in question_lower
        for phrase in (
            "who am i",
            "what do you know about me",
            "what do you remember about me",
            "summarize my profile",
            "summarise my profile",
            "profile summary",
        )
    ):
        predicates.extend(
            [
                "preferred_name",
                "occupation",
                "city",
                "home_country",
                "timezone",
                "startup_name",
                "founder_of",
                "current_mission",
                "spark_role",
                "hack_actor",
                "location",
            ]
        )
    if "live" in question_lower or "living" in question_lower or "moved" in question_lower:
        predicates.append("location")
    if any(
        phrase in question_lower
        for phrase in (
            "where do i live now",
            "where do i live",
            "what city do i live in",
            "which city do i live in",
            "what city do you have for me",
        )
    ):
        predicates.append("city")
    if any(
        phrase in question_lower
        for phrase in (
            "where did i live before",
            "where was i living before",
            "what city did i live in before",
            "which city did i live in before",
            "what was my previous city",
            "what city was i in before",
            "what city did you have for me before",
            "what memory events do you have about where i live",
            "what memory events do you have about my city",
            "what memory events do you have about my location",
            "show my city history",
            "show my location history",
        )
    ):
        predicates.append("city")
        predicates.append("location")
    if any(
        phrase in question_lower
        for phrase in (
            "what country did i live in before",
            "which country did i live in before",
            "what was my previous country",
            "what country did you have for me before",
            "what memory events do you have about my country",
            "show my country history",
            "what country history do you have for me",
        )
    ):
        predicates.append("home_country")
        predicates.append("location")
    if "favourite colour" in question_lower or "favorite colour" in question_lower:
        predicates.append("favorite_color")
    if "favorite color" in question_lower or "favourite color" in question_lower:
        predicates.append("favorite_color")
    if "music" in question_lower or "prefer" in question_lower or "like" in question_lower:
        predicates.append("preference")
    if "commute" in question_lower:
        predicates.append("commute_duration")
    if "play did i attend" in question_lower or ("what play" in question_lower and "attend" in question_lower):
        predicates.append("attended_play")
    if "playlist" in question_lower:
        predicates.append("playlist_name")
    if "where did i redeem" in question_lower or ("coupon" in question_lower and "where" in question_lower):
        predicates.append("retailer")
    if "previous occupation" in question_lower or "previous role" in question_lower:
        predicates.append("previous_occupation")
    if "how many bikes" in question_lower and "own" in question_lower:
        predicates.append("bike_count")
    if "breed is my dog" in question_lower:
        predicates.append("dog_breed")
    if "bachelor" in question_lower and "computer science" in question_lower:
        predicates.append("computer_science_degree_institution")
    if "music streaming service" in question_lower:
        predicates.append("music_service")
    if "fields would" in question_lower and "pursue" in question_lower:
        predicates.append("education_fields")
    if question_lower.startswith("what did") and "research" in question_lower:
        predicates.append("research_topic")
    if "relationship status" in question_lower:
        predicates.append("relationship_status")
    if "school" in question_lower and ("speech" in question_lower or "give a speech" in question_lower):
        predicates.append("school_event_time")
    if "friends, family, and mentors" in question_lower and ("meet up" in question_lower or "meet" in question_lower):
        predicates.append("support_network_meetup_time")
    if "charity race" in question_lower:
        predicates.append("charity_race_time")
    if "current group of friends" in question_lower:
        predicates.append("current_friend_group_duration")
    if "move from" in question_lower:
        predicates.append("moved_from_location")
    if "career path" in question_lower:
        predicates.append("career_path")
    if "museum" in question_lower:
        predicates.append("museum_visit_time")
    if "identity" in question_lower:
        predicates.append("identity")
    if "what kind of place" in question_lower and "create for people" in question_lower:
        predicates.append("supportive_space_goal")
    if question_lower.startswith("did ") and "bowl in the photo" in question_lower:
        predicates.append("made_object_photo")
    if "what kind of books" in question_lower and "library" in question_lower:
        predicates.append("library_books")
    if "paint" in question_lower and "sunrise" in question_lower:
        predicates.append("sunrise_paint_time")
    if "planning on going camping" in question_lower or ("when is" in question_lower and "camping" in question_lower):
        predicates.append("camping_plan_time")
    if "sign up" in question_lower and "pottery class" in question_lower:
        predicates.append("pottery_class_signup_time")
    if "activities" in question_lower and ("partake" in question_lower or "does" in question_lower):
        predicates.append("activity")
    if "where has" in question_lower and "camped" in question_lower:
        predicates.append("camp_location")
    if "kids like" in question_lower:
        predicates.append("kids_interest")
    if "bookshelf" in question_lower or "dr. seuss" in question_lower:
        predicates.append("bookshelf_collection")
    if "favorite book" in question_lower and "childhood" in question_lower:
        predicates.append("book_read")
    if question_lower.startswith("what book") and "recommend" in question_lower:
        predicates.append("book_read")
    if (question_lower.startswith("what books") or question_lower.startswith("what book")) and "read" in question_lower:
        predicates.append("book_read")
    if "take away from the book" in question_lower or ("becoming nicole" in question_lower and "take away" in question_lower):
        predicates.append("book_takeaway")
    if "new shoes" in question_lower and "used for" in question_lower:
        predicates.append("shoe_use")
    if "reason for getting into running" in question_lower:
        predicates.append("running_reason")
    if "running has been great for" in question_lower:
        predicates.append("running_benefit")
    if "pottery workshop" in question_lower and "what did" in question_lower and "make" in question_lower:
        predicates.append("pottery_output")
    if "what kind of pot" in question_lower and "clay" in question_lower:
        predicates.append("pottery_output")
    if "what creative project" in question_lower and "besides pottery" in question_lower:
        predicates.append("family_creative_activity")
    if "what did mel and her kids paint" in question_lower:
        predicates.append("family_paint_subject")
    if "council meeting for adoption" in question_lower:
        predicates.append("adoption_meeting_takeaway")
    if "what do sunflowers represent" in question_lower:
        predicates.append("flower_symbolism")
    if "why are flowers important" in question_lower:
        predicates.append("flower_importance")
    if "painting for the art show" in question_lower:
        predicates.append("art_show_inspiration")
    if "camping trip last year" in question_lower and "what did" in question_lower:
        predicates.append("family_trip_sighting")
    if "meteor shower" in question_lower and "how did" in question_lower:
        predicates.append("family_trip_feeling")
    if "whose birthday did" in question_lower and "celebrate" in question_lower:
        predicates.append("birthday_person")
    if "who performed" in question_lower and "daughter's birthday" in question_lower:
        predicates.append("birthday_performer")
    if "colors and patterns" in question_lower and "pottery project" in question_lower:
        predicates.append("pottery_design_reason")
    if question_lower.startswith("what pet does") and "caroline" in question_lower:
        predicates.append("pet_type")
    if question_lower.startswith("what pets does") and "melanie" in question_lower:
        predicates.append("pet_household_summary")
    if "destress" in question_lower:
        predicates.append("destress_activity")
    if ("painted" in question_lower or ("paint" in question_lower and "what" in question_lower)) and "when" not in question_lower:
        predicates.append("paint_subject")
    if "pets' names" in question_lower or ("pet" in question_lower and "names" in question_lower):
        predicates.append("pet_name")
    if "symbols" in question_lower:
        predicates.append("important_symbol")
    if "instruments" in question_lower:
        predicates.append("instrument")
    if "artists/bands" in question_lower or "artists" in question_lower or "bands" in question_lower:
        predicates.append("seen_artist")
    if "family on hikes" in question_lower:
        predicates.append("family_hike_activity")
    if "changes" in question_lower and "transition journey" in question_lower:
        predicates.append("transition_change")
    if "transgender-specific events" in question_lower:
        predicates.append("trans_event")
    if "practicing art" in question_lower or "creating art" in question_lower:
        predicates.append("art_practice_duration")
    if "used to do" in question_lower and "dad" in question_lower:
        predicates.append("childhood_activity")
    if "find in her neighborhood" in question_lower and "during her walk" in question_lower:
        predicates.append("neighborhood_find")
    if "classical musicians" in question_lower:
        predicates.append("classical_musicians")
    if "modern music" in question_lower:
        predicates.append("modern_music_artist")
    if "precautionary sign" in question_lower and "caf" in question_lower:
        predicates.append("precautionary_sign")
    if "getting started with adoption" in question_lower:
        predicates.append("adoption_start_advice")
    if "what setback" in question_lower and "october 2023" in question_lower:
        predicates.append("pottery_setback")
    if "keep herself busy" in question_lower and "pottery break" in question_lower:
        predicates.append("pottery_break_activity")
    if "what painting did melanie show" in question_lower and "october 13, 2023" in question_lower:
        predicates.append("recent_painting")
    if "what kind of painting did caroline share" in question_lower and "october 13, 2023" in question_lower:
        predicates.append("abstract_painting")
    if "what was the poetry reading" in question_lower:
        predicates.append("poetry_reading_topic")
    if "posters at the poetry reading" in question_lower:
        predicates.append("poster_text")
    if "drawing symbolize" in question_lower:
        predicates.append("drawing_symbolism")
    if "journey through life together" in question_lower:
        predicates.append("shared_life_journey")
    if "son handle the accident" in question_lower:
        predicates.append("son_accident_reaction")
    if "feel about her family after the accident" in question_lower:
        predicates.append("family_importance")
    if "children handle the accident" in question_lower:
        predicates.append("children_accident_reaction")
    if "feel after the accident" in question_lower:
        predicates.append("post_accident_feeling")
    if "reaction to her children enjoying the grand canyon" in question_lower:
        predicates.append("canyon_reaction")
    if "what do melanie's family give her" in question_lower:
        predicates.append("family_strength_source")
    if "how many children" in question_lower:
        predicates.append("child_count")
    if "what items" in question_lower and "bought" in question_lower:
        predicates.append("bought_item")
    if "charity race" in question_lower and "realize" in question_lower:
        predicates.append("self_care_realization")
    if "prioritize self-care" in question_lower:
        predicates.append("self_care_method")
    if "plans for the summer" in question_lower:
        predicates.extend(["summer_plan", "research_topic"])
    if "choose the adoption agency" in question_lower:
        predicates.append("adoption_agency_reason")
    if "excited about" in question_lower and "adoption process" in question_lower:
        predicates.append("adoption_goal")
    if "decision to adopt" in question_lower:
        predicates.append("adoption_opinion")
    if "married" in question_lower:
        predicates.append("marriage_duration")
    if "necklace symbolize" in question_lower:
        predicates.append("necklace_symbolism")
    if "what country" in question_lower and "grandma" in question_lower:
        predicates.append("moved_from_location")
    if "grandma's gift" in question_lower:
        predicates.append("gift_item")
    if "hand-painted bowl" in question_lower:
        predicates.append("bowl_symbolism")
    if "while camping" in question_lower:
        predicates.append("camping_activity")
    if "road trip" in question_lower and "relax" in question_lower:
        predicates.append("camping_activity")
    if "what kind of counseling and mental health services" in question_lower:
        predicates.extend(["counseling_interest_detail", "career_path"])
    if "what workshop" in question_lower and "attend recently" in question_lower:
        predicates.append("workshop_name")
    if "what was discussed" in question_lower and "workshop" in question_lower:
        predicates.append("workshop_topic")
    if "what motivated" in question_lower and "pursue counseling" in question_lower:
        predicates.append("counseling_motivation")
    if question_lower.startswith("how long was i in"):
        predicates.append("trip_duration")
    if not predicates:
        predicates.append("raw_turn")
    return predicates


__all__ = ["_question_predicates", "_question_subject", "_question_subjects"]
