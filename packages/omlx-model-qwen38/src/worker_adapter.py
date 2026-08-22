# SPDX-License-Identifier: Apache-2.0
"""Isolated AI2Apps Model Worker entry point for Qwen3.8."""

from __future__ import annotations

from ai2apps.model_worker import ModelWorkerCheckpoint, OmlxChatAdapter

from omlx_model_qwen38.adapter import Qwen38Adapter


class Qwen38WorkerAdapter(OmlxChatAdapter):
    async def create_engine(self, checkpoint: ModelWorkerCheckpoint, runtime_options=None):
        # This registry belongs to the Package Worker process. Registering the
        # compatibility loader here never mutates or imports code in Host.
        from omlx.model_adapters import get_model_adapter_registry
        from omlx.engine.vlm import VLMBatchedEngine

        get_model_adapter_registry().register(Qwen38Adapter(), replace=True)
        if checkpoint.path is None:  # engine_for reports the structured error first
            return await super().create_engine(checkpoint, runtime_options)
        return VLMBatchedEngine(str(checkpoint.path), trust_remote_code=False)


def create_adapter(context):
    return Qwen38WorkerAdapter(context)
