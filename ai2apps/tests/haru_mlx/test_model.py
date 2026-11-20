"""The MLX model on a small random configuration, and (with ``HARU_MODEL``) a real conversation."""

import os

import numpy as np
import pytest

mx = pytest.importorskip("mlx.core")

from mlx.utils import tree_flatten, tree_map  # noqa: E402

from ai2apps.model_worker.haru_mlx import weights  # noqa: E402
from ai2apps.model_worker.haru_mlx.models import CodecStream, HaruModel  # noqa: E402


@pytest.fixture(scope="module")
def model(tiny_config):
    """Random weights: enough to check shapes and that the streaming paths agree."""
    mx.random.seed(0)
    model = HaruModel(tiny_config)

    def randomize(value):
        scale = 0.1 if value.ndim <= 1 else value.shape[-1] ** -0.5
        return (mx.random.normal(value.shape) * scale).astype(mx.float32)

    model.update(tree_map(randomize, model.parameters()))
    model.latent_scale, model.latent_bias = mx.array(0.2), mx.array(0.05)
    mx.eval(model.parameters())
    return model


def relative_error(a, b) -> float:
    a, b = np.array(a, dtype=np.float64), np.array(b, dtype=np.float64)
    return float(np.linalg.norm(a - b) / (np.linalg.norm(b) + 1e-12))


def test_parameters_match_the_declared_shapes(tiny_config):
    parameters = {name: tuple(value.shape) for name, value in tree_flatten(HaruModel(tiny_config).parameters())}
    assert parameters == weights.parameter_shapes(tiny_config)


def test_real_configuration_matches_the_declared_shapes(checkpoint):
    from ai2apps.model_worker.haru_mlx.config import HaruConfig

    config = HaruConfig.from_file(checkpoint / "config.json")
    # Parameters are created lazily: listing their shapes allocates nothing.
    parameters = {name: tuple(value.shape) for name, value in tree_flatten(HaruModel(config).parameters())}
    assert parameters == weights.parameter_shapes(config)


def test_backbone_step_by_step_equals_one_call(model):
    embeddings = mx.random.normal((1, 12, model.config.hidden_size))
    whole = model(embeddings, model.new_cache())
    cache = model.new_cache()
    prefix = model(embeddings[:, :5], cache)
    steps = [model(embeddings[:, i : i + 1], cache) for i in range(5, 12)]
    assert relative_error(mx.concatenate([prefix, *steps], axis=1), whole) < 1e-4


def test_embed_masks_audio_streams(model):
    tokens = mx.array([[5, 6, 7]])
    latents = mx.random.normal((1, 3, model.config.latent_dim))
    text_only = model.embed(tokens)
    masked = model.embed(tokens, latents, latents, mx.array([[False, True, True]]), mx.array([[False, False, True]]))
    assert relative_error(masked[:, 0], text_only[:, 0]) < 1e-6
    assert relative_error(masked[:, 1], text_only[:, 1]) > 1e-3
    assert relative_error(model.unscale_latents(model.scale_latents(latents)), latents) < 1e-5


def test_logits_fp32_matches_logits(model):
    hidden = mx.random.normal((1, model.config.hidden_size))
    tokens = mx.array([3, 248076])
    assert relative_error(model.logits_fp32(hidden, tokens), model.logits(hidden)[:, tokens]) < 1e-5


def test_codec_stream_equals_whole_clip(model):
    frame = model.config.frame_samples
    audio = 0.1 * mx.random.normal((3 * frame,))
    whole = model.codec.encode(audio)
    assert whole.shape == (1, 3, model.config.latent_dim)
    assert model.codec.encode(audio[: 2 * frame + 17]).shape[1] == 3  # a partial last frame counts

    stream = CodecStream(model.codec)
    for piece in np.array_split(np.array(audio), [10, 450, 3000, 3200, 5111, 9000]):
        stream.feed(mx.array(piece))
    assert stream.frames_ready == 3
    fed = mx.concatenate([stream.pop() for _ in range(3)], axis=1)
    assert relative_error(fed, whole) < 1e-4
    assert relative_error(CodecStream(model.codec).encode(audio[None]), whole) < 1e-4

    latents = mx.random.normal((1, 3, model.config.latent_dim))
    decoded = mx.concatenate([stream.decode(latents[:, i : i + 1]) for i in range(3)], axis=1)
    assert decoded.shape == (1, 3 * frame)
    assert relative_error(decoded, model.codec.decode(latents)) < 1e-4
    with pytest.raises(RuntimeError):
        stream.pop()


