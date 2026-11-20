"""Fixed Flash execution: fixture models, real queues, versions and permissions."""
import asyncio
import json
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from starlette.responses import JSONResponse
from ai2apps.messager.flash_plans import Plan,CompileRequest,compile_plan,reviewed,activate,ActivateRequest
from ai2apps.messager.creation import create
from ai2apps.messager.app_access import digest
from ai2apps.todo.service import TodoService
from test_app_interactions import runtime,wait
from test_bot_capability_discovery import setup,P
from test_bot_creation import draft
from test_app_chat_durable import response,bind_identity


def prepared(r,plan,role='Translate input to Japanese',apps=None,initialize=True):
    if initialize:setup(r);r.todo=TodoService(r)
    apps=apps or []
    value={'role':role,'model':'fixture','apps':apps,'plan':Plan.model_validate(plan).model_dump()}
    ref=digest(value)
    with r.database.transaction(write=True) as db:db.execute('INSERT OR IGNORE INTO messager_flash_drafts VALUES(?,?,?)',('local',ref,json.dumps(value)))
    config=reviewed(r,'local',ref,role,'fixture',apps)
    bot=create(r,'local',draft(r,request_id='custom-'+ref[:20],name=plan['name'],duty=role,model_id='fixture',apps=apps,bot_type='flash',definition={'execution_mode':'flash','config':config}))
    sid=r.app_chat.open(P(),'ai2apps.messager.bots',{'bot_id':bot['id']},{})
    return bot,sid,config


TRANSLATE={'name':'日语翻译','usage':'输入要翻译成日文的文本。','steps':[{'kind':'ai','instruction':'Translate the input to Japanese. Return the translation only.'}]}


@pytest.mark.asyncio
async def test_compile_uses_real_invocation_signature_and_principal_context(runtime,monkeypatch):
    from ai2apps.model_invocation import ModelInvocationService
    setup(runtime)
    service=ModelInvocationService(runtime)
    runtime.model_invocations=service
    calls=[]
    async def transport(model_id,operation,payload,*,workload_class,request_id=None,context=None):
        calls.append(context)
        assert model_id=='fixture' and operation=='chat_completions'
        assert context.actor_user_id==P().actor_user_id
        assert context.consumer_app_id=='ai2apps.messager'
        assert context.session_id.startswith(('flash-compile:','flash-review:'))
        return JSONResponse({'choices':[{'message':{'content':json.dumps({'consistent':True,'issues':[]} if payload['messages'][0]['content'].startswith('Review fixed workflow consistency') else TRANSLATE)}}]})
    monkeypatch.setattr(service,'_invoke_json',transport)
    first=await compile_plan(runtime,P(),CompileRequest(role='翻译成日文',model='fixture'))
    second=await compile_plan(runtime,P(),CompileRequest(role='翻译成日文',model='fixture'))
    assert first['review_id']==second['review_id']
    assert calls[0].session_id!=calls[1].session_id


async def submitted(r,bot,sid,text,key='fixed-request'):
    ref=r.messager_dialogue.submit(P(),bot['id'],sid,key,text,'ignored',[])
    for _ in range(100):
        row=r.messager_flash.row(ref)
        if row['agent_run']:return ref,row
        await asyncio.sleep(.02)
    raise AssertionError('No admitted Run')


async def close(r):
    await r.todo.shutdown();await r.system_tasks.shutdown();await r.agent_runtime.stop()


@pytest.mark.asyncio
async def test_translation_is_one_fixed_call_without_history_or_tools(runtime):
    bot,sid,config=prepared(runtime,TRANSLATE)
    calls=[]
    async def model(request):calls.append(request);return response(text='こんにちは')
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        ref,row=await submitted(runtime,bot,sid,'你好')
        result=await wait(runtime,row['agent_run'],'completed')
        runtime.messager_flash.settle(runtime.messager_flash.row(ref))
        assert result.output['content']=='こんにちは'
        assert len(calls)==1 and len(calls[0]['messages'])==2 and 'tools' not in calls[0]
        assert runtime.messager_dialogue.submit(P(),bot['id'],sid,'fixed-request','你好','ignored',[])==ref
        assert len(calls)==1
        assert runtime.app_chat.message_page(P(),sid)['items'][-1]['content']=='こんにちは'
    finally:await close(runtime)


