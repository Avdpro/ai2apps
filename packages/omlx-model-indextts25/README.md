# IndexTTS 2.5 MLX

AI2Apps Model Worker Package for Torch-free, native MLX IndexTTS 2.5
synthesis on Apple Silicon. P0 supports single-reference voice cloning,
Chinese and English text, the official eight-axis numeric emotion control,
and native `duration_factor` speaking-rate control.

The unified `speed` multiplier is mapped to `duration_factor = 1 / speed`.
Neutral keeps the reference-derived expression path; it is not rewritten as
the `calm` emotion axis. Reference transcripts are accepted by the common API
for role compatibility but are not consumed by this synthesis path.

The optional Qwen text-to-emotion model and independent emotion-reference
audio are intentionally not included in 0.1.0. They require separate P1/P2
capability declarations and must not download silently at inference time.

IndexTTS model weights are governed by the Bilibili Model Use License
Agreement included under `META/licenses/`; the WIndexTTS MLX implementation is
Apache-2.0.
