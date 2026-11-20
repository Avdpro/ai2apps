"""Real codec checkpoint: encode/decode and preservation of code-zero frames."""

import bootstrap
from bootstrap import CHECKPOINT_ROOT
import sys
import mlx.core as mx
from exomni_mlx.codec import SpeechCodec

codec = SpeechCodec(CHECKPOINT_ROOT / "qwen-codec")
wave = (
    mx.sin(mx.arange(4800, dtype=mx.float32) * (440 * 2 * 3.141592653589793 / 24000))
    * 0.1
)
codes = codec.encode(wave)
assert codes.ndim == 3 and codes.shape[-1] == 16 and codes.shape[1] > 0
assert bool(mx.all((codes >= 0) & (codes < 2048)).item())
# Zero is a valid codec ID; it must not be interpreted as missing padding.
zero_codes = mx.zeros((1, 2, 16), dtype=mx.int32)
output = codec.decode(zero_codes)
mx.eval(output)
assert output.shape == (2 * codec.model.decode_upsample_rate,)
assert bool(mx.all(mx.isfinite(output)).item())
assert "torch" not in sys.modules
print("PASS: real codec encode/decode, valid zero-code frames, no Torch import")
