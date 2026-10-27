import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from jsonschema import ValidationError
from ai2apps.identity import RequestPrincipal
from ai2apps.chat import ChatRepository
from ai2apps.browser.mini_apps import WebAgentMiniAppBroker
from ai2apps.research import search_preparation as prep, search_workflow as workflow
from ai2apps.services import ToolProviderError
from test_app_interactions import runtime, wait

@pytest.fixture
def prepared(runtime,monkeypatch):
    from dataclasses import replace
    original_context=runtime.tools.context_for_session
    monkeypatch.setattr(runtime.tools,'context_for_session',lambda **kwargs:replace(original_context(**kwargs),actor_user_id='local',installation_id='local'))
    actor=RequestPrincipal.legacy_local()
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Shared search')
    declaration=json.loads((Path(__file__).resolve().parents[2]/'packages/ai2apps-search-all/app.yaml').read_text())['mini_apps'][0]
    mini=SimpleNamespace(declaration=declaration,mount={'app_instance_id':'app','app_key':'ai2apps-search-all','effective_digest':'digest','interaction_session_id':thread.session.id})
    plan={'optimized_query':'SQLite WAL checkpoint backup','sources':['google','wikipedia'],'limit':5,'x_sort':'top','xiaohongshu_sort':'general','reason':'Primary documentation'}
    calls=[]
    def submit(self,mounted,principal,**kwargs):
        calls.append(kwargs);return {'id':'plan-task','status':'queued'}
    monkeypatch.setattr(WebAgentMiniAppBroker,'submit_declared',submit)
    monkeypatch.setattr(WebAgentMiniAppBroker,'task_declared',lambda *args:{'id':'plan-task','status':'completed','result':plan})
    monkeypatch.setattr(WebAgentMiniAppBroker,'registered',lambda *args:mini)
    state=prep.begin(runtime,actor,mini,scope='app:app',session_id=thread.session.id,query='SQLite WAL?',request_id='first')
    return actor,thread,mini,state,calls

def values(prepared,**changes):
    state=prepared[3]
    return {'query':state['query'],'mode':'preferred','sources':state['sources'],'limit':5,'profile':'default','preparation_id':state['id'],**changes}

def test_preparation_is_ai_only_confirmation_is_immutable_and_owned(runtime,prepared):
    actor,thread,mini,state,calls=prepared
    assert [c['capability'] for c in calls]==['plan']
    with pytest.raises(ToolProviderError):prep.require_confirmation(runtime,actor,{'confirmation_id':state['id']},session_id=thread.session.id)
    edited=values(prepared,query='SQLite official WAL',sources=['bing','wikipedia'])
    result=prep.confirm(runtime,actor,mini,state['id'],edited,scope='app:app')
    assert result['query']==edited['query'] and result['sources']==edited['sources']
    assert prep.confirm(runtime,actor,mini,state['id'],edited,scope='app:app')==result
    with pytest.raises(ValueError):prep.confirm(runtime,actor,mini,state['id'],values(prepared),scope='app:app')
    for other in [SimpleNamespace(actor_user_id='other',installation_id='local'),SimpleNamespace(actor_user_id='local',installation_id='other')]:
        with pytest.raises(ValueError):prep.owned(runtime,other,state['id'])
    with pytest.raises(ValueError):prep.owned(runtime,actor,state['id'],scope='interaction:foreign')
    with pytest.raises(ToolProviderError):prep.require_confirmation(runtime,actor,{'confirmation_id':state['id'],'query':'changed'},session_id=thread.session.id)
    with pytest.raises(ToolProviderError):prep.require_confirmation(runtime,actor,{'confirmation_id':state['id']},session_id='another-session')
    assert len(calls)==1

@pytest.mark.parametrize('change',[{'sources':[]},{'sources':['unknown']},{'sources':['google','google']},{'query':' '},{'profile':'other'},{'mode':'fast','sources':['bing']}])
def test_invalid_choices_do_not_execute(runtime,prepared,change):
    actor,_,mini,state,calls=prepared
    with pytest.raises((ValueError,ValidationError)):
        prep.confirm(runtime,actor,mini,state['id'],values(prepared,**change),scope='app:app')
    assert [c['capability'] for c in calls]==['plan']

