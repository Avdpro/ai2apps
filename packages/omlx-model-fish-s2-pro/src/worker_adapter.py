from ai2apps.model_worker import OmlxTTSAdapter

class DramaAdapter(OmlxTTSAdapter):
    def synthesis_options(self, model_id, body, *, speed, emotion, emotion_strength, instructions):
        cues = []
        if emotion and emotion != "neutral" and emotion_strength > 0:
            cues.append(emotion)
        if instructions:
            cues.append(instructions.strip().strip("[]"))
        return {"speed": speed, "language": body.get("language") or None,
                "instructions": "] [".join(cues) or None}

def create_adapter(context):
    return DramaAdapter(context)
