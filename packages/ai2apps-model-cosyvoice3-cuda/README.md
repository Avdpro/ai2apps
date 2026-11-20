# CosyVoice 3 CUDA development Package

Uses the existing pinned official FP32 CUDA adapter and original FunAudioLLM checkpoint. Product speech, cloning, emotion and instruction contracts are retained. Speed uses official numerical mel interpolation rather than a qualitative style instruction. Quantized CUDA implementations and evidence remain separate; this does not retire those paths.

This adapter inherits transport and cancellation from the bundled cuda_cosyvoice_adapter and Runtime-provided cuda_audio. Engines, dependencies and upstream source are supplied by the separately validated Runtime. Retained META notices and SPDX components include conversion provenance; they are not a declaration that MLX dependencies are shipped by this adapter Package.

The original checkpoint distribution dist_ai2apps_cosyvoice3_original_29e01c4e_v1 is published and anonymously verified in signed Index134. Service weights bind this exact distribution. Existing model evidence does not prove this new Package installation; known content-quality failures remain release gates.
