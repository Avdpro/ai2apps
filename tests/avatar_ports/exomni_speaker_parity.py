"""Compare the Runtime speaker encoder with Ex-Omni's actual upstream class."""

import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT
import ast, json, sys
from dataclasses import dataclass, field
import numpy as np
import torch
import mlx.core as mx
from exomni_mlx.speaker import SpeakerEncoder

path = UPSTREAM_ROOT / "exomni/ex_omni/model/speech_generator/qwen3_tts_speaker.py"
tree = ast.parse(path.read_text())
tree.body = [
    node
    for node in tree.body
    if isinstance(node, ast.ClassDef) and node.name != "Qwen3TTSSpeakerEmbedding"
]
namespace = dict(
    torch=torch, nn=torch.nn, F=torch.nn.functional, dataclass=dataclass, field=field
)
exec(compile(tree, str(path), "exec"), namespace)
config = namespace["Qwen3TTSSpeakerEncoderConfig"](
    **json.loads((CHECKPOINT_ROOT / "qwen-tts/config.json").read_text())[
        "speaker_encoder_config"
    ]
)
reference = namespace["Qwen3TTSSpeakerEncoder"](config).eval()
index = json.loads(
    (CHECKPOINT_ROOT / "exomni/model.safetensors.index.json").read_text()
)["weight_map"]
prefix = "model.speech_generator.roleplay_speaker_encoder.encoder."
names = {key for key in index if key.startswith(prefix)}
weights = {}
from safetensors import safe_open

for shard in {index[key] for key in names}:
    with safe_open(CHECKPOINT_ROOT / "exomni" / shard, framework="pt") as handle:
        weights.update(
            {
                key[len(prefix) :]: handle.get_tensor(key).float()
                for key in names
                if index[key] == shard
            }
        )
reference.load_state_dict(weights, strict=True)
model = SpeakerEncoder(
    CHECKPOINT_ROOT / "exomni", CHECKPOINT_ROOT / "qwen-tts/config.json"
)
mel = np.random.default_rng(4).normal(size=(1, 40, 128)).astype("float32")
with torch.no_grad():
    expected = reference(torch.from_numpy(mel)).numpy()
actual = np.array(model.model(mx.array(mel)))
error = float(np.max(np.abs(actual - expected)))
print("speaker max_abs", error, "shape", actual.shape)
np.testing.assert_allclose(actual, expected, atol=2e-4, rtol=2e-4)
print("PASS")
