"""Automatic face tracking and parsing for local mouth refinement."""

from pathlib import Path

import av
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, gaussian_filter1d, maximum_filter

from .face_detection import MLXYuNet
from .face_parsing import FaceParser
from .template import FaceRegion


def mouth_mask(labels):
    """Keep the original upper face and blend only a feathered mouth surround."""
    lips = np.isin(labels, (11, 12, 13))
    if np.count_nonzero(lips) < 8:
        raise ValueError("Mouth parsing failed; use a clear, front-facing portrait")
    # Parser map is 512 square. Leave room for a newly opened mouth while
    # preventing a full-face generative replacement.
    lips = (
        np.asarray(
            Image.fromarray(lips.astype(np.uint8) * 255).resize(
                (256, 256), Image.Resampling.NEAREST
            )
        )
        > 0
    )
    expanded = maximum_filter(lips.astype(np.float32), size=31)
    alpha = gaussian_filter(expanded, 3.0)
    alpha[alpha < 0.002] = 0
    return np.clip(alpha, 0, 1).astype(np.float32)


def prepare_regions(
    source, assets, *, cancel_check=lambda: None, progress=lambda done, total: None
):
    assets = Path(assets)
    detector = MLXYuNet(assets / "yunet")
    boxes = []
    with av.open(str(source)) as media:
        stream = media.streams.video[0]
        total = stream.frames
        width, height = stream.width, stream.height
        for i, frame in enumerate(media.decode(stream)):
            cancel_check()
            rgb = frame.to_ndarray(format="rgb24")
            faces = detector.detect(np.ascontiguousarray(rgb[..., ::-1]))
            if len(faces) != 1:
                raise ValueError(
                    f"Expected one clear face at frame {i}; found {len(faces)}"
                )
            x0, y0, x1, y1 = faces[0].bbox
            fw, fh = x1 - x0, y1 - y0
            boxes.append(
                (
                    max(0, x0 - 0.10 * fw),
                    max(0, y0 - 0.18 * fh),
                    min(width, x1 + 0.10 * fw),
                    min(height, y1 + 0.10 * fh),
                )
            )
            progress(i + 1, 2 * total)
    if not boxes:
        raise ValueError("Video contains no frames")
    boxes = np.rint(gaussian_filter1d(np.asarray(boxes), 1.0, axis=0)).astype(int)
    parser = FaceParser(assets / "bisenet")
    regions = []
    with av.open(str(source)) as media:
        for i, frame in enumerate(media.decode(video=0)):
            cancel_check()
            rgb = frame.to_ndarray(format="rgb24")
            x0, y0, x1, y1 = boxes[i]
            labels = parser.parse(rgb[y0:y1, x0:x1])
            regions.append(
                FaceRegion(tuple(int(x) for x in boxes[i]), mouth_mask(labels))
            )
            progress(len(boxes) + i + 1, 2 * len(boxes))
    # Symmetric 3-frame smoothing keeps the mask from flickering without
    # shifting the video or audio timeline. Process independently per frame.
    masks = [r.mask for r in regions]
    regions = [
        FaceRegion(
            r.box,
            (masks[max(i - 1, 0)] + 2 * masks[i] + masks[min(i + 1, len(masks) - 1)])
            / 4,
        )
        for i, r in enumerate(regions)
    ]
    for r in regions:
        r.validate(width, height)
    return regions
