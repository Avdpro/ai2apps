"""Small in-process controls for live Fusion turns."""

from __future__ import annotations

import threading


_lock = threading.Lock()
_skip_review_sessions: set[str] = set()
_active_fusion_sessions: dict[str, int] = {}


def begin_fusion_session(session_id: str) -> None:
    with _lock:
        _active_fusion_sessions[session_id] = (
            _active_fusion_sessions.get(session_id, 0) + 1
        )


def end_fusion_session(session_id: str) -> None:
    with _lock:
        remaining = _active_fusion_sessions.get(session_id, 0) - 1
        if remaining > 0:
            _active_fusion_sessions[session_id] = remaining
        else:
            _active_fusion_sessions.pop(session_id, None)
            _skip_review_sessions.discard(session_id)


def request_active_skip_review(session_id: str) -> bool:
    """Queue a skip only for a Fusion turn that is currently running."""
    with _lock:
        if _active_fusion_sessions.get(session_id, 0) <= 0:
            return False
        _skip_review_sessions.add(session_id)
        return True


def request_skip_review(session_id: str) -> None:
    with _lock:
        _skip_review_sessions.add(session_id)


def skip_review_requested(session_id: str) -> bool:
    with _lock:
        return session_id in _skip_review_sessions


def consume_skip_review(session_id: str) -> bool:
    with _lock:
        if session_id not in _skip_review_sessions:
            return False
        _skip_review_sessions.remove(session_id)
        return True
