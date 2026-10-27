"""Search owner API tests: fixture HTTP, never user credentials or paid requests."""
from types import SimpleNamespace
from unittest.mock import Mock
import json
import pytest
from ai2apps.browser import search_api as api

@pytest.fixture
def runtime():
    provider={'id':'deepseek','base_url':'https://api.deepseek.com','enabled':True,'configured':True}
    manager=SimpleNamespace(list_cloud=lambda:[provider],resolve_credential=Mock(return_value='fixture-key'))
    return SimpleNamespace(model_manager=manager,privacy_mode=False,secrets=SimpleNamespace(list=lambda:[]),provider=provider)

@pytest.mark.parametrize('update',[{'configured':False},{'enabled':False},{'base_url':'https://proxy.example/v1'},{'base_url':'https://api.deepseek.com.evil.test'},{'id':'another-provider'}])
def test_only_official_enabled_byok_qualifies(runtime,update):
    assert api.deepseek_available(runtime,'local')
    runtime.provider.update(update)
    assert not api.deepseek_available(runtime,'local')
    assert api.status(runtime,'local')['fast_source']=='google'
    runtime.model_manager.resolve_credential.assert_not_called()

def test_core_identity_required(runtime,monkeypatch):
    from ai2apps.identity import IdentityRepository
    monkeypatch.setattr(IdentityRepository,'local_principal_for',lambda *args:SimpleNamespace(is_core=False))
    runtime.database=object()
    assert not api.deepseek_available(runtime,'guest')

@pytest.mark.asyncio
@pytest.mark.parametrize('system,profile',[(True,'normal'),(False,'privacy')])
async def test_privacy_denies_before_key_resolution_or_http(runtime,system,profile):
    runtime.privacy_mode=system
    with pytest.raises(ValueError,match='privacy'):
        await api.search(runtime,'local','query',5,provider='deepseek',model_profile=profile)
    runtime.model_manager.resolve_credential.assert_not_called()

@pytest.mark.asyncio
async def test_scope_and_length_deny_before_credentials(runtime):
    for query,scope in [('x'*129,['https://api.deepseek.com/**']),('query',['https://example.com/**'])]:
        with pytest.raises(ValueError):await api.search(runtime,'local',query,5,provider='deepseek',scopes=scope)
    runtime.model_manager.resolve_credential.assert_not_called()

@pytest.mark.asyncio
async def test_official_post_normalization_and_no_secrets(runtime,monkeypatch):
    requests=[]
    class Client:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            requests.append((url,kwargs))
            return SimpleNamespace(status_code=200,content=b'{}',json=lambda:{'results':[
                {'title':'Official','url':'https://example.com/a','snippet':'Snippet','summary':'Long','content':'Unrequested'},
                {'title':'bad','url':'javascript:bad'}, {'title':'bad','url':'https://user:password@example.com/'},None]})
    monkeypatch.setattr(api.httpx,'AsyncClient',lambda **kwargs:Client())
    found=await api.search(runtime,'local','测试',5,provider='deepseek',scopes=['https://api.deepseek.com/v1/tools/search'])
    assert found['items']==[{'title':'Official','url':'https://example.com/a','summary':'Snippet'}]
    assert found['provider']=='deepseek' and 'fixture-key' not in json.dumps(found)
    assert requests[0][1]['headers']=={'Authorization':'Bearer fixture-key'}
    assert requests[0][1]['json']=={'query':'测试','count':5,'need_content':False}
    assert api.status(runtime,'local')['fast_source']=='deepseek'

@pytest.mark.asyncio
@pytest.mark.parametrize('status',[401,402,429,500])
async def test_api_failure_never_falls_back_or_retries(runtime,monkeypatch,status):
    called=[]
    class Client:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):called.append(1);return SimpleNamespace(status_code=status)
    monkeypatch.setattr(api.httpx,'AsyncClient',lambda **kwargs:Client())
    with pytest.raises(ValueError) as error:await api.search(runtime,'local','query',5,provider='deepseek')
    assert str(status) in str(error.value) and 'fixture-key' not in str(error.value)
    assert len(called)==1

@pytest.mark.asyncio
async def test_transport_exception_redacted(runtime,monkeypatch):
    class Client:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):raise api.httpx.ConnectError('fixture-key')
    monkeypatch.setattr(api.httpx,'AsyncClient',lambda **kwargs:Client())
    with pytest.raises(ValueError) as error:await api.search(runtime,'local','query',5,provider='deepseek')
    assert 'fixture-key' not in str(error.value)