@pytest.mark.asyncio
@pytest.mark.parametrize('normalized,expected',[({'text':'(3**7-1)%7','rejected':False,'answer_mode':'divisible'},'不是，余数为 2'),({'text':'','rejected':True,'question':'请提供数学表达式；我不能绘画。'},'请提供数学表达式')])
async def test_optional_adaptation_revalidates_and_returns_usage(runtime,normalized,expected):
    plan={'name':'算术','usage':'输入数学表达式，也可询问整除关系。','input_kind':'expression','adapt_input':True,'steps':[{'kind':'calculate'}]}
    bot,sid,_=prepared(runtime,plan,'计算表达式，支持自然语言转换。')
    calls=[]
    async def model(request):calls.append(request);return response(text=json.dumps(normalized))
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        _,row=await submitted(runtime,bot,sid,'3的7次方-1是不是7的倍数')
        run=await wait(runtime,row['agent_run'],'completed')
        assert expected in run.output['content'] and len(calls)==1
    finally:await close(runtime)


@pytest.mark.asyncio
async def test_adapter_cannot_turn_text_into_executable_code(runtime):
    plan={'name':'算术','usage':'输入算式','input_kind':'expression','adapt_input':True,'steps':[{'kind':'calculate'}]}
    bot,sid,_=prepared(runtime,plan)
    async def model(request):return response(text=json.dumps({'text':'__import__("os").system("id")','rejected':False}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        _,row=await submitted(runtime,bot,sid,'run this')
        result=await wait(runtime,row['agent_run'],'completed')
        assert result.output['input_rejected'] and result.output['content']=='输入算式'
        assert not any(s.kind=='tool' for s in runtime.agents.list_steps(result.id))
    finally:await close(runtime)


def test_version_review_owner_and_role_guard(runtime):
    bot,sid,config=prepared(runtime,TRANSLATE)
    with pytest.raises(ValueError):reviewed(runtime,'foreign',config['review_id'],'Translate input to Japanese','fixture',[])
    with pytest.raises(ValueError):reviewed(runtime,'local',config['review_id'],'Run arbitrary tools','fixture',[])
    with pytest.raises(ValueError):runtime.messager_bots.update('local',bot['id'],'new','Silently change execution')
    runtime.todo.max_concurrent_runs=0
    ref=runtime.messager_dialogue.submit(P(),bot['id'],sid,'frozen-version','你好','ignored',[])
    replacement={**TRANSLATE,'steps':[{'kind':'ai','instruction':'Translate to French'}]}
    value={'role':'Translate to French','model':'fixture','apps':[],'plan':Plan.model_validate(replacement).model_dump()};revision=digest(value)
    with runtime.database.transaction(write=True) as db:db.execute('INSERT INTO messager_flash_drafts VALUES(?,?,?)',('local',revision,json.dumps(value)))
    updated=activate(runtime,'local',bot['id'],ActivateRequest(role=value['role'],model='fixture',apps=[],review_id=revision,expected_revision=1))
    assert updated['revision']==2
    assert runtime.messager_flash.row(ref)['payload']['definition']['config']==config
    assert runtime.messager_flash.guard(runtime.messager_flash.row(ref))
    with pytest.raises(ValueError):activate(runtime,'local',bot['id'],ActivateRequest(role=value['role'],model='fixture',apps=[],review_id=revision,expected_revision=1))


@pytest.mark.parametrize('binding',['steps.0.content','input.__class__','steps.999.content','/tmp/input'])
def test_forward_unknown_and_executable_bindings_rejected(binding):
    with pytest.raises(ValidationError):Plan.model_validate({'name':'x','usage':'x','steps':[{'kind':'ai','instruction':'x','arguments':{'value':{'$ref':binding}}}]})


@pytest.mark.asyncio
async def test_compile_is_only_a_draft_and_cannot_invent_tools(runtime):
    setup(runtime)
    class Invocations:
        def context_for_actor(self,*a,**k):return None
        async def invoke_foreground_json(self,*a,**k):return JSONResponse({'choices':[{'message':{'content':json.dumps({'consistent':True,'issues':[]} if a[2]['messages'][0]['content'].startswith('Review fixed workflow consistency') else TRANSLATE)}}]})
    runtime.model_invocations=Invocations()
    before=len(runtime.messager_bots.list('local'))
    result=await compile_plan(runtime,P(),CompileRequest(role='翻译成日文',model='fixture'))
    assert result['plan']['steps'][0]['kind']=='ai' and len(runtime.messager_bots.list('local'))==before
    class Bad(Invocations):
        async def invoke_foreground_json(self,*a,**k):return JSONResponse({'choices':[{'message':{'content':json.dumps({'name':'bad','usage':'bad','steps':[{'kind':'aaat','provider':'invented','capability':'shell.execute','version':'1'}]})}}]})
    runtime.model_invocations=Bad()
    with pytest.raises(ValueError):await compile_plan(runtime,P(),CompileRequest(role='do something',model='fixture'))


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id',['fixture.preset','independent.transform'])
async def test_compile_receives_live_contract_and_rejects_invalid_literal(runtime,monkeypatch,provider_id):
    import ai2apps.messager.flash_plans as plans
    setup(runtime)
    schema={'type':'object','properties':{'source':{'type':'string'},'engine':{'type':'string','enum':['exact.engine/v2']}},'required':['source','engine'],'additionalProperties':False}
    async def describe(principal,model=None):return {'effective_schema':schema}
    provider=SimpleNamespace(id=provider_id,version='1',describe=describe)
    monkeypatch.setattr(plans,'selected_catalog',lambda r,a:[{'capability':'fixture.process','provider':provider_id,'version':'1','input_schema':{'type':'object'}}])
    runtime.app_capability_router.providers[provider_id]=provider
    class Invocation:
        async def invoke_foreground_json(self,model,operation,payload,*,context):
            assert 'exact.engine/v2' in payload['messages'][1]['content']
            return JSONResponse({'choices':[{'message':{'content':json.dumps({'name':'Transform','usage':'Upload a file','input_kind':'files','steps':[{'kind':'aaat','capability':'fixture.process','provider':provider_id,'version':'1','arguments':{'source':{'$ref':'input.files.0.artifact_id'},'engine':'invented'}}]})}}]})
    runtime.model_invocations=Invocation()
    with pytest.raises(ValueError,match='engine'):
        await compile_plan(runtime,P(),CompileRequest(role='Transform input',model='fixture'))


def test_flash_failure_is_readable_without_receipt_dump():
    from ai2apps.messager.flash import failure_message
    text=failure_message({'code':'parameter_contract_mismatch','message':'{"parameter_contract":{"very_large":"technical"}}'})
    assert '重新生成' in text and 'very_large' not in text and 'parameter_contract' not in text


@pytest.mark.parametrize('filename,mime',[('reference.png','image/png'),('notes.txt','text/plain')])
def test_flash_input_material_is_preserved_and_projected_in_its_user_message(runtime,tmp_path,filename,mime):
    plan={**TRANSLATE,'input_kind':'files'}
    bot,sid,_=prepared(runtime,plan)
    source=tmp_path/filename;source.write_bytes(b'fixture material')
    attachment=runtime.documents.create_reference(sid,source,filename=filename,media_type=mime)
    runtime.todo.max_concurrent_runs=0
    ref=runtime.messager_flash.submit(P(),bot['id'],sid,'material-request','请查看附件',[attachment.id],None,'zh')
    row=runtime.messager_flash.row(ref)
    files=row['payload']['input']['files']
    assert files[0]['id']==attachment.id
    asset=runtime.workspace.get_artifact(sid,files[0]['artifact_id'])
    assert asset.name==filename
    messages=runtime.app_chat.message_page(P(),sid)['items']
    user=next(m for m in messages if m['role']=='user')
    assert user['artifacts'][0]['artifact_id']==asset.id
    assert user['artifacts'][0]['filename']==filename and user['artifacts'][0]['media_type']==mime
    runtime.messager_flash.append(row,'请查看附件','input','user')
    assert len([m for m in runtime.app_chat.message_page(P(),sid)['items'] if m['role']=='user'])==1

@pytest.mark.asyncio
@pytest.mark.parametrize('name,app',[('fixture.flash_write','ai2apps.gallery'),('different.flash_compose','ai2apps.knowledge')])
async def test_fixed_aaat_sequence_uses_frozen_provider_and_existing_grants(runtime,name,app):
    _,_,calls,provider=setup(runtime,name,app)
    runtime.todo=TodoService(runtime)
    tool=runtime.services.get_tool(name)
    runtime.services.ensure_tool(service_id=tool.service_id,qualified_name=name,display_name=tool.display_name,description=tool.description,
        input_schema={**tool.input_schema,'properties':{**tool.input_schema['properties'],'provider':{'type':'string'}}},output_schema=tool.output_schema,effects=tool.effects,required_capabilities=tool.required_capabilities)
    plan={'name':'Fixed owner task','usage':'输入文本','steps':[{'kind':'aaat','capability':name,'provider':provider.id,'version':provider.version,'arguments':{'prompt':{'$ref':'input.text'}}}]}
    bot,sid,_=prepared(runtime,plan,'固定提交输入到已选应用',apps=[{'app_id':app,'enabled':True}],initialize=False)
    async def forbidden(request):raise AssertionError('Fixed AaAT workflow must not replan')
    runtime.agent_runtime.bind_model_provider(forbidden);await runtime.agent_runtime.start()
    try:
        _,row=await submitted(runtime,bot,sid,'hello')
        run=await wait(runtime,row['agent_run'],'completed')
        assert calls==[({'prompt':'hello'},sid)]
        assert [s.tool_name for s in runtime.agents.list_steps(run.id) if s.kind=='tool']==[name]
    finally:await close(runtime)


@pytest.mark.asyncio
@pytest.mark.parametrize('name,app',[('fixture.repair','ai2apps.gallery'),('independent.repair','ai2apps.knowledge')])
async def test_flash_repairs_effect_free_preset_once_and_versions_future_submissions(runtime,name,app):
    from dataclasses import replace
    _,_,calls,provider=setup(runtime,name,app)
    runtime.todo=TodoService(runtime)
    tool=runtime.services.get_tool(name)
    runtime.services.ensure_tool(service_id=tool.service_id,qualified_name=name,display_name=tool.display_name,description=tool.description,
        input_schema={'type':'object','properties':{'prompt':{'type':'string'},'engine':{'type':'string'},'provider':{'type':'string'}},'required':['prompt','engine'],'additionalProperties':False},output_schema=tool.output_schema,effects=tool.effects,required_capabilities=tool.required_capabilities)
    schema={'type':'object','properties':{'prompt':{'type':'string'},'engine':{'type':'string','enum':['exact/v2']}},'required':['prompt','engine'],'additionalProperties':False}
    async def describe(principal,model=None):return {'effective_schema':schema}
    runtime.app_capability_router.providers[provider.id]=replace(provider,describe=describe)
    plan={'name':'Repair fixture','usage':'Transform input with the selected engine','steps':[{'kind':'aaat','capability':name,'provider':provider.id,'version':provider.version,'arguments':{'prompt':{'$ref':'input.text'},'engine':'obsolete'}}]}
    bot,sid,config=prepared(runtime,plan,apps=[{'app_id':app,'enabled':True}],initialize=False)
    models=[]
    async def model(request):models.append(request);return response(text=json.dumps({'engine':'exact/v2'}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        _,row=await submitted(runtime,bot,sid,'hello')
        run=await wait(runtime,row['agent_run'],'completed')
        assert len(models)==1 and len(calls)==1
        assert calls[0][0]=={'prompt':'hello','engine':'exact/v2'}
        assert run.output['workflow_repairs']==[0]
        current=runtime.messager_bots.definition('local',bot['id'])
        assert current['revision']==2 and current['config']['plan']['steps'][0]['arguments']=={'prompt':{'$ref':'input.text'},'engine':'exact/v2'}
        assert row['payload']['definition']['config']==config
        _,next_row=await submitted(runtime,bot,sid,'next','second')
        await wait(runtime,next_row['agent_run'],'completed')
        assert len(models)==1 and len(calls)==2
    finally:await close(runtime)


def test_flash_repair_rejects_uncertain_effects_bindings_and_changes_outside_rejected_field():
    from ai2apps.messager.flash_plans import Step,repair_contract,repaired_arguments
    step=Step(kind='aaat',capability='arbitrary',provider='arbitrary.owner',version='1',arguments={'engine':'old','source':{'$ref':'input.files.0.artifact_id'}})
    contract={'provider':step.provider,'provider_version':'1','schema':{'properties':{'engine':{'enum':['new']}}}}
    receipt={'code':'parameter_contract_mismatch','submitted':False,'side_effects':False,'parameter_contract':contract,'errors':[{'validator':'enum','path':['engine']}]}
    assert repair_contract(receipt,step)
    assert repair_contract({**receipt,'side_effects':True},step) is None
    assert repair_contract({**receipt,'submitted':True},step) is None
    assert repair_contract({**receipt,'errors':[{'validator':'enum','path':['source']}]},step) is None
    with pytest.raises(ValueError):repaired_arguments('{"engine":"new","source":"invented"}',step,contract,['engine'])


def conversation_body(sid,text,request_id='conversation-request',**extra):
    from ai2apps.api.messager import BotDialogueTurn
    return BotDialogueTurn(session_id=sid,request_id=request_id,text=text,model='fixture',**extra)


@pytest.mark.asyncio
async def test_flash_conversation_valid_text_is_classified_before_execution(runtime):
    from ai2apps.messager.flash_conversation import submit
    bot,sid,_=prepared(runtime,TRANSLATE)
    runtime.todo.max_concurrent_runs=0
    class Invocation:
        async def invoke_foreground_json(self,*a,**kw):return JSONResponse({'choices':[{'message':{'content':json.dumps({'intent':'execute'})}}]})
    runtime.model_invocations=Invocation()
    result=await submit(runtime,P(),bot['id'],conversation_body(sid,'你好'))
    assert result['kind']=='execution' and result['run_id']


@pytest.mark.asyncio
async def test_flash_conversation_edits_are_reviewed_idempotent_and_not_executed(runtime):
    from ai2apps.messager.flash_conversation import submit
    plan=TRANSLATE
    bot,sid,config=prepared(runtime,plan,'Translate uploaded file content')
    calls=[]
    updated={**plan,'usage':'上传文件后翻译为日文并用简短标题标注','steps':[{'kind':'ai','instruction':'Translate file content to Japanese and add a short heading.'}]}
    class Invocation:
        async def invoke_foreground_json(self,model,operation,payload,**kw):
            calls.append(payload)
            system=payload['messages'][0]['content']
            value=({'intent':'edit','role':'Translate uploaded file content to Japanese with a short heading'} if system.startswith('Classify') else
                   {'consistent':True,'issues':[]} if system.startswith('Review fixed') else updated)
            return JSONResponse({'choices':[{'message':{'content':json.dumps(value)}}]})
    runtime.model_invocations=Invocation()
    body=conversation_body(sid,'以后翻译时加一个简短标题')
    result=await submit(runtime,P(),bot['id'],body)
    assert result['kind']=='workflow_review' and len(calls)==3
    assert await submit(runtime,P(),bot['id'],body)==result and len(calls)==3
    assert runtime.messager_bots.definition('local',bot['id'])['config']==config
    with runtime.database.transaction() as db:assert db.execute('SELECT count(*) FROM messager_flash_submissions WHERE bot_id=?',(bot['id'],)).fetchone()[0]==0
    d=result['draft']
    activate(runtime,'local',bot['id'],ActivateRequest(role=d['role'],model=d['model'],apps=d['apps'],review_id=d['review_id'],expected_revision=result['expected_revision'],session_id=sid))
    assert runtime.messager_bots.definition('local',bot['id'])['config']['plan']['steps'][0]['instruction']==updated['steps'][0]['instruction']
    assert any('工作流已更新' in m['content'] for m in runtime.app_chat.message_page(P(),sid)['items'])


@pytest.mark.asyncio
@pytest.mark.parametrize('broken_phase,first_response,recovers,expected_reason',[
    ('conversation', (None,'stop'),True,'empty'),
    ('compile', ('{"name":','length'),True,'length'),
    ('review', ('{}','stop'),True,'invalid'),
    ('review', ('not JSON','stop'),False,'invalid'),
    ('compile', (None,'content_filter'),False,'unavailable'),
])
async def test_flash_edit_recovers_only_failed_analysis_stage(
    runtime,caplog,broken_phase,first_response,recovers,expected_reason,
):
    from ai2apps.messager.flash_conversation import submit
    bot,sid,config=prepared(runtime,TRANSLATE)
    draft={**TRANSLATE,'steps':[{'kind':'ai','instruction':'Translate to Japanese with a heading.'}]}
    calls=[]
    class Invocation:
        async def invoke_foreground_json(self,model,operation,payload,*,context):
            phase=context.session_id.split(':')[0].removeprefix('flash-')
            previous=sum(p==phase for p,_ in calls)
            calls.append((phase,payload))
            assert 'tools' not in payload
            good={
                'conversation':{'intent':'edit','role':'Translate input to Japanese with a heading'},
                'compile':draft,
                'review':{'consistent':True,'issues':[]},
            }
            content,finish=(first_response if phase==broken_phase and (not previous or not recovers)
                            else (json.dumps(good[phase]),'stop'))
            return JSONResponse({'choices':[{'finish_reason':finish,'message':{'content':content}}]})
    runtime.model_invocations=Invocation()
    body=conversation_body(sid,'以后翻译时加一个标题')
    result=await submit(runtime,P(),bot['id'],body)
    assert result['kind']==('workflow_review' if recovers else 'help')
    if not recovers:
        assert ('检查工作流草案' if broken_phase=='review' else '生成工作流草案') in result['message']
        assert '当前工作流未改变' in result['message']
    assert f'phase={broken_phase} attempt=1 reason={expected_reason}' in caplog.text
    phases=['conversation','compile','review']
    index=phases.index(broken_phase)
    expected=phases[:index]+[broken_phase]*(1 if expected_reason=='unavailable' else 2)
    if recovers:expected+=phases[index+1:]
    assert [phase for phase,_ in calls]==expected
    if expected_reason=='length':
        assert calls[index+1][1]['max_tokens']==2*calls[index][1]['max_tokens']
        assert calls[index+1][1]['messages'][1]==calls[index][1]['messages'][1]
    assert await submit(runtime,P(),bot['id'],body)==result and len(calls)==len(expected)
    assert runtime.messager_bots.definition('local',bot['id'])['config']==config
    with runtime.database.transaction() as db:
        assert db.execute('SELECT count(*) FROM messager_flash_submissions').fetchone()[0]==0


@pytest.mark.asyncio
async def test_flash_conversation_rejected_input_explains_usage_without_task(runtime):
    from ai2apps.messager.flash_conversation import submit
    bot,sid,_=prepared(runtime,{**TRANSLATE,'input_kind':'files','usage':'请上传文件'})
    class Invocation:
        async def invoke_foreground_json(self,*a,**kw):return JSONResponse({'choices':[{'message':{'content':json.dumps({'intent':'reject','message':'需要附件才能处理，请先上传文件。'})}}]})
    runtime.model_invocations=Invocation()
    result=await submit(runtime,P(),bot['id'],conversation_body(sid,'这句可以处理么'))
    assert result['kind']=='help' and '上传文件' in result['message']
    assert runtime.app_chat.message_page(P(),sid)['items'][-1]['content']==result['message']


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id',['fixture.archive','independent.archive'])
async def test_consistency_review_rejects_missing_promised_effect(runtime,monkeypatch,provider_id):
    import ai2apps.messager.flash_plans as plans
    setup(runtime)
    monkeypatch.setattr(plans,'selected_catalog',lambda r,a:[{'provider':provider_id,'capability':'arbitrary.store','version':'1','description':'Persist supplied material','input_schema':{'type':'object'}}])
    class Invocation:
        async def invoke_foreground_json(self,model,operation,payload,**kw):
            value={'consistent':False,'issues':['说明承诺保存产物，但流程只有文本转换，没有持久化步骤']} if payload['messages'][0]['content'].startswith('Review fixed') else TRANSLATE
            return JSONResponse({'choices':[{'message':{'content':json.dumps(value)}}]})
    runtime.model_invocations=Invocation()
    with pytest.raises(ValueError,match='持久化步骤'):
        await compile_plan(runtime,P(),CompileRequest(role='Translate and persist the result',model='fixture'))


@pytest.mark.asyncio
async def test_flash_conversation_disambiguates_valid_translation_and_blocks_foreign_session(runtime):
    from ai2apps.messager.flash_conversation import submit
    bot,sid,_=prepared(runtime,TRANSLATE)
    class Invocation:
        async def invoke_foreground_json(self,*a,**kw):return JSONResponse({'choices':[{'message':{'content':json.dumps({'intent':'help','message':'请说明要修改的要求。'})}}]})
    runtime.model_invocations=Invocation()
    result=await submit(runtime,P(),bot['id'],conversation_body(sid,'修改翻译要求'))
    assert result['kind']=='help'
    other,foreign,_=prepared(runtime,TRANSLATE,role='Other translation Bot',initialize=False)
    with pytest.raises(PermissionError):await submit(runtime,P(),bot['id'],conversation_body(foreign,'修改要求'))


@pytest.mark.asyncio
async def test_compile_resolves_selected_model_instead_of_default_contract(runtime,monkeypatch):
    import ai2apps.messager.flash_plans as plans
    setup(runtime)
    calls=[]
    async def describe(principal,model=None):
        calls.append(model)
        return {'effective_schema':{'type':'object','properties':{
            'model':{'type':'string','const':model or 'default'},
            'size':{'type':'string','enum':['auto'] if model=='selected' else ['1024x1024']}},
            'required':['model','size'],'additionalProperties':False}}
    provider=SimpleNamespace(describe=describe,id='fixture.parameterized',version='1')
    runtime.app_capability_router.providers[provider.id]=provider
    monkeypatch.setattr(plans,'selected_catalog',lambda r,a:[{'provider':provider.id,'capability':'fixture.transform','version':'1','input_schema':{'type':'object'}}])
    plan={'name':'Fixture','usage':'Transform using selected model','input_kind':'text',
          'steps':[{'kind':'aaat','capability':'fixture.transform','provider':provider.id,'version':'1','arguments':{'model':'selected','size':'auto'}}]}
    class Invocation:
        async def invoke_foreground_json(self,model,operation,payload,**kw):
            value={'consistent':True,'issues':[]} if payload['messages'][0]['content'].startswith('Review fixed') else plan
            return JSONResponse({'choices':[{'message':{'content':json.dumps(value)}}]})
    runtime.model_invocations=Invocation()
    result=await compile_plan(runtime,P(),CompileRequest(role='Transform using selected model',model='fixture'))
    assert result['plan']['steps'][0]['arguments']['size']=='auto'
    assert calls==[None,'selected']


@pytest.mark.asyncio
@pytest.mark.parametrize('capability,ambiguous', [('fixture.produce', False), ('independent.render', True)])
async def test_flash_repairs_missing_handoff_without_replaying_completed_producer(runtime, tmp_path, capability, ambiguous):
    from dataclasses import replace

    app = 'ai2apps.knowledge'
    _, _, _, producer = setup(runtime, capability, app)
    runtime.todo = TodoService(runtime)
    source = tmp_path / 'fixture.txt'
    source.write_text('one durable workflow output')
    produced = []

    async def produce(arguments, context):
        artifact = runtime.workspace.import_artifact(context.session_id, source, name='fixture.txt', media_type='text/plain')
        produced.append(artifact.id)
        result = {'output': {'ref': artifact.id}}
        if ambiguous:
            result['alternate'] = {'ref': artifact.id}
        return result

    runtime.app_capability_router.providers[producer.id] = replace(producer, handler=produce)
    tool = runtime.services.get_tool(capability)
    reference = {'type': 'string', 'x-ai2apps-asset': {'storage': 'artifact'}}
    resource = {'type': 'object', 'properties': {'ref': reference}}
    consumer = next(p for p in runtime.messager_bot_app_access.providers() if p.capability == 'gallery.save_material')
    plan = {'name': 'Handoff', 'usage': 'Produce and save a file.', 'steps': [
        {'kind': 'aaat', 'capability': capability, 'provider': producer.id, 'version': producer.version,
         'arguments': {'prompt': {'$ref': 'input.text'}}},
        {'kind': 'aaat', 'capability': consumer.capability, 'provider': consumer.id, 'version': consumer.version,
         'arguments': {'artifact_id': {'$ref': 'steps.0.content'}}},
    ]}
    apps = [{'app_id': target, 'enabled': True} for target in (app, 'ai2apps.gallery')]
    bot, sid, original = prepared(runtime, plan, 'Produce and save a file', apps, initialize=False)
    runtime.services.ensure_tool(service_id=tool.service_id, qualified_name=capability, display_name=tool.display_name,
        description=tool.description, input_schema={**tool.input_schema,
            'properties': {**tool.input_schema['properties'], 'provider': {'type': 'string'}}}, effects=tool.effects,
        output_schema={'type': 'object', 'properties': {'output': resource, 'alternate': resource}})
    with pytest.raises(ValueError, match='Declared artifact outputs'):
        reviewed(runtime, 'local', original['review_id'], 'Produce and save a file', 'fixture', apps)
    await runtime.agent_runtime.start()
    try:
        _, row = await submitted(runtime, bot, sid, 'produce the file')
        run = await wait(runtime, row['agent_run'], 'failed' if ambiguous else 'completed')
        assert len(produced) == 1
        steps = runtime.agents.list_steps(run.id)
        current = runtime.messager_bots.definition('local', bot['id'])
        if ambiguous:
            assert len(steps) == 1
            assert run.error['code'] == 'flash_missing_binding'
            assert 'steps.0.content' in run.error['message']
            assert current['config'] == original
        else:
            assert [step.tool_name for step in steps] == [capability, consumer.capability]
            assert steps[1].input['artifact_id'] == produced[0]
            assert steps[1].output['status'] == 'completed'
            assert current['config']['plan']['steps'][1]['arguments'] == {'artifact_id': {'$ref': 'steps.0.output.ref'}}
            assert row['payload']['definition']['config'] == original
            assert not runtime.agents.list_interactions(run.id)
            _, next_row = await submitted(runtime, bot, sid, 'produce another file', 'next-handoff')
            next_run = await wait(runtime, next_row['agent_run'], 'completed')
            assert not runtime.agents.list_interactions(next_run.id)
            assert next_run.output['workflow_repairs'] == []
            assert len(produced) == 2
            access = runtime.messager_bot_app_access
            catalog = access.catalog('local', bot['id'])
            access.save('local', bot['id'], catalog['revision'], catalog['review_hash'],
                        [{'app_id': app, 'enabled': True}, {'app_id': 'ai2apps.gallery', 'enabled': False}])
            _, revoked_row = await submitted(runtime, bot, sid, 'try without Gallery access', 'revoked-handoff')
            revoked = await wait(runtime, revoked_row['agent_run'], 'failed')
            assert not runtime.agents.list_interactions(revoked.id)
            assert all(step.tool_name != consumer.capability for step in runtime.agents.list_steps(revoked.id))
    finally:
        await close(runtime)
