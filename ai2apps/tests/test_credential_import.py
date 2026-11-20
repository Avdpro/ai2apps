import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.credential_import import CredentialImport, CredentialImportError
from ai2apps.model_manager import ModelManagerStore
from ai2apps.identity import RequestPrincipal, MemberRole


class Secrets:
    def __init__(self): self.values = {}
    def load(self, key): return self.values[key]
    def store(self, key, value): self.values[key] = value
    def delete(self, key): self.values.pop(key, None)


IDENTITY = {'user_id':'user-one','actor_id':'user-one','cloud_origin':'https://cloud.example',
            'installation_id':'installation-one','membership_epoch':1,'security_id':'security-one'}
PRINCIPAL = RequestPrincipal('user-one','installation-one','org','billing',MemberRole.CORE,1)


def setup(tmp_path, label, identity=None):
    path = tmp_path / label
    store = ModelManagerStore(path, secret_backend=Secrets())
    runtime = SimpleNamespace(model_manager=store, config=SimpleNamespace(paths=SimpleNamespace(base_path=path)),
                              cloud=SimpleNamespace(base_url='https://cloud.example'))
    current = dict(identity or IDENTITY)
    current['security_id'] = label
    service = CredentialImport(runtime)
    runtime.credential_import = service
    service.principal_context = lambda principal: dict(current)
    async def live(principal=None): return dict(current)
    service.live_identity = live
    return service, current


def put(service, key='source-token', endpoint='https://api.example/v1'):
    return service.runtime.model_manager.put_cloud('sample', {'name':'Sample','base_url':endpoint,
             'protocol':'openai','models':['chat-one'],'api_key':key})


async def prepare(source, target, replace=False):
    offer = await source.native_context()
    action = {'action':'import','source':'source','offer_id':offer['offer_id'],
              'selected':['cloud:sample'],'replace_existing':replace}
    ticket = target.begin(PRINCIPAL,action)
    payload = await source.native_export({'offer_id':offer['offer_id'],'selected':['cloud:sample'],
                                        'destination':await target.live_identity()})
    return ticket, payload


@pytest.mark.asyncio
async def test_one_shot_copies_into_independent_secret_store(tmp_path):
    source,_ = setup(tmp_path,'source'); target,_ = setup(tmp_path,'target')
    put(source)
    offer = await source.native_context()
    assert 'source-token' not in json.dumps(offer)
    ticket,payload = await prepare(source,target)
    result = await target.native_install({'ticket':ticket,'payload':payload})
    assert result == {'status':'completed','items':[{'key':'cloud:sample','status':'imported'}]}
    assert 'source-token' not in json.dumps(result)
    assert target.runtime.model_manager._load_provider_key('sample',target.runtime.model_manager._cloud_data()['sample']) == 'source-token'
    source.runtime.model_manager.delete_cloud('sample')
    assert target.runtime.model_manager.list_cloud()[-1]['configured']
    with pytest.raises(CredentialImportError): await target.native_install({'ticket':ticket,'payload':payload})


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value',[('user_id','other'),('cloud_origin','https://other.example')])
async def test_source_rejects_different_account_or_cloud(tmp_path,field,value):
    source,_=setup(tmp_path,'source');put(source)
    offer=await source.native_context();other={**IDENTITY,field:value}
    with pytest.raises(CredentialImportError,match='same AI2Apps'):
        await source.native_export({'offer_id':offer['offer_id'],'selected':['cloud:sample'],'destination':other})


@pytest.mark.asyncio
async def test_changed_source_cannot_use_old_offer(tmp_path):
    source,_=setup(tmp_path,'source');put(source)
    offer=await source.native_context();put(source,'rotated-token')
    with pytest.raises(CredentialImportError,match='changed'):
        await source.native_export({'offer_id':offer['offer_id'],'selected':['cloud:sample'],'destination':IDENTITY})


@pytest.mark.asyncio
async def test_destination_change_during_native_consent_rejected(tmp_path):
    source,_=setup(tmp_path,'source');target,_=setup(tmp_path,'target');put(source)
    ticket,payload=await prepare(source,target)
    put(target,'concurrent-key')
    with pytest.raises(CredentialImportError,match='Destination changed'):
        await target.native_install({'ticket':ticket,'payload':payload})
    assert target.runtime.model_manager._load_provider_key('sample',target.runtime.model_manager._cloud_data()['sample']) == 'concurrent-key'


