"""Lazy bridge from built-in Knowledge Core to installable RAG Packages."""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import uuid
from contextlib import suppress
from contextvars import ContextVar

from ai2apps.services import ServiceRepository

from .backends import (
    ServiceEmbeddingProvider,
    ServiceEndpoint,
    ServiceVectorIndexBackend,
)
from .indexer import KnowledgeVectorIndexer
from .profiles import RetrievalProfile
from .retrieval import HybridKnowledgeRetriever
from .store import KnowledgeStore

EMBEDDING_MODEL_ID = "ai2apps.model.multilingual-e5-small/default"
EMBEDDING_DIMENSION = 384
INDEX_GENERATION = "lancedb_e5_small_5030c762_v1"
CUDA_EMBEDDING_MODEL_ID = "ai2apps.model.multilingual-e5-small-cuda/default"
CUDA_INDEX_GENERATION = "lancedb_e5_small_cuda_614241f6_fp32_v1"
logger = logging.getLogger(__name__)
_search_principal = ContextVar("knowledge_search_principal", default=None)


class _HostKnowledgeRetriever(HybridKnowledgeRetriever):
    def search(self, principal, query, **options):
        token = _search_principal.set(principal)
        try:
            return super().search(principal, query, **options)
        finally:
            _search_principal.reset(token)



class KnowledgePackageRuntime:
    """Own reusable clients and cursor state without importing native libraries."""

    def __init__(
        self,
        store: KnowledgeStore,
        services: ServiceRepository,
        *,
        runtime=None,
        embedding_backend: str | None = None,
    ) -> None:
        backend = embedding_backend or ("cuda" if sys.platform == "linux" else "mlx")
        if backend not in {"mlx", "cuda"}:
            raise ValueError("Unsupported Knowledge embedding backend")
        self.embedding_model_id = CUDA_EMBEDDING_MODEL_ID if backend == "cuda" else EMBEDDING_MODEL_ID
        generation = CUDA_INDEX_GENERATION if backend == "cuda" else INDEX_GENERATION
        embedding_endpoint = ServiceEndpoint(
            services, self.embedding_model_id.rsplit("/", 1)[0]
        )
        vector_endpoint = ServiceEndpoint(services, "ai2apps.knowledge-vector.lancedb")
        query_embedding = ServiceEmbeddingProvider(
            embedding_endpoint,
            model_id=self.embedding_model_id,
            dimension=EMBEDDING_DIMENSION,
            input_type="query",
            request_json=self._embedding_request if backend == "cuda" else None,
        )
        passage_embedding = query_embedding.for_passages()
        vector = ServiceVectorIndexBackend(
            vector_endpoint,
            generation=generation,
            dimension=EMBEDDING_DIMENSION,
        )
        profile = RetrievalProfile.hybrid(
            vector_backend="lancedb-package",
            embedding_model_id=self.embedding_model_id,
            embedding_dimension=EMBEDDING_DIMENSION,
        )
        self.indexer = KnowledgeVectorIndexer(
            store,
            vector,
            passage_embedding,
            profile_id=profile.id,
        )
        self.retriever = _HostKnowledgeRetriever(
            store, vector, query_embedding, profile=profile
        )
        self.runtime = runtime
        self._worker_lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._worker: asyncio.Task[None] | None = None
        self._scheduled = False
        self._closing = False
        self._phase = "idle"

    def _embedding_request(self, body):
        from ai2apps.model_invocation import ModelInvocationContext
        invocations = getattr(self.runtime, "model_invocations", None)
        if invocations is None or self._loop is None:
            raise RuntimeError("Knowledge model gateway is unavailable")
        principal = _search_principal.get()
        context = None if principal is None else ModelInvocationContext.from_principal(
            principal, session_id="knowledge:search", consumer_app_id="ai2apps.knowledge"
        )
        return invocations.invoke_sync_json(
            self._loop, self.embedding_model_id, "embeddings", body, context=context
        )

    async def startup(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._closing = False
        status = self.indexer.status()
        if status.sequence < status.target_sequence:
            self.schedule_index()

    async def shutdown(self) -> None:
        self._closing = True
        with self._worker_lock:
            worker = self._worker
            phase = self._phase
        if worker is not None and not worker.done():
            # A function dispatched through asyncio.to_thread cannot be stopped by
            # cancelling its awaiting Task. Let an active indexing chunk finish so
            # its model lease remains valid; queued work is safe to cancel.
            if phase in {"scheduled", "queued"}:
                worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
        with self._worker_lock:
            self._worker = None
            self._scheduled = False
            self._phase = "idle"
        self._loop = None

    def schedule_index(self) -> bool:
        """Schedule one background indexing Attempt on the Host event loop."""

        with self._worker_lock:
            if self._closing or self._scheduled or (
                self._worker is not None and not self._worker.done()
            ):
                return False
            loop = self._loop
            if loop is None or loop.is_closed():
                return False
            self._scheduled = True
        loop.call_soon_threadsafe(self._start_index_task)
        return True

    def _start_index_task(self) -> None:
        with self._worker_lock:
            if self._closing:
                self._scheduled = False
                return
            if self._worker is not None and not self._worker.done():
                self._scheduled = False
                return
            self._worker = asyncio.create_task(
                self._run_index(), name="ai2apps-knowledge-index"
            )
            self._phase = "scheduled"
            self._scheduled = False
            self._worker.add_done_callback(self._index_done)

    def _index_done(self, task: asyncio.Task[None]) -> None:
        with self._worker_lock:
            if self._worker is task:
                self._worker = None
                self._phase = "idle"

    async def _run_index(self) -> None:
        try:
            invocations = getattr(self.runtime, "model_invocations", None)
            if invocations is None:
                raise RuntimeError("Model invocation service is unavailable")
            while not self._closing:
                with self._worker_lock:
                    self._phase = "queued"

                def admitted() -> None:
                    with self._worker_lock:
                        self._phase = "running"

                result = await invocations.run_background_sync(
                    self.embedding_model_id,
                    self.indexer.sync,
                    request_id=f"knowledge-index-{uuid.uuid4().hex}",
                    on_admitted=admitted,
                    **(
                        {
                            "context": invocations.context_for_actor(
                                "local",
                                session_id="knowledge:index",
                                consumer_app_id="ai2apps.knowledge",
                            )
                        }
                        if hasattr(invocations, "context_for_actor")
                        else {}
                    ),
                )
                status = await asyncio.to_thread(self.indexer.status)
                if (
                    result.changed_items == 0
                    or status.sequence >= status.target_sequence
                ):
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Knowledge vector background indexing failed")

    def status(self):
        return self.indexer.status()

    def retry(self) -> bool:
        return self.schedule_index()

    def rebuild(self) -> bool:
        self.indexer.reset()
        return self.schedule_index()

    def ready_retriever(self) -> HybridKnowledgeRetriever:
        """Return immediately; FTS5 covers changes while vectors catch up."""

        status = self.indexer.status()
        if status.sequence < status.target_sequence:
            self.schedule_index()
        return self.retriever
