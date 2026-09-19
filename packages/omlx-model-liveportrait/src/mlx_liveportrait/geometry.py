"""Face alignment and compositing helpers for the MLX experiment."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_erosion, gaussian_filter

from .media import resize_float, warp_affine_bgr, warp_affine_float

ARCFACE_112 = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def alignment_template(size: int) -> np.ndarray:
    if size % 112 == 0:
        ratio = size / 112.0
        offset_x = 0.0
    elif size % 128 == 0:
        ratio = size / 128.0
        offset_x = 8.0 * ratio
    else:
        raise ValueError("alignment size must be divisible by 112 or 128")
    result = ARCFACE_112 * ratio
    result[:, 0] += offset_x
    return result


def estimate_similarity(landmarks: np.ndarray, size: int) -> np.ndarray:
    points = np.asarray(landmarks, dtype=np.float32)
    if points.shape != (5, 2):
        raise ValueError(f"expected five 2D landmarks, got {points.shape}")
    target = alignment_template(size).astype(np.float64)
    source = points.astype(np.float64)
    rows = np.empty((source.shape[0] * 2, 4), dtype=np.float64)
    values = np.empty(source.shape[0] * 2, dtype=np.float64)
    rows[0::2] = np.column_stack(
        (source[:, 0], -source[:, 1], np.ones(5), np.zeros(5))
    )
    rows[1::2] = np.column_stack(
        (source[:, 1], source[:, 0], np.zeros(5), np.ones(5))
    )
    values[0::2] = target[:, 0]
    values[1::2] = target[:, 1]
    a, b, translate_x, translate_y = np.linalg.lstsq(rows, values, rcond=None)[0]
    return np.asarray(
        ((a, -b, translate_x), (b, a, translate_y)), dtype=np.float32
    )


def align_face(
    image_bgr: np.ndarray, landmarks: np.ndarray, size: int
) -> tuple[np.ndarray, np.ndarray]:
    matrix = estimate_similarity(landmarks, size)
    crop = warp_affine_bgr(image_bgr, matrix, (size, size))
    return crop, matrix


def paste_face(
    target_bgr: np.ndarray,
    swapped_crop_bgr: np.ndarray,
    target_to_crop: np.ndarray,
    *,
    aligned_face_mask: np.ndarray | None = None,
    erosion_fraction: float = 0.08,
    blur_fraction: float = 0.04,
) -> np.ndarray:
    """Warp an aligned swap back with a conservative soft oval mask."""
    height, width = swapped_crop_bgr.shape[:2]
    yy, xx = np.ogrid[:height, :width]
    center = (width / 2.0, height / 2.0)
    axes = (width * 0.43, height * 0.47)
    mask = (
        ((xx - center[0]) / axes[0]) ** 2
        + ((yy - center[1]) / axes[1]) ** 2
        <= 1.0
    ).astype(np.float32)
    erode = max(1, int(min(height, width) * erosion_fraction))
    mask = binary_erosion(mask > 0, structure=np.ones((erode, erode))).astype(
        np.float32
    )
    blur = max(3, int(min(height, width) * blur_fraction) | 1)
    sigma = 0.3 * ((blur - 1) * 0.5 - 1) + 0.8
    mask = gaussian_filter(mask, sigma=sigma)
    if aligned_face_mask is not None:
        semantic = resize_float(
            np.asarray(aligned_face_mask, dtype=np.float32), (width, height)
        )
        semantic = gaussian_filter(semantic, sigma=sigma)
        mask *= np.clip(semantic, 0.0, 1.0)

    crop_to_target = np.linalg.inv(
        np.vstack((target_to_crop, (0.0, 0.0, 1.0)))
    )[:2]
    output_size = (target_bgr.shape[1], target_bgr.shape[0])
    warped = warp_affine_bgr(swapped_crop_bgr, crop_to_target, output_size).astype(
        np.float32
    )
    warped_mask = warp_affine_float(mask, crop_to_target, output_size)[..., None]
    merged = warped * warped_mask + target_bgr.astype(np.float32) * (1.0 - warped_mask)
    return np.clip(merged, 0, 255).astype(np.uint8)
