from __future__ import annotations

from collections.abc import Callable

from .contracts import NormalizedQuestion
from .memory_extraction import MemoryAtom


def atom_score(
    question: NormalizedQuestion,
    atom: MemoryAtom,
    *,
    question_subject: Callable[[NormalizedQuestion], str],
    question_subjects: Callable[[NormalizedQuestion], list[str]],
    question_predicates: Callable[[NormalizedQuestion], list[str]],
    tokenize: Callable[[str], list[str]],
    token_bigrams: Callable[[str], set[tuple[str, str]]],
) -> float:
    score = 0.0
    subject = question_subject(question)
    subjects = set(question_subjects(question))
    predicates = question_predicates(question)
    question_tokens = set(tokenize(question.question))
    atom_tokens = set(tokenize(atom.source_text))
    question_bigrams = token_bigrams(question.question)
    atom_bigrams = token_bigrams(atom.source_text)

    if atom.subject == subject:
        score += 3.0
    elif atom.subject in subjects:
        score += 2.5
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


def choose_atoms(
    question: NormalizedQuestion,
    atoms: list[MemoryAtom],
    limit: int,
    *,
    question_predicates: Callable[[NormalizedQuestion], list[str]],
    question_subjects: Callable[[NormalizedQuestion], list[str]],
    atom_score: Callable[[NormalizedQuestion, MemoryAtom], float],
) -> list[MemoryAtom]:
    predicates = set(question_predicates(question))
    subjects = set(question_subjects(question))
    latest_by_key: dict[tuple[str, str], MemoryAtom] = {}
    other_atoms: list[MemoryAtom] = []
    for atom in atoms:
        key = (atom.subject, atom.predicate)
        if atom.subject in subjects and atom.predicate in predicates:
            current = latest_by_key.get(key)
            if current is None or (atom.timestamp or "") >= (current.timestamp or ""):
                latest_by_key[key] = atom
        else:
            other_atoms.append(atom)

    scored = sorted(
        [*latest_by_key.values(), *other_atoms],
        key=lambda atom: (atom_score(question, atom), atom.timestamp or "", atom.atom_id),
        reverse=True,
    )
    chosen: list[MemoryAtom] = []
    seen_keys: set[tuple[str, str]] = set()
    for atom in scored:
        key = (atom.subject, atom.predicate)
        if atom.subject in subjects and atom.predicate in predicates:
            if key in seen_keys:
                continue
            seen_keys.add(key)
            chosen.append(atom)
        elif len(chosen) < limit:
            chosen.append(atom)
        if len(chosen) >= limit:
            break
    return chosen
