from __future__ import annotations

import re

_SMALL_NUMBER_WORDS = {
    "a": 1.0,
    "an": 1.0,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
}


def parse_small_number(raw_value: str) -> float | None:
    value = raw_value.strip().lower().replace(",", "")
    if not value:
        return None
    if value in _SMALL_NUMBER_WORDS:
        return _SMALL_NUMBER_WORDS[value]
    try:
        return float(value)
    except ValueError:
        return None


def format_count_value(value: float, unit: str = "") -> str:
    if value.is_integer():
        text = str(int(value))
    else:
        text = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{text} {unit}".strip()


def extract_first_numeric_match(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    for group in match.groups():
        if group is None:
            continue
        parsed = parse_small_number(group)
        if parsed is not None:
            return parsed
    return None
