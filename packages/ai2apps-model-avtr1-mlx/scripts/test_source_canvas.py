import json
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root), str(root / "packages/ai2apps-model-avtr1-mlx/src")]
from avtr_mlx.video_writer import VideoWriter  # noqa: E402

from ai2apps.avatar.composition import SourceCanvas, load_source_rgb  # noqa: E402


class CanvasTests(unittest.TestCase):
    def test_existing_alpha_is_composited_before_rgb(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alpha.png"
            rgba = np.array(
                [[[255, 255, 255, 0], [255, 255, 255, 128], [10, 20, 30, 255]]],
                dtype="uint8",
            )
            Image.fromarray(rgba).save(path)
            rgb = load_source_rgb(path)
            np.testing.assert_array_equal(
                rgb, [[[0, 0, 0], [128, 128, 128], [10, 20, 30]]]
            )
            rgb = load_source_rgb(path, background=(20, 40, 60))
            np.testing.assert_array_equal(rgb[0, 0], [20, 40, 60])
            np.testing.assert_array_equal(rgb[0, 2], [10, 20, 30])

    def test_identity_and_feather(self):
        src = np.full((101, 151, 3), 130, np.uint8)
        canvas = SourceCanvas(src, [[1, 0, 30], [0, 1, 20]], (64, 64))
        result = canvas.compose(np.full((64, 64, 3), 130, np.uint8))
        np.testing.assert_array_equal(result, src)
        result = canvas.compose(np.full((64, 64, 3), 230, np.uint8))
        np.testing.assert_array_equal(result[40, 50], [230] * 3)
        np.testing.assert_array_equal(result[20, 30], [130] * 3)
        self.assertTrue(130 < result[22, 32, 0] < 230)
        np.testing.assert_array_equal(result[:19], src[:19])

    def test_rotated_clipped_no_dark_border(self):
        src = np.full((101, 151, 3), 120, np.uint8)
        matrix = cv2.getRotationMatrix2D((32, 32), 31, 1.3)
        matrix[:, 2] += [-24, 10]
        canvas = SourceCanvas(src, matrix, (64, 64))
        result = canvas.compose(np.full((64, 64, 3), 120, np.uint8))
        np.testing.assert_array_equal(result, src)
        result = canvas.compose(np.full((64, 64, 3), 210, np.uint8))
        self.assertEqual(result.shape, src.shape)
        self.assertGreater(result.max(), 120)
        self.assertGreaterEqual(result.min(), 120)

    def test_arbitrary_crop_and_offcenter_canvas(self):
        src = np.zeros((1080, 1920, 3), np.uint8)
        canvas = SourceCanvas(src, [[2, 0, 1400], [0, 2, 600]], (100, 150))
        result = canvas.compose(np.full((150, 100, 3), 255, np.uint8))
        np.testing.assert_array_equal(result[:590], src[:590])
        np.testing.assert_array_equal(result[:, :1390], src[:, :1390])
        self.assertEqual(result[700, 1500, 0], 255)

    def test_invalid_matrix(self):
        src = np.zeros((20, 20, 3), np.uint8)
        for matrix in (
            [[0, 0, 0], [0, 0, 0]],
            [[1, 0, 100], [0, 1, 100]],
            [[1, 0, float("nan")], [0, 1, 0]],
            [[1, 0, 0], [0, 1, 0], [1, 0, 1]],
        ):
            with self.assertRaises(ValueError):
                SourceCanvas(src, matrix, (16, 16))

    def test_exact_even_and_odd_video_sizes(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            audio = folder / "audio.wav"
            with wave.open(str(audio), "wb") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(16000)
                f.writeframes(bytes(16000))
            for w, h in ((1920, 1080), (360, 640), (321, 181)):
                output = folder / f"{w}x{h}.mp4"
                writer = VideoWriter(output, audio, 0.2, size=(w, h))
                writer.submit(np.full((5, h, w, 3), 120, np.uint8))
                writer.close()
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
                video = info["streams"][0]
                self.assertEqual((video["width"], video["height"]), (w, h))
                self.assertEqual(int(video["nb_frames"]), 5)
                self.assertEqual(
                    video["pix_fmt"],
                    "yuv420p" if w % 2 == 0 and h % 2 == 0 else "yuv444p",
                )


if __name__ == "__main__":
    unittest.main()
