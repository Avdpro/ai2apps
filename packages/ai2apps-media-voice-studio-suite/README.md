# Media Voice Studio Suite

This is the first installable MVP of the AI2Apps audio/video localization suite. It is one ordinary
App Package containing six Studio Mini-Apps:

1. detailed recording transcription with speaker naming;
2. voice/background source separation;
3. one-speaker voice replacement in audio;
4. video subtitle generation, translation, file export, and burn-in configuration;
5. single-narrator video audio translation with a Voice Studio Character or request-scoped original-voice clone;
6. one-speaker voice replacement in video.

The Package is a Mini-App provider rather than an independently usable App. Its `app.yaml` therefore
declares `navigation.launcher: false`: the Package itself is not shown in App Launcher or Dock, while its
six Mini-Apps continue to appear in their declared Voice Studio and Video Studio placements.

## MVP boundary

Version `0.2.0` targets the complete Package → install → Studio discovery → trusted mount path. Each
Mini-App provides its own responsive UI, media selection, workflow options, speaker naming, local draft
persistence, and JSON draft export. All six workflows execute through the same mount-bound Host Capability
Broker. Detailed Transcription uses MLX WhisperX; separation uses MLX Demucs; speaker replacement combines
speaker diarization, dialogue/background separation, reference-based MLX Seed-VC conversion, timeline-aware
mixing, and optional video remux; video subtitles combine transcription, optional Standard-model translation,
SRT/WebVTT/ASS export, and optional local burn-in. Video audio translation is intentionally single-narrator in
this phase: it removes source dialogue, translates sentence-sized cues, synthesizes one selected ready Character or a temporary original-voice reference,
mixes the result over the Demucs background stem, and remuxes an MP4.

Video subtitle burn-in offers four responsive font-size presets and a choice between white
text with a thick black outline or white text on a translucent black box. The Host measures wrapping,
outline width, box padding, and safe-area placement together, shrinking only when needed to keep the
complete caption within two lines and inside the video frame.

The MVP Broker operations are intentionally bounded and synchronous. Binary results remain in the page until
the user downloads them; browser storage keeps metadata and drafts only. Durable Resource Handle, Run, and
Artifact persistence, automatic ACPF setup, cancellation, and progress streaming remain follow-up contracts.
Mini-App code must not import another Package, read another Package's installation directory, construct
a private Worker endpoint, or exchange absolute filesystem paths.

## Capability/provider plan

The App Package intentionally has no eager top-level model dependency. Installing this small UI suite
must not automatically download every model. At the moment the intended providers are:

| Capability | Initial provider Package |
| --- | --- |
| `audio.detailed_transcription` | `ai2apps/model-detailed-transcription-mlx >=0.1.2,<1.0.0` |
| `audio.speaker_diarization` | `ai2apps/model-detailed-transcription-mlx >=0.1.2,<1.0.0` |
| `audio.source_separation` | `ai2apps/model-demucs-mlx >=0.1.0,<1.0.0` |
| `audio.voice_conversion` | `ai2apps/model-seed-vc-v2-mlx >=0.1.0,<1.0.0` |
| `audio.speech_generation` | the model bound to the selected ready Voice Studio Character |
| `audio.voice_clone` | optional request-scoped original-voice cloning through a compatible TTS model |
| `text.translation` | the configured Standard model through the existing local/Cloud model route |
| `media.audio.extract` | Host media pipeline |
| `media.subtitle.export` | Package/Host subtitle pipeline |
| `media.video.subtitle_burn_in` | Host media pipeline |
| `media.video.audio_mux` | Host media pipeline |

The Resolver satisfies installed providers at operation time. Provider selection is operation-scoped: the
suite Package never hard-codes model endpoints or checkpoint locations. Model Packages remain lazy rather
than eager dependencies so installing the UI suite does not download every model.

## Source validation

From the repository root, build an unsigned contract artifact for local structural validation:

```bash
./.venv/bin/python -c "from ai2apps.packages.contract_v1 import build_package; build_package('packages/ai2apps-media-voice-studio-suite', '/tmp/ai2apps-media-voice-studio-suite-0.2.0.ai2app')"
```

Production signing and publication must use `scripts/build_signed_registry_release.py` and the standard
Package publication runbook.
