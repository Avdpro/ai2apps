#!/usr/bin/env python3
"""Export the official GhostV2 generator and CVLFace encoder to ONNX."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
import torch.nn as nn
from safetensors.torch import load_file


class GeneratorOutput(nn.Module):
    def __init__(self, model: nn.Module):
        super().__init__()
        self.model = model

    def forward(self, target: torch.Tensor, identity: torch.Tensor) -> torch.Tensor:
        return self.model(target, identity)[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--opset", type=int, default=16)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(args.repo.resolve()))
    from CVLFace import get_vit_model  # noqa: PLC0415
    from Ghost.AEI_Net import AEI_Net  # noqa: PLC0415

    generator = AEI_Net("unet", num_blocks=2, c_id=512, align_corners=True)
    generator.load_state_dict(
        {
            key.removeprefix("_orig_mod."): value
            for key, value in load_file(
                args.repo / "weights/GhostV2/G_unet_2blocks.safetensors"
            ).items()
        },
        strict=True,
    )
    generator.eval()
    identity = get_vit_model(
        str(
            args.repo
            / "weights/CVLFace/cvlface_adaface_vit_base_webface4m.safetensors"
        )
    ).eval()

    dynamic = {"image": {0: "batch"}, "embedding": {0: "batch"}}
    torch.onnx.export(
        identity,
        (torch.zeros(1, 3, 112, 112),),
        args.output / "ghostv2_cvlface.onnx",
        input_names=["image"],
        output_names=["embedding"],
        dynamic_axes=dynamic,
        opset_version=args.opset,
        do_constant_folding=True,
        dynamo=False,
    )
    torch.onnx.export(
        GeneratorOutput(generator),
        (torch.zeros(1, 3, 256, 256), torch.zeros(1, 512)),
        args.output / "ghostv2_generator.onnx",
        input_names=["target", "identity"],
        output_names=["image"],
        dynamic_axes={
            "target": {0: "batch"},
            "identity": {0: "batch"},
            "image": {0: "batch"},
        },
        opset_version=args.opset,
        do_constant_folding=True,
        dynamo=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
