# Third-party notices

The CosyVoice 3, CAMPlus speaker encoder, S3Gen, and S3Tokenizer MLX backend
modules are derived from DePasqualeOrg/mlx-audio-plus 0.1.8 and are used under
its MIT License. The corresponding license text is included in
`META/licenses/MLX-Audio-Plus-MIT.txt`.

CosyVoice model code and weights originate from FunAudioLLM/CosyVoice and are
distributed under Apache License 2.0. Model Packages carry their own model
license and attribution notices.

mflux 0.19.0 supplies the MLX-native FLUX.2 Klein and Z-Image implementations
and is used under the MIT License. Runtime 1.5.3 installs the digest-pinned
wheel without Torch/OpenCV and makes its conversion, ControlNet, and PiD-only
imports lazy; normal generation, editing, quantization, compiled denoising, and
edit KV caching remain native MLX paths. The license is included in
`META/licenses/mflux-MIT.txt`.
