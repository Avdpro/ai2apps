"""Minimal MLX BERT encoder for Multilingual E5.

The architecture follows the MIT-licensed ``mlx-embeddings`` BERT backend,
trimmed to the one text-only model used by Knowledge. Keeping this adapter in
the model Package avoids pulling unrelated VLM, audio, and OpenCV dependencies
into the on-demand Runtime.
"""

from __future__ import annotations

import glob
import inspect
import json
import math
from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
from transformers import AutoTokenizer


@dataclass
class ModelArgs:
    model_type: str
    num_hidden_layers: int
    num_attention_heads: int
    hidden_size: int
    intermediate_size: int
    max_position_embeddings: int
    hidden_dropout_prob: float = 0.1
    attention_probs_dropout_prob: float = 0.1
    type_vocab_size: int = 2
    initializer_range: float = 0.02
    layer_norm_eps: float = 1e-12
    vocab_size: int = 30522

    @classmethod
    def from_dict(cls, value: dict):
        fields = inspect.signature(cls).parameters
        return cls(**{key: item for key, item in value.items() if key in fields})


class BertEmbeddings(nn.Module):
    def __init__(self, config: ModelArgs) -> None:
        super().__init__()
        self.word_embeddings = nn.Embedding(config.vocab_size, config.hidden_size)
        self.position_embeddings = nn.Embedding(
            config.max_position_embeddings, config.hidden_size
        )
        self.token_type_embeddings = nn.Embedding(
            config.type_vocab_size, config.hidden_size
        )
        self.LayerNorm = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)

    def __call__(self, input_ids, token_type_ids=None):
        length = input_ids.shape[1]
        positions = mx.arange(length, dtype=mx.int32)[None, :]
        if token_type_ids is None:
            token_type_ids = mx.zeros_like(input_ids)
        return self.LayerNorm(
            self.word_embeddings(input_ids)
            + self.position_embeddings(positions)
            + self.token_type_embeddings(token_type_ids)
        )


class BertSelfAttention(nn.Module):
    def __init__(self, config: ModelArgs) -> None:
        super().__init__()
        self.heads = config.num_attention_heads
        self.head_size = config.hidden_size // self.heads
        self.size = self.heads * self.head_size
        self.query = nn.Linear(config.hidden_size, self.size)
        self.key = nn.Linear(config.hidden_size, self.size)
        self.value = nn.Linear(config.hidden_size, self.size)

    def _heads(self, value):
        shape = value.shape[:-1] + (self.heads, self.head_size)
        return value.reshape(shape).transpose(0, 2, 1, 3)

    def __call__(self, hidden, attention_mask=None):
        query = self._heads(self.query(hidden))
        key = self._heads(self.key(hidden))
        value = self._heads(self.value(hidden))
        scores = mx.matmul(query, key.transpose(0, 1, 3, 2)) / math.sqrt(
            self.head_size
        )
        if attention_mask is not None:
            scores += attention_mask
        context = mx.matmul(mx.softmax(scores, axis=-1), value)
        return context.transpose(0, 2, 1, 3).reshape(hidden.shape)


class BertSelfOutput(nn.Module):
    def __init__(self, config: ModelArgs) -> None:
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.LayerNorm = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)

    def __call__(self, hidden, residual):
        return self.LayerNorm(self.dense(hidden) + residual)


class BertAttention(nn.Module):
    def __init__(self, config: ModelArgs) -> None:
        super().__init__()
        self.self = BertSelfAttention(config)
        self.output = BertSelfOutput(config)

    def __call__(self, hidden, attention_mask=None):
        return self.output(self.self(hidden, attention_mask), hidden)


class BertIntermediate(nn.Module):
    def __init__(self, config: ModelArgs) -> None:
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.intermediate_size)
        self.activation = nn.GELU()

    def __call__(self, hidden):
        return self.activation(self.dense(hidden))


class BertOutput(nn.Module):
    def __init__(self, config: ModelArgs) -> None:
        super().__init__()
        self.dense = nn.Linear(config.intermediate_size, config.hidden_size)
        self.LayerNorm = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)

    def __call__(self, hidden, residual):
        return self.LayerNorm(self.dense(hidden) + residual)


class BertLayer(nn.Module):
    def __init__(self, config: ModelArgs) -> None:
        super().__init__()
        self.attention = BertAttention(config)
        self.intermediate = BertIntermediate(config)
        self.output = BertOutput(config)

    def __call__(self, hidden, attention_mask=None):
        attention = self.attention(hidden, attention_mask)
        return self.output(self.intermediate(attention), attention)


class BertEncoder(nn.Module):
    def __init__(self, config: ModelArgs) -> None:
        super().__init__()
        self.layer = [BertLayer(config) for _ in range(config.num_hidden_layers)]

    def __call__(self, hidden, attention_mask=None):
        for layer in self.layer:
            hidden = layer(hidden, attention_mask)
        return hidden


class BertPooler(nn.Module):
    def __init__(self, config: ModelArgs) -> None:
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)

    def __call__(self, hidden):
        return mx.tanh(self.dense(hidden[:, 0]))


class BertModel(nn.Module):
    def __init__(self, config: ModelArgs) -> None:
        super().__init__()
        self.embeddings = BertEmbeddings(config)
        self.encoder = BertEncoder(config)
        # Retained because the converted checkpoint contains pooler weights.
        self.pooler = BertPooler(config)

    def __call__(self, input_ids, attention_mask, token_type_ids=None):
        hidden = self.embeddings(input_ids, token_type_ids)
        extended = (1.0 - attention_mask[:, None, None, :]) * -10000.0
        hidden = self.encoder(hidden, extended)
        expanded = attention_mask[:, :, None].astype(mx.float32)
        pooled = mx.sum(hidden * expanded, axis=1) / mx.maximum(
            mx.sum(expanded, axis=1), 1e-9
        )
        return pooled / mx.maximum(
            mx.linalg.norm(pooled, ord=2, axis=-1, keepdims=True), 1e-9
        )


class E5Embedder:
    def __init__(self, root: Path) -> None:
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        self.model = BertModel(ModelArgs.from_dict(config))
        weights = {}
        files = sorted(
            {
                *glob.glob(str(root / "**/model*.safetensors"), recursive=True),
                *glob.glob(str(root / "**/weights*.safetensors"), recursive=True),
            }
        )
        if not files:
            raise RuntimeError("Embedding checkpoint has no safetensors weights")
        for filename in files:
            weights.update(mx.load(filename))
        weights = {
            key.removeprefix("bert."): value
            for key, value in weights.items()
            if "position_ids" not in key
        }
        self.model.load_weights(list(weights.items()))
        mx.eval(self.model.parameters())
        self.model.eval()
        self.tokenizer = AutoTokenizer.from_pretrained(root, local_files_only=True)

    def encode(self, texts: list[str]) -> list[list[float]]:
        values = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="np",
        )
        embeddings = self.model(
            mx.array(values["input_ids"]),
            mx.array(values["attention_mask"]),
            (
                mx.array(values["token_type_ids"])
                if "token_type_ids" in values
                else None
            ),
        )
        mx.eval(embeddings)
        return embeddings.tolist()