@pytest.mark.asyncio
async def test_existing_key_requires_replacement_and_uses_source_endpoint(tmp_path):
    source,_=setup(tmp_path,'source');target,_=setup(tmp_path,'target');put(source);put(target,'old','https://other.example/v1')
    ticket,payload=await prepare(source,target)
    with pytest.raises(CredentialImportError,match='explicitly'):
        await target.native_install({'ticket':ticket,'payload':payload})
    ticket,payload=await prepare(source,target,replace=True)
    assert (await target.native_install({'ticket':ticket,'payload':payload}))['status']=='completed'
    raw=target.runtime.model_manager._cloud_data()['sample']
    assert raw['base_url']=='https://api.example/v1'
    assert 'api_key' not in raw


@pytest.mark.asyncio
async def test_foreign_owner_neither_exported_nor_overwritten(tmp_path):
    source,_=setup(tmp_path,'source');put(source)
    foreign={**IDENTITY,'user_id':'other','actor_id':'other'}
    source.mark_owner(foreign,'cloud:sample')
    assert (await source.native_context())['providers']==[]
    target,_=setup(tmp_path,'target');put(target,'old');target.mark_owner(foreign,'cloud:sample')
    fresh,_=setup(tmp_path,'fresh');put(fresh)
    ticket,payload=await prepare(fresh,target,replace=True)
    with pytest.raises(CredentialImportError,match='another account'):
        await target.native_install({'ticket':ticket,'payload':payload})


@pytest.mark.asyncio
async def test_expiry_reset_and_account_switch_invalidate_requests(tmp_path):
    source,_=setup(tmp_path,'source');target,current=setup(tmp_path,'target');put(source)
    ticket,payload=await prepare(source,target)
    current['membership_epoch']=2
    with pytest.raises(CredentialImportError,match='changed'):
        await target.native_install({'ticket':ticket,'payload':payload})
    current['membership_epoch']=1
    target.clock=lambda:10**12
    with pytest.raises(CredentialImportError,match='expired'):
        await target.native_context(ticket)
    replacement=CredentialImport(target.runtime)
    with pytest.raises(CredentialImportError,match='expired'):
        await replacement.native_context(ticket)


@pytest.mark.asyncio
async def test_export_offer_consumed_once_and_selection_fixed(tmp_path):
    source,_=setup(tmp_path,'source');put(source)
    offer=await source.native_context()
    body={'offer_id':offer['offer_id'],'selected':['cloud:sample'],'destination':IDENTITY}
    await source.native_export(body)
    with pytest.raises(CredentialImportError,match='expired'):
        await source.native_export(body)


@pytest.mark.asyncio
async def test_video_byok_is_actor_bound_and_copied_without_returning_key(tmp_path):
    from ai2apps.video.byok import set_credential,credential
    source,_=setup(tmp_path,'source');target,_=setup(tmp_path,'target')
    set_credential(source.runtime,'minimax','user-one','test-video-token')
    offer=await source.native_context()
    assert offer['providers'][0]['key']=='video:minimax'
    assert offer['providers'][0]['ownership']=='owned'
    action={'action':'import','source':'source','offer_id':offer['offer_id'],'selected':['video:minimax']}
    ticket=target.begin(PRINCIPAL,action)
    payload=await source.native_export({**action,'destination':IDENTITY})
    result=await target.native_install({'ticket':ticket,'payload':payload})
    assert credential(target.runtime,'minimax','user-one')=='test-video-token'
    assert 'test-video-token' not in json.dumps(result)
    with pytest.raises(Exception):credential(target.runtime,'minimax','other-user')


@pytest.mark.asyncio
async def test_partial_import_keeps_verified_success(tmp_path,monkeypatch):
    source,_=setup(tmp_path,'source');target,_=setup(tmp_path,'target');put(source)
    from ai2apps.video.byok import set_credential
    set_credential(source.runtime,'minimax','user-one','video-key')
    offer=await source.native_context();keys=[e['key'] for e in offer['providers']]
    action={'action':'import','source':'source','offer_id':offer['offer_id'],'selected':keys}
    ticket=target.begin(PRINCIPAL,action)
    payload=await source.native_export({**action,'destination':IDENTITY})
    original=target._install_entry
    def install(identity,entry):
        if entry['kind']=='video':raise RuntimeError('must-not-leak-secret')
        return original(identity,entry)
    monkeypatch.setattr(target,'_install_entry',install)
    result=await target.native_install({'ticket':ticket,'payload':payload})
    assert result['status']=='partial'
    assert [i['status'] for i in result['items']]==['imported','failed']
    assert 'must-not-leak' not in json.dumps(result)


