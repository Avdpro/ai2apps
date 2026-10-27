from types import SimpleNamespace as NS
from datetime import datetime,timezone
import pytest
from ai2apps.browser.social import explicit_handle,select_posts,source,APP,CALLER
from ai2apps.browser.background_executor import BackgroundExecutor
from test_app_interactions import runtime

def test_account_input_canonicalization_does_not_invent_identity():
    assert explicit_handle('马斯克') is None
    assert explicit_handle('@elonmusk')=='elonmusk'
    assert explicit_handle('https://x.com/elonmusk')=='elonmusk'
    for value in ('https://x.com.evil/elonmusk','https://x.com/home','https://x.com/elonmusk/status/1','@bad-handle'):
        with pytest.raises(ValueError):explicit_handle(value)

def test_today_uses_timezone_excludes_old_pin_foreign_quote_repost_and_future():
    base={'author':'elonmusk','text':'observed','pinned':False,'repost':False}
    rows=[{**base,'id':str(i),'published_at':stamp} for i,stamp in enumerate(['2026-10-21T16:01:00Z','2026-10-21T15:59:00Z','2026-10-22T03:00:00Z'])]
    rows += [{**rows[0],'id':'foreign','author':'other'},{**rows[0],'id':'repost','repost':True},{**rows[1],'id':'pin','pinned':True}]
    result,start,end=select_posts(rows,'elonmusk',1,'Asia/Shanghai',datetime(2026,10,21,20,tzinfo=timezone.utc))
    assert [r['id'] for r in result]==['0'] and start.startswith('2026-10-22T00:00')

@pytest.mark.asyncio
@pytest.mark.parametrize('owner,action',[('fixture.alpha','read_a'),('fixture.beta','read_b')])
async def test_generic_owner_reader_dispatch_preserves_exact_owner_and_input(owner,action,monkeypatch):
    calls=[]
    async def handler(page,step,inputs,run):calls.append(inputs);return {'outcome':'success','evidence':{'result':inputs}}
    fake=NS(browser_owner_readers={(owner,action):handler},database=None,events=None)
    repo=NS(get=lambda *a:{'run_id':'fixture-run'},program=lambda *a:({},owner))
    monkeypatch.setattr('ai2apps.browser.tasks.BrowserTaskRepository',lambda *a:repo)
    executor=BackgroundExecutor(fake);step={'operation':'inspect','arguments':{'owner_action':action}}
    run=NS(id='fixture-run',input={'parameters':{'caller_app_id':owner,'owner_user_id':'actor','browser_task_id':'task'}})
    result=await executor.owner_read(None,step,run,{'fixture':'value'})
    assert result['outcome']=='success' and calls==[{'fixture':'value'}]
    run.id='another-run'
    assert (await executor.owner_read(None,step,run,{}))['evidence']['reason']=='owner_reader_task_mismatch'
    run.id='fixture-run'
    step['operation']='click'
    assert (await executor.owner_read(None,step,run,{}))['outcome']=='restricted'
    step['operation']='inspect'
    run.input['parameters']['caller_app_id']='foreign'
    assert (await executor.owner_read(None,step,run,{}))['outcome']=='restricted' and len(calls)==1

@pytest.mark.asyncio
async def test_owner_registers_account_resolution_and_confirmed_read_with_bilingual_fields(runtime):
    from ai2apps.identity import RequestPrincipal
    from ai2apps.agents.parameter_forms import FORMS
    for action in ('account',):
        p=runtime.app_capability_router.providers[APP+'.social.'+action]
        d=await p.describe(RequestPrincipal.legacy_local())
        assert all(set(f['label'])=={'zh','en'} for f in d['fields'])
        from ai2apps.agent_builder.compiler import compile_source
        assert compile_source(source('read_account',d['effective_schema'])).valid
    assert FORMS[APP+'.social.account'].prompt['zh']=='确认社交账号与读取范围'
    assert (CALLER,'read_account') in runtime.browser_owner_readers