@pytest.mark.parametrize('mode',['preferred','fast'])
@pytest.mark.asyncio
async def test_durable_workflow_reads_bodies_and_cites_only_read_sources(runtime,prepared,monkeypatch,mode):
    actor,thread,mini,state,calls=prepared
    confirmed=prep.confirm(runtime,actor,mini,state['id'],values(prepared,mode=mode,sources=['google']),scope='app:app');executed=[]
    async def search(self,args,context):
        executed.append('search')
        return {'query':args['query'],'results':[{'url':'https://sqlite.org/wal.html','title':'SQLite WAL','browser_task_id':'source-task','search_source':'google'},{'url':'https://sqlite.org/backup.html','title':'Backup','browser_task_id':'source-task','search_source':'google'}]}
    async def read(self,args,context):
        assert args['mode']==mode
        executed.append(args['url'])
        if args['url'].endswith('backup.html'):
            from ai2apps.research.mini_apps import WebMiniAppTaskError
            raise WebMiniAppTaskError({'id':'failed-task','run_id':'failed-run','status':'failed','failure':{'code':'article_extraction_failed','cause':{'fallback_reason':'CSP blocked extraction'}}})
        return {'url':args['url'],'title':'SQLite WAL','text':'Actual original article body.','browser_task_id':'read-task'}
    async def model(request):
        assert 'Actual original article body' in request['messages'][1]['content']
        return {'choices':[{'message':{'content':json.dumps({'overview':'WAL overview','points':[{'text':'Local WAL.','source_ids':['1']}],'limitations':'One source unread.'})}}]}
    monkeypatch.setattr('ai2apps.research.mini_apps.WebMiniAppAdapters.search',search)
    monkeypatch.setattr('ai2apps.research.mini_apps.WebMiniAppAdapters.fetch',read)
    monkeypatch.setattr('ai2apps.research.search_workflow.resolve_task_model',lambda *a:'model')
    runtime.agent_runtime.bind_model_provider(model)
    run=workflow.start(runtime,actor,confirmed['confirmation_id'],session_id=thread.session.id)
    assert workflow.start(runtime,actor,confirmed['confirmation_id'],session_id=thread.session.id).id==run.id
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        done=await wait(runtime,run.id,'completed')
        assert executed==['search','https://sqlite.org/wal.html','https://sqlite.org/backup.html']
        assert len(done.output['articles'])==1 and len(done.output['read_failures'])==1
        assert done.output['read_failures'][0]['failure']['failure']['cause']['fallback_reason']=='CSP blocked extraction'
        assert done.output['read_failures'][0]['failure']['task_id']=='failed-task'
        assert done.output['citations']==[{'id':'1','title':'SQLite WAL','url':'https://sqlite.org/wal.html'}]
        assert '[SQLite WAL](https://sqlite.org/wal.html)' in done.output['markdown']
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_agent_parameter_form_uses_shared_preparation_and_confirmation(runtime,prepared,monkeypatch):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.router import create_ai2apps_router
    import test_parameter_forms
    actor,_,mini,_,calls=prepared
    initial={'query':'SQLite WAL?','mode':'preferred','profile':'default','limit':5}
    monkeypatch.setattr(test_parameter_forms,'ARGS',{'request_id':'search-form','capability':'web.search','provider':'ai2apps.search-all.search','values':initial})
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=test_parameter_forms.setup(runtime);await wait(runtime,run.id,'waiting_input')
        item=runtime.agents.list_interactions(run.id)[0];url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            state=await client.get(url);assert state.status_code==200,state.text
            assert state.json()['search_workflow'] and state.json()['submit_label']=={'zh':'搜索','en':'Search'}
            assert next(f for f in state.json()['descriptor']['fields'] if f['key']=='sources')['type']=='multiselect'
            start=await client.post(url+'/search/prepare',json={'revision':0,'values':initial});assert start.status_code==200,start.text
            search=start.json()
            edited={**initial,'query':'User edited SQLite','sources':['bing'],'preparation_id':search['id'],'preparation_ready':True}
            assert (await client.put(url,json={'revision':0,'values':edited})).status_code==200
            response=await client.post(url+'/submit',json={'revision':1,'values':edited});assert response.status_code==200,response.text
            arguments=response.json()['result']['arguments']
            assert arguments['query']==edited['query'] and arguments['sources']==['bing']
            assert arguments['confirmation_id']==search['id']
            assert all(c['capability']=='plan' for c in calls)
            await wait(runtime,run.id,'completed')
    finally:await runtime.stop_background_tasks()


