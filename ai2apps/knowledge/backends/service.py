"""Host-side clients for isolated Knowledge Runtime Packages."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any

from ai2apps.services import ServiceInstanceStatus, ServiceRepository, ServiceStatus

from .protocol import (
    BackendHealth,
    VectorBackendError,
    VectorBackendUnavailableError,
    VectorRecord,
    VectorSearchCandidate,
    VectorSearchRequest,
)

MAX_RESPONSE_BYTES = 64 * 1024 * 1024


class ServiceEndpoint:
    """Resolve only an enabled, running local Service instance."""

    def __init__(self, services: ServiceRepository, service_key: str) -> None:
        self.services = services
        self.service_key = service_key

    def __call__(self) -> str:
        try:
            service = self.services.get_service(self.service_key)
            instance = self.services.get_instance_for_service(service.id)
        except Exception as error:
            raise VectorBackendUnavailableError(
                f"Knowledge component is not installed: {self.service_key}"
            ) from error
        if service.status is not ServiceStatus.ENABLED or instance.status not in {
            ServiceInstanceStatus.RUNNING,
            ServiceInstanceStatus.DEGRADED,
        }:
            raise VectorBackendUnavailableError(
                f"Knowledge component is not running: {self.service_key}"
            )
        if not instance.endpoint:
            raise VectorBackendUnavailableError(
                f"Knowledge component has no endpoint: {self.service_key}"
            )
        return instance.endpoint.rstrip("/")


def _post(
    endpoint: Callable[[], str], path: str, body: dict[str, Any]
) -> dict[str, Any]:
    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    request = urllib.request.Request(
        endpoint() + path,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, urllib.error.URLError) as error:
        raise VectorBackendUnavailableError(
            f"Knowledge Runtime request failed: {error}"
        ) from error
    if len(content) > MAX_RESPONSE_BYTES:
        raise VectorBackendError("Knowledge Runtime response exceeded its limit")
    try:
        value = json.loads(content)
    except json.JSONDecodeError as error:
        raise VectorBackendError("Knowledge Runtime returned invalid JSON") from error
    if not isinstance(value, dict):
        raise VectorBackendError("Knowledge Runtime response must be an object")
    return value


class ServiceEmbeddingProvider:
    def __init__(
        self,
        endpoint: Callable[[], str],
        *,
        model_id: str,
        dimension: int,
        input_type: str = "query",
    ) -> None:
        self.endpoint = endpoint
        self._model_id = model_id
        self._dimension = dimension
        self.input_type = input_type

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    def for_passages(self) -> ServiceEmbeddingProvider:
        return ServiceEmbeddingProvider(
            self.endpoint,
            model_id=self.model_id,
            dimension=self.dimension,
            input_type="passage",
        )

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        value = _post(
            self.endpoint,
            "/v1/embeddings",
            {
                "model": self.model_id,
                "input": list(texts),
                "input_type": self.input_type,
            },
        )
        data = value.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise VectorBackendError("Embedding Service returned an invalid batch")
        ordered = sorted(data, key=lambda item: item.get("index", -1))
        result = []
        for item in ordered:
            vector = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(vector, list) or len(vector) != self.dimension:
                raise VectorBackendError("Embedding Service returned an invalid vector")
            result.append(tuple(float(number) for number in vector))
        return tuple(result)


class ServiceVectorIndexBackend:
    def __init__(
        self,
        endpoint: Callable[[], str],
        *,
        generation: str,
        dimension: int,
    ) -> None:
        self.endpoint = endpoint
        self._generation = generation
        self.dimension = dimension

    @property
    def generation(self) -> str:
        return self._generation

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        if not records:
            return
        _post(
            self.endpoint,
            "/v1/upsert",
            {
                "generation": self.generation,
                "dimension": self.dimension,
                "records": [
                    {
                        "chunk_id": record.chunk_id,
                        "item_id": record.item_id,
                        "installation_id": record.installation_id,
                        "owner_user_id": record.owner_user_id,
                        "visibility": record.visibility,
                        "bucket_ids": list(record.bucket_ids),
                        "text": record.text,
                        "vector": list(record.vector),
                    }
                    for record in records
                ],
            },
        )

    def delete_items(self, item_ids: Sequence[str]) -> None:
        if item_ids:
            _post(
                self.endpoint,
                "/v1/delete",
                {"generation": self.generation, "item_ids": list(item_ids)},
            )

    def reset(self) -> None:
        _post(self.endpoint, "/v1/reset", {"generation": self.generation})

    def search(self, request: VectorSearchRequest) -> tuple[VectorSearchCandidate, ...]:
        value = _post(
            self.endpoint,
            "/v1/search",
            {
                "generation": self.generation,
                "dimension": self.dimension,
                "vector": list(request.vector),
                "installation_id": request.installation_id,
                "actor_user_id": request.actor_user_id,
                # Membership edits advance the authoritative Knowledge change
                # log. This prefilter improves recall for small buckets; Core
                # still rechecks every candidate against SQLite.
                "bucket_ids": list(request.bucket_ids),
                "limit": request.limit,
            },
        )
        items = value.get("items")
        if not isinstance(items, list):
            raise VectorBackendError("Vector Service returned invalid candidates")
        return tuple(
            VectorSearchCandidate(
                chunk_id=str(item["chunk_id"]),
                item_id=str(item["item_id"]),
                text=str(item["text"]),
                distance=float(item["distance"]),
            )
            for item in items
            if isinstance(item, dict)
        )

    def count(self) -> int:
        value = _post(self.endpoint, "/v1/health", {"generation": self.generation})
        return int(value.get("count") or 0)

    def health(self) -> BackendHealth:
        try:
            value = _post(self.endpoint, "/v1/health", {"generation": self.generation})
        except VectorBackendError as error:
            return BackendHealth(
                status="unavailable",
                backend="lancedb",
                generation=self.generation,
                detail=str(error),
            )
        return BackendHealth(
            status=str(value.get("status", "unavailable")),
            backend="lancedb",
            generation=self.generation,
            detail=f"{int(value.get('count') or 0)} chunks",
        )
