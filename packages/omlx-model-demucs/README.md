# MLX Demucs

Native Apple-Silicon HTDemucs source separation for AI2Apps. The Package
supports three stable profiles through `audio_process` with
`task=source_separation`:

- `music_4stem`: native drums, bass, other and vocals stems;
- `vocals_instrumental`: vocals plus an exact residual instrumental stem;
- `dialogue_background`: dialogue approximated by the vocals stem plus an
  exact residual background stem.

The response is `demucs-stems.zip`, containing PCM16 WAV files and
`separation.json` (`ai2apps.audio-separation-result/v1`). Input timing is
preserved after resampling to the native 44.1 kHz stereo model boundary.
Unknown profiles and inputs with more than two channels are rejected.

This source tree contains no pretrained weights. The release binds a separate
signed dual-source distribution containing only the pinned public HTDemucs
safetensors and config. Runtime dependency: `ai2apps/runtime-omlx >=1.6.2`.
