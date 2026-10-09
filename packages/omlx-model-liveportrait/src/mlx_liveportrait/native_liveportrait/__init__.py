"""Specialized native MLX LivePortrait implementation."""

from .pipeline import NativeMLXLivePortrait

__all__ = [
    "MlxAppearanceFeatureExtractorModel",
    "MlxMotionExtractorModel",
    "MlxStitchingModel",
    "MlxWarpingSpadeModel",
    "NativeMLXLivePortrait",
]


def __getattr__(name):
    # Keep shared motion orchestration importable without initializing Metal.
    modules = {
        "MlxAppearanceFeatureExtractorModel": "mlx_appearance_feature_extractor_model",
        "MlxMotionExtractorModel": "mlx_motion_extractor_model",
        "MlxStitchingModel": "mlx_stitching_model",
        "MlxWarpingSpadeModel": "mlx_warping_spade_model",
    }
    if name not in modules:
        raise AttributeError(name)
    from importlib import import_module

    value = getattr(import_module("." + modules[name], __name__), name)
    globals()[name] = value
    return value
