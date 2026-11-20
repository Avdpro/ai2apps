# SenseVoice Small CUDA — development source

Official FunASR CUDA transcription, with word/segment timestamps and a pinned
CPU FSMN VAD helper for audio longer than 30 seconds (one-hour input limit).
The Host decodes the supported input formats. Streaming, diarization, emotion
and speaker recognition are not supported. The official ITN path is retained;
this Package does not claim the separate Mac punctuation pipeline is identical.

The ASR model declares its internal VAD as a required model in the same Service.
The adapter selects the helper by its exact upstream ID; the Host supplies both
read-only checkpoints. Installing ASR must acquire the helper dependency too.

Both checkpoint distributions are published and anonymously verified in Registry
Index 126. The Service binds the new same-Service VAD identity. The old
cross-Service signed VAD candidate remains preserved and unused. This does
not establish signed Service installation or new long-audio GPU acceptance.

Requires a released CUDA Runtime >=0.6.0 with the SenseVoice profile. Preserve
all model license terms and require each installing user's explicit declaration.
See spark/SENSEVOICE-RELEASE-PREPARATION.md for evidence and remaining gates.
