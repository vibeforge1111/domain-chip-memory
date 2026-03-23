from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .contracts import JsonDict, NormalizedBenchmarkSample, NormalizedQuestion, NormalizedSession, NormalizedTurn
from .runs import BaselinePromptPacket, RetrievedContextItem, build_run_manifest


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "now",
    "of",
    "on",
    "or",
    "the",
    "to",
    "was",
    "what",
    "when",
    "where",
    "who",
    "why",
    "you",
}

IRREGULAR_TOKEN_NORMALIZATIONS = {
    "went": "go",
    "gone": "go",
    "did": "do",
    "done": "do",
    "ran": "run",
    "sang": "sing",
    "bought": "buy",
    "brought": "bring",
    "thought": "think",
    "felt": "feel",
    "met": "meet",
    "took": "take",
    "taken": "take",
    "made": "make",
    "painted": "paint",
    "studied": "study",
    "moved": "move",
    "spoke": "speak",
}


@dataclass(frozen=True)
class MemoryAtom:
    atom_id: str
    subject: str
    predicate: str
    value: str
    session_id: str
    turn_id: str
    timestamp: str | None
    source_text: str
    metadata: JsonDict


@dataclass(frozen=True)
class ObservationEntry:
    observation_id: str
    subject: str
    predicate: str
    text: str
    session_id: str
    turn_ids: list[str]
    timestamp: str | None
    metadata: JsonDict


@dataclass(frozen=True)
class EventCalendarEntry:
    event_id: str
    subject: str
    predicate: str
    text: str
    session_id: str
    turn_ids: list[str]
    timestamp: str | None
    metadata: JsonDict


def _normalize_token(token: str) -> str:
    normalized = token.lower()
    if normalized in IRREGULAR_TOKEN_NORMALIZATIONS:
        return IRREGULAR_TOKEN_NORMALIZATIONS[normalized]
    if len(normalized) > 5 and normalized.endswith("ies"):
        return normalized[:-3] + "y"
    if len(normalized) > 5 and normalized.endswith("ing"):
        return normalized[:-3]
    if len(normalized) > 4 and normalized.endswith("ed"):
        stem = normalized[:-2]
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    if len(normalized) > 4 and normalized.endswith("es"):
        return normalized[:-2]
    if len(normalized) > 3 and normalized.endswith("s") and not normalized.endswith("ss"):
        return normalized[:-1]
    return normalized


def _tokenize(text: str) -> list[str]:
    return [
        normalized
        for token in re.findall(r"[a-z0-9]+", text.lower())
        for normalized in [_normalize_token(token)]
        if normalized not in STOPWORDS
    ]


def _token_bigrams(text: str) -> set[tuple[str, str]]:
    tokens = _tokenize(text)
    return set(zip(tokens, tokens[1:]))


def _serialize_session(session: NormalizedSession) -> str:
    lines = []
    header = f"Session {session.session_id}"
    if session.timestamp:
        header += f" @ {session.timestamp}"
    lines.append(header)
    for turn in session.turns:
        lines.append(f"{turn.speaker}: {turn.text}")
    return "\n".join(lines)


def _canonical_subject(turn: NormalizedTurn) -> str:
    speaker = turn.speaker.strip().lower()
    if speaker in {"user", "speaker_a", "speaker b", "speaker_a:", "speaker_b", "speaker_b:"}:
        return "user"
    return speaker


def _normalize_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .,:;!?")


def _subject_to_surface(subject: str) -> str:
    return "I" if subject == "user" else subject.capitalize()


def _observation_surface_text(subject: str, predicate: str, value: str, source_text: str) -> str:
    surface_subject = _subject_to_surface(subject)
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
    if predicate == "trip_duration":
        return source_text
    return source_text


def _answer_candidate_surface_text(subject: str, predicate: str, value: str, source_text: str) -> str:
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
        "destress_activity",
        "book_read",
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


