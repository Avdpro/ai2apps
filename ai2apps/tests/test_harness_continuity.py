"""Real SQLite, process, artifact and PDF tests; model capability is a fixture."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import io
import shutil

import pytest
from PIL import Image
from ai2apps.processes import TestSandboxAdapter as SandboxFixture
from ai2apps.processes.continuity import Continuity
from ai2apps.services.aaat import AgentResultPolicy
from ai2apps.services.capability_routing import CapabilityProvider
from ai2apps.agents.image_inputs import project_artifact_images
from test_harness_file_utilities import setup, artifact
from test_app_chat_durable import bind_identity
from test_app_interactions import runtime


def plain_context(runtime,c):
    from ai2apps.chat.repository import ChatRepository
    sid=ChatRepository(runtime.database,runtime.events).create_thread(title='Harness fixture')[0].session.id
    run=runtime.agents.create_run(session_id=sid,agent_key='ai2apps.app-chat-agent',input={'model':'fixture'})[0]
    return replace(c,session_id=sid,trace_id=run.id)


@pytest.mark.asyncio
async def test_harness_checkpoint_survives_recreation_and_refuses_stale_foreign_or_changed_outputs(runtime,tmp_path):
    _,c,_ = setup(runtime,tmp_path)
    owner = runtime.harness_continuity
    a = artifact(runtime,c,tmp_path)
    assert owner.checkpoint({'expected_revision':0,'notes':'data, not authority','remaining':['save copy'],'artifact_ids':[a.id]},c)['revision']==1
    fresh = Continuity(runtime)
    result = fresh.resume({},c)
    assert result['revision']==1 and result['artifacts'][0]['verified']
    with pytest.raises(ValueError,match='changed'): fresh.checkpoint({'expected_revision':0},c)
    with pytest.raises(Exception): fresh.resume({},replace(c,session_id='foreign'))
    with pytest.raises(Exception): fresh.resume({},replace(c,trace_id='run_foreign'))
    runtime.workspace.artifact_path(a).write_bytes(b'tampered')
    assert fresh.verify({'artifact_ids':[a.id]},c)['status']=='partial'
    assert fresh.resume({},c)['artifacts'][0]['verified'] is False


@pytest.mark.asyncio
async def test_harness_preflight_arbitrary_providers_never_dispatches_or_grants(runtime,tmp_path):
    _,c,_ = setup(runtime,tmp_path)
    c=plain_context(runtime,c)
    observed=[]
    async def describe(principal,model=None):
        observed.append(model)
        return {'effective_schema':{'type':'object'},'configuration_required':model is None}
    for name in ('arbitrary.alpha','independent.beta'):
        handler = AsyncMock(side_effect=AssertionError('No execution during preflight'))
        runtime.app_capability_router.register(CapabilityProvider(name,name,'ai2apps.knowledge',handler,version='17',describe=describe))
    result = await runtime.harness_continuity.preflight({'provider_ids':['arbitrary.alpha','independent.beta','missing'],
        'values':{'arbitrary.alpha':{'model':'selected-fixture-model'}}},c)
    assert [x['status'] for x in result['items']]==['registered','registered','unavailable']
    assert result['authorization']=='not_granted'
    assert observed==['selected-fixture-model',None]
    assert result['items'][0]['contract']['configuration_required'] is False
    assert result['items'][1]['contract']['configuration_required'] is True
    for name in ('arbitrary.alpha','independent.beta'): runtime.app_capability_router.providers[name].handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_harness_batch_is_bounded_independent_ordered_and_blocks_all_writes_before_dispatch(runtime,tmp_path):
    _,c,_ = setup(runtime,tmp_path)
    c=plain_context(runtime,c)
    owner=runtime.harness_continuity
    active=0; peak=0; calls=[]
    async def read(args,context):
        nonlocal active,peak
        active+=1;peak=max(peak,active);calls.append(args['path'])
        try:
            await asyncio.sleep(.01)
            if args['path']=='bad': raise ValueError('private detail')
            return {'path':args['path']}
        finally:active-=1
    owner.read_handlers['workspace.stat']=read
    requests=[{'capability':'workspace.stat','arguments':{'path':str(i)}} for i in range(7)]
    result=await owner.read_batch({'requests':requests},c)
    assert peak==3 and [x['index'] for x in result['items']]==list(range(7))
    assert result['status']=='completed'
    assert (await owner.read_batch({'requests':[{'capability':'workspace.stat','arguments':{'path':'bad'}}]},c))['status']=='partial'
    calls.clear()
    with pytest.raises(ValueError):await owner.read_batch({'requests':requests[:1]+[{'capability':'workspace.write','arguments':{}}]},c)
    assert not calls
    with pytest.raises(ValueError):await owner.read_batch({'requests':requests*2},c)


@pytest.mark.asyncio
async def test_harness_jobs_pty_input_resize_exit_and_scope_use_existing_process_lifecycle(runtime,tmp_path):
    if not shutil.which('sh'):pytest.skip('sh unavailable')
    _,c,_=setup(runtime,tmp_path);runtime.processes.sandbox=SandboxFixture()
    proc=await runtime.processes.start(session_id=c.session_id,run_id=c.trace_id,caller_id='fixture',
        argv=[shutil.which('sh'),'-c','test -t 0 && echo PTY_READY; read line; echo "received:$line"'],pty=True)
    try:
        assert runtime.harness_continuity.jobs({},c)['items'][0]['id']==proc.id
        assert runtime.harness_continuity.jobs({},replace(c,trace_id=runtime.agents.create_run(session_id=c.session_id,agent_key='ai2apps.app-chat-agent',input={})[0].id))['items']==[]
        runtime.processes.resize(proc.id,session_id=c.session_id,run_id=c.trace_id,cols=80,rows=24)
        with pytest.raises(Exception):runtime.processes.resize(proc.id,session_id=c.session_id,run_id='run_foreign',cols=80,rows=24)
        with pytest.raises(ValueError):runtime.processes.resize(proc.id,session_id=c.session_id,run_id=c.trace_id,cols=0,rows=24)
        await runtime.processes.write_stdin(proc.id,'hello\n',session_id=c.session_id,run_id=c.trace_id)
        done=await runtime.processes.wait(proc.id,session_id=c.session_id,run_id=c.trace_id,timeout_ms=3000)
        assert done.exit_code==0
        logs=runtime.processes.logs(proc.id,session_id=c.session_id,run_id=c.trace_id)
        text=''.join(x.content for x in logs)
        assert 'PTY_READY' in text and 'received:hello' in text
    finally:await runtime.processes.cancel(proc.id,session_id=c.session_id,run_id=c.trace_id)


@pytest.mark.asyncio
async def test_harness_interrupt_and_wait_timeout_do_not_replay(runtime,tmp_path):
    _,c,_=setup(runtime,tmp_path);runtime.processes.sandbox=SandboxFixture()
    proc=await runtime.processes.start(session_id=c.session_id,run_id=c.trace_id,caller_id='fixture',argv=[shutil.which('sleep'),'20'])
    try:
        with pytest.raises(Exception):await runtime.processes.wait(proc.id,session_id=c.session_id,run_id=c.trace_id,timeout_ms=10)
        assert runtime.processes.status(proc.id,session_id=c.session_id,run_id=c.trace_id).status.value=='running'
        provider=runtime.app_capability_router.providers['ai2apps.harness.process.wait']
        result=await provider.handler({'process_id':proc.id,'timeout_ms':10},c)
        assert result['status']=='running' and result['wait_timed_out'] is True
        with pytest.raises(Exception):runtime.processes.interrupt(proc.id,session_id=c.session_id,run_id='run_foreign')
        runtime.processes.interrupt(proc.id,session_id=c.session_id,run_id=c.trace_id)
        assert (await runtime.processes.wait(proc.id,session_id=c.session_id,run_id=c.trace_id,timeout_ms=3000)).exit_code==-2
        assert len(runtime.harness_continuity.jobs({},c)['items'])==1
    finally:await runtime.processes.cancel(proc.id,session_id=c.session_id,run_id=c.trace_id)


@pytest.mark.asyncio
async def test_harness_pdf_pages_are_real_bounded_images_and_inspection_is_next_turn_not_hidden_call(runtime,tmp_path,monkeypatch):
    _,c,_=setup(runtime,tmp_path)
    create=runtime.app_capability_router.providers['ai2apps.harness.document.create_pdf']
    result=await create.handler({'content':'# Visual report\n\nActual PDF page.', 'output_path':'out.pdf'},c)
    rendered=await asyncio.to_thread(runtime.harness_continuity.render,{'artifact_id':result['artifact']['id'],'pages':[1]},c)
    assert rendered['status']=='completed'
    identifier=rendered['artifacts'][0]['artifact_id']
    a=runtime.workspace.get_artifact(c.session_id,identifier)
    with Image.open(runtime.workspace.artifact_path(a)) as image:assert max(image.size)<=2048
    from ai2apps import model_vision
    monkeypatch.setattr(model_vision,'resolve_vision',AsyncMock(return_value={'status':'supported'}))
    inspected=await runtime.harness_continuity.image({'artifact_id':identifier},c)
    content=project_artifact_images(runtime.workspace,c.session_id,inspected['visual_artifact_ids'])
    assert content[1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    with pytest.raises(Exception):project_artifact_images(runtime.workspace,'foreign',inspected['visual_artifact_ids'])
    with pytest.raises(ValueError):await runtime.harness_continuity.image({'artifact_id':identifier,'crop':[0,0,99999,10]},c)
    monkeypatch.setattr(model_vision,'resolve_vision',AsyncMock(return_value={'status':'unsupported'}))
    assert (await runtime.harness_continuity.image({'artifact_id':identifier},c))['status']=='configuration_required'


@pytest.mark.parametrize('name',['arbitrary.visual','independent.pages'])
def test_harness_visual_policy_is_scoped_and_completion_retains_failed_verification(runtime,name):
    router=runtime.app_capability_router
    router.register_result_policy(AgentResultPolicy(name,lambda s:None,lambda c,s:(c,None),capabilities=(name,),visual_inputs=lambda s:['owned-fixture']))
    step=NS(kind='tool',tool_name=name,status=NS(value='completed'),error=None,output={})
    assert router.visual_inputs((step,))==['owned-fixture']
    assert router.visual_inputs((replace_step:=NS(**{**vars(step),'tool_name':'other'}),))==[]
    check=router.result_policies['harness-continuity'].completion_check
    step=NS(kind='tool',tool_name='task.verify',status=NS(value='completed'),output={'verified':False})
    assert check((step,),[])['code']=='harness_output_unverified'
    step.output={'verified':True};assert check((step,),[]) is None


def test_harness_environment_exposes_versions_not_secrets(runtime,tmp_path):
    _,c,_=setup(runtime,tmp_path)
    result=runtime.harness_continuity.environment({'packages':['Pillow','does-not-exist-fixture']},c)
    assert result['packages']['Pillow']['installed']
    assert not result['packages']['does-not-exist-fixture']['installed']
    assert 'environ' not in result and 'PATH' not in result

