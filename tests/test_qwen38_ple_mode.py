from __future__ import annotations

from pathlib import Path

import pytest

from omlx.patches.mlx_vlm_qwen4_exp_compat import (
    apply_mlx_vlm_qwen4_exp_compat_patch,
)

apply_mlx_vlm_qwen4_exp_compat_patch()

from mlx_vlm.models.qwen4_exp.language import resolve_ple_runtime_mode  # noqa: E402
from omlx.patches.qwen38_next_cache.runtime import (  # noqa: E402
    _is_checkpoint_safetensor,
)


def test_qwen4_ple_disabled_is_explicit_only():
    assert (
        resolve_ple_runtime_mode(
            "disabled", checkpoint_bytes=100, physical_memory=100
        )
        == "disabled"
    )
    assert (
        resolve_ple_runtime_mode("auto", checkpoint_bytes=80, physical_memory=100)
        == "mmap"
    )
    assert (
        resolve_ple_runtime_mode("auto", checkpoint_bytes=60, physical_memory=100)
        == "resident"
    )


def test_qwen4_ple_rejects_implicit_off_aliases():
    with pytest.raises(ValueError):
        resolve_ple_runtime_mode("off", checkpoint_bytes=100, physical_memory=100)


def test_qwen4_prepared_symlink_is_matched_by_model_view_path(tmp_path):
    model = tmp_path / "models" / "owner" / "model"
    blobs = tmp_path / "hub" / "blobs"
    model.mkdir(parents=True)
    blobs.mkdir(parents=True)
    blob = blobs / "digest"
    blob.write_bytes(b"weights")
    shard = model / "model-00001.safetensors"
    shard.symlink_to(blob)

    assert shard.resolve().parent == blobs
    assert _is_checkpoint_safetensor(shard, model.resolve())
