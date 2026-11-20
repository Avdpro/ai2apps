"""Numerical parity with the PyTorch package on fixed inputs.

Needs MLX, a checkpoint (``HARU_MODEL``) and the outputs of
``parity/dump_reference.py`` for the same checkpoint (``HARU_REFERENCE``).
``HARU_PARITY_DTYPE=float32`` loads the weights in float32 (for a dump made
with ``--dtype float32``); the tolerance follows the dtype.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

mx = pytest.importorskip("mlx.core")

MODEL = os.environ.get("HARU_MODEL")
REFERENCE = os.environ.get("HARU_REFERENCE")
DTYPE = os.environ.get("HARU_PARITY_DTYPE")
pytestmark = pytest.mark.skipif(not (MODEL and REFERENCE), reason="set HARU_MODEL and HARU_REFERENCE")


def relative_error(value, expected) -> float:
    value, expected = np.asarray(value, dtype=np.float64), np.asarray(expected, dtype=np.float64)
    assert value.shape == expected.shape
    return float(np.linalg.norm(value - expected) / (np.linalg.norm(expected) + 1e-12))


@pytest.fixture(scope="module")
def model():
    from ai2apps.model_worker.haru_mlx import load_model

    return load_model(MODEL, dtype=getattr(mx, DTYPE) if DTYPE else None)


@pytest.fixture(scope="module")
def ref():
    return dict(np.load(REFERENCE))


@pytest.fixture(scope="module")
def tolerance(model) -> float:
    # float32: the prompt runs through a chunked form of the Gated DeltaNet recurrence
    # in PyTorch and position by position here; the two agree to about three digits.
    # bfloat16 keeps 8 significant bits and the frameworks round at different places:
    # PyTorch's own bfloat16 hidden states are 6e-2 to 7e-2 from its float32 ones, and
    # the ones here, on an Apple GPU, up to 1.6e-1 from either.
    return 5e-3 if model.dtype == mx.float32 else 0.2


@pytest.fixture(scope="module")
def audio_tolerance(model, tolerance) -> float:
    # The decoder amplifies rounding: in bfloat16 its output moves by about 20 %
    # of its norm between any two implementations (and against float32).
    return tolerance if model.dtype == mx.float32 else 0.35


@pytest.fixture(scope="module")
def hidden(model, ref):
    """Hidden states of the prompt in one call, then one position at a time."""
    n, prefill = ref["text"].shape[0], int(ref["prefill"])
    cache = model.new_cache()
    out = []
    for s, e in [(0, prefill)] + [(i, i + 1) for i in range(prefill, n)]:
        embeddings = model.embed(
            mx.array(ref["text"][None, s:e]),
            mx.array(ref["model_latents"][None, s:e]),
            mx.array(ref["user_latents"][None, s:e]),
            mx.array(ref["model_mask"][None, s:e]),
            mx.array(ref["user_mask"][None, s:e]),
        )
        out.append(model(embeddings, cache)[0])
        mx.eval(out[-1], [a for c in cache for a in c.arrays()])
    return mx.concatenate(out)


def test_backbone(hidden, ref, tolerance):
    prefill = int(ref["prefill"])
    value = np.array(hidden.astype(mx.float32))
    assert relative_error(value[:prefill], ref["hidden"][:prefill]) < tolerance
    assert relative_error(value[prefill:], ref["hidden"][prefill:]) < tolerance


def test_logits(model, hidden, ref, tolerance):
    steps = ref["stream_logits"].shape[0]
    logits = np.array(model.logits(hidden[-steps:]))
    assert relative_error(logits.max(axis=-1), ref["logits_max"]) < tolerance
    if model.dtype == mx.float32:
        assert (logits.argmax(axis=-1) == ref["logits_top"][:, 0]).all()
    cfg = model.config
    stream = model.logits_fp32(hidden[-steps:], mx.array([cfg.pad_token_id, cfg.eop_token_id]))
    assert relative_error(np.array(stream), ref["stream_logits"]) < tolerance


def test_head(model, ref, tolerance):
    # From the reference hidden states, so that this isolates the head.
    conditions = mx.array(ref["hidden"]).astype(model.dtype)
    noise = mx.array(ref["noise"]).astype(model.dtype)
    latents = model.unscale_latents(model.head.sample(conditions, noise, model.config.head.guidance_scale))
    assert relative_error(np.array(latents), ref["head_latents"]) < tolerance


def test_codec_whole_clip(model, ref, tolerance, audio_tolerance):
    mean = model.codec.encode(mx.array(ref["clip"]))
    assert relative_error(np.array(mean), ref["clip_mean"]) < tolerance
    audio = model.codec.decode(mx.array(ref["latents"]))
    assert relative_error(np.array(audio), ref["clip_audio"]) < audio_tolerance


def test_codec_stream(model, ref, tolerance, audio_tolerance):
    from ai2apps.model_worker.haru_mlx.models import CodecStream

    stream = CodecStream(model.codec)
    frames = ref["frames"][0]
    # Uneven pieces, as a microphone delivers them.
    for piece in np.array_split(frames, [100, 1500, 3200, 3300, 7000]):
        stream.feed(mx.array(piece))
    assert stream.frames_ready == frames.shape[0] // model.config.frame_samples
    mean = mx.concatenate([stream.pop() for _ in range(stream.frames_ready)], axis=1)
    assert relative_error(np.array(mean), ref["stream_mean"]) < tolerance

    latents = mx.array(ref["latents"])
    audio = mx.concatenate([stream.decode(latents[:, i : i + 1]) for i in range(latents.shape[1])], axis=1)
    assert relative_error(np.array(audio), ref["stream_audio"]) < audio_tolerance
    # Frame by frame equals the whole sequence at once (in bfloat16 up to the
    # decoder's rounding, as in PyTorch).
    whole = np.array(model.codec.decode(latents))
    assert relative_error(np.array(audio), whole) < (1e-3 if model.dtype == mx.float32 else audio_tolerance)
