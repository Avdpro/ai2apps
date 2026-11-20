"""Utterance-level hidden steering from the official fixed ZONOS3 bundle.

Directions are mean differences, not unit vectors. Inject only during audio
steps, before the selected attention-residual source enters the bank.
"""
import math
from pathlib import Path
from functools import lru_cache
import numpy as np

ALIASES = {"fearful": "scared", "afraid": "scared", "fear": "scared"}
EMOTIONS = ("happy", "scared", "angry", "sad")

@lru_cache(maxsize=4)
def direction(name):
    vector = np.load(Path(__file__).with_name("steering") / (name + ".npy"), allow_pickle=False)
    if vector.shape != (1024,) or not np.isfinite(vector).all():
        raise ValueError("Invalid ZONOS3 steering vector")
    vector.setflags(write=False)
    return vector


def emotion_delta(emotion, strength, config):
    if emotion in (None, "", "neutral"):
        return None
    name = ALIASES.get(emotion, emotion)
    if name not in EMOTIONS:
        raise ValueError(f"Unsupported ZONOS3 emotion: {emotion}")
    if isinstance(strength, bool) or not math.isfinite(strength) or not 0 <= strength <= 8:
        raise ValueError("emotion_strength must be finite and between 0 and 8")
    if config.dim != 1024 or config.n_layers != 11:
        raise ValueError("ZONOS3 emotion directions require the supported Mini architecture")
    if strength == 0:
        return None
    return {19: direction(name) * strength}
