# InterpolateRegulator — S2Mel length regulator, MLX port (continuous path only).
# content_in_proj(1024->512) -> nearest-interp to ylens.max() -> 4x(Conv1d3+GN1+Mish)
# + Conv1d1. GroupNorm(1,512) NOT LayerNorm; nn.Mish; nearest never 'linear'.
import mlx.core as mx
import mlx.nn as nn

from omlx.vendor.indextts25 import ops
from omlx.vendor.indextts25.ops import Seq


class Mish(nn.Module):
    def __call__(self, x):
        sp = mx.where(x > 20, x, mx.log(1 + mx.exp(x)))  # torch softplus threshold 20
        return x * mx.tanh(sp)


class InterpolateRegulator(nn.Module):
    def __init__(self, channels=512, sampling_ratios=(1, 1, 1, 1), is_discrete=False, in_channels=None,
                 codebook_size=1024, out_channels=None, groups=1, n_codebooks=1):
        super().__init__()
        self.sampling_ratios = list(sampling_ratios)
        self.interpolate = len(self.sampling_ratios) > 0
        out_channels = out_channels or channels
        model = {}
        i = 0
        for _ in self.sampling_ratios:
            model[str(i)] = nn.Conv1d(channels, channels, 3, padding=1); i += 1
            model[str(i)] = nn.GroupNorm(groups, channels); i += 1
            model[str(i)] = Mish(); i += 1
        model[str(i)] = nn.Conv1d(channels, out_channels, 1)
        self.model = Seq(model)
        self.embedding = nn.Embedding(codebook_size, channels)  # discrete path (ckpt compat)
        self.mask_token = mx.zeros((1, channels))
        self.is_discrete = is_discrete
        self.n_codebooks = n_codebooks
        if n_codebooks > 1:
            self.extra_codebooks = Seq({str(i): nn.Embedding(codebook_size, channels) for i in range(n_codebooks - 1)})
            self.extra_codebook_mask_tokens = Seq({str(i): mx.zeros((1, channels)) for i in range(n_codebooks - 1)})
        if not is_discrete:
            self.content_in_proj = nn.Linear(in_channels, channels)

    def __call__(self, x, ylens=None, n_quantizers=None, f0=None):  # x [B,T,1024]
        x = self.content_in_proj(x)
        mx.eval(x)
        mask = ops.sequence_mask(ylens, int(ylens.max())).astype(mx.float32)[..., None]  # [B,T,1]
        if self.interpolate:
            x = ops.interpolate_nearest(x, int(ylens.max()))
        x = self.model(x)
        mx.eval(x)
        return x * mask, ylens, None, None, None
