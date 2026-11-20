"""Checkpoint loading from a local directory or the Hugging Face Hub."""

from __future__ import annotations

import mlx.core as mx
from tokenizers import Tokenizer

from .. import weights
from ..config import HaruConfig
from ..hub import DEFAULT_REPO, resolve_checkpoint
from .haru import HaruModel

def load_tokenizer(path_or_repo: str = DEFAULT_REPO) -> Tokenizer:
    return Tokenizer.from_file(str(resolve_checkpoint(path_or_repo) / "tokenizer.json"))


def _convert(conversion: weights.Conversion, tensors: dict[str, mx.array], dtype: mx.Dtype | None) -> mx.array:
    """Build one model parameter from its checkpoint tensors (see :mod:`haru_mlx.weights`)."""
    parts = [tensors[name] for name in conversion.sources]
    value = parts[0] if len(parts) == 1 else mx.concatenate(parts, axis=0)
    layout = conversion.layout
    if layout == weights.GAMMA:
        return value.astype(mx.float32) + 1.0
    if layout == weights.SCALAR:
        return value.astype(mx.float32).reshape(())
    if layout == weights.CHANNELS_LAST:
        value = value.transpose(0, 2, 1)
    elif layout == weights.CONV_MATRIX:
        value = value.transpose(0, 2, 1).reshape(conversion.shape)
    elif layout == weights.CONV_TRANSPOSE_MATRIX:
        value = value.transpose(1, 2, 0).reshape(conversion.shape)
    return value if dtype is None else value.astype(dtype)


def load_model(
    path_or_repo: str = DEFAULT_REPO,
    dtype: mx.Dtype | None = None,
    revision: str | None = None,
    quantize: int | None = None,
) -> HaruModel:
    """Build a :class:`HaruModel` with its tokenizer attached.

    ``dtype`` defaults to the checkpoint's (bfloat16); pass ``mx.float32`` to
    run on CPU. ``quantize=8`` stores the backbone and the embedding table
    with 8 bits per weight, see :meth:`HaruModel.quantize`.
    """
    directory = resolve_checkpoint(path_or_repo, revision)
    config = HaruConfig.from_file(directory / "config.json")
    model = HaruModel(config)

    tensors = mx.load(str(directory / "model.safetensors"))
    plan = weights.conversion_plan({name: tuple(tensor.shape) for name, tensor in tensors.items()})
    weights.check_plan(plan, weights.parameter_shapes(config))
    # Tensors are read lazily: nothing is in memory until it is evaluated, and
    # a tensor that only feeds a stacked or quantized weight is freed again.
    model.load_weights([(name, _convert(conversion, tensors, dtype)) for name, conversion in plan.items()])
    del tensors
    if quantize is not None:
        model.quantize(bits=quantize)
    mx.eval(model.parameters())

    model.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
    model.eval()
    return model
