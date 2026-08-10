"""Supported AI2Apps imports for product-specific inference engines."""

from omlx.engine.flesh import DeepseekV4FleshEngine
from omlx.engine.qwen36_arena import Qwen36ArenaEngine
from omlx.engine.qwen36_flesh import Qwen36FleshEngine
from omlx.engine.qwen36_tiered import Qwen36TieredEngine

__all__ = [
    "DeepseekV4FleshEngine",
    "Qwen36ArenaEngine",
    "Qwen36FleshEngine",
    "Qwen36TieredEngine",
]
