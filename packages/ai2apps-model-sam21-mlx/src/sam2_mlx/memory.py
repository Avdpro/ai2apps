"""Memory encoder and attention for SAM2 video tracking, ported to MLX."""

import math

import mlx.core as mx
import mlx.nn as nn

from .position_encoding import apply_rotary_enc, compute_axial_cis, PositionEmbeddingSine
from .sam2_utils import DropPath, LayerNorm2d


class MaskDownSampler(nn.Module):
    """Downsample mask from [B,1,1024,1024] → [B,256,32,32]."""

    def __init__(self, embed_dim: int = 256):
        super().__init__()
        self.embed_dim = embed_dim
        self.layers = []
        chans = [1, 4, 16, 64, 256]
        for i in range(len(chans) - 1):
            self.layers.append(nn.Conv2d(chans[i], chans[i + 1], kernel_size=3, stride=2, padding=1))
            self.layers.append(LayerNorm2d(chans[i + 1]))
            self.layers.append(nn.GELU())
        self.final_conv = nn.Conv2d(256, embed_dim, kernel_size=1)

    def __call__(self, x: mx.array) -> mx.array:
        # x: [B, 1, H, W] channels-first → channels-last for MLX conv
        x = x.transpose(0, 2, 3, 1)  # [B, H, W, 1]
        for layer in self.layers:
            if isinstance(layer, LayerNorm2d):
                x = x.transpose(0, 3, 1, 2)
                x = layer(x)
                x = x.transpose(0, 2, 3, 1)
            else:
                x = layer(x)
        x = self.final_conv(x)  # [B, H', W', 256]
        return x.transpose(0, 3, 1, 2)  # [B, 256, H', W']


class CXBlock(nn.Module):
    """ConvNeXt block for mask-pixel feature fusion."""

    def __init__(self, dim: int):
        super().__init__()
        self.dwconv = nn.Conv2d(dim, dim, kernel_size=7, padding=3, groups=dim)
        self.norm = LayerNorm2d(dim)
        self.pw1 = nn.Linear(dim, 4 * dim)
        self.act = nn.GELU()
        self.pw2 = nn.Linear(4 * dim, dim)
        self.gamma = mx.ones((dim,))
        self.drop_path = DropPath(0.0)

    def __call__(self, x: mx.array) -> mx.array:
        # x: [B, C, H, W] channels-first
        shortcut = x
        x = x.transpose(0, 2, 3, 1)  # → [B, H, W, C]
        x = self.dwconv(x)
        x = x.transpose(0, 3, 1, 2)  # → [B, C, H, W]
        x = self.norm(x)
        x = x.transpose(0, 2, 3, 1)  # → [B, H, W, C]
        x = self.pw2(self.act(self.pw1(x)))
        x = x.transpose(0, 3, 1, 2)  # → [B, C, H, W]
        x = shortcut + self.drop_path(x) * self.gamma.reshape(1, -1, 1, 1)
        return x


class Fuser(nn.Module):
    """Fuses pixel features and mask features via ConvNeXt blocks.

    PT order: x = proj(input); for layer in layers: x = layer(x).
    With default config `input_projection=False`, proj is Identity (no
    weights). MLX matches PT key names: `proj` (Identity placeholder, no
    parameters) and `layers` (CXBlock list).
    """

    def __init__(self, num_layers: int = 2, dim: int = 256):
        super().__init__()
        # PT default: proj is nn.Identity() — emit no parameters. We omit it.
        self.layers = [CXBlock(dim) for _ in range(num_layers)]

    def __call__(self, x: mx.array) -> mx.array:
        # x: [B, C, H, W] channels-first (already pix_feat + mask_feat fused)
        for blk in self.layers:
            x = blk(x)
        return x


