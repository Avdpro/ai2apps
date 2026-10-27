import json
from types import SimpleNamespace as NS
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai2apps.intelligence import article_chat as chat, service
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.api.intelligence_article_chat import install
from ai2apps.system_tasks import SystemTaskService, TaskContext
from ai2apps.storage import PlatformDatabase
from ai2apps.events import EventStore, EventNotificationBus

@pytest.fixture
def env(tmp_path):
    store=IntelligenceStore(tmp_path/'intel');db=PlatformDatabase(tmp_path/'platform.sqlite3');db.initialize()
    runtime=NS(database=db,events=EventStore(db),notifications=EventNotificationBus())
    runtime.intelligence_collector=NS(store=store)
    runtime.system_tasks=SystemTaskService(runtime)
    channel=store.save_channel('owner',{'name':'AI','interests':'models','interval_hours':0})
    article={'id':'article','title':'Model X release','summary':'release','body':'Model X facts','sources':[],
             'channel_id':channel['id'],'updated_at':'2026-10-20T00:00:00+00:00'}
    with store.connect() as conn:
        conn.execute('INSERT INTO articles VALUES(?,?,?,?)',('article','owner',channel['id'],json.dumps(article)))
        conn.execute('INSERT INTO articles VALUES(?,?,?,?)',('other','owner',channel['id'],json.dumps({**article,'id':'other'})))
    principal=NS(actor_user_id='owner')
    def authorize(owner,payload):store.get('channels',owner,payload['channel_id'])
    chat.register(runtime,lambda owner:principal,authorize)
    app=FastAPI();from fastapi import APIRouter,Depends
    router=APIRouter();install(router,lambda:runtime,lambda:store,Depends(lambda:principal));app.include_router(router)
    return store,runtime,principal,article,TestClient(app)


def args(thread,mode='answer',request_id='request-123456789'):
    return {'thread':thread,'mode':mode,'request_id':request_id,'question':'Explain Model X','confirmation_id':None}


def test_thread_isolation_idempotency_reset_and_stale_write(env):
    s,r,p,a,c=env;repo=chat.Repository(s);first=repo.get('owner','article')
    assert first['thread']!=repo.get('owner','other')['thread']
    with pytest.raises(KeyError):repo.get('foreign','article')
    body=args(first['thread']);repo.reserve('owner','article',body)
    assert repo.reserve('owner','article',body)['args']==body
    with pytest.raises(ValueError):repo.reserve('owner','article',{**body,'question':'changed'})
    repo.finish('owner','article',body['request_id'],result={'answer':'Facts [1]','references':[]})
    assert len(repo.get('owner','article')['turns'])==1
    new=repo.reset('owner','article',first['thread']);assert new['turns']==[] and new['thread']!=first['thread']
    with pytest.raises(ValueError):repo.finish('owner','article',body['request_id'],result={'answer':'late'})
    assert repo.get('owner','article')['turns']==[]


def test_routes_return_quick_task_and_reset_only_article(env):
    s,r,p,a,c=env;root='/articles/article/chat';first=c.get(root).json()
    assert c.get('/articles/foreign/chat').status_code==404
    body=args(first['thread'],'suggest')
    one=c.post(root+'/actions',json=body);assert one.status_code==200 and one.json()['status']=='queued'
    assert c.post(root+'/actions',json=body).json()['task_id']==one.json()['task_id']
    assert c.post(root+'/actions',json={**body,'question':'changed'}).status_code==409
    assert c.post(root+'/reset',json={'thread':first['thread']}).status_code==200
    assert c.get(root).json()['turns']==[]
    assert r.system_tasks.get('owner',one.json()['task_id'])['status']=='cancelled'
    assert c.post(root+'/actions',json=body).status_code==409


