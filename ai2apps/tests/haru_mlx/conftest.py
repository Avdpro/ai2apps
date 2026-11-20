import json
import os
import struct
from pathlib import Path

import pytest

# Numerical parity uses full float32. MLX otherwise defaults to reduced
# precision GEMM on newer Apple GPUs; retain the upstream error thresholds.
# Also pass this at process launch when combining with other MLX test suites.
os.environ.setdefault('MLX_ENABLE_TF32', '0')

TINY_CONFIG = Path(__file__).parent / "parity" / "tiny_config.json"


@pytest.fixture(scope="session")
def tiny_config():
    """A Haru configuration with every layer type at a size that runs anywhere."""
    from ai2apps.model_worker.haru_mlx.config import HaruConfig

    return HaruConfig.from_dict(json.loads(TINY_CONFIG.read_text()))


@pytest.fixture(scope="session")
def checkpoint() -> Path:
    """The checkpoint directory named by ``HARU_MODEL``."""
    path = os.environ.get("HARU_MODEL")
    if not path:
        pytest.skip("set HARU_MODEL to a checkpoint directory")
    return Path(path)


@pytest.fixture(scope="session")
def checkpoint_shapes(checkpoint) -> dict[str, tuple[int, ...]]:
    """``{tensor name: shape}`` from the safetensors header (no tensor is read)."""
    with (checkpoint / "model.safetensors").open("rb") as file:
        (length,) = struct.unpack("<Q", file.read(8))
        header = json.loads(file.read(length))
    header.pop("__metadata__", None)
    return {name: tuple(entry["shape"]) for name, entry in header.items()}
