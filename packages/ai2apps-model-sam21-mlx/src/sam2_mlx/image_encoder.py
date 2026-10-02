"""Image encoder for SAM2: FPN neck + ImageEncoder wrapper, ported to MLX."""

from typing import List, Optional

import mlx.core as mx
import mlx.nn as nn


class FpnNeck(nn.Module):
    """Feature Pyramid Network neck with lateral 1x1 convs and top-down fusion."""

    def __init__(
        self,
        position_encoding: nn.Module,
        d_model: int,
        backbone_channel_list: List[int],
        fpn_top_down_levels: Optional[List[int]] = None,
        fpn_interp_model: str = "nearest",
    ):
        super().__init__()
        self.position_encoding = position_encoding
        self.backbone_channel_list = backbone_channel_list

        self.convs = []
        for dim in backbone_channel_list:
            conv = nn.Conv2d(dim, d_model, kernel_size=1, stride=1, padding=0)
            self.convs.append(conv)

        if fpn_top_down_levels is None:
            fpn_top_down_levels = list(range(len(self.convs)))
        self.fpn_top_down_levels = list(fpn_top_down_levels)

        # PT yaml uses `fpn_interp_model: nearest`. The previous default
        # ('linear') produced different top-down features and silently
        # broke parity with the official checkpoint.
        self._upsample = nn.Upsample(scale_factor=2.0, mode=fpn_interp_model)

    def __call__(self, xs: List[mx.array]):
        """xs: list of [B, C_i, H_i, W_i] (channels-first) from Hiera.
        Returns: (features, pos_enc) — both lists of [B, d_model, H, W].
        """
        out = [None] * len(self.convs)
        pos = [None] * len(self.convs)
        prev_features = None
        n = len(self.convs) - 1

        for i in range(n, -1, -1):
            x = xs[i]
            # Lateral conv: channels-first [B, C, H, W] → [B, H, W, C] → conv → [B, H', W', d_model]
            x_cl = x.transpose(0, 2, 3, 1)  # → [B, H, W, C]
            lateral = self.convs[n - i](x_cl)  # [B, H, W, d_model]

            if i in self.fpn_top_down_levels and prev_features is not None:
                # Top-down: upsample prev → add
                # nn.Upsample expects channels-last [B, H, W, C]
                td = self._upsample(prev_features)
                prev_features = lateral + td.astype(lateral.dtype)
            else:
                prev_features = lateral

            # Back to channels-first for output
            x_out = prev_features.transpose(0, 3, 1, 2)  # [B, d_model, H, W]
            out[i] = x_out
            pos[i] = self.position_encoding(x_out).astype(x_out.dtype)

        return out, pos


class ImageEncoder(nn.Module):
    """Wraps Hiera trunk + FPN neck."""

    def __init__(self, trunk: nn.Module, neck: FpnNeck, scalp: int = 1):
        super().__init__()
        self.trunk = trunk
        self.neck = neck
        self.scalp = scalp

    def __call__(self, sample: mx.array):
        """
        Args:
            sample: [B, 3, H, W] (channels-first, [-1, 1])
        Returns:
            dict with: vision_features [B, d_model, H_low, W_low],
                       vision_pos_enc [B, d_model, H_low, W_low],
                       backbone_fpn: list of [B, d_model, H, W]
        """
        trunk_outs = self.trunk(sample)  # list of [B, C, H, W]
        features, pos = self.neck(trunk_outs)

        if self.scalp > 0:
            features = features[: -self.scalp]
            pos = pos[: -self.scalp]

        return {
            "vision_features": features[-1],
            "vision_pos_enc": pos,
            "backbone_fpn": features,
        }