def test_preparation_and_confirmation_survive_runtime_reconstruction(runtime,prepared):
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.config import PlatformConfig
    actor,thread,mini,state,calls=prepared
    confirmed=prep.confirm(runtime,actor,mini,state['id'],values(prepared),scope='app:app')
    base=runtime.config.paths.base_path
    runtime.stop()
    second=PlatformRuntime(PlatformConfig.from_base_path(base));second.start()
    try:
        row=prep.owned(second,actor,state['id'],scope='app:app',session_id=thread.session.id)
        assert json.loads(row['confirmed_json'])['query']==state['query']
        assert prep.confirm(second,actor,mini,state['id'],values(prepared),scope='app:app')==confirmed
        assert len(calls)==1
    finally:second.stop()

@pytest.mark.asyncio
@pytest.mark.parametrize('answer,mode',[
    ('WAL fact [[cite:S1]]','source_ids'),
    ('WAL fact [wrong](https://invented.example/wal.html)','verified_report_fallback'),
])
async def test_general_agent_waits_for_search_confirmation_then_returns_shared_report(runtime,prepared,monkeypatch,answer,mode):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.router import create_ai2apps_router
    actor,thread,mini,_,calls=prepared
    monkeypatch.setattr(runtime.extension_manager,'_studio_mini_app_definition',lambda *args:({'package_id':'ai2apps-search-all'},mini.declaration))
    monkeypatch.setattr('ai2apps.research.search_workflow.resolve_task_model',lambda *a:'model')
    executed=[]
    async def search(self,args,context):
        executed.append(args['query'])
        return {'query':args['query'],'results':[{'url':'https://sqlite.org/wal.html','title':'SQLite WAL','browser_task_id':'source-task','search_source':'bing'}]}
    async def read(self,args,context):return {'url':args['url'],'title':'SQLite WAL','text':'Read original WAL body.'}
    monkeypatch.setattr('ai2apps.research.mini_apps.WebMiniAppAdapters.search',search)
    monkeypatch.setattr('ai2apps.research.mini_apps.WebMiniAppAdapters.fetch',read)
    async def model(request):
        if 'tools' not in request:
            assert 'Read original WAL body.' in request['messages'][1]['content']
            return {'choices':[{'message':{'content':json.dumps({'overview':'WAL conclusion','points':[{'text':'WAL fact','source_ids':['1']}],'limitations':''})}}]}
        tools=[m for m in request['messages'] if m.get('role')=='tool']
        if tools and json.loads(tools[-1]['content']).get('error',{}).get('code')!='tool_declaration_required':
            body=json.loads(tools[-1]['content'])
            assert 'Read original WAL body.' in json.dumps(body)
            assert any('Final-answer citation contract' in m.get('content','') for m in request['messages'] if m.get('role')=='system')
            return {'choices':[{'message':{'role':'assistant','content':answer},'finish_reason':'stop'}]}
        alias=next(t['function']['name'] for t in request['tools'] if t['function']['name'].startswith('web__search_'))
        return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':'search','type':'function','function':{'name':alias,'arguments':json.dumps({'query':'SQLite WAL?'})}}]},'finish_reason':'tool_calls'}]}
    runtime.agent_runtime.bind_model_provider(model)
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.general-agent',input={'model':'model','prompt':'Research SQLite WAL'})
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await wait(runtime,run.id,'waiting_input');assert executed==[]
        item=next(i for i in runtime.agents.list_interactions(run.id) if i.request.get('control')=='parameter_form')
        url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            state=(await client.get(url)).json();draft={**state['values'],'mode':'preferred','profile':'default','limit':5}
            assert (await client.put(url,json={'revision':0,'values':draft})).status_code==200
            p=await client.post(url+'/search/prepare',json={'revision':1,'values':draft});assert p.status_code==200,p.text
            draft.update(query='Edited SQLite WAL',sources=['bing'],preparation_id=p.json()['id'],preparation_ready=True)
            assert (await client.put(url,json={'revision':1,'values':draft})).status_code==200
            submitted=await client.post(url+'/submit',json={'revision':2,'values':draft});assert submitted.status_code==200,submitted.text
        import asyncio
        for _ in range(800):
            current=runtime.agents.get_run(run.id)
            if current.status.value=='waiting_capability':
                approval=next(i for i in runtime.agents.list_interactions(run.id) if i.status.value=='pending')
                runtime.agents.respond_interaction(run.id,approval.id,response={'decision':'approve','scope':'run'},response_id='approve-search')
            if current.status.value in ('completed','failed'):break
            await asyncio.sleep(.01)
        assert current.status.value=='completed',current.error
        assert executed==['Edited SQLite WAL']
        assert len(runtime.agents.list_children(run.id))==1
        assert 'https://sqlite.org/wal.html' in json.dumps(current.output)
        assert current.output['citation_binding']['mode']==mode
        assert 'invented.example' not in current.output['content']
        from ai2apps.storage.repositories import MessageRepository
        from ai2apps.agents.general import _session_message
        saved=MessageRepository(runtime.database,runtime.events).get(current.output['message_id'],session_id=thread.session.id)
        assert _session_message(saved)['content']==current.output['content']
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_mini_app_endpoints_share_confirmation_and_reject_foreign_app_scope(runtime,prepared,monkeypatch):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.router import create_ai2apps_router
    actor,thread,mini,_,calls=prepared
    monkeypatch.setattr(WebAgentMiniAppBroker,'mounted',lambda *args:mini)
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    url='/v1/platform/studios/ai2apps.ai-browser/mini-app-mounts/mount/web-agent'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        started=await client.post(url+'/search-preparations',json={'query':'SQLite WAL?','request_id':'mini-request'})
        assert started.status_code==200,started.text
        state=started.json()
        assert all(c['capability']=='plan' for c in calls)
        body={'preparation_id':state['id'],'values':{**values(prepared),'preparation_id':state['id'],'query':'User final terms','sources':['bing']}}
        invalid=await client.post(url+'/search-workflows',json={**body,'values':{**body['values'],'sources':['foreign']}})
        assert invalid.status_code==422,invalid.text
        confirmed=await client.post(url+'/search-workflows',json=body);assert confirmed.status_code==200,confirmed.text
        repeated=await client.post(url+'/search-workflows',json=body);assert repeated.status_code==200,repeated.text
        assert repeated.json()['id']==confirmed.json()['id']
        assert all(c['capability']=='plan' for c in calls) # Run is queued; no foreground execution loop.
        mini.mount['app_instance_id']='foreign-app'
        rejected=await client.get(url+'/search-workflows/'+state['id'])
        assert rejected.status_code==422,rejected.text

