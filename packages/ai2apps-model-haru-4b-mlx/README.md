# Haru-4B MLX 0.1.0 — experimental

Apple Silicon / macOS 26.2+, recommended 16GiB or more unified memory.
Requires Host feature model.audio-realtime.v1 (catalog/Worker lifecycle only),
ai2apps/runtime-omlx >=1.8.18 and audio-duplex-v1. The 10.56GB BF16
checkpoint is downloaded separately through a signed HF/ModelScope Distribution;
the backbone is quantized to 8-bit on loading, while the audio codec stays native.

Native 24kHz mono f32le input/output, 3200 samples per frame. A 3–30 second
voice reference and character prompt are required at session start. Session limit
600 seconds. Playback interrupt/resume do not cancel Bot tasks. Worker access is
private and authenticated; Local HTML must use a compatible host-owned Gateway.
No browser-to-Worker access, public Cloud Gateway or Bot voice UI is supplied by
this Package. Old Hosts without audio_realtime support require an upgrade.

Supports concurrent listening/speaking and generated text output. Does not expose
user ASR transcripts, text input, tool calls, async Bot result injection or semantic
response cancellation. Conversational factual/instruction fidelity is experimental;
Bot remains the task and approval authority. No live microphone, AEC, second Mac
or long-session acceptance is claimed. Published benchmark used system TTS input.

Install: ordinary Registry review + Runtime dependency + checkpoint verification.
Start/readiness/health/stop/restart/uninstall follow Managed Model Worker v1;
uninstall removes Package state, retaining checkpoints unless explicitly requested.
