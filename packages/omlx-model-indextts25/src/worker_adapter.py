from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from ai2apps.model_worker import ModelWorkerError, OmlxTTSAdapter


_EMOTIONS = (
    "happy",
    "angry",
    "sad",
    "afraid",
    "disgusted",
    "melancholic",
    "surprised",
    "calm",
)
_BIASES = (0.9375, 0.875, 1.0, 1.0, 0.9375, 0.9375, 0.6875, 0.5625)
_ALIASES = {
    "happy": {"happy": 0.8},
    "angry": {"angry": 0.8},
    "sad": {"sad": 0.8},
    "calm": {"calm": 0.8},
    "surprised": {"surprised": 0.8},
}


def _emotion_vector(emotion: str | None) -> list[float] | None:
    if not emotion or emotion.lower() == "neutral":
        return None
    raw = _ALIASES[emotion.lower()]
    values = [raw.get(name, 0.0) * bias for name, bias in zip(_EMOTIONS, _BIASES)]
    total = sum(values)
    if total > 0.8:
        values = [value * 0.8 / total for value in values]
    return values


def _language(value: Any, text: Any) -> str:
    requested = str(value or "auto").lower().replace("_", "-")
    if requested in {"zh", "zh-cn", "zh-hans", "chinese"}:
        return "ZH"
    if requested in {"en", "en-us", "en-gb", "english"}:
        return "EN"
    if requested != "auto":
        raise ModelWorkerError(
            f"IndexTTS 2.5 P0 does not support language: {value}",
            code="unsupported_feature",
            status_code=400,
        )
    return "ZH" if re.search(r"[\u3400-\u9fff]", str(text or "")) else "EN"


class IndexTTS25Adapter(OmlxTTSAdapter):
    async def create_engine(self, checkpoint, runtime_options=None):
        from omlx.engine.indextts25 import IndexTTS25Engine

        return IndexTTS25Engine(
            str(checkpoint.path),
            **dict(runtime_options or {}),
        )

    async def invoke(self, request):
        if (request.parts or {}).get("reference_audio") is None:
            raise ModelWorkerError(
                "IndexTTS 2.5 requires an authorized reference_audio part",
                code="invalid_reference_audio",
                status_code=400,
            )
        return await super().invoke(request)

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
        return {
            "speed": 1.0,
            "duration_factor": 1.0 / speed,
            "emotion_vector": _emotion_vector(emotion),
            "emotion_strength": emotion_strength,
            "language": _language(body.get("language"), body.get("input")),
            "instructions": None,
        }


def create_adapter(context):
    return IndexTTS25Adapter(context)
