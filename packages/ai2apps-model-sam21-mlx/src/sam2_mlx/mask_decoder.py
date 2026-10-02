"""SAM2 mask decoder, prompt encoder, and two-way transformer. Ported to MLX."""

import math
from typing import List, Optional, Tuple

import mlx.core as mx
import mlx.nn as nn

from .position_encoding import PositionEmbeddingRandom
from .sam2_utils import MLP, get_activation_fn


class Attention(nn.Module):
    """Multi-head attention with optional projection downsampling.

    Mirrors PyTorch SAM2's modeling/sam/transformer.py::Attention. The
    `downsample_rate` knob is what SAM2 uses to shrink the internal q/k/v
    dim to `dim // downsample_rate`, which is why the cross-attn weights in
    the checkpoint are [128, 256] instead of [256, 256].
    """

    def __init__(
        self,
        dim: int,
        num_heads: int = 8,
        downsample_rate: int = 1,
        kv_in_dim: Optional[int] = None,
    ):
        super().__init__()
        self.num_heads = num_heads
        kv_in_dim = kv_in_dim or dim
        internal_dim = dim // downsample_rate
        assert internal_dim % num_heads == 0, "num_heads must divide internal_dim"
        head_dim = internal_dim // num_heads
        self.scale = head_dim ** -0.5

        self.q_proj = nn.Linear(dim, internal_dim)
        self.k_proj = nn.Linear(kv_in_dim, internal_dim)
        self.v_proj = nn.Linear(kv_in_dim, internal_dim)
        self.out_proj = nn.Linear(internal_dim, dim)

    def _separate_heads(self, x: mx.array, num_heads: int) -> mx.array:
        B, L, D = x.shape
        return x.reshape(B, L, num_heads, D // num_heads).transpose(0, 2, 1, 3)

    def _combine_heads(self, x: mx.array) -> mx.array:
        B, N, L, D = x.shape
        return x.transpose(0, 2, 1, 3).reshape(B, L, N * D)

    def __call__(self, q: mx.array, k: mx.array, v: mx.array) -> mx.array:
        q = self.q_proj(q)
        k = self.k_proj(k)
        v = self.v_proj(v)

        q = self._separate_heads(q, self.num_heads)
        k = self._separate_heads(k, self.num_heads)
        v = self._separate_heads(v, self.num_heads)

        out = mx.fast.scaled_dot_product_attention(q, k, v, scale=self.scale)
        out = self._combine_heads(out)
        return self.out_proj(out)


class TwoWayAttentionBlock(nn.Module):
    def __init__(
        self,
        embedding_dim: int = 256,
        num_heads: int = 8,
        mlp_dim: int = 2048,
        attention_downsample_rate: int = 2,
        skip_first_layer_pe: bool = False,
    ):
        super().__init__()
        # Self-attn on tokens stays at full dim (downsample_rate=1)
        self.self_attn = Attention(embedding_dim, num_heads)
        self.norm1 = nn.LayerNorm(embedding_dim)
        # Both cross-attns use the reduced internal dim.
        self.cross_attn_token_to_image = Attention(
            embedding_dim, num_heads, downsample_rate=attention_downsample_rate
        )
        self.norm2 = nn.LayerNorm(embedding_dim)
        self.mlp = MLP(embedding_dim, mlp_dim, embedding_dim, num_layers=2, activation=nn.ReLU)
        self.norm3 = nn.LayerNorm(embedding_dim)
        self.norm4 = nn.LayerNorm(embedding_dim)
        self.cross_attn_image_to_token = Attention(
            embedding_dim, num_heads, downsample_rate=attention_downsample_rate
        )
        self.skip_first_layer_pe = skip_first_layer_pe

    def __call__(
        self,
        queries: mx.array,
        keys: mx.array,
        query_pe: mx.array,
        key_pe: mx.array,
    ) -> Tuple[mx.array, mx.array]:
        # Self-attn on queries — first layer has no residual AND no PE addition
        # (per PT reference: queries = self_attn(queries, queries, queries)).
        # Later layers use the standard residual path with PE added to q.
        if self.skip_first_layer_pe:
            queries = self.self_attn(queries, queries, queries)
        else:
            q = queries + query_pe
            attn_out = self.self_attn(q, q, queries)
            queries = queries + attn_out
        queries = self.norm1(queries)

        # Cross-attn: tokens attend to image.
        q = queries + query_pe
        k = keys + key_pe
        attn_out = self.cross_attn_token_to_image(q, k, keys)
        queries = self.norm2(queries + attn_out)

        # MLP
        queries = self.norm3(queries + self.mlp(queries))

        # Cross-attn: image attends to tokens.
        q = queries + query_pe
        k = keys + key_pe
        attn_out = self.cross_attn_image_to_token(k, q, queries)
        keys = self.norm4(keys + attn_out)

        return queries, keys


class TwoWayTransformer(nn.Module):
    def __init__(
        self,
        depth: int = 2,
        embedding_dim: int = 256,
        num_heads: int = 8,
        mlp_dim: int = 2048,
        attention_downsample_rate: int = 2,
    ):
        super().__init__()
        self.layers = [
            TwoWayAttentionBlock(
                embedding_dim, num_heads, mlp_dim,
                attention_downsample_rate=attention_downsample_rate,
                skip_first_layer_pe=(i == 0),
            )
            for i in range(depth)
        ]
        self.final_attn = Attention(
            embedding_dim, num_heads, downsample_rate=attention_downsample_rate,
        )
        self.norm_final = nn.LayerNorm(embedding_dim)

    def __call__(
        self,
        image_embedding: mx.array,
        image_pe: mx.array,
        point_embedding: mx.array,
    ) -> Tuple[mx.array, mx.array]:
        # [B, C, H, W] → [B, H*W, C]
        B, C, H, W = image_embedding.shape
        image_embedding = image_embedding.reshape(B, C, H * W).transpose(0, 2, 1)
        image_pe = image_pe.reshape(1, C, H * W).transpose(0, 2, 1)

        queries = point_embedding  # [B, N_tokens, C]
        keys = image_embedding     # [B, H*W, C]

        # Match PT: query_pe is the *original* point_embedding reused per layer
        # (NOT zeros), key_pe is broadcast image_pe.
        query_pe = point_embedding
        key_pe = mx.broadcast_to(image_pe, (B, H * W, C))

        for layer in self.layers:
            queries, keys = layer(queries, keys, query_pe, key_pe)

        q = queries + query_pe
        k = keys + key_pe
        attn_out = self.final_attn(q, k, keys)
        queries = self.norm_final(queries + attn_out)

        return queries, keys


class PromptEncoder(nn.Module):
    def __init__(
        self,
        embed_dim: int = 256,
        image_embedding_size: int = 64,
        input_image_size: int = 1024,
        mask_in_chans: int = 16,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.input_image_size = input_image_size
        self.image_embedding_size = image_embedding_size
        self.pe_layer = PositionEmbeddingRandom(embed_dim // 2)

        self.point_embeddings = [
            nn.Embedding(1, embed_dim) for _ in range(4)
        ]  # pos, neg, top-left, bottom-right
        self.not_a_point_embed = nn.Embedding(1, embed_dim)

        self.mask_input = nn.Sequential(
            nn.Conv2d(1, mask_in_chans // 4, kernel_size=2, stride=2),
            _LayerNormWrapper(mask_in_chans // 4),
            nn.GELU(),
            nn.Conv2d(mask_in_chans // 4, mask_in_chans, kernel_size=2, stride=2),
            _LayerNormWrapper(mask_in_chans),
            nn.GELU(),
            nn.Conv2d(mask_in_chans, embed_dim, kernel_size=1),
        )
        self.no_mask_embed = nn.Embedding(1, embed_dim)

    def _embed_points(self, points: mx.array, labels: mx.array, pad: bool) -> mx.array:
        """Embed prompt points. points: [B, N, 2] (pixel coords), labels: [B, N].

        Label mapping (matches PT):
            -1 → padding (zero out PE, add not_a_point)
             0 → negative click            → point_embeddings[0]
             1 → positive click            → point_embeddings[1]
             2 → box top-left corner       → point_embeddings[2]
             3 → box bottom-right corner   → point_embeddings[3]
        """
        B, N = points.shape[:2]
        # PT shifts coords by +0.5 to point at pixel centers.
        points = points + 0.5
        if pad:
            # PT appends a padding point (coord=0) with label=-1 so the batch
            # always has at least one "not-a-point" token.
            pad_point = mx.zeros((B, 1, 2), dtype=points.dtype)
            pad_label = -mx.ones((B, 1), dtype=labels.dtype)
            points = mx.concatenate([points, pad_point], axis=1)
            labels = mx.concatenate([labels, pad_label], axis=1)
            N = N + 1

        pe = self.pe_layer.forward_with_coords(
            points, (self.input_image_size, self.input_image_size)
        )  # [B, N, embed_dim]

        # Zero the PE at padding positions (PT: point_embedding[labels == -1] = 0.0).
        not_pad = (labels != -1).astype(pe.dtype).reshape(B, N, 1)
        pe = pe * not_pad

        # Pull all label-keyed embeddings once (each is a [embed_dim] vector).
        zero_idx = mx.zeros((1,), dtype=mx.int32)
        not_a_point = self.not_a_point_embed(zero_idx).reshape(1, 1, -1)
        emb0 = self.point_embeddings[0](zero_idx).reshape(1, 1, -1)  # neg
        emb1 = self.point_embeddings[1](zero_idx).reshape(1, 1, -1)  # pos
        emb2 = self.point_embeddings[2](zero_idx).reshape(1, 1, -1)  # box TL
        emb3 = self.point_embeddings[3](zero_idx).reshape(1, 1, -1)  # box BR

        def _mask(val: int) -> mx.array:
            return (labels == val).astype(pe.dtype).reshape(B, N, 1)

        pe = pe + _mask(-1) * not_a_point
        pe = pe + _mask(0) * emb0
        pe = pe + _mask(1) * emb1
        pe = pe + _mask(2) * emb2
        pe = pe + _mask(3) * emb3
        return pe

    def _embed_masks(self, masks: mx.array) -> mx.array:
        # masks: [B, 1, H, W] channels-first → channels-last for MLX conv
        x = masks.transpose(0, 2, 3, 1)  # [B, H, W, 1]
        for layer in self.mask_input.layers:
            if isinstance(layer, _LayerNormWrapper):
                x = x.transpose(0, 3, 1, 2)
                x = layer(x)
                x = x.transpose(0, 2, 3, 1)
            else:
                x = layer(x)
        return x.transpose(0, 3, 1, 2)  # [B, C, H, W]

    def __call__(
        self,
        coords: Optional[mx.array] = None,
        labels: Optional[mx.array] = None,
        boxes: Optional[mx.array] = None,
        masks: Optional[mx.array] = None,
    ) -> Tuple[mx.array, mx.array]:
        """
        Returns:
            sparse_embeddings: [B, N_tokens, embed_dim]
            dense_embeddings: [B, embed_dim, H_enc, W_enc]
        """
        sparse_embeddings = None
        if coords is not None and labels is not None:
            sparse_embeddings = self._embed_points(coords, labels, pad=(boxes is None))

        if boxes is not None:
            # Convert boxes to corner points
            box_coords = boxes.reshape(-1, 2, 2)
            box_labels = mx.array([[2, 3]], dtype=mx.int32)
            box_labels = mx.broadcast_to(box_labels, (box_coords.shape[0], 2))
            box_emb = self._embed_points(box_coords, box_labels, pad=False)
            if sparse_embeddings is not None:
                sparse_embeddings = mx.concatenate([sparse_embeddings, box_emb], axis=1)
            else:
                sparse_embeddings = box_emb

        if sparse_embeddings is None:
            # PT returns empty (B, 0, embed_dim) when no prompts are given.
            # Tried the no_mask_embed fallback historically — caller doesn't
            # rely on a non-empty sparse, so empty is correct and matches PT.
            B = masks.shape[0] if masks is not None else 1
            sparse_embeddings = mx.zeros((B, 0, self.embed_dim), dtype=mx.float32)

        dense_embeddings = self.no_mask_embed(mx.zeros((1,), dtype=mx.int32)).reshape(1, -1, 1, 1)
        dense_embeddings = mx.broadcast_to(
            dense_embeddings,
            (sparse_embeddings.shape[0], self.embed_dim, self.image_embedding_size, self.image_embedding_size),
        )

        if masks is not None:
            mask_emb = self._embed_masks(masks)
            dense_embeddings = dense_embeddings + mask_emb

        return sparse_embeddings, dense_embeddings


class _LayerNormWrapper(nn.Module):
    """Channel-wise LayerNorm wrapped as an nn.Module for conv feature maps."""

    def __init__(self, num_channels: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.weight = mx.ones((num_channels,))
        self.bias = mx.zeros((num_channels,))

    def __call__(self, x: mx.array) -> mx.array:
        # x: [B, C, H, W]
        mean = x.mean(axis=1, keepdims=True)
        var = ((x - mean) ** 2).mean(axis=1, keepdims=True)
        x = (x - mean) / mx.sqrt(var + self.eps)
        return self.weight.reshape(1, -1, 1, 1) * x + self.bias.reshape(1, -1, 1, 1)


class MaskDecoder(nn.Module):
    def __init__(
        self,
        transformer_dim: int = 256,
        num_multimask_outputs: int = 3,
        iou_head_depth: int = 3,
        iou_head_hidden_dim: int = 256,
        pred_obj_scores: bool = True,
    ):
        super().__init__()
        self.transformer_dim = transformer_dim
        self.num_mask_tokens = num_multimask_outputs + 1  # +1 for IoU token
        self.num_multimask_outputs = num_multimask_outputs
        self.pred_obj_scores = pred_obj_scores

        # High-res feature convs (matching PyTorch channel dims)
        self.conv_s0 = nn.Conv2d(256, 32, kernel_size=1)
        self.conv_s1 = nn.Conv2d(256, 64, kernel_size=1)

        # Output tokens. SAM2-Hiera-Large is trained with pred_obj_scores=True,
        # so the obj_score_token at index 0 is part of the queries the
        # transformer was trained to attend to. Dropping it shifts every other
        # token's learned attention pattern by one slot — checkpoint tokens
        # then desynchronise from the transformer weights, scrambling masks.
        if self.pred_obj_scores:
            self.obj_score_token = nn.Embedding(1, transformer_dim)
        self.iou_token = nn.Embedding(1, transformer_dim)
        self.mask_tokens = nn.Embedding(self.num_mask_tokens, transformer_dim)
        self.transformer = TwoWayTransformer(depth=2, embedding_dim=transformer_dim, num_heads=8, mlp_dim=2048)

        # Output upscaling — native ConvTranspose2d, matching PyTorch SAM2 exactly.
        # Previous port used Upsample + Conv2d(k=3, pad=1) because the original dev
        # assumed MLX lacked ConvTranspose2d. MLX 0.22+ has nn.ConvTranspose2d
        # (verified bit-exact vs torch in test_conv_transpose_parity.py), so the
        # real op goes back in and the upscaling weights actually load.
        self.output_upscaling = nn.Sequential(
            nn.ConvTranspose2d(transformer_dim, transformer_dim // 4, kernel_size=2, stride=2),
            _LayerNormWrapper(transformer_dim // 4),
            nn.GELU(),
            nn.ConvTranspose2d(transformer_dim // 4, transformer_dim // 8, kernel_size=2, stride=2),
            nn.GELU(),
        )

        self.output_hypernetworks_mlps = [
            MLP(transformer_dim, transformer_dim, transformer_dim // 8, num_layers=3, activation=nn.ReLU)
            for _ in range(self.num_mask_tokens)
        ]

        self.iou_prediction_head = MLP(
            transformer_dim, iou_head_hidden_dim, self.num_mask_tokens, num_layers=iou_head_depth, activation=nn.ReLU
        )

        # SAM2-Hiera-Large checkpoint stores `pred_obj_score_head` as a 3-layer MLP
        # (pred_obj_scores_mlp=True). It produces a single object-presence logit
        # from the obj_score_token's transformer output. We don't currently use
        # this for the predict mask path, but loading it (even unused) keeps the
        # weight count clean and leaves the door open to use it later.
        if self.pred_obj_scores:
            self.pred_obj_score_head = MLP(
                transformer_dim, transformer_dim, 1, num_layers=3, activation=nn.ReLU
            )

    def __call__(
        self,
        image_embeddings: mx.array,
        image_pe: mx.array,
        sparse_prompt_embeddings: mx.array,
        dense_prompt_embeddings: mx.array,
        multimask_output: bool = True,
        high_res_features: Optional[List[mx.array]] = None,
    ) -> Tuple[mx.array, mx.array]:
        """
        Args:
            image_embeddings: [B, 256, 64, 64]
            image_pe: [1, 256, 64, 64]
            sparse_prompt_embeddings: [B, N_p, 256]
            dense_prompt_embeddings: [B, 256, 64, 64]
            high_res_features: Optional list [s0, s1] of high-res features
                                channels-first — s0: [B, C/8, 4H, 4W] (from Hiera stage 0),
                                s1: [B, C/4, 2H, 2W] (from Hiera stage 1).
                                When supplied, the two ConvTranspose2d layers in
                                output_upscaling get additive skip connections,
                                matching PT's use_high_res_features=True.
        Returns:
            masks: [B, M, 256, 256]
            iou_pred: [B, M]
        """
        B = image_embeddings.shape[0]

        # Combine image + dense embeddings
        img_embed = image_embeddings + dense_prompt_embeddings

        # Output tokens. PT order with pred_obj_scores=True:
        #     [obj_score_token, iou_token, mask_token_0..3, sparse_prompts...]
        # The obj_score_token at index 0 is critical even if we don't read its
        # transformer output: dropping it shifts every other token's learned
        # attention by one slot, which silently scrambles SAM2 masks.
        zero_idx = mx.zeros((1,), dtype=mx.int32)
        s = 0
        toks = []
        if self.pred_obj_scores:
            obj_tok = mx.broadcast_to(
                self.obj_score_token(zero_idx).reshape(1, 1, -1),
                (B, 1, self.transformer_dim),
            )
            toks.append(obj_tok)
            s = 1
        iou_tok = mx.broadcast_to(
            self.iou_token(zero_idx).reshape(1, 1, -1),
            (B, 1, self.transformer_dim),
        )
        mask_tok = mx.broadcast_to(
            self.mask_tokens(mx.arange(self.num_mask_tokens, dtype=mx.int32)).reshape(1, -1, self.transformer_dim),
            (B, self.num_mask_tokens, self.transformer_dim),
        )
        toks.extend([iou_tok, mask_tok, sparse_prompt_embeddings])
        output_tokens = mx.concatenate(toks, axis=1)

        # Run transformer
        queries, keys = self.transformer(img_embed, image_pe, output_tokens)

        # Token indexing per PT: iou at slot s, masks at slots s+1 .. s+num_mask_tokens.
        iou_token_out = queries[:, s:s + 1]
        mask_tokens_out = queries[:, s + 1:s + 1 + self.num_mask_tokens]

        # Upscale image features.
        # PT uses the transformer-PROCESSED image features (`src` aka our
        # `keys`) for upscaling, NOT the raw input. Earlier this layer
        # passed `img_embed` (= image_embeddings + dense), which discarded
        # all the cross-attention with the prompt tokens — that's why
        # masks pointed at the wrong object even though sparse_emb,
        # dense_emb, transformer queries, and IoU were all bit-exact.
        # PT with use_high_res_features=True:
        #     dc1, ln1, act1, dc2, act2 = self.output_upscaling
        #     src_4d = src.transpose(1,2).view(b, c, h, w)
        #     x = act1(ln1(dc1(src_4d) + feat_s1))
        #     x = act2(dc2(x) + feat_s0)
        # Our Sequential layout: [ConvTranspose2d, LayerNorm2d, GELU, ConvTranspose2d, GELU].
        B, C, H, W = img_embed.shape
        # Reshape transformer output `keys` (B, H*W, C) → (B, C, H, W).
        src_4d = keys.transpose(0, 2, 1).reshape(B, C, H, W)

        layers = self.output_upscaling.layers
        dc1, ln1, act1, dc2, act2 = layers[0], layers[1], layers[2], layers[3], layers[4]

        # ConvTranspose2d expects channels-last input.
        x_cl = src_4d.transpose(0, 2, 3, 1)       # [B, H, W, C]
        x_cl = dc1(x_cl)                           # [B, 2H, 2W, C/4]
        x_cf = x_cl.transpose(0, 3, 1, 2)
        if high_res_features is not None:
            x_cf = x_cf + high_res_features[1]     # s1 skip
        x_cf = ln1(x_cf)
        x_cl = x_cf.transpose(0, 2, 3, 1)
        x_cl = act1(x_cl)
        x_cl = dc2(x_cl)                           # [B, 4H, 4W, C/8]
        x_cf = x_cl.transpose(0, 3, 1, 2)
        if high_res_features is not None:
            x_cf = x_cf + high_res_features[0]     # s0 skip
        x_cl = x_cf.transpose(0, 2, 3, 1)
        x_cl = act2(x_cl)
        upscaled = x_cl.transpose(0, 3, 1, 2)      # [B, C/8, 4H, 4W]

        # Hypernetwork: mask tokens → weights → spatial dot product with upscaled embeddings.
        # Equivalent to PT: hyper_in @ upscaled.view(B, C, H*W) → reshape (B, M, H, W).
        masks = []
        for i in range(self.num_mask_tokens):
            hyper_out = self.output_hypernetworks_mlps[i](mask_tokens_out[:, i])  # [B, C_up]
            B_c, _, H_up, W_up = upscaled.shape
            w = hyper_out.reshape(B, -1, 1, 1)
            mask = (upscaled * w).sum(axis=1, keepdims=True)  # [B, 1, H_up, W_up]
            masks.append(mask)
        masks = mx.concatenate(masks, axis=1)  # [B, M, H_up, W_up]

        # IoU prediction
        iou_pred = self.iou_prediction_head(iou_token_out)  # [B, 1, M]
        iou_pred = iou_pred[:, 0]  # [B, M]

        # Object-presence score from obj_score_token's transformer output.
        # PT default 10.0 (always-present) when pred_obj_scores=False.
        if self.pred_obj_scores:
            object_score_logits = self.pred_obj_score_head(queries[:, 0])  # [B, 1]
        else:
            object_score_logits = mx.full((B, 1), 10.0, dtype=mx.float32)

        # Mask resolution is already the SAM2 output resolution (4x patch size,
        # = 256×256 for a 1024 input). PT does NOT apply an additional 4× here —
        # the predictor resizes from 256×256 to original image size. An earlier
        # version of this code added an extra nn.Upsample(scale_factor=4) that
        # produced 1024×1024 masks, which silently shifted spatial alignment
        # because nearest-neighbor 4× of low-res mask = blocky and off-center.

        # Select masks per multimask_output (drop mask_token_0).
        if multimask_output:
            masks = masks[:, 1:, :, :]  # [B, 3, H_up, W_up]
            iou_pred = iou_pred[:, 1:]   # [B, 3]
        else:
            masks = masks[:, 0:1, :, :]
            iou_pred = iou_pred[:, 0:1]

        # `use_multimask_token_for_obj_ptr=True` in sam2_hiera_l.yaml: when
        # multimask_output is on, obj_ptr is sourced from the 3 multimask
        # tokens (caller picks by best-IoU). Otherwise the single-mask token.
        if multimask_output:
            sam_tokens_out = mask_tokens_out[:, 1:]  # [B, 3, C]
        else:
            sam_tokens_out = mask_tokens_out[:, 0:1]  # [B, 1, C]

        return masks, iou_pred, sam_tokens_out, object_score_logits
