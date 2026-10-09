"""Host-only output geometry adaptation for 32-pixel-aligned video Workers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import av


def crop_video_canvas(source: Path, destination: Path, *, width: int, height: int,
                      check: Callable[[], None]) -> Path:
    """Center-crop a generated MP4 while copying its compressed audio track."""
    with (av.open(str(source)) as original,
          av.open(str(source)) as audio_source,
          av.open(str(destination), "w", format="mp4") as target):
        if len(original.streams.video) != 1 or len(original.streams.audio) > 1:
            raise ValueError("Generated video has unsupported tracks")
        video_input = original.streams.video[0]
        if width > video_input.width or height > video_input.height:
            raise ValueError("Requested crop exceeds generated video dimensions")
        left = (video_input.width - width) // 2
        top = (video_input.height - height) // 2
        rate = video_input.average_rate or video_input.guessed_rate
        if rate is None:
            raise ValueError("Generated video has no frame rate")
        video_output = target.add_stream("libx264", rate=rate)
        video_output.width, video_output.height = width, height
        video_output.pix_fmt = "yuv420p"
        video_output.options = {"crf": "18", "preset": "fast"}
        audio_input = audio_source.streams.audio[0] if audio_source.streams.audio else None
        audio_output = target.add_stream_from_template(audio_input) if audio_input else None
        for index, frame in enumerate(original.decode(video_input)):
            check()
            pixels = frame.to_ndarray(format="rgb24")[top:top + height, left:left + width]
            cropped = av.VideoFrame.from_ndarray(pixels.copy(), format="rgb24")
            cropped.pts = index
            for packet in video_output.encode(cropped):
                target.mux(packet)
        for packet in video_output.encode():
            target.mux(packet)
        if audio_input is not None:
            for packet in audio_source.demux(audio_input):
                check()
                if packet.dts is not None:
                    packet.stream = audio_output
                    target.mux(packet)
    return destination
