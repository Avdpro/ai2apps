"""Versionable hybrid retrieval orchestration for Knowledge."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ai2apps.identity import RequestPrincipal

from .backends.protocol import (
    EmbeddingProvider,
    VectorBackendError,
    VectorIndexBackend,
    VectorSearchRequest,
)
from .models import KnowledgeScope, KnowledgeSearchHit
from .profiles import RetrievalMode, RetrievalProfile
from .store import KnowledgeStore


@dataclass(frozen=True, slots=True)
class RetrievalDiagnostics:
    profile_id: str
    mode: str
    lexical_candidates: int
    semantic_candidates: int
    semantic_error: str | None = None


def _looks_like_prose(value: str) -> bool:
    """Distinguish article prose from menus and other low-signal boilerplate."""

    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if len(lines) >= 20:
        short_line_ratio = sum(len(line) < 35 for line in lines) / len(lines)
        if short_line_ratio >= 0.85:
            return False
    return len(re.findall(r"[.!?。！？](?:\s|$)", value)) >= 2


class HybridKnowledgeRetriever:
    """Fuse FTS5 and semantic ranks while SQLite remains final authority."""

    def __init__(
        self,
        store: KnowledgeStore,
        vector_backend: VectorIndexBackend,
        embedding_provider: EmbeddingProvider,
        *,
        profile: RetrievalProfile | None = None,
    ) -> None:
        profile = profile or RetrievalProfile.hybrid(
            vector_backend=type(vector_backend).__name__,
            embedding_model_id=embedding_provider.model_id,
            embedding_dimension=embedding_provider.dimension,
        )
        if profile.mode is not RetrievalMode.HYBRID:
            raise ValueError("HybridKnowledgeRetriever requires a hybrid profile")
        if profile.embedding_model_id != embedding_provider.model_id:
            raise ValueError("retrieval profile embedding model differs from provider")
        if profile.embedding_dimension != embedding_provider.dimension:
            raise ValueError(
                "retrieval profile embedding dimension differs from provider"
            )
        self.store = store
        self.vector_backend = vector_backend
        self.embedding_provider = embedding_provider
        self.profile = profile

    def search(
        self,
        principal: RequestPrincipal,
        query: str,
        *,
        scope: KnowledgeScope | None = None,
        kind: str | None = None,
        tags: Sequence[str] = (),
        bucket_ids: Sequence[str] = (),
        source_app_id: str | None = None,
        source_session_id: str | None = None,
        source_after: datetime | None = None,
        source_before: datetime | None = None,
        limit: int = 20,
    ) -> tuple[tuple[KnowledgeSearchHit, ...], RetrievalDiagnostics]:
        fetch_limit = min(100, max(limit * 3, 20))
        lexical = self.store.search(
            principal,
            query,
            scope=scope,
            kind=kind,
            tags=tags,
            bucket_ids=bucket_ids,
            source_app_id=source_app_id,
            source_session_id=source_session_id,
            source_after=source_after,
            source_before=source_before,
            limit=fetch_limit,
        )
        try:
            vectors = self.embedding_provider.embed((query,))
            if len(vectors) != 1:
                raise VectorBackendError("embedding provider returned an invalid batch")
            semantic = self.vector_backend.search(
                VectorSearchRequest(
                    vector=vectors[0],
                    installation_id=principal.installation_id,
                    actor_user_id=principal.actor_user_id,
                    bucket_ids=tuple(bucket_ids),
                    limit=fetch_limit,
                )
            )
        except Exception as error:
            return lexical[:limit], RetrievalDiagnostics(
                profile_id=self.profile.id,
                mode="fts5",
                lexical_candidates=len(lexical),
                semantic_candidates=0,
                semantic_error=str(error),
            )

        hits_by_id = {hit.item.id: hit for hit in lexical}
        lexical_ids = set(hits_by_id)
        scores: dict[str, float] = {}
        for rank, hit in enumerate(lexical, 1):
            scores[hit.item.id] = scores.get(hit.item.id, 0.0) + (
                self.profile.lexical_weight / (self.profile.rrf_constant + rank)
            )
        authorized_semantic = 0
        for rank, candidate in enumerate(semantic, 1):
            hit = self.store.hydrate_semantic_hit(
                principal,
                candidate.item_id,
                excerpt=candidate.text,
                distance=candidate.distance,
                scope=scope,
                kind=kind,
                tags=tags,
                bucket_ids=bucket_ids,
                source_app_id=source_app_id,
                source_session_id=source_session_id,
                source_after=source_after,
                source_before=source_before,
            )
            if hit is None:
                continue
            authorized_semantic += 1
            existing = hits_by_id.get(candidate.item_id)
            if existing is None:
                hits_by_id[candidate.item_id] = hit
            elif (
                candidate.item_id not in lexical_ids
                and not _looks_like_prose(existing.excerpt)
                and _looks_like_prose(hit.excerpt)
            ):
                # A long imported page can contribute many vector chunks. The
                # nearest one is sometimes a brand/category menu; keep scanning
                # the ranked candidates until substantive prose from that same
                # authorized item appears.
                hits_by_id[candidate.item_id] = hit
            scores[candidate.item_id] = scores.get(candidate.item_id, 0.0) + (
                self.profile.semantic_weight / (self.profile.rrf_constant + rank)
            )
        ordered = sorted(scores, key=lambda item_id: (-scores[item_id], item_id))
        fused = tuple(
            KnowledgeSearchHit(
                item=hits_by_id[item_id].item,
                excerpt=hits_by_id[item_id].excerpt,
                rank=scores[item_id],
                tags=hits_by_id[item_id].tags,
                source_facets=hits_by_id[item_id].source_facets,
                location=hits_by_id[item_id].location,
            )
            for item_id in ordered[:limit]
        )
        return fused, RetrievalDiagnostics(
            profile_id=self.profile.id,
            mode="hybrid",
            lexical_candidates=len(lexical),
            semantic_candidates=authorized_semantic,
        )