@pytest.mark.asyncio
async def test_async_answer_is_saved_once_and_uses_only_bound_evidence(env,monkeypatch):
    s,r,p,a,c=env;repo=chat.Repository(s);state=repo.get('owner','article');seen=[]
    async def model(*args,**kwargs):
        data,validate=args[-2:];seen.append(data)
        with pytest.raises(ValueError):validate({'answer':'Invented [99]','evidence_ids':[99]})
        with pytest.raises(ValueError):validate({'answer':'Made up https://bad.example [1]','evidence_ids':[1]})
        return validate({'answer':'Facts [1]','evidence_ids':[1]})
    monkeypatch.setattr(service,'model_json',model)
    body=args(state['thread']);response=c.post('/articles/article/chat/actions',json=body).json()
    task=r.system_tasks.get('owner',response['task_id']);ctx=TaskContext(r.system_tasks,task)
    handler=r.system_tasks.handlers['intelligence.article_chat']
    await handler.execute(ctx);assert (await handler.execute(ctx))['cached']
    assert len(seen)==1 and seen[0]['selected_article_id']=='article' and not seen[0]['external_reading']
    assert len(repo.get('owner','article')['turns'])==1
    assert repo.get('owner','other')['turns']==[]


@pytest.mark.asyncio
async def test_suggestions_are_choices_and_do_not_search(env,monkeypatch):
    s,r,p,a,c=env;repo=chat.Repository(s);state=repo.get('owner','article')
    async def model(*args,**kwargs):
        validate=args[-1]
        with pytest.raises(ValueError):validate({'analysis':'A','questions':['Repeat','Repeat']})
        return validate({'analysis':'Possible discussion angles','questions':['What is Model X?','How strong is the evidence?']})
    monkeypatch.setattr(service,'model_json',model)
    body=args(state['thread'],'followup');response=c.post('/articles/article/chat/actions',json=body).json()
    task=r.system_tasks.get('owner',response['task_id'])
    await r.system_tasks.handlers['intelligence.article_chat'].execute(TaskContext(r.system_tasks,task))
    value=repo.get('owner','article');assert len(value['questions'])==2 and value['turns']==[]


def test_search_confirmation_cannot_cross_thread_or_actor(env,monkeypatch):
    s,r,p,a,c=env;state=c.get('/articles/article/chat').json()
    def deny(*args,**kwargs):raise ValueError('Search preparation scope changed')
    monkeypatch.setattr('ai2apps.research.search_preparation.owned',deny)
    monkeypatch.setattr('ai2apps.system_tasks.sessions.execution_session',lambda *a:'session')
    response=c.post('/articles/article/chat/actions',json={**args(state['thread']),'confirmation_id':'foreign-confirmation'})
    assert response.status_code==409
    assert chat.Repository(s).get('owner','article')['busy'] is None

@pytest.mark.asyncio
async def test_confirmed_search_uses_selected_provider_and_only_read_bodies(env,monkeypatch):
    s,r,p,a,c=env;repo=chat.Repository(s);state=repo.get('owner','article')
    for key in ('installation_id','organization_id','billing_account_id','membership_epoch'):setattr(p,key,None)
    p.installation_id='installation'
    monkeypatch.setattr('ai2apps.system_tasks.sessions.execution_session',lambda *a:'session')
    monkeypatch.setattr('ai2apps.research.search_preparation.owned',lambda *a,**k:{})
    monkeypatch.setattr('ai2apps.research.search_preparation.require_confirmation',lambda *a,**k:({'mode':'fast','limit':3,'sources':['google']},{}))
    used=[]
    async def invoke(capability,arguments,context):
        used.append((capability,arguments,context))
        return {'articles':[{'source_id':'web1','url':'https://example.com/read','title':'Original','read':True,'text':'Original body'},
                            {'source_id':'web2','url':'https://example.com/snippet','title':'Unread','read':False,'text':'Search snippet'}]}
    r.app_capability_router=NS(invoke=invoke)
    async def model(*args,**kwargs):
        evidence=args[-2]['evidence']
        assert any(e['body']=='Original body' for e in evidence)
        assert not any(e['body']=='Search snippet' for e in evidence)
        selected=next(e['evidence_id'] for e in evidence if e['body']=='Original body')
        return args[-1]({'answer':f'External fact [{selected}]','evidence_ids':[selected]})
    monkeypatch.setattr(service,'model_json',model)
    body={**args(state['thread']),'confirmation_id':'confirmed-search'}
    repo.reserve('owner','article',body)
    task=r.system_tasks.submit('owner','ai2apps.intelligence','intelligence.article_chat','Discuss',{'article_id':'article','request_id':body['request_id']})
    await r.system_tasks.handlers['intelligence.article_chat'].execute(TaskContext(r.system_tasks,task))
    assert used[0][0]=='web.search' and used[0][1]=={'provider':'ai2apps.search-all.search','confirmation_id':'confirmed-search','mode':'fast'}
    assert used[0][2].actor_user_id=='owner' and used[0][2].installation_id=='installation'
    assert repo.get('owner','article')['turns'][0]['references'][0]['url']=='https://example.com/read'

