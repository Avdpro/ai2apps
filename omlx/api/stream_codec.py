"""Stable pure-Python stream decoding extension points for model Packages.

Model Packages may provide a codec object from their signed Python adapter, but
native tokenizers, kernels and execution remain owned by the oMLX Runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Protocol, runtime_checkable

MODEL_STREAM_CODEC_API = "ai2apps.model-stream-codec/v1"
_UNICODE_REPLACEMENT = "\ufffd"


@runtime_checkable
class ModelStreamCodec(Protocol):
    """Package-overridable token-prefix to append-only text contract."""

    api_version: str

    def decode_prefix(
        self,
        tokenizer: Any,
        token_ids: list[int],
        *,
        eos_token_id: int | None,
    ) -> str: ...

    def append_delta(self, previous: str, current: str) -> tuple[str, str]: ...


@dataclass(frozen=True, slots=True)
class PrefixTextStreamCodec:
    """Decode the complete generated prefix and emit only its stable suffix.

    Keeping special tokens visible lets the Runtime reasoning parser split
    ``<think>`` boundaries.  A trailing replacement character is withheld
    because tokenizers may expose it while a multi-byte UTF-8 sequence is
    incomplete and revise it after the next token arrives.
    """

    api_version: ClassVar[str] = MODEL_STREAM_CODEC_API
    skip_special_tokens: bool = False
    strip_terminal_eos: bool = True
    withhold_incomplete_unicode: bool = True

    def decode_prefix(
        self,
        tokenizer: Any,
        token_ids: list[int],
        *,
        eos_token_id: int | None,
    ) -> str:
        decode_ids = token_ids
        if (
            self.strip_terminal_eos
            and token_ids
            and eos_token_id is not None
            and token_ids[-1] == eos_token_id
        ):
            decode_ids = token_ids[:-1]
        text = tokenizer.decode(
            decode_ids,
            skip_special_tokens=self.skip_special_tokens,
        )
        if self.withhold_incomplete_unicode:
            text = text.rstrip(_UNICODE_REPLACEMENT)
        return text

    def append_delta(self, previous: str, current: str) -> tuple[str, str]:
        if current.startswith(previous):
            return current, current[len(previous) :]
        # Fail closed on an unstable decoder prefix. Replaying the entire
        # generation would duplicate content and can expose reasoning text.
        return previous, ""


def validate_model_stream_codec(codec: Any) -> ModelStreamCodec:
    """Validate a Package-provided codec before it reaches generation."""

    if getattr(codec, "api_version", None) != MODEL_STREAM_CODEC_API:
        raise ValueError(
            f"Model stream codec must use {MODEL_STREAM_CODEC_API}"
        )
    if not callable(getattr(codec, "decode_prefix", None)) or not callable(
        getattr(codec, "append_delta", None)
    ):
        raise TypeError("Model stream codec must implement decode_prefix and append_delta")
    return codec


__all__ = [
    "MODEL_STREAM_CODEC_API",
    "ModelStreamCodec",
    "PrefixTextStreamCodec",
    "validate_model_stream_codec",
]
