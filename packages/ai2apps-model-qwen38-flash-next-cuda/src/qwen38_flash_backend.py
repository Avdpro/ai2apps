"""Bounded-memory correctness prototype for the exact MLX SSD checkpoint.

No expert replacement policy or performance claim: routed experts are read on
demand and discarded. PLE reads only requested affine-Q4 rows from disk.
"""
import bisect
import json
import os
from pathlib import Path
import struct

import torch
from torch import nn


def dequantize(weight, scales, biases):
    shifts = torch.arange(0, 32, 4, device=weight.device, dtype=torch.int64)
    q = ((weight.to(torch.int64)[..., None] >> shifts) & 15).flatten(-2).float()
    group = q.shape[-1] // scales.shape[-1]
    assert group == 32
    return (q * scales.float().repeat_interleave(group, -1)
            + biases.float().repeat_interleave(group, -1)).to(torch.bfloat16)


class TensorStore:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.index = json.loads((self.root / "model.safetensors.index.json").read_text())["weight_map"]
        self.headers = {}
        self.handles = {}
        for file in sorted(set(self.index.values())):
            path = (self.root / file).resolve(strict=True)
            path.relative_to(self.root)
            with path.open("rb") as stream:
                size = struct.unpack("<Q", stream.read(8))[0]
                assert size < 64 * 1024 * 1024
                self.headers[file] = (8 + size, json.loads(stream.read(size)))

    def read(self, file, offset, length):
        if file not in self.handles:
            path = (self.root / file).resolve(strict=True)
            path.relative_to(self.root)
            self.handles[file] = os.open(path, os.O_RDONLY)
        data = os.pread(self.handles[file], length, offset)
        if len(data) != length:
            raise IOError(f"Incomplete tensor read in {file}")
        return bytearray(data)

    def tensor(self, key, row=None):
        file = self.index[key]
        base, header = self.headers[file]
        item = header[key]
        dtype = {"BF16": torch.bfloat16, "F32": torch.float32, "F16": torch.float16,
                 "U32": torch.uint32, "I32": torch.int32, "I64": torch.int64}[item["dtype"]]
        shape = item["shape"]
        start, end = item["data_offsets"]
        if row is not None:
            assert 0 <= row < shape[0]
            length = (end - start) // shape[0]
            start += row * length
            end = start + length
            shape = shape[1:]
        return torch.frombuffer(self.read(file, base + start, end - start), dtype=dtype).reshape(shape)

    def weight(self, key):
        packed = self.tensor(key)
        scale_key = key[:-7] + ".scales" if key.endswith(".weight") else ""
        if scale_key not in self.index:
            return packed.to("cuda")
        scales = self.tensor(scale_key)
        biases = self.tensor(key[:-7] + ".biases")
        result = torch.empty((packed.shape[0], packed.shape[1] * 8), device="cuda", dtype=torch.bfloat16)
        for start in range(0, packed.shape[0], 256):
            end = start + 256
            result[start:end] = dequantize(packed[start:end].to("cuda"), scales[start:end].to("cuda"), biases[start:end].to("cuda"))
        return result

    def close(self):
        for handle in self.handles.values():
            os.close(handle)
        self.handles.clear()


class DiskEmbedding(nn.Module):
    def __init__(self, store, prefix):
        super().__init__()
        self.store, self.prefix = store, prefix
        self.weight = nn.Parameter(torch.empty(0, device="cuda", dtype=torch.bfloat16), requires_grad=False)
        self.ends = []
        rows = 0
        for shard in range(128):
            key = f"{prefix}.shard_{shard}.weight"
            file = store.index[key]
            rows += store.headers[file][1][key]["shape"][0]
            self.ends.append(rows)

    def forward(self, ids):
        unique, inverse = ids.reshape(-1).cpu().unique(return_inverse=True)
        triples = [[], [], []]
        for index in unique.tolist():
            shard = bisect.bisect_right(self.ends, index)
            assert shard < len(self.ends) and index >= 0
            row = index - (self.ends[shard - 1] if shard else 0)
            for target, field in zip(triples, ("weight", "scales", "biases")):
                target.append(self.store.tensor(f"{self.prefix}.shard_{shard}.{field}", row))
        decoded = dequantize(*(torch.stack(items).to("cuda") for items in triples))
        return decoded[inverse.to("cuda")].reshape(*ids.shape, decoded.shape[-1])


