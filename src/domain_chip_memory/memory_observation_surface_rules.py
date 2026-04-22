from __future__ import annotations

from .memory_extraction import _subject_to_surface


def observation_surface_text(subject: str, predicate: str, value: str, source_text: str) -> str:
    surface_subject = _subject_to_surface(subject)
    if predicate in {"loss_event", "gift_event", "support_event"}:
        return value
    if predicate == "location":
        return f"{surface_subject} live in {value}" if subject == "user" else f"{surface_subject} lives in {value}"
    if predicate == "preference":
        return f"{surface_subject} prefer {value}" if subject == "user" else f"{surface_subject} prefers {value}"
    if predicate == "favorite_color":
        return f"My favourite colour is {value}" if subject == "user" else f"{surface_subject}'s favourite colour is {value}"
    if predicate == "commute_duration":
        return f"My daily commute takes {value}" if subject == "user" else f"{surface_subject}'s daily commute takes {value}"
    if predicate == "attended_play":
        return f"I attended {value}" if subject == "user" else f"{surface_subject} attended {value}"
    if predicate == "playlist_name":
        return f"My playlist is {value}" if subject == "user" else f"{surface_subject}'s playlist is {value}"
    if predicate == "retailer":
        return f"I shop at {value}" if subject == "user" else f"{surface_subject} shops at {value}"
    if predicate == "previous_occupation":
        return f"My previous occupation was {value}" if subject == "user" else f"{surface_subject}'s previous occupation was {value}"
    if predicate == "bike_count":
        return f"I own {value} bikes" if subject == "user" else f"{surface_subject} owns {value} bikes"
    if predicate == "dog_breed":
        return f"My dog is a {value}" if subject == "user" else f"{surface_subject}'s dog is a {value}"
    if predicate == "computer_science_degree_institution":
        return (
            f"I completed my Bachelor's degree in Computer Science from {value}"
            if subject == "user"
            else f"{surface_subject} completed a Bachelor's degree in Computer Science from {value}"
        )
    if predicate == "music_service":
        return (
            f"The music streaming service I've been using lately is {value}"
            if subject == "user"
            else f"{surface_subject}'s music streaming service lately is {value}"
        )
    if predicate == "education_fields":
        return (
            f"I'm likely to pursue {value}"
            if subject == "user"
            else f"{surface_subject} is likely to pursue {value}"
        )
    if predicate == "research_topic":
        return (
            f"I researched {value}"
            if subject == "user"
            else f"{surface_subject} researched {value}"
        )
    if predicate == "relationship_status":
        return (
            f"My relationship status is {value}"
            if subject == "user"
            else f"{surface_subject}'s relationship status is {value}"
        )
    if predicate == "school_event_time":
        return (
            f"I had a school event {value}"
            if subject == "user"
            else f"{surface_subject} had a school event {value}"
        )
    if predicate == "support_network_meetup_time":
        return (
            f"I met up with friends, family, and mentors {value}"
            if subject == "user"
            else f"{surface_subject} met up with friends, family, and mentors {value}"
        )
    if predicate == "charity_race_time":
        return (
            f"I ran a charity race {value}"
            if subject == "user"
            else f"{surface_subject} ran a charity race {value}"
        )
    if predicate == "current_friend_group_duration":
        return (
            f"I've had my current group of friends for {value}"
            if subject == "user"
            else f"{surface_subject} has had the current group of friends for {value}"
        )
    if predicate == "moved_from_location":
        return (
            f"I moved from {value}"
            if subject == "user"
            else f"{surface_subject} moved from {value}"
        )
    if predicate == "career_path":
        return (
            f"My career path is {value}"
            if subject == "user"
            else f"{surface_subject}'s career path is {value}"
        )
    if predicate == "museum_visit_time":
        return (
            f"I went to the museum {value}"
            if subject == "user"
            else f"{surface_subject} went to the museum {value}"
        )
    if predicate == "identity":
        return (
            f"My identity is {value}"
            if subject == "user"
            else f"{surface_subject}'s identity is {value}"
        )
    if predicate == "sunrise_paint_time":
        return (
            f"I painted a sunrise {value}"
            if subject == "user"
            else f"{surface_subject} painted a sunrise {value}"
        )
    if predicate == "camping_plan_time":
        return (
            f"I'm planning on going camping {value}"
            if subject == "user"
            else f"{surface_subject} is planning on going camping {value}"
        )
    if predicate == "pottery_class_signup_time":
        return (
            f"I signed up for a pottery class {value}"
            if subject == "user"
            else f"{surface_subject} signed up for a pottery class {value}"
        )
    if predicate == "activity":
        return (
            f"I partake in {value}"
            if subject == "user"
            else f"{surface_subject} partakes in {value}"
        )
    if predicate == "camp_location":
        return (
            f"I camped at the {value}"
            if subject == "user"
            else f"{surface_subject} camped at the {value}"
        )
    if predicate == "kids_interest":
        return (
            f"My kids like {value}"
            if subject == "user"
            else f"{surface_subject}'s kids like {value}"
        )
    if predicate == "bookshelf_collection":
        return (
            f"I collect {value}"
            if subject == "user"
            else f"{surface_subject} collects {value}"
        )
    if predicate == "supportive_space_goal":
        return (
            f"I want to create {value}"
            if subject == "user"
            else f"{surface_subject} wants to create {value}"
        )
    if predicate == "made_object_photo":
        return (
            f"I made the {value} in the photo"
            if subject == "user"
            else f"{surface_subject} made the {value} in the photo"
        )
    if predicate == "library_books":
        return (
            f"I have {value} in my library"
            if subject == "user"
            else f"{surface_subject} has {value} in the library"
        )
    if predicate == "destress_activity":
        return (
            f"I de-stress by {value}"
            if subject == "user"
            else f"{surface_subject} de-stresses by {value}"
        )
    if predicate == "book_read":
        return (
            f'I read "{value}"'
            if subject == "user"
            else f'{surface_subject} read "{value}"'
        )
    if predicate == "book_takeaway":
        return (
            f"I took away {value} from the book"
            if subject == "user"
            else f"{surface_subject} took away {value} from the book"
        )
    if predicate == "shoe_use":
        return (
            f"My new shoes are for {value}"
            if subject == "user"
            else f"{surface_subject}'s new shoes are for {value}"
        )
    if predicate == "running_reason":
        return (
            f"I got into running {value}"
            if subject == "user"
            else f"{surface_subject} got into running {value}"
        )
    if predicate == "running_benefit":
        return (
            f"Running has been great for {value}"
            if subject == "user"
            else f"Running has been great for {surface_subject}'s {value}"
        )
    if predicate == "pottery_output":
        return (
            f"I made {value} at the pottery workshop"
            if subject == "user"
            else f"{surface_subject} made {value} at the pottery workshop"
        )
    if predicate == "family_creative_activity":
        return (
            f"My family does {value} together"
            if subject == "user"
            else f"{surface_subject}'s family does {value} together"
        )
    if predicate == "family_paint_subject":
        return (
            f"My family painted {value}"
            if subject == "user"
            else f"{surface_subject}'s family painted {value}"
        )
    if predicate == "paint_subject":
        return f"I painted {value}" if subject == "user" else f"{surface_subject} painted {value}"
    if predicate == "adoption_meeting_takeaway":
        return (
            f"I saw {value} at the adoption council meeting"
            if subject == "user"
            else f"{surface_subject} saw {value} at the adoption council meeting"
        )
    if predicate == "flower_symbolism":
        return (
            f"Sunflowers represent {value} to me"
            if subject == "user"
            else f"Sunflowers represent {value} according to {surface_subject}"
        )
    if predicate == "flower_importance":
        return (
            f"Flowers are important to me because {value}"
            if subject == "user"
            else f"Flowers are important to {surface_subject} because {value}"
        )
    if predicate == "art_show_inspiration":
        return (
            f"My art-show painting was inspired by {value}"
            if subject == "user"
            else f"{surface_subject}'s art-show painting was inspired by {value}"
        )
    if predicate == "family_trip_sighting":
        return (
            f"I saw the {value} while camping"
            if subject == "user"
            else f"{surface_subject} saw the {value} while camping"
        )
    if predicate == "family_trip_feeling":
        return (
            f"I felt {value} while watching the meteor shower"
            if subject == "user"
            else f"{surface_subject} felt {value} while watching the meteor shower"
        )
    if predicate == "birthday_person":
        return (
            f"I celebrated {value}'s birthday"
            if subject == "user"
            else f"{surface_subject} celebrated {value}'s birthday"
        )
    if predicate == "birthday_performer":
        return (
            f"{value} performed at my daughter's birthday"
            if subject == "user"
            else f"{value} performed at {surface_subject}'s daughter's birthday"
        )
    if predicate == "pottery_design_reason":
        return (
            f"I used colors and patterns because {value}"
            if subject == "user"
            else f"{surface_subject} used colors and patterns because {value}"
        )
    if predicate == "pet_name":
        return f"I have a pet named {value}" if subject == "user" else f"{surface_subject} has a pet named {value}"
    if predicate == "pet_type":
        return f"I have a {value}" if subject == "user" else f"{surface_subject} has a {value}"
    if predicate == "pet_household_summary":
        return f"I have {value}" if subject == "user" else f"{surface_subject} has {value}"
    if predicate == "important_symbol":
        return (
            f"An important symbol to me is {value}"
            if subject == "user"
            else f"An important symbol to {surface_subject} is {value}"
        )
    if predicate == "instrument":
        return f"I play {value}" if subject == "user" else f"{surface_subject} plays {value}"
    if predicate == "seen_artist":
        return f"I saw {value}" if subject == "user" else f"{surface_subject} saw {value}"
    if predicate == "family_hike_activity":
        return f"On family hikes I {value}" if subject == "user" else f"On family hikes {surface_subject} {value}"
    if predicate == "transition_change":
        return (
            f"During my transition I faced {value}"
            if subject == "user"
            else f"During the transition {surface_subject} faced {value}"
        )
    if predicate == "trans_event":
        return (
            f"I attended a transgender-specific event: {value}"
            if subject == "user"
            else f"{surface_subject} attended a transgender-specific event: {value}"
        )
    if predicate == "art_practice_duration":
        return (
            f"I've been practicing art for {value}"
            if subject == "user"
            else f"{surface_subject} has been practicing art for {value}"
        )
    if predicate == "childhood_activity":
        return (
            f"I used to do {value} with my dad"
            if subject == "user"
            else f"{surface_subject} used to do {value} with {surface_subject}'s dad"
        )
    if predicate == "neighborhood_find":
        return (
            f"I found {value} in my neighborhood"
            if subject == "user"
            else f"{surface_subject} found {value} in the neighborhood"
        )
    if predicate == "classical_musicians":
        return (
            f"I enjoy listening to {value}"
            if subject == "user"
            else f"{surface_subject} enjoys listening to {value}"
        )
    if predicate == "modern_music_artist":
        return (
            f"I'm a fan of {value}"
            if subject == "user"
            else f"{surface_subject} is a fan of {value}"
        )
    if predicate == "precautionary_sign":
        return (
            f"I saw {value} at the cafe"
            if subject == "user"
            else f"{surface_subject} saw {value} at the cafe"
        )
    if predicate == "adoption_start_advice":
        return (
            f"My adoption advice is {value}"
            if subject == "user"
            else f"{surface_subject}'s adoption advice is {value}"
        )
    if predicate == "pottery_setback":
        return (
            f"My setback was {value}"
            if subject == "user"
            else f"{surface_subject}'s setback was {value}"
        )
    if predicate == "pottery_break_activity":
        return (
            f"During my pottery break I {value}"
            if subject == "user"
            else f"During the pottery break {surface_subject} did {value}"
        )
    if predicate == "recent_painting":
        return f"I showed {value}" if subject == "user" else f"{surface_subject} showed {value}"
    if predicate == "abstract_painting":
        return f"I shared {value}" if subject == "user" else f"{surface_subject} shared {value}"
    if predicate == "poetry_reading_topic":
        return (
            f"My poetry reading was {value}"
            if subject == "user"
            else f"{surface_subject}'s poetry reading was {value}"
        )
    if predicate == "poster_text":
        return f"My poster said {value}" if subject == "user" else f"{surface_subject}'s poster said {value}"
    if predicate == "drawing_symbolism":
        return (
            f"My drawing symbolizes {value}"
            if subject == "user"
            else f"{surface_subject}'s drawing symbolizes {value}"
        )
    if predicate == "shared_life_journey":
        return (
            f"Our journey through life together is {value}"
            if subject == "user"
            else f"{surface_subject}'s journey through life is {value}"
        )
    if predicate == "son_accident_reaction":
        return (
            f"My son handled the accident by being {value}"
            if subject == "user"
            else f"{surface_subject}'s son handled the accident by being {value}"
        )
    if predicate == "family_importance":
        return f"My family are {value}" if subject == "user" else f"{surface_subject}'s family are {value}"
    if predicate == "children_accident_reaction":
        return f"My children were {value}" if subject == "user" else f"{surface_subject}'s children were {value}"
    if predicate == "post_accident_feeling":
        return (
            f"After the accident I felt {value}"
            if subject == "user"
            else f"After the accident {surface_subject} felt {value}"
        )
    if predicate == "canyon_reaction":
        return (
            f"When my children enjoyed the Grand Canyon I felt {value}"
            if subject == "user"
            else f"When the children enjoyed the Grand Canyon {surface_subject} felt {value}"
        )
    if predicate == "family_strength_source":
        return (
            f"My family give me {value}"
            if subject == "user"
            else f"{surface_subject}'s family give {surface_subject} {value}"
        )
    if predicate == "child_count":
        return f"I have {value} children" if subject == "user" else f"{surface_subject} has {value} children"
    if predicate == "bought_item":
        return f"I bought {value}" if subject == "user" else f"{surface_subject} bought {value}"
    if predicate == "self_care_realization":
        return f"I realized {value}" if subject == "user" else f"{surface_subject} realized {value}"
    if predicate == "self_care_method":
        return (
            f"I prioritize self-care by {value}"
            if subject == "user"
            else f"{surface_subject} prioritizes self-care by {value}"
        )
    if predicate == "summer_plan":
        return (
            f"My plan for the summer is {value}"
            if subject == "user"
            else f"{surface_subject}'s plan for the summer is {value}"
        )
    if predicate == "adoption_agency_reason":
        return (
            f"I chose the adoption agency because {value}"
            if subject == "user"
            else f"{surface_subject} chose the adoption agency because {value}"
        )
    if predicate == "adoption_goal":
        return (
            f"I'm excited about {value} in the adoption process"
            if subject == "user"
            else f"{surface_subject} is excited about {value} in the adoption process"
        )
    if predicate == "adoption_opinion":
        return (
            f"I think the adoption decision is {value}"
            if subject == "user"
            else f"{surface_subject} thinks the adoption decision is {value}"
        )
    if predicate == "marriage_duration":
        return (
            f"I have been married for {value}"
            if subject == "user"
            else f"{surface_subject} has been married for {value}"
        )
    if predicate == "necklace_symbolism":
        return (
            f"My necklace symbolizes {value}"
            if subject == "user"
            else f"{surface_subject}'s necklace symbolizes {value}"
        )
    if predicate == "gift_item":
        return (
            f"My grandma gave me a {value}"
            if subject == "user"
            else f"{surface_subject}'s grandma gave {surface_subject} a {value}"
        )
    if predicate == "bowl_symbolism":
        return (
            f"My hand-painted bowl reminds me of {value}"
            if subject == "user"
            else f"{surface_subject}'s hand-painted bowl reminds {surface_subject} of {value}"
        )
    if predicate == "camping_activity":
        return (
            f"While camping I {value}"
            if subject == "user"
            else f"While camping {surface_subject} {value}"
        )
    if predicate == "counseling_interest_detail":
        return (
            f"I'm interested in {value}"
            if subject == "user"
            else f"{surface_subject} is interested in {value}"
        )
    if predicate == "workshop_name":
        return f"I attended {value}" if subject == "user" else f"{surface_subject} attended {value}"
    if predicate == "workshop_topic":
        return (
            f"The workshop discussed {value}"
            if subject == "user"
            else f"{surface_subject}'s workshop discussed {value}"
        )
    if predicate == "counseling_motivation":
        return f"I was motivated by {value}" if subject == "user" else f"{surface_subject} was motivated by {value}"
    if predicate == "trip_duration":
        return source_text
    return source_text
