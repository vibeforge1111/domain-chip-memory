from __future__ import annotations

from copy import deepcopy
from typing import Any


KNOWN_BENCHMARK_ISSUES: dict[str, dict[str, Any]] = {
    "conv-26-qa-6": {
        "classification": "benchmark_inconsistency",
        "summary": "Evidence turn D2:1 says last Saturday on 25 May, 2023, while the gold answer expects Sunday.",
        "recommended_lane": "benchmark_audit",
    },
}


def get_known_benchmark_issue(question_id: str) -> dict[str, Any] | None:
    issue = KNOWN_BENCHMARK_ISSUES.get(question_id)
    if issue is None:
        return None
    return deepcopy(issue)
