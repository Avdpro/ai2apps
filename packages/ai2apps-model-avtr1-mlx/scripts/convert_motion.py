"""Convert the pinned authorized official TorchScript checkpoint offline."""

import argparse
import hashlib
import json
from pathlib import Path

REVISION = "4c9bd5550f2617d0409ac602f75378502f675731"
SOURCE_SHA256 = "c345fb1e84eabee3c247533b74e020f918eeec86febe5928fe16f8935572aed3"


def digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if digest(args.input) != SOURCE_SHA256:
        raise ValueError(
            "Checkpoint does not match the reviewed, pinned AVTR-1 artifact"
        )
    import torch
    from safetensors.torch import save_file

    model = torch.jit.load(str(args.input), map_location="cpu").eval()
    config = {}
    attributes = (
        "nfeats",
        "chunk_size",
        "past_size",
        "future_size",
        "latent_dim",
        "num_layers",
        "num_heads",
        "cond_feature_dim",
        "d_model",
        "nhead",
        "inner_dim",
        "use_gate",
        "eps",
        "dim",
        "split_sizes",
        "normalized_shape",
    )
    for name, module in model.named_modules():
        config[name] = {
            "type": module.original_name,
            **{key: getattr(module, key) for key in attributes if hasattr(module, key)},
        }
    args.output.mkdir(parents=True, exist_ok=True)
    config_path = args.output / "model_config.json"
    weights_path = args.output / "motion.safetensors"
    config_path.write_text(json.dumps(config, indent=2))
    weights = {
        k: v.detach().contiguous().clone() for k, v in model.state_dict().items()
    }
    save_file(weights, str(weights_path))
    receipt = {
        "source_repo": "avaturn-live/avtr-1",
        "source_revision": REVISION,
        "source_sha256": SOURCE_SHA256,
        "weights_sha256": digest(weights_path),
        "config_sha256": digest(config_path),
        "tensors": len(weights),
    }
    (args.output / "conversion.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
