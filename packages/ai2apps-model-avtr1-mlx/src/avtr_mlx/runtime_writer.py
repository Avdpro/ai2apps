"""Runtime-provided PyAV encoder; no external executable or native payload."""

import os
from pathlib import Path

import av
import numpy as np
import soundfile as sf


class RuntimeVideoWriter:
    def __init__(self, output, audio, duration, *, size=(512, 512), asynchronous=True):
        self.output = Path(output)
        self.temporary = self.output.with_suffix(".encoding.mp4")
        self.size = size
        self.pixel_format = "yuv420p" if all(v % 2 == 0 for v in size) else "yuv444p"
        self.samples, self.rate = sf.read(str(audio), dtype="float32", always_2d=True)
        self.samples = self.samples.mean(axis=1)[: round(duration * self.rate)]
        self.container = av.open(
            str(self.temporary), "w", options={"movflags": "+faststart"}
        )
        self.video = self.container.add_stream("libx264", rate=25)
        self.video.width, self.video.height = size
        self.video.pix_fmt = self.pixel_format
        self.video.options = {"crf": "18", "preset": "fast"}
        self.audio = self.container.add_stream("aac", rate=self.rate)
        self.audio.layout = "mono"
        self.count = 0
        self.closed = False

    def submit(self, frames):
        for rgb in frames:
            frame = av.VideoFrame.from_ndarray(rgb, format="rgb24")
            frame.pts = self.count
            self.count += 1
            for packet in self.video.encode(frame):
                self.container.mux(packet)

    def close(self):
        if self.closed:
            return
        try:
            for packet in self.video.encode():
                self.container.mux(packet)
            for start in range(0, len(self.samples), 1024):
                chunk = np.ascontiguousarray(self.samples[start : start + 1024][None])
                frame = av.AudioFrame.from_ndarray(chunk, format="fltp", layout="mono")
                frame.sample_rate = self.rate
                frame.pts = start
                for packet in self.audio.encode(frame):
                    self.container.mux(packet)
            for packet in self.audio.encode():
                self.container.mux(packet)
            self.container.close()
            self.closed = True
            os.replace(self.temporary, self.output)
        except BaseException:
            self.abort()
            raise

    def abort(self):
        if not self.closed:
            self.container.close()
            self.closed = True
        self.temporary.unlink(missing_ok=True)
