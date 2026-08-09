from __future__ import annotations

import json

import mlx.core as mx
import pytest

from omlx.cache.moe_expert_store import ExpertMajorStore, create_expert_major_store


def test_create_and_read_fixed_expert_records(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(bytes(4096) + b"abcd" + b"12" + b"WXYZ" + b"34")
    manifest = {
        "layers": {
            "3": {
                "file": "source.bin",
                "expert_count": 2,
                "expert_bytes": 6,
                "experts": [
                    {
                        "tensors": [
                            {
                                "name": "w",
                                "absolute_offset": 4096,
                                "nbytes": 4,
                                "dtype": "U32",
                                "shape": [1],
                            },
                            {
                                "name": "s",
                                "absolute_offset": 4100,
                                "nbytes": 2,
                                "dtype": "U8",
                                "shape": [2],
                            },
                        ]
                    },
                    {
                        "tensors": [
                            {
                                "name": "w",
                                "absolute_offset": 4102,
                                "nbytes": 4,
                                "dtype": "U32",
                                "shape": [1],
                            },
                            {
                                "name": "s",
                                "absolute_offset": 4106,
                                "nbytes": 2,
                                "dtype": "U8",
                                "shape": [2],
                            },
                        ]
                    },
                ],
            }
        }
    }
    manifest_path = tmp_path / "offsets.json"
    manifest_path.write_text(json.dumps(manifest))

    # Production MXFP4 records are page aligned; relax the fixture via padding.
    manifest["layers"]["3"]["expert_bytes"] = 4096
    for expert in manifest["layers"]["3"]["experts"]:
        expert["tensors"].append(
            {
                "name": "pad",
                "absolute_offset": 0,
                "nbytes": 4090,
                "dtype": "U8",
                "shape": [4090],
            }
        )
    manifest_path.write_text(json.dumps(manifest))
    output = tmp_path / "layer-003.moe"
    result = create_expert_major_store(manifest_path, 3, output)

    assert result["record_bytes"] == 4096
    with ExpertMajorStore(output) as store:
        assert store.layer == 3
        assert store.read(0)[:6] == b"abcd12"
        staging = store.allocate_staging()
        assert bytes(store.read_into(1, staging)[:6]) == b"WXYZ34"
        assert bytes(store.mmap_view(0)[:6]) == b"abcd12"
        views = list(store.tensor_views(store.read(1)))
        assert [layout.name for layout, _ in views] == ["w", "s", "pad"]
        mlx_views = store.mlx_tensor_views(store.read(0), copy_record=True)
        mx.eval(*mlx_views.values())
        assert mlx_views["w"].dtype == mx.uint32
        assert mlx_views["w"].shape == (1,)
        assert mlx_views["s"].shape == (2,)


def test_rejects_existing_output(tmp_path):
    output = tmp_path / "exists.moe"
    output.write_bytes(b"x")
    with pytest.raises(FileExistsError):
        create_expert_major_store(tmp_path / "missing.json", 0, output)


def test_wraps_dmoe_fixed_stride_qwen_layer(tmp_path):
    source = tmp_path / "layer-000.bin"
    first = b"a" * 4096
    second = b"b" * 4096
    source.write_bytes(first + second)
    manifest = {
        "layers": {
            "0": {
                "file": source.name,
                "expert_count": 2,
                "expert_bytes": 4096,
                "expert_stride": 4096,
                "tensors": [
                    {
                        "name": "gate_proj.weight",
                        "relative_offset": 0,
                        "nbytes": 2048,
                        "dtype": "U32",
                        "shape": [512],
                    },
                    {
                        "name": "gate_proj.scales",
                        "relative_offset": 2048,
                        "nbytes": 2048,
                        "dtype": "BF16",
                        "shape": [1024],
                    },
                ],
            }
        }
    }
    manifest_path = tmp_path / "offset-manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    output = tmp_path / "layer-000.moe"
    result = create_expert_major_store(manifest_path, 0, output)

    assert result["source_layout"] == "fixed-stride"
    with ExpertMajorStore(output) as store:
        assert store.num_experts == 2
        assert store.read(0) == first
        assert store.read(1) == second
        assert [item.name for item in store.tensors] == [
            "gate_proj.weight",
            "gate_proj.scales",
        ]