@pytest.mark.parametrize('point',[
    {'text':'Unsupported claim','source_ids':['999']},
    {'text':'See https://invented.example/ for evidence','source_ids':['1']},
    {'text':'Uncited claim','source_ids':[]},
])
def test_new_workflow_rejects_unknown_generated_or_missing_citations(point):
    from ai2apps.agents import FailAction
    rows=[{'url':'https://sqlite.org/wal.html','title':'WAL'}]
    steps={'search':SimpleNamespace(output={'query':'WAL','results':rows}),
        'read:0':SimpleNamespace(output={'read':True,'title':'WAL','url':rows[0]['url'],'text':'Original article body'}),
        'summary':SimpleNamespace(output={'choices':[{'message':{'content':json.dumps({'overview':'Overview','points':[point],'limitations':''})}}]})}
    steps['summary:repair:1']=steps['summary'];steps['summary:repair:2']=steps['summary']
    context=SimpleNamespace(run=SimpleNamespace(id='run',input={'confirmation_id':'confirmed'}),step=steps.get)
    result=workflow.execute(None,context)
    assert isinstance(result,FailAction) and result.code=='invalid_grounded_summary'

def test_changed_package_after_confirmation_cannot_start_a_search(runtime,prepared):
    actor,thread,mini,state,calls=prepared
    prep.confirm(runtime,actor,mini,state['id'],values(prepared),scope='app:app')
    mini.mount['effective_digest']='changed'
    with pytest.raises(ToolProviderError,match='Package changed'):
        workflow.start(runtime,actor,state['id'],session_id=thread.session.id)
    assert [c['capability'] for c in calls]==['plan']

