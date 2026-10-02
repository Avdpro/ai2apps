"""Place animated crops back on a source canvas without person segmentation."""

import numpy as np
from PIL import Image, ImageOps


def load_source_rgb(path, background=(0, 0, 0)):
    """Flatten existing image alpha before detection, cropping or resizing."""
    with Image.open(path) as image:
        if image.width * image.height > 40_000_000:
            raise ValueError("Portrait exceeds 40 million pixels")
        image = ImageOps.exif_transpose(image).convert("RGBA")
        canvas = Image.new("RGBA", image.size, (*background, 255))
        canvas.alpha_composite(image)
        return np.array(canvas.convert("RGB"))


class SourceCanvas:
    """Reusable placement for providers exposing a crop-to-source affine matrix.

    Sizes use (width, height); RGB images use HWC uint8. The fixed inward feather
    blends the crop boundary, not the person's silhouette. All work except the
    output copy is restricted to the transformed crop's intersection with source.
    """

    def __init__(self, source, crop_to_source, crop_size=(512, 512), feather=0.1):
        if source.dtype != np.uint8 or source.ndim != 3 or source.shape[2] != 3:
            raise ValueError("Expected source RGB uint8 HWC image")
        if min(source.shape[:2]) < 1:
            raise ValueError("Source dimensions must be positive")
        if len(crop_size) != 2 or any(int(v) != v or v < 2 for v in crop_size):
            raise ValueError("Crop dimensions must be integers of at least two")
        if not 0 < feather <= 0.5:
            raise ValueError("Feather must be in (0, 0.5]")
        matrix = np.asarray(crop_to_source, dtype=np.float64)
        if matrix.shape == (2, 3):
            matrix = np.vstack((matrix, [0, 0, 1]))
        if (
            matrix.shape != (3, 3)
            or not np.isfinite(matrix).all()
            or not np.allclose(matrix[2], [0, 0, 1])
            or abs(np.linalg.det(matrix[:2, :2])) < 1e-12
        ):
            raise ValueError("Expected finite invertible affine crop-to-source matrix")
        self.source = source.copy()
        self.size = (source.shape[1], source.shape[0])
        self.crop_size = tuple(map(int, crop_size))
        width, height = self.crop_size

        # Premultiplication before interpolation prevents dark borders when a
        # rotated patch extends beyond its support. End pixels have zero alpha.
        def ramp(length):
            distance = np.minimum(np.arange(length), np.arange(length)[::-1])
            t = np.clip(distance / max(1, length * feather), 0, 1)
            return t * t * (3 - 2 * t)

        self.mask = (ramp(height)[:, None] * ramp(width)[None, :]).astype("float32")
        corners = np.array(
            [[0, 0, 1], [width, 0, 1], [0, height, 1], [width, height, 1]]
        )
        bounds = corners @ matrix[:2].T
        low = np.maximum(np.floor(bounds.min(axis=0) - 1), 0)
        high = np.minimum(np.ceil(bounds.max(axis=0) + 1), self.size)
        self.roi = tuple(int(v) for v in (*low, *high))
        x0, y0, x1, y1 = self.roi
        if x1 <= x0 or y1 <= y0:
            raise ValueError("Animated crop does not intersect source canvas")
        self.matrix = matrix[:2].copy()
        self.matrix[:, 2] -= (x0, y0)
        self.roi_size = (x1 - x0, y1 - y0)
        self.alpha = self._warp(self.mask)[..., None]
        self.background = self.source[y0:y1, x0:x1].astype("float32") * (1 - self.alpha)

    def _warp(self, image):
        return warp_affine(image, self.matrix, self.roi_size)

    def compose(self, crop):
        width, height = self.crop_size
        if crop.dtype != np.uint8 or crop.shape != (height, width, 3):
            raise ValueError("Rendered RGB crop must match the declared crop size")
        foreground = self._warp(crop.astype("float32") * self.mask[..., None])
        result = self.source.copy()
        x0, y0, x1, y1 = self.roi
        result[y0:y1, x0:x1] = np.clip(
            np.rint(self.background + foreground), 0, 255
        ).astype("uint8")
        return result


def warp_affine(image, source_to_output, size):
    """Pillow affine sampling; supports uint8 RGB and premultiplied float planes."""
    matrix = np.asarray(source_to_output, dtype=np.float64)
    if matrix.shape == (2, 3):
        matrix = np.vstack((matrix, [0, 0, 1]))
    inverse = np.linalg.inv(matrix)[:2]
    # Pillow coordinates are pixel corners; our matrices use pixel centers.
    inverse[:, 2] += 0.5 - inverse[:, :2] @ np.array([0.5, 0.5])

    def plane(values):
        return np.array(
            Image.fromarray(values).transform(
                tuple(size),
                Image.Transform.AFFINE,
                tuple(inverse.reshape(-1)),
                resample=Image.Resampling.BILINEAR,
                fillcolor=0,
            )
        )

    if image.dtype == np.uint8 or image.ndim == 2:
        return plane(image)
    return np.stack(
        [plane(image[..., channel]) for channel in range(image.shape[2])], axis=-1
    )


def prepare_portrait(path, output_path, size, *, detector=None, crop_scale=3.2):
    """Frame the largest face and persist a model-sized RGB crop for any provider."""
    from .face_detection import detect_faces

    source = load_source_rgb(path)
    if source.shape[0] * source.shape[1] > 40_000_000:
        raise ValueError("Portrait exceeds 40 million pixels")
    faces = (detector or detect_faces)(source)
    if not faces:
        raise ValueError("No face detected; choose a clear portrait")
    x, y, width, height = max(faces, key=lambda box: box[2] * box[3])
    if not np.isfinite([x, y, width, height]).all() or min(width, height) <= 0:
        raise ValueError("Invalid face rectangle")
    side = max(width, height) * crop_scale
    left, top = x + width / 2 - side / 2, y + height * 0.65 - side / 2
    # Preserve the complete crop and its inverse, even at canvas boundaries.
    matrix = np.array([[side / size[0], 0, left], [0, side / size[1], top], [0, 0, 1]])
    canvas = SourceCanvas(source, matrix, size)
    crop = warp_affine(source, np.linalg.inv(matrix), size)
    Image.fromarray(crop).save(output_path)
    return canvas
