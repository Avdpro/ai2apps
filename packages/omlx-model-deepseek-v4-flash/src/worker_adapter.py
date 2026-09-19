from importlib.resources import files

from ai2apps.model_worker.cache_moe import DeepseekV4ChatAdapter


class DeepSeekV4FlashWorkerAdapter(DeepseekV4ChatAdapter):
    async def configure_engine(self, engine, checkpoint, runtime_options) -> None:
        await super().configure_engine(engine, checkpoint, runtime_options)
        tokenizer = getattr(engine, "tokenizer", None)
        if tokenizer is None:
            raise RuntimeError("DeepSeek V4 tokenizer is unavailable after engine start")
        template = files("omlx_model_deepseek_v4_flash").joinpath(
            "assets", "chat_template.jinja"
        ).read_text(encoding="utf-8")
        tokenizer.chat_template = template


def create_adapter(context):
    return DeepSeekV4FlashWorkerAdapter(context)