@pytest.mark.asyncio
async def test_reset_during_model_call_discards_late_answer(env,monkeypatch):
    import asyncio
    s,r,p,a,c=env;repo=chat.Repository(s);state=repo.get('owner','article')
    entered=asyncio.Event();release=asyncio.Event()
    async def model(*args,**kwargs):
        entered.set();await release.wait()
        return args[-1]({'answer':'Late answer [1]','evidence_ids':[1]})
    monkeypatch.setattr(service,'model_json',model)
    response=c.post('/articles/article/chat/actions',json=args(state['thread'])).json()
    task=r.system_tasks.get('owner',response['task_id'])
    worker=asyncio.create_task(r.system_tasks.handlers['intelligence.article_chat'].execute(TaskContext(r.system_tasks,task)))
    await entered.wait();repo.reset('owner','article',state['thread']);release.set()
    with pytest.raises(ValueError,match='reset'):await worker
    assert repo.get('owner','article')['turns']==[]


def test_retry_cannot_interleave_with_another_active_action(env):
    s,r,p,a,c=env;repo=chat.Repository(s);state=repo.get('owner','article')
    first=args(state['thread']);repo.reserve('owner','article',first);repo.finish('owner','article',first['request_id'],error='failed')
    second={**first,'request_id':'second-request-12345'};repo.reserve('owner','article',second)
    with pytest.raises(ValueError,match='Another'):repo.claim('owner','article',first['request_id'])


def test_explanation_and_research_have_independent_threads_busy_and_reset(env):
    s,r,p,a,c=env;repo=chat.Repository(s)
    simple=c.get('/articles/article/chat').json()
    deep=c.get('/articles/article/chat?purpose=research').json()
    assert simple['purpose']=='explain' and deep['purpose']=='research'
    assert simple['thread']!=deep['thread']
    assert c.get('/articles/article/chat?purpose=invalid').status_code==409
    one=args(simple['thread'],request_id='request-simple-123')
    two=args(deep['thread'],request_id='request-research-123')
    repo.reserve('owner','article',one);repo.reserve('owner','article',two)
    assert repo.claim('owner','article',two['request_id'])['purpose']=='research'
    repo.finish('owner','article',one['request_id'],result={'answer':'Simple','references':[]})
    assert repo.get('owner','article','research')['busy']==two['request_id']
    new=repo.reset('owner','article',deep['thread'])
    assert new['purpose']=='research' and new['turns']==[]
    assert repo.get('owner','article')['turns'][0]['answer']=='Simple'
    assert repo.action('owner','article',one['request_id'])['status']=='completed'
    with pytest.raises(ValueError):repo.finish('owner','article',two['request_id'],result={'answer':'Late'})
    with pytest.raises(KeyError):repo.get('other-owner','article','research')


@pytest.mark.asyncio
async def test_explanation_topics_and_research_prompt_are_distinct(env,monkeypatch):
    s,r,p,a,c=env;seen=[]
    async def model(runtime,frame,principal,channel,prompt,payload,validate,**kwargs):
        seen.append(prompt)
        assert payload['article']['body']=='Model X facts'
        return validate({'analysis':'','questions':['What is Model X?']})
    monkeypatch.setattr(service,'model_json',model)
    repo=chat.Repository(s)
    for purpose in ('explain','research'):
        state=repo.get('owner','article',purpose)
        result=await chat.generate(r,p,s,a,state,args(state['thread'],'suggest'))
        assert result['topic_style']==purpose
    assert 'EXPLICITLY MENTIONED' in seen[0]
    assert 'short, simple explanation request' in seen[0]
    assert 'Do not propose implications' in seen[0]
    assert 'evidence gaps, implications or comparisons' in seen[1]
    assert all('No web access' in prompt for prompt in seen)


