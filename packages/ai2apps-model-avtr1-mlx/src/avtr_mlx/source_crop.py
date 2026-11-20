# SPDX-FileCopyrightText: 2026 Goodsize Inc.
# SPDX-License-Identifier: LicenseRef-AVTR-1-Community
# Vendored unchanged from AVTR-1 eb1e5a89ed7bec3debe712b090efd676b3a420bd.
# ruff: noqa: N803, N806

"""Source-image crop pipeline.

Given a portrait image and the 203-point landmarks, this module computes the
512x512 face crop and the crop->original affine ``M_c2o``. The crop region is
defined by a similarity transform that places the eye-center / lip-center
pair at a fixed location in the output, scaled by ``crop_scale`` and offset by
``crop_vy_ratio`` to include forehead.

This is the same math as the reference's ``crop_image`` — the only thing
that's removed is the legacy support for video (last_lmk tracking) and other
landmark counts (we only feed it 203-point arrays).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import acos, cos, sin

import numpy as np

from .image import warp_affine

DTYPE = np.float32


@dataclass(slots=True, frozen=True)
class CropResult:
    img_crop: np.ndarray  # (dsize, dsize, 3) uint8
    M_o2c: np.ndarray  # (3, 3) original -> crop
    M_c2o: np.ndarray  # (3, 3) crop -> original


def _parse_pt2_from_pt106(pts: np.ndarray) -> np.ndarray:
    pt_left_eye = np.mean(pts[[33, 35, 40, 39]], axis=0)
    pt_right_eye = np.mean(pts[[87, 89, 94, 93]], axis=0)
    pt_center_eye = (pt_left_eye + pt_right_eye) / 2
    pt_center_lip = (pts[52] + pts[61]) / 2
    return np.stack([pt_center_eye, pt_center_lip], axis=0)


def _parse_pt2_from_pt203(pts: np.ndarray) -> np.ndarray:
    pt_left_eye = np.mean(pts[[0, 6, 12, 18]], axis=0)
    pt_right_eye = np.mean(pts[[24, 30, 36, 42]], axis=0)
    pt_center_eye = (pt_left_eye + pt_right_eye) / 2
    pt_center_lip = (pts[48] + pts[66]) / 2
    return np.stack([pt_center_eye, pt_center_lip], axis=0)


def _parse_pt2(pts: np.ndarray) -> np.ndarray:
    """Eye-center / lip-center pair from a landmark array. Supports the two
    counts the loader actually uses (106 and 203)."""
    n = pts.shape[0]
    if n == 106:
        return _parse_pt2_from_pt106(pts)
    if n == 203:
        return _parse_pt2_from_pt203(pts)
    raise ValueError(f"Unsupported landmark count: {n}")


def _parse_rect_from_landmark(
    pts: np.ndarray,
    *,
    scale: float,
    vx_ratio: float,
    vy_ratio: float,
    need_square: bool = True,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Compute (center, size, angle) of the aligned bounding rect.

    Bit-exact replica of the reference's helper for these landmark counts.
    """
    pt2 = _parse_pt2(pts)
    uy = pt2[1] - pt2[0]
    L = float(np.linalg.norm(uy))
    uy = np.array([0, 1], dtype=DTYPE) if L <= 1e-3 else uy / L
    ux = np.array((uy[1], -uy[0]), dtype=DTYPE)

    angle = acos(float(ux[0]))
    if ux[1] < 0:
        angle = -angle

    M = np.array([ux, uy])
    center0 = np.mean(pts, axis=0)
    rpts = (pts - center0) @ M.T
    lt_pt = np.min(rpts, axis=0)
    rb_pt = np.max(rpts, axis=0)
    center1 = (lt_pt + rb_pt) / 2

    size = rb_pt - lt_pt
    if need_square:
        m = float(max(size[0], size[1]))
        size = np.array([m, m], dtype=DTYPE)

    size = size * scale
    center = center0 + ux * center1[0] + uy * center1[1]
    center = center + ux * (vx_ratio * size) + uy * (vy_ratio * size)

    return center.astype(DTYPE), size.astype(DTYPE), float(angle)


def _estimate_similar_transform_from_pts(
    pts: np.ndarray,
    *,
    dsize: int,
    scale: float,
    vx_ratio: float,
    vy_ratio: float,
    flag_do_rot: bool,
) -> np.ndarray:
    center, size, angle = _parse_rect_from_landmark(
        pts, scale=scale, vx_ratio=vx_ratio, vy_ratio=vy_ratio
    )
    s = dsize / size[0]
    tcx, tcy = dsize / 2, dsize / 2
    cx, cy = center[0], center[1]

    if flag_do_rot:
        ct, st = cos(angle), sin(angle)
        M_INV = np.array(
            [
                [s * ct, s * st, tcx - s * (ct * cx + st * cy)],
                [-s * st, s * ct, tcy - s * (-st * cx + ct * cy)],
            ],
            dtype=DTYPE,
        )
    else:
        M_INV = np.array([[s, 0, tcx - s * cx], [0, s, tcy - s * cy]], dtype=DTYPE)
    return M_INV


