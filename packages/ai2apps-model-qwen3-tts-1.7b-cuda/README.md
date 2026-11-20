# Qwen3 TTS 1.7B CUDA — development source

Uses fixed official BF16 checkpoints through the bundled CUDA audio adapter.
Speed and emotion are not advertised as validated controls. 0.6B does not
support instructions; 1.7B CustomVoice/VoiceDesign do. Base requires reference
audio, with an optional transcript. These limitations remain tracked for parity.

Distribution IDs intentionally remain absent until the signed candidates are
published and publicly verified. No weights are bundled. Requires released
Runtime >=0.6.0 and formal signed Package installation acceptance.