def test_research_handoff_is_bounded_data_not_a_run_or_cross_client_thread(env):
    s,r,p,a,c=env;repo=chat.Repository(s)
    simple=repo.get('owner','article');deep=repo.get('owner','article','research')
    body=chat.ResearchHandoff(thread=deep['thread'],request_id='handoff-request-123')
    with pytest.raises(ValueError):chat.research_handoff(r,p,s,'article',body)
    key=args(deep['thread'],'suggest');repo.reserve('owner','article',key)
    repo.finish('owner','article',key['request_id'],result={'analysis':'Review limits','questions':['How does Model X compare?'],'topic_style':'research'})
    result=chat.research_handoff(r,p,s,'article',body);seed=result['chat_seed']
    assert seed['session_metadata']['agentMode'] is True
    assert seed['session_metadata']['starterSuggestions']==['How does Model X compare?']
    assert 'Model X facts' in seed['legacy_messages'][0]['content']
    assert 'not instructions or authorization' in seed['legacy_messages'][0]['content']
    assert seed['legacy_messages'][0]['role']=='user'
    assert chat.research_handoff(r,p,s,'article',body)==result
    from ai2apps.api.chat import ChatThreadCreateRequest
    parsed=ChatThreadCreateRequest.model_validate(seed)
    from ai2apps.chat import ChatRepository, LegacyChatMessageInput
    from ai2apps.identity import RequestPrincipal
    from ai2apps.core import RepositoryError
    from dataclasses import replace
    from ai2apps.identity import MemberRole
    principal=RequestPrincipal(actor_user_id='research-user',installation_id='installation-1',organization_id='household-1',billing_account_id='research-user',role=MemberRole.CORE,membership_epoch=1)
    desktop=ChatRepository(r.database,r.events,principal=principal)
    mobile=ChatRepository(r.database,r.events,principal=replace(principal,client_scope='mobile-agent-fixture'))
    kwargs=dict(title=parsed.title,legacy_thread_id=parsed.legacy_thread_id,metadata=parsed.session_metadata,
        legacy_messages=tuple(LegacyChatMessageInput(role=m.role,content=m.content,metadata=m.metadata) for m in parsed.legacy_messages))
    desktop_args={**kwargs,'legacy_thread_id':'context:'+desktop.ensure_builtin().instance.id+':'+kwargs['legacy_thread_id']}
    mobile_args={**kwargs,'legacy_thread_id':'context:'+mobile.ensure_builtin().instance.id+':'+kwargs['legacy_thread_id']}
    first,created=desktop.create_thread(**desktop_args);again,duplicate=desktop.create_thread(**desktop_args)
    other,_=mobile.create_thread(**mobile_args)
    assert created and not duplicate and first.session.id==again.session.id
    assert other.session.id!=first.session.id
    assert desktop.get_content(first.session.id).metadata['agentMode'] is True
    with pytest.raises(RepositoryError):mobile.get_content(first.session.id)
    assert repo.get('owner','article')['thread']==simple['thread']
    with pytest.raises(ValueError):chat.research_handoff(r,p,s,'article',chat.ResearchHandoff(thread=simple['thread'],request_id=body.request_id))