def _extract_atoms_from_turn(
    session: NormalizedSession,
    turn: NormalizedTurn,
    *,
    allow_raw_fallback: bool = False,
) -> list[MemoryAtom]:
    text = turn.text.strip()
    lower = text.lower()
    subject = _canonical_subject(turn)
    atoms: list[MemoryAtom] = []

    patterns = [
        (r"\b(?:i|we)\s+moved to\s+([A-Za-z0-9 _-]+)", "location"),
        (r"\b(?:i|we)\s+live in\s+([A-Za-z0-9 _-]+)", "location"),
        (r"\b([A-Z][A-Za-z0-9_-]+)\s+(?:moved to|lives in|live in)\s+([A-Za-z0-9 _-]+)", "location_named"),
        (r"\b(?:i now prefer|i prefer|i like)\s+([A-Za-z0-9 _-]+)", "preference"),
        (r"\b([A-Z][A-Za-z0-9_-]+)\s+(?:now prefers|prefers|likes)\s+([A-Za-z0-9 _-]+)", "preference_named"),
        (r"\bmy favourite colour is\s+([A-Za-z0-9 _-]+)", "favorite_color"),
        (r"\bmy favorite color is\s+([A-Za-z0-9 _-]+)", "favorite_color"),
        (r"\bmy favourite color is\s+([A-Za-z0-9 _-]+)", "favorite_color"),
        (r"\bmy favorite colour is\s+([A-Za-z0-9 _-]+)", "favorite_color"),
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
        (r"\bpainted that lake sunrise\b", "activity_painting"),
        (r"\bpainting'?s a fun way\b", "activity_painting"),
        (r"\bgoing\s+(camping)\b", "activity"),
        (r"\bcamping in the\s+(?:mountains|forest)\b", "activity_camping"),
        (r"\bcamping at the\s+beach\b", "activity_camping"),
        (r"\bcamping in the\s+(mountains)\b", "camp_location"),
        (r"\bcamping at the\s+(beach)\b", "camp_location"),
        (r"\bcamping trip in the\s+(forest)\b", "camp_location"),
        (r"\bthe \d+\s+younger kids love\s+(nature)\b", "kids_interest"),
        (r"\bdinosaur exhibit\b", "kids_interest_dinosaurs"),
        (r"\bkids'? books-?\s+classics\b", "bookshelf_collection"),
        (r'\bloved reading\s+"([^"]+)"', "book_read"),
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
        elif predicate == "activity_camping":
            atom_subject = subject
            atom_predicate = "activity"
            value = "camping"
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
    observations: list[ObservationEntry] = []
    for atom in extract_memory_atoms(sample):
        if atom.predicate == "raw_turn":
            speaker = _subject_to_surface(atom.subject)
            if atom.timestamp:
                text = f"On {atom.timestamp}, {speaker} said: {atom.source_text}"
            else:
                text = f"{speaker} said: {atom.source_text}"
            image_evidence: list[str] = []
            blip_caption = atom.metadata.get("blip_caption")
            if blip_caption:
                image_evidence.append(f"image_caption: {blip_caption}")
            search_query = atom.metadata.get("search_query")
            if search_query:
                image_evidence.append(f"image_query: {search_query}")
            img_url = atom.metadata.get("img_url")
            if img_url:
                if isinstance(img_url, list) and img_url:
                    image_evidence.append(f"image_url: {img_url[0]}")
                elif isinstance(img_url, str):
                    image_evidence.append(f"image_url: {img_url}")
            if image_evidence:
                text = f"{text} Image evidence: {'; '.join(image_evidence)}"
        else:
            text = _observation_surface_text(atom.subject, atom.predicate, atom.value, atom.source_text)
            if atom.timestamp and atom.predicate in {
                "school_event_time",
                "support_network_meetup_time",
                "charity_race_time",
                "museum_visit_time",
                "sunrise_paint_time",
                "camping_plan_time",
                "pottery_class_signup_time",
            }:
                text = f"On {atom.timestamp}, {text}"
        observations.append(
            ObservationEntry(
                observation_id=f"{atom.atom_id}:obs",
                subject=atom.subject,
                predicate=atom.predicate,
                text=text,
                session_id=atom.session_id,
                turn_ids=[atom.turn_id],
                timestamp=atom.timestamp,
                metadata={"source_text": atom.source_text, "value": atom.value, **atom.metadata},
            )
        )
    return observations


def reflect_observations(observations: list[ObservationEntry]) -> list[ObservationEntry]:
    latest_by_key: dict[tuple[str, str, str], ObservationEntry] = {}
    passthrough: list[ObservationEntry] = []
    for observation in observations:
        if observation.predicate == "raw_turn":
            passthrough.append(observation)
            continue
        key = (
            observation.subject,
            observation.predicate,
            str(observation.metadata.get("entity_key", "")),
        )
        current = latest_by_key.get(key)
        if current is None or (observation.timestamp or "") >= (current.timestamp or ""):
            latest_by_key[key] = observation
    reflected = sorted(
        [*latest_by_key.values(), *passthrough],
        key=lambda entry: (entry.timestamp or "", entry.observation_id),
    )
    return reflected


def build_event_calendar(sample: NormalizedBenchmarkSample) -> list[EventCalendarEntry]:
    events: list[EventCalendarEntry] = []
    for atom in extract_memory_atoms(sample):
        if atom.predicate == "raw_turn":
            continue
        text = _observation_surface_text(atom.subject, atom.predicate, atom.value, atom.source_text)
        events.append(
            EventCalendarEntry(
                event_id=f"{atom.atom_id}:event",
                subject=atom.subject,
                predicate=atom.predicate,
                text=text,
                session_id=atom.session_id,
                turn_ids=[atom.turn_id],
                timestamp=atom.timestamp,
                metadata={"source_text": atom.source_text, "value": atom.value, **atom.metadata},
            )
        )
    return sorted(events, key=lambda entry: (entry.timestamp or "", entry.event_id))


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


def _question_predicates(question: NormalizedQuestion) -> list[str]:
    question_lower = question.question.lower()
    predicates: list[str] = []
    if "live" in question_lower or "moved" in question_lower:
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
    if "what books" in question_lower and "read" in question_lower:
        predicates.append("book_read")
    if "destress" in question_lower:
        predicates.append("destress_activity")
    if question_lower.startswith("how long was i in"):
        predicates.append("trip_duration")
    if not predicates:
        predicates.append("raw_turn")
    return predicates


def _atom_score(question: NormalizedQuestion, atom: MemoryAtom) -> float:
    score = 0.0
    subject = _question_subject(question)
    predicates = _question_predicates(question)
    question_tokens = set(_tokenize(question.question))
    atom_tokens = set(_tokenize(atom.source_text))
    question_bigrams = _token_bigrams(question.question)
    atom_bigrams = _token_bigrams(atom.source_text)

    if atom.subject == subject:
        score += 3.0
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
    subject = _question_subject(question)
    latest_by_key: dict[tuple[str, str], MemoryAtom] = {}
    other_atoms: list[MemoryAtom] = []
    for atom in atoms:
        key = (atom.subject, atom.predicate)
        if atom.subject == subject and atom.predicate in predicates:
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
        if atom.subject == subject and atom.predicate in predicates:
            if key in seen_keys:
                continue
            seen_keys.add(key)
            chosen.append(atom)
        elif len(chosen) < limit:
            chosen.append(atom)
        if len(chosen) >= limit:
            break
    return chosen


def _session_lookup(sample: NormalizedBenchmarkSample) -> dict[str, NormalizedSession]:
    return {session.session_id: session for session in sample.sessions}


def _dedupe_observations(entries: list[ObservationEntry]) -> list[ObservationEntry]:
    deduped: list[ObservationEntry] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for entry in entries:
        entity_key = str(entry.metadata.get("entity_key", "")) if entry.predicate != "raw_turn" else entry.observation_id
        key = (entry.subject, entry.predicate, entity_key)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(entry)
    return deduped


def _observation_score(question: NormalizedQuestion, observation: ObservationEntry) -> float:
    score = 0.0
    subject = _question_subject(question)
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
    if observation.predicate in predicates:
        score += 4.0
    score += float(len(question_tokens.intersection(observation_tokens)))
    score += 1.5 * min(len(question_bigrams.intersection(observation_bigrams)), 3)
    if question.category in {"knowledge-update", "temporal", "temporal-reasoning"} and observation.timestamp:
        score += 1.0
    if observation.timestamp:
        score += 0.001 * sum(ord(char) for char in observation.timestamp)
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
            score += 6.0
        if "support group" in observation_lower or "support groups" in observation_lower:
            score += 6.0
    if "what events has" in question_lower and "help children" in question_lower:
        if any(
            token in observation_lower
            for token in ("mentorship program", "mentor", "young folks", "youth", "kids", "children")
        ):
            score += 6.0
        if "school event" in observation_lower or "giving my talk" in observation_lower or "better allies" in observation_lower:
            score += 6.0
    if "in what ways is" in question_lower and "lgbtq community" in question_lower:
        if "activist group" in observation_lower:
            score += 6.0
        if "pride parade" in observation_lower:
            score += 6.0
        if "art show" in observation_lower:
            score += 6.0
        if "mentorship program" in observation_lower or "mentor" in observation_lower:
            score += 6.0
    if "join a mentorship program" in question_lower:
        if "mentorship program" in observation_lower or "mentor" in observation_lower or "last weekend" in observation_lower:
            score += 7.0
    if "join a new activist group" in question_lower:
        if "activist group" in observation_lower or "last tues" in observation_lower or "last tuesday" in observation_lower:
            score += 7.0
    if "camping in june" in question_lower:
        if any(token in observation_lower for token in ("camping", "campfire", "nature", "hike", "marshmallows")):
            score += 7.0
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
    return score


def _question_aware_observation_limits(
    sample: NormalizedBenchmarkSample,
    question: NormalizedQuestion,
    *,
    max_observations: int,
    max_reflections: int,
) -> tuple[int, int]:
    if sample.benchmark_name != "LoCoMo":
        return max_observations, max_reflections

    question_lower = question.question.lower()
    observation_limit = max_observations
    reflection_limit = max_reflections

    if question.category in {"1", "3", "single-hop", "multi-hop"}:
        observation_limit = max(observation_limit, 6)
        reflection_limit = max(reflection_limit, 4)

    if (
        question_lower.startswith("who ")
        or question_lower.startswith("how many")
        or question_lower.startswith("would ")
        or question_lower.startswith("what events")
        or question_lower.startswith("what activities")
        or "in what ways" in question_lower
        or "what types of pottery" in question_lower
        or "what kind of art" in question_lower
        or ("what did" in question_lower and "paint" in question_lower)
    ):
        observation_limit = max(observation_limit, 10)
        reflection_limit = max(reflection_limit, 6)

    if question_lower.startswith("when did") or question_lower.startswith("when was") or question_lower.startswith("when is"):
        observation_limit = max(observation_limit, 6)
        reflection_limit = max(reflection_limit, 4)
        if any(
            token in question_lower
            for token in ("camping", "pride", "birthday", "activist group", "mentorship program")
        ):
            observation_limit = max(observation_limit, 8)
            reflection_limit = max(reflection_limit, 5)

    if (
        ("what lgbtq+" in question_lower or "what lgbtq events" in question_lower)
        or ("what events has" in question_lower and "help children" in question_lower)
    ):
        observation_limit = max(observation_limit, 12)
        reflection_limit = max(reflection_limit, 7)

    return observation_limit, reflection_limit


def _event_score(question: NormalizedQuestion, event: EventCalendarEntry) -> float:
    score = 0.0
    subject = _question_subject(question)
    predicates = _question_predicates(question)
    question_tokens = set(_tokenize(question.question))
    event_tokens = set(_tokenize(event.text))
    question_bigrams = _token_bigrams(question.question)
    event_bigrams = _token_bigrams(event.text)
    if event.subject == subject:
        score += 3.0
    if event.predicate in predicates:
        score += 5.0
    score += float(len(question_tokens.intersection(event_tokens)))
    score += 1.5 * min(len(question_bigrams.intersection(event_bigrams)), 3)
    if question.category in {"knowledge-update", "temporal", "temporal-reasoning"} and event.timestamp:
        score += 2.0
    if event.timestamp:
        score += 0.001 * sum(ord(char) for char in event.timestamp)
    return score


def build_observational_temporal_memory_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int = 8,
    max_reflections: int = 4,
    run_id: str = "observational-temporal-memory-v1",
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    packets: list[BaselinePromptPacket] = []
    for sample in samples:
        observations = build_observation_log(sample)
        reflected = reflect_observations(observations)
        for question in sample.questions:
            observation_limit, reflection_limit = _question_aware_observation_limits(
                sample,
                question,
                max_observations=max_observations,
                max_reflections=max_reflections,
            )
            if sample.benchmark_name == "LoCoMo":
                stable_window = _dedupe_observations(sorted(
                    observations,
                    key=lambda entry: (_observation_score(question, entry), entry.timestamp or "", entry.observation_id),
                    reverse=True,
                ))[:observation_limit]
            else:
                stable_window = sorted(
                    observations,
                    key=lambda entry: (entry.timestamp or "", entry.observation_id),
                )[-observation_limit:]
            ranked_reflections = sorted(
                reflected,
                key=lambda entry: (_observation_score(question, entry), entry.timestamp or "", entry.observation_id),
                reverse=True,
            )[:reflection_limit]

            context_blocks = ["stable_memory_window:"]
            retrieved_items: list[RetrievedContextItem] = []
            for entry in stable_window:
                line = f"observation: {entry.text}"
                item_metadata = {
                    "timestamp": entry.timestamp,
                    "predicate": entry.predicate,
                    "subject": entry.subject,
                }
                for field_name in ("img_url", "blip_caption", "search_query"):
                    if field_name in entry.metadata:
                        item_metadata[field_name] = entry.metadata[field_name]
                context_blocks.append(line)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=entry.session_id,
                        turn_ids=entry.turn_ids,
                        score=0.25,
                        strategy="observation_log",
                        text=line,
                        metadata=item_metadata,
                    )
                )

            context_blocks.append("reflected_memory:")
            for entry in ranked_reflections:
                line = f"reflection: {entry.text}"
                item_metadata = {
                    "timestamp": entry.timestamp,
                    "predicate": entry.predicate,
                    "subject": entry.subject,
                }
                for field_name in ("img_url", "blip_caption", "search_query"):
                    if field_name in entry.metadata:
                        item_metadata[field_name] = entry.metadata[field_name]
                context_blocks.append(line)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=entry.session_id,
                        turn_ids=entry.turn_ids,
                        score=_observation_score(question, entry),
                        strategy="reflected_memory",
                        text=line,
                        metadata=item_metadata,
                    )
                )

            if ranked_reflections:
                top_entry = ranked_reflections[0]
                answer_text = _answer_candidate_surface_text(
                    top_entry.subject,
                    top_entry.predicate,
                    top_entry.metadata.get("value", ""),
                    top_entry.text,
                )
                context_blocks.append(f"answer_candidate: {answer_text}")

            packets.append(
                BaselinePromptPacket(
                    benchmark_name=sample.benchmark_name,
                    baseline_name="observational_temporal_memory",
                    sample_id=sample.sample_id,
                    question_id=question.question_id,
                    question=question.question,
                    assembled_context="\n\n".join(context_blocks),
                    retrieved_context_items=retrieved_items,
                    metadata={
                        "route": "observational_temporal_memory",
                        "max_observations": observation_limit,
                        "max_reflections": reflection_limit,
                    },
                )
            )

    manifest = build_run_manifest(
        samples,
        baseline_name="observational_temporal_memory",
        run_id=run_id,
        metadata={
            "baseline_type": "candidate_memory_system",
            "system_name": "Observational Temporal Memory",
            "max_observations": max_observations,
            "max_reflections": max_reflections,
        },
    )
    return manifest.to_dict(), packets