def crop_image(
    img_rgb: np.ndarray,
    pts: np.ndarray,
    *,
    dsize: int,
    scale: float = 1.5,
    vx_ratio: float = 0.0,
    vy_ratio: float = -0.1,
    flag_do_rot: bool = True,
) -> CropResult:
    """Crop ``img_rgb`` around ``pts`` into a ``dsize x dsize`` aligned face.

    Returns the crop, the original->crop affine, and its inverse.
    """
    M_INV = _estimate_similar_transform_from_pts(
        pts,
        dsize=dsize,
        scale=scale,
        vx_ratio=vx_ratio,
        vy_ratio=vy_ratio,
        flag_do_rot=flag_do_rot,
    )
    img_crop = warp_affine(img_rgb, M_INV, (dsize, dsize))

    M_o2c = np.vstack([M_INV, np.array([0, 0, 1], dtype=DTYPE)])
    M_c2o = np.linalg.inv(M_o2c).astype(DTYPE)
    return CropResult(img_crop=img_crop, M_o2c=M_o2c, M_c2o=M_c2o)


def get_default_mask(
    W: int = 512, H: int = 512, ratio_w: float = 0.9, ratio_h: float = 0.9
) -> np.ndarray:
    """Smooth feathered mask for paste-back.

    Bit-exact replica of ``core.utils.get_mask`` from the reference. Returns
    a (H, W, 1) float32 array in [0, 1] with rounded-corner falloff. The
    caller usually triplicates it across the channel axis for compatibility
    with the reference's mask format.
    """
    w = int(W * ratio_w)
    h = int(H * ratio_h)
    x1 = (W - w) // 2
    x2 = x1 + w
    y1 = (H - h) // 2
    y2 = y1 + h

    mask = np.ones((H, W), dtype=np.float32)

    # top edge: gradient from 0 (top) to 1 (interior)
    col = np.linspace(0, 1, y1, dtype=np.float32)[:, None]
    mask[0:y1, x1:x2] = np.broadcast_to(col, (y1, w)).copy()

    # bottom edge: gradient from 1 (interior) to 0 (bottom)
    col_b = np.linspace(1, 0, H - y2, dtype=np.float32)[:, None]
    mask[y2:H, x1:x2] = np.broadcast_to(col_b, (H - y2, w)).copy()

    # left edge: gradient from 0 (left) to 1 (interior)
    row = np.linspace(0, 1, x1, dtype=np.float32)[None, :]
    mask[y1:y2, 0:x1] = np.broadcast_to(row, (h, x1)).copy()

    # right edge: gradient from 1 (interior) to 0 (right)
    row_r = np.linspace(1, 0, W - x2, dtype=np.float32)[None, :]
    mask[y1:y2, x2:W] = np.broadcast_to(row_r, (h, W - x2)).copy()

    # corners: 1 - clip(sqrt(...), 0, 1)
    row_tl = np.linspace(1, 0, x1, dtype=np.float32)[None, :]
    col_tl = np.linspace(1, 0, y1, dtype=np.float32)[:, None]
    grad_tl = np.sqrt(row_tl**2 + col_tl**2).astype(np.float32)
    mask[0:y1, 0:x1] = 1 - np.clip(grad_tl, 0, 1)

    row_tr = np.linspace(0, 1, W - x2, dtype=np.float32)[None, :]
    col_tr = np.linspace(1, 0, y1, dtype=np.float32)[:, None]
    grad_tr = np.sqrt(row_tr**2 + col_tr**2).astype(np.float32)
    mask[0:y1, x2:W] = 1 - np.clip(grad_tr, 0, 1)

    row_bl = np.linspace(1, 0, x1, dtype=np.float32)[None, :]
    col_bl = np.linspace(0, 1, H - y2, dtype=np.float32)[:, None]
    grad_bl = np.sqrt(row_bl**2 + col_bl**2).astype(np.float32)
    mask[y2:H, 0:x1] = 1 - np.clip(grad_bl, 0, 1)

    row_br = np.linspace(0, 1, W - x2, dtype=np.float32)[None, :]
    col_br = np.linspace(0, 1, H - y2, dtype=np.float32)[:, None]
    grad_br = np.sqrt(row_br**2 + col_br**2).astype(np.float32)
    mask[y2:H, x2:W] = 1 - np.clip(grad_br, 0, 1)

    return mask[:, :, None]
