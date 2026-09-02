# AI2Apps Spark model parity

Spark parity is defined by user-facing model capability, not by using the same
checkpoint or framework as MLX. Every Model Package keeps its adapter and
immutable checkpoint declaration separate from its inference Runtime Package.

| Capability | MLX baseline | Spark/CUDA baseline | Runtime layer | Status |
| --- | --- | --- | --- | --- |
| Text chat | Qwen/DeepSeek model workers | Qwen2.5 Instruct | `cuda-torch` | GPU verified |
| Vision chat | Qwen VLM workers | Qwen3-VL 2B Instruct | `cuda-torch` 0.2 | Package built |
| Speech recognition | Qwen3-ASR/SenseVoice | Qwen3-ASR 0.6B HF | `cuda-torch` 0.2 | GPU verified |
| Speech synthesis | Qwen3-TTS/CosyVoice/Fish/VibeVoice | Qwen3-TTS 0.6B CustomVoice | `cuda-audio` | Next |
| Image generation/editing | Worker protocol only | Qwen-Image | `cuda-diffusers` | Next |
| Video generation | EchoMimic V3 MLX | Wan TI2V, then EchoMimic avatar | `cuda-video` | Next |

Runtime policy:

- `cuda-torch` contains only the common CPython, PyTorch, Transformers and
  media-decoding base used by LLM, VLM and native Transformers ASR Workers.
- `cuda-audio` adds Qwen-TTS and audio codec dependencies. It is a separate
  complete Runtime because Runtime layers are immutable and a Worker selects
  exactly one provider.
- `cuda-diffusers` adds Diffusers/Accelerate and image codecs.
- `cuda-video` adds video diffusion and FFmpeg bindings. Avatar-specific code
  stays in its Model Package unless it introduces binary dependencies.

All production model declarations pin a full upstream revision, execute with
outbound network disabled, and consume only Host-resolved checkpoints from the
shared Hugging Face cache. Large model weights are never embedded in the pip
wheel or duplicated in the signed adapter Package.