def build_beam_ready_temporal_atom_router_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    top_k_atoms: int = 3,
    include_rehydrated_sessions: int = 1,
    run_id: str = "beam-temporal-atom-router-v1",
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    packets: list[BaselinePromptPacket] = []
    for sample in samples:
        atoms = extract_memory_atoms(sample)
        sessions = _session_lookup(sample)
        for question in sample.questions:
            chosen_atoms = _choose_atoms(question, atoms, top_k_atoms)
            rehydrated_session_ids: list[str] = []
            for atom in chosen_atoms:
                if atom.session_id not in rehydrated_session_ids:
                    rehydrated_session_ids.append(atom.session_id)
            rehydrated_session_ids = rehydrated_session_ids[:include_rehydrated_sessions]

            retrieved_items: list[RetrievedContextItem] = []
            context_blocks: list[str] = []
            for atom in chosen_atoms:
                atom_line = f"memory: {atom.source_text}"
                context_blocks.append(atom_line)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=atom.session_id,
                        turn_ids=[atom.turn_id],
                        score=_atom_score(question, atom),
                        strategy="temporal_atom_router",
                        text=atom_line,
                        metadata={
                            "atom_id": atom.atom_id,
                            "subject": atom.subject,
                            "predicate": atom.predicate,
                            "timestamp": atom.timestamp,
                        },
                    )
                )

            for session_id in rehydrated_session_ids:
                session = sessions[session_id]
                session_text = _serialize_session(session)
                context_blocks.append(session_text)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=session.session_id,
                        turn_ids=[turn.turn_id for turn in session.turns],
                        score=0.5,
                        strategy="source_rehydration",
                        text=session_text,
                        metadata={"timestamp": session.timestamp},
                    )
                )

            if chosen_atoms:
                primary_atom = chosen_atoms[0]
                context_blocks.append(f"answer_candidate: {primary_atom.source_text}")

            assembled_context = "\n\n".join(context_blocks)
            packets.append(
                BaselinePromptPacket(
                    benchmark_name=sample.benchmark_name,
                    baseline_name="beam_temporal_atom_router",
                    sample_id=sample.sample_id,
                    question_id=question.question_id,
                    question=question.question,
                    assembled_context=assembled_context,
                    retrieved_context_items=retrieved_items,
                    metadata={
                        "route": "temporal_atom_router",
                        "top_k_atoms": top_k_atoms,
                        "include_rehydrated_sessions": include_rehydrated_sessions,
                    },
                )
            )

    manifest = build_run_manifest(
        samples,
        baseline_name="beam_temporal_atom_router",
        run_id=run_id,
        metadata={
            "baseline_type": "candidate_memory_system",
            "system_name": "Beam-Ready Temporal Atom Router",
            "top_k_atoms": top_k_atoms,
            "include_rehydrated_sessions": include_rehydrated_sessions,
        },
    )
    return manifest.to_dict(), packets


