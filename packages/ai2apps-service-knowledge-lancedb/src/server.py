"""Isolated LanceDB HTTP worker for rebuildable Knowledge vectors."""

from __future__ import annotations

import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MAX_BODY_BYTES = 32 * 1024 * 1024
MAX_BATCH_RECORDS = 1000
MAX_TEXT_BYTES = 256 * 1024
MAX_DIMENSION = 4096
SAFE_GENERATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class RequestError(ValueError):
    pass


def _text(value: Any, field: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise RequestError(f"{field} is invalid")
    return value


def _generation(value: Any) -> str:
    if not isinstance(value, str) or not SAFE_GENERATION.fullmatch(value):
        raise RequestError("generation is invalid")
    return value


def _dimension(value: Any) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1 <= value <= MAX_DIMENSION
    ):
        raise RequestError("dimension is invalid")
    return value


def _vector(value: Any, dimension: int) -> list[float]:
    if not isinstance(value, list) or len(value) != dimension:
        raise RequestError("vector dimension mismatch")
    result: list[float] = []
    for item in value:
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            raise RequestError("vector contains a non-number")
        result.append(float(item))
    return result


def _sql(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class Store:
    def __init__(self, root: Path) -> None:
        try:
            import lancedb
        except ImportError as error:
            raise RuntimeError(
                "LanceDB is absent from the Knowledge Runtime"
            ) from error
        root.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(root))

    def names(self) -> set[str]:
        names = self.db.table_names()
        if hasattr(names, "tables"):
            names = names.tables
        return {str(name) for name in names}

    @staticmethod
    def table_name(generation: str) -> str:
        return "knowledge_" + re.sub(r"[^A-Za-z0-9_]", "_", generation)

    def table(self, generation: str):
        name = self.table_name(generation)
        return self.db.open_table(name) if name in self.names() else None

    def upsert(self, body: dict[str, Any]) -> dict[str, Any]:
        generation = _generation(body.get("generation"))
        dimension = _dimension(body.get("dimension"))
        records = body.get("records")
        if not isinstance(records, list) or len(records) > MAX_BATCH_RECORDS:
            raise RequestError("records is invalid")
        rows = []
        for raw in records:
            if not isinstance(raw, dict):
                raise RequestError("record is invalid")
            bucket_ids = raw.get("bucket_ids", [])
            if not isinstance(bucket_ids, list) or len(bucket_ids) > 100:
                raise RequestError("bucket_ids is invalid")
            text = _text(raw.get("text"), "text", maximum=MAX_TEXT_BYTES)
            rows.append(
                {
                    "chunk_id": _text(raw.get("chunk_id"), "chunk_id"),
                    "item_id": _text(raw.get("item_id"), "item_id"),
                    "installation_id": _text(
                        raw.get("installation_id"), "installation_id"
                    ),
                    "owner_user_id": _text(raw.get("owner_user_id"), "owner_user_id"),
                    "visibility": _text(
                        raw.get("visibility"), "visibility", maximum=32
                    ),
                    "bucket_ids": [_text(value, "bucket_id") for value in bucket_ids],
                    "text": text,
                    "vector": _vector(raw.get("vector"), dimension),
                }
            )
        if not rows:
            return {"upserted": 0, "generation": generation}
        table = self.table(generation)
        if table is None:
            self.db.create_table(self.table_name(generation), data=rows)
        else:
            (
                table.merge_insert("chunk_id")
                .when_matched_update_all()
                .when_not_matched_insert_all()
                .execute(rows)
            )
        return {"upserted": len(rows), "generation": generation}

    def delete(self, body: dict[str, Any]) -> dict[str, Any]:
        generation = _generation(body.get("generation"))
        values = body.get("item_ids")
        if not isinstance(values, list) or len(values) > 1000:
            raise RequestError("item_ids is invalid")
        item_ids = list(dict.fromkeys(_text(value, "item_id") for value in values))
        table = self.table(generation)
        if table is not None and item_ids:
            table.delete(
                "item_id IN (" + ",".join(_sql(value) for value in item_ids) + ")"
            )
        return {"deleted": len(item_ids), "generation": generation}

    def reset(self, body: dict[str, Any]) -> dict[str, Any]:
        generation = _generation(body.get("generation"))
        name = self.table_name(generation)
        try:
            self.db.drop_table(name)
        except Exception as error:
            if "not found" not in str(error).lower():
                raise
        return {"reset": True, "generation": generation}

    def search(self, body: dict[str, Any]) -> dict[str, Any]:
        generation = _generation(body.get("generation"))
        dimension = _dimension(body.get("dimension"))
        limit = body.get("limit", 20)
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 100
        ):
            raise RequestError("limit is invalid")
        installation = _text(body.get("installation_id"), "installation_id")
        actor = _text(body.get("actor_user_id"), "actor_user_id")
        buckets = body.get("bucket_ids", [])
        if not isinstance(buckets, list) or len(buckets) > 100:
            raise RequestError("bucket_ids is invalid")
        clauses = [
            f"installation_id = {_sql(installation)}",
            "(visibility = 'installation' OR "
            f"(visibility = 'private' AND owner_user_id = {_sql(actor)}))",
        ]
        if buckets:
            selected = ",".join(_sql(_text(value, "bucket_id")) for value in buckets)
            clauses.append(f"array_has_any(bucket_ids, [{selected}])")
        table = self.table(generation)
        if table is None:
            return {"items": [], "generation": generation}
        rows = (
            table.search(
                _vector(body.get("vector"), dimension), vector_column_name="vector"
            )
            .where(" AND ".join(clauses), prefilter=True)
            .select(["chunk_id", "item_id", "text"])
            .limit(limit)
            .to_arrow()
            .to_pylist()
        )
        return {
            "items": [
                {
                    "chunk_id": str(row["chunk_id"]),
                    "item_id": str(row["item_id"]),
                    "text": str(row["text"]),
                    "distance": float(row["_distance"]),
                }
                for row in rows
            ],
            "generation": generation,
        }

    def health(self, body: dict[str, Any]) -> dict[str, Any]:
        generation = body.get("generation")
        count = None
        if generation is not None:
            table = self.table(_generation(generation))
            count = 0 if table is None else int(table.count_rows())
        return {
            "status": "ready",
            "backend": "lancedb",
            "generation": generation,
            "count": count,
            "capabilities": ["knowledge-vector-index-v1"],
        }