@pytest.mark.asyncio
async def test_read_requires_observed_profile_account_and_exact_confirmed_values(runtime,monkeypatch):
    from dataclasses import replace
    from test_builtin_app_aaat import context
    from ai2apps.browser import social
    from ai2apps.browser.invocation import WebAgentInvocation
    ctx=replace(context(runtime),invocation_id='social-test')
    args={'action':'read_account','platform':'x','resolution_task':'observed','handle':'elonmusk','days':1,'limit':20,'profile':'default','time_zone':''}
    monkeypatch.setattr(social,'observed_resolution',lambda *a:({'profile_key':'default'},{'candidates':[{'handle':'elonmusk'}]}))
    submitted=[]
    monkeypatch.setattr(WebAgentInvocation,'submit',lambda self,**kw:submitted.append(kw) or {'id':'fixture'})
    async def result(*a):return {'items':[],'status':'partial'}
    monkeypatch.setattr(social,'task_result',result)
    monkeypatch.setattr(runtime.agents,'list_interactions',lambda *a:[])
    provider=runtime.app_capability_router.providers[APP+'.social.account']
    from ai2apps.services import ToolProviderError
    with pytest.raises(ToolProviderError,match='Confirm the exact'):await provider.handler(args,ctx)
    assert not submitted
    from ai2apps.agents.parameter_forms import FORMS
    form=FORMS[APP+'.social.account']
    receipt=NS(id='confirmed-read',status=NS(value='submitted'),request={'version':form.version},ui_hints={'provider':form.key,'provider_version':form.provider_version},response={'result':{'provider':form.key,'capability':'social.account','configure_only':True,'user_confirmed':True,'arguments':args.copy()}})
    monkeypatch.setattr('ai2apps.agents.form_continuation.selected_form',lambda *a:form)
    monkeypatch.setattr(runtime.agents,'list_interactions',lambda *a:[receipt])
    await provider.handler(args,ctx)
    assert len(submitted)==1 and submitted[0]['profile']=='default' and submitted[0]['caller_app_id']==CALLER
    assert not submitted[0].get('retain_pages_reason') and submitted[0]['parameters']['handle']=='elonmusk'
    await provider.handler(args,replace(ctx,invocation_id='another-model-call'))
    assert len(submitted)==2 and submitted[0]['key']==submitted[1]['key']=='social-read-confirmed-read'
    with pytest.raises(ToolProviderError,match='Select an observed'):await provider.handler({**args,'handle':'other'},ctx)
    with pytest.raises(ToolProviderError,match='Select an observed'):await provider.handler({**args,'profile':'other'},ctx)
    assert len(submitted)==2

@pytest.mark.asyncio
async def test_login_requires_assistance_without_starting_another_browser():
    from ai2apps.browser.social import execute
    calls=[]
    class Page:
        profile_key='default'
        async def navigate(self,url):calls.append(('navigate',url))
        async def call_json(self,*args):return {'login_required':True,'items':[]}
        async def scroll(self,*args):raise AssertionError('No scrolling behind login wall')
    result=await execute(Page(),{'arguments':{'owner_action':'read_account'}},{'handle':'elonmusk'},None)
    assert result['outcome']=='needs_user' and result['evidence']['reason']=='social_login_required'
    assert calls==[('navigate','https://x.com/elonmusk')]

def test_browser_failure_summary_is_short_and_keeps_original_structured_details():
    from ai2apps.research.mini_apps import WebMiniAppTaskError
    task={'id':'btask-fixture','run_id':'run-fixture','status':'failed','failure':{'code':'markup_missing','cause':{'private_evidence':'preserved'}},'message':'large evidence'*100}
    error=WebMiniAppTaskError(task)
    assert str(error)=='Browser task failed: markup_missing (task btask-fixture)'
    assert error.details['failure']==task['failure'] and '{' not in str(error)


def test_retry_read_reference_follows_only_persisted_resolution(monkeypatch):
    from ai2apps.browser import social
    from ai2apps.browser.tasks import BrowserTaskRepository
    from ai2apps.services import ToolProviderError
    tasks={'read':{'session_id':'session','status':'completed','capability':'read_account','profile_key':'default','input':{'resolution_task':'resolve'}},'resolve':{'session_id':'session','status':'completed','capability':'resolve_account','profile_key':'default','run_id':'observed'}}
    monkeypatch.setattr(BrowserTaskRepository,'get',lambda self,owner,key:tasks[key])
    monkeypatch.setattr(BrowserTaskRepository,'program',lambda *a:(None,social.CALLER))
    monkeypatch.setattr('ai2apps.api.agent_platform._run_result',lambda run:{'candidates':[]})
    runtime=NS(database=None,events=None,agents=NS(get_run=lambda key:key))
    ctx=NS(actor_user_id='owner',session_id='session')
    assert social.observed_resolution(runtime,ctx,'read')[0]['run_id']=='observed'
    tasks['resolve']['session_id']='foreign'
    with pytest.raises(ToolProviderError):social.observed_resolution(runtime,ctx,'read')

