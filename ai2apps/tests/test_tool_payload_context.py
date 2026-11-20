"""Generic historical payload projection: no execution or owner semantics."""
from copy import deepcopy
from types import SimpleNamespace as NS
import json
import pytest
from ai2apps.agents.result_reference import parameter_preview, result_preview, install_result_reader, RESULT_READER
from ai2apps.agents.models import RunStepStatus
from ai2apps.agents.general import GeneralAgentExecutor, _tool_action_key
from ai2apps.services import ToolProviderError
from test_discover_bilingual import context
from test_app_interactions import runtime


def test_large_values_keep_structure_references_and_deterministic_prefix():
    for owner in ('arbitrary.alpha', 'unrelated.beta'):
        original={'provider':owner,'artifact_id':'exact-id','payload':[{'a/b~c':'中'*9000}],
                  'image':'data:image/png;base64,'+'A'*100000,'count':2}
        snapshot=deepcopy(original)
        projected=parameter_preview(original,step_id='step',reader_alias='read')
        assert original==snapshot
        assert projected['artifact_id']=='exact-id' and projected['count']==2
        assert projected['payload'][0]['a/b~c']['path']=='/payload/0/a~1b~0c'
        assert projected['image']['preview']=='data:image/png;base64'
        assert len(json.dumps(projected, ensure_ascii=False).encode()) < 3500
        assert projected==parameter_preview(original,step_id='step',reader_alias='read')
        assert parameter_preview({'text':'short'},step_id='s',reader_alias='r')=={'text':'short'}
        preview=json.loads(result_preview(NS(output=original,id='step',tool_name=owner),reader_alias='read'))
        assert len(json.dumps(preview, ensure_ascii=False).encode()) < 12000


def test_reader_input_and_nested_output_ranges_are_original_and_scope_checked():
    original={'a/b~c':['data:image/png;base64,'+'A'*20000]}
    source=NS(id='s',kind='tool',tool_name='arbitrary.alpha',status=RunStepStatus.FAILED,input=original,output=original)
    steps=[source]; handlers={}
    agents=NS(get_run=lambda _:NS(id='run',session_id='session-a'),list_steps=lambda _:steps)
    registry=NS(bind_tool=lambda name,**kw:handlers.update({name:kw['handler']}))
    install_result_reader(agents,NS(ensure_tool=lambda **kw:None),registry,service_id='s',provider_key='p')
    args={'step_id':'s','source':'input','path':'/a~1b~0c/0','offset':20,'limit':100}
    read=handlers[RESULT_READER](args,context())
    assert read['content']==original['a/b~c'][0][20:120]
    steps.append(NS(id='read',kind='tool',tool_name=RESULT_READER,status=RunStepStatus.COMPLETED,output=read))
    assert handlers[RESULT_READER](args,context())['already_read']
    with pytest.raises(ToolProviderError):handlers[RESULT_READER]({**args,'source':'output'},context())
    source.status=RunStepStatus.COMPLETED
    assert 'already_read' not in handlers[RESULT_READER]({**args,'source':'output'},context())
    with pytest.raises(ToolProviderError):handlers[RESULT_READER]({**args,'path':'/missing'},context())
    from dataclasses import replace
    with pytest.raises(ToolProviderError):handlers[RESULT_READER](args,replace(context(),session_id='foreign'))


