import os
from importlib.resources import files

from ai2apps.model_worker.cache_moe import DeepseekV4ChatAdapter


class DeepSeekV4Flash2BitWorkerAdapter(DeepseekV4ChatAdapter):
    async def configure_engine(self, engine, checkpoint, runtime_options) -> None:
        await super().configure_engine(engine, checkpoint, runtime_options)
        tokenizer = getattr(engine, "tokenizer", None)
        if tokenizer is None:
            raise RuntimeError("DeepSeek V4 tokenizer is unavailable after engine start")
        template = files("omlx_model_deepseek_v4_flash_2bit").joinpath(
            "assets", "chat_template.jinja"
        ).read_text(encoding="utf-8")
        tokenizer.chat_template = template


def create_adapter(context):
    # Runtime 1.5.4 provides the byte-exact native Direct-L1 loader and Direct
    # Prefill path validated for this pinned 2-bit expert-major checkpoint.
    # Explicit Host environment settings remain authoritative for A/B rollback.
    os.environ.setdefault("OMLX_MOE_DIRECT_L1", "1")
    os.environ.setdefault("OMLX_DEEPSEEK_V4_DIRECT_PREFILL", "1")
    return DeepSeekV4Flash2BitWorkerAdapter(context)
