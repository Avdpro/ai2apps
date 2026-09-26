from __future__ import annotations

import json


class BigVGANConfig(dict):
    """Torch-free subset of WIndexTTS's BigVGAN configuration."""

    def __init__(self, **kwargs):
        defaults = {
            "resblock": "1",
            "upsample_rates": [4, 4, 2, 2, 2, 2],
            "upsample_kernel_sizes": [8, 8, 4, 4, 4, 4],
            "upsample_initial_channel": 1536,
            "resblock_kernel_sizes": [3, 7, 11],
            "resblock_dilation_sizes": [[1, 3, 5] for _ in range(3)],
            "use_tanh_at_final": False,
            "use_bias_at_final": False,
            "activation": "snakebeta",
            "snake_logscale": True,
            "num_mels": 80,
            "sampling_rate": 22050,
        }
        super().__init__(defaults | kwargs)

    @classmethod
    def from_json(cls, path):
        with open(path, encoding="utf-8") as stream:
            return cls(**json.load(stream))
