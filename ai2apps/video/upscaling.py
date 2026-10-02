"""Frame-accurate outer segmentation for bounded video upscaling Workers.

The Worker owns its internal 41-frame windows.  These outer segments only make
long inputs fit the Worker's 60-second/1500-frame request limit.
"""

from __future__ import annotations

import os
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

SUPPORTED_AUDIO = {"aac", "mp3", "alac", "ac3", "eac3"}
MAX_SOURCE_FRAMES = 108_000
MAX_SOURCE_SECONDS = 3_600
LEGACY_MAX_INPUT_SIDE = 512


@dataclass(frozen=True)
class Segment:
    path: Path
    start: int
    frames: int
    overlap: int


@dataclass(frozen=True)
class SourceInfo:
    width: int
    height: int
    fps: Fraction
    frames: int
    segments: tuple[Segment, ...]
    has_audio: bool


def _check_dimensions(width: int, height: int, capabilities: dict | None) -> None:
    if width < 32 or height < 32:
        raise ValueError("Input width and height must each be at least 32 pixels")
    limits = capabilities or {}
    if limits.get("resolution_policy") == "resource_limited":
        return
    # The pre-0.1.1 SoL Worker has a separate 512-per-side guard. Its pixel
    # budget alone cannot describe that guard (a wide, short video may fit it).
    if width > LEGACY_MAX_INPUT_SIDE or height > LEGACY_MAX_INPUT_SIDE:
        raise ValueError("The installed model limits input width and height to 512 pixels")
    maximum_output_pixels = limits.get("maximum_output_pixels")
    if maximum_output_pixels is not None and width * height * 4 > maximum_output_pixels:
        raise ValueError("Input exceeds the installed model's output pixel limit")


def inspect_source(source: Path, *, check: Callable[[], None],
                   capabilities: dict | None = None) -> SourceInfo:
    """Read every presentation timestamp before deciding whether splitting is needed."""
    with av.open(str(source)) as container:
        if len(container.streams.video) != 1:
            raise ValueError("Video must contain exactly one video stream")
        video = container.streams.video[0]
        _check_dimensions(video.width, video.height, capabilities)
        rate = video.average_rate or video.guessed_rate
        if rate is None or not 1 <= float(rate) <= 60:
            raise ValueError("Input must have a constant frame rate of 1–60 fps")
        if len(container.streams.audio) > 1:
            raise ValueError("Only one input audio track is supported")
        if container.streams.audio and container.streams.audio[0].codec_context.name not in SUPPORTED_AUDIO:
            raise ValueError("Input audio codec is unsupported; convert it before upscaling")
        first_time: float | None = None
        count = 0
        for frame in container.decode(video):
            check()
            if frame.pts is None or frame.time is None:
                raise ValueError("Video frames must have timestamps")
            if first_time is None:
                first_time = float(frame.time)
            if abs((float(frame.time) - first_time) - count / float(rate)) > 0.45 / float(rate):
                raise ValueError("Variable-frame-rate video is unsupported; convert to CFR first")
            count += 1
            if count > MAX_SOURCE_FRAMES or count / float(rate) > MAX_SOURCE_SECONDS:
                raise ValueError("Video exceeds the one-hour/108000-frame Host limit")
        if not count:
            raise ValueError("Video contains no frames")
        return SourceInfo(video.width, video.height, rate, count, (), bool(container.streams.audio))


def _encode_segment(path: Path, frames: list[np.ndarray], rate: Fraction) -> None:
    with av.open(str(path), "w", format="mp4") as target:
        stream = target.add_stream("libx264", rate=rate)
        stream.width = frames[0].shape[1]
        stream.height = frames[0].shape[0]
        # Preserve odd input dimensions; the Worker converts decoded frames to RGB.
        stream.pix_fmt = "yuv444p"
        stream.options = {"crf": "16", "preset": "fast"}
        for index, pixels in enumerate(frames):
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            frame.pts = index
            for packet in stream.encode(frame):
                target.mux(packet)
        for packet in stream.encode():
            target.mux(packet)


