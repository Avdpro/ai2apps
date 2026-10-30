from types import SimpleNamespace
import pytest
from ai2apps.model_invocation import ModelInvocationService,ModelInvocationContext
from ai2apps.identity import RequestPrincipal

@pytest.mark.asyncio
@pytest.mark.parametrize('model_id',['arbitrary-provider/small','different-provider/vision'])
async def test_host_chat_transport_is_identity_scoped_and_provider_agnostic(model_id):
 service=ModelInvocationService(SimpleNamespace(services=None));calls=[]
 async def provider(payload,model_context=None):calls.append((payload,model_context));return {'choices':[]}
 async def catalog():return {'models':[{'id':model_id,'capabilities':['image_recognition']}]}
 service.bind_chat_provider(provider,catalog)
 context=ModelInvocationContext.from_principal(RequestPrincipal.legacy_local(),session_id='owner-task',consumer_app_id='arbitrary-app')
 assert service.chat_provider_ready
 assert (await service.chat_catalog())[0]['id']==model_id
 await service.invoke_chat_json({'model':model_id,'messages':[]},context=context)
 assert calls[0][1] is context and calls[0][0]['model']==model_id

@pytest.mark.asyncio
async def test_unbound_gateway_is_unavailable_not_fallback():
 service=ModelInvocationService(SimpleNamespace(services=None))
 assert not service.chat_provider_ready
 with pytest.raises(RuntimeError):await service.chat_catalog()
