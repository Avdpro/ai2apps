"""Bounded asynchronous RGB-to-H.264 writer with atomic publication and error propagation."""

import os
import queue
import subprocess
import tempfile
import threading
from contextlib import suppress
from pathlib import Path

import numpy as np


class VideoWriter:
    def __init__(
        self,
        output,
        audio,
        duration,
        *,
        asynchronous=True,
        queue_size=2,
        size=(512, 512),
    ):
        if queue_size < 1:
            raise ValueError("queue_size must be positive")
        if len(size) != 2 or any(int(v) != v or v < 1 for v in size):
            raise ValueError("Video dimensions must be positive integers")
        self.size = tuple(map(int, size))
        # 4:4:4 retains exact odd dimensions; no silent padding or stretching.
        self.pixel_format = (
            "yuv420p" if all(v % 2 == 0 for v in self.size) else "yuv444p"
        )
        self.output = Path(output)
        fd, name = tempfile.mkstemp(
            prefix=".avtr-encode-", suffix=".mp4", dir=self.output.parent
        )
        os.close(fd)
        self.temporary = Path(name)
        self.stderr = tempfile.TemporaryFile()  # noqa: SIM115 - owned until close/abort
        self.error = None
        self.queue = queue.Queue(maxsize=queue_size)
        self.asynchronous = asynchronous
        self.finished = False
        try:
            self.process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-f",
                    "rawvideo",
                    "-pix_fmt",
                    "rgb24",
                    "-s",
                    f"{self.size[0]}x{self.size[1]}",
                    "-r",
                    "25",
                    "-i",
                    "pipe:0",
                    "-i",
                    str(audio),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-t",
                    str(duration),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    self.pixel_format,
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                    str(self.temporary),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=self.stderr,
            )
        except BaseException:
            self.stderr.close()
            self.temporary.unlink(missing_ok=True)
            raise
        self.thread = None
        if asynchronous:
            self.thread = threading.Thread(
                target=self._worker, name="avtr-video-encoder", daemon=True
            )
            self.thread.start()

    def _worker(self):
        try:
            while True:
                frames = self.queue.get()
                if frames is None:
                    break
                self.process.stdin.write(frames.tobytes())
        except BaseException as exc:
            self.error = exc
        finally:
            with suppress(OSError):
                self.process.stdin.close()

    def _put(self, frames):
        while True:
            if self.error is not None:
                raise RuntimeError("Video encoder failed") from self.error
            if self.thread is not None and not self.thread.is_alive():
                raise RuntimeError("Video encoder stopped")
            try:
                self.queue.put(frames, timeout=0.1)
                return
            except queue.Full:
                continue

    def submit(self, frames):
        if self.finished:
            raise RuntimeError("Video encoder is closed")
        if (
            frames.dtype != np.uint8
            or frames.ndim != 4
            or frames.shape[1:] != (self.size[1], self.size[0], 3)
        ):
            raise ValueError("Expected RGB uint8 frames matching the video dimensions")
        # Own the buffer: callers may reuse their arrays while encoding continues.
        frames = np.array(frames, copy=True, order="C")
        if self.asynchronous:
            self._put(frames)
        else:
            self.process.stdin.write(frames.tobytes())

    def close(self):
        if self.finished:
            return
        try:
            if self.asynchronous:
                self._put(None)
                self.thread.join()
            else:
                self.process.stdin.close()
            code = self.process.wait()
            if code or self.error:
                self.stderr.seek(0)
                raise RuntimeError(
                    "Video encoding failed: "
                    + self.stderr.read(4096).decode(errors="replace")
                ) from self.error
            os.replace(self.temporary, self.output)
            self.finished = True
            self.stderr.close()
        except BaseException:
            self.abort()
            raise

    def abort(self):
        if self.finished:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.thread is not None and self.thread.is_alive():
            # Wake an idle worker; a blocked pipe write exits when FFmpeg terminates.
            with suppress(queue.Full):
                self.queue.put_nowait(None)
            self.thread.join(timeout=5)
        with suppress(OSError):
            self.process.stdin.close()
        self.stderr.close()
        self.temporary.unlink(missing_ok=True)
        self.finished = True