@pytest.mark.parametrize('mode,limit,sources',[('custom',3,['google']),('preferred',3,['google']),('fast',5,['google']),('fast',3,['google','bing'])])
@pytest.mark.asyncio
async def test_article_search_policy_rechecked_at_submission_and_resume(env,monkeypatch,mode,limit,sources):
    s,r,p,a,c=env;repo=chat.Repository(s);state=repo.get('owner','article')
    monkeypatch.setattr('ai2apps.system_tasks.sessions.execution_session',lambda *a:'session')
    monkeypatch.setattr('ai2apps.research.search_preparation.owned',lambda *a,**k:{})
    monkeypatch.setattr('ai2apps.research.search_preparation.require_confirmation',lambda *a,**k:({'mode':mode,'limit':limit,'sources':sources},{}))
    body={**args(state['thread']),'confirmation_id':'old-receipt'}
    assert c.post('/articles/article/chat/actions',json=body).status_code==409
    assert repo.get('owner','article')['busy'] is None
    # A durable request saved before the upgrade must be rejected too, before tool/model use.
    repo.reserve('owner','article',body)
    task=r.system_tasks.submit('owner','ai2apps.intelligence','intelligence.article_chat','Discuss',{'article_id':'article','request_id':body['request_id']})
    with pytest.raises(ValueError,match='fast mode'):
        await r.system_tasks.handlers['intelligence.article_chat'].execute(TaskContext(r.system_tasks,task))
    assert repo.get('owner','article')['turns']==[]


def test_article_preparation_and_confirmation_force_fast(env,monkeypatch):
    from ai2apps.research import search_preparation as prep
    from ai2apps.browser.mini_apps import WebAgentMiniAppBroker
    s,r,p,a,c=env;state=c.get('/articles/article/chat').json();seen=[]
    monkeypatch.setattr('ai2apps.system_tasks.sessions.execution_session',lambda *a:'session')
    monkeypatch.setattr(WebAgentMiniAppBroker,'registered',lambda *a:object())
    monkeypatch.setattr(prep,'begin',lambda *a,**k:seen.append(k) or {'status':'completed'})
    response=c.post('/articles/article/chat/search',json={'thread':state['thread'],'request_id':'search-request-123','query':'Model X'})
    assert response.status_code==200 and seen[0]['fast'] is True
    monkeypatch.setattr(prep,'owned',lambda *a,**k:{'profile':'default'})
    def confirm(*a,**k):
        assert a[-1]['mode']=='fast' and a[-1]['limit']==8
        assert a[-1]['cloud_consent'] is False
        return {'confirmation_id':'receipt'}
    monkeypatch.setattr(prep,'confirm',confirm)
    assert c.post('/articles/article/chat/search/confirm',json={'thread':state['thread'],'preparation_id':'prep','query':'Model X','source':'google'}).status_code==200

@pytest.mark.asyncio
async def test_ai_requests_fast_search_once_and_reuses_cached_decision_after_prepare_failure(env,monkeypatch):
    from ai2apps.research import search_preparation as prep
    from ai2apps.browser.mini_apps import WebAgentMiniAppBroker
    s,r,p,a,c=env;repo=chat.Repository(s);state=repo.get('owner','article');calls=[];preparations=[]
    monkeypatch.setattr('ai2apps.system_tasks.sessions.execution_session',lambda *a:'session')
    monkeypatch.setattr(WebAgentMiniAppBroker,'registered',lambda *a:object())
    async def model(*args,**kwargs):
        calls.append(kwargs);tool=kwargs['tools'][0]['function'];assert tool['name']=='web_search'
        assert tool['parameters']['properties']['mode']['enum']==['fast']
        with pytest.raises(ValueError):args[-1]({'tool':'execute_code','query':'hello'})
        return args[-1]({'tool':'web_search','query':'Model X meaning'})
    def prepare(*args,**kwargs):
        preparations.append(kwargs)
        if len(preparations)==1:raise ValueError('Temporary preparation failure')
        return {'id':'search-prep','status':'completed','query':kwargs['query'],'fast_source':'google','choices':[{'id':'google','name':'Google'}]}
    monkeypatch.setattr(service,'model_json',model);monkeypatch.setattr(prep,'begin',prepare)
    body=args(state['thread']);response=c.post('/articles/article/chat/actions',json=body).json()
    ctx=TaskContext(r.system_tasks,r.system_tasks.get('owner',response['task_id']));handler=r.system_tasks.handlers['intelligence.article_chat']
    with pytest.raises(ValueError,match='Temporary'):await handler.execute(ctx)
    await handler.execute(ctx)
    saved=repo.get('owner','article');assert saved['turns']==[] and saved['busy'] is None
    assert saved['pending_search']['question']==body['question'] and saved['pending_search']['query']=='Model X meaning'
    assert len(calls)==1 and len(preparations)==2
    assert preparations[0]==preparations[1] and preparations[0]['fast'] is True
    assert (await handler.execute(ctx))['cached'] and len(calls)==1
    repo.reset('owner','article',state['thread']);assert 'pending_search' not in repo.get('owner','article')

