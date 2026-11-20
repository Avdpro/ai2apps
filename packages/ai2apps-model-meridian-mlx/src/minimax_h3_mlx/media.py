"""Writing MiniMax-H3 output to files.

Deliberately dependency-free: stereo WAV goes through the standard library's ``wave`` module and
video is piped as raw RGB frames into the ``ffmpeg`` binary, so the port needs no imageio,
soundfile or torchvision. If ``ffmpeg`` is absent the frames can still be written as a PNG
sequence.
"""

from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np


def save_wav(path: str | Path, audio: np.ndarray, sample_rate: int) -> Path:
    """Write ``(channels, samples)`` float audio in ``[-1, 1]`` as 16-bit PCM."""
    path = Path(path)
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 1:
        audio = audio[None]
    clipped = np.clip(audio, -1.0, 1.0)
    # Interleave channels, which is what WAV expects.
    pcm = (clipped.T * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(audio.shape[0])
        fh.setsampwidth(2)
        fh.setframerate(int(sample_rate))
        fh.writeframes(pcm.tobytes())
    return path


def save_mp4(
    path: str | Path,
    video: np.ndarray,
    fps: int,
    audio: np.ndarray | None = None,
    sample_rate: int = 32000,
    crf: int = 18,
) -> Path:
    """Encode ``(frames, height, width, 3)`` uint8 video, muxing audio when given.

    Raises if ``ffmpeg`` is not on PATH; use :func:`save_frames` in that case.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg not found on PATH; use save_frames() instead.")

    path = Path(path)
    video = np.ascontiguousarray(video, dtype=np.uint8)
    frames, height, width, _ = video.shape

    audio_path = None
    if audio is not None:
        audio_path = path.with_suffix(".wav")
        save_wav(audio_path, audio, sample_rate)

    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0",
    ]
    if audio_path is not None:
        cmd += ["-i", str(audio_path), "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p", str(path)]

    process = subprocess.run(cmd, input=video.tobytes(), capture_output=True)
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {process.stderr.decode()[:500]}")
    return path


def save_frames(directory: str | Path, video: np.ndarray, limit: int | None = None) -> Path:
    """Write frames as ``frame_00000.png`` — the fallback when ffmpeg is unavailable."""
    from PIL import Image

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    count = len(video) if limit is None else min(limit, len(video))
    for index in range(count):
        Image.fromarray(video[index]).save(directory / f"frame_{index:05d}.png")
    return directory
