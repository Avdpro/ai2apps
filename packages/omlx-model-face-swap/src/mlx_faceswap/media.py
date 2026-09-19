"""Small image/video helpers using dependencies already present in Runtime 1.6.2."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image

_RESAMPLING = {
    "nearest": Image.Resampling.NEAREST,
    "linear": Image.Resampling.BILINEAR,
    "cubic": Image.Resampling.BICUBIC,
    "area": Image.Resampling.LANCZOS,
}


def read_image_bgr(path: str | Path) -> np.ndarray:
    """Read an image as contiguous uint8 BGR, matching the model-facing convention."""

    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    return np.ascontiguousarray(rgb[..., ::-1])


def write_image_bgr(path: str | Path, image_bgr: np.ndarray) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rgb = np.ascontiguousarray(np.asarray(image_bgr, dtype=np.uint8)[..., ::-1])
    Image.fromarray(rgb, mode="RGB").save(destination)


def resize_bgr(
    image_bgr: np.ndarray,
    size: tuple[int, int],
    *,
    interpolation: str = "linear",
) -> np.ndarray:
    rgb = np.ascontiguousarray(np.asarray(image_bgr, dtype=np.uint8)[..., ::-1])
    resized = Image.fromarray(rgb, mode="RGB").resize(
        size, resample=_RESAMPLING[interpolation]
    )
    return np.ascontiguousarray(np.asarray(resized, dtype=np.uint8)[..., ::-1])


def resize_float(image: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    source = Image.fromarray(np.asarray(image, dtype=np.float32), mode="F")
    return np.asarray(
        source.resize(size, resample=Image.Resampling.BILINEAR), dtype=np.float32
    )


def blob_from_bgr(
    image_bgr: np.ndarray,
    size: tuple[int, int],
    *,
    scale: float = 1.0,
    mean: float = 0.0,
    swap_rb: bool = True,
) -> np.ndarray:
    resized = resize_bgr(image_bgr, size)
    values = resized[..., ::-1] if swap_rb else resized
    values = (values.astype(np.float32) - mean) * scale
    return np.ascontiguousarray(values.transpose(2, 0, 1)[None])


def warp_affine_bgr(
    image_bgr: np.ndarray,
    source_to_output: np.ndarray,
    output_size: tuple[int, int],
) -> np.ndarray:
    """Warp BGR input with a 2x3 source-to-output affine transform."""

    matrix = np.vstack(
        (np.asarray(source_to_output, dtype=np.float64), (0.0, 0.0, 1.0))
    )
    inverse = np.linalg.inv(matrix)[:2]
    rgb = np.ascontiguousarray(np.asarray(image_bgr, dtype=np.uint8)[..., ::-1])
    transformed = Image.fromarray(rgb, mode="RGB").transform(
        output_size,
        Image.Transform.AFFINE,
        tuple(inverse.reshape(-1)),
        resample=Image.Resampling.BILINEAR,
        fillcolor=(0, 0, 0),
    )
    return np.ascontiguousarray(np.asarray(transformed, dtype=np.uint8)[..., ::-1])


def warp_affine_float(
    image: np.ndarray,
    source_to_output: np.ndarray,
    output_size: tuple[int, int],
) -> np.ndarray:
    matrix = np.vstack(
        (np.asarray(source_to_output, dtype=np.float64), (0.0, 0.0, 1.0))
    )
    inverse = np.linalg.inv(matrix)[:2]
    transformed = Image.fromarray(np.asarray(image, dtype=np.float32), mode="F").transform(
        output_size,
        Image.Transform.AFFINE,
        tuple(inverse.reshape(-1)),
        resample=Image.Resampling.BILINEAR,
        fillcolor=0.0,
    )
    return np.asarray(transformed, dtype=np.float32)


class VideoReader:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.container = av.open(str(self.path), mode="r")
        self.stream = self.container.streams.video[0]
        rate = self.stream.average_rate or self.stream.guessed_rate
        self.fps = float(rate) if rate else 25.0
        self.width = int(self.stream.codec_context.width)
        self.height = int(self.stream.codec_context.height)

    def __iter__(self):
        for frame in self.container.decode(self.stream):
            yield frame.to_ndarray(format="bgr24")

    def close(self) -> None:
        self.container.close()


class VideoWriter:
    def __init__(
        self,
        path: str | Path,
        fps: float,
        size: tuple[int, int],
        *,
        codec: str = "libx264",
    ):
        self.container = av.open(str(path), mode="w")
        rate = Fraction(fps).limit_denominator(100_000)
        try:
            self.stream = self.container.add_stream(codec, rate=rate)
        except av.error.UnknownCodecError:
            fallback = "libx264" if codec != "libx264" else "h264"
            self.stream = self.container.add_stream(fallback, rate=rate)
        self.stream.width, self.stream.height = size
        self.stream.pix_fmt = "yuv420p"

    def write(self, frame_bgr: np.ndarray) -> None:
        frame = av.VideoFrame.from_ndarray(
            np.ascontiguousarray(frame_bgr), format="bgr24"
        )
        for packet in self.stream.encode(frame):
            self.container.mux(packet)

    def close(self) -> None:
        for packet in self.stream.encode():
            self.container.mux(packet)
        self.container.close()


def remux_source_audio(
    silent_video: str | Path, source_media: str | Path, output: str | Path
) -> bool:
    """Copy generated video and the first source audio stream without ffmpeg CLI."""

    video_input = av.open(str(silent_video), mode="r")
    source_input = av.open(str(source_media), mode="r")
    audio_streams = list(source_input.streams.audio)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not audio_streams:
        video_input.close()
        source_input.close()
        Path(silent_video).replace(destination)
        return False
    output_container = av.open(str(destination), mode="w")
    output_video = output_container.add_stream_from_template(video_input.streams.video[0])
    output_audio = output_container.add_stream_from_template(audio_streams[0])
    for packet in video_input.demux(video_input.streams.video[0]):
        if packet.dts is not None:
            packet.stream = output_video
            output_container.mux(packet)
    for packet in source_input.demux(audio_streams[0]):
        if packet.dts is not None:
            packet.stream = output_audio
            output_container.mux(packet)
    output_container.close()
    video_input.close()
    source_input.close()
    return True
