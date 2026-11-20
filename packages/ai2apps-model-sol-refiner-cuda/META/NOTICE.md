# Sources and attribution

This implementation follows the inference equations and checkpoint layout of:

- NVIDIA Research, SoL-Refiner, NVlabs/Sana `sol-engine` branch.
  https://github.com/NVlabs/Sana/tree/sol-engine/models/sol-refiner
- Hugging Face Diffusers / Lightricks LTX-2.3: video transformer, video VAE,
  text connectors, and latent upsampler. Reference files carry the Apache-2.0
  license and copyright notices of Lightricks and the HuggingFace Team.
  https://github.com/huggingface/diffusers
- Apple's `mlx-lm` Gemma 3 module is used as a dependency (MIT license).
  https://github.com/ml-explore/mlx-lm

The MIT-licensed dgrauet/ltx-2-mlx repository was inspected during the initial
feasibility assessment; this implementation has no runtime dependency on it.

No model weights are included in this source directory. Downloaded SoL, LTX,
and Gemma weights retain their upstream terms. This experiment does not grant
additional rights to redistribute them.

## Checkpoint terms

Gemma is provided under and subject to the Gemma Terms of Use found at ai.google.dev/gemma/terms

Complete LTX-2 Community and Gemma terms are included in META/CHECKPOINT-TERMS.txt. These terms govern checkpoint use and downstream distribution, including their use restrictions. LTX-2 entities with annual revenues of at least US$10 million require a separate commercial license. The Package does not relicense these weights under Apache-2.0.

The Python implementation adapts the upstream inference equations and layouts to MLX and adds bounded overlapping video windows. Checkpoint files remain byte-identical to the fixed upstream repositories.

Modified by AI2Apps on 2026-10-01: unused audio/vision tensors removed; safetensors repacked without changing retained tensor values; default-prompt context precomputed. No quantization. Original source revision c69c2a543997fe12c1ae24c776df6188e5d2248a.
