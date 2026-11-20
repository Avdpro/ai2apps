"""E5 embedding adapter for authenticated Model Worker v1."""
import asyncio
import threading
from ai2apps.model_worker.protocol import ModelWorkerError

MODEL_ID='ai2apps.model.multilingual-e5-small-cuda/default'
REPO='intfloat/multilingual-e5-small'
REVISION='614241f622f53c4eeff9890bdc4f31cfecc418b3'

def fail(message,code='invalid_request',status=400):
    raise ModelWorkerError(message,code=code,status_code=status)

class CudaE5Adapter:
    def __init__(self,context):
        self.context=context;self.engine=None;self.path=None
        self.lock=asyncio.Lock();self.events={};self.stopped=False
    async def start(self):pass
    def cancel(self,request_id):
        if event:=self.events.get(request_id):event.set()
    async def stop(self):
        self.stopped=True
        for event in self.events.values():event.set()
        async with self.lock:
            if self.engine is not None:await asyncio.to_thread(self.engine.close)
            self.engine=None;self.path=None
    async def invoke(self,request):
        if self.stopped:fail('Embedding adapter stopped','model_unavailable',503)
        if request.operation!='embeddings':fail('Unsupported operation','operation_not_supported')
        body=dict(request.payload)
        if body.get('model') not in (MODEL_ID,REPO):fail('Unknown E5 model','model_not_supported')
        if body.get('encoding_format','float')!='float':fail('Only float embeddings are supported','unsupported_feature')
        dimensions=body.get('dimensions',384)
        if type(dimensions) is not int or dimensions!=384:fail('E5 requires384 dimensions','unsupported_feature')
        if body.get('stream') or body.get('_ai2apps_model_settings'):fail('Unsupported embedding options','unsupported_feature')
        texts=body.get('input');texts=[texts] if isinstance(texts,str) else texts
        kind=body.get('input_type','passage')
        from cuda_e5_engine import CudaE5Engine
        try:CudaE5Engine.validate(texts,kind)
        except ValueError as e:fail(str(e))
        cp=self.context.checkpoint_for(str(body['model']))
        if cp is None or cp.path is None:fail('E5 checkpoint unavailable','model_unavailable',503)
        if cp.model_id!=MODEL_ID or cp.repo_id!=REPO or cp.revision!=REVISION:fail('Unsupported E5 checkpoint','model_not_supported')
        if request.request_id in self.events:fail('Duplicate request ID','request_conflict',409)
        event=threading.Event();self.events[request.request_id]=event
        def check():
            if event.is_set():fail('Embedding cancelled','request_cancelled',499)
        def compute():
            check()
            if self.engine is None:
                self.engine=CudaE5Engine(cp.path,check=check);self.path=cp.path
            elif self.path!=cp.path:fail('E5 checkpoint changed','model_not_supported')
            result=self.engine.encode(texts,input_type=kind,check=check);check()
            return {'object':'list','model':MODEL_ID,'dimension':384,'data':[{'object':'embedding','index':i,'embedding':v} for i,v in enumerate(result['vectors'])],'usage':{'prompt_tokens':result['prompt_tokens'],'total_tokens':result['prompt_tokens']}}
        try:
            async with self.lock:
                if self.stopped:fail('Embedding adapter stopped','model_unavailable',503)
                check();task=asyncio.create_task(asyncio.to_thread(compute))
                try:return await asyncio.shield(task)
                except asyncio.CancelledError:
                    event.set()
                    while not task.done():
                        try:await asyncio.shield(task)
                        except asyncio.CancelledError:continue
                        except Exception:break
                    if not task.cancelled():task.exception()
                    raise
        finally:self.events.pop(request.request_id,None)

def create_adapter(context):return CudaE5Adapter(context)