class MemoryEncoder(nn.Module):
    """Encodes mask prediction and pixel features into memory features."""

    def __init__(self, out_dim: int = 64, in_dim: int = 256):
        super().__init__()
        self.mask_downsampler = MaskDownSampler(embed_dim=in_dim)
        # PT applies a 1x1 projection to pix_feat BEFORE adding the
        # downsampled mask. Without this layer the masks are fused into
        # untransformed backbone features → memory_encoder produces noise.
        self.pix_feat_proj = nn.Conv2d(in_dim, in_dim, kernel_size=1)
        self.fuser = Fuser(num_layers=2, dim=in_dim)
        self.out_proj = nn.Conv2d(in_dim, out_dim, kernel_size=1) if in_dim != out_dim else None
        self.pos_encoder = PositionEmbeddingSine(out_dim, normalize=True)

    def __call__(
        self,
        pix_feat: mx.array,
        masks: mx.array,
        skip_mask_sigmoid: bool = False,
    ) -> tuple:
        """
        Args:
            pix_feat: [B, 256, 32, 32]
            masks: [B, 1, 1024, 1024]
        Returns:
            (vision_features [B, 64, 32, 32], vision_pos_enc [B, 64, 32, 32])
        """
        if not skip_mask_sigmoid:
            masks = mx.sigmoid(masks)
        mask_feat = self.mask_downsampler(masks)  # [B, 256, 32, 32]

        # pix_feat → 1x1 proj → add to mask_feat → ConvNeXt fuser
        pix = pix_feat.astype(mx.float32).transpose(0, 2, 3, 1)  # → [B,H,W,C]
        pix = self.pix_feat_proj(pix).transpose(0, 3, 1, 2)      # back [B,C,H,W]
        x = pix + mask_feat.astype(mx.float32)
        x = self.fuser(x)

        if self.out_proj is not None:
            x = x.transpose(0, 2, 3, 1)
            x = self.out_proj(x)
            x = x.transpose(0, 3, 1, 2)
        pos = self.pos_encoder(x)
        return x, pos


class RoPEAttention(nn.Module):
    """Multi-head attention with 2D-axial Rotary Position Embedding.

    Mirrors PT `sam2.modeling.sam.transformer.RoPEAttention`. RoPE is
    applied via complex multiplication using `apply_rotary_enc`.
    """

    def __init__(
        self,
        d_model: int = 256,
        num_heads: int = 1,
        kv_in_dim: int = 64,
        rope_k_repeat: bool = False,
    ):
        super().__init__()
        self.num_heads = num_heads
        head_dim = d_model // num_heads
        self.scale = head_dim**-0.5

        self.q_proj = nn.Linear(d_model, d_model)
        self.k_proj = nn.Linear(kv_in_dim, d_model)
        self.v_proj = nn.Linear(kv_in_dim, d_model)
        self.out_proj = nn.Linear(d_model, d_model)

        self.rope_k_repeat = rope_k_repeat
        self.head_dim = head_dim

    def __call__(
        self,
        q: mx.array,
        k: mx.array,
        v: mx.array,
        freqs_cis: mx.array,
        num_k_exclude_rope: int = 0,
    ) -> mx.array:
        """
        Args:
            q: [L_q, B, d_model]
            k: [L_k, B, kv_in_dim]
            v: [L_k, B, kv_in_dim]
            freqs_cis: complex `(L_q, head_dim/2)` from `compute_axial_cis`
            num_k_exclude_rope: tail K tokens (e.g. obj_ptr) to skip RoPE on
        """
        L_q, B, _ = q.shape
        L_k = k.shape[0]

        q = self.q_proj(q)
        k = self.k_proj(k)
        v = self.v_proj(v)

        # → [B, N_heads, L, head_dim]
        q = q.reshape(L_q, B, self.num_heads, self.head_dim).transpose(1, 2, 0, 3)
        k = k.reshape(L_k, B, self.num_heads, self.head_dim).transpose(1, 2, 0, 3)
        v = v.reshape(L_k, B, self.num_heads, self.head_dim).transpose(1, 2, 0, 3)

        # Split obj_ptr tail off K, rotate the spatial part, then re-attach.
        num_rotate = L_k - num_k_exclude_rope
        if num_rotate > 0:
            k_rot = k[..., :num_rotate, :]
            q_rot, k_rot = apply_rotary_enc(
                q, k_rot, freqs_cis, repeat_freqs_k=self.rope_k_repeat
            )
            q = q_rot
            if num_k_exclude_rope > 0:
                k = mx.concatenate([k_rot, k[..., num_rotate:, :]], axis=-2)
            else:
                k = k_rot
        # else: no rotation (degenerate case)

        # SDPA
        out = mx.fast.scaled_dot_product_attention(q, k, v, scale=self.scale)
        out = out.transpose(0, 2, 1, 3).reshape(L_q, B, -1)
        return self.out_proj(out)


