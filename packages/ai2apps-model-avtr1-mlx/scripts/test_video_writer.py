"""CPU integration tests for frame order, queue shutdown and failed publication."""

import json
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from avtr_mlx.video_writer import VideoWriter  # noqa: E402


class VideoWriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.audio = self.root / "silence.wav"
        with wave.open(str(self.audio), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16000)
            out.writeframes(bytes(32000))

    def tearDown(self):
        self.temp.cleanup()

    def test_order_and_sync_async_equivalence(self):
        colors = np.array(
            [[20 + i * 25, 180 - i * 15, 30 + i * 10] for i in range(8)], dtype="uint8"
        )
        frames = np.broadcast_to(colors[:, None, None, :], (8, 512, 512, 3)).copy()
        decoded = []
        for asynchronous in (False, True):
            output = self.root / f"{asynchronous}.mp4"
            writer = VideoWriter(
                output, self.audio, 8 / 25, asynchronous=asynchronous, queue_size=1
            )
            for start, end in [(0, 3), (3, 5), (5, 8)]:
                writer.submit(frames[start:end])
            writer.close()
            writer.close()
            if writer.thread:
                self.assertFalse(writer.thread.is_alive())
            info = json.loads(
                subprocess.check_output(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_streams",
                        "-of",
                        "json",
                        str(output),
                    ]
                )
            )
            self.assertEqual(
                [s["codec_type"] for s in info["streams"]], ["video", "audio"]
            )
            self.assertEqual(int(info["streams"][0]["nb_frames"]), 8)
            raw = subprocess.check_output(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    str(output),
                    "-f",
                    "rawvideo",
                    "-pix_fmt",
                    "rgb24",
                    "-",
                ]
            )
            image = np.frombuffer(raw, dtype="uint8").reshape(8, 512, 512, 3)
            self.assertLess(np.max(abs(image.mean(axis=(1, 2)) - colors)), 6)
            decoded.append(image)
        np.testing.assert_array_equal(*decoded)

    def test_failure_preserves_destination(self):
        output = self.root / "result.mp4"
        output.write_bytes(b"existing artifact")
        writer = VideoWriter(output, self.root / "missing.wav", 0.2, queue_size=1)
        with self.assertRaises((RuntimeError, BrokenPipeError)):
            try:
                for _ in range(5):
                    writer.submit(np.zeros((1, 512, 512, 3), dtype="uint8"))
                writer.close()
            finally:
                writer.abort()
        self.assertEqual(output.read_bytes(), b"existing artifact")
        self.assertIsNotNone(writer.process.poll())
        self.assertFalse(writer.thread.is_alive())
        self.assertFalse(writer.temporary.exists())

    def test_abort_idle_worker(self):
        writer = VideoWriter(self.root / "aborted.mp4", self.audio, 0.2)
        writer.abort()
        writer.abort()
        self.assertFalse(writer.thread.is_alive())
        self.assertFalse(writer.temporary.exists())
        self.assertFalse((self.root / "aborted.mp4").exists())


if __name__ == "__main__":
    unittest.main()
