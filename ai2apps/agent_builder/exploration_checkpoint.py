"""Owner- and Tab-bound recovery points for Sidebar-driven exploration."""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

MAX_BYTES = 2_000_000
TTL_SECONDS = 24 * 60 * 60

class ExplorationCheckpointStore:
    def __init__(self, root: Path):
        self.root = root

    def path(self, actor: str, context: str) -> Path:
        key = hashlib.sha256((actor + '\0' + context).encode()).hexdigest()
        return self.root / (key + '.json')

    def save(self, actor: str, context: str, checkpoint: dict) -> None:
        payload = json.dumps({'saved_at': time.time(), 'checkpoint': checkpoint}, ensure_ascii=False).encode()
        if len(payload) > MAX_BYTES:
            raise ValueError('Exploration checkpoint exceeds 2 MB')
        self.root.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.root, prefix='.checkpoint-')
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path(actor, context))
        finally:
            Path(name).unlink(missing_ok=True)

    def load(self, actor: str, context: str) -> dict | None:
        path = self.path(actor, context)
        try:
            payload = json.loads(path.read_text())
        except (FileNotFoundError, ValueError):
            return None
        if time.time() - payload['saved_at'] > TTL_SECONDS:
            path.unlink(missing_ok=True)
            return None
        return payload['checkpoint']