def split_source(source: Path, directory: Path, *, check: Callable[[], None],
                 capabilities: dict | None = None) -> SourceInfo:
    """Validate CFR media and write bounded, frame-overlapping, silent MP4 parts."""
    directory.mkdir(parents=True, exist_ok=True)
    with av.open(str(source)) as container:
        if len(container.streams.video) != 1:
            raise ValueError("Video must contain exactly one video stream")
        video = container.streams.video[0]
        _check_dimensions(video.width, video.height, capabilities)
        rate = video.average_rate or video.guessed_rate
        if rate is None or not 1 <= float(rate) <= 60:
            raise ValueError("Input must have a constant frame rate of 1–60 fps")
        if len(container.streams.audio) > 1:
            raise ValueError("Only one input audio track is supported")
        if container.streams.audio and container.streams.audio[0].codec_context.name not in SUPPORTED_AUDIO:
            raise ValueError("Input audio codec is unsupported; convert it before upscaling")
        # Avoid buffering 240 full-resolution RGB frames for HD/4K sources.
        input_frame_bytes = video.width * video.height * 3
        output_frame_bytes = input_frame_bytes * 4
        limit = min(1500, max(9, int(float(rate) * 55)), 240,
                    max(9, (512 * 1024 * 1024) // input_frame_bytes))
        overlap = min(17, max(1, limit // 4),
                      max(1, (128 * 1024 * 1024) // output_frame_bytes))
        pending: list[np.ndarray] = []
        segments: list[Segment] = []
        first_time: float | None = None
        count = 0
        start = 0
        for frame in container.decode(video):
            check()
            if frame.pts is None or frame.time is None:
                raise ValueError("Video frames must have timestamps")
            if first_time is None:
                first_time = float(frame.time)
            if abs((float(frame.time) - first_time) - count / float(rate)) > 0.45 / float(rate):
                raise ValueError("Variable-frame-rate video is unsupported; convert to CFR first")
            count += 1
            if count > MAX_SOURCE_FRAMES or count / float(rate) > MAX_SOURCE_SECONDS:
                raise ValueError("Video exceeds the one-hour/108000-frame Host limit")
            pending.append(frame.to_ndarray(format="rgb24"))
            if len(pending) == limit:
                path = directory / f"segment-{len(segments):05d}.mp4"
                _encode_segment(path, pending, rate)
                segments.append(Segment(path, start, len(pending), overlap if segments else 0))
                pending = pending[-overlap:]
                start = count - overlap
        if not count:
            raise ValueError("Video contains no frames")
        if len(pending) > overlap or not segments:
            path = directory / f"segment-{len(segments):05d}.mp4"
            _encode_segment(path, pending, rate)
            segments.append(Segment(path, start, len(pending), overlap if segments else 0))
        return SourceInfo(video.width, video.height, rate, count, tuple(segments), bool(container.streams.audio))


def _remux_original_audio(silent: Path, source: Path, target_path: Path, *, check: Callable[[], None]) -> None:
    with (av.open(str(silent)) as video_source,
          av.open(str(source)) as audio_source,
          av.open(str(target_path), "w", format="mp4") as target):
            video_input = video_source.streams.video[0]
            video_output = target.add_stream_from_template(video_input)
            audio_input = audio_source.streams.audio[0] if audio_source.streams.audio else None
            audio_output = target.add_stream_from_template(audio_input) if audio_input else None
            for packet in video_source.demux(video_input):
                check()
                if packet.dts is not None:
                    packet.stream = video_output
                    target.mux(packet)
            if audio_input is not None:
                original_video = audio_source.streams.video[0]
                video_start = (original_video.start_time or 0) * original_video.time_base
                origin = round(video_start / audio_input.time_base)
                for packet in audio_source.demux(audio_input):
                    check()
                    if packet.dts is None:
                        continue
                    if packet.pts is not None:
                        packet.pts -= origin
                    packet.dts -= origin
                    packet.stream = audio_output
                    target.mux(packet)


def stitch_segments(
    source: Path, outputs: list[Path], info: SourceInfo, destination: Path,
    *, check: Callable[[], None], progress: Callable[[int, int], None] | None = None,
) -> None:
    """Crossfade corresponding overlap frames; keep the original compressed audio."""
    if len(outputs) != len(info.segments):
        raise ValueError("Upscaled segment count does not match the source")
    silent = destination.with_name(destination.stem + "-silent.mp4")
    temporary = destination.with_name(destination.stem + "-partial.mp4")
    emitted = 0
    pending: list[np.ndarray] = []
    try:
        with av.open(str(silent), "w", format="mp4") as target:
            video = target.add_stream("libx264", rate=info.fps)
            video.width, video.height = info.width * 2, info.height * 2
            video.pix_fmt = "yuv420p"
            video.options = {"crf": "18", "preset": "fast"}

            def emit(pixels: np.ndarray) -> None:
                nonlocal emitted
                check()
                frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
                frame.pts = emitted
                for packet in video.encode(frame):
                    target.mux(packet)
                emitted += 1
                if progress and (emitted == 1 or emitted % 30 == 0):
                    progress(emitted, info.frames)

            for number, (path, segment) in enumerate(zip(outputs, info.segments, strict=True)):
                with av.open(str(path)) as part:
                    frames = part.streams.video[0]
                    if frames.width != video.width or frames.height != video.height:
                        raise ValueError("Upscaled segment has the wrong dimensions")
                    produced = 0
                    tail: deque[np.ndarray] = deque()
                    for decoded in part.decode(frames):
                        check()
                        pixels = decoded.to_ndarray(format="rgb24")
                        if produced < segment.overlap:
                            if produced >= len(pending):
                                raise ValueError("Upscaled overlap is incomplete")
                            weight = (produced + 1) / (segment.overlap + 1)
                            mixed = np.rint(pending[produced].astype(np.float32) * (1 - weight) + pixels.astype(np.float32) * weight).astype(np.uint8)
                            emit(mixed)
                        else:
                            tail.append(pixels)
                            if number == len(outputs) - 1 or len(tail) > info.segments[number + 1].overlap:
                                emit(tail.popleft())
                        produced += 1
                    if produced != segment.frames:
                        raise ValueError("Upscaled segment changed the frame count")
                    pending = list(tail)
            if pending:
                raise ValueError("The final overlap was not stitched")
            for packet in video.encode():
                target.mux(packet)
        if emitted != info.frames:
            raise ValueError("Stitched output changed the original frame count")
        if info.has_audio:
            _remux_original_audio(silent, source, temporary, check=check)
            os.replace(temporary, destination)
        else:
            os.replace(silent, destination)
        if progress:
            progress(info.frames, info.frames)
    finally:
        silent.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)