def test_failed_source_gets_bounded_stable_replacements_from_confirmed_results():
    rows=[{'url':f'https://example.com/{i}','search_source':'bilibili' if i in (2,5,6,7,8,9) else 'google'} for i in range(10)]
    found={'results':rows}
    steps={'read:'+str(i):SimpleNamespace(output={'read':i!=2,'text':'body' if i!=2 else ''}) for i in range(5)}
    assert workflow.readable_results(found,steps.get)==rows[:6]
    steps['read:5']=SimpleNamespace(output={'read':False,'text':''})
    assert workflow.readable_results(found,steps.get)==rows[:7]
    steps['read:6']=SimpleNamespace(output={'read':True,'text':'Actual video description'})
    assert workflow.readable_results(found,steps.get)==rows[:7]
    for i in range(5,10):steps['read:'+str(i)]=SimpleNamespace(output={'read':False,'text':''})
    assert len(workflow.readable_results(found,steps.get))==9
    assert workflow.readable_results(found)==rows[:5]

def test_video_description_does_not_satisfy_subtitle_replacement_coverage():
    rows=[{'url':f'https://example.com/{i}','search_source':'bilibili' if i in (2,5,6) else 'google'} for i in range(7)]
    steps={'read:'+str(i):SimpleNamespace(output={'read':True,'text':'actual text'}) for i in range(5)}
    steps['read:2'].output.update(extraction_method='bilibili-video-content',content_kind='description')
    assert workflow.readable_results({'results':rows},steps.get)==rows[:6]
    steps['read:5']=SimpleNamespace(output={'read':True,'text':'[00:00:01.000] Actual captions',
        'extraction_method':'bilibili-video-content','content_kind':'subtitles','subtitle_cues':[{'start_ms':1000,'end_ms':2000,'text':'Actual captions'}]})
    assert workflow.readable_results({'results':rows},steps.get)==rows[:6]
    steps['read:5'].output.pop('subtitle_cues')
    assert workflow.readable_results({'results':rows},steps.get)==rows[:7]

