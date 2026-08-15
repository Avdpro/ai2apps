# AI2Apps default model routing

AI2Apps stores system-wide model choices in
`<base-path>/ai2apps/default-models.json`. The file is written atomically with
owner-only permissions and uses the schema `ai2apps.model-defaults/v1`.

The routing table has nine stable purposes:

| Purpose | Intended use |
| --- | --- |
| `work_simple` | Classification, extraction, short rewrites, and lightweight tool decisions |
| `work_standard` | General conversation, coding, analysis, and ordinary Agent work |
| `work_complex` | Long-horizon reasoning, difficult coding, review, and high-risk planning |
| `speech_recognition` | Speech-to-text and audio transcription |
| `speech_generation` | Text-to-speech, narration, and voices |
| `audio_processing` | Enhancement, separation, and speech-to-speech processing |
| `image_recognition` | Visual understanding, OCR, and visual question answering |
| `image_generation` | Image synthesis and editing |
| `video_generation` | Video synthesis and editing |

An empty value means that no purpose-specific override is assigned. Work
callers should then use the existing API default model. Dedicated media callers
should treat an empty value as unavailable instead of sending the request to a
text model.

Python system components resolve a route through the shared store:

```python
from ai2apps.model_manager import ModelManagerStore

model_id = ModelManagerStore(base_path).resolve_default_model(
    "work_standard",
    fallback=api_default_model,
)
```

The Models App is the authoritative editor. Its Defaults Entry only offers
currently available, non-hidden, non-helper models and filters dedicated slots
by runtime capability. `PUT /admin/api/model-manager/defaults` repeats the same
availability and compatibility validation server-side before committing the
complete table.

This routing layer does not replace the API default model. The API default is
the compatibility fallback for requests that do not declare a purpose; the
purpose table lets Apps, Agents, Services, and system automation make a stable
intent-level request without hard-coding a particular model id.
