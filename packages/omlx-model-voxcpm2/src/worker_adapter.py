from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ai2apps.model_worker import OmlxTTSAdapter


_EMOTION_INSTRUCTIONS = {
    "happy": "sound genuinely happy and warm",
    "sad": "sound subdued and sad",
    "angry": "sound controlled but clearly angry",
    "calm": "sound calm and composed",
    "excited": "sound energetic and excited",
    "surprised": "sound naturally surprised",
}


def _speed_instruction(speed: float) -> str | None:
    if speed < 0.75:
        return "speak much more slowly than normal"
    if speed < 0.95:
        return "speak more slowly than normal"
    if speed > 1.5:
        return "speak much faster than normal"
    if speed > 1.05:
        return "speak faster than normal"
    return None


class VoxCPM2Adapter(OmlxTTSAdapter):
    def synthesis_options(
        self,
        model_id: str,
        body: Mapping[str, Any],
        *,
        speed: float,
        emotion: str | None,
        emotion_strength: float,
        instructions: str | None,
    ) -> dict[str, Any]:
        mandatory = []
        if emotion and emotion.lower() != "neutral":
            mandatory.append(_EMOTION_INSTRUCTIONS[emotion.lower()])
        rate = _speed_instruction(speed)
        if rate:
            mandatory.append(rate)

        parts = []
        if instructions and instructions.strip():
            parts.append(instructions.strip())
        if mandatory:
            parts.append(
                "Mandatory delivery controls override conflicting earlier style: "
                + "; ".join(mandatory)
                + "."
            )
        return {
            # VoxCPM2 has instruction-based rate control, not an exact numeric
            # speed parameter.  Keep the backend multiplier neutral.
            "speed": 1.0,
            "instructions": " ".join(parts) or None,
            "language": body.get("language") or None,
        }


def create_adapter(context):
    return VoxCPM2Adapter(context)
