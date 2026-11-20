"""Real registry, owner access, Session artifacts and durable publish form; network fixtures only."""
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import asyncio
import httpx
import pytest
from fastapi import FastAPI
from ai2apps.api.router import create_ai2apps_router
from ai2apps.agents import CompleteAction,ToolCallAction
from ai2apps.agents.parameter_forms import form_action
from ai2apps.chat import ChatRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.services import ToolCallContext,ToolProviderError
from ai2apps.services.aaat import principal_for
from ai2apps.share_works.service import HOST,MINI
from test_app_interactions import runtime,wait


def context(runtime):
    from ai2apps.identity import IdentityRepository,OrganizationType
    identities=IdentityRepository(runtime.database)
    if identities.get_installation() is None:identities.bind_installation(installation_id='share-install',cloud_device_id='share-device',organization_id='share-org',organization_type=OrganizationType.HOUSEHOLD,core_user_id='share-owner',billing_account_id='share-billing',access_epoch=1)
    principal=identities.local_principal_for('share-owner')
    thread,_=ChatRepository(runtime.database,runtime.events,principal=principal).create_thread(title='Share Works')
    return ToolCallContext.from_principal(principal,caller_id='fixture',session_id=thread.session.id)


def setup_cli(runtime,destination='hf'):
    class CLI:
        uploads=0
        async def inspect(self,repo):return {'provider':destination,'repo':repo,'account':'fixture','application_url':'https://fixture-site.hf.space/' if destination=='hf' else 'https://fixture-site.ms.show/'}
        async def upload(self,*args):self.uploads+=1
        async def deploy(self,*args):pass
    cli=CLI();runtime.share_works.cli_factory=lambda provider:cli
    return cli


def test_builtin_share_exports_registered_and_publication_effects(runtime):
    exports=[p for p in runtime.app_capability_router.providers.values() if p.mini_app_id==MINI]
    assert {p.capability for p in exports}=={'share.destinations','share.prepare','share.publish','share.history','share.verify','share.cancel','share.social_prepare','share.social_status','share.x_publish'}
    p=runtime.app_capability_router.providers[MINI+'.publish']
    assert p.app_id==HOST and p.version=='0.1.2'
    tool=runtime.services.get_tool('share.publish')
    assert 'external' in tool.effects
    assert 'publish' in runtime.services.get_tool('share.x_publish').effects


@pytest.mark.asyncio
@pytest.mark.parametrize('source',['workspace','attachment'])
async def test_prepare_owned_session_artifact_and_no_upload(runtime,tmp_path,source):
    cli=setup_cli(runtime);ctx=context(runtime);other=context(runtime)
    path=tmp_path/'work.html';path.write_text('<h1>My work</h1>')
    asset=runtime.workspace.import_artifact(ctx.session_id,path) if source=='workspace' else runtime.documents.create_reference(ctx.session_id,path,media_type='text/html')
    args={'destination':'hf','repo':'fixture/site','artifact_id':asset.id,'title':'Work'}
    result=await runtime.app_capability_router.invoke('share.prepare',args,ctx)
    assert result['status']=='prepared' and not result['published'] and cli.uploads==0
    assert result['publish_parameters']['digest']==result['snapshot']['digest']
    assert result['snapshot']['files']==1
    with pytest.raises(Exception):await runtime.app_capability_router.invoke('share.prepare',args,other)
    publish=result['publish_parameters']
    with pytest.raises(Exception):await runtime.app_capability_router.invoke('share.publish',publish,ctx)
    assert cli.uploads==0
    with pytest.raises(Exception):await runtime.app_capability_router.invoke('share.prepare',{**args,'path':'/tmp/work.html'},ctx)


