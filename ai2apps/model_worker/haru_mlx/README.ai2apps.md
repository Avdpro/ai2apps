# Haru MLX source integration

This directory contains the official Haru MLX inference core from
https://github.com/higurashi-ai/Haru at
`7fe6b7665f8bf035998f401f8cb779fbe53f2751` (Apache-2.0).
It is an integration of that implementation, not a newly authored model port.
See `LICENSE`, `THIRD_PARTY_NOTICES.md` and `UPSTREAM.json`.

Included: Qwen3.5 backbone and gated-delta kernel, MeanFlow head, streaming
VibeVoice codec and depthwise kernel, prompt, tokenizer/weight conversion,
sampling, audio helpers, session and character templates. Upstream native App,
socket server, web client and automatic microphone access are not included.

The package was relocated to `ai2apps.model_worker.haru_mlx`; `prompt.py` resolves
resources relative to `__package__`. Model computation and weight layouts are
unchanged. The AI2Apps lifecycle/control adapter lives in `../haru_duplex.py`.
It loads only an installed local checkpoint and keeps all MLX work on one
dedicated thread. Its playback fence does not cancel model listening or tasks.

The upstream tests in `ai2apps/tests/haru_mlx` retain their numerical thresholds.
Imports and resource paths use the relocated package. `MLX_ENABLE_TF32=0` is
required for strict float32 comparisons on newer Apple GPUs; launch pytest with
that environment setting when mixing with other MLX tests. PyTorch-reference
tests are skipped unless a separately generated reference dump is supplied.

Haru is a pretrained speech base model. It does not supply reliable Tool
instructions, live text/result injection, an ASR user transcript, image input,
or discrete response cancellation. These capabilities remain disabled in the
adapter. Task execution and approval stay with the existing Bot owners.
