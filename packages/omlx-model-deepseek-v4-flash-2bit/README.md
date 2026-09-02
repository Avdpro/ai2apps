# DeepSeek V4 Flash 2-bit model package

Adds the pinned MLX 2-bit checkpoint recipe and Scope Pack needed by
AI2Apps/oMLX.

Version 0.3.3 requires Runtime 1.5.4 and enables its validated native
Direct-L1 Decode and Direct Prefill paths by default. Host environment values
remain authoritative, so `OMLX_MOE_DIRECT_L1=0` and
`OMLX_DEEPSEEK_V4_DIRECT_PREFILL=0` retain the legacy A/B and rollback path.