@pytest.mark.asyncio
async def test_form_recovers_missing_reference_from_same_session_profile(runtime,monkeypatch):
    from ai2apps.browser import social
    from ai2apps.browser.tasks import BrowserTaskRepository
    from ai2apps.agents.parameter_forms import FORMS
    task={'id':'observed','session_id':'session','profile_key':'default','status':'completed','capability':'resolve_account'}
    monkeypatch.setattr(BrowserTaskRepository,'list',lambda *a:[{**task,'id':'foreign','session_id':'other'},task])
    monkeypatch.setattr(runtime.agents,'get_run',lambda *a:NS(session_id='session'))
    seen=[]
    def observed(*args):
        seen.append(args[-1]);return task,{'candidates':[{'handle':'elonmusk','name':'Elon Musk','url':'https://x.com/elonmusk'}]}
    monkeypatch.setattr(social,'observed_resolution',observed)
    form=FORMS[APP+'.social.account'];values={'handle':'elonmusk','profile':'default'}
    extra=await form.describe(runtime,NS(actor_user_id='owner'),form,values,NS(run_id='run'))
    assert extra['schema']['properties']['resolution_task']['default']=='observed'
    assert next(f for f in extra['fields'] if f['key']=='resolution_task')['default']=='observed'
    assert 'foreign' not in seen
    assert extra['schema']['properties']['handle']['enum']==['elonmusk']

@pytest.mark.asyncio
async def test_scroll_passes_old_pin_and_deduplicates_until_regular_date_boundary(monkeypatch):
    from ai2apps.browser import social
    from datetime import timedelta
    today=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
    def row(id,delta=0,**kw):return {'id':id,'author':'user','published_at':(today+timedelta(seconds=delta)).isoformat(),'text':id,**kw}
    pin=row('pin',-86400,pinned=True)
    batches=[[pin,row(str(i),i)] for i in range(1,11)]+[[row('10',10),row('old',-1)]]
    class Page:
        profile_key='default'
        def __init__(self):self.reads=0;self.scrolls=0
        async def navigate(self,url):pass
        async def call_json(self,*args):
            result={'items':batches[min(self.reads,len(batches)-1)],'time_zone':'UTC'};self.reads+=1;return result
        async def scroll(self,*args):self.scrolls+=1
    async def sleep(*a):pass
    monkeypatch.setattr(social.asyncio,'sleep',sleep)
    page=Page();value=(await social.execute(page,{'arguments':{'owner_action':'read_account'}},{'handle':'user','time_zone':'UTC','limit':500},None))['evidence']['result']
    assert page.reads==11 and page.scrolls==10
    assert value['boundary_reached'] and value['stop_reason']=='date_boundary'
    assert len(value['items'])==10 and len({r['id'] for r in value['items']})==10
    assert value['pinned_items'][0]['id']=='pin' and value['coverage']=='date_boundary_observed'


def test_boundary_rejects_pin_unknown_foreign_repost_and_out_of_order():
    from ai2apps.browser.social import timeline_boundary
    old={'author':'user','published_at':'2026-10-20T00:00:00Z'};new={**old,'published_at':'2026-10-22T01:00:00Z'};start='2026-10-22T00:00:00+00:00'
    for batch in ([{**old,'pinned':True}],[{**old,'repost':True}],[{**old,'author':'other'}],[old,new],[{**old,'published_at':None}]):assert not timeline_boundary(batch,'user',start)
    assert timeline_boundary([new,old],'user',start)

