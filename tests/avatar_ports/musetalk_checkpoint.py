import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT
import sys, time, json
from pathlib import Path

import mlx.core as mx
import numpy as np
from musetalk_mlx.pipeline_mlx import MuseTalkPipeline
from musetalk_mlx.whisper.log_mel import log_mel_spectrogram

start = time.perf_counter()
pipe = MuseTalkPipeline.from_pretrained_mlx(CHECKPOINT_ROOT / "musetalk-q4")
load = time.perf_counter() - start
image = np.full((256, 256, 3), 128, dtype=np.uint8)
latents = pipe.get_latents_for_unet(image)
# Synthetic audio tests the complete frontend without using personal media.
wav = mx.sin(mx.arange(16000, dtype=mx.float32) * (2 * np.pi * 220 / 16000)) * 0.05
mel = log_mel_spectrogram(wav)
chunks = pipe.encode_audio(mel, 16000, fps=25)
frames = pipe.run_batched(latents, chunks[:1], batch_size=1)
assert frames.shape == (1, 256, 256, 3) and frames.dtype == np.uint8
assert "torch" not in sys.modules and "cv2" not in sys.modules
print(
    json.dumps(
        {
            "load_seconds": load,
            "total_seconds": time.perf_counter() - start,
            "output_shape": frames.shape,
            "audio_chunks": chunks.shape,
            "peak_bytes": mx.get_peak_memory(),
            "torch_imported": False,
            "cv2_imported": False,
        }
    )
)
