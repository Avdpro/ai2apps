"""Development entry point for Flash Next using the shared Qwen Worker protocol."""
from ai2apps.model_worker.cuda_qwen import CudaQwenChatAdapter


class FlashAdapter(CudaQwenChatAdapter):
    checkpoint_revision = "23c6ed09ef3ec9bec2f31039f0e23e94dfacd1b5"

    def load_backend(self, checkpoint):
        from transformers import AutoProcessor
        from qwen38_flash_backend import load
        model, self.store, self.load_report = load(checkpoint, batched_experts=True)
        processor = AutoProcessor.from_pretrained(checkpoint, local_files_only=True,
            trust_remote_code=False, use_fast=False)
        return model, processor

    def unload_backend(self):
        if getattr(self, "store", None) is not None:
            self.store.close()
            self.store = None


def create_adapter(context):
    return FlashAdapter(context)
