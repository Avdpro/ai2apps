#!/usr/bin/env python3
"""Offline conversion of the pinned avatar project's pure-tensor checkpoints.

Developer tool only: production inference reads safetensors and never calls
this script. No remote-code execution and no automatic file downloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if source == output:
        parser.error("Input and output must differ")
    if output.suffix != ".safetensors":
        parser.error("Output must be a safetensors file")
    receipt = output.with_suffix(".conversion.json")
    if not args.force and (output.exists() or receipt.exists()):
        parser.error("Output exists; use --force to replace")
    import torch
    from safetensors.torch import save_file

    state = torch.load(source, map_location="cpu", weights_only=True)
    if (
        not isinstance(state, dict)
        or not state
        or not all(
            isinstance(k, str) and isinstance(v, torch.Tensor) for k, v in state.items()
        )
    ):
        raise ValueError(
            "Expected the reviewed flat string-to-Tensor checkpoint format"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=output.parent, prefix="." + output.name, suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
    try:
        save_file(
            {k: v.contiguous() for k, v in state.items()},
            str(temporary),
            metadata={"source_revision": args.source_revision},
        )
        record = {
            "source": str(source),
            "source_revision": args.source_revision,
            "source_sha256": sha256(source),
            "output": str(output),
            "output_sha256": sha256(temporary),
            "output_bytes": temporary.stat().st_size,
            "tensor_count": len(state),
            "conversion": "unchanged keys and numerical dtype; contiguous storage only",
            "torch_version": torch.__version__,
        }
        os.replace(temporary, output)
        receipt.write_text(json.dumps(record, indent=2) + "\n")
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
