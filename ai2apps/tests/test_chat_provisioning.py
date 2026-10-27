"""Chat hosts existing durable ACPF sessions; no business task is submitted."""
from types import SimpleNamespace
from dataclasses import replace
import pytest
import httpx
from fastapi import FastAPI
from ai2apps.agents.parameter_forms import ParameterForm, register_form, FORMS
from ai2apps.api.parameter_forms import create_parameter_forms_router
from ai2apps.identity import RequestPrincipal
from ai2apps.provisioning.repository import ProvisioningSessionRepository
from test_app_interactions import runtime, wait
import test_parameter_forms as forms

@pytest.mark.asyncio
@pytest.mark.parametrize('owner', ['fixture.alpha', 'package.beta'])
async def test_chat_configuration_reconnect_guards_and_no_business_submission(runtime,monkeypatch,owner):
    key=owner+'.chat-config'
    async def describe(*args): return {'install':{'appId':owner,'capability':'fixture.compute'}}
    register_form(ParameterForm(key,owner,{'type':'object','properties':{'text':{'type':'string'}},'additionalProperties':False},(),describe=describe,provider_version='1'))
    monkeypatch.setattr(forms,'ARGS',{'request_id':'config-'+owner,'capability':key,'initial_values':{'text':'preserved'}})
    repo=ProvisioningSessionRepository(runtime.database);calls=[]
    async def resume(identifier):return repo.get(identifier)
    async def confirm(identifier,consents):
        calls.append(('confirm',consents));return repo.update(identifier,status='downloading_checkpoint')
    async def cancel(identifier):return repo.update(identifier,status='cancelled')
    def ensure(**args):
        calls.append(('ensure',args));record=repo.create(**{k:v for k,v in args.items() if k!='requirements'},profile_id='standard',request_fingerprint='a'*64,status='awaiting_confirmation',plan={'profileId':'standard'})
        return {'status':'setup_required','session':record}
    async def noop():pass
    def select_profile(identifier, profile):
        old=repo.get(identifier)
        repo.update(identifier,status='cancelled')
        record=repo.create(actor_id=old['actorId'],installation_id=old['installationId'],
            app_instance_id=old['appInstanceId'],app_id=old['appId'],capability=old['capability'],
            action_id=old['actionId'],intent=old['intent'],profile_id=profile,
            request_fingerprint='b'*64,status='awaiting_confirmation',plan={'profileId':profile})
        return {'status':'setup_required','session':record}
    engine=SimpleNamespace(startup=noop,shutdown=noop,repository=repo,select_profile=select_profile,resume_if_possible=resume,ensure=ensure,confirm=confirm,cancel=cancel)
    monkeypatch.setattr(runtime,'provisioning',engine)
    monkeypatch.setattr(runtime.extension_manager,'launch_app',lambda app_id,**kw:(SimpleNamespace(id='fixture-instance'),None,None))
    run=forms.setup(runtime)
    try:
        await runtime.start_background_tasks();run=await wait(runtime,run.id,'waiting_input');item=runtime.agents.list_interactions(run.id)[0]
        app=FastAPI();app.include_router(create_parameter_forms_router(lambda:runtime,RequestPrincipal.legacy_local),prefix='/v1/platform')
        base=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            assert (await client.get(base+'/setup/session')).json()['session'] is None
            state=(await client.get(base)).json()
            first=await client.post(base+'/setup/session');assert first.status_code==200,first.text
            identifier=first.json()['session']['id']
            assert (await client.post(base+'/setup/session')).json()['session']['id']==identifier
            assert len(calls)==1
            selected=await client.post(base+'/setup/session/select-profile',json={'profileId':'compact'})
            assert selected.status_code==200,selected.text
            identifier=selected.json()['session']['id']
            assert (await client.get(base+'/setup/session')).json()['session']['profileId']=='compact'
            assert calls[0][1]['app_id']==owner and calls[0][1]['intent']['completionPolicy']=='configure_only'
            assert (await client.post(base+'/setup/session/acknowledge-return',json={})).status_code==409
            assert (await client.post(base+'/setup/session/confirm',json={'licenseConsents':[]})).status_code==200
            # Recreate the view/router: discovery is from the server record, no browser storage.
            assert (await client.get(base+'/setup/session')).json()['session']['status']=='downloading_checkpoint'
            repo.update(identifier,status='ready')
            assert (await client.post(base+'/setup/session/acknowledge-return',json={})).status_code==200
            assert (await client.get(base)).json()['values']==state['values']
            assert runtime.agents.get_run(run.id).status.value=='waiting_input'
            assert (await client.post(base+'/setup/session/execute',json={})).status_code==404
            foreign_app=FastAPI()
            def foreign():return replace(RequestPrincipal.legacy_local(),actor_user_id='foreign')
            foreign_app.include_router(create_parameter_forms_router(lambda:runtime,foreign),prefix='/v1/platform')
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=foreign_app),base_url='http://test') as other:
                assert (await other.get(base+'/setup/session')).status_code in (403,404)
                assert (await other.post(base+'/setup/session/confirm',json={})).status_code in (403,404)
            FORMS[key]=replace(FORMS[key],provider_version='changed')
            assert (await client.get(base+'/setup/session')).status_code==409
    finally:
        await runtime.stop_background_tasks();FORMS.pop(key,None)
