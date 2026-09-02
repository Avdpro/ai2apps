"""Physical L1/Hot restoration for serialized GLM-5 chat sessions."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any


class Glm5SessionCacheController:
    def __init__(self, owner: Any, *, max_sessions: int = 8) -> None:
        self.owner = owner
        self.max_sessions = max_sessions
        self.active_session: str | None = None
        self.snapshots: OrderedDict[str, dict] = OrderedDict()
        self.restores = 0
        self.restore_experts = 0
        self.restore_bytes = 0
        self.restore_seconds = 0.0

    def _cache(self):
        for decoder in self.owner._vlm_model.language_model.model.layers:
            cache = getattr(decoder.mlp, "dynamic_cache", None)
            if cache is not None:
                return cache
        raise RuntimeError("GLM5 dynamic cache is not attached to the model")

    def _save(self, session_id: str) -> None:
        self.snapshots[session_id] = self._cache().session_snapshot()
        self.snapshots.move_to_end(session_id)
        while len(self.snapshots) > self.max_sessions:
            self.snapshots.popitem(last=False)

    def prepare(self, session_id: str) -> dict[str, int | float]:
        if session_id == self.active_session:
            return {"experts_loaded": 0, "bytes_loaded": 0, "seconds": 0.0}
        if self.active_session is not None:
            self._save(self.active_session)
        result = {"experts_loaded": 0, "bytes_loaded": 0, "seconds": 0.0}
        snapshot = self.snapshots.get(session_id)
        if snapshot is not None:
            result = self._cache().restore_session(snapshot)
            self.snapshots.move_to_end(session_id)
            self.restores += 1
            self.restore_experts += int(result["experts_loaded"])
            self.restore_bytes += int(result["bytes_loaded"])
            self.restore_seconds += float(result["seconds"])
        self.active_session = session_id
        return result

    def finish(self, session_id: str) -> None:
        if session_id == self.active_session:
            self._save(session_id)

    def stats(self) -> dict[str, int | float | str | None]:
        return {
            "active_session": self.active_session,
            "saved_sessions": len(self.snapshots),
            "max_sessions": self.max_sessions,
            "restores": self.restores,
            "restore_experts": self.restore_experts,
            "restore_bytes": self.restore_bytes,
            "restore_seconds": self.restore_seconds,
        }


__all__ = ["Glm5SessionCacheController"]