def test_native_callbacks_reject_browser_and_missing_token(tmp_path,monkeypatch):
    from ai2apps.api.credential_import import create_credential_import_router
    source,_=setup(tmp_path,'source');put(source)
    app=FastAPI();app.include_router(create_credential_import_router(lambda:source.runtime,lambda:PRINCIPAL))
    client=TestClient(app)
    monkeypatch.setenv('AI2APPS_HELPER_TOKEN','a'*64)
    for path in ['context','export','install']:
        assert client.post('/credential-import/native/'+path,json={}).status_code==401
        assert client.post('/credential-import/native/'+path,json={},headers={'Authorization':'Bearer '+'a'*64,'Origin':'http://localhost'}).status_code==401
    response=client.post('/credential-import/native/context',json={},headers={'Authorization':'Bearer '+'a'*64})
    assert response.status_code==200 and 'source-token' not in response.text
    assert client.post('/credential-import/action',json={'action':'import','api_key':'forged'}).status_code==422


def test_legacy_or_non_desktop_principal_is_not_a_user_proof(tmp_path):
    source,_=setup(tmp_path,'source')
    with pytest.raises(CredentialImportError,match='Sign in'):
        CredentialImport.principal_context(source,RequestPrincipal.legacy_local())


@pytest.mark.asyncio
async def test_live_identity_requires_cloud_verified_user_not_email(tmp_path):
    source,_=setup(tmp_path,'source')
    runtime=source.runtime;runtime.offline_mode=False
    class Cloud:
        base_url='https://cloud.example'
        async def request(self,*args):
            return httpx.Response(200,json={'user':{'id':'other','email':'same@example.com'}})
    runtime.cloud=Cloud()
    with pytest.raises(CredentialImportError,match='Reauthenticate'):
        await CredentialImport.live_identity(source,PRINCIPAL)


@pytest.mark.asyncio
async def test_refreshing_model_catalog_does_not_reassign_key_owner(tmp_path):
    source,_=setup(tmp_path,'source');put(source)
    source.mark_owner(IDENTITY,'cloud:sample')
    source.runtime.model_manager.put_cloud('sample',{'models':['chat-two','chat-three']})
    offer=await source.native_context()
    assert offer['providers'][0]['ownership']=='owned'


@pytest.mark.asyncio
async def test_owner_storage_failure_rolls_back_replaced_provider(tmp_path,monkeypatch):
    source,_=setup(tmp_path,'source');target,_=setup(tmp_path,'target')
    put(source);put(target,'old-token','https://old.example/v1')
    ticket,payload=await prepare(source,target,replace=True)
    original=target._write_owners;attempts=[]
    def write(value):
        attempts.append(1)
        if len(attempts)==1:raise OSError('fixture disk failure')
        return original(value)
    monkeypatch.setattr(target,'_write_owners',write)
    result=await target.native_install({'ticket':ticket,'payload':payload})
    assert result['items'][0]['status']=='failed'
    raw=target.runtime.model_manager._cloud_data()['sample']
    assert raw['base_url']=='https://old.example/v1'
    assert target.runtime.model_manager._load_provider_key('sample',raw)=='old-token'


@pytest.mark.asyncio
async def test_impossible_rollback_reported_unknown_not_unchanged(tmp_path,monkeypatch):
    source,_=setup(tmp_path,'source');target,_=setup(tmp_path,'target');put(source)
    ticket,payload=await prepare(source,target)
    def fail(value):raise OSError('fixture permanent failure')
    monkeypatch.setattr(target,'_write_owners',fail)
    result=await target.native_install({'ticket':ticket,'payload':payload})
    assert result['status']=='partial' and result['items'][0]['status']=='unknown'


@pytest.mark.asyncio
async def test_unsafe_source_endpoint_not_offered_but_destination_conflict_preserved(tmp_path):
    source,_=setup(tmp_path,'source');put(source,endpoint='http://localhost:1234/v1')
    assert (await source.native_context())['providers']==[]
    target,_=setup(tmp_path,'target');put(target,'old-token','http://localhost:1234/v1')
    put(source,endpoint='https://api.example/v1')
    ticket,payload=await prepare(source,target)
    with pytest.raises(CredentialImportError,match='explicitly'):
        await target.native_install({'ticket':ticket,'payload':payload})

@pytest.mark.asyncio
async def test_selected_ui_language_is_bound_to_target_ticket(tmp_path):
    target, identity = setup(tmp_path, 'target')
    ticket = target.begin(PRINCIPAL, {'action':'list', 'language':'ja'})
    context = await target.native_context(ticket)
    assert context['action']['language'] == 'ja'
    assert context['identity'] == identity


def test_import_ui_language_rejects_arbitrary_dialog_content():
    from pydantic import ValidationError
    from ai2apps.api.credential_import import ImportAction
    assert ImportAction(action='list', language='zh-TW').language == 'zh-TW'
    with pytest.raises(ValidationError):
        ImportAction(action='list', language='Authenticate to another account')
