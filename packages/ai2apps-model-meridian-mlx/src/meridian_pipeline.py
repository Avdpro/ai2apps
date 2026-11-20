"""Meridian teacher + turbo LoRA over a pinned H3 FL2VA 8-bit base.

AI2Apps adaptation of the verified local probe; no Torch, developer paths,
network downloads or runtime custom Metal source compilation.
"""
import gc
import json
from pathlib import Path
import mlx.core as mx
import mlx.nn as nn
from minimax_h3_mlx.load import load_dit
from minimax_h3_mlx.variants import map_lora_module
from minimax_h3_mlx.staged_pipeline import StagedMiniMaxH3Pipeline


class LiveLoRA(nn.Module):
    def __init__(self, base):
        super().__init__()
        self.base = base
        self.adapters = []

    @property
    def weight(self):
        return self.base.weight

    @property
    def scales(self):
        return getattr(self.base, "scales", None)

    def __call__(self, x):
        y = self.base(x).astype(mx.float32)
        for a,b,start,end in self.adapters:
            delta = (x.astype(mx.float32) @ a.T) @ b.T
            y = y + delta if start is None else y.at[..., start:end].add(delta)
        return y.astype(x.dtype)


def create_pipeline(root, base_root, phase_observer=None):
    def dit_loader(**kwargs):
        model = load_dit(base_root)
        count = 0
        for name in ("teacher_lora", "turbo_lora"):
            weights = mx.load(str(root / name / "pytorch_lora_weights.safetensors"))
            for key,a in weights.items():
                if not key.endswith(".lora_A.weight"):
                    continue
                name = key[:-len(".lora_A.weight")]
                b = weights[name + ".lora_B.weight"]
                start = end = None
                swap = False
                if name == "proj_in":
                    path = "video_patch_proj"
                elif name == "proj_out":
                    path = "final_layer.video_out"
                else:
                    target = map_lora_module(name)
                    path = target.weight_key[:-7]
                    start,end,swap = target.row_start,target.row_end,target.swap_halves
                if swap:
                    b = mx.concatenate(mx.split(b,2,axis=0)[::-1],axis=0)
                obj = model
                parts = path.split(".")
                for part in parts[:-1]:
                    obj = obj[int(part)] if part.isdigit() else getattr(obj,part)
                old = getattr(obj,parts[-1])
                layer = old if isinstance(old,LiveLoRA) else LiveLoRA(old)
                layer.adapters.append((a.astype(mx.float32),b.astype(mx.float32),start,end))
                setattr(obj,parts[-1],layer)
                count += 1
            mx.eval(model.parameters())
            del weights
            gc.collect()
            mx.clear_cache()
        if count != 604:
            raise ValueError("Meridian adapter inventory differs from verified checkpoint")
        return model

    class FixedEncoder:
        def encode_references(self,*args):
            frames=pipeline.meridian_num_frames
            assets=root
            embeddings = mx.load(str(assets/f"fixed_embed_{frames}.safetensors"))
            tags = json.loads((assets/f"fixed_embed_{frames}_tags.json").read_text())
            return embeddings["prompt_embeds"],tags

    pipeline = StagedMiniMaxH3Pipeline(base_root,loaders={"dit":dit_loader,"text_encoder":lambda **kw:FixedEncoder()},phase_observer=phase_observer)
    if "ref2va" not in pipeline.config.tasks:
        pipeline.config.tasks.append("ref2va")
    pipeline.config.sigma_shift_video = 3.0
    pipeline.config.sigma_shift_audio = 3.0
    pipeline.meridian_num_frames=73
    return pipeline
