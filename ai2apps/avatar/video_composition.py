"""Streaming source-canvas output for Host-owned digital-human video tasks."""

import os
from pathlib import Path


def compose_video(source_video, output, canvas, *, check=lambda: None, progress=None):
    import av
    import numpy as np

    output = Path(output)
    temporary = output.with_suffix(".partial.mp4")
    count = 0
    try:
        with av.open(str(source_video)) as source:
            video = source.streams.video[0]
            rate = video.average_rate or video.guessed_rate
            if not rate:
                raise ValueError("Generated video has no frame rate")
            with av.open(str(temporary), "w") as target:
                encoded = target.add_stream("libx264", rate=rate)
                # Browser H.264 decoders require 4:2:0. Preserve source pixels
                # and extend only the bottom/right edge for odd canvas sizes.
                width, height = canvas.size
                encoded.width = width + width % 2
                encoded.height = height + height % 2
                encoded.pix_fmt = "yuv420p"
                encoded.options = {"crf": "18", "preset": "fast"}
                audio = {
                    stream.index: target.add_stream_from_template(stream)
                    for stream in source.streams.audio
                }
                for packet in source.demux():
                    check()
                    if packet.stream.index in audio:
                        if packet.dts is not None:
                            packet.stream = audio[packet.stream.index]
                            target.mux(packet)
                        continue
                    if packet.stream.index != video.index:
                        continue
                    for frame in packet.decode():
                        check()
                        rgb = canvas.compose(frame.to_ndarray(format="rgb24"))
                        if width % 2 or height % 2:
                            rgb = np.pad(
                                rgb, ((0, height % 2), (0, width % 2), (0, 0)),
                                mode="edge",
                            )
                        result = av.VideoFrame.from_ndarray(rgb, format="rgb24")
                        result.pts = frame.pts
                        result.time_base = frame.time_base
                        for encoded_packet in encoded.encode(result):
                            target.mux(encoded_packet)
                        count += 1
                        if progress and (count == 1 or count % 25 == 0):
                            progress(count, video.frames or count)
                for packet in encoded.encode():
                    target.mux(packet)
                if not count:
                    raise ValueError("Generated video has no frames")
        check()
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output
