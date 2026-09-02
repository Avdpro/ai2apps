# CosyVoice 3 0.5B

AI2Apps Model Worker Package for the native MLX CosyVoice 3 backend. It offers
4-bit and 8-bit pinned checkpoints with reference voice cloning, multilingual
synthesis, and natural-language style or emotion instructions.

Reference audio is required by the converted CosyVoice 3 checkpoints. Providing
an accurate transcript improves zero-shot fidelity; omitting it selects the
cross-lingual path without downloading a hidden ASR model.

Both public variants declare the pinned `mlx-community/S3TokenizerV3`
checkpoint as an internal dependency. AI2Apps downloads it during model
installation (about 0.97 GB upstream storage) and hides it from the model picker,
so synthesis never needs an undeclared runtime download.
