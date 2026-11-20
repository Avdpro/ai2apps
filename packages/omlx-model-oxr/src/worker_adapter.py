from ai2apps.model_worker import OmlxChatAdapter

class OxrWorkerAdapter(OmlxChatAdapter):
    async def create_engine(self, checkpoint, runtime_options=None):
        if checkpoint.path is None:
            return await super().create_engine(checkpoint, runtime_options)
        from omlx.engine.vlm import VLMBatchedEngine
        return VLMBatchedEngine(str(checkpoint.path), trust_remote_code=False)

def create_adapter(context):
    return OxrWorkerAdapter(context)
