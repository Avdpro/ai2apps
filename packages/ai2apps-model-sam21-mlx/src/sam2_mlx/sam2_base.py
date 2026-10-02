"""SAM2Base — core SAM2 model orchestrator for video tracking. Ported to MLX."""

from typing import Dict, List, Optional, Tuple
import math

import mlx.core as mx
import mlx.nn as nn

from .image_encoder import ImageEncoder
from .mask_decoder import MaskDecoder, PromptEncoder
from .memory import MemoryAttention, MemoryEncoder


class _MLP3(nn.Module):
    """Match PT `MLP(input, hidden, output, num_layers=3, activation=ReLU)`.

    Three Linear layers; ReLU between them, not after the last. PT key
    naming `layers.0`, `layers.1`, `layers.2`.
    """
    def __init__(self, dim_in: int, dim_hidden: int, dim_out: int):
        super().__init__()
        self.layers = [
            nn.Linear(dim_in, dim_hidden),
            nn.Linear(dim_hidden, dim_hidden),
            nn.Linear(dim_hidden, dim_out),
        ]

    def __call__(self, x):
        for i, lyr in enumerate(self.layers):
            x = lyr(x)
            if i < len(self.layers) - 1:
                x = nn.relu(x)
        return x


class SAM2Base(nn.Module):
    """Core SAM2 model: image encoder + mask decoder + memory for video tracking."""

    def __init__(
        self,
        image_encoder: ImageEncoder,
        mask_decoder: MaskDecoder,
        prompt_encoder: PromptEncoder,
        memory_attention: MemoryAttention,
        memory_encoder: MemoryEncoder,
        image_size: int = 1024,
        num_maskmem: int = 7,
        backbone_stride: int = 16,
        sigmoid_scale_for_mem_enc: float = 20.0,
        sigmoid_bias_for_mem_enc: float = -10.0,
        use_mask_input_as_output_without_sam: bool = False,
        max_cond_frames_in_attn: int = -1,
        directly_add_no_mem_embed: bool = True,
        no_obj_embed_spatial: bool = False,
        use_high_res_features_in_sam: bool = True,
        multimask_output_in_sam: bool = True,
        multimask_min_pt_num: int = 0,
        multimask_max_pt_num: int = 1,
        use_mlp_for_obj_ptr_proj: bool = True,
        # sam2.1 additions
        add_tpos_enc_to_obj_ptrs: bool = False,
        proj_tpos_enc_in_obj_ptrs: bool = False,
        use_signed_tpos_enc_to_obj_ptrs: bool = False,
        max_obj_ptrs_in_encoder: int = 16,
        compile_image_encoder: bool = False,
    ):
        super().__init__()
        self.image_encoder = image_encoder
        self.mask_decoder = mask_decoder
        self.prompt_encoder = prompt_encoder
        self.memory_attention = memory_attention
        self.memory_encoder = memory_encoder

        self.image_size = image_size
        self.backbone_stride = backbone_stride
        self.num_maskmem = num_maskmem
        self.sigmoid_scale_for_mem_enc = sigmoid_scale_for_mem_enc
        self.sigmoid_bias_for_mem_enc = sigmoid_bias_for_mem_enc
        self.use_mask_input_as_output_without_sam = use_mask_input_as_output_without_sam
        self.max_cond_frames_in_attn = max_cond_frames_in_attn
        self.directly_add_no_mem_embed = directly_add_no_mem_embed
        self.use_high_res_features_in_sam = use_high_res_features_in_sam
        self.multimask_output_in_sam = multimask_output_in_sam
        # sam2.1 obj_ptr extras
        self.add_tpos_enc_to_obj_ptrs = add_tpos_enc_to_obj_ptrs
        self.proj_tpos_enc_in_obj_ptrs = proj_tpos_enc_in_obj_ptrs
        self.use_signed_tpos_enc_to_obj_ptrs = use_signed_tpos_enc_to_obj_ptrs
        self.max_obj_ptrs_in_encoder = max_obj_ptrs_in_encoder

        # Learned embedding for "no memory" placeholder
        self.no_mem_embed = mx.random.normal((1, 1, 256)) * 0.02
        self.no_mem_pos_enc = mx.random.normal((1, 1, 256)) * 0.02
        self.maskmem_tpos_enc = mx.random.normal((num_maskmem, 1, 1, 64)) * 0.02

        # Object pointer projection — PT uses a 3-layer MLP with ReLU,
        # not Linear→GELU→Linear. PT key naming `obj_ptr_proj.layers.0/1/2`.
        d_model = mask_decoder.transformer_dim
        if use_mlp_for_obj_ptr_proj:
            self.obj_ptr_proj = _MLP3(d_model, d_model, d_model)
        else:
            self.obj_ptr_proj = nn.Linear(d_model, d_model)

        self.no_obj_ptr = mx.random.normal((1, d_model)) * 0.02

        # sam2.1: project sine temporal PE for obj_ptr cross-attn into mem_dim.
        # Shape (256, 64) Linear matches PT's `obj_ptr_tpos_proj`.
        if add_tpos_enc_to_obj_ptrs and proj_tpos_enc_in_obj_ptrs:
            self.obj_ptr_tpos_proj = nn.Linear(d_model, 64)
        else:
            self.obj_ptr_tpos_proj = None

        # sam2.1: spatial "no object" embedding added to memory features
        # when the object isn't present (object_score < 0).
        if no_obj_embed_spatial:
            self.no_obj_embed_spatial = mx.random.normal((1, 64)) * 0.02
        else:
            self.no_obj_embed_spatial = None

        # mask_downsample: PyTorch's separate downsampling conv for masks
        self.mask_downsample = nn.Conv2d(1, 1, kernel_size=4, stride=4)

    def _get_image_feature(self, img_batch: mx.array, pad_nf: int = 0):
        """Run image encoder on a batch of images."""
        # img_batch: [B, C, H, W] (single image or batch of same image)
        backbone_out = self.image_encoder(img_batch)
        return backbone_out

    def _prepare_backbone_features(self, backbone_out: dict) -> Tuple[List[mx.array], List[mx.array], List[Tuple[int, int]]]:
        """Prepare backbone features: flatten spatial dims → [H*W, B, C]."""
        num_levels = len(backbone_out["backbone_fpn"])
        vision_feats = []
        vision_pos_embeds = []
        feat_sizes = []

        for level in range(num_levels):
            feat = backbone_out["backbone_fpn"][level]  # [B, C, H, W]
            pos_enc = backbone_out["vision_pos_enc"][level]  # [B, C_pos, H, W]
            B, C, H, W = feat.shape
            feat_sizes.append((H, W))
            # Flatten: [B, C, H*W] → [H*W, B, C]
            vision_feats.append(feat.reshape(B, C, H * W).transpose(0, 2, 1).transpose(1, 0, 2))
            vision_pos_embeds.append(pos_enc.reshape(B, C, H * W).transpose(0, 2, 1).transpose(1, 0, 2))

        return vision_feats, vision_pos_embeds, feat_sizes

    def _prepare_memory_conditioned_features(
        self,
        frame_idx: int,
        is_init_cond_frame: bool,
        current_vision_feats: List[mx.array],
        current_vision_pos_embeds: List[mx.array],
        feat_sizes: List[Tuple[int, int]],
        feat_sizes_high_res: Optional[List[Tuple[int, int]]],
        cond_frame_outputs: Dict[int, dict],
        non_cond_frame_outputs: Dict[int, dict],
    ) -> Tuple[mx.array, mx.array, mx.array, mx.array]:
        """Fuse memory features into current vision features via memory attention.

        Mirrors PT `SAM2Base._prepare_memory_conditioned_features`. Critical:
        each memory frame's spatial pos enc is summed with a *temporal* pos
        enc `maskmem_tpos_enc[num_maskmem - t_pos - 1]` so the attention
        can distinguish memory from different time slots.
        """
        B = current_vision_feats[-1].shape[1]
        H, W = feat_sizes[-1]
        C = 256

        # Initial conditioning frame: skip memory attention; use no_mem_embed.
        if is_init_cond_frame:
            if self.directly_add_no_mem_embed:
                pix_feat = current_vision_feats[-1] + self.no_mem_embed.reshape(1, 1, C)
                pix_feat = pix_feat.transpose(1, 0, 2).reshape(B, H, W, C).transpose(0, 3, 1, 2)
                return pix_feat, None, None, None
            # (Non-default branch — falls through below with a 1-token dummy memory.)

        # Build memory tokens (cond at t_pos=0, non-cond at t_pos=1..num_maskmem-1).
        to_cat_mem: list[mx.array] = []
        to_cat_pos: list[mx.array] = []

        # Cond frames first — temporal slot 0 (the prompted frame).
        # Per SAM2 paper §4 + appendix D: each memory frame's spatial pos
        # enc is summed with a learned temporal pos enc `maskmem_tpos_enc`
        # so the attention can distinguish memory from different time
        # slots. Cond gets t_pos=0 (slot num_maskmem-1 in the embed table).
        for t in sorted(cond_frame_outputs.keys()):
            out = cond_frame_outputs[t]
            feats = out["maskmem_features"].reshape(B, 64, -1).transpose(2, 0, 1)
            penc = out["maskmem_pos_enc"].reshape(B, 64, -1).transpose(2, 0, 1)
            penc = penc + self.maskmem_tpos_enc[self.num_maskmem - 1].reshape(1, 1, 64)
            to_cat_mem.append(feats)
            to_cat_pos.append(penc)

        # Non-cond memory: per SAM2 paper §4. Auto-enable only when
        # obj_ptr cross-attn is functional (sam2.1 with full obj_ptr_tpos_proj).
        # For v1 large or partially-ported configs, non-cond memory destabilizes
        # propagation (memory features encode wrong location, cascade through frames).
        sorted_nc = []
        if self.add_tpos_enc_to_obj_ptrs and self.obj_ptr_tpos_proj is not None:
            sorted_nc = sorted(t for t in non_cond_frame_outputs if t < frame_idx)
        recent = sorted_nc[-(self.num_maskmem - 1):] if sorted_nc else []
        for offset, t in enumerate(reversed(recent)):
            t_pos = self.num_maskmem - 1 - offset
            out = non_cond_frame_outputs[t]
            feats = out["maskmem_features"].reshape(B, 64, -1).transpose(2, 0, 1)
            penc = out["maskmem_pos_enc"].reshape(B, 64, -1).transpose(2, 0, 1)
            penc = penc + self.maskmem_tpos_enc[self.num_maskmem - t_pos - 1].reshape(1, 1, 64)
            to_cat_mem.append(feats)
            to_cat_pos.append(penc)

        if not to_cat_mem:
            pix_feat = current_vision_feats[-1] + self.no_mem_embed.reshape(1, 1, C)
            pix_feat = pix_feat.transpose(1, 0, 2).reshape(B, H, W, C).transpose(0, 3, 1, 2)
            return pix_feat, None, None, None

        # ── Object pointers (sam2.1 critical addition) ──
        # PT cross-attends to obj_ptr tokens from past frames. Each 256-D
        # ptr is split into 4 × 64-D tokens so it lives in mem_dim=64
        # space. Temporal sine PE on |frame_idx - t| is projected through
        # `obj_ptr_tpos_proj` and broadcast across the 4 sub-tokens.
        num_obj_ptr_tokens = 0
        if (self.add_tpos_enc_to_obj_ptrs and
                self.obj_ptr_tpos_proj is not None and
                (cond_frame_outputs or non_cond_frame_outputs)):
            max_ptrs = self.max_obj_ptrs_in_encoder
            pos_and_ptrs: list[tuple[float, mx.array]] = []

            # Cond ptrs: only past for eval (t <= frame_idx).
            for t in sorted(cond_frame_outputs.keys()):
                if t > frame_idx:
                    continue
                out = cond_frame_outputs[t]
                if "obj_ptr" in out:
                    sign = (frame_idx - t) if self.use_signed_tpos_enc_to_obj_ptrs else abs(frame_idx - t)
                    pos_and_ptrs.append((float(sign), out["obj_ptr"]))

            # Non-cond ptrs: walk backward from frame_idx-1.
            for t_diff in range(1, max_ptrs):
                t = frame_idx - t_diff
                if t < 0:
                    break
                if t in non_cond_frame_outputs:
                    out = non_cond_frame_outputs[t]
                    if "obj_ptr" in out:
                        sign = (frame_idx - t) if self.use_signed_tpos_enc_to_obj_ptrs else t_diff
                        pos_and_ptrs.append((float(sign), out["obj_ptr"]))

            if pos_and_ptrs:
                positions = [p for p, _ in pos_and_ptrs]
                ptrs_stack = mx.stack([p for _, p in pos_and_ptrs], axis=0)  # [N, B, 256]
                N = ptrs_stack.shape[0]

                # Sine temporal PE on (sign / max_ptrs-1) of dimension 256
                # (PT: get_1d_sine_pe), then project to 64-D via Linear.
                from .position_encoding import _get_1d_sine_pe
                tpos = mx.array(positions, dtype=mx.float32) / max(1, max_ptrs - 1)
                tpos_sine = _get_1d_sine_pe(tpos, dim=C)         # [N, 256]
                tpos_proj = self.obj_ptr_tpos_proj(tpos_sine)    # [N, 64]
                obj_pos = tpos_proj.reshape(N, 1, 64)
                obj_pos = mx.broadcast_to(obj_pos, (N, B, 64))

                # Split each 256-D obj_ptr into (256/64=4) tokens of 64.
                ratio = C // 64  # = 4
                tokens = ptrs_stack.reshape(N, B, ratio, 64).transpose(0, 2, 1, 3).reshape(N * ratio, B, 64)
                # Repeat-interleave obj_pos by `ratio` so each ptr's 4
                # sub-tokens share the same temporal embedding.
                obj_pos_rep = mx.repeat(obj_pos, ratio, axis=0)

                to_cat_mem.append(tokens)
                to_cat_pos.append(obj_pos_rep)
                num_obj_ptr_tokens = tokens.shape[0]

        memory = mx.concatenate(to_cat_mem, axis=0)
        memory_pos = mx.concatenate(to_cat_pos, axis=0)

        # Memory attention (head_dim=256 = d_model since num_heads=1).
        curr = current_vision_feats[-1]
        curr_pos = current_vision_pos_embeds[-1]
        from .position_encoding import compute_axial_cis
        freqs_cis = compute_axial_cis(256, H, W)

        curr_out = self.memory_attention(
            curr, memory, curr_pos, memory_pos, freqs_cis,
            num_obj_ptr_tokens=num_obj_ptr_tokens,
        )
        pix_feat = curr_out.transpose(1, 0, 2).reshape(B, H, W, C).transpose(0, 3, 1, 2)
        return pix_feat, None, None, None

    def _get_obj_ptr_pe(self, t_pos: mx.array) -> mx.array:
        """Get position encoding for object pointer based on temporal position."""
        # Simple sine PE based on t_pos
        dim = 64
        pe = []
        for tp in t_pos:
            enc = mx.sin(tp * mx.exp(-math.log(10000.0) * mx.arange(0, dim, 2) / dim))
            pe.append(enc)
        return mx.stack(pe, axis=0).reshape(-1, 1, dim)

    def _forward_sam_heads(
        self,
        backbone_features: mx.array,
        backbone_high_res_features: Optional[List[mx.array]],
        point_inputs: Optional[Tuple[mx.array, mx.array]] = None,
        mask_inputs: Optional[mx.array] = None,
        high_res_feats_s0: Optional[mx.array] = None,
        high_res_feats_s1: Optional[mx.array] = None,
        multimask_output: bool = True,
    ) -> Tuple[mx.array, mx.array, mx.array]:
        """Run SAM mask decoder on backbone features."""
        B, C, H, W = backbone_features.shape

        # Image PE must come from prompt_encoder.pe_layer (PositionEmbeddingRandom)
        # — same random gaussian basis that encodes the point prompts. PT's
        # `PromptEncoder.get_dense_pe()` = pe_layer(image_embedding_size).unsqueeze(0).
        # A previous version here built a fresh PositionEmbeddingSine(256), which
        # produces a totally different PE and scrambles the mask_decoder.
        image_pe = self.prompt_encoder.pe_layer((H, W))  # [C, H, W]
        image_pe = image_pe.reshape(1, C, H, W)

        # Prompt encoding — PT always creates at least one point (with label
        # -1 = padding) so the mask decoder always has ≥1 sparse token.
        if point_inputs is not None:
            points, labels = point_inputs
            sparse_emb, dense_emb = self.prompt_encoder(points, labels)
        elif mask_inputs is not None:
            sparse_emb, dense_emb = self.prompt_encoder(masks=mask_inputs)
        else:
            # FIX BUG 1: Create dummy point with label -1 (matches PT exactly)
            dummy_coords = mx.zeros((B, 1, 2), dtype=mx.float32)
            dummy_labels = -mx.ones((B, 1), dtype=mx.int32)
            sparse_emb, dense_emb = self.prompt_encoder(dummy_coords, dummy_labels)

        # Run mask decoder — pass s0/s1 so the output_upscaling picks up the
        # high-res skip connections PT uses with use_high_res_features=True.
        high_res = None
        if high_res_feats_s0 is not None and high_res_feats_s1 is not None:
            high_res = [high_res_feats_s0, high_res_feats_s1]
        low_res_masks, iou_pred, sam_tokens_out, object_score_logits = self.mask_decoder(
            backbone_features,
            image_pe,
            sparse_emb,
            dense_emb,
            multimask_output=multimask_output,
            high_res_features=high_res,
        )

        # FIX BUG 2: Apply NO_OBJ_SCORE gating (matches PT exactly).
        # When object_score_logits <= 0 (obj not appearing), replace the
        # entire mask with NO_OBJ_SCORE so memory encoder gets a clean
        # "no object" signal instead of noisy mask data.
        NO_OBJ_SCORE = -1024.0
        is_obj_appearing = object_score_logits[:, 0] > 0   # [B]
        # Gate the mask: replace with NO_OBJ_SCORE when obj not appearing
        gate = is_obj_appearing.astype(low_res_masks.dtype).reshape(-1, 1, 1, 1)
        low_res_masks = gate * low_res_masks + (1 - gate) * NO_OBJ_SCORE

        # NOTE: PT pre-picks the best multimask candidate here. We
        # return all 3 channels and let downstream pick by argmax(iou)
        # — produces the same chosen mask but lets test/debug code
        # see all candidates. Keep this for v1 baseline stability.

        # obj_ptr derivation: argmax(iou) over sam_tokens_out.
        if multimask_output and sam_tokens_out.shape[1] > 1:
            B_ = sam_tokens_out.shape[0]
            best_iou_inds = mx.argmax(iou_pred, axis=-1)
            picked = mx.take_along_axis(
                sam_tokens_out, best_iou_inds.reshape(B_, 1, 1), axis=1
            )
            sam_output_token = picked[:, 0]
        else:
            sam_output_token = sam_tokens_out[:, 0]
        obj_ptr = self.obj_ptr_proj(sam_output_token)

        lam = is_obj_appearing.astype(obj_ptr.dtype).reshape(-1, 1)
        obj_ptr = lam * obj_ptr + (1 - lam) * self.no_obj_ptr.reshape(1, -1)

        return low_res_masks, low_res_masks, iou_pred, obj_ptr, object_score_logits

    def _use_mask_as_output(self, backbone_features, high_res_masks):
        """When bypassing SAM: interpolate mask input to backbone resolution."""
        B, _, H_hr, W_hr = high_res_masks.shape
        H_low = backbone_features.shape[2]
        masks_cl = high_res_masks[:, 0:1].transpose(0, 2, 3, 1)  # [B, H, W, 1]
        nn_upsample = nn.Upsample((H_low, H_low))
        low_res = nn_upsample(masks_cl.reshape(B, H_hr, W_hr, 1))
        low_res = low_res.reshape(B, H_low * H_low).reshape(B, 1, H_low, H_low)
        return low_res.reshape(B, H_low, H_low).reshape(B, 1, H_low, H_low)

    def _encode_new_memory(
        self,
        current_vision_feats: List[mx.array],
        feat_sizes: List[Tuple[int, int]],
        pred_masks_high_res: mx.array,
        is_mask_from_pts: bool,
        iou_pred: Optional[mx.array] = None,
        object_score_logits: Optional[mx.array] = None,
    ) -> Tuple[mx.array, mx.array]:
        """Encode mask prediction into memory features."""
        B = pred_masks_high_res.shape[0]
        pix_feat = current_vision_feats[-1].transpose(1, 0, 2).reshape(
            B, feat_sizes[-1][0], feat_sizes[-1][1], -1
        ).transpose(0, 3, 1, 2)  # [B, 256, H, W]

        # Pick best candidate by IoU (was 3-channel before this step).
        if pred_masks_high_res.shape[1] > 1 and iou_pred is not None:
            best = mx.argmax(iou_pred, axis=-1)
            masks_for_mem = mx.take_along_axis(
                pred_masks_high_res,
                best.reshape(B, 1, 1, 1),
                axis=1,
            )
        else:
            masks_for_mem = pred_masks_high_res[:, 0:1]

        if masks_for_mem.shape[2] != self.image_size:
            H, W = masks_for_mem.shape[2:]
            scale = self.image_size / H
            masks_cl = masks_for_mem.reshape(B * 1, H, W, 1)
            masks_for_mem = nn.Upsample(scale_factor=scale)(masks_cl)
            masks_for_mem = masks_for_mem.reshape(B, 1, self.image_size, self.image_size)

        # PT order: sigmoid FIRST, then scale * sigmoid + bias.
        # NOTE: this is PT 2.1's exact formula. For v1 large checkpoint
        # the original `sigmoid(scale * x + bias)` form ALSO worked
        # because mask logits are bounded; sticking with PT's sequence
        # for forward-compat with sam2.1.
        mask_for_mem = mx.sigmoid(masks_for_mem)
        mask_for_mem = mask_for_mem * self.sigmoid_scale_for_mem_enc + self.sigmoid_bias_for_mem_enc

        maskmem_features, maskmem_pos_enc = self.memory_encoder(
            pix_feat, mask_for_mem, skip_mask_sigmoid=True,
        )

        # sam2.1: add `no_obj_embed_spatial` to maskmem features when obj
        # is absent (PT behavior verbatim).
        if self.no_obj_embed_spatial is not None and object_score_logits is not None:
            is_obj = (object_score_logits[:, 0] > 0).astype(maskmem_features.dtype)
            absent = (1.0 - is_obj).reshape(-1, 1, 1, 1)
            embed = self.no_obj_embed_spatial.reshape(1, 64, 1, 1)
            maskmem_features = maskmem_features + absent * embed
        return maskmem_features, maskmem_pos_enc

    def track_step(
        self,
        frame_idx: int,
        is_init_cond_frame: bool,
        current_vision_feats: List[mx.array],
        current_vision_pos_embeds: List[mx.array],
        feat_sizes: List[Tuple[int, int]],
        point_inputs: Optional[Tuple[mx.array, mx.array]] = None,
        mask_inputs: Optional[mx.array] = None,
        high_res_feats_s0: Optional[mx.array] = None,
        high_res_feats_s1: Optional[mx.array] = None,
        feat_sizes_high_res: Optional[List[Tuple[int, int]]] = None,
        cond_frame_outputs: Optional[Dict[int, dict]] = None,
        non_cond_frame_outputs: Optional[Dict[int, dict]] = None,
    ) -> dict:
        """Single-frame tracking step."""
        if cond_frame_outputs is None:
            cond_frame_outputs = {}
        if non_cond_frame_outputs is None:
            non_cond_frame_outputs = {}

        # Get backbone features
        bb_feats = current_vision_feats[-1].transpose(1, 0, 2).reshape(
            1, feat_sizes[-1][0], feat_sizes[-1][1], -1
        ).transpose(0, 3, 1, 2)

        # Memory-conditioned features
        pix_feat, _, obj_ptr, _ = self._prepare_memory_conditioned_features(
            frame_idx, is_init_cond_frame,
            current_vision_feats, current_vision_pos_embeds, feat_sizes, feat_sizes_high_res,
            cond_frame_outputs, non_cond_frame_outputs,
        )

        if pix_feat is None:
            pix_feat = bb_feats

        is_mem_cond = not is_init_cond_frame and (cond_frame_outputs or non_cond_frame_outputs)

        if self.use_mask_input_as_output_without_sam and mask_inputs is not None and not is_mem_cond:
            pred_masks_high_res = mask_inputs
            iou_pred = mx.ones((1, 1))
            low_res_masks = None
            obj_ptr = self.no_obj_ptr.reshape(1, -1)
            object_score_logits = None
        else:
            # high_res_feats_s0/s1 are already precomputed in forward_image (conv applied there)

            low_res_masks, pred_masks_high_res, iou_pred, obj_ptr, object_score_logits = self._forward_sam_heads(
                pix_feat, [high_res_feats_s0, high_res_feats_s1] if high_res_feats_s0 is not None else None,
                point_inputs=point_inputs if point_inputs is not None else None,
                mask_inputs=mask_inputs if mask_inputs is None else mask_inputs,
                high_res_feats_s0=high_res_feats_s0,
                high_res_feats_s1=high_res_feats_s1,
                multimask_output=self.multimask_output_in_sam,
            )

        if obj_ptr is None:
            obj_ptr = self.no_obj_ptr.reshape(1, -1)

        # Encode memory
        maskmem_features, maskmem_pos_enc = self._encode_new_memory(
            current_vision_feats, feat_sizes, pred_masks_high_res,
            is_mask_from_pts=(point_inputs is not None),
            iou_pred=iou_pred,
            object_score_logits=object_score_logits,
        )

        return {
            "pred_masks": low_res_masks,
            "pred_masks_high_res": pred_masks_high_res,
            "iou_pred": iou_pred,
            "obj_ptr": obj_ptr,
            "object_score_logits": object_score_logits,
            "maskmem_features": maskmem_features,
            "maskmem_pos_enc": maskmem_pos_enc,
        }

    def forward_image(self, img_batch: mx.array):
        """Run image encoder and precompute high-res features."""
        backbone_out = self._get_image_feature(img_batch)
        # Precompute high-res feature projections (s0, s1)
        fpn = backbone_out["backbone_fpn"]
        if len(fpn) >= 3 and self.use_high_res_features_in_sam:
            # fpn[0]: [B, 256, H/4, W/4], fpn[1]: [B, 256, H/8, W/8]
            s0 = fpn[0].transpose(0, 2, 3, 1)
            s0 = self.mask_decoder.conv_s0(s0)  # [B, H/4, W/4, 64]
            s0 = s0.transpose(0, 3, 1, 2)
            backbone_out["high_res_feats_s0"] = s0

            s1 = fpn[1].transpose(0, 2, 3, 1)
            s1 = self.mask_decoder.conv_s1(s1)  # [B, H/8, W/8, 128]
            s1 = s1.transpose(0, 3, 1, 2)
            backbone_out["high_res_feats_s1"] = s1
        return backbone_out