class MemoryAttentionLayer(nn.Module):
    """One layer: self-attn → cross-attn (with memory_pos on K) → FFN.

    Per SAM2 yaml:
      - pos_enc_at_attn = False              (self-attn has no pos add)
      - pos_enc_at_cross_attn_queries = False
      - pos_enc_at_cross_attn_keys = True    (memory + memory_pos as K, V)
    """

    def __init__(
        self,
        d_model: int = 256,
        dim_feedforward: int = 2048,
        mem_dim: int = 64,
    ):
        super().__init__()
        self.self_attn = RoPEAttention(d_model=d_model, num_heads=1, kv_in_dim=d_model)
        self.cross_attn = RoPEAttention(
            d_model=d_model, num_heads=1, kv_in_dim=mem_dim,
            rope_k_repeat=True,
        )
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm3 = nn.LayerNorm(d_model)
        self.linear1 = nn.Linear(d_model, dim_feedforward)
        self.linear2 = nn.Linear(dim_feedforward, d_model)
        # PT has 3 dropout layers (p=0.1) but at inference they are no-ops.
        # Note: MLX `Module.training` defaults to True (opposite of PT),
        # so calling `nn.Dropout(0.1)` here would randomize outputs unless
        # the caller remembers `.train(False)`. Skip dropout entirely for
        # inference parity.

    def __call__(
        self,
        curr: mx.array,
        memory: mx.array,
        curr_pos: mx.array,
        memory_pos: mx.array,
        freqs_cis: mx.array,
        num_obj_ptr_tokens: int = 0,
    ) -> mx.array:
        # Self-attention (no pos add — pos_enc_at_attn=False)
        curr2 = self.norm1(curr)
        curr2 = self.self_attn(curr2, curr2, curr2, freqs_cis)
        curr = curr + curr2

        # Cross-attention: K = memory + memory_pos, V = memory.
        # The last `num_obj_ptr_tokens` of memory are the object-pointer
        # tokens; they bypass RoPE inside the K projection.
        curr2 = self.norm2(curr)
        k_in = memory + memory_pos
        curr2 = self.cross_attn(
            curr2, k_in, memory, freqs_cis,
            num_k_exclude_rope=num_obj_ptr_tokens,
        )
        curr = curr + curr2

        # FFN
        curr2 = self.norm3(curr)
        curr2 = self.linear2(nn.relu(self.linear1(curr2)))
        curr = curr + curr2
        return curr


class MemoryAttention(nn.Module):
    """Stack of MemoryAttentionLayers + a top-level LayerNorm.

    PT applies `output = output + 0.1 * curr_pos` before the layers
    (pos_enc_at_input=True), and `self.norm(output)` after them. Both were
    missing from the original MLX port.
    """

    def __init__(
        self,
        d_model: int = 256,
        num_layers: int = 4,
        dim_feedforward: int = 2048,
        mem_dim: int = 64,
        pos_enc_at_input: bool = True,
    ):
        super().__init__()
        self.layers = [
            MemoryAttentionLayer(d_model, dim_feedforward, mem_dim)
            for _ in range(num_layers)
        ]
        self.norm = nn.LayerNorm(d_model)
        self.pos_enc_at_input = pos_enc_at_input

    def __call__(
        self,
        curr: mx.array,
        memory: mx.array,
        curr_pos: mx.array,
        memory_pos: mx.array,
        freqs_cis: mx.array,
        num_obj_ptr_tokens: int = 0,
    ) -> mx.array:
        output = curr
        if self.pos_enc_at_input and curr_pos is not None:
            output = output + 0.1 * curr_pos
        for layer in self.layers:
            output = layer(output, memory, curr_pos, memory_pos, freqs_cis, num_obj_ptr_tokens)
        return self.norm(output)