@pytest.mark.asyncio
async def test_stalled_or_undated_timeline_never_claims_date_boundary(monkeypatch):
    from ai2apps.browser import social
    class Page:
        profile_key='default'
        async def navigate(self,*a):pass
        async def call_json(self,*a):return {'items':[{'id':'one','author':'user','published_at':None}],'time_zone':'UTC'}
        async def scroll(self,*a):pass
    async def sleep(*a):pass
    monkeypatch.setattr(social.asyncio,'sleep',sleep)
    result=(await social.execute(Page(),{'arguments':{'owner_action':'read_account'}},{'handle':'user'},None))['evidence']['result']
    assert result['status']=='partial' and result['stop_reason']=='loading_stalled' and len(result['undated_items'])==1


def test_platform_url_scope_and_explicit_identity():
    from ai2apps.browser.social_platforms import explicit_account,account_url
    for platform,handle in [('weibo','1234567890'),('xiaohongshu','1234567890abcdef12345678')]:
        url=account_url(platform,handle)
        assert explicit_account(platform,url)==handle
        assert source('read_account',{},platform)['site_scope']!=source('read_account',{})['site_scope']
        with pytest.raises(ValueError):explicit_account(platform,'https://evil.test/user/profile/'+handle)
        with pytest.raises(ValueError):account_url(platform,'../other')


def test_single_social_capability_and_retired_adapter_tools(runtime):
    providers=[key for key in runtime.app_capability_router.providers if key.startswith(APP+'.social.')]
    assert providers==[APP+'.social.account']
    service=runtime.services.get_tool('social.account').service_id
    runtime.services.ensure_tool(service_id=service,qualified_name='fixture.retired',display_name='Old fixture',description='retired fixture',input_schema={'type':'object'},output_schema={'type':'object'})
    from ai2apps.services.builtin_apps import install
    runtime.app_capability_router.providers.clear()
    runtime.app_capability_router.result_policies.clear()
    install(runtime)
    assert 'fixture.retired' not in {tool.qualified_name for tool in runtime.services.list_tools()}
    assert runtime.services.get_tool('social.account').enabled

@pytest.mark.asyncio
async def test_unified_platform_cannot_reuse_other_platform_account_confirmation(runtime,monkeypatch):
    from dataclasses import replace
    from test_builtin_app_aaat import context
    from ai2apps.browser import social
    from ai2apps.services import ToolProviderError
    monkeypatch.setattr(social,'observed_resolution',lambda *a:({'profile_key':'default','input':{'platform':'weibo'}},{'candidates':[{'handle':'1234567890'}]}))
    provider=runtime.app_capability_router.providers[APP+'.social.account']
    with pytest.raises(ToolProviderError,match='same Profile'):
        await provider.handler({'action':'read_account','platform':'x','handle':'1234567890','resolution_task':'observed'},replace(context(runtime),invocation_id='fixture'))

@pytest.mark.asyncio
async def test_bilingual_search_refines_literal_query_without_inventing_identity(monkeypatch):
    from ai2apps.browser import social
    class Page:
        profile_key='default'
        def __init__(self):self.urls=[]
        async def navigate(self,url):self.urls.append(url)
        async def call_json(self,*a):return {'candidates':[] if len(self.urls)==1 else [{'handle':'observed','name':'Observed','url':'https://x.com/observed'}]}
    async def sleep(*a):pass
    monkeypatch.setattr(social.asyncio,'sleep',sleep)
    page=Page();r=(await social.execute(page,{'arguments':{'owner_action':'resolve_account'}},{'platform':'x','query':'Elon Musk 马斯克'},None))['evidence']['result']
    assert len(page.urls)==2 and page.urls[-1].startswith('https://x.com/search?q=Elon%20Musk&')
    assert r['candidates'][0]['handle']=='observed'

@pytest.mark.asyncio
async def test_unified_owner_prepare_normalizes_display_name_alias_before_stage_validation(runtime):
    from test_builtin_app_aaat import context
    from jsonschema import ValidationError
    provider=runtime.app_capability_router.providers[APP+'.social.account']
    values=await provider.prepare({'platform':'weibo','handle':'人民日报'},context(runtime))
    assert values['query']=='人民日报' and values['action']=='resolve_account'
    with pytest.raises(ValidationError):await provider.prepare({'action':'read_account','platform':'weibo','handle':'1234567890'},context(runtime))