@pytest.mark.asyncio
async def test_ui_search_stops_before_reading_and_summary_and_chat_are_explicit(runtime,prepared,monkeypatch):
    actor,thread,mini,state,calls=prepared
    confirmed=prep.confirm(runtime,actor,mini,state['id'],values(prepared),scope='app:app');actions=[]
    async def search(self,args,context):
        actions.append('search');return {'query':args['query'],'results':[{'title':'Reference','url':'https://example.com/doc','snippet':'Untrusted text','browser_task_id':'task','search_source':'bing'}]}
    async def read(self,args,context):actions.append('read');return {'title':'Reference','url':args['url'],'text':'Original evidence.'}
    async def model(request):
        actions.append('summary');return {'choices':[{'message':{'content':json.dumps({'overview':'Evidence summary','points':[{'text':'Evidence point','source_ids':['1']}],'limitations':''})}}]}
    monkeypatch.setattr('ai2apps.research.mini_apps.WebMiniAppAdapters.search',search)
    monkeypatch.setattr('ai2apps.research.mini_apps.WebMiniAppAdapters.fetch',read)
    monkeypatch.setattr('ai2apps.research.search_workflow.resolve_task_model',lambda *a:'model')
    runtime.agent_runtime.bind_model_provider(model)
    run=workflow.start(runtime,actor,confirmed['confirmation_id'],session_id=thread.session.id,auto_summary=False)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        done=await wait(runtime,run.id,'completed');assert actions==['search'];assert done.output['results']
        chat=workflow.new_agent_chat(runtime,actor,state['id'],session_id=thread.session.id,request_id='chat-request-one')
        again=workflow.new_agent_chat(runtime,actor,state['id'],session_id=thread.session.id,request_id='chat-request-one')
        assert chat['session_id']==again['session_id'] and chat['session_id']!=thread.session.id
        content=ChatRepository(runtime.database,runtime.events,principal=actor).get_content(chat['session_id'])
        assert content.metadata['agentMode'] is True
        assert len(content.messages)==1 and content.messages[0].role.value=='user'
        assert 'https://example.com/doc' in content.messages[0].content and content.messages[0].metadata['data_trust']=='untrusted'
        assert actions==['search'],'handoff must not invoke an Agent or perform a purchase'
        summary=workflow.start_summary(runtime,actor,state['id'],session_id=thread.session.id)
        assert workflow.start_summary(runtime,actor,state['id'],session_id=thread.session.id).id==summary.id
        report=await wait(runtime,summary.id,'completed');assert actions==['search','read','summary'];assert report.output['summary']['overview']=='Evidence summary'
        with_summary=workflow.new_agent_chat(runtime,actor,state['id'],session_id=thread.session.id,request_id='chat-after-summary')
        summarized_context=ChatRepository(runtime.database,runtime.events,principal=actor).get_content(with_summary['session_id'])
        assert 'Evidence summary' in summarized_context.messages[0].content
        assert actions==['search','read','summary']
        with pytest.raises((ValueError,ToolProviderError)):workflow.new_agent_chat(runtime,actor,state['id'],session_id='foreign',request_id='chat-request-two')
    finally:await runtime.stop_background_tasks()

def test_deepseek_choice_and_confirmation_reuse_shared_aaat_flow(runtime,prepared,monkeypatch):
    actor,thread,mini,state,calls=prepared
    monkeypatch.setattr(runtime,'model_manager',SimpleNamespace(list_cloud=lambda:[{
        'id':'deepseek','enabled':True,'configured':True,'base_url':'https://api.deepseek.com'}]))
    choices=prep.choices(runtime,actor,mini)
    assert 'deepseek' in [c['id'] for c in choices]
    assert prep.view(runtime,actor,mini,state['id'])['fast_source']=='deepseek'
    with pytest.raises(ValueError,match='128'):
        prep.confirm(runtime,actor,mini,state['id'],values(prepared,query='x'*129,sources=['deepseek']),scope='app:app')
    confirmed=prep.confirm(runtime,actor,mini,state['id'],values(prepared,mode='fast',sources=['deepseek']),scope='app:app')
    saved,_=prep.require_confirmation(runtime,actor,confirmed,session_id=thread.session.id)
    assert saved['sources']==['deepseek']
    monkeypatch.setattr(runtime,'privacy_mode',True,raising=False)
    assert 'deepseek' not in [c['id'] for c in prep.choices(runtime,actor,mini)]

