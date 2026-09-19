from pathlib import Path

import numpy as np

from experiments.mlx_faceswap.media import (
    blob_from_bgr,
    read_image_bgr,
    resize_bgr,
    warp_affine_bgr,
    write_image_bgr,
)


def test_image_round_trip_and_resize_without_opencv(tmp_path: Path):
    image = np.zeros((8, 10, 3), dtype=np.uint8)
    image[..., 0] = 17
    image[..., 1] = 91
    image[..., 2] = 203
    path = tmp_path / "sample.png"
    write_image_bgr(path, image)
    np.testing.assert_array_equal(read_image_bgr(path), image)
    assert resize_bgr(image, (5, 4)).shape == (4, 5, 3)


def test_blob_channel_order_and_normalization():
    bgr = np.array([[[10, 20, 30]]], dtype=np.uint8)
    rgb_blob = blob_from_bgr(bgr, (1, 1), scale=0.5, mean=10, swap_rb=True)
    bgr_blob = blob_from_bgr(bgr, (1, 1), swap_rb=False)
    np.testing.assert_array_equal(rgb_blob, [[[[10]], [[5]], [[0]]]])
    np.testing.assert_array_equal(bgr_blob, [[[[10]], [[20]], [[30]]]])


def test_identity_warp_preserves_image():
    image = np.arange(9 * 7 * 3, dtype=np.uint8).reshape(9, 7, 3)
    matrix = np.array(((1, 0, 0), (0, 1, 0)), dtype=np.float32)
    np.testing.assert_array_equal(warp_affine_bgr(image, matrix, (7, 9)), image)
