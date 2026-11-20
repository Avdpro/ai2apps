"""Ex-Omni text-hidden-state to multi-codebook speech generation.

Uses the already pinned Runtime mlx-audio Talker. Reference-speaker embeddings
can be prepared with SpeakerEncoder in speaker.py and supplied by the caller.
"""

import json
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
from mlx_audio.tts.models.qwen3_tts.config import (
    Qwen3TTSTalkerConfig,
    filter_dict_for_dataclass,
)
from mlx_audio.tts.models.qwen3_tts.talker import Qwen3TTSTalkerForConditionalGeneration

from .speech import TQGF


class SpeechGenerator(nn.Module):
    def __init__(self, llm_hidden_size, talker_config):
        super().__init__()
        self.talker = Qwen3TTSTalkerForConditionalGeneration(talker_config)
        dim = talker_config.hidden_size
        self.input_proj = nn.Sequential(
            nn.Linear(llm_hidden_size, dim * 4), nn.GELU(), nn.Linear(dim * 4, dim * 4)
        )
        self.fusion = TQGF(dim)
        self._key = mx.random.key(0)

    @classmethod
    def from_pretrained(cls, exomni_dir, qwen_config):
        root = Path(exomni_dir)
        config = json.loads((root / "config.json").read_text())
        tconfig = json.loads(Path(qwen_config).read_text())["talker_config"]
        model = cls(
            config["hidden_size"],
            Qwen3TTSTalkerConfig(
                **filter_dict_for_dataclass(Qwen3TTSTalkerConfig, tconfig)
            ),
        )
        index = json.loads((root / "model.safetensors.index.json").read_text())[
            "weight_map"
        ]
        prefix = "model.speech_generator."
        names = {
            k
            for k in index
            if k.startswith(
                tuple(prefix + part for part in ("talker.", "input_proj.", "fusion."))
            )
        }
        weights = {}
        for shard in sorted({index[k] for k in names}):
            state = mx.load(str(root / shard))
            for key in names.intersection(state):
                name = key[len(prefix) :]
                if name.startswith("input_proj."):
                    name = name.replace("input_proj.", "input_proj.layers.", 1)
                elif name.startswith("fusion.layers."):
                    parts = name.split(".")
                    if parts[3] == "1":
                        parts.insert(4, "layers")
                    name = ".".join(parts)
                weights[name] = state[key]
        model.load_weights(list(weights.items()), strict=True)
        model.eval()
        mx.eval(model.parameters())
        return model

    def embed_codes(self, codes):
        value = self.talker.get_input_embeddings()(codes[..., 0])
        for i in range(1, codes.shape[-1]):
            value = value + self.talker.code_predictor.codec_embedding[i - 1](
                codes[..., i]
            )
        return value

    def _sample(
        self,
        logits,
        history,
        *,
        sample,
        temperature,
        top_k,
        top_p,
        repetition_penalty=1,
        repetition_aware=False,
        main=False,
        ignore_eos=False,
    ):
        scores = logits.astype(mx.float32)
        scores = scores - mx.logsumexp(scores, axis=-1)
        config = self.talker.config
        eos = config.codec_eos_token_id
        if main:
            ids = mx.arange(scores.size)
            allowed = ids < config.code_predictor_config.vocab_size
            if not ignore_eos:
                allowed = allowed | (ids == eos)
            scores = mx.where(allowed, scores, -float("inf"))
        if repetition_penalty <= 0:
            raise ValueError("Repetition penalty must be positive")
        if history and repetition_penalty != 1:
            indices = mx.array(sorted(set(history)), dtype=mx.int32)
            values = scores[indices]
            scores = scores.at[indices].add(
                mx.where(
                    values < 0, values * repetition_penalty, values / repetition_penalty
                )
                - values
            )
        if not sample:
            return int(mx.argmax(scores).item())
        if temperature <= 0 or not 0 < top_p <= 1:
            raise ValueError("Invalid sampling temperature/top_p")
        scores = scores / temperature
        unfiltered = scores
        if 0 < top_k < scores.size:
            cutoff = mx.sort(scores)[-top_k]
            scores = mx.where(scores >= cutoff, scores, -float("inf"))
        if top_p < 1:
            order = mx.argsort(-scores)
            sorted_scores = scores[order]
            prob = mx.softmax(sorted_scores)
            kept = mx.where(
                mx.cumsum(prob) - prob > top_p, -float("inf"), sorted_scores
            )
            scores = kept[mx.argsort(order)]
        self._key, key = mx.random.split(self._key)
        candidate = int(mx.random.categorical(scores, key=key).item())
        if repetition_aware and history[-10:].count(candidate) > 1:
            self._key, key = mx.random.split(self._key)
            candidate = int(mx.random.categorical(unfiltered, key=key).item())
        return candidate

    def generate_codes(
        self,
        hidden,
        text_tokens,
        *,
        speaker_embedding=None,
        max_tokens=750,
        min_token_text_ratio=2,
        max_token_text_ratio=20,
        sample=True,
        temperature=0.9,
        top_k=50,
        top_p=1.0,
        repetition_penalty=1.05,
        seed=0,
        cancel_check=lambda: None,
    ):
        if (
            hidden.shape[0] != 1
            or text_tokens.shape[0] != 1
            or text_tokens.shape[1] < 2
        ):
            raise ValueError("Expected one nonempty text sequence including final EOS")
        if max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        self._key = mx.random.key(seed)
        config = self.talker.config
        text = text_tokens[:, :-1]
        query = self.talker.text_projection(self.talker.get_text_embeddings()(text))
        projected = self.input_proj(hidden)
        b, n, _ = projected.shape
        projected = (
            projected.reshape(b, n, config.hidden_size, 4)
            .transpose(0, 1, 3, 2)
            .reshape(b, n * 4, config.hidden_size)
        )
        query = self.fusion(projected, query)
        parts = [
            query,
            self.talker.get_input_embeddings()(mx.array([[config.codec_bos_id]])),
        ]
        if speaker_embedding is not None:
            parts.insert(0, speaker_embedding.astype(query.dtype))
        cache = self.talker.make_cache()
        logits, last = self.talker(mx.concatenate(parts, axis=1), cache=cache)
        frames = []
        history = []
        steps = min(max_tokens, text.shape[1] * max_token_text_ratio)
        for step in range(steps):
            cancel_check()
            first = self._sample(
                logits[0, -1],
                history,
                sample=sample,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                repetition_aware=True,
                main=True,
                ignore_eos=step < text.shape[1] * min_token_text_ratio,
            )
            if first == config.codec_eos_token_id:
                break
            codes = [first]
            predictor = self.talker.code_predictor
            pcache = predictor.make_cache()
            embed = self.talker.get_input_embeddings()(mx.array([[first]]))
            prefix = mx.concatenate([last[:, -1:], embed], axis=1)
            for group in range(1, config.num_code_groups):
                cancel_check()
                output, _, _ = predictor(
                    prefix, cache=pcache, generation_step=group - 1
                )
                token = self._sample(
                    output[0, -1],
                    [],
                    sample=sample,
                    temperature=temperature,
                    top_k=top_k,
                    top_p=top_p,
                )
                codes.append(token)
                prefix = predictor.codec_embedding[group - 1](mx.array([[token]]))
            history.append(first)
            frames.append(codes)
            if step + 1 < steps:
                logits, last = self.talker(
                    self.embed_codes(mx.array([[codes]])), cache=cache
                )
        return mx.array(frames, dtype=mx.int32).reshape(
            1, len(frames), config.num_code_groups
        )