def test_new_execution_receipts_preserve_old_confirmation_and_deduplicate(runtime,prepared):
    actor,thread,mini,state,calls=prepared
    old=prep.confirm(runtime,actor,mini,state['id'],values(prepared),scope='app:app')
    child=prep.execution_preparation(runtime,actor,mini,state['id'],'new-click',scope='app:app')
    assert child!=state['id']
    updated=values(prepared,mode='fast',sources=['google'])
    fresh=prep.confirm(runtime,actor,mini,child,updated,scope='app:app')
    assert fresh['confirmation_id']==child
    assert prep.require_confirmation(runtime,actor,old,session_id=thread.session.id)[0]['sources']==old['sources']
    assert prep.execution_preparation(runtime,actor,mini,state['id'],'new-click',scope='app:app')==child
    with pytest.raises(ValueError,match='cannot be changed'):
        prep.confirm(runtime,actor,mini,child,{**updated,'query':'modified retry'},scope='app:app')
    assert len(calls)==1 # Reuses completed planning; no new AI task.
    with pytest.raises(ValueError):prep.execution_preparation(runtime,actor,mini,state['id'],'another',scope='app:foreign')
    with runtime.database.transaction(write=True) as db:
        db.execute('UPDATE search_preparations SET origin_run=? WHERE id=?',('agent-run',state['id']))
    with pytest.raises(ValueError,match='Agent search'):
        prep.execution_preparation(runtime,actor,mini,state['id'],'another',scope='app:app')