class Handler(BaseHTTPRequestHandler):
    server_version = "AI2AppsKnowledgeVector/0.1"

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
        try:
            self._send(200, self.server.store.health({}))
        except Exception as error:
            self._send(503, {"status": "unavailable", "error": str(error)})

    def do_POST(self) -> None:  # noqa: N802
        routes = {
            "/v1/upsert": self.server.store.upsert,
            "/v1/delete": self.server.store.delete,
            "/v1/reset": self.server.store.reset,
            "/v1/search": self.server.store.search,
            "/v1/health": self.server.store.health,
        }
        operation = routes.get(self.path)
        if operation is None:
            self._send(404, {"error": "not_found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0 or size > MAX_BODY_BYTES:
                raise RequestError("request body is too large")
            value = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(value, dict):
                raise RequestError("request body must be an object")
            self._send(200, operation(value))
        except (RequestError, json.JSONDecodeError, ValueError) as error:
            self._send(400, {"error": "invalid_request", "detail": str(error)})
        except Exception as error:
            self._send(500, {"error": "vector_backend_error", "detail": str(error)})

    def log_message(self, format: str, *args: Any) -> None:
        print(json.dumps({"level": "info", "message": format % args}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    data_root = Path(os.environ["AI2APPS_DATA_ROOT"]) / "lancedb"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.store = Store(data_root)
    server.serve_forever()


if __name__ == "__main__":
    main()
