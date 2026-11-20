"""Bounded local media decoding for MiniMax-H3 Ref2VA requests."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .packing import CANVAS_MULTIPLE, FPS, MAX_PIXELS, align_num_frames

REFERENCE_IMAGE_SHORT_EDGE = 2048
AUDIO_SAMPLE_RATE = 32000
MIN_REFERENCE_SECONDS = 2.0
MAX_REFERENCE_SECONDS = 15.0


@dataclass(frozen=True)
class ReferenceInput:
    """One decoded Ref2VA item; tuple order is part of the model contract."""

    kind: str
    frames: tuple[Image.Image, ...] = ()
    audio: np.ndarray | None = None  # (2, samples), float32 at 32 kHz

    def __post_init__(self) -> None:
        if self.kind not in {"image", "video", "audio"}:
            raise ValueError(f"Unsupported reference kind: {self.kind!r}")
        if self.kind == "image" and len(self.frames) != 1:
            raise ValueError("An image reference must contain one frame")
        if self.kind == "video" and not self.frames:
            raise ValueError("A video reference must contain frames")
        if self.kind == "audio" and (self.frames or self.audio is None):
            raise ValueError("An audio reference must contain only audio")
        if self.kind == "image" and self.audio is not None:
            raise ValueError("An image reference cannot carry audio")


def _rounded_axis(value: float) -> int:
    return max(CANVAS_MULTIPLE, round(value / CANVAS_MULTIPLE) * CANVAS_MULTIPLE)


def reference_image_canvas(
    width: int,
    height: int,
    *,
    target_width: int,
    target_height: int,
    size: str = "match",
) -> tuple[int, int]:
    if size == "match":
        scale = min(1.0, math.sqrt((target_width * target_height) / (width * height)))
    elif size == "max":
        scale = min(1.0, REFERENCE_IMAGE_SHORT_EDGE / min(width, height))
    else:
        raise ValueError(f"Unsupported reference image size policy: {size}")
    return _rounded_axis(width * scale), _rounded_axis(height * scale)


def reference_video_canvas(width: int, height: int) -> tuple[int, int]:
    ratio = width / height
    if ratio >= 1.0:
        target_width, target_height = 768 * ratio, 768.0
    else:
        target_width, target_height = 768.0, 768 / ratio
    if target_width * target_height > MAX_PIXELS:
        scale = math.sqrt(MAX_PIXELS / (target_width * target_height))
        target_width *= scale
        target_height *= scale
    if width * height < target_width * target_height:
        target_width, target_height = width, height
    return _rounded_axis(target_width), _rounded_axis(target_height)


def load_image(path: str | Path, *, target_width: int, target_height: int, size: str = "match") -> ReferenceInput:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        width, height = reference_image_canvas(
            *image.size, target_width=target_width, target_height=target_height, size=size
        )
        if image.size != (width, height):
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        image.load()
    return ReferenceInput("image", (image.copy(),))


def _stream_duration_seconds(stream) -> float | None:
    if stream.duration is None:
        return None
    return float(stream.duration * stream.time_base)


def _decode_audio(path: str | Path, *, max_seconds: float = MAX_REFERENCE_SECONDS) -> np.ndarray:
    import av

    pieces: list[np.ndarray] = []
    limit = round(max_seconds * AUDIO_SAMPLE_RATE)
    with av.open(str(path)) as container:
        streams = [stream for stream in container.streams if stream.type == "audio"]
        if not streams:
            raise ValueError("Reference media has no audio stream")
        stream = streams[0]
        resampler = av.AudioResampler(format="fltp", layout="stereo", rate=AUDIO_SAMPLE_RATE)
        count = 0
        for frame in container.decode(stream):
            converted = resampler.resample(frame)
            if converted is None:
                continue
            if not isinstance(converted, list):
                converted = [converted]
            for item in converted:
                chunk = np.asarray(item.to_ndarray(), dtype=np.float32)
                if chunk.ndim == 1:
                    chunk = chunk[None]
                if chunk.shape[0] == 1:
                    chunk = np.repeat(chunk, 2, axis=0)
                chunk = chunk[:2, : max(0, limit - count)]
                if chunk.size:
                    pieces.append(chunk)
                    count += chunk.shape[1]
                if count >= limit:
                    break
            if count >= limit:
                break
    if not pieces:
        raise ValueError("Reference audio could not be decoded")
    return np.ascontiguousarray(np.concatenate(pieces, axis=1), dtype=np.float32)


def load_audio(path: str | Path) -> ReferenceInput:
    audio = _decode_audio(path)
    seconds = audio.shape[1] / AUDIO_SAMPLE_RATE
    if seconds < MIN_REFERENCE_SECONDS:
        raise ValueError(f"Reference audio must be at least {MIN_REFERENCE_SECONDS:g} seconds")
    return ReferenceInput("audio", audio=audio)


def load_video(
    path: str | Path,
    *,
    max_frames: int,
    include_audio: bool = True,
) -> ReferenceInput:
    import av

    frames: list[Image.Image] = []
    with av.open(str(path)) as container:
        streams = [stream for stream in container.streams if stream.type == "video"]
        if not streams:
            raise ValueError("Reference media has no video stream")
        stream = streams[0]
        width, height = reference_video_canvas(stream.codec_context.width, stream.codec_context.height)
        duration = _stream_duration_seconds(stream)
        if duration is not None and duration < MIN_REFERENCE_SECONDS:
            raise ValueError(f"Reference video must be at least {MIN_REFERENCE_SECONDS:g} seconds")
        target_time = 0.0
        previous = None
        previous_time = 0.0
        for frame in container.decode(stream):
            current_time = float(frame.pts * stream.time_base) if frame.pts is not None else target_time
            current = frame.reformat(width=width, height=height, format="rgb24").to_image()
            while target_time <= current_time + 1e-9 and len(frames) < max_frames:
                chosen = current
                if previous is not None and abs(previous_time - target_time) <= abs(current_time - target_time):
                    chosen = previous
                frames.append(chosen.copy())
                target_time = len(frames) / FPS
            previous, previous_time = current, current_time
            if len(frames) >= max_frames or current_time >= MAX_REFERENCE_SECONDS:
                break
    if len(frames) < round(MIN_REFERENCE_SECONDS * FPS):
        raise ValueError(f"Reference video must provide at least {MIN_REFERENCE_SECONDS:g} seconds at {FPS} fps")
    # Ref2VA visual latents use the same 17n+5 ladder, rounded down for references.
    count = min(len(frames), max_frames)
    while count >= 5 and count % 17 != 5:
        count -= 1
    if count < 5:
        raise ValueError("Reference video is too short for the H3 latent frame ladder")
    frames = frames[:count]
    audio = None
    if include_audio:
        try:
            audio = _decode_audio(path, max_seconds=count / FPS)
        except ValueError as exc:
            if "no audio stream" not in str(exc):
                raise
    return ReferenceInput("video", tuple(frames), audio)


def target_frame_limit(duration_seconds: float) -> int:
    return align_num_frames(round(duration_seconds * FPS))
