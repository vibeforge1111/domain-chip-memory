from __future__ import annotations

import re

from .provider_temporal_rescue import COUNT_WORDS, COUNT_WORD_TO_INT


def numeric_rescue(question_lower: str, answer: str, combined: str) -> str | None:
    if "what speed" in question_lower or "internet plan" in question_lower:
        match = re.search(r"\b(\d+\s*(?:mbps|gbps))\b", combined, re.IGNORECASE)
        if match:
            return match.group(1)

    if question_lower.startswith("how much"):
        for pattern in (
            r"\$(\d+(?:,\d{3})*(?:\.\d+)?)",
            r"\b(\d+\s*dollars)\b",
            r"(?<!\S)(\d+%)(?!\S)",
            r"\b(\d+:\d+)\b",
            r"\b(\d+gb)\b",
        ):
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if pattern.startswith(r"\$("):
                    return f"${value}"
                return value

    if "discount" in question_lower:
        match = re.search(r"(?<!\S)(\d+%)(?!\S)", answer, re.IGNORECASE) or re.search(
            r"(?<!\S)(\d+%)(?!\S)",
            combined,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)

    if "how old was i" in question_lower:
        match = re.search(r"\bmy\s+(\d+)(?:st|nd|rd|th)\s+birthday\b", combined, re.IGNORECASE)
        if match:
            return match.group(1)

    if " ratio" in question_lower or "ratio " in question_lower:
        match = re.search(r"\b(\d+:\d+)\b", combined, re.IGNORECASE)
        if match:
            return match.group(1)

    if question_lower.startswith("how long ago"):
        match = re.search(
            r"\b(" + "|".join(sorted(COUNT_WORDS, key=len, reverse=True)) + r"|\d+)\s+(years?|months?|weeks?|days?)\s+ago\b",
            combined,
            re.IGNORECASE,
        )
        if match:
            raw_count = match.group(1).lower()
            count = raw_count if raw_count.isdigit() else str(COUNT_WORD_TO_INT.get(raw_count, raw_count))
            return f"{count} {match.group(2)} ago"

    if question_lower.startswith("how long") and "married" not in question_lower:
        match = re.search(
            r"\b(" + "|".join(sorted(COUNT_WORDS, key=len, reverse=True)) + r"|\d+)\s+(hours?|days?|weeks?|months?|years?)\b",
            combined,
            re.IGNORECASE,
        )
        if match:
            raw_count = match.group(1).lower()
            count = raw_count if raw_count.isdigit() else str(COUNT_WORD_TO_INT.get(raw_count, raw_count))
            return f"{count} {match.group(2)}"

    return None
