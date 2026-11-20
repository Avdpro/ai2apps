"""Offline template inference with explicitly prepared face boxes and masks.

Automatic face detection/parsing is a separate preprocessing stage. This API
requires a per-frame box and a 256x256 alpha mask; it does not silently replace
segmentation with a rectangular paste.
"""

from dataclasses import dataclass

import av
import mlx.core as mx
import numpy as np
import soundfile as sf
from PIL import Image

from .media import write_mp4_chunks_with_audio
from .pipeline_mlx import MuseTalkPipeline


@dataclass(frozen=True)
class FaceRegion:
    box: tuple[int, int, int, int]
    mask: np.ndarray

    def validate(self, width, height):
        x0, y0, x1, y1 = self.box
        if not 0 <= x0 < x1 <= width or not 0 <= y0 < y1 <= height:
            raise ValueError("Face box is outside the template frame")
        if (
            self.mask.shape != (256, 256)
            or not np.isfinite(self.mask).all()
            or self.mask.min() < 0
            or self.mask.max() > 1
        ):
            raise ValueError("Face mask must be finite 256x256 alpha values in [0,1]")
        if not np.any(self.mask):
            raise ValueError("Face mask must contain a nonempty foreground")


def render_template(
    pipeline: MuseTalkPipeline,
    source_video,
    audio_path,
    output_path,
    regions,
    *,
    batch_size=4,
    fps=25,
    frame_interval=None,
    source_start=0,
    cancel_check=lambda: None,
    progress=lambda done, total: None,
):
    if not regions or batch_size < 1:
        raise ValueError("Prepared regions and a positive batch size are required")
    if frame_interval is None:
        info = sf.info(str(audio_path))
        total = (info.frames * fps + info.samplerate - 1) // info.samplerate
        if total < 1:
            raise ValueError("Audio is shorter than one video frame")
        features = pipeline.encode_audio_from_wav(audio_path, fps=fps)
        if features.shape[0] == total - 1 and features.shape[0] > 0:
            features = mx.concatenate([features, features[-1:]], axis=0)
        if features.shape[0] != total:
            raise ValueError("Audio feature frame count mismatch")
    else:
        start, end = frame_interval
        if (type(source_start) is not int or source_start < 0
                or end <= start or source_start + end - start > len(regions)):
            raise ValueError("Segment frame range exceeds the source motion")
        total = end - start
        features = pipeline.encode_audio_frame_range(
            audio_path, start, end, fps=fps, cancel_check=cancel_check)
        if features.shape[0] != total:
            raise ValueError("Segment audio feature frame count mismatch")

    def source_frames():
        while True:
            count = 0
            with av.open(str(source_video)) as media:
                stream = media.streams.video[0]
                if abs(float(stream.average_rate) - fps) > 1e-4:
                    raise ValueError(
                        "Normalize the source template to the output frame rate first"
                    )
                for frame in media.decode(stream):
                    if count >= len(regions):
                        raise ValueError("Missing prepared face region")
                    yield frame.to_ndarray(format="rgb24"), regions[count]
                    count += 1
            if count != len(regions):
                raise ValueError(
                    "Prepared regions do not match the template frame count"
                )

    def chunks():
        iterator = source_frames()
        try:
            for _ in range(source_start):
                next(iterator)
            for start in range(0, total, batch_size):
                cancel_check()
                frames = []
                metadata = []
                latents = []
                for _ in range(start, min(start + batch_size, total)):
                    frame, region = next(iterator)
                    region.validate(frame.shape[1], frame.shape[0])
                    x0, y0, x1, y1 = region.box
                    crop = np.array(
                        Image.fromarray(frame[y0:y1, x0:x1]).resize(
                            (256, 256), Image.Resampling.BILINEAR
                        )
                    )
                    latents.append(
                        pipeline.get_latents_for_unet(
                            np.ascontiguousarray(crop[..., ::-1])
                        )
                    )
                    frames.append(frame)
                    metadata.append(region)
                generated = pipeline.run_batched(
                    mx.concatenate(latents),
                    features[start : start + len(frames)],
                    batch_size=batch_size,
                )
                cancel_check()
                for frame, region, face in zip(frames, metadata, generated):
                    x0, y0, x1, y1 = region.box
                    shape = (x1 - x0, y1 - y0)
                    face = np.asarray(
                        Image.fromarray(np.ascontiguousarray(face[..., ::-1])).resize(
                            shape, Image.Resampling.BILINEAR
                        ),
                        dtype=np.float32,
                    )
                    alpha = np.asarray(
                        Image.fromarray(region.mask.astype(np.float32)).resize(
                            shape, Image.Resampling.BILINEAR
                        )
                    )[..., None]
                    frame[y0:y1, x0:x1] = np.rint(
                        face * alpha + frame[y0:y1, x0:x1] * (1 - alpha)
                    ).astype(np.uint8)
                yield np.stack(frames).astype(np.float32) / 127.5 - 1
                progress(start + len(frames), total)
        finally:
            iterator.close()

    return write_mp4_chunks_with_audio(
        chunks(), audio_path if frame_interval is None else None, output_path, fps=fps)