@pytest.mark.asyncio
async def test_repeated_search_endpoint_creates_new_run_and_retries_same_run(runtime,prepared,monkeypatch):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.router import create_ai2apps_router
    actor,thread,mini,state,calls=prepared
    monkeypatch.setattr(WebAgentMiniAppBroker,'mounted',lambda *args:mini)
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    url='/v1/platform/studios/ai2apps.ai-browser/mini-app-mounts/mount/web-agent/search-workflows'
    body={'preparation_id':state['id'],'values':values(prepared),'request_id':'click-one'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        first=await client.post(url,json=body);assert first.status_code==200,first.text
        a=first.json()
        retry=await client.post(url,json=body);assert retry.status_code==200,retry.text
        assert retry.json()['id']==a['id']
        assert retry.json()['preparation_id']==a['preparation_id']!=state['id']
        second_body={'preparation_id':a['preparation_id'],'request_id':'click-two','values':values(prepared,mode='fast',sources=['google'])}
        blocked=await client.post(url,json=second_body);assert blocked.status_code==422
        with runtime.database.transaction(write=True) as db:
            db.execute("UPDATE agent_runs SET status='planning' WHERE id=?",(a['id'],))
            db.execute("UPDATE agent_runs SET status='running' WHERE id=?",(a['id'],))
            db.execute("UPDATE agent_runs SET status='completed',output_json='{}' WHERE id=?",(a['id'],))
        second=await client.post(url,json=second_body);assert second.status_code==200,second.text
        assert second.json()['id']!=a['id']
        assert second.json()['preparation_id']!=a['preparation_id']
        original=prep.owned(runtime,actor,a['preparation_id'])
        assert json.loads(original['confirmed_json'])['mode']=='preferred'
    assert len(calls)==1

@pytest.mark.parametrize('bad',[
    {'choices':[{'finish_reason':'length','message':{'content':'','reasoning_content':'budget exhausted'}}]},
    {'choices':[{'message':{'content':'not JSON'}}]},
    {'choices':[{'message':{'content':json.dumps({'overview':'A','points':[{'text':'bad source','source_ids':['999']}],'limitations':''})}}]},
])
def test_summary_repairs_are_bounded_and_keep_evidence(bad,monkeypatch):
    from ai2apps.agents import ModelCallAction,FailAction,CompleteAction
    monkeypatch.setattr(workflow,'resolve_task_model',lambda *a:'model')
    monkeypatch.setattr(workflow,'progress',lambda *a,**k:None)
    steps={'search':SimpleNamespace(output={'query':'WAL','results':[{'url':'https://sqlite.org/wal.html','title':'WAL'}]}),
        'read:0':SimpleNamespace(output={'read':True,'title':'WAL','url':'https://sqlite.org/wal.html','text':'Retained original body'}),
        'summary':SimpleNamespace(output=bad)}
    context=SimpleNamespace(run=SimpleNamespace(id='run',input={'confirmation_id':'receipt'}),step=steps.get)
    saved=steps.pop('summary')
    initial=workflow.execute(None,context)
    assert initial.call_id=='summary' and initial.request['reasoning_effort']=='low'
    steps['summary']=saved
    first=workflow.execute(None,context);assert isinstance(first,ModelCallAction) and first.call_id=='summary:repair:1'
    assert first.request['max_tokens']==10000
    assert first.request['reasoning_effort']=='low'
    assert 'Retained original body' in first.request['messages'][1]['content']
    assert '999' not in first.request['messages'][0]['content']
    steps['summary:repair:1']=SimpleNamespace(output=bad)
    second=workflow.execute(None,context);assert isinstance(second,ModelCallAction) and second.call_id=='summary:repair:2'
    assert second.request['max_tokens']==16000
    assert second.request['reasoning_effort']=='low'
    steps['summary:repair:2']=SimpleNamespace(output=bad)
    assert isinstance(workflow.execute(None,context),FailAction)
    steps['summary:repair:2']=SimpleNamespace(output={'choices':[{'message':{'content':json.dumps({'overview':'WAL','points':[{'text':'Grounded','source_ids':['1']}],'limitations':''})}}]})
    assert isinstance(workflow.execute(None,context),CompleteAction)

@pytest.mark.asyncio
async def test_failed_summary_retry_reuses_read_steps_without_search_or_fetch(runtime,prepared,monkeypatch):
    actor,thread,mini,state,calls=prepared;executed=[];model_calls=[];valid=False
    confirmed=prep.confirm(runtime,actor,mini,state['id'],values(prepared),scope='app:app')
    async def search(self,args,context):
        executed.append('search');return {'query':'WAL','results':[{'url':'https://sqlite.org/wal.html','title':'WAL','search_source':'google'}]}
    async def read(self,args,context):
        executed.append('read');return {'url':args['url'],'title':'WAL','text':'Saved original body'}
    async def model(request):
        model_calls.append(request)
        if not valid:return {'choices':[{'finish_reason':'length','message':{'content':''}}]}
        return {'choices':[{'message':{'content':json.dumps({'overview':'WAL','points':[{'text':'Grounded','source_ids':['1']}],'limitations':''})}}]}
    monkeypatch.setattr('ai2apps.research.mini_apps.WebMiniAppAdapters.search',search)
    monkeypatch.setattr('ai2apps.research.mini_apps.WebMiniAppAdapters.fetch',read)
    monkeypatch.setattr(workflow,'resolve_task_model',lambda *a:'model')
    runtime.agent_runtime.bind_model_provider(model)
    run=workflow.start(runtime,actor,confirmed['confirmation_id'],session_id=thread.session.id)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        failed=await wait(runtime,run.id,'failed');assert failed.error['code']=='invalid_grounded_summary'
        assert len(model_calls)==3 and executed==['search','read']
        valid=True;retry=workflow.start_summary(runtime,actor,confirmed['confirmation_id'],session_id=thread.session.id)
        assert retry.input['reuse_readings'] is True
        done=await wait(runtime,retry.id,'completed')
        assert executed==['search','read'] and len(model_calls)==4
        assert done.output['articles'][0]['text']=='Saved original body'
        assert workflow.start_summary(runtime,actor,confirmed['confirmation_id'],session_id=thread.session.id).id==retry.id
        from dataclasses import replace
        with pytest.raises(ToolProviderError):workflow.cached_read_steps(runtime,replace(retry,session_id='foreign'))
    finally:await runtime.stop_background_tasks()

@pytest.mark.parametrize('reason',['timeout','read_requires_interaction'])
def test_fast_failed_page_is_replaced_from_same_confirmed_pool_without_rereading_successes(reason):
    rows=[{'url':f'https://example.com/{i}','search_source':'deepseek'} for i in range(8)]
    found={'results':rows,'read_limit':3}
    steps={f'read:{i}':SimpleNamespace(output={'read':i!=1,'text':'body' if i!=1 else '', 'reason':reason}) for i in range(3)}
    assert workflow.readable_results(found,steps.get)==rows[:4]
    steps['read:3']=SimpleNamespace(output={'read':True,'text':'replacement original body'})
    assert workflow.readable_results(found,steps.get)==rows[:4]
    assert workflow.readable_results(found)==rows[:3]
