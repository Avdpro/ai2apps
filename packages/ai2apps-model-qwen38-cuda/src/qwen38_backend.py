"""Pinned Qwen3.8: native NVFP4 MLP, remaining FP8 projections in BF16."""
import gc
import json
from pathlib import Path


def load(checkpoint):
    import torch
    from accelerate.utils import set_module_tensor_to_device
    from transformers import AutoModelForImageTextToText, AutoProcessor, CompressedTensorsConfig, GenerationConfig
    from compressed_tensors.quantization.lifecycle.helpers import disable_quantization
    from ai2apps.model_worker.native_nvfp4 import NativeNVFP4Linear
    from qwen38_27b_compat import apply_qwen38_swish

    if torch.cuda.get_device_capability() != (12, 1):
        raise RuntimeError("Qwen3.8 native NVFP4 requires GB10 SM121")
    checkpoint = Path(checkpoint)
    config = json.loads((checkpoint / "config.json").read_text())
    index = json.loads((checkpoint / "model.safetensors.index.json").read_text())["weight_map"]
    paths = {name.removesuffix(".weight_packed") for name in index
             if name.endswith(".weight_packed") and not name.startswith("mtp.")}
    expected = {f"model.language_model.layers.{i}.mlp.{projection}"
                for i in range(56) for projection in ("gate_proj", "up_proj", "down_proj")}
    if paths != expected:
        raise RuntimeError("Checkpoint does not match the validated 168 NVFP4 MLP projections")
    quantization = {**config["quantization_config"], "dequantize": False,
                    "use_optimized_inference": False}
    model = AutoModelForImageTextToText.from_pretrained(checkpoint, local_files_only=True,
        trust_remote_code=False, dtype=torch.bfloat16, device_map={"": "cuda:0"},
        quantization_config=CompressedTensorsConfig(**quantization), attn_implementation="sdpa")
    for path in sorted(paths):
        original = model.get_submodule(path)
        native = NativeNVFP4Linear(original.weight_packed, original.weight_scale,
                                  original.weight_global_scale, original.input_global_scale)
        parent, child = path.rsplit(".", 1)
        setattr(model.get_submodule(parent), child, native)
        del original
    # Only the remaining FP8 modules retain a scheme for the official decompressor.
    model.hf_quantizer.compressor.decompress_model(model=model)
    model.apply(disable_quantization)
    for name, buffer in list(model.named_buffers()):
        if buffer.device.type == "meta":
            raise RuntimeError(f"Uninitialized buffer: {name}")
        if buffer.device.type != "cuda":
            set_module_tensor_to_device(model, name, "cuda", value=buffer)
    apply_qwen38_swish(model, config)
    model.generation_config = GenerationConfig.from_pretrained(checkpoint, local_files_only=True)
    processor = AutoProcessor.from_pretrained(checkpoint, local_files_only=True,
        trust_remote_code=False, use_fast=False)
    gc.collect()
    torch.cuda.empty_cache()
    return model.eval(), processor
