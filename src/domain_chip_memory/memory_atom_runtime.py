from __future__ import annotations

from .contracts import NormalizedBenchmarkSample, NormalizedQuestion
from .memory_aggregate_support import raw_user_turn_entries as _raw_user_turn_entries_impl
from .memory_aggregate_support import select_aggregate_support_entries as _select_aggregate_support_entries_impl
from .memory_atom_extraction import extract_memory_atoms
from .memory_atom_routing import atom_score as _atom_score_impl
from .memory_atom_routing import choose_atoms as _choose_atoms_impl
from .memory_extraction import MemoryAtom, ObservationEntry, _token_bigrams, _tokenize
from .memory_queries import _question_predicates, _question_subject, _question_subjects


def _atom_score(question: NormalizedQuestion, atom: MemoryAtom) -> float:
    return _atom_score_impl(
        question,
        atom,
        question_subject=_question_subject,
        question_subjects=_question_subjects,
        question_predicates=_question_predicates,
        tokenize=_tokenize,
        token_bigrams=_token_bigrams,
    )


def _choose_atoms(question: NormalizedQuestion, atoms: list[MemoryAtom], limit: int) -> list[MemoryAtom]:
    return _choose_atoms_impl(
        question,
        atoms,
        limit,
        question_predicates=_question_predicates,
        question_subjects=_question_subjects,
        atom_score=_atom_score,
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