@pytest.mark.asyncio
async def test_social_assistance_is_published_to_chat_observer(monkeypatch):
    from ai2apps.browser import social
    states=iter(['waiting_input','completed']);updates=[]
    task={'id':'task','run_id':'child','capability':'resolve_account'}
    repo=NS(get=lambda *a:{**task,'status':next(states)})
    monkeypatch.setattr('ai2apps.browser.tasks.BrowserTaskRepository',lambda *a:repo)
    monkeypatch.setattr('ai2apps.api.agent_platform._run_result',lambda *a:{'candidates':[]})
    prompt=social.assistance('xiaohongshu')['evidence']['assistance_message']
    interaction=NS(status=NS(value='pending'),request={'control':'browser_user_assistance'},ui_hints={'control':'browser_user_assistance'},prompt=prompt)
    runtime=NS(database=None,events=None,agents=NS(list_interactions=lambda *a:[interaction],get_run=lambda *a:None))
    async def report(*a,**kw):updates.append(kw['content']['task_progress'])
    async def sleep(*a):pass
    monkeypatch.setattr(social.asyncio,'sleep',sleep)
    await social.task_result(runtime,task,NS(actor_user_id='owner',report_progress=report))
    assert updates[0]['requires_user'] and '小红书 登录' in updates[0]['wait_reason']
    assert not updates[1]['requires_user']

@pytest.mark.asyncio
async def test_cancelled_social_task_preserves_cancellation_not_retryable_failure(monkeypatch):
    import asyncio
    from ai2apps.browser import social
    task={'id':'task','run_id':'child','capability':'resolve_account','status':'cancelled'}
    monkeypatch.setattr('ai2apps.browser.tasks.BrowserTaskRepository',lambda *a:NS(get=lambda *a:task))
    async def progress(*a,**kw):pass
    with pytest.raises(asyncio.CancelledError):
        await social.task_result(NS(database=None,events=None),task,NS(actor_user_id='owner',report_progress=progress))

@pytest.mark.asyncio
@pytest.mark.parametrize('parent_session,expected',[('session',['parent']),('other',[])])
async def test_social_cancel_persists_only_exact_invoking_session_run(monkeypatch,parent_session,expected):
    import asyncio
    from ai2apps.browser import social
    task={'id':'task','run_id':'child','capability':'resolve_account','status':'cancelled'}
    monkeypatch.setattr('ai2apps.browser.tasks.BrowserTaskRepository',lambda *a:NS(get=lambda *a:task))
    cancelled=[]
    runtime=NS(database=None,events=None,agents=NS(get_run=lambda *a:NS(id='parent',session_id=parent_session)),agent_runtime=NS(cancel=cancelled.append))
    async def progress(*a,**kw):pass
    with pytest.raises(asyncio.CancelledError):
        await social.task_result(runtime,task,NS(actor_user_id='owner',session_id='session',trace_id='parent',report_progress=progress))
    assert cancelled==expected

@pytest.mark.asyncio
@pytest.mark.parametrize('states,expected',[
    (['logged_in','login_required'],'https://www.rednote.com'),
    (['login_required','logged_in'],'https://www.xiaohongshu.com'),
    (['login_required','login_required'],None),
    (['unknown','login_required'],'https://www.rednote.com'),
    (['outside_scope','login_required'],None),
])
async def test_xhs_probes_both_homes_in_one_page(monkeypatch,states,expected):
    from ai2apps.browser import social_platforms as adapters
    visits=[];index=-1
    class Page:
        async def navigate(self,url):
            nonlocal index
            visits.append(url);index+=1
        async def call_json(self,script):return {'state':states[index],'origin':adapters.XHS_ORIGINS[index]}
    async def sleep(*args):pass
    monkeypatch.setattr('asyncio.sleep',sleep)
    selected,checks=await adapters.choose_home(Page())
    assert visits==[o+'/' for o in adapters.XHS_ORIGINS]
    assert selected==expected and [c['state'] for c in checks]==states

def test_xhs_origin_is_bound_to_persisted_resolution():
    from ai2apps.browser.social import resolution_origin
    from ai2apps.browser.social_platforms import explicit_account,account_url,search_url
    handle='1234567890abcdef12345678';origin='https://www.rednote.com'
    assert explicit_account('xiaohongshu',origin+'/user/profile/'+handle)==handle
    assert resolution_origin({'candidates':[{'handle':handle,'url':origin+'/user/profile/'+handle}]},handle)==origin
    assert account_url('xiaohongshu',handle,origin).startswith(origin+'/')
    assert search_url('xiaohongshu','测试',origin).startswith(origin+'/')
    for bad in ['https://www.rednote.com.evil','https://www.rednote.com:444','http://www.rednote.com']:
        with pytest.raises(ValueError):resolution_origin({'site_origin':bad},handle)
        with pytest.raises(ValueError):account_url('xiaohongshu',handle,bad)

