"""Model configs and builder for SAM2.1 variants."""

from .hiera import Hiera
from .image_encoder import FpnNeck, ImageEncoder
from .mask_decoder import MaskDecoder, PromptEncoder
from .memory import MemoryAttention, MemoryEncoder
from .position_encoding import PositionEmbeddingSine
from .sam2_base import SAM2Base


MODEL_CONFIGS = {
    "small": dict(
        embed_dim=96, num_heads=1,
        stages=(1, 2, 11, 2), window_spec=(8, 4, 14, 7),
        global_att_blocks=(7, 10, 13),
        window_pos_embed_bkg_spatial_size=(7, 7),
        backbone_channel_list=[768, 384, 192, 96],
    ),
    "base_plus": dict(
        embed_dim=112, num_heads=2,
        stages=(2, 3, 16, 3), window_spec=(8, 4, 14, 7),
        global_att_blocks=(12, 16, 20),
        window_pos_embed_bkg_spatial_size=(14, 14),
        backbone_channel_list=[896, 448, 224, 112],
    ),
    "large": dict(
        embed_dim=144, num_heads=2,
        stages=(2, 6, 36, 4), window_spec=(8, 4, 14, 7),
        global_att_blocks=(23, 33, 43),
        window_pos_embed_bkg_spatial_size=(14, 14),
        backbone_channel_list=[1152, 576, 288, 144],
    ),
}

DEFAULT_WEIGHTS = {
    "small": "weights/sam2.1_hiera_small.safetensors",
    "base_plus": "weights/sam2.1_hiera_base_plus.safetensors",
    "large": "weights/sam2.1_hiera_large.safetensors",
}


def build_model(model_size: str = "base_plus", weights_path: str = None) -> SAM2Base:
    """Build a SAM2.1 model and load weights.

    Args:
        model_size: "small", "base_plus", or "large"
        weights_path: path to .safetensors file. If None, uses default.
    """
    cfg = MODEL_CONFIGS[model_size]
    if weights_path is None:
        weights_path = DEFAULT_WEIGHTS[model_size]

    hiera = Hiera(
        embed_dim=cfg["embed_dim"],
        num_heads=cfg["num_heads"],
        stages=cfg["stages"],
        window_spec=cfg["window_spec"],
        global_att_blocks=cfg["global_att_blocks"],
        window_pos_embed_bkg_spatial_size=cfg["window_pos_embed_bkg_spatial_size"],
    )
    pe = PositionEmbeddingSine(256, normalize=True)
    sam = SAM2Base(
        ImageEncoder(
            hiera,
            FpnNeck(pe, 256, cfg["backbone_channel_list"],
                    fpn_top_down_levels=[2, 3], fpn_interp_model="nearest"),
            scalp=1,
        ),
        MaskDecoder(), PromptEncoder(),
        MemoryAttention(d_model=256, num_layers=4, dim_feedforward=2048, mem_dim=64),
        MemoryEncoder(out_dim=64, in_dim=256),
        image_size=1024, num_maskmem=7,
        sigmoid_scale_for_mem_enc=20.0, sigmoid_bias_for_mem_enc=-10.0,
        directly_add_no_mem_embed=True, no_obj_embed_spatial=True,
        use_high_res_features_in_sam=True, multimask_output_in_sam=True,
        add_tpos_enc_to_obj_ptrs=True, proj_tpos_enc_in_obj_ptrs=True,
        use_signed_tpos_enc_to_obj_ptrs=True, max_obj_ptrs_in_encoder=16,
        multimask_min_pt_num=0, multimask_max_pt_num=1,
        use_mlp_for_obj_ptr_proj=True,
    )
    sam.load_weights(weights_path, strict=False)
    sam.eval()
    return sam
