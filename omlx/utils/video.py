# SPDX-License-Identifier: Apache-2.0
"""Bounded inline video decoding for native VLM input (never fetch URLs)."""

import base64
import binascii
import hashlib
import json
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..exceptions import InvalidRequestError


@dataclass
class VideoInput:
    frames: Any  # uint8 T,C,H,W; already resized before stacking
    timestamps: list[float]
    fps: float
    duration: float
    digest: str


def _invalid(message):
    raise InvalidRequestError(message, field="video_url")


def load_inline_video(value):
    """Accept video_url {url: data:video/...;base64,..., fps, max_frames, max_edge}.

    Sampling is uniform across the whole clip. Bounds apply before decoder
    allocation; only one resized frame is retained per sample. Audio is ignored.
    """
    if not isinstance(value, dict):
        _invalid("video_url must be an object")
    uri = value.get("url", "")
    if (
        not isinstance(uri, str)
        or not uri.startswith("data:video/")
        or ";base64," not in uri
    ):
        _invalid(
            "Video must use a base64 data:video URI; remote URLs and file paths are unsupported"
        )
    if len(uri) > 90_000_000:
        _invalid("Video exceeds the 64 MiB input limit")
    try:
        raw = base64.b64decode(uri.split(",", 1)[1], validate=True)
    except (ValueError, binascii.Error):
        _invalid("Invalid video base64")
    if not raw or len(raw) > 64 * 1024 * 1024:
        _invalid("Video must contain 1 byte to 64 MiB")
    fps = value.get("fps", 2.0)
    count = value.get("max_frames", 32)
    edge = value.get("max_edge", 640)
    if (
        isinstance(fps, bool)
        or not isinstance(fps, (int, float))
        or not math.isfinite(fps)
        or not 0.1 <= fps <= 8
    ):
        _invalid("fps must be between 0.1 and 8")
    if type(count) is not int or not 4 <= count <= 128 or count % 2:
        _invalid("max_frames must be an even integer between 4 and 128")
    if type(edge) is not int or not 128 <= edge <= 960:
        _invalid("max_edge must be an integer between 128 and 960")
    import cv2
    import numpy as np

    with tempfile.TemporaryDirectory(prefix="omlx-video-") as directory:
        path = Path(directory) / "input.video"
        path.write_bytes(raw)
        cap = cv2.VideoCapture(str(path))
        try:
            rate = cap.get(cv2.CAP_PROP_FPS)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width, height = (
                cap.get(cv2.CAP_PROP_FRAME_WIDTH),
                cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
            )
            if (
                not cap.isOpened()
                or not math.isfinite(rate)
                or rate <= 0
                or total < 2
                or not 0 < width * height <= 33_177_600
            ):
                _invalid("Invalid or unsupported video geometry")
            duration = total / rate
            if not math.isfinite(duration) or duration > 600:
                _invalid("Video duration must not exceed 600 seconds")
            n = min(count, max(4, int(math.ceil(duration * fps / 2)) * 2))
            indices = np.linspace(0, total - 1, n).round().astype(int)
            frames = []
            for index in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
                ok, frame = cap.read()
                if not ok:
                    _invalid("Unable to decode a sampled video frame")
                h, w = frame.shape[:2]
                scale = min(1.0, edge / max(h, w))
                frame = cv2.resize(
                    frame, (max(1, round(w * scale)), max(1, round(h * scale)))
                )
                frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).transpose(2, 0, 1))
        finally:
            cap.release()
    timestamps = (indices / rate).tolist()
    frames = np.stack(frames)
    effective_fps = (n - 1) / timestamps[-1] if timestamps[-1] else rate
    digest = hashlib.sha256(
        frames.tobytes() + json.dumps(timestamps).encode()
    ).hexdigest()
    return VideoInput(frames, timestamps, effective_fps, duration, digest)


def extract_video_from_messages(messages):
    videos = []
    for message in messages:
        for part in (
            message.get("content", [])
            if isinstance(message.get("content"), list)
            else []
        ):
            if isinstance(part, dict) and part.get("type") == "video_url":
                if message.get("role") != "user":
                    _invalid("Video input is only supported on user messages")
                videos.append(part.get("video_url"))
    if len(videos) > 1:
        _invalid("Only one video per request is currently supported")
    return load_inline_video(videos[0]) if videos else None
