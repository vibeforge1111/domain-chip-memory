from __future__ import annotations

from .contracts import NormalizedSession


def serialize_session(session: NormalizedSession) -> str:
    lines = []
    header = f"Session {session.session_id}"
    if session.timestamp:
        header += f" @ {session.timestamp}"
    lines.append(header)
    for turn in session.turns:
        lines.append(f"{turn.speaker}: {turn.text}")
    return "\n".join(lines)
