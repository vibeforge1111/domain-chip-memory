from __future__ import annotations

import re
from datetime import datetime, timedelta


def parse_observation_anchor(timestamp: str) -> datetime | None:
    timestamp = timestamp.strip()
    if not timestamp:
        return None
    normalized = timestamp.replace("am", "AM").replace("pm", "PM")
    for pattern in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%I:%M %p on %d %B, %Y", "%I:%M %p on %d %B %Y"):
        try:
            return datetime.strptime(normalized, pattern)
        except ValueError:
            continue
    return None


def format_full_date(value: datetime) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def format_month_year(value: datetime) -> str:
    return value.strftime("%B %Y")


def shift_month(value: datetime, offset: int) -> datetime:
    month_index = (value.month - 1) + offset
    year = value.year + (month_index // 12)
    month = (month_index % 12) + 1
    return datetime(year, month, 1)


def parse_question_state_anchor(question_lower: str) -> tuple[datetime | None, datetime | None, datetime | None]:
    exact_time_match = re.search(
        r"\bat\s+(\d{1,2}(?::\d{2})?\s*[ap]m)\s+on\s+(\d{1,2})\s+"
        r"(january|february|march|april|may|june|july|august|september|october|november|december)"
        r"\s+(\d{4})\b",
        question_lower,
    )
    if exact_time_match:
        clock_text = re.sub(r"\s+", " ", exact_time_match.group(1).upper()).strip()
        parsed_time: datetime | None = None
        for pattern in ("%I:%M %p", "%I %p"):
            try:
                parsed_time = datetime.strptime(clock_text, pattern)
                break
            except ValueError:
                continue
        if parsed_time is not None:
            return (
                datetime.strptime(
                    f"{exact_time_match.group(2)} {exact_time_match.group(3).title()} {exact_time_match.group(4)} "
                    f"{parsed_time.strftime('%H:%M')}",
                    "%d %B %Y %H:%M",
                ),
                None,
                None,
            )

    exact_date_match = re.search(
        r"\b(?:on)\s+(\d{1,2})\s+"
        r"(january|february|march|april|may|june|july|august|september|october|november|december)"
        r"\s+(\d{4})\b",
        question_lower,
    )
    if exact_date_match:
        target_start = datetime.strptime(
            f"{exact_date_match.group(1)} {exact_date_match.group(2).title()} {exact_date_match.group(3)}",
            "%d %B %Y",
        )
        return (None, target_start, target_start + timedelta(days=1))

    month_match = re.search(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})\b",
        question_lower,
    )
    if month_match:
        target_start = datetime.strptime(
            f"{month_match.group(1).title()} {month_match.group(2)}",
            "%B %Y",
        )
        return (None, target_start, shift_month(target_start, 1))
    return (None, None, None)