@pytest.mark.asyncio
async def test_xhs_resolver_uses_selected_home_and_reports_probe_evidence(monkeypatch):
    from ai2apps.browser import social,social_platforms as adapters
    visited=[];handle='1234567890abcdef12345678'
    class Page:
        profile_key='default'
        async def navigate(self,url):visited.append(url)
        async def call_json(self,script,args=None):
            if script==adapters.HOME_SCRIPT:
                return {'origin':visited[-1].rstrip('/'),'state':'logged_in' if 'rednote.com' in visited[-1] else 'login_required'}
            return {'candidates':[{'handle':handle,'name':'Observed','url':visited[-1],'identity_source':'profile_header'}]}
    result=await social.execute(Page(),{'arguments':{'owner_action':'resolve_account'}},{'platform':'xiaohongshu','query':'https://www.rednote.com/user/profile/'+handle},None)
    assert visited==[o+'/' for o in adapters.XHS_ORIGINS]+['https://www.rednote.com/user/profile/'+handle]
    result=result['evidence']['result']
    assert result['site_origin']=='https://www.rednote.com'
    assert [c['state'] for c in result['home_checks']]==['logged_in','login_required']


@pytest.mark.asyncio
async def test_post_author_recovery_verifies_observed_profile_in_same_page(monkeypatch):
    from ai2apps.browser import social_platforms as a
    origin='https://www.rednote.com';handle='1234567890abcdef12345678';visits=[];scrolls=[]
    class Page:
        async def navigate(self,url):visits.append(url)
        async def scroll(self,dy):scrolls.append(dy)
        async def call_json(self,*args):
            if '/user/profile/' in visits[-1]:return {'candidates':[{'handle':handle,'name':'Requested','url':visits[-1],'identity_source':'profile_header'}]}
            if 'type=51' in visits[-1]:return {'candidates':[]}
            return {'candidates':[{'handle':handle,'name':'Requested','url':origin+'/user/profile/'+handle+'?xsec_token=observed','identity_source':'post_author'}]}
    async def sleep(*args):pass
    monkeypatch.setattr('asyncio.sleep',sleep)
    result=await a.resolve_xhs(Page(),'Requested',origin)
    assert len(result['resolution_attempts'])==2 and scrolls
    assert all(url.startswith(origin+'/') for url in visits)
    assert '?xsec_token=observed' in visits[-1]
    assert result['candidates'][0]['identity_verified'] is True
    assert result['candidates'][0]['identity_source']=='post_author'

@pytest.mark.asyncio
@pytest.mark.parametrize('bad',['wrong_header','foreign_origin','login_required'])
async def test_author_is_not_accepted_without_same_origin_profile_verification(monkeypatch,bad):
    from ai2apps.browser import social_platforms as a
    origin='https://www.rednote.com';handle='1234567890abcdef12345678';visits=[]
    class Page:
        async def navigate(self,url):visits.append(url)
        async def call_json(self,*args):
            if '/user/profile/' in visits[-1]:return {'login_required':True} if bad=='login_required' else {'candidates':[{'handle':'aaaaaaaaaaaaaaaaaaaaaaaa','name':'Other','identity_source':'profile_header'}]}
            return {'candidates':[{'handle':handle,'name':'Requested','url':('https://foreign.test' if bad=='foreign_origin' else origin)+'/user/profile/'+handle,'identity_source':'post_author'}]}
    async def sleep(*args):pass
    monkeypatch.setattr('asyncio.sleep',sleep)
    result=await a.resolve_xhs(Page(),'Requested',origin)
    assert not result.get('candidates')
    assert all(url.startswith(origin+'/') for url in visits)
    if bad=='login_required':assert result['login_required']

