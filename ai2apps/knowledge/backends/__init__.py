"""Replaceable derived-index backends for the Knowledge Core."""

from .protocol import (
    BackendHealth,
    VectorBackendError,
    VectorBackendUnavailableError,
    VectorRecord,
    VectorSearchCandidate,
    VectorSearchRequest,
)
from .service import (
    ServiceEmbeddingProvider,
    ServiceEndpoint,
    ServiceVectorIndexBackend,
)

__all__ = [
    "BackendHealth",
    "VectorBackendError",
    "VectorBackendUnavailableError",
    "ServiceEmbeddingProvider",
    "ServiceEndpoint",
    "ServiceVectorIndexBackend",
    "VectorRecord",
    "VectorSearchCandidate",
    "VectorSearchRequest",
]
