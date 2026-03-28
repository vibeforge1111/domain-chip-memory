from __future__ import annotations

from .contracts import NormalizedBenchmarkSample, NormalizedQuestion
from .memory_atom_extraction import extract_memory_atoms
from .memory_extraction import EventCalendarEntry, ObservationEntry, _turn_order_key
from .memory_extraction import build_event_calendar as _build_event_calendar
from .memory_extraction import build_observation_log as _build_observation_log
from .memory_observation_scoring_rules import observation_score as _observation_score_impl
from .memory_observation_support import build_event_calendar as _build_event_calendar_support_impl
from .memory_observation_support import build_observation_log as _build_observation_log_support_impl
from .memory_observation_support import reflect_observations as _reflect_observations_impl
from .memory_observation_support import topical_episode_support as _topical_episode_support_impl
from .memory_observation_rendering import observation_surface_text as _observation_surface_text
from .memory_updates import build_current_state_view


def _observation_score(question: NormalizedQuestion, observation: ObservationEntry) -> float:
    return _observation_score_impl(question, observation)


def build_observation_log(sample: NormalizedBenchmarkSample) -> list[ObservationEntry]:
    return _build_observation_log_support_impl(
        sample,
        build_observation_log_impl=_build_observation_log,
        extract_memory_atoms=extract_memory_atoms,
        observation_surface_text=_observation_surface_text,
    )


def reflect_observations(observations: list[ObservationEntry]) -> list[ObservationEntry]:
    return _reflect_observations_impl(
        observations,
        build_current_state_view=build_current_state_view,
    )


def _topical_episode_support(
    question: NormalizedQuestion,
    stable_window: list[ObservationEntry],
    observations: list[ObservationEntry],
    *,
    max_support: int = 2,
) -> tuple[str, list[ObservationEntry]]:
    return _topical_episode_support_impl(
        question,
        stable_window,
        observations,
        max_support=max_support,
        observation_score=_observation_score,
        turn_order_key=_turn_order_key,
    )


def build_event_calendar(sample: NormalizedBenchmarkSample) -> list[EventCalendarEntry]:
    return _build_event_calendar_support_impl(
        sample,
        build_event_calendar_impl=_build_event_calendar,
        extract_memory_atoms=extract_memory_atoms,
        observation_surface_text=_observation_surface_text,
    )
