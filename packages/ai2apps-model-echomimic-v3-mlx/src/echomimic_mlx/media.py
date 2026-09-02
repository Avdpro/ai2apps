"""Image, audio, frame, and Runtime-provided PyAV integration."""

from __future__ import annotations

import math
import os
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import av
import numpy as np
import numpy.typing as npt
import pyloudnorm as pyln  # type: ignore[import-untyped]
import soundfile as sf  # type: ignore[import-untyped]
from PIL import Image

FloatArray = npt.NDArray[np.float32]
UInt8Array = npt.NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class PreparedImage:
    """Fixed-size RGB image plus the VAE masked-video and mask inputs."""

    rgb: UInt8Array
    masked_video: FloatArray
    mask: FloatArray


@dataclass(frozen=True, slots=True)
class AudioSegments:
    paths: tuple[Path, ...]
    total_frames: int
    stride_frames: int


@contextmanager
def temporary_audio_segments(
    path: str | Path,
    *,
    fps: int = 25,
    sampling_rate: int = 16_000,
    window_frames: int = 81,
    stride_frames: int = 80,
) -> Iterator[AudioSegments]:
    """Create fixed-size overlapping WAV windows for bounded long-video inference."""

    if fps <= 0 or window_frames <= 0 or not 0 < stride_frames < window_frames:
        raise ValueError("audio segmentation requires positive frames and an overlapping stride")
    values, actual_rate = sf.read(Path(path).expanduser(), dtype="float32", always_2d=True)
    if actual_rate != sampling_rate:
        raise ValueError(f"audio sampling rate is {actual_rate}, expected {sampling_rate}")
    mono: FloatArray = np.asarray(np.mean(values, axis=1, dtype=np.float32), dtype=np.float32)
    total_frames = int(mono.size / sampling_rate * fps)
    if total_frames <= 0:
        raise ValueError("audio is too short to produce one video frame")
    window_samples = int(window_frames / fps * sampling_rate)
    starts = range(0, max(total_frames - 1, 1), stride_frames)
    with tempfile.TemporaryDirectory(prefix="echomimic-audio-segments-") as directory:
        paths: list[Path] = []
        for index, start_frame in enumerate(starts):
            start_sample = int(start_frame / fps * sampling_rate)
            segment = mono[start_sample : start_sample + window_samples]
            if segment.size < window_samples:
                segment = np.pad(segment, (0, window_samples - segment.size))
            segment_path = Path(directory) / f"segment-{index:04d}.wav"
            sf.write(segment_path, segment, sampling_rate, subtype="FLOAT")
            paths.append(segment_path)
        yield AudioSegments(tuple(paths), total_frames, stride_frames)


