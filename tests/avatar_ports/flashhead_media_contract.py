import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT

"""Catch frame-boundary and numeric-range errors independently of expensive models."""
import sys, tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np, mlx.core as mx, av, soundfile as sf

from flashhead_mlx.pipeline import FlashHeadPipeline

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    for motion, count in [
        (m, n) for m in (5, 9) for n in (1, 25, 33, 34, 57, 58, 61, 62)
    ]:
        sf.write(
            root / "audio.wav", np.ones(count * 640, dtype=np.float32) * 0.1, 16000
        )
        pipeline = FlashHeadPipeline.__new__(FlashHeadPipeline)
        pipeline.audio_parameters = None
        pipeline.dtype = mx.float32
        pipeline.motion_frames = motion
        pipeline.chunk_stride = 33 - motion
        pipeline.prepare = lambda *a, **k: None
        pipeline.generate_chunk = lambda *a, **k: mx.zeros((1, 3, 33, 32, 32))
        with patch(
            "flashhead_mlx.pipeline.wav2vec2_encode",
            side_effect=lambda *a, output_length, **k: tuple(
                mx.zeros((1, output_length, 1)) for _ in range(12)
            ),
        ):
            pipeline.generate(
                "unused.png", root / "audio.wav", root / "output.mp4", size=32
            )
        with av.open(str(root / "output.mp4")) as m:
            assert len(m.streams.audio) == 1
            frames = list(m.decode(video=0))
        assert len(frames) == count, (count, len(frames))
        values = frames[-1].to_ndarray(format="rgb24")
        assert abs(float(values.mean()) - 128) <= 3, values.mean()
    print(
        "PASS: audio track, frame counts across chunk boundaries, [-1,1] media input range"
    )