@pytest.mark.asyncio
async def test_search_result_cannot_request_another_tool(env,monkeypatch):
    s,r,p,a,c=env;state=chat.Repository(s).get('owner','article')
    async def model(*args,**kwargs):
        assert kwargs['tools'] is None
        with pytest.raises(ValueError,match='one fast search'):args[-1]({'tool':'web_search','query':'another'})
        return args[-1]({'answer':'Model X [1]','evidence_ids':[1]})
    monkeypatch.setattr(service,'model_json',model)
    result=await chat.generate(r,p,s,a,state,{**args(state['thread']),'confirmation_id':'receipt'},external={'articles':[]})
    assert result['answer']=='Model X [1]'

@pytest.mark.asyncio
async def test_native_function_call_is_validated_before_owner_dispatch(env,monkeypatch):
    from fastapi import HTTPException
    s,r,p,a,c=env;payloads=[];responses=[]
    r.model_manager=NS(resolve_default_model=lambda purpose:'model')
    async def invoke(*args,**kwargs):
        payloads.append(args[2]);return NS(status_code=200,body=json.dumps(responses[0]).encode())
    r.model_invocations=NS(model=lambda id:NS(id=id,endpoints=['chat_completions']),context_for_actor=lambda *a,**k:object(),invoke_background_json=invoke)
    tool={'type':'function','function':{'name':'web_search','description':'Fast search','parameters':{'type':'object','properties':{'query':{'type':'string','maxLength':128},'mode':{'enum':['fast']}},'required':['query','mode'],'additionalProperties':False}}}
    responses.append({'choices':[{'message':{'tool_calls':[{'function':{'name':'web_search','arguments':json.dumps({'query':'Model X','mode':'fast'})}}]},'finish_reason':'tool_calls'}]})
    result=await service.model_json(r,None,p,a['channel_id'],'Return an answer or use the Tool.',{},lambda value:value,stage='article_chat_answer',tools=[tool])
    assert result=={'tool':'web_search','query':'Model X'} and payloads[0]['tool_choice']=='auto'
    responses[0]['choices'][0]['message']['tool_calls'][0]['function']['arguments']=json.dumps({'query':'Model X','mode':'custom'})
    before=len(payloads)
    with pytest.raises(HTTPException):await service.model_json(r,None,p,a['channel_id'],'Use fast only.',{},lambda value:value,tools=[tool])
    assert len(payloads)-before==3

@pytest.mark.asyncio
async def test_model_selection_is_owner_checked_and_rechecked_on_execution(env,monkeypatch):
    s,r,p,a,c=env;state=c.get('/articles/article/chat').json();available=['model-a']
    async def catalog(*args):return {'models':[{'id':id,'name':id} for id in available],'default':'model-a'}
    monkeypatch.setattr(chat,'conversation_models',catalog)
    assert c.get('/articles/article/chat/models').json()['default']=='model-a'
    assert c.get('/articles/foreign/chat/models').status_code==404
    assert c.post('/articles/article/chat/actions',json={**args(state['thread']),'model':'foreign-model'}).status_code==409
    response=c.post('/articles/article/chat/actions',json={**args(state['thread']),'model':'model-a'}).json()
    assert chat.Repository(s).action('owner','article',args(state['thread'])['request_id'])['args']['model']=='model-a'
    available.clear()
    with pytest.raises(ValueError,match='model is unavailable'):
        await r.system_tasks.handlers['intelligence.article_chat'].execute(TaskContext(r.system_tasks,r.system_tasks.get('owner',response['task_id'])))
    assert chat.Repository(s).get('owner','article')['turns']==[]