def test_head_is_deterministic_and_follows_guidance(model):
    hidden = mx.random.normal((2, model.config.hidden_size))
    noise = mx.random.normal((2, model.config.latent_dim))
    a = model.head.sample(hidden, noise, 1.5)
    assert a.shape == noise.shape
    assert relative_error(model.head.sample(hidden, noise), a) == 0.0  # the configured default scale
    assert relative_error(model.head.sample(hidden, noise, 1.0), a) > 1e-6
    assert model.head.sample(hidden, noise, 1.5, steps=2).shape == noise.shape


def test_quantized_backbone_stays_close(tiny_config):
    mx.random.seed(1)
    model = HaruModel(tiny_config)
    mx.eval(model.parameters())
    embeddings = mx.random.normal((1, 4, tiny_config.hidden_size))
    exact = model(embeddings, model.new_cache())
    logits = model.logits(exact)
    model.quantize(bits=8)
    assert relative_error(model(embeddings, model.new_cache()), exact) < 0.1
    assert relative_error(model.logits(exact), logits) < 0.1
    with pytest.raises(ValueError):
        model.quantize(bits=3)


# ------------------------------------------------------------ real checkpoint

needs_checkpoint = pytest.mark.skipif(not os.environ.get("HARU_MODEL"), reason="set HARU_MODEL to a checkpoint")


@pytest.fixture(scope="module")
def loaded(checkpoint):
    from ai2apps.model_worker.haru_mlx import load_model

    dtype = os.environ.get("HARU_PARITY_DTYPE")
    return load_model(str(checkpoint), dtype=getattr(mx, dtype) if dtype else None)


def voice(seconds: float = 4.0) -> np.ndarray:
    t = np.arange(int(seconds * 24_000)) / 24_000
    return (0.2 * np.sin(2 * np.pi * 180 * t) * (1 + np.sin(2 * np.pi * 3 * t))).astype(np.float32)


@needs_checkpoint
def test_session_produces_frames_and_is_reproducible(loaded):
    from ai2apps.model_worker.haru_mlx import DuplexConfig, DuplexSession

    def run():
        session = DuplexSession(loaded, "You are Haru.", voice(), DuplexConfig(seed=7, speak_first=True))
        frames = [session.start()]
        silence = np.zeros(session.frame_samples, dtype=np.float32)
        frames += [session.step(silence) for _ in range(3)]
        # The same audio through feed() in pieces, then step() without an argument.
        session.feed(silence[:1000])
        session.feed(silence[1000:])
        assert session.frames_ready == 1
        frames.append(session.step())
        return session, frames

    session, frames = run()
    assert [frame.index for frame in frames] == [0, 1, 2, 3, 4]
    assert all(frame.audio.shape == (3200,) and frame.audio.dtype == np.float32 for frame in frames)
    assert all(np.isfinite(frame.audio).all() and np.abs(frame.audio).max() <= 1.0 for frame in frames)
    assert frames[0].token not in (loaded.config.pad_token_id, loaded.config.eop_token_id)  # it speaks first
    _, again = run()
    assert [frame.token for frame in again] == [frame.token for frame in frames]
    assert all(np.array_equal(a.audio, b.audio) for a, b in zip(again, frames))


@needs_checkpoint
def test_step_rejects_a_wrong_frame_size(loaded):
    from ai2apps.model_worker.haru_mlx import DuplexSession

    session = DuplexSession(loaded)
    with pytest.raises(RuntimeError):
        session.step(np.zeros(3200, dtype=np.float32))
    session.start()
    with pytest.raises(ValueError):
        session.step(np.zeros(100, dtype=np.float32))