def test_transcript_projects_only_saved_calls_without_mutating_execution():
    args={'body':'x'*20000,'resource':'artifact-exact'}
    call={'id':'c','type':'function','function':{'name':'arbitrary_alpha','arguments':json.dumps(args)}}
    message={'tool_calls':[call],'content':None}
    model=NS(id='m',kind='model',sequence=1,action_key='model',status=RunStepStatus.COMPLETED,
             input={},output={'choices':[{'message':message,'finish_reason':'tool_calls'}]})
    saved=NS(id='s',kind='tool',action_key=_tool_action_key(1,0,'c'),status=RunStepStatus.COMPLETED,
             input=deepcopy(args),output={'artifact_id':'artifact-result'},tool_name='arbitrary.alpha')
    transcript,latest,_,error=GeneralAgentExecutor._transcript([], (model,saved),result_reader_alias='reader')
    assert not error and latest[1]==message
    shortened=json.loads(transcript[0]['tool_calls'][0]['function']['arguments'])
    assert shortened['body']['read_with']['arguments']['source']=='input'
    assert shortened['resource']=='artifact-exact'
    assert json.loads(call['function']['arguments'])==saved.input==args
    later=NS(id='m2',kind='model',sequence=3,action_key='m2',status=RunStepStatus.COMPLETED,
             input={},output={'choices':[{'message':{'content':'next'},'finish_reason':'stop'}]})
    appended,_,_,_=GeneralAgentExecutor._transcript([], (model,saved,later),result_reader_alias='reader')
    assert appended[:len(transcript)]==transcript
    pending,_,_,_=GeneralAgentExecutor._transcript([], (model,),result_reader_alias='reader')
    assert pending[0]['tool_calls']==[call]
    unbounded,_,_,_=GeneralAgentExecutor._transcript([], (model,saved))
    assert unbounded[0]['tool_calls']==[call]
    saved.input={'different':'normalized-input'}
    mismatch,_,_,_=GeneralAgentExecutor._transcript([], (model,saved),result_reader_alias='reader')
    assert mismatch[0]['tool_calls']==[call]


def test_large_mixed_result_does_not_echo_data_url_and_keeps_original_offsets():
    data='data:application/octet-stream;base64,'+'Z'*30000
    output={'a':data,'large_text':'x'*20000,'status':'completed'}
    preview=json.loads(result_preview(NS(id='s',tool_name='unrelated.beta',output=output),reader_alias='reader'))
    assert 'Z'*100 not in json.dumps(preview)
    assert preview['read_with']['arguments']['offset']==0
    assert preview['status']=='completed' and output['a']==data


def test_new_session_opt_in_freezes_views_and_preludes_without_changing_legacy(runtime):
    from ai2apps.agents.context_history import PROFILE, PROFILE_KEY
    from ai2apps.agents.session_memory import SessionMemory
    from ai2apps.storage.repositories import SessionRepository
    from test_aaat_execution_flow import new_run
    old = new_run(runtime, [])
    memory = SessionMemory(runtime.database, runtime.events, lambda item: None)
    old_context = NS(run=old)
    first = {'role':'tool','tool_call_id':'c','content':'original preview'}
    assert memory.freeze_history_message(old_context,'s',first)==first
    changed = {**first,'content':'different'}
    assert memory.freeze_history_message(old_context,'s',changed)==changed
    parent = SessionRepository(runtime.database).get(old.session_id)
    session = SessionRepository(runtime.database, runtime.events).create(
        app_instance_id=parent.app_instance_id,metadata={PROFILE_KEY:PROFILE})
    run,_ = runtime.agents.create_run(session_id=session.id,agent_key='ai2apps.general-agent',
        input={'model':'fixture','prompt':'continue','tools':[]})
    ctx=NS(run=run)
    assert memory.freeze_history_message(ctx,'s',first)==first
    assert memory.freeze_history_message(ctx,'s',changed)==first
    assert memory.freeze_history_message(ctx,'ui',{'role':'user','content':'snapshot'},prelude=True)['content']=='snapshot'
    # A new service instance recovers the immutable first view from SQLite.
    recovered=SessionMemory(runtime.database,runtime.events,lambda item:None)
    assert recovered.freeze_history_message(ctx,'s',changed)==first
    assert recovered.prune_old_results(ctx,None)==0
    with runtime.database.transaction() as connection:
        from ai2apps.agents.context_history import enabled, VIEW
        assert enabled(connection,session.id) and not enabled(connection,old.session_id)
        assert len(recovered._events(connection,session.id,(VIEW,)))==1


