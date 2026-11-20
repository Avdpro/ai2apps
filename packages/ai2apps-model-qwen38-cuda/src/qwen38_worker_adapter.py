"""Pinned Qwen3.8 27B CUDA Model Worker entry point."""
from ai2apps.model_worker.cuda_qwen import CudaQwenChatAdapter


class Qwen38Adapter(CudaQwenChatAdapter):
    checkpoint_revision = "16b6615af3548b88e2d8e382457bc705b00479cf"

    def load_backend(self, checkpoint):
        from qwen38_backend import load
        return load(checkpoint)


def create_adapter(context):
    return Qwen38Adapter(context)
