from __future__ import annotations

from .memory_answer_rendering import answer_candidate_surface_text
from .contracts import NormalizedSession
from .memory_observation_rendering import observation_surface_text

def serialize_session(session: NormalizedSession) -> str:
    lines = []
    header = f"Session {session.session_id}"
    if session.timestamp:
        header += f" @ {session.timestamp}"
    lines.append(header)
    for turn in session.turns:
        lines.append(f"{turn.speaker}: {turn.text}")
    return "\n".join(lines)