@pytest.mark.asyncio
@pytest.mark.parametrize('destination',['hf','ms'])
async def test_real_form_publish_once_history_and_changed_receipt(runtime,tmp_path,destination):
    cli=setup_cli(runtime,destination);ctx=context(runtime)
    path=tmp_path/'work.html';path.write_text('<h1>Reviewed work</h1>')
    asset=runtime.workspace.import_artifact(ctx.session_id,path)
    prepared=await runtime.app_capability_router.invoke('share.prepare',{'destination':destination,'repo':'fixture/site','artifact_id':asset.id,'title':'Reviewed work'},ctx)
    args=prepared['publish_parameters'];form_args={'request_id':'publish-confirm-1','capability':'share.publish','provider':MINI+'.publish','initial_values':args}
    runtime.agents.ensure_definition(agent_key='fixture.share',package_version='1',display_name='Share fixture',executor_key='fixture.share',max_steps=10,timeout_seconds=120)
    def execute(c):
        action=form_action(c,form_args)
        if action:return action
        item=c.interaction('form:publish-confirm-1')
        if (item.response or {}).get('status')=='cancelled':return CompleteAction({'cancelled':True})
        if not c.step('publish'):return ToolCallAction('publish','share.publish',{'provider':MINI+'.publish',**args})
        return CompleteAction(c.step('publish').output)
    runtime.agent_runtime.bind_executor('fixture.share',execute)
    run,_=runtime.agents.create_run(session_id=ctx.session_id,agent_key='fixture.share',input={})
    # Read-only public verification fixture; upload/deploy and Task lifecycle are production owner code.
    async def verified(owner,row,report=lambda **kw:None):
        snap=runtime.share_works.snapshot(owner,row['snapshot_id'])
        report(message='Verifying fixture',progress={'stage':'verify','done':1,'total':1})
        result={'anonymous':True,'verified_files':1,'url':snap['application_url']+snap['remote_path']+'/index.html'}
        row['verified']=result;runtime.share_works.store.save('publications',owner,row['request_id'],row)
        return result
    runtime.share_works.verify=verified
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:principal_for(runtime,ctx)))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input');item=runtime.agents.list_interactions(run.id)[0]
        url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            state=await client.get(url);assert state.status_code==200,state.text
            assert state.json()['values']==args and cli.uploads==0
            response=await client.post(url+'/submit',json={'revision':0,'values':args});assert response.status_code==200,response.text
            assert (await client.post(url+'/submit',json={'revision':0,'values':args})).status_code==200
        done=await wait(runtime,run.id,'completed')
        assert cli.uploads==1,done.output
        rows=(await runtime.app_capability_router.invoke('share.history',{},ctx))['items'];assert len(rows)==1
        assert rows[0]['result']['anonymous'] and rows[0]['status']=='completed'
        # A repeated invocation with the same receipt reuses the same publication.
        again=replace(ctx,trace_id=run.id,invocation_id='fixture-repeat')
        await runtime.app_capability_router.invoke('share.publish',args,again)
        assert cli.uploads==1 and len(runtime.share_works.store.recent(ctx.actor_user_id))==1
        # Changing reviewed arguments cannot turn an old receipt into a new effect.
        with pytest.raises(Exception):await runtime.app_capability_router.invoke('share.publish',{**args,'title':'Unreviewed'},again)
        assert cli.uploads==1
        task=runtime.system_tasks.get(ctx.actor_user_id,rows[0]['task_id']);assert task['progress']['done']==1
        await runtime.app_capability_router.invoke('share.verify',{'request_id':rows[0]['request_id']},ctx)
        cancelled=await runtime.app_capability_router.invoke('share.cancel',{'request_id':rows[0]['request_id']},ctx)
        assert cancelled['uploaded_files_may_remain'] and cli.uploads==1
    finally:await runtime.stop_background_tasks()

@pytest.mark.parametrize('change',['cancelled','version','arguments','session'])
def test_publish_receipt_cancel_version_edit_and_foreign_session_block(monkeypatch,change):
    from ai2apps.share_works.aaat import consent
    provider=MINI+'.publish';args={'snapshot_id':'a'*32}
    good=NS(id='old',request={'control':'parameter_form'},ui_hints={'provider':provider,'provider_version':'0.1.1'},status=NS(value='submitted'),response={'status':'completed','result':{'capability':'share.publish','configure_only':True,'user_confirmed':True,'arguments':args}})
    import copy
    latest=copy.deepcopy(good);latest.id='new'
    if change=='cancelled':latest.response={'status':'cancelled','result':{}}
    if change=='version':latest.ui_hints['provider_version']='old'
    if change=='arguments':latest.response['result']['arguments']={'snapshot_id':'b'*32}
    agents=NS(get_run=lambda rid:NS(id=rid,session_id='foreign' if change=='session' else 'session'),list_interactions=lambda rid:[good,latest])
    runtime=NS(database=None,agents=agents,app_capability_router=NS(providers={provider:NS(version='0.1.1',capability='share.publish')}))
    monkeypatch.setattr('ai2apps.agents.form_continuation.selected_form',lambda *a:NS(key=provider,provider_version='0.1.1'))
    with pytest.raises(ToolProviderError):consent(runtime,args,NS(invocation_id='durable',trace_id='run',session_id='session'),provider)

@pytest.mark.asyncio
async def test_cancel_queued_share_keeps_snapshot_and_never_uploads(runtime,tmp_path):
    cli=setup_cli(runtime);ctx=context(runtime)
    path=tmp_path/'cancel.html';path.write_text('<h1>Cancel before upload</h1>')
    asset=runtime.workspace.import_artifact(ctx.session_id,path)
    prepared=await runtime.app_capability_router.invoke('share.prepare',{'destination':'hf','repo':'fixture/site','artifact_id':asset.id},ctx)
    row=runtime.share_works.publish(ctx.actor_user_id,prepared['snapshot']['id'],'fixture_cancel_12345',True)
    result=await runtime.app_capability_router.invoke('share.cancel',{'request_id':row['request_id']},ctx)
    assert result['status']=='cancelling' and not result['uploaded_files_may_remain']
    await runtime.system_tasks.startup()
    try:
        terminal=await runtime.system_tasks.follow(ctx.actor_user_id,row['task_id'],ctx,app_id=HOST,timeout=5)
        assert terminal['status']=='cancelled'
    finally:await runtime.system_tasks.shutdown()
    assert cli.uploads==0 and runtime.share_works.snapshot(ctx.actor_user_id,prepared['snapshot']['id'])
