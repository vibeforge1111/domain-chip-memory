from __future__ import annotations

import re


def ordered_sequence_labels(context_lines: list[str]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    patterns = (
        r"\bi visited\s+([A-Z][A-Za-z0-9 .'-]+?)\s+in\b",
        r"\bi booked\s+([A-Z][A-Za-z0-9 .'-]+?)\s+for\b",
    )
    for line in context_lines:
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if not match:
                continue
            label = match.group(1).strip().rstrip(".!?")
            key = label.lower()
            if key in seen:
                break
            seen.add(key)
            labels.append(label)
            break
    return labels


def ordered_location_rows(context_lines: list[str]) -> list[tuple[int, str, str]]:
    def _extract_location_rows(lines: list[str]) -> list[tuple[int, str, str]]:
        rows: list[tuple[int, str, str]] = []
        patterns = (
            r"\b(?:live|lived)\s+in\s+([A-Za-z][A-Za-z0-9 .'-]+)",
            r"\b(?:moved|move)\s+(?:back\s+)?to\s+([A-Za-z][A-Za-z0-9 .'-]+)",
        )
        for idx, line in enumerate(lines):
            for pattern in patterns:
                location_match = re.search(pattern, line, re.IGNORECASE)
                if not location_match:
                    continue
                rows.append((idx, location_match.group(1).strip().rstrip(".!?"), line.lower()))
                break
        return rows

    observation_lines = [line for line in context_lines if line.lower().startswith("observation:")]
    return _extract_location_rows(observation_lines) or _extract_location_rows(context_lines)


def location_anchor_from_phrase(phrase: str) -> tuple[str, bool] | None:
    normalized = phrase.strip().rstrip(".!?")
    if not normalized:
        return None
    location_match = re.search(r"\b(?:back to|to|in)\s+([a-z][a-z0-9 .'-]+)$", normalized)
    if location_match:
        return location_match.group(1).strip(), "back to" in normalized or "again" in normalized
    return normalized, "back to" in normalized or "again" in normalized
