# WIndexTTS-MLX: full-pipeline MLX inference for IndexTTS-2.5 (Apple Silicon).
# Pure MLX runtime (no torch/torch.mps); shares the pure-python frontend
# (tokenizer/segmenter/normalizer) and config with the torch package.
__version__ = "0.3.0-mlx"

from omlx.vendor.indextts25.inference import WIndexTTSMLX  # noqa: F401
