import io
import math
import struct
import wave

from ai2apps.model_worker import ModelWorkerError, ModelWorkerResponse


class MockTTSAdapter:
    def __init__(self, context):
        self.context = context

    async def start(self):
        return None

    async def stop(self):
        return None

    async def invoke(self, request):
        if request.operation != "audio_speech":
            raise ModelWorkerError(
                "Unsupported operation", code="unsupported_operation", status_code=400
            )
        text = str(request.payload.get("input") or "").strip()
        if not text:
            raise ModelWorkerError(
                "input must not be empty", code="invalid_request", status_code=400
            )
        response_format = str(request.payload.get("response_format") or "wav")
        if response_format not in {"wav", "pcm"}:
            raise ModelWorkerError(
                "Mock TTS supports WAV/PCM only",
                code="unsupported_audio_format",
                status_code=415,
            )
        sample_rate = 16_000
        duration = min(1.0, max(0.12, len(text) * 0.025))
        frames = bytearray()
        for index in range(int(sample_rate * duration)):
            envelope = min(1.0, index / 320, (sample_rate * duration - index) / 320)
            sample = int(1400 * envelope * math.sin(2 * math.pi * 440 * index / sample_rate))
            frames.extend(struct.pack("<h", sample))
        content = bytes(frames)
        media_type = "audio/pcm"
        if response_format == "wav":
            output = io.BytesIO()
            with wave.open(output, "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(sample_rate)
                target.writeframes(content)
            content = output.getvalue()
            media_type = "audio/wav"
        return ModelWorkerResponse(
            content,
            media_type=media_type,
            headers={
                "X-AI2Apps-Audio-Sample-Rate": str(sample_rate),
                "X-AI2Apps-Audio-Channels": "1",
                "X-AI2Apps-Audio-Sample-Width": "2",
                "X-AI2Apps-Feature-Speed": "native",
                "X-AI2Apps-Feature-Emotion": "fallback:neutral",
            },
        )


def create_adapter(context):
    return MockTTSAdapter(context)
