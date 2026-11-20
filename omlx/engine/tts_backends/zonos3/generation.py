"""SuperBPE prompts, delay-pattern alignment, and MLX sampling."""

from __future__ import annotations

import bisect
import hashlib
import math
from pathlib import Path

import mlx.core as mx


class TextTokenizer:
    def __init__(self, root, spec, text_vocab):
        from tokenizers import Tokenizer

        if (spec["kind"], spec["offset"], spec["bos"], spec["eos"]) != (
            "superbpe",
            4,
            2,
            3,
        ):
            raise ValueError("unsupported SuperBPE ID convention")
        if text_vocab != spec["vocab_size"] + 4:
            raise ValueError("SuperBPE vocabulary mismatch")
        raw = (Path(root) / spec["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != spec["sha256"]:
            raise ValueError("SuperBPE SHA mismatch")
        self.tokenizer = Tokenizer.from_str(raw.decode())
        if (
            self.tokenizer.get_vocab_size(with_added_tokens=True) != spec["vocab_size"]
            or self.tokenizer.padding is not None
            or self.tokenizer.truncation is not None
        ):
            raise ValueError("SuperBPE artifact mismatch")

    def encode(self, text):
        return [
            2,
            *[i + 4 for i in self.tokenizer.encode(text, add_special_tokens=False).ids],
            3,
        ]


def delay_codes(codes, pad_id, flush=True):
    codes = mx.array(codes, dtype=mx.int32)
    length, channels = codes.shape
    out = mx.full((length + (channels - 1 if flush else 0), channels), pad_id, mx.int32)
    for cb in range(channels):
        take = min(length, len(out) - cb)
        if take > 0:
            out[cb : cb + take, cb] = codes[:take, cb]
    return out


def aligned_codes(rows, n_codebooks, eos_frame=None, start=0):
    length = max(0, len(rows) - n_codebooks + 1)
    if eos_frame is not None:
        length = min(length, eos_frame)
    if length <= start:
        return mx.zeros((0, n_codebooks), mx.int32)
    rows = mx.array(rows[start : length + n_codebooks - 1], dtype=mx.int32)
    return mx.stack(
        [rows[cb : cb + length - start, cb] for cb in range(n_codebooks)], axis=-1
    )


def condition_ids(config, buckets=None, values=None):
    if buckets is not None and values is not None:
        raise ValueError(
            "condition_buckets and condition_values are mutually exclusive"
        )
    names, counts = config.condition_names, config.condition_bucket_counts
    supplied = values if values is not None else buckets
    if supplied is None:
        return list(counts)
    if isinstance(supplied, dict):
        if set(supplied) - set(names):
            raise ValueError(
                f"unknown conditions: {sorted(set(supplied) - set(names))}"
            )
        supplied = [supplied.get(name) for name in names]
    if len(supplied) != len(names):
        raise ValueError(f"expected {len(names)} conditions")
    result = []
    for name, count, value in zip(names, counts, supplied):
        if value is None:
            result.append(count)
        elif values is not None:
            if not math.isfinite(float(value)):
                raise ValueError("condition values must be finite")
            result.append(
                bisect.bisect_right(config.condition_edges[name], float(value))
            )
        else:
            if int(value) != value or not 0 <= int(value) <= count:
                raise ValueError(f"{name} bucket must be in [0, {count}]")
            result.append(int(value))
    return result


def sample_row(
    logits,
    config,
    *,
    step,
    history,
    temperature=0.75,
    top_k=80,
    top_p=0.69,
    min_p=0.0,
    repetition_penalty=2.4,
    repetition_window=96,
    repetition_codebooks=6,
    min_frames=0,
    has_audio_prefix=False,
    key=None,
):
    c = config
    ids = mx.arange(logits.shape[-1])[None]
    invalid = (ids == c.audio_pad_id) | ((ids >= c.codebook_size) & (ids != c.eoa_id))
    invalid = invalid | (
        (ids == c.eoa_id) & (step < min_frames + mx.arange(c.n_codebooks)[:, None])
    )
    x = mx.where(invalid, -mx.inf, logits.astype(mx.float32))
    window = min(max(int(repetition_window), 0), len(history))
    if window and repetition_penalty > 1 and repetition_codebooks:
        recent = mx.array(history[-window:], dtype=mx.int32)[:, : c.n_codebooks].T
        valid = (recent >= 0) & (recent < c.codebook_size)
        if repetition_codebooks >= 0:
            valid = valid & (mx.arange(c.n_codebooks)[:, None] < repetition_codebooks)
        # Add counts so duplicate ids and invalid entries clamped to code zero
        # cannot overwrite one another's presence flags.
        repeated = mx.zeros(logits.shape, mx.int32)
        repeated = (
            repeated.at[
                mx.arange(c.n_codebooks)[:, None],
                mx.clip(recent, 0, logits.shape[-1] - 1),
            ].add(valid.astype(mx.int32))
            > 0
        )
        x = mx.where(
            repeated,
            mx.where(x > 0, x / repetition_penalty, x * repetition_penalty),
            x,
        )
    if temperature <= 0:
        token = mx.argmax(x, axis=-1)
    else:
        x = x / temperature
        if 0 < top_k < x.shape[-1]:
            threshold = mx.min(mx.topk(x, top_k, axis=-1), axis=-1, keepdims=True)
            x = mx.where(x < threshold, -mx.inf, x)
        probs = mx.softmax(x, axis=-1)
        if 0 < top_p < 1:
            order = mx.argsort(-probs, axis=-1)
            ranked = mx.take_along_axis(probs, order, axis=-1)
            ranked = mx.where(mx.cumsum(ranked, axis=-1) - ranked > top_p, 0.0, ranked)
            probs = mx.put_along_axis(mx.zeros_like(probs), order, ranked, axis=-1)
            probs = probs / mx.maximum(probs.sum(axis=-1, keepdims=True), 1e-8)
        if min_p > 0:
            probs = mx.where(
                probs < min_p * probs.max(axis=-1, keepdims=True), 0.0, probs
            )
        greedy = ids == mx.argmax(x, axis=-1, keepdims=True)
        probs = mx.where(probs.sum(axis=-1, keepdims=True) <= 0, greedy, probs)
        token = mx.random.categorical(mx.log(probs), key=key)
    if not has_audio_prefix:
        token = mx.where(mx.arange(c.n_codebooks) > step, c.audio_pad_id, token)
    return token.astype(mx.int32)


def output_audio(audio, gain):
    audio = mx.array(audio, dtype=mx.float32) * gain
    knee = 10 ** (-1 / 20)
    magnitude = mx.abs(audio)
    limited = knee + (1 - knee) * mx.tanh((magnitude - knee) / (1 - knee))
    return mx.where(magnitude > knee, mx.sign(audio) * limited, audio)
