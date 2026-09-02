#!/usr/bin/env python3
"""Verify native direct-L1 writes against a real expert-major record."""

from __future__ import annotations

import argparse
import json

import mlx.core as mx
import numpy as np

from omlx.cache.moe_expert_store import ExpertMajorStore
from omlx.custom_kernels.glm_moe_dsa import fast as glm_fast


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("store")
    parser.add_argument("--experts", nargs=2, type=int, default=(7, 193))
    parser.add_argument("--slots", nargs=2, type=int, default=(3, 0))
    parser.add_argument("--capacity", type=int, default=8)
    parser.add_argument("--io-workers", type=int, default=2)
    args = parser.parse_args()

    symbols = glm_fast.native_symbols()
    if "preadv_fused_experts" not in symbols:
        raise RuntimeError("native direct expert loader is unavailable")
    if len(set(args.experts)) != 2 or len(set(args.slots)) != 2:
        raise ValueError("experts and slots must each contain two distinct values")
    if min(args.slots) < 0 or max(args.slots) >= args.capacity:
        raise ValueError("physical slots must fit within capacity")

    dtype_map = {
        "U8": mx.uint8,
        "U32": mx.uint32,
        "F16": mx.float16,
        "BF16": mx.bfloat16,
    }
    with ExpertMajorStore(args.store) as store:
        arrays = [
            mx.zeros((args.capacity, *tensor.shape), dtype=dtype_map[tensor.dtype])
            for tensor in store.tensors
        ]
        mx.eval(*arrays)
        mx.synchronize()
        loaded = glm_fast.preadv_expert_segments(
            store.fileno(),
            store.data_offset,
            store.record_bytes,
            args.experts,
            args.slots,
            *arrays,
            io_workers=args.io_workers,
        )
        mx.synchronize()
        if loaded != len(args.experts) * store.record_bytes:
            raise RuntimeError("native loader returned an invalid byte count")

        comparisons = 0
        for expert_id, slot in zip(args.experts, args.slots, strict=True):
            record = store.read(expert_id)
            for array, (layout, expected) in zip(
                arrays, store.tensor_views(record), strict=True
            ):
                actual_u8 = array[slot].view(mx.uint8).reshape((-1,))
                expected_u8 = mx.array(np.frombuffer(expected, dtype=np.uint8))
                if not bool(mx.array_equal(actual_u8, expected_u8).item()):
                    raise RuntimeError(
                        f"tensor mismatch: expert={expert_id} slot={slot} "
                        f"tensor={layout.name}"
                    )
                comparisons += 1

        print(
            json.dumps(
                {
                    "store": str(store.path),
                    "variant": store.variant,
                    "experts": args.experts,
                    "slots": args.slots,
                    "segments": len(store.tensors),
                    "comparisons": comparisons,
                    "loaded_bytes": loaded,
                    "exact": True,
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