def reference_sample_size(
    image: Image.Image, maximum: tuple[int, int] = (512, 512)
) -> tuple[int, int]:
    """Match upstream's area-preserving size calculation and 16-pixel rounding."""

    width, height = image.size
    original_area = width * height
    maximum_area = maximum[0] * maximum[1]
    if maximum_area < original_area:
        ratio = math.sqrt(original_area / maximum_area)
        width = int(width / ratio // 16 * 16)
        height = int(height / ratio // 16 * 16)
    else:
        width = width // 16 * 16
        height = height // 16 * 16
    if width <= 0 or height <= 0:
        raise ValueError("image is too small after 16-pixel size alignment")
    return height, width


def prepare_reference_image(
    path: str | Path,
    *,
    num_frames: int = 81,
    size: tuple[int, int] = (512, 512),
) -> PreparedImage:
    """Load one RGB image and construct upstream's single-start-frame VAE inputs."""

    if num_frames <= 0:
        raise ValueError("number of image-conditioning frames must be positive")
    with Image.open(Path(path).expanduser()) as source:
        image = source.convert("RGB").resize((size[1], size[0]), Image.Resampling.LANCZOS)
        rgb = np.asarray(image, dtype=np.uint8).copy()
    normalized = rgb.astype(np.float32) / np.float32(127.5) - np.float32(1.0)
    masked_video = np.zeros((1, 3, num_frames, size[0], size[1]), dtype=np.float32)
    masked_video[0, :, 0] = np.transpose(normalized, (2, 0, 1))
    mask = np.ones((1, 1, num_frames, size[0], size[1]), dtype=np.float32)
    mask[:, :, 0] = 0.0
    return PreparedImage(rgb=rgb, masked_video=masked_video, mask=mask)


def load_reference_audio(
    path: str | Path,
    *,
    num_frames: int = 81,
    fps: int = 25,
    sampling_rate: int = 16_000,
    target_lufs: float = -23.0,
) -> FloatArray:
    """Decode mono 16 kHz audio, crop it to the video, and apply upstream loudness normalization."""

    values, actual_rate = sf.read(Path(path).expanduser(), dtype="float32", always_2d=True)
    if actual_rate != sampling_rate:
        raise ValueError(f"audio sampling rate is {actual_rate}, expected {sampling_rate}")
    if values.shape[1] != 1:
        values = np.mean(values, axis=1, keepdims=True, dtype=np.float32)
    waveform = np.ascontiguousarray(values[:, 0])
    required = int(num_frames / fps * sampling_rate)
    if waveform.size < required:
        raise ValueError(f"audio has {waveform.size} samples, but {required} are required")
    waveform = waveform[:required]
    meter = pyln.Meter(sampling_rate)
    loudness = float(meter.integrated_loudness(waveform))
    if abs(loudness) <= 100:
        waveform = pyln.normalize.loudness(waveform, loudness, target_lufs)
    return np.asarray(waveform, dtype=np.float32)


def frames_to_uint8(frames: npt.ArrayLike) -> UInt8Array:
    """Convert `[frames,height,width,channels]` values in `[-1,1]` to RGB bytes."""

    values = np.asarray(frames, dtype=np.float32)
    if values.ndim != 4 or values.shape[-1] != 3:
        raise ValueError("video frames must have shape [frames, height, width, 3]")
    values = np.clip((values + 1.0) * 127.5, 0.0, 255.0)
    return np.rint(values).astype(np.uint8)


def write_mp4_with_audio(
    frames: npt.ArrayLike,
    audio_path: str | Path,
    output_path: str | Path,
    *,
    fps: int = 25,
    ffmpeg: str | None = None,
) -> Path:
    """Encode one evaluated RGB array through the Runtime's PyAV codecs."""

    del ffmpeg
    return write_mp4_chunks_with_audio((frames,), audio_path, output_path, fps=fps)


def write_mp4_chunks_with_audio(
    chunks: Iterable[npt.ArrayLike],
    audio_path: str | Path,
    output_path: str | Path,
    *,
    fps: int = 25,
    ffmpeg: str | None = None,
) -> Path:
    """Incrementally encode RGB chunks with PyAV and atomically commit the MP4."""

    del ffmpeg
    iterator = iter(chunks)
    try:
        first = np.ascontiguousarray(frames_to_uint8(next(iterator)))
    except StopIteration as error:
        raise ValueError("at least one video frame chunk is required") from error
    height, width = first.shape[1:3]
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}.", suffix=".tmp.mp4", dir=destination.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
    try:
        frame_count = 0
        samples, sample_rate = sf.read(
            Path(audio_path).expanduser(), dtype="float32", always_2d=True
        )
        mono_source = np.mean(samples, axis=1, dtype=np.float32)
        with av.open(str(temporary), "w", format="mp4", options={"movflags": "+faststart"}) as container:
            video = container.add_stream("libx264", rate=fps)
            video.width = width
            video.height = height
            video.pix_fmt = "yuv420p"
            video.options = {"crf": "23", "preset": "medium"}
            audio = container.add_stream("aac", rate=sample_rate)
            audio.layout = "mono"

            def encode_chunk(rgb: UInt8Array) -> None:
                nonlocal frame_count
                if rgb.shape[1:3] != (height, width):
                    raise ValueError("all video frame chunks must use the same dimensions")
                for pixels in rgb:
                    frame_count += 1
                    for packet in video.encode(
                        av.VideoFrame.from_ndarray(
                            np.ascontiguousarray(pixels), format="rgb24"
                        )
                    ):
                        container.mux(packet)

            encode_chunk(first)
            for chunk in iterator:
                encode_chunk(np.ascontiguousarray(frames_to_uint8(chunk)))
            for packet in video.encode():
                container.mux(packet)

            mono = np.ascontiguousarray(
                mono_source[: int(frame_count / fps * sample_rate)], dtype=np.float32
            )
            for offset in range(0, mono.size, 1024):
                values = np.ascontiguousarray(mono[offset : offset + 1024][None, :])
                audio_frame = av.AudioFrame.from_ndarray(
                    values, format="fltp", layout="mono"
                )
                audio_frame.sample_rate = sample_rate
                for packet in audio.encode(audio_frame):
                    container.mux(packet)
            for packet in audio.encode():
                container.mux(packet)
        with temporary.open("rb") as encoded:
            os.fsync(encoded.fileno())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