@pytest.mark.asyncio
@pytest.mark.parametrize('name',['arbitrary.read','unrelated.inspect'])
async def test_stable_task_history_replays_projection_and_can_read_previous_run(runtime,name):
    from ai2apps.agents.context_history import PROFILE, PROFILE_KEY
    from ai2apps.storage.repositories import SessionRepository
    from test_aaat_execution_flow import register,new_run,response
    from test_app_interactions import wait
    payload='BEGIN-'+'stable synthetic content '*1000+'-END'
    async def execute(args,context):return {'text':payload,'id':'exact-resource'}
    register(runtime,name,execute,invocation_policy=lambda a,c:True)
    from dataclasses import replace
    provider=runtime.app_capability_router.providers[name+'.provider']
    runtime.app_capability_router.providers[provider.id]=replace(provider,
        discovery_context=lambda scope: {'schema':'ai2apps.aaat-discovery-context/v1','resources':[{'revision':len(requests)}]})
    initial=new_run(runtime,[name,RESULT_READER,'agent.read_session_memory'])
    # Fixture setup stands in for trusted creation-time owner opt-in.
    with runtime.database.transaction(write=True) as c:
        c.execute('UPDATE sessions SET metadata_json=? WHERE id=?',(json.dumps({PROFILE_KEY:PROFILE}),initial.session_id))
    requests=[]
    async def model(request):
        requests.append(request)
        if not any(m.get('role')=='tool' and 'tool-result-reference' in m.get('content','') for m in request['messages']):
            # Pin the fixture's registered Provider so the model call matches
            # the durable execution input and can back an exact input reference.
            return response(name,{'query':'Q'*10000,'provider':provider.id})
        return response(text='first complete')
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        runtime.agent_runtime.wake();await wait(runtime,initial.id,'completed')
        step=next(s for s in runtime.agents.list_steps(initial.id) if s.tool_name==name and s.status==RunStepStatus.COMPLETED)
        original_messages=requests[-1]['messages']
        tool_view=next(m for m in original_messages if m.get('role')=='tool' and 'tool-result-reference' in m.get('content',''))
        call_view=next(m for m in reversed(original_messages) if m.get('tool_calls') and m['tool_calls'][0]['function']['name']==__import__('ai2apps.agents.general',fromlist=['_tool_alias'])._tool_alias(name))
        assert 'Q'*9000 not in str(call_view)
        follow=[]
        async def next_model(request):
            follow.append(request)
            current=[m for m in request['messages'] if m.get('role')=='tool' and 'BEGIN-' in m.get('content','') and '"content"' in m.get('content','')]
            if current:return response(text='continued')
            return response(RESULT_READER,{'step_id':step.id,'source':'output','path':'/text','offset':0,'limit':40})
        runtime.agent_runtime.bind_model_provider(next_model)
        run,_=runtime.agents.create_run(session_id=initial.session_id,agent_key='ai2apps.general-agent',
            input={'model':'fixture','prompt':'continue previous exact source','tools':[name,RESULT_READER,'agent.read_session_memory']})
        runtime.agent_runtime.wake();await wait(runtime,run.id,'completed')
        assert tool_view in follow[0]['messages'] and call_view in follow[0]['messages']
        from ai2apps.agents.aaat_context import OBSERVATION_PREFIX
        original_observations=[m for m in original_messages if m.get('role')=='user' and isinstance(m.get('content'),str) and m['content'].startswith(OBSERVATION_PREFIX)]
        assert len(original_observations)>1
        old_data=[m for m in original_messages if m['role']!='system']
        new_data=[m for m in follow[0]['messages'] if m['role']!='system']
        assert new_data[:len(old_data)]==old_data
        for observation in original_observations:
            assert observation in follow[0]['messages']
        reads=[s for s in runtime.agents.list_steps(run.id) if s.tool_name==RESULT_READER and s.status==RunStepStatus.COMPLETED]
        assert reads and reads[0].output['content']==payload[:40]
        current_context=runtime.tools.context_for_session(caller_id='agent-test',session_id=initial.session_id,trace_id=run.id)
        read_input=runtime.service_registry.bound_tool(RESULT_READER).handler({'step_id':step.id,'source':'input','path':'/query','offset':510,'limit':32},current_context)
        assert read_input['content']=='Q'*32
        # Cross-Session references are never readable, even with the stable profile.
        foreign=new_run(runtime,[])
        reader=runtime.service_registry.bound_tool(RESULT_READER).handler
        foreign_context=runtime.tools.context_for_session(caller_id='agent-test',session_id=foreign.session_id,trace_id=foreign.id)
        with pytest.raises(ToolProviderError):
            reader({'step_id':step.id,'source':'input','path':'/query'},foreign_context)
        # No rewrite/deletion of original execution input or result.
        original=next(s for s in runtime.agents.list_steps(initial.id) if s.id==step.id)
        assert original.input['query']=='Q'*10000
        assert original.output['text']==payload
    finally:await runtime.stop_background_tasks()
