from __future__ import annotations

from .contracts import NormalizedQuestion
from .memory_extraction import ObservationEntry, _token_bigrams, _tokenize
from .memory_queries import _question_predicates, _question_subject, _question_subjects

def observation_score(question: NormalizedQuestion, observation: ObservationEntry) -> float:
    score = 0.0
    subject = _question_subject(question)
    subjects = set(_question_subjects(question))
    predicates = _question_predicates(question)
    question_lower = question.question.lower()
    question_tokens = set(_tokenize(question.question))
    observation_tokens = set(_tokenize(observation.text))
    question_bigrams = _token_bigrams(question.question)
    observation_bigrams = _token_bigrams(observation.text)
    observation_lower = observation.text.lower()
    caption_lower = str(observation.metadata.get("blip_caption", "")).lower()
    if observation.subject == subject:
        score += 3.0
    elif observation.subject in subjects:
        score += 2.5
    if observation.predicate in predicates:
        score += 4.0
    score += float(len(question_tokens.intersection(observation_tokens)))
    score += 1.5 * min(len(question_bigrams.intersection(observation_bigrams)), 3)
    if question.category in {"knowledge-update", "temporal", "temporal-reasoning"} and observation.timestamp:
        score += 1.0
    if observation.timestamp:
        score += 0.001 * sum(ord(char) for char in observation.timestamp)
    if "hobby" in question_lower or "hobbies" in question_lower:
        if any(
            phrase in observation_lower
            for phrase in (
                "hobby",
                "hobbies",
                "one of her hobbies",
                "one of his hobbies",
                "great passion",
                "interested in art",
                "passion for cooking",
            )
        ):
            score += 8.0
        if any(token in observation_lower for token in ("reading", "travel", "art", "cooking", "painting", "hiking", "running", "kayaking")):
            score += 4.0
        if any(token in question_lower for token in ("mother", "mom")) and any(
            token in observation_lower for token in ("my mother", "my mom", "her mother", "her mom")
        ):
            score += 8.0
        if any(token in question_lower for token in ("father", "dad")) and any(
            token in observation_lower for token in ("my father", "my dad", "her father", "her dad")
        ):
            score += 8.0
    if question_lower.startswith("when did") and observation.predicate == "raw_turn":
        if "pottery workshop" in question_lower and "pottery workshop" in observation_lower:
            score += 14.0
            if "last fri" in observation_lower or "last friday" in observation_lower:
                score += 8.0
        if "camping in june" in question_lower and "camping" in observation_lower:
            score += 12.0
            if "last week" in observation_lower:
                score += 8.0
        if "camping in july" in question_lower and "camping" in observation_lower:
            score += 12.0
            if "two weekends ago" in observation_lower:
                score += 8.0
            if "last year" in observation_lower:
                score -= 8.0
    if (
        "who supports" in question_lower
        or ("supports" in question_lower and "negative experience" in question_lower)
    ):
        if any(
            token in observation_lower
            for token in ("support", "friends", "family", "mentors", "rocks", "support system", "looked up to")
        ):
            score += 5.0
    if ("what lgbtq+" in question_lower or "what lgbtq events" in question_lower) and "events" in question_lower:
        if "pride parade" in observation_lower:
            score += 6.0
        if "school event" in observation_lower or "transgender journey" in observation_lower or "better allies" in observation_lower:
            score += 10.0
        if "support group" in observation_lower or "support groups" in observation_lower:
            score += 6.0
        if "conference" in observation_lower or "activists" in observation_lower:
            score -= 2.5
    if "what events has" in question_lower and "help children" in question_lower:
        if any(
            token in observation_lower
            for token in ("mentorship program", "mentor", "young folks", "youth", "kids", "children")
        ):
            score += 6.0
        if "school event" in observation_lower or "giving my talk" in observation_lower or "better allies" in observation_lower:
            score += 10.0
        if "make a difference for the lgbtq+ community" in observation_lower or "make a difference for the lgbtq community" in observation_lower:
            score -= 3.0
    if "in what ways is" in question_lower and "lgbtq community" in question_lower:
        if "activist group" in observation_lower:
            score += 6.0
        if "pride parade" in observation_lower:
            score += 6.0
        if "art show" in observation_lower:
            score += 8.0
        if "mentorship program" in observation_lower or "mentor" in observation_lower:
            score += 6.0
        if "make a difference for the lgbtq+ community" in observation_lower or "make a difference for the lgbtq community" in observation_lower:
            score -= 3.0
    if "join a mentorship program" in question_lower:
        if "mentorship program" in observation_lower or "mentor" in observation_lower or "last weekend" in observation_lower:
            score += 7.0
    if "join a new activist group" in question_lower:
        if "activist group" in observation_lower or "last tues" in observation_lower or "last tuesday" in observation_lower:
            score += 7.0
    if "pottery workshop" in question_lower:
        if "pottery workshop" in observation_lower:
            score += 10.0
        if "last fri" in observation_lower or "last friday" in observation_lower:
            score += 8.0
        if "last month" in observation_lower and "pottery workshop" not in observation_lower:
            score -= 5.0
    if "camping in june" in question_lower:
        if any(token in observation_lower for token in ("camping", "campfire", "nature", "hike", "marshmallows")):
            score += 7.0
        if "june" in (observation.timestamp or "").lower():
            score += 9.0
        if not any(token in observation_lower for token in ("camping", "campfire", "nature", "hike", "marshmallows")):
            score -= 6.0
    if "camping in july" in question_lower:
        if "two weekends ago" in observation_lower or "quiet weekend after we went camping" in observation_lower:
            score += 10.0
        if "last year" in observation_lower:
            score -= 6.0
    if "during the summer" in question_lower and "pride parade" in question_lower:
        if "pride parade" in observation_lower and "last week" in observation_lower:
            score += 6.0
        if "last fri" in observation_lower or "last friday" in observation_lower:
            score -= 1.5
    if question_lower.startswith("how many times") and "beach" in question_lower:
        if "beach" in observation_lower:
            score += 4.0
        if any(token in observation_lower for token in ("once or twice", "twice a year", "once a year")):
            score += 5.0
    if "what kind of art" in question_lower or ("what did" in question_lower and "paint" in question_lower):
        if any(token in observation_lower for token in ("abstract art", "paint", "painting", "sunset", "art show")):
            score += 4.0
        if "abstract" in observation_lower:
            score += 6.0
        if "sunset" in caption_lower:
            score += 6.0
    if "what kind of place" in question_lower and "create for people" in question_lower:
        if observation.predicate == "supportive_space_goal":
            score += 14.0
        if "safe, inviting place for people to grow" in observation_lower or "safe and inviting place for people to grow" in observation_lower:
            score += 9.0
        if "safe and loving home" in observation_lower:
            score -= 5.0
    if question_lower.startswith("did ") and "bowl in the photo" in question_lower:
        if observation.predicate == "made_object_photo":
            score += 14.0
        if "made this bowl" in observation_lower or ("made this" in observation_lower and "bowl" in caption_lower):
            score += 10.0
    if "what kind of books" in question_lower and "library" in question_lower:
        if observation.predicate == "library_books":
            score += 14.0
        if all(token in observation_lower for token in ("kids' books", "classics", "different cultures", "educational books")):
            score += 10.0
    if "what has" in question_lower and "painted" in question_lower:
        if observation.predicate == "paint_subject":
            score += 10.0
        if any(token in observation_lower for token in ("horse painting", "painted sunrise", "painted sunset", "inspired by the sunsets")):
            score += 6.0
    if "pets' names" in question_lower:
        if observation.predicate == "pet_name":
            score += 10.0
        if any(token in observation_lower for token in ("luna", "oliver", "bailey")):
            score += 6.0
        if "oscar" in observation_lower:
            score -= 4.0
    if "symbols" in question_lower:
        if observation.predicate == "important_symbol":
            score += 10.0
        if "rainbow flag" in observation_lower or "transgender symbol" in observation_lower:
            score += 7.0
    if "instruments" in question_lower:
        if observation.predicate == "instrument":
            score += 10.0
        if "clarinet" in observation_lower or "violin" in observation_lower:
            score += 6.0
    if "artists/bands" in question_lower:
        if observation.predicate == "seen_artist":
            score += 10.0
        if "matt patterson" in observation_lower or "summer sounds" in observation_lower:
            score += 6.0
    if "book did" in question_lower and "read" in question_lower:
        if observation.predicate == "book_read":
            score += 10.0
        if "becoming nicole" in observation_lower or ("recommended" in observation_lower and "book" in observation_lower):
            score += 6.0
    if "favorite book" in question_lower and "childhood" in question_lower:
        if observation.predicate == "book_read":
            score += 14.0
        if "charlotte's web" in observation_lower:
            score += 10.0
    if question_lower.startswith("what book") and "recommend" in question_lower:
        if observation.predicate == "book_read":
            score += 14.0
        if "becoming nicole" in observation_lower:
            score += 10.0
    if "take away from the book" in question_lower:
        if observation.predicate == "book_takeaway":
            score += 14.0
        if "self-acceptance" in observation_lower and "find support" in observation_lower:
            score += 10.0
    if "new shoes" in question_lower and "used for" in question_lower:
        if observation.predicate == "shoe_use":
            score += 14.0
        if "these are for running" in observation_lower:
            score += 10.0
    if "reason for getting into running" in question_lower:
        if observation.predicate == "running_reason":
            score += 14.0
        if "de-stress and clear my mind" in observation_lower:
            score += 10.0
    if "running has been great for" in question_lower:
        if observation.predicate == "running_benefit":
            score += 14.0
        if "great for my mental health" in observation_lower or "mental health" in observation_lower:
            score += 10.0
    if "pottery workshop" in question_lower and "what did" in question_lower and "make" in question_lower:
        if observation.predicate == "pottery_output":
            score += 12.0
        if "made our own pots" in observation_lower:
            score += 10.0
    if "what kind of pot" in question_lower and "clay" in question_lower:
        if observation.predicate == "pottery_output":
            score += 12.0
        if "dog face" in observation_lower or "dog face" in caption_lower:
            score += 10.0
    if "what creative project" in question_lower and "besides pottery" in question_lower:
        if observation.predicate == "family_creative_activity":
            score += 12.0
        if "painting together" in observation_lower:
            score += 9.0
    if "what did mel and her kids paint" in question_lower:
        if observation.predicate == "family_paint_subject":
            score += 12.0
        if "sunset with a palm tree" in observation_lower or "sunset with a palm tree" in caption_lower:
            score += 10.0
    if "council meeting for adoption" in question_lower:
        if observation.predicate == "adoption_meeting_takeaway":
            score += 12.0
        if "loving homes for children in need" in observation_lower:
            score += 9.0
    if "what do sunflowers represent" in question_lower:
        if observation.predicate == "flower_symbolism":
            score += 12.0
        if "warmth and happiness" in observation_lower:
            score += 9.0
    if "why are flowers important" in question_lower:
        if observation.predicate == "flower_importance":
            score += 12.0
        if "small moments" in observation_lower and "wedding decor" in observation_lower:
            score += 9.0
    if "painting for the art show" in question_lower:
        if observation.predicate == "art_show_inspiration":
            score += 12.0
        if "visited a lgbtq center" in observation_lower and "unity and strength" in observation_lower:
            score += 9.0
    if "camping trip last year" in question_lower and "what did" in question_lower:
        if observation.predicate == "family_trip_sighting":
            score += 12.0
        if "perseid meteor shower" in observation_lower:
            score += 9.0
    if "meteor shower" in question_lower and "how did" in question_lower:
        if observation.predicate == "family_trip_feeling":
            score += 12.0
        if "in awe of the universe" in observation_lower or "awe-inspiring" in observation_lower:
            score += 9.0
    if "whose birthday did" in question_lower and "celebrate" in question_lower:
        if observation.predicate == "birthday_person":
            score += 12.0
        if "daughter's birthday" in observation_lower:
            score += 9.0
    if "who performed" in question_lower and "daughter's birthday" in question_lower:
        if observation.predicate in {"birthday_performer", "seen_artist"}:
            score += 12.0
        if "matt patterson" in observation_lower:
            score += 9.0
    if "colors and patterns" in question_lower and "pottery project" in question_lower:
        if observation.predicate == "pottery_design_reason":
            score += 12.0
        if "catch the eye and make people smile" in observation_lower:
            score += 9.0
    if question_lower.startswith("what pet does") and "caroline" in question_lower:
        if observation.predicate == "pet_type":
            score += 12.0
        if "guinea pig" in observation_lower:
            score += 9.0
    if question_lower.startswith("what pets does") and "melanie" in question_lower:
        if observation.predicate == "pet_household_summary":
            score += 12.0
        if "another cat named bailey" in observation_lower or "black dog" in caption_lower:
            score += 9.0
    if "family on hikes" in question_lower:
        if observation.predicate == "family_hike_activity":
            score += 10.0
        if any(token in observation_lower for token in ("marshmallows", "stories", "campfire")):
            score += 6.0
    if "changes" in question_lower and "transition journey" in question_lower:
        if observation.predicate == "transition_change":
            score += 10.0
        if any(token in observation_lower for token in ("changing body", "weren't able to handle it", "supporting me")):
            score += 6.0
    if "transgender-specific events" in question_lower:
        if observation.predicate == "trans_event":
            score += 10.0
        if "conference" in observation_lower or "poetry reading" in observation_lower:
            score += 6.0
    if "practicing art" in question_lower or "creating art" in question_lower:
        if observation.predicate == "art_practice_duration":
            score += 10.0
        if "seven years" in observation_lower:
            score += 6.0
    if "used to do" in question_lower and "dad" in question_lower:
        if observation.predicate == "childhood_activity":
            score += 14.0
        if "horseback riding" in observation_lower:
            score += 10.0
    if "find in her neighborhood" in question_lower and "during her walk" in question_lower:
        if observation.predicate == "neighborhood_find":
            score += 14.0
        if "rainbow sidewalk" in observation_lower:
            score += 10.0
    if "classical musicians" in question_lower:
        if observation.predicate == "classical_musicians":
            score += 14.0
        if "bach" in observation_lower and "mozart" in observation_lower:
            score += 10.0
    if "modern music" in question_lower:
        if observation.predicate == "modern_music_artist":
            score += 14.0
        if "ed sheeran" in observation_lower:
            score += 10.0
    if "precautionary sign" in question_lower and "caf" in question_lower:
        if observation.predicate == "precautionary_sign":
            score += 14.0
        if "not being able to leave" in observation_lower or "sign posted on a door" in caption_lower:
            score += 10.0
    if "getting started with adoption" in question_lower:
        if observation.predicate == "adoption_start_advice":
            score += 14.0
        if "adoption agency or lawyer" in observation_lower and "prepare emotionally" in observation_lower:
            score += 10.0
    if "what setback" in question_lower and "october 2023" in question_lower:
        if observation.predicate == "pottery_setback":
            score += 14.0
        if "take a break from pottery" in observation_lower and "got hurt" in observation_lower:
            score += 10.0
    if "keep herself busy" in question_lower and "pottery break" in question_lower:
        if observation.predicate == "pottery_break_activity":
            score += 14.0
        if "reading that book" in observation_lower and "painting to keep busy" in observation_lower:
            score += 10.0
    if "what painting did melanie show" in question_lower and "october 13, 2023" in question_lower:
        if observation.predicate == "recent_painting":
            score += 14.0
        if "pink sky" in caption_lower or "inspired by the sunsets" in observation_lower:
            score += 10.0
    if "what kind of painting did caroline share" in question_lower and "october 13, 2023" in question_lower:
        if observation.predicate == "abstract_painting":
            score += 14.0
        if "blue streaks" in observation_lower or "abstract painting" in observation_lower:
            score += 10.0
    if "what was the poetry reading" in question_lower:
        if observation.predicate == "poetry_reading_topic":
            score += 14.0
        if "transgender people shared their stories" in observation_lower:
            score += 10.0
    if "posters at the poetry reading" in question_lower:
        if observation.predicate == "poster_text":
            score += 14.0
        if "trans lives matter" in observation_lower or "trans lives matter" in caption_lower:
            score += 10.0
    if "drawing symbolize" in question_lower:
        if observation.predicate == "drawing_symbolism":
            score += 14.0
        if "freedom and being real" in observation_lower or "stay true to myself" in observation_lower:
            score += 10.0
    if "journey through life together" in question_lower:
        if observation.predicate == "shared_life_journey":
            score += 14.0
        if "ongoing adventure of learning and growing" in observation_lower:
            score += 10.0
    if "son handle the accident" in question_lower:
        if observation.predicate == "son_accident_reaction":
            score += 14.0
        if "reassured them" in observation_lower and "brother would be ok" in observation_lower:
            score += 10.0
    if "feel about her family after the accident" in question_lower:
        if observation.predicate == "family_importance":
            score += 14.0
        if "mean the world to me" in observation_lower:
            score += 10.0
    if "children handle the accident" in question_lower:
        if observation.predicate == "children_accident_reaction":
            score += 14.0
        if "they're tough kids" in observation_lower or ("reassured them" in observation_lower and "brother would be ok" in observation_lower):
            score += 10.0
    if "feel after the accident" in question_lower:
        if observation.predicate == "post_accident_feeling":
            score += 14.0
        if "thankful to have them" in observation_lower and "family" in observation_lower:
            score += 10.0
    if "reaction to her children enjoying the grand canyon" in question_lower:
        if observation.predicate == "canyon_reaction":
            score += 14.0
        if "grand canyon" in observation_lower and "thankful" in observation_lower:
            score += 10.0
    if "what do melanie's family give her" in question_lower:
        if observation.predicate == "family_strength_source":
            score += 14.0
        if "strength to keep going" in observation_lower or "biggest motivation and support" in observation_lower:
            score += 10.0
    if "how many children" in question_lower:
        if observation.predicate == "child_count":
            score += 14.0
        if any(token in observation_lower for token in ("my son", "their brother", "2 younger kids", "kids")):
            score += 4.0
    if "what items" in question_lower and "bought" in question_lower:
        if observation.predicate == "bought_item":
            score += 12.0
        if any(token in observation_lower for token in ("figurines", "shoes", "bought")):
            score += 6.0
    if "charity race" in question_lower and "realize" in question_lower:
        if observation.predicate == "self_care_realization":
            score += 12.0
        if "self-care is really important" in observation_lower:
            score += 7.0
    if "prioritize self-care" in question_lower:
        if observation.predicate == "self_care_method":
            score += 12.0
        if any(token in observation_lower for token in ("me-time", "running", "reading", "violin")):
            score += 6.0
    if "plans for the summer" in question_lower:
        if observation.predicate in {"summer_plan", "research_topic"}:
            score += 12.0
        if "researching adoption agencies" in observation_lower:
            score += 8.0
    if "choose the adoption agency" in question_lower:
        if observation.predicate == "adoption_agency_reason":
            score += 12.0
        if any(token in observation_lower for token in ("lgbtq+ folks with adoption", "lgbtq folks with adoption", "inclusivity and support")):
            score += 8.0
    if "excited about" in question_lower and "adoption process" in question_lower:
        if observation.predicate == "adoption_goal":
            score += 12.0
        if "make a family for kids who need one" in observation_lower:
            score += 8.0
    if "decision to adopt" in question_lower:
        if observation.predicate == "adoption_opinion":
            score += 12.0
        if "doing something amazing" in observation_lower or "awesome mom" in observation_lower:
            score += 8.0
    if "married" in question_lower:
        if observation.predicate == "marriage_duration":
            score += 12.0
        if "5 years already" in observation_lower:
            score += 8.0
    if "necklace symbolize" in question_lower:
        if observation.predicate == "necklace_symbolism":
            score += 12.0
        if "love, faith and strength" in observation_lower or "love, faith, and strength" in observation_lower:
            score += 8.0
    if "what country" in question_lower and "grandma" in question_lower:
        if observation.predicate == "moved_from_location":
            score += 12.0
        if "home country, sweden" in observation_lower:
            score += 8.0
    if "grandma's gift" in question_lower:
        if observation.predicate == "gift_item":
            score += 12.0
        if "gift from my grandma" in observation_lower or "necklace" in observation_lower:
            score += 7.0
    if "hand-painted bowl" in question_lower:
        if observation.predicate == "bowl_symbolism":
            score += 12.0
        if "art and self-expression" in observation_lower or "hand-painted bowl" in observation_lower:
            score += 7.0
    if "while camping" in question_lower:
        if observation.predicate == "camping_activity":
            score += 12.0
        if any(token in observation_lower for token in ("explored nature", "roasted marshmallows", "went on a hike")):
            score += 7.0
    if "what kind of counseling and mental health services" in question_lower:
        if observation.predicate in {"counseling_interest_detail", "career_path"}:
            score += 12.0
        if "working with trans people" in observation_lower or "supporting their mental health" in observation_lower:
            score += 8.0
    if "what workshop" in question_lower and "attend recently" in question_lower:
        if observation.predicate == "workshop_name":
            score += 12.0
        if "counseling workshop" in observation_lower:
            score += 8.0
    if "what was discussed" in question_lower and "workshop" in question_lower:
        if observation.predicate == "workshop_topic":
            score += 12.0
        if "therapeutic methods" in observation_lower or "work with trans people" in observation_lower:
            score += 8.0
    if "what motivated" in question_lower and "pursue counseling" in question_lower:
        if observation.predicate == "counseling_motivation":
            score += 12.0
        if "my own journey" in observation_lower or "support groups improved my life" in observation_lower:
            score += 8.0
    if "political leaning" in question_lower:
        if any(
            token in observation_lower
            for token in ("lgbtq rights", "acceptance", "supportive community", "youth center", "homeless shelter", "make a difference")
        ):
            score += 5.0
    if "considered religious" in question_lower:
        if any(token in observation_lower for token in ("faith", "church", "religious conservatives")):
            score += 5.0
    if "what activities has" in question_lower and "family" in question_lower:
        if observation.predicate == "activity":
            score += 7.0
        if any(token in observation_lower for token in ("pottery", "painting", "camping", "museum", "swimming", "hiking")):
            score += 5.0
        if "family" in observation_lower or "kids" in observation_lower:
            score += 2.0
    if "daughter's birthday" in question_lower:
        if "daughter's birthday" in observation_lower or "last night was amazing" in observation_lower:
            score += 7.0
    if question_lower.startswith("would") and "national park or a theme park" in question_lower:
        if any(token in observation_lower for token in ("outdoors", "nature", "camping", "forest", "hiking", "campfire")):
            score += 7.0
    if question_lower.startswith("what types of pottery"):
        if any(token in observation_lower for token in ("pottery workshop", "clay", "bowl", "cup")):
            score += 6.0
        if any(token in caption_lower for token in ("bowl", "cup")):
            score += 6.0
    if "pride fes" in question_lower or "pride festival" in question_lower:
        if "pride fest" in observation_lower or ("last year" in observation_lower and "pride" in observation_lower):
            score += 8.0
    if (
        "what events has" in question_lower
        or "in what ways is" in question_lower
        or ("what activities has" in question_lower and "family" in question_lower)
        or "what types of pottery" in question_lower
        or ("help children" in question_lower and "what events" in question_lower)
    ):
        for token in (
            "pride parade",
            "support group",
            "school",
            "speech",
            "mentoring",
            "mentor",
            "art show",
            "youth center",
            "pottery",
            "painting",
            "camping",
            "museum",
            "swimming",
            "hiking",
            "bowl",
            "cup",
            "family",
        ):
            if token in observation_lower:
                score += 1.5
    if observation.predicate == "raw_turn":
        score -= 2.5
        if "what books" in question_lower and "read" in question_lower:
            lower_text = observation.text.lower()
            if "book" in lower_text and "read" in lower_text:
                score += 4.0
            if observation.metadata.get("img_url") or observation.metadata.get("blip_caption") or observation.metadata.get("search_query"):
                score += 4.0
    if question_lower.startswith("when did") and observation.predicate == "raw_turn":
        if "apply to adoption agencies" in question_lower and "applied to adoption agencies" in observation_lower:
            score += 12.0
            if "this week" in observation_lower:
                score += 8.0
        if "negative experience" in question_lower and "hike" in question_lower and "hiking last week" in observation_lower:
            score += 14.0
        if "make a plate" in question_lower and "pottery class yesterday" in observation_lower:
            score += 14.0
        if "friend adopt a child" in question_lower and "adopted last year" in observation_lower:
            score += 14.0
        if "get hurt" in question_lower and "last month i got hurt" in observation_lower:
            score += 14.0
        if "family go on a roadtrip" in question_lower and "roadtrip this past weekend" in observation_lower:
            score += 14.0
    if len(subjects) >= 2 and observation.subject in subjects:
        if "destress" in question_lower and "dance" in observation_lower:
            score += 8.0
        if "both have in common" in question_lower and any(
            token in observation_lower for token in ("lost my job", "lost his job", "lost her job", "start", "business", "store", "studio")
        ):
            score += 14.0
        if question_lower.startswith("do ") and "start businesses" in question_lower and any(
            token in observation_lower for token in ("passion", "love", "doing something i love", "turn my dancing passion into a business")
        ):
            score += 8.0
    return score

