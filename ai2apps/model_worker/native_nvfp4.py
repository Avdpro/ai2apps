"""Reusable native NVFP4 Linear for CUDA Model Workers.

Explicit CUTLASS backend; no dequantized fallback. Checkpoint scale semantics
and packed format must be verified by the model adapter before construction.
"""
import torch
from torch import nn
from flashinfer import nvfp4_quantize, mm_fp4, SfLayout
from flashinfer.quantization import block_scale_interleave


class NativeNVFP4Linear(nn.Module):
    def __init__(self, packed, scales, weight_global, input_global):
        super().__init__()
        if torch.cuda.get_device_capability() != (12, 1):
            raise RuntimeError("This NVFP4 Runtime requires NVIDIA GB10 SM121")
        from flashinfer.jit import env as jit_env
        from flashinfer.version import __version__
        if __version__ != "0.7.0.post1":
            raise RuntimeError("Native NVFP4 requires the validated FlashInfer version")
        for name in ("fp4_gemm_cutlass_sm120", "fp4_quantization_120f"):
            if not (jit_env.FLASHINFER_AOT_DIR / name / f"{name}.so").is_file():
                raise RuntimeError(f"Runtime is missing bundled NVFP4 AOT module: {name}")
        if packed.dtype != torch.uint8 or packed.ndim != 2:
            raise ValueError("NVFP4 weights must be packed uint8 matrices")
        if scales.shape != (packed.shape[0], packed.shape[1] // 8):
            raise ValueError("NVFP4 block scales must use group size 16")
        if weight_global.numel() != 1 or input_global.numel() != 1:
            raise ValueError("NVFP4 global scales must be scalar")
        self.register_buffer('packed', packed.cuda())
        self.register_buffer('scales', block_scale_interleave(scales.cuda().view(torch.uint8)))
        self.register_buffer('input_global', input_global.cuda())
        self.register_buffer('alpha', 1 / (weight_global.cuda() * self.input_global))
        self.out_features, half = packed.shape
        self.in_features = half * 2
        self.calls = 0

    def forward(self, x):
        shape = x.shape
        q, scale = nvfp4_quantize(x.reshape(-1, self.in_features).contiguous(),
                                 self.input_global, sfLayout=SfLayout.layout_128x4)
        out = mm_fp4(q, self.packed.T, scale, self.scales, self.alpha, backend='cutlass')
        self.calls += 1
        return out.reshape(*shape[:-1], self.out_features)
