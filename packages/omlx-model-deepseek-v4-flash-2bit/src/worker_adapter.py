import os

from ai2apps.model_worker.cache_moe import DeepseekV4ChatAdapter


def create_adapter(context):
    # Runtime 1.5.4 provides the byte-exact native Direct-L1 loader and Direct
    # Prefill path validated for this pinned 2-bit expert-major checkpoint.
    # Explicit Host environment settings remain authoritative for A/B rollback.
    os.environ.setdefault("OMLX_MOE_DIRECT_L1", "1")
    os.environ.setdefault("OMLX_DEEPSEEK_V4_DIRECT_PREFILL", "1")
    return DeepseekV4ChatAdapter(context)