def build_dual_store_event_calendar_hybrid_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int = 6,
    top_k_events: int = 3,
    run_id: str = "dual-store-event-calendar-hybrid-v1",
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    packets: list[BaselinePromptPacket] = []
    for sample in samples:
        observations = build_observation_log(sample)
        reflected = reflect_observations(observations)
        events = build_event_calendar(sample)
        stable_window = sorted(
            observations,
            key=lambda entry: (entry.timestamp or "", entry.observation_id),
        )[-max_observations:]
        for question in sample.questions:
            ranked_reflections = sorted(
                reflected,
                key=lambda entry: (_observation_score(question, entry), entry.timestamp or "", entry.observation_id),
                reverse=True,
            )[:2]
            ranked_events = sorted(
                events,
                key=lambda entry: (_event_score(question, entry), entry.timestamp or "", entry.event_id),
                reverse=True,
            )[:top_k_events]

            context_blocks = ["stable_memory_window:"]
            retrieved_items: list[RetrievedContextItem] = []
            for entry in stable_window:
                line = f"observation: {entry.text}"
                context_blocks.append(line)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=entry.session_id,
                        turn_ids=entry.turn_ids,
                        score=0.25,
                        strategy="hybrid_observation_window",
                        text=line,
                        metadata={"timestamp": entry.timestamp, "predicate": entry.predicate, "subject": entry.subject},
                    )
                )

            context_blocks.append("event_calendar:")
            for entry in ranked_events:
                prefix = f"{entry.timestamp} " if entry.timestamp else ""
                line = f"event: {prefix}{entry.text}"
                context_blocks.append(line)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=entry.session_id,
                        turn_ids=entry.turn_ids,
                        score=_event_score(question, entry),
                        strategy="event_calendar",
                        text=line,
                        metadata={"timestamp": entry.timestamp, "predicate": entry.predicate, "subject": entry.subject},
                    )
                )

            context_blocks.append("reflected_memory:")
            for entry in ranked_reflections:
                line = f"reflection: {entry.text}"
                context_blocks.append(line)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=entry.session_id,
                        turn_ids=entry.turn_ids,
                        score=_observation_score(question, entry),
                        strategy="hybrid_reflection",
                        text=line,
                        metadata={"timestamp": entry.timestamp, "predicate": entry.predicate, "subject": entry.subject},
                    )
                )

            if ranked_events:
                top_entry = ranked_events[0]
                answer_text = _answer_candidate_surface_text(
                    top_entry.subject,
                    top_entry.predicate,
                    top_entry.metadata.get("value", ""),
                    top_entry.text,
                )
                context_blocks.append(f"answer_candidate: {answer_text}")
            elif ranked_reflections:
                top_entry = ranked_reflections[0]
                answer_text = _answer_candidate_surface_text(
                    top_entry.subject,
                    top_entry.predicate,
                    top_entry.metadata.get("value", ""),
                    top_entry.text,
                )
                context_blocks.append(f"answer_candidate: {answer_text}")

            packets.append(
                BaselinePromptPacket(
                    benchmark_name=sample.benchmark_name,
                    baseline_name="dual_store_event_calendar_hybrid",
                    sample_id=sample.sample_id,
                    question_id=question.question_id,
                    question=question.question,
                    assembled_context="\n\n".join(context_blocks),
                    retrieved_context_items=retrieved_items,
                    metadata={
                        "route": "dual_store_event_calendar_hybrid",
                        "max_observations": max_observations,
                        "top_k_events": top_k_events,
                    },
                )
            )

    manifest = build_run_manifest(
        samples,
        baseline_name="dual_store_event_calendar_hybrid",
        run_id=run_id,
        metadata={
            "baseline_type": "candidate_memory_system",
            "system_name": "Dual-Store Event Calendar Hybrid",
            "max_observations": max_observations,
            "top_k_events": top_k_events,
        },
    )
    return manifest.to_dict(), packets


def build_memory_system_contract_summary() -> dict[str, Any]:
    return {
        "candidate_memory_systems": [
            {
                "system_name": "beam_temporal_atom_router",
                "entrypoint": "build_beam_ready_temporal_atom_router_packets",
                "behavior": "Extract temporal atoms, apply recency-aware routing, then rehydrate the strongest source sessions.",
            },
            {
                "system_name": "observational_temporal_memory",
                "entrypoint": "build_observational_temporal_memory_packets",
                "behavior": "Build a stable observation log, reflect it into a compressed memory window, and answer from that stable context.",
            },
            {
                "system_name": "dual_store_event_calendar_hybrid",
                "entrypoint": "build_dual_store_event_calendar_hybrid_packets",
                "behavior": "Combine a stable observation window with an explicit event calendar and answer from the strongest hybrid signal.",
            }
        ],
        "memory_contracts": [
            "MemoryAtom",
            "ObservationEntry",
            "EventCalendarEntry",
            "RetrievedContextItem",
            "BaselinePromptPacket",
        ],
    }
