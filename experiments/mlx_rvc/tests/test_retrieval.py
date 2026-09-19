from __future__ import annotations

import numpy as np
import pytest

from experiments.mlx_rvc.retrieval import blend_retrieved, retrieve_mlx, retrieve_numpy


def test_numpy_retrieval_handles_exact_match_without_nan():
    vectors = np.eye(4, dtype=np.float32)
    result = retrieve_numpy(vectors[:1], vectors, k=2)

    assert np.isfinite(result.features).all()
    np.testing.assert_allclose(result.features, vectors[:1], atol=1e-6)


def test_mlx_retrieval_matches_cpu_reference():
    mx = pytest.importorskip("mlx.core")
    rng = np.random.default_rng(7)
    query = rng.normal(size=(5, 8)).astype(np.float32)
    vectors = rng.normal(size=(24, 8)).astype(np.float32)
    expected = retrieve_numpy(query, vectors, k=8)
    actual = retrieve_mlx(mx.array(query), mx.array(vectors), k=8)
    mx.eval(actual.features)

    # Accelerate the exact L2 search with q² + v² - 2qv. Accelerate/BLAS
    # accumulation order differs slightly between MLX and NumPy, and RVC's
    # inverse-square weighting amplifies those harmless distance roundoffs.
    np.testing.assert_allclose(
        np.asarray(actual.features), expected.features, rtol=3e-2, atol=2e-3
    )


def test_blend_validates_rate_and_shape():
    original = np.zeros((2, 3), dtype=np.float32)
    retrieved = np.ones((2, 3), dtype=np.float32)
    np.testing.assert_allclose(blend_retrieved(original, retrieved, 0.25), 0.25)
    with pytest.raises(ValueError, match="between"):
        blend_retrieved(original, retrieved, 1.1)
