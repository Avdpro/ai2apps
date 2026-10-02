"""SAM2 module: Segment Anything 2 for video object tracking, ported to MLX."""

from .build import build_model, MODEL_CONFIGS
from .predictor import SAM2ImagePredictor, SAM2VideoPredictor
