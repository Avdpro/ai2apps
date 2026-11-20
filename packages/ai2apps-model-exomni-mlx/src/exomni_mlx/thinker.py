"""Ex-Omni Qwen3 thinker using the Runtime's native mlx-lm implementation."""

import json
from pathlib import Path

import mlx.core as mx
from mlx_lm.models.qwen3 import Model, ModelArgs


class ExOmniThinker(Model):
    def forward_hidden(self, tokens, *, cache=None, input_embeddings=None):
        """Return logits and last-layer hidden states for learned speech fusion."""
        hidden = self.model(tokens, cache, input_embeddings)
        logits = (
            self.model.embed_tokens.as_linear(hidden)
            if self.args.tie_word_embeddings
            else self.lm_head(hidden)
        )
        return logits, hidden

    @classmethod
    def from_pretrained(cls, root):
        root = Path(root)
        config = json.loads((root / "config.json").read_text())
        if config.get("model_type") not in ("qwen3", "llava_her_qwen3"):
            raise ValueError("Expected Ex-Omni Qwen3 thinker checkpoint")
        model = cls(ModelArgs.from_dict(config))
        weights = {}
        index = json.loads((root / "model.safetensors.index.json").read_text())[
            "weight_map"
        ]
        names = {
            k
            for k in index
            if k.startswith(
                ("model.embed_tokens.", "model.layers.", "model.norm.", "lm_head.")
            )
        }
        for shard in sorted({index[k] for k in names}):
            state = mx.load(str(root / shard))
            weights.update({k: v for k, v in state.items() if k in names})
        model.load_weights(list(weights.items()), strict=True)
        model.eval()
        mx.eval(model.parameters())
        return model
