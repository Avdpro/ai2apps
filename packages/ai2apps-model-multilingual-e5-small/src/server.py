"""Local OpenAI-compatible embedding endpoint backed by MLX Embeddings."""

from __future__ import annotations

import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MODEL_ID = "mlx-community/multilingual-e5-small-mlx"
DIMENSION = 384
MAX_BODY_BYTES = 4 * 1024 * 1024
MAX_INPUTS = 256
MAX_TEXT_BYTES = 64 * 1024


class RequestError(ValueError):
    pass


class Embedder:
    def __init__(self) -> None:
        raw = os.environ.get("AI2APPS_MODEL_CHECKPOINTS_JSON", "[]")
        try:
            checkpoints = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError("Host checkpoint declaration is invalid") from error
        selected = next(
            (item for item in checkpoints if item.get("model_id", "").endswith("/default")),
            None,
        )
        self.path = Path(selected["path"]) if selected and selected.get("path") else None
        self._model = None
        self._tokenizer = None
        self._lock = threading.Lock()

    @property
    def checkpoint_ready(self) -> bool:
        return self.path is not None and self.path.is_dir()

    def _load(self):
        if not self.checkpoint_ready:
            raise RuntimeError("Embedding checkpoint is not ready")
        with self._lock:
            if self._model is None:
                from e5_mlx import E5Embedder

                self._model = E5Embedder(self.path)
        return self._model

    def embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        if input_type not in {"query", "passage"}:
            raise RequestError("input_type must be query or passage")
        prefix = input_type + ": "
        model = self._load()
        values = model.encode([prefix + text for text in texts])
        if len(values) != len(texts) or any(len(row) != DIMENSION for row in values):
            raise RuntimeError("Embedding Runtime returned an unexpected shape")
        return [[float(value) for value in row] for row in values]


class Handler(BaseHTTPRequestHandler):
    server_version = "AI2AppsEmbedding/0.1"

    def _send(self, status: int, value: dict[str, Any]) -> None:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self._send(404, {"error": "not_found"})
            return
        self._send(
            200,
            {
                "status": "ready",
                "checkpoint_ready": self.server.embedder.checkpoint_ready,
                "model": MODEL_ID,
                "dimension": DIMENSION,
                "capabilities": ["text-embeddings"],
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/embeddings":
            self._send(404, {"error": "not_found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0 or size > MAX_BODY_BYTES:
                raise RequestError("request body is too large")
            body = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(body, dict):
                raise RequestError("request body must be an object")
            inputs = body.get("input")
            if isinstance(inputs, str):
                inputs = [inputs]
            if not isinstance(inputs, list) or not 1 <= len(inputs) <= MAX_INPUTS:
                raise RequestError("input is invalid")
            if not all(
                isinstance(value, str)
                and value
                and len(value.encode("utf-8")) <= MAX_TEXT_BYTES
                for value in inputs
            ):
                raise RequestError("input contains invalid text")
            vectors = self.server.embedder.embed(inputs, body.get("input_type", "passage"))
            self._send(
                200,
                {
                    "object": "list",
                    "model": MODEL_ID,
                    "data": [
                        {"object": "embedding", "index": index, "embedding": vector}
                        for index, vector in enumerate(vectors)
                    ],
                    "usage": {"prompt_tokens": 0, "total_tokens": 0},
                    "dimension": DIMENSION,
                },
            )
        except (RequestError, json.JSONDecodeError, ValueError) as error:
            self._send(400, {"error": {"code": "invalid_request", "message": str(error)}})
        except RuntimeError as error:
            self._send(503, {"error": {"code": "embedding_unavailable", "message": str(error)}})

    def log_message(self, format: str, *args: Any) -> None:
        print(json.dumps({"level": "info", "message": format % args}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.embedder = Embedder()
    server.serve_forever()


if __name__ == "__main__":
    main()
