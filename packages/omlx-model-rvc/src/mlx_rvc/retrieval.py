"""MLX-native exact retrieval used instead of a runtime FAISS dependency."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class RetrievalResult:
    features: Any
    indices: Any
    squared_distances: Any


def _validate_shapes(query: Any, vectors: Any, k: int) -> None:
    if query.ndim != 2 or vectors.ndim != 2:
        raise ValueError("query and retrieval vectors must be rank-2")
    if query.shape[1] != vectors.shape[1]:
        raise ValueError("query and retrieval vectors must have the same feature width")
    if not 1 <= k <= vectors.shape[0]:
        raise ValueError("k must be between one and the retrieval vector count")


def retrieve_mlx(
    query: Any, vectors: Any, *, k: int = 8, epsilon: float = 1e-12
) -> RetrievalResult:
    """Reproduce RVC's inverse-squared-distance feature blending on Metal.

    RVC applies ``weight = (1 / squared_l2_distance) ** 2`` to FAISS results.
    The epsilon also makes exact vector matches deterministic instead of producing
    NaNs through infinity divided by infinity.
    """

    import mlx.core as mx

    _validate_shapes(query, vectors, k)
    query32 = query.astype(mx.float32)
    vectors32 = vectors.astype(mx.float32)
    distances = (
        mx.sum(mx.square(query32), axis=1, keepdims=True)
        + mx.sum(mx.square(vectors32), axis=1)[None, :]
        - 2.0 * (query32 @ vectors32.T)
    )
    distances = mx.maximum(distances, 0.0)
    indices = mx.argpartition(distances, kth=k - 1, axis=1)[:, :k]
    selected_distances = mx.take_along_axis(distances, indices, axis=1)
    selected_vectors = vectors32[indices]
    weights = mx.square(mx.reciprocal(mx.maximum(selected_distances, epsilon)))
    weights /= mx.sum(weights, axis=1, keepdims=True)
    features = mx.sum(selected_vectors * weights[:, :, None], axis=1)
    return RetrievalResult(
        features=features, indices=indices, squared_distances=selected_distances
    )


def retrieve_numpy(
    query: np.ndarray,
    vectors: np.ndarray,
    *,
    k: int = 8,
    epsilon: float = 1e-12,
) -> RetrievalResult:
    """CPU reference with the same semantics as :func:`retrieve_mlx`."""

    query32 = np.asarray(query, dtype=np.float32)
    vectors32 = np.asarray(vectors, dtype=np.float32)
    _validate_shapes(query32, vectors32, k)
    distances = (
        np.sum(np.square(query32), axis=1, keepdims=True)
        + np.sum(np.square(vectors32), axis=1)[None, :]
        - 2.0 * (query32 @ vectors32.T)
    )
    distances = np.maximum(distances, 0.0)
    indices = np.argpartition(distances, kth=k - 1, axis=1)[:, :k]
    selected_distances = np.take_along_axis(distances, indices, axis=1)
    selected_vectors = vectors32[indices]
    weights = np.square(1.0 / np.maximum(selected_distances, epsilon))
    weights /= np.sum(weights, axis=1, keepdims=True)
    features = np.sum(selected_vectors * weights[:, :, None], axis=1)
    return RetrievalResult(
        features=features, indices=indices, squared_distances=selected_distances
    )


def blend_retrieved(original: Any, retrieved: Any, rate: float) -> Any:
    if not 0.0 <= rate <= 1.0:
        raise ValueError("retrieval rate must be between zero and one")
    if original.shape != retrieved.shape:
        raise ValueError("original and retrieved features must have the same shape")
    return retrieved * rate + original * (1.0 - rate)
