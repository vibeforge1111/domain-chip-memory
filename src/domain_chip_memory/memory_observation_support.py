from __future__ import annotations

from collections.abc import Callable

from .contracts import NormalizedBenchmarkSample, NormalizedQuestion
from .memory_extraction import EventCalendarEntry, ObservationEntry


def build_observation_log(
    sample: NormalizedBenchmarkSample,
    *,
    build_observation_log_impl: Callable[..., list[ObservationEntry]],
    extract_memory_atoms: Callable[[NormalizedBenchmarkSample], list[object]],
    observation_surface_text: Callable[..., str],
) -> list[ObservationEntry]:
    return build_observation_log_impl(
        sample,
        extract_memory_atoms=extract_memory_atoms,
        observation_surface_text=observation_surface_text,
    )


def reflect_observations(
    observations: list[ObservationEntry],
    *,
    build_current_state_view: Callable[[list[ObservationEntry]], list[ObservationEntry]],
) -> list[ObservationEntry]:
    return build_current_state_view(observations)


def topical_episode_support(
    question: NormalizedQuestion,
    stable_window: list[ObservationEntry],
    observations: list[ObservationEntry],
    *,
    max_support: int = 2,
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    turn_order_key: Callable[[list[str]], tuple[object, ...]],
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
        candidate_topic_scores[topic_id] = candidate_topic_scores.get(topic_id, 0.0) + max(observation_score(question, entry), 0.0)
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
            key=lambda entry: (observation_score(question, entry), entry.timestamp or "", *turn_order_key(entry.turn_ids), entry.observation_id),
            reverse=True,
        )[:max_support]
        if ranked_extras:
            return candidate_topic_summaries.get(topic_id, ""), ranked_extras
    return "", []


def build_event_calendar(
    sample: NormalizedBenchmarkSample,
    *,
    build_event_calendar_impl: Callable[..., list[EventCalendarEntry]],
    extract_memory_atoms: Callable[[NormalizedBenchmarkSample], list[object]],
    observation_surface_text: Callable[..., str],
) -> list[EventCalendarEntry]:
    return build_event_calendar_impl(
        sample,
        extract_memory_atoms=extract_memory_atoms,
        observation_surface_text=observation_surface_text,
    )
