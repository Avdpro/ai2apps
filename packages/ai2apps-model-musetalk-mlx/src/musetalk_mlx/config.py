"""Frozen upstream configs — the oracle. Do NOT "improve" these values.

Captured 2026-06-04 from pinned upstream commit
0a89dec45a0192b824e3cf4daf96c239440c5ed8 and the component HF repos.
"""

# musetalkV15/musetalk.json  (TMElyralab/MuseTalk) — UNet2DConditionModel, diffusers 0.6.0.dev0
UNET_CONFIG = {
    "_class_name": "UNet2DConditionModel",
    "_diffusers_version": "0.6.0.dev0",
    "act_fn": "silu",
    "attention_head_dim": 8,  # MISNOMER: num-heads-style -> real head_dim = block_ch // 8
    "block_out_channels": [320, 640, 1280, 1280],
    "center_input_sample": False,
    "cross_attention_dim": 384,  # whisper-tiny encoder feature dim (NOT 768 text)
    "down_block_types": [
        "CrossAttnDownBlock2D",
        "CrossAttnDownBlock2D",
        "CrossAttnDownBlock2D",
        "DownBlock2D",
    ],
    "downsample_padding": 1,
    "flip_sin_to_cos": True,
    "freq_shift": 0,
    "in_channels": 8,  # 4 masked-target latent (+) 4 reference latent
    "layers_per_block": 2,
    "mid_block_scale_factor": 1,
    "norm_eps": 1e-05,
    "norm_num_groups": 32,
    "out_channels": 4,
    "sample_size": 64,  # nominal; real latent is 256/8 = 32x32
    "up_block_types": [
        "UpBlock2D",
        "CrossAttnUpBlock2D",
        "CrossAttnUpBlock2D",
        "CrossAttnUpBlock2D",
    ],
}

# stabilityai/sd-vae-ft-mse — AutoencoderKL, diffusers 0.4.2
# (scaling_factor not in json -> diffusers default 0.18215, which MuseTalk reads at runtime)
VAE_CONFIG = {
    "_class_name": "AutoencoderKL",
    "_diffusers_version": "0.4.2",
    "act_fn": "silu",
    "block_out_channels": [128, 256, 512, 512],
    "down_block_types": ["DownEncoderBlock2D"] * 4,
    "up_block_types": ["UpDecoderBlock2D"] * 4,
    "in_channels": 3,
    "out_channels": 3,
    "latent_channels": 4,
    "layers_per_block": 2,
    "norm_num_groups": 32,
    "sample_size": 256,
}
VAE_SCALING_FACTOR = 0.18215

# Pipeline constants (from musetalk/models/vae.py + scripts/inference.py)
RESIZED_IMG = 256  # face crop size
LATENT_SIZE = 32  # 256 // 8
UNET_TIMESTEP = 0  # single-step inpainting: fixed t=0
AUDIO_FEATURE_DIM = 384  # whisper-tiny encoder hidden
AUDIO_FEAT_WINDOW = [2, 2]  # get_whisper_chunk window (2 left + center + 2 right)
WHISPER_FPS_MULTIPLIER = 50.0  # whisper_idx_multiplier = 50 / fps

# Pinned sources
UPSTREAM_COMMIT = "0a89dec45a0192b824e3cf4daf96c239440c5ed8"
HF_MAIN = "TMElyralab/MuseTalk"  # musetalkV15/{unet.pth, musetalk.json}
HF_VAE = "stabilityai/sd-vae-ft-mse"
HF_WHISPER = "openai/whisper-tiny"