def test_desktop_legacy_backend_never_launches_an_isolated_browser():
    from ai2apps.browser.acefox import AceFoxBrowserBackend
    from ai2apps.browser.models import BrowserRuntimeConfig,BrowserError
    calls=[]
    backend=AceFoxBrowserBackend(BrowserRuntimeConfig(profile_path='/tmp/unused'),helper_provider=lambda:calls.append('helper'),require_profile_binding=True)
    with pytest.raises(BrowserError,match='Profile-bound'):backend.start_for_actor('arbitrary-actor')
    assert calls==[] and backend.connection is None

def test_confirmed_profile_entry_preserves_observed_access_parameters_and_scope():
    from ai2apps.browser.social import resolution_entry
    h='1234567890abcdef12345678';origin='https://www.rednote.com';url=origin+'/user/profile/'+h+'?xsec_token=observed&xsec_source=search'
    observed={'site_origin':origin,'candidates':[{'handle':h,'url':url}]}
    assert resolution_entry(observed,h)==url
    for bad in ['https://foreign.test/user/profile/'+h,origin+'/user/profile/aaaaaaaaaaaaaaaaaaaaaaaa',origin+'/explore/'+h]:
        with pytest.raises(ValueError):resolution_entry({**observed,'candidates':[{'handle':h,'url':bad}]},h)

@pytest.mark.asyncio
async def test_xhs_read_uses_one_native_click_per_observed_note_and_reads_back(monkeypatch):
    from ai2apps.browser import social,social_platforms as a
    from ai2apps.browser.search import XHS_NOTE_TARGET_SCRIPT
    from datetime import timedelta
    h='1234567890abcdef12345678';origin='https://www.rednote.com';clicks=[];history=[];visits=[];updates=[]
    stamp=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
    notes=[{'id':str(i)*24,'author':h,'url':origin+'/user/profile/'+h+'/'+str(i)*24,'text':'List title','published_at':None,'pinned':False} for i in (1,2)]
    class Page:
        profile_key='default';context_id='same-default-context';active=None
        async def search_progress(self,value):updates.append(value['progress_snapshot']['content']['task_progress'])
        async def navigate(self,url):visits.append(url)
        async def call_json(self,script,args=None):
            if script==a.POSTS_SCRIPT:return {'items':notes,'time_zone':'UTC'}
            if script==XHS_NOTE_TARGET_SCRIPT:return {'rect':{'x':0,'y':0,'width':100,'height':100},'id':args[0].split('/')[-1]}
            if script==a.DETAIL_SCRIPT:return {'id':self.active,'author':h,'text':'Verified full body','published_at':stamp}
            raise AssertionError('Unexpected page operation')
        async def pointer_to(self,target):self.active=target['id'];clicks.append(self.active)
    page=Page()
    async def command(method,params):history.append((method,params));page.active=None
    page.connection=NS(command=command)
    async def sleep(*args):pass
    monkeypatch.setattr(social.asyncio,'sleep',sleep)
    result=(await social.execute(page,{'arguments':{'owner_action':'read_account'}},{'platform':'xiaohongshu','handle':h,'site_origin':origin,'account_entry_url':origin+'/user/profile/'+h+'?xsec_token=observed','days':365,'limit':2},None))['evidence']['result']
    assert len(clicks)==len(set(clicks))==2 and len(history)==2
    assert all(params['context']=='same-default-context' for _,params in history)
    assert len(visits)==1 and 'xsec_token=observed' in visits[0]
    assert len(result['items'])==2 and all(x['text']=='Verified full body' for x in result['items'])
    assert result['stop_reason']=='post_limit' and result['coverage']=='partial'
    assert any(v['stage']=='reading' and v['metrics'][1]['value']==1 for v in updates)
    assert updates[-1]['stage']=='finalizing' and [m['value'] for m in updates[-1]['metrics']]==[2,2,0]

