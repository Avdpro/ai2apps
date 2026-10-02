"""Tiny OpenCV compatibility subset used by the vendored SAM 2.1 MLX port.

The signed oMLX Runtime intentionally does not ship OpenCV.  Keeping this
pure-Python shim in the Package avoids adding a large native wheel merely for
resize and connected-component operations.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage

INTER_LINEAR = 1
INTER_CUBIC = 2
CC_STAT_LEFT = 0
CC_STAT_TOP = 1
CC_STAT_WIDTH = 2
CC_STAT_HEIGHT = 3
CC_STAT_AREA = 4


def resize(source, dsize, interpolation=INTER_LINEAR):
    width, height = (int(dsize[0]), int(dsize[1]))
    array = np.asarray(source)
    if array.ndim not in {2, 3} or width < 1 or height < 1:
        raise ValueError("resize expects a 2D/3D array and positive dimensions")
    mode = Image.Resampling.BICUBIC if interpolation == INTER_CUBIC else Image.Resampling.BILINEAR
    dtype = array.dtype
    if array.ndim == 2 and np.issubdtype(dtype, np.floating):
        result = np.asarray(Image.fromarray(array.astype(np.float32), mode="F").resize((width, height), mode))
    else:
        result = np.asarray(Image.fromarray(array).resize((width, height), mode))
    return result.astype(dtype, copy=False)


def connectedComponentsWithStats(source, connectivity=8):  # noqa: N802 - cv2 API
    binary = np.asarray(source) != 0
    structure = ndimage.generate_binary_structure(2, 1 if connectivity == 4 else 2)
    labels, count = ndimage.label(binary, structure=structure)
    stats = np.zeros((count + 1, 5), dtype=np.int32)
    centroids = np.zeros((count + 1, 2), dtype=np.float64)
    for label in range(count + 1):
        ys, xs = np.nonzero(labels == label)
        if xs.size:
            stats[label] = (xs.min(), ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1, xs.size)
            centroids[label] = (xs.mean(), ys.mean())
    return count + 1, labels.astype(np.int32), stats, centroids
