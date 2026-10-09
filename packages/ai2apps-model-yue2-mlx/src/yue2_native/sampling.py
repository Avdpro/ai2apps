"""Request-local MLX sampling with the released vocabulary and CFG arithmetic."""

import time

import mlx.core as mx

from .protocol import ABC_END, CODEC_OFFSET, CODEC_SIZE, CONTEXT, EOD, MUSIC_END


def distribution(logits, sampling, history, step, phase, legacy_off=False):
    scores = logits if legacy_off else logits.astype(mx.float32)
    ids = mx.arange(scores.shape[-1])
    end = ABC_END if phase == "abc" else MUSIC_END
    allowed = (
        ids < EOD
        if phase == "abc"
        else (ids >= CODEC_OFFSET) & (ids < CODEC_OFFSET + CODEC_SIZE)
    )
    allowed = allowed | ((ids == end) & (step >= sampling.min_tokens))
    scores = mx.where(allowed, scores, -mx.inf)
    if sampling.repetition_penalty != 1 and history:
        recent = history[-sampling.penalty_window :]
        freq = mx.zeros(scores.shape[-1], dtype=scores.dtype)
        freq = freq.at[mx.array(recent)].add(mx.ones(len(recent), dtype=scores.dtype))
        alpha = sampling.repetition_penalty**freq
        scores = mx.where(scores < 0, scores * alpha, scores / alpha)
    if sampling.temperature == 0:
        return scores
    scores = scores / sampling.temperature
    threshold = mx.min(
        mx.topk(scores, min(sampling.top_k, scores.shape[-1])), axis=-1, keepdims=True
    )
    scores = mx.where(scores < threshold, -mx.inf, scores)
    if sampling.top_p < 1:
        order = mx.argsort(-scores, axis=-1)
        values = mx.take_along_axis(scores, order, axis=-1)
        probs = mx.softmax(values, axis=-1)
        removed = mx.cumsum(probs, axis=-1) - probs > sampling.top_p
        removed[..., : 3 if legacy_off else 1] = False
        values = mx.where(removed, -mx.inf, values)
        scores = mx.zeros_like(scores)
        scores = mx.put_along_axis(scores, order, values, axis=-1)
    return scores


def generate_tokens(
    model,
    prefix,
    sampling,
    seed,
    phase,
    negative=None,
    cfg_scale=1.0,
    legacy_off=False,
    cancelled=None,
    on_token=None,
):
    if len(prefix) + sampling.max_tokens > CONTEXT:
        raise ValueError("Prefix plus generation budget exceeds context")
    if cfg_scale != 1 and not negative:
        raise ValueError("CFG needs negative prefix")
    if negative and len(negative) + sampling.max_tokens > CONTEXT:
        raise ValueError("Negative prefix exceeds context")
    output_range = (
        (MUSIC_END, CODEC_OFFSET + CODEC_SIZE) if phase == "semantic" else None
    )

    def forward(ids, state):
        compact = model(ids, state, output_range=output_range)[:, -1]
        if output_range is None:
            return compact
        # Retain the original full-vocabulary categorical RNG positions and masks.
        # Only the unobservable LM-head rows are skipped, not sampling semantics.
        scores = mx.full(
            (compact.shape[0], model.config.vocab_size), -mx.inf, compact.dtype
        )
        scores[:, output_range[0] : output_range[1]] = compact
        return scores

    start = time.perf_counter()
    cache = model.cache()
    neg_cache = model.cache() if cfg_scale != 1 else None

    def prefill(tokens, state):
        for a in range(0, len(tokens), 512):
            if cancelled and cancelled():
                raise InterruptedError("Cancelled during prefill")
            logits = forward(mx.array([tokens[a : a + 512]]), state)
            mx.eval(logits)
        return logits

    positive = prefill(prefix, cache)
    negative_logits = prefill(negative, neg_cache) if neg_cache else None
    prefill_seconds = time.perf_counter() - start
    history = []
    eos = False
    first = None
    key = mx.array([seed >> 32, seed & 0xFFFFFFFF], dtype=mx.uint32)
    end = ABC_END if phase == "abc" else MUSIC_END
    for step in range(sampling.max_tokens):
        if cancelled and cancelled():
            raise InterruptedError("Cancelled during " + phase)
        logits = (
            positive
            if neg_cache is None
            else negative_logits + cfg_scale * (positive - negative_logits)
        )
        scores = distribution(logits, sampling, history, step, phase, legacy_off)
        key, draw = mx.random.split(key)
        next_id = (
            mx.argmax(scores, axis=-1)
            if sampling.temperature == 0
            else mx.random.categorical(scores.astype(mx.float32), key=draw)
        )
        mx.async_eval(next_id)
        # Queue the next forward before waiting for this token on the host.
        # This overlaps Python graph construction with GPU sampling/decoding.
        # At EOS one speculative forward is discarded; no extra token is emitted.
        if step + 1 < sampling.max_tokens:
            ids = next_id.reshape(1, 1)
            next_positive = forward(ids, cache)
            next_negative = forward(ids, neg_cache) if neg_cache else None
            mx.async_eval(next_positive, *([next_negative] if neg_cache else []))
        token = int(next_id.item())
        if first is None:
            first = time.perf_counter() - start
        if on_token:
            on_token(phase, token)
        if token == end:
            eos = True
            break
        history.append(token)
        if step + 1 < sampling.max_tokens:
            positive = next_positive
            if neg_cache:
                negative_logits = next_negative
    # Include any discarded EOS prefetch in elapsed time and release accounting.
    mx.synchronize()
    elapsed = time.perf_counter() - start
    return (
        history,
        {
            "seconds": elapsed,
            "prefill_seconds": prefill_seconds,
            "ttft_seconds": first,
            "content_tokens": len(history),
            "output_tokens": len(history) + int(eos),
            "output_tps": (len(history) + int(eos)) / elapsed,
            "cfg_branches": 1 if neg_cache is None else 2,
        },
        not eos,
    )
