"""Conversation prompt: a character card, then a voice reference.

    position:  [0, P)          [P, S)                 [S, ...)
    text:      system card     PAD ... PAD EOP        live text stream
    model:     -               reference latents      model audio
    user:      -               -                      user audio

The card is a ChatML system turn and carries no audio. The reference is audio
only, on the model channel; its text is PAD on every frame and EOP on the last.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from importlib import resources
from typing import TYPE_CHECKING, Any

import numpy as np

from .config import HaruConfig

if TYPE_CHECKING:
    import mlx.core as mx

    from .models.vibevoice_codec import VibeVoiceCodec

CARD_FIELDS = ("persona", "name", "gender", "backchannel", "other_name", "relationship", "situation")


def card_templates() -> dict[str, Any]:
    """Per-language card wording (lead sentence, field headers, option labels)."""
    path = resources.files(__package__) / "assets" / "card_templates.json"
    return json.loads(path.read_text(encoding="utf-8"))


def render_card(card: dict[str, Any], template: dict[str, Any]) -> str:
    """Character card text from its fields, in one language's ``template``."""
    lines = [template["lead"]]
    for key in CARD_FIELDS:
        value = str(card.get(key) or "").strip()
        if key in ("gender", "backchannel"):
            value = template[key].get(value, "")
        if value:
            lines += [template["headers"][key], value]
    return "\n".join(lines)


def system_prompt_ids(tokenizer, system_prompt: str) -> list[int]:
    if not system_prompt:
        return []
    text = f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
    return tokenizer.encode(text, add_special_tokens=False).ids


def reference_ids(frames: int, pad_id: int, eop_id: int) -> list[int]:
    return [pad_id] * (frames - 1) + [eop_id] if frames > 0 else []


def reference_frames(num_samples: int, frame_samples: int) -> int:
    return math.ceil(num_samples / frame_samples)


@dataclass
class Prompt:
    """Inputs of the prompt positions: text tokens and both audio streams."""

    tokens: "mx.array"  # [n]
    model_latents: "mx.array"  # [n, D]
    user_latents: "mx.array"  # [n, D]
    model_mask: "mx.array"  # [n] positions that carry model audio
    user_mask: "mx.array"  # [n] positions that carry user audio

    @property
    def length(self) -> int:
        return self.tokens.shape[0]


def prompt_length(tokenizer, system_prompt: str, reference_samples: int, speak_first: bool, frame_samples: int) -> int:
    """Number of positions :func:`build_prompt` produces."""
    n = len(system_prompt_ids(tokenizer, system_prompt)) + reference_frames(reference_samples, frame_samples)
    return n + 2 if speak_first else max(n, 1)


def build_prompt(
    config: HaruConfig,
    codec: "VibeVoiceCodec",
    tokenizer,
    system_prompt: str = "",
    reference: "np.ndarray | None" = None,
    speak_first: bool = False,
    key: "mx.array | None" = None,
) -> Prompt:
    """System prompt, then the voice reference, then (``speak_first``) an opening turn."""
    import mlx.core as mx

    pad, eop = config.pad_token_id, config.eop_token_id
    card = system_prompt_ids(tokenizer, system_prompt)
    ref_latents = None
    if reference is not None and len(reference):
        ref_latents = codec.sample(codec.encode(mx.array(reference)), key)[0]
    n_ref = 0 if ref_latents is None else ref_latents.shape[0]
    # A reference already ends in EOP, so an opening turn starts with PAD, EOP.
    grid = [pad, eop] if speak_first else []
    if not card and not n_ref and not grid:
        grid = [pad]
    tokens = card + reference_ids(n_ref, pad, eop) + grid
    n, n_card, n_grid = len(tokens), len(card), len(grid)

    # Audio streams per position: none on the card, the model's only on the
    # reference. Positions before any generated audio carry the speaker's
    # room tone, and encoded silence on the user side.
    dim = config.latent_dim
    model_parts = [mx.zeros((n_card, dim))]
    user_parts = [mx.zeros((n - n_grid, dim))]
    if n_ref:
        model_parts.append(ref_latents)
    if n_grid:
        model_parts.append(mx.broadcast_to(_room_tone(codec, reference, ref_latents), (n_grid, dim)))
        user_parts.append(mx.broadcast_to(silence_latent(codec), (n_grid, dim)))
    positions = mx.arange(n)
    return Prompt(
        tokens=mx.array(tokens, dtype=mx.int32),
        model_latents=mx.concatenate(model_parts),
        user_latents=mx.concatenate(user_parts),
        model_mask=positions >= n_card,
        user_mask=positions >= n - n_grid,
    )


def silence_latent(codec: "VibeVoiceCodec") -> "mx.array":
    """Latent of digital silence: the input of an audio stream with no sound yet."""
    import mlx.core as mx

    cached = getattr(codec, "_silence_latent", None)
    if cached is None:
        cached = codec.encode(mx.zeros((16 * codec.config.frame_samples,)))[0, -1]
        mx.eval(cached)
        codec._silence_latent = cached
    return cached


def _room_tone(codec: "VibeVoiceCodec", reference: "np.ndarray | None", ref_latents: "mx.array | None") -> "mx.array":
    """The reference's quietest frame (the speaker's noise floor), else silence."""
    frame = codec.config.frame_samples
    whole = 0 if reference is None else len(reference) // frame
    if ref_latents is None or whole == 0:
        return silence_latent(codec)
    energy = np.square(reference[: whole * frame].reshape(whole, -1)).mean(axis=1)
    return ref_latents[int(energy.argmin())]