class DiskExperts(nn.Module):
    def __init__(self, store, metadata, layer):
        super().__init__()
        self.store, self.metadata, self.layer = store, metadata, layer

    def projection(self, expert, projection):
        parts = []
        for field, dtype in (("weight", torch.uint32), ("scales", torch.bfloat16), ("biases", torch.bfloat16)):
            entry = self.metadata[f"language_model.model.layers.{self.layer}.mlp.switch_mlp.{projection}.{field}"]
            assert 0 <= expert < entry["count"]
            raw = self.store.read(entry["file"], entry["offset"] + expert * entry["stride"], entry["row_bytes"])
            parts.append(torch.frombuffer(raw, dtype=dtype).reshape(entry["shape"][1:]).to("cuda"))
        return dequantize(*parts)

    def forward(self, hidden, indices, scores):
        output = torch.zeros_like(hidden)
        assert indices.shape[-1] == 10, "Keep the original Top-10 routing"
        for expert in indices.unique().tolist():
            rows, slots = torch.where(indices == expert)
            x = hidden[rows]
            gate = nn.functional.linear(x, self.projection(expert, "gate_proj"))
            up = nn.functional.linear(x, self.projection(expert, "up_proj"))
            value = nn.functional.linear(nn.functional.silu(gate) * up, self.projection(expert, "down_proj"))
            output.index_add_(0, rows, value * scores[rows, slots, None])
        return output


def load(root, *, batched_experts=False):
    from accelerate import init_empty_weights
    from transformers import AutoConfig, AutoModelForImageTextToText, GenerationConfig
    from transformers.models.qwen4_exp.modeling_qwen4_exp import Qwen4ExpTextRMSNorm
    config = AutoConfig.from_pretrained(root, local_files_only=True, trust_remote_code=False)
    assert config.model_type == "qwen4_exp" and config.text_config.num_experts_per_tok == 10
    assert config.text_config.output_gate_type == "sigmoid"
    config._attn_implementation = "sdpa"
    with init_empty_weights(include_buffers=False):
        model = AutoModelForImageTextToText.from_config(config, trust_remote_code=False, dtype=torch.bfloat16)
    store = TensorStore(root)
    external = json.loads((Path(root) / "external-tensors.json").read_text())
    # Match Mac's canonicalization of legacy direct-gamma RMSNorm weights.
    anchors = torch.stack([store.tensor(f"language_model.model.layers.{i}.attn_hyper_connection.hc_norm.weight").float().mean() for i in range(48)])
    median, vote = float(anchors.median()), float((anchors > .5).float().mean())
    recenter = vote >= .9 and .75 <= median <= 1.5
    assert recenter or (vote <= .1 and -.5 <= median <= .25), "Ambiguous RMSNorm centering"
    norms = {name + ".weight" for name, module in model.named_modules() if isinstance(module, Qwen4ExpTextRMSNorm)}
    expected = set(model.state_dict())
    loaded = set()
    for key in store.index:
        if key.endswith((".scales", ".biases")) or ".ngram_embedding.shard_" in key:
            continue
        target = key.replace("language_model.model.", "model.language_model.", 1)
        if target.startswith("language_model.lm_head."):
            target = target.replace("language_model.lm_head.", "lm_head.", 1)
        if target.startswith("vision_tower."):
            target = target.replace("vision_tower.", "model.visual.", 1)
        assert target in expected, target
        value = store.weight(key)
        if target.endswith(".conv1d.weight"):
            value = value.permute(0, 2, 1).contiguous()
        elif target == "model.visual.patch_embed.proj.weight":
            value = value.permute(0, 4, 1, 2, 3).contiguous()
        if recenter and target in norms:
            value = value.float() - 1
        parent, _, attr = target.rpartition(".")
        module = model.get_submodule(parent)
        assert tuple(getattr(module, attr).shape) == tuple(value.shape), target
        if attr in module._buffers:
            module._buffers[attr] = value
        else:
            module._parameters[attr] = nn.Parameter(value, requires_grad=False)
        loaded.add(target)
    expert_class = DiskExperts
    if batched_experts:
        from qwen38_flash_batched_experiment import BatchedDiskExperts
        expert_class = BatchedDiskExperts
    for i, layer in enumerate(model.model.language_model.layers):
        layer.mlp.experts = expert_class(store, external, i)
        loaded.update({f"model.language_model.layers.{i}.mlp.experts.gate_up_proj", f"model.language_model.layers.{i}.mlp.experts.down_proj"})
        if layer.ple is not None:
            prefix = f"language_model.model.layers.{i}.ple.ple_embedding.ngram_embedding"
            layer.ple.ple_embedding.ngram_embedding = DiskEmbedding(store, prefix)
            loaded.add(f"model.language_model.layers.{i}.ple.ple_embedding.ngram_embedding.weight")
    assert loaded == expected, {"missing": sorted(expected - loaded), "extra": sorted(loaded - expected)}
    for module in model.modules():
        for name, value in module._buffers.items():
            if value is not None:
                assert value.device.type != "meta", name
                module._buffers[name] = value.to("cuda")
    assert all(p.device.type != "meta" for p in model.parameters())
    model.eval()
    model.generation_config = GenerationConfig.from_pretrained(root, local_files_only=True)
    return model, store, {"norm_recentered": recenter, "norm_anchor_median": median,
                          "parameters_mapped": len(loaded), "expert_mode": "batched disk reads; no replacement cache" if batched_experts else "disk read per selected expert; no replacement cache"}
