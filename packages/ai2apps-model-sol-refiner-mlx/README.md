# SoL-Refiner Image & Video Upscaler MLX

2x video upscaling on Apple Silicon. Select **Standard Upscaling** for normal use: approximately 28.71 GB, with a fixed default prompt and no prompt entry required.

For custom prompts, install **Custom Prompts** from this same Package in Discover. Its complete data is approximately 57.04 GB. With Standard already installed and its shared cache retained, approximately 28.33 GB of text components are added; video weights are reused by checksum. Select the Custom Prompts model when sending a custom prompt. Standard rejects unsupported custom prompts with a clear installation instruction.

- Standard model: `ai2apps.model.sol-refiner-mlx/ltx23-one-step` (recommended).
- Custom model: `ai2apps.model.sol-refiner-mlx/ltx23-custom-prompt` (optional).
- Operation: `video_upscaling`, multipart `POST /v1/videos/upscalings`.
- Input: `video`, `model`, optional `parameters` JSON with `scale=2`, `seed`, `prompt`. Missing/blank prompt uses the default.
- CFR 1-60 fps, at least 32 pixels per side, with no fixed input edge limit; up to 1500 frames / 60 seconds per request.
- Output: 2x dimensions, same frame count, MP4/H.264. AAC, MP3, ALAC, AC3, EAC3 compressed audio passthrough. Unsupported audio and VFR are rejected explicitly.
- Whole-clip VAE encoding, latent upsampling and one DiT refinement preserve temporal context. Only VAE decoding uses adaptive 9/17/25/33/41-frame windows with overlapping transitions. No independent refinement fallback is allowed. Memory still grows with clip length; Worker admission checks real frame count, geometry and available memory before loading weights. Insufficient memory returns `resource_exhausted` (503).
- Updated Hosts must honor `segmented: false` / `temporal_policy: whole_clip`, reserve memory for the whole clip, and reject inputs beyond the model duration/frame contract. Apps must submit the complete clip in one request.
- Requires Runtime >=1.8.8 and Host support for the video_upscaling model type.

Weights remain BF16: unused tensors were removed, without quantizing retained values. Fixed default context reproduces the original default-prompt computation in the tested cases. Source, modifications and applicable LTX/Gemma terms are included in META. ACPF/Discover must collect the installing user's consent before checkpoint acquisition.

Package version 0.1.3. Requires Runtime >=1.8.8 and a Host with image_upscaling and the resource_limited resolution contract. No checkpoint weights or native dependencies are embedded in this Package.

Historical 0.1.2 4K execution probe (independent refinement windows; not a 0.1.3 benchmark): 17 frames at 1920×1080 produced 17 frames at 3840×2160 in 103.53 seconds, MLX peak 14.07 GiB on the development machine. This verifies execution and dimensions, not universal temporal/image quality. The source was resized for the geometry probe; timings are not a stable performance promise. Existing BF16 Distributions and shared weight cache remain unchanged.

## Direct image upscaling

The same two model IDs also advertise the distinct `image_upscaling` operation.
Send multipart `POST /v1/images/upscalings` through the Host invocation service,
with `image`, `model`, and optional `parameters` JSON (`scale=2`, `seed`, `prompt`).
The response is binary `image/png`, not a JSON image-generation response.

Single-frame 8-bit PNG, JPEG and WebP are supported. EXIF orientation is applied,
embedded supported color profiles are converted to sRGB, and output is encoded
as PNG without video compression. Alpha is resized with Lanczos and retained;
the model refines RGB, not alpha. Animated and HDR/16-bit inputs are explicitly
rejected. Output strips input EXIF metadata. There is no fixed edge/pixel limit;
Host resource admission and decoder safety limits still apply.

The standard model needs no prompt; select the custom model for custom prompts.
No extra checkpoint is required for images. ACPF capability `image.upscaling`
selects these same existing model IDs. Apps must discover support by the
`image_upscaling` capability, not require the provider's primary model_type to
be `image_upscaling`: SoL also remains a video_upscaling provider.

## 0.1.3 arithmetic corrections

Weighted RMSNorm keeps normalization and affine multiplication in FP32 before
rounding once. DiT GELU/SiLU and latent upsampler SiLU also use FP32 intermediate
arithmetic, then restore the BF16 input dtype. Weights, RoPE and linear kernels
are unchanged. CPU reference experiments reduce the measured DiT discrepancy;
they do not establish full CUDA pipeline parity or eliminate invented texture.
