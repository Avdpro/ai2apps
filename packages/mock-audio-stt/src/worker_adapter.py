from ai2apps.model_worker import ModelWorkerError


class MockSTTAdapter:
    def __init__(self, context):
        self.context = context

    async def start(self):
        return None

    async def stop(self):
        return None

    async def invoke(self, request):
        if request.operation != "audio_transcription":
            raise ModelWorkerError(
                "Unsupported operation", code="unsupported_operation", status_code=400
            )
        audio = request.part("file")
        return {
            "text": "AI2Apps mock transcription",
            "language": request.payload.get("language") or "und",
            "duration": None,
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 0.0,
                    "text": "AI2Apps mock transcription",
                    "speaker": "speaker_0",
                }
            ],
            "features": {
                "timestamps": {
                    "status": "native",
                    "requested": "segment",
                    "effective": "segment",
                    "provider": self.context.service_id,
                }
            },
            "input": {
                "media_type": audio.media_type,
                "size": audio.size,
                "sha256": audio.sha256,
            },
        }


def create_adapter(context):
    return MockSTTAdapter(context)