@pytest.mark.asyncio
async def test_reply_originals_are_one_hop_deduped_and_share_media_budget(monkeypatch):
    from ai2apps.browser import social,social_media
    seen=[];navigations=[]
    class Media:
        extra=[]
        def __init__(self,*a):pass
        def can_continue(self):return True
        async def review(self,page,item,**kw):seen.append(item['id'])
        def annotate(self,item):pass
        def summary(self,posts):return {'ids':[p['id'] for p in posts]}
    monkeypatch.setattr(social_media,'SocialMediaReview',Media)
    original={'id':'10','author':'other','url':'https://x.com/other/status/10','text':'Original','published_at':'2020-01-01T00:00:00Z','images':[],'relation':'reply_to','context_status':'observed'}
    now=datetime.now(timezone.utc).isoformat()
    posts=[{'id':i,'author':'reader','url':'https://x.com/reader/status/'+i,'text':'Reply','published_at':now,'images':[]} for i in ('20','21')]
    class Page:
        profile_key='default'
        async def navigate(self,url):navigations.append(url)
        async def call_json(self,*a):return {'items':posts,'time_zone':'UTC'}
    async def detail(page,item,handle):
        if handle=='other':return {**original,'related_posts':[{'id':'0'}]},None
        return {**item,'related_posts':[dict(original)]},None
    monkeypatch.setattr(social,'x_detail',detail)
    result=await social.execute(Page(),{'arguments':{'owner_action':'read_account'}},{'platform':'x','handle':'reader','limit':2},None,runtime=NS())
    result=result['evidence']['result']
    assert [i['id'] for i in result['items']]==['20','21']
    assert seen.count('10')==1 and seen.count('20')==1 and seen.count('21')==1
    assert set(result['media_coverage']['ids'])=={'10','20','21'}
    assert navigations.count(original['url'])==1
    assert all('related_posts' not in i['related_posts'][0] for i in result['items'])

@pytest.mark.asyncio
async def test_social_progress_counts_unique_evidence_and_persists_only_changes():
    from ai2apps.browser.social import SocialProgress
    updates=[]
    async def publish(value):updates.append(value)
    progress=SocialProgress(NS(search_progress=publish))
    await progress.publish('extracting',rows=[{'id':'post-a'},{'id':'post-a'},{'id':'post-b'}])
    await progress.publish('extracting',rows=[{'id':'post-a'}])
    assert len(updates)==1
    progress.read.add('post-a')
    await progress.publish('reading')
    await progress.reviewed({'media_review':{'images':[
        {'image_key':'one','status':'seen'}, {'image_key':'two','status':'unseen'},
        {'image_key':'one','status':'seen'}]}})
    await progress.reviewed({'media_review':{'images':[{'image_key':'one','status':'seen'}]}})
    metrics=updates[-1]['progress_snapshot']['content']['task_progress']['metrics']
    assert [m['value'] for m in metrics]==[2,1,1]
    assert len(updates)==3
    assert 'post-a' not in str(updates)

@pytest.mark.asyncio
async def test_social_chat_forwards_durable_counters_dedupes_and_keeps_terminal_metrics(monkeypatch):
    from ai2apps.browser import social
    states=iter(['running','running','waiting_input','completed']);updates=[]
    task={'id':'task','run_id':'child','capability':'read_account'}
    repo=NS(get=lambda *a:{**task,'status':next(states)})
    monkeypatch.setattr('ai2apps.browser.tasks.BrowserTaskRepository',lambda *a:repo)
    monkeypatch.setattr('ai2apps.api.agent_platform._run_result',lambda *a:{'status':'partial'})
    snapshots=[]
    async def publish(value):snapshots.append(value)
    progress=social.SocialProgress(NS(search_progress=publish))
    await progress.publish('extracting',rows=[{'id':'one'},{'id':'two'}])
    monkeypatch.setattr('ai2apps.browser.search_progress.read',lambda *a:snapshots[-1])
    interaction=NS(status=NS(value='pending'),request={'control':'browser_user_assistance'},ui_hints={'control':'browser_user_assistance'},prompt='请处理页面验证')
    runtime=NS(database=object(),events=None,agents=NS(list_interactions=lambda *a:[interaction],get_run=lambda *a:None))
    async def report(text,**kw):updates.append((text,kw['content']['task_progress']))
    async def sleep(*a):pass
    monkeypatch.setattr(social.asyncio,'sleep',sleep)
    result=await social.task_result(runtime,task,NS(actor_user_id='owner',report_progress=report))
    assert result['status']=='partial' and len(updates)==3
    assert updates[0][1]['metrics'][0]['value']==2
    assert updates[1][1]['requires_user'] and updates[1][1]['wait_reason']=='请处理页面验证'
    assert updates[-1][1]['state']=='completed' and not updates[-1][1]['requires_user']
    assert updates[-1][1]['task_id']=='task' and updates[-1][1]['metrics']==updates[0][1]['metrics']
