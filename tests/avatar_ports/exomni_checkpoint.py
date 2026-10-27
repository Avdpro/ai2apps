import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT
import sys, time, json
from pathlib import Path


import mlx.core as mx
from tokenizers import Tokenizer
from exomni_mlx.thinker import ExOmniThinker
from exomni_mlx.generator import SpeechGenerator
from exomni_mlx.speaker import SpeakerEncoder

root = Path(CHECKPOINT_ROOT)
start = time.perf_counter()
thinker = ExOmniThinker.from_pretrained(root / "exomni")
tokenizer = Tokenizer.from_file(str(root / "exomni/tokenizer.json"))
tokens = mx.array(
    [tokenizer.encode("你好，欢迎。", add_special_tokens=False).ids + [151645]]
)
logits, hidden = thinker.forward_hidden(tokens)
mx.eval(logits, hidden)
assert bool(mx.all(mx.isfinite(logits)).item())
print(
    "thinker", logits.shape, "loaded_seconds", time.perf_counter() - start, flush=True
)
# The speech bridge consumes response hidden states, not probabilities.
speech = SpeechGenerator.from_pretrained(root / "exomni", root / "qwen-tts/config.json")
speaker = SpeakerEncoder(root / "exomni", root / "qwen-tts/config.json")
voice = speaker(mx.sin(mx.arange(24000, dtype=mx.float32) * 0.07) * 0.1)
assert voice.shape == (1, 1, 1024) and bool(mx.all(mx.isfinite(voice)).item())
codes = speech.generate_codes(
    hidden, tokens, speaker_embedding=voice, max_tokens=2, sample=False
)
mx.eval(codes)
assert codes.shape == (1, 2, 16)
assert bool(mx.all((codes >= 0) & (codes < 2048)).item())
mx.save(str(root / "exomni-generated-codes.npy"), codes)
assert "torch" not in sys.modules
print(
    json.dumps(
        {
            "strict_load": True,
            "codes_shape": list(codes.shape),
            "seconds": time.perf_counter() - start,
            "peak_bytes": mx.get_peak_memory(),
            "torch_imported": False,
        }
    )
)
