from dataclasses import replace
import pytest
import httpx
from fastapi import FastAPI
from ai2apps.agents.parameter_forms import ParameterForm,register_form,FORMS
from ai2apps.api.parameter_forms import create_parameter_forms_router
from ai2apps.identity import RequestPrincipal
from test_app_interactions import runtime,wait
import test_parameter_forms as forms

@pytest.mark.asyncio
@pytest.mark.parametrize('owner',['fixture.alpha','package.beta'])
async def test_setup_is_owner_declared_read_only_and_keeps_pending_draft(runtime,monkeypatch,owner):
    key=owner+'.configure'
    async def describe(*a):return {'install':{'appId':owner,'capability':'fixture.render','requirements':{}},'models':[]}
    register_form(ParameterForm(key,owner,{'type':'object','properties':{'text':{'type':'string'}},'additionalProperties':False},(),describe=describe,provider_version='1'))
    monkeypatch.setattr(forms,'ARGS',{'request_id':'setup-'+owner,'capability':key,'initial_values':{'text':'preserve'}})
    run=forms.setup(runtime)
    try:
        await runtime.start_background_tasks();run=await wait(runtime,run.id,'waiting_input')
        interaction=runtime.agents.list_interactions(run.id)[0]
        app=FastAPI();app.include_router(create_parameter_forms_router(lambda:runtime,RequestPrincipal.legacy_local),prefix='/v1/platform')
        base=f'/v1/platform/agent-runs/{run.id}/interactions/{interaction.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            state=(await client.get(base)).json()
            setup=await client.get(base+'/setup');assert setup.status_code==200,setup.text
            data=setup.json();assert data['target']['app_id']==owner and data['install']['appId']==owner
            assert data['install']['intent']['completionPolicy']=='configure_only'
            assert (await client.get(base+'/setup')).json()['install']['actionId']==data['install']['actionId']
            after=(await client.get(base)).json();assert after['values']==state['values'] and after['revision']==state['revision']
            assert runtime.agents.get_run(run.id).status.value=='waiting_input'
            with runtime.database.transaction() as db:assert db.execute('select count(*) from studio_background_jobs').fetchone()[0]==0
            FORMS[key]=replace(FORMS[key],provider_version='changed')
            assert (await client.get(base+'/setup')).status_code==409
    finally:await runtime.stop_background_tasks();FORMS.pop(key,None)