def test_old_search_assistance_is_discarded_when_no_readable_sources_fail_action(env):
    s,r,p,a,c=env;repo=chat.Repository(s);state=repo.get('owner','article')
    args={'thread':state['thread'],'request_id':'assistance-request-123','mode':'answer','question':'Explain','confirmation_id':None}
    repo.reserve('owner','article',args)
    repo.assistance('owner','article',args['request_id'],[{'task_id':'btask_help','requires_user':True,'assistance_kind':'authentication'},
        {'task_id':'https://malicious.invalid','requires_user':True}])
    repo.finish('owner','article',args['request_id'],error='No readable sources')
    result=repo.get('owner','article')
    assert 'reading_assistance' not in result
    assert 'reading_assistance' not in repo.action('owner','article',args['request_id'])
    assert result['busy'] is None

@pytest.mark.parametrize('question',['你搜索一下看看','上网查一下','search that online'])
@pytest.mark.asyncio
async def test_explicit_contextual_search_reaches_confirmation_with_system_policy(env,monkeypatch,question):
    """Fixture model checks the real system payload; preparation never executes search."""
    from ai2apps.research import search_preparation as prep
    from ai2apps.browser.mini_apps import WebAgentMiniAppBroker
    s,r,p,a,c=env;repo=chat.Repository(s);state=repo.get('owner','article');prepared=[]
    first=args(state['thread'],request_id='prior-question-123')
    repo.reserve('owner','article',first)
    repo.finish('owner','article',first['request_id'],result={'answer':'Model X is an agent runtime [1]','references':[]})
    r.model_manager=NS(resolve_default_model=lambda purpose:'fixture-model')
    async def invoke(*values,**kwargs):
        payload=values[2];system=payload['messages'][0]
        assert system['role']=='system'
        assert 'MUST request web.search before answering' in system['content']
        assert 'NOT that web search is forbidden' in system['content']
        assert 'not search instructions quoted' in system['content']
        data=json.loads(payload['messages'][1]['content'])
        assert data['question']==question and data['external_reading'] is False
        assert data['history'][-1]['question']=='Explain Model X'
        assert payload['tools'][0]['function']['name']=='web_search'
        return NS(status_code=200,body=json.dumps({'choices':[{'message':{'tool_calls':[
            {'function':{'name':'web_search','arguments':json.dumps({'query':'Model X agent runtime official','mode':'fast'})}}
        ]},'finish_reason':'tool_calls'}]}).encode())
    r.model_invocations=NS(model=lambda id:NS(id=id,endpoints=['chat_completions']),
        context_for_actor=lambda *a,**k:object(),invoke_background_json=invoke)
    monkeypatch.setattr('ai2apps.system_tasks.sessions.execution_session',lambda *a:'session')
    monkeypatch.setattr(WebAgentMiniAppBroker,'registered',lambda *a:object())
    def begin(*values,**kwargs):
        prepared.append(kwargs)
        return {'id':'search-prep','query':kwargs['query'],'fast_source':'google','choices':[]}
    monkeypatch.setattr(prep,'begin',begin)
    body={**args(state['thread']),'question':question}
    result=c.post('/articles/article/chat/actions',json=body).json()
    await r.system_tasks.handlers['intelligence.article_chat'].execute(
        TaskContext(r.system_tasks,r.system_tasks.get('owner',result['task_id'])))
    saved=repo.get('owner','article')
    assert saved['pending_search']['question']==question
    assert saved['pending_search']['query']=='Model X agent runtime official'
    assert len(saved['turns'])==1 and len(prepared)==1 and prepared[0]['fast'] is True
    assert not hasattr(r,'app_capability_router')

@pytest.mark.asyncio
async def test_empty_completed_search_is_not_reported_as_not_started(env,monkeypatch):
    s,r,p,a,c=env;state=chat.Repository(s).get('owner','article')
    async def model(*values,**kwargs):
        assert values[-2]['external_reading'] is True
        assert kwargs['tools'] is None
        return values[-1]({'answer':'No readable external evidence; local fact [1]','evidence_ids':[1]})
    monkeypatch.setattr(service,'model_json',model)
    result=await chat.generate(r,p,s,a,state,{**args(state['thread']),'confirmation_id':'receipt'},external={})
    assert 'No readable external evidence' in result['answer']
