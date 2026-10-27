from types import SimpleNamespace
import pytest
from ai2apps.browser.background_page import BackgroundPage
from ai2apps.browser.background_executor import BackgroundExecutor


@pytest.mark.asyncio
@pytest.mark.parametrize('args',[{}, {'search_provider':'x'}, {'search_provider':'google'}, {'site_extraction':{'schema':'ai2apps.site-extraction/v1'}}])
async def test_list_blocks_before_sort_or_extraction(args):
    page=BackgroundPage(SimpleNamespace(),'tab')
    async def access(**kwargs):return {'classification':'needs_user','reason':'cookie_consent','frame':True}
    async def snapshot():return {'url':'https://example.com/news'}
    async def forbidden(*a,**kw):raise AssertionError('Blocked page must not extract')
    page.handle_access=access;page.snapshot=snapshot;page.call_json=forbidden
    result=await page.extract_list({'arguments':args})
    assert result['classification']=='needs_user' and result['items']==[] and result['frame']


@pytest.mark.asyncio
async def test_news_scan_returns_blocker_instead_of_scanning_more():
    page=BackgroundPage(SimpleNamespace(),'tab')
    calls=[]
    async def snapshot():return {'url':'https://example.com/news'}
    async def extract(step):calls.append(step);return {'classification':'restricted','reason':'paywall','items':[]}
    page.snapshot=snapshot;page.extract_list=extract
    result=await page.extract_news_list({'arguments':{'news_scan':True}})
    assert len(calls)==1 and result['classification']=='restricted'
    assert result['discovery']['stop_reason']=='page_blocked'


@pytest.mark.asyncio
async def test_dismissal_is_reobserved_and_bounded():
    page=BackgroundPage(SimpleNamespace(),'tab');clicks=[];observations=[]
    async def helper(*a):observations.append(a);return {'classification':'safe_dismiss','reason':'dismissible_prompt'}
    async def click(target,**kw):clicks.append(target)
    async def stable(**kw):return {'stable':True}
    page.helper=helper;page.pointer_to=click;page.wait_stable=stable
    result=await page.handle_access()
    assert len(clicks)==3 and len(observations)==4
    assert result['classification']=='needs_user' and result['reason']=='dismissible_prompt'


@pytest.mark.asyncio
@pytest.mark.parametrize('phase',[None,'finish'])
async def test_detail_checks_access_before_extraction_including_preloaded_tab(phase):
    page=BackgroundPage(SimpleNamespace(),'tab')
    async def snapshot():return {'url':'https://example.com/article'}
    async def access(**kwargs):return {'classification':'needs_user','reason':'cookie_consent','assistance_kind':'legal_consent','frame':True}
    async def navigate(*args,**kwargs):return {}
    async def forbidden(*args,**kwargs):raise AssertionError('Must not extract blocked content')
    page.snapshot=snapshot;page.handle_access=access;page.navigate=navigate;page.helper=forbidden
    async def observed(*a,**kw):return {'paragraphs':[], 'notice':''}
    page.call_json=observed
    result=await page.read_page({'url':'https://example.com/article','new_tab':False,'phase':phase,'opened':{'context':'tab'}})
    assert result['outcome']=='needs_user' and result['access']['frame']


@pytest.mark.asyncio
@pytest.mark.parametrize('classification',['needs_user','restricted'])
async def test_executor_preserves_blocker_for_non_search_lists(classification):
    class Page:
        context_id='tab'
        async def snapshot(self):return {'url':'https://example.com/news'}
        async def extract_list(self,step):return {'classification':classification,'reason':'cookie_consent','items':[]}
    result=await BackgroundExecutor(None).compiled(Page(),{'operation':'extract_list','arguments':{}},['https://example.com/**'])
    assert result['outcome']==classification and result['evidence']['reason']=='cookie_consent'


@pytest.mark.asyncio
@pytest.mark.parametrize('hit',[True,False])
async def test_cross_origin_consent_checks_ancestors_and_uses_child_input(hit):
    calls=[];clicked=[]
    class Connection:
        async def command(self,method,params):
            calls.append((method,params))
            return {'result':{'type':'window','value':{'context':'consent-child'}}}
    page=BackgroundPage(Connection(),'tab')
    async def helper(*args):
        if clicked:return {'classification':'none'}
        return {'classification':'needs_user','reason':'cookie_consent','frame':True,'frame_index':0,
                'frame_viewport':{'x':100,'y':200,'scale_x':.5,'scale_y':.5}}
    async def script(source,args,**kwargs):
        if kwargs['context_id']=='tab':return hit
        assert kwargs['context_id']=='consent-child' and args==[True]
        return {'classification':'safe_dismiss','reason':'cookie_consent','name':'Reject Non-Essential Cookies',
                'rect':{'x':20,'y':40,'width':200,'height':60}}
    async def pointer(target,**kw):clicked.append(target)
    async def stable(**kw):return {}
    page.helper=helper;page.call_json=script;page.pointer_to=pointer;page.wait_stable=stable
    result=await page.handle_access()
    if not hit:
        assert result['classification']=='needs_user' and result['frame_obscured'] and clicked==[]
        return
    assert result=={'classification':'none','dismissed':True}
    assert clicked[0]['rect']=={'x':119,'y':69,'width':2,'height':2}
    assert calls[0][1]['target']=={'context':'tab'}
    assert clicked[0]['input_context']=='consent-child'


@pytest.mark.asyncio
async def test_unresolved_iframe_never_becomes_success():
    class Connection:
        async def command(self,*args):return {'result':{'type':'null'}}
    page=BackgroundPage(Connection(),'tab')
    async def helper(*args):return {'classification':'needs_user','reason':'cookie_consent','frame':True,'frame_index':0}
    page.helper=helper
    result=await page.handle_access()
    assert result['classification']=='needs_user' and not result['dismissed']

@pytest.mark.asyncio
async def test_optional_overlay_reads_loaded_paragraphs_without_clicking_or_human_wait():
    page=BackgroundPage(SimpleNamespace(),'tab')
    async def access(**kwargs):return {'classification':'needs_user','reason':'blocking_prompt'}
    async def observed(*a,**k):return {'url':'https://example.com/article','title':'Article','notice':'','paragraphs':['Loaded original paragraph. '*12]}
    page.handle_access=access;page.call_json=observed
    blocker,result=await page.article_access({'max_chars':1000})
    assert result['extraction_method']=='loaded-dom-under-overlay' and 'Loaded original' in result['text']
    assert blocker['reason']=='blocking_prompt'

@pytest.mark.asyncio
@pytest.mark.parametrize('reason',['authentication','captcha','paywall'])
async def test_real_access_gate_never_uses_html_fallback_or_visual(reason):
    page=BackgroundPage(SimpleNamespace(),'tab')
    async def access(**kwargs):return {'classification':'needs_user','reason':reason}
    async def forbidden(*a,**k):raise AssertionError('No gate bypass')
    page.handle_access=access;page.call_json=forbidden
    blocker,result=await page.article_access({})
    assert result is None and blocker['reason']==reason

@pytest.mark.asyncio
async def test_optional_overlay_one_visual_attempt_after_empty_loaded_html():
    page=BackgroundPage(SimpleNamespace(),'tab');calls=[]
    async def access(**kwargs):return {'classification':'needs_user','reason':'blocking_prompt'}
    async def observed(source,*a,**k):return ['close-ref'] if 'data-ai2apps-ref' in source else {'paragraphs':[],'notice':''}
    async def snapshot(**k):return {}
    async def inspect():return {'classification':'none'}
    async def click(page,goal,**k):calls.append((goal,k));return {'performed':True,'state_verified':True}
    page.handle_access=access;page.call_json=observed;page.snapshot=snapshot;page.inspect_access=inspect
    page.visual_recovery=SimpleNamespace(policy={'visual_locating':True},click=click)
    blocker,result=await page.article_access({})
    assert blocker['classification']=='none' and result is None and len(calls)==1
    assert calls[0][1]['allowed_refs']==['close-ref'] and 'Never' in calls[0][0]

@pytest.mark.asyncio
async def test_plain_read_timeout_is_failure_instead_of_assistance():
    page=BackgroundPage(SimpleNamespace(),'tab')
    async def expired(options):raise TimeoutError()
    page._read_page=expired
    result=await page.read_page({'url':'https://example.com/article'})
    assert result=={'outcome':'failed','reason':'article_read_timeout','timeout_seconds':10}

def test_assistance_navigation_uses_only_the_task_owned_observed_context():
    from ai2apps.browser.task_presentation import browser_task_wait_presentation
    action=SimpleNamespace(id='action',status='submitted',request={'control':'browser_bidi_action'},
        response={'evidence':{'result':{'context':'child'}}})
    help=SimpleNamespace(id='help',status='pending',request_key='browser-assistance:action',prompt='Please sign in',
        request={'control':'browser_user_assistance','reason':'authentication'})
    context={'bidi_context':'root','owned_contexts':{'child':'root'}}
    result=browser_task_wait_presentation([action,help],context)
    assert result['assistance_context']=='child' and result['assistance_kind']=='authentication'
    assert 'assistance_context' not in browser_task_wait_presentation([action,help],{'bidi_context':'root','owned_contexts':{}})

@pytest.mark.asyncio
async def test_unrecognised_restriction_is_not_treated_as_optional_overlay():
    page=BackgroundPage(SimpleNamespace(),'tab')
    async def access(**kwargs):return {'classification':'restricted','reason':'restricted_access'}
    async def forbidden(*a,**k):raise AssertionError('Restricted pages do not fall back')
    page.handle_access=access;page.call_json=forbidden
    blocker,result=await page.article_access({})
    assert result is None and blocker['classification']=='restricted'


@pytest.mark.asyncio
async def test_disabled_visual_policy_never_captures_or_calls_visual_recovery_for_blocker():
    page=BackgroundPage(SimpleNamespace(),'tab')
    async def access(**kwargs):return {'classification':'needs_user','reason':'blocking_prompt'}
    async def observed(*a,**k):return {'paragraphs':[],'notice':''}
    async def forbidden(*a,**k):raise AssertionError('Visual assistance is disabled')
    page.handle_access=access;page.call_json=observed;page.snapshot=forbidden
    page.visual_recovery=SimpleNamespace(policy={'visual_locating':False,'visual_review':'off'},click=forbidden)
    blocker,result=await page.article_access({})
    assert result is None and blocker['reason']=='blocking_prompt'

@pytest.mark.asyncio
@pytest.mark.parametrize('host',['arbitrary.test','another.example'])
async def test_owned_auth_popup_is_specific_handoff_without_input_or_replay(host):
    from unittest.mock import AsyncMock
    page=SimpleNamespace(context_id='source')
    page.snapshot=AsyncMock(return_value={'url':f'https://{host}/search'})
    page.related_windows=AsyncMock(return_value=[{'context':'owned-popup','url':f'https://{host}/user/login'}])
    async def access(**kwargs):
        return {'classification':'needs_user','reason':'authentication','assistance_kind':'authentication'} if page.context_id=='owned-popup' else {'classification':'none'}
    page.inspect_access=AsyncMock(side_effect=access)
    result=await BackgroundExecutor(None).access_blocker(page,{'arguments':{'locale':'en'}},[f'https://{host}/**'],dispatched=True)
    assert result['evidence']['reason']=='authentication'
    assert result['evidence']['result']['context']=='owned-popup'
    assert result['evidence']['action_outcome_unknown'] is True
    assert result['evidence']['automatic_replay_allowed'] is False
    assert 'sign-in' in result['evidence']['assistance_message']
    assert page.context_id=='source'

@pytest.mark.asyncio
async def test_access_handoff_does_not_inspect_unscoped_popup():
    from unittest.mock import AsyncMock
    page=SimpleNamespace(context_id='source',snapshot=AsyncMock(return_value={'url':'https://arbitrary.test/search'}),
        related_windows=AsyncMock(return_value=[{'context':'foreign','url':'https://other.example/login'}]),
        inspect_access=AsyncMock(return_value={'classification':'none'}))
    assert await BackgroundExecutor(None).access_blocker(page,{},['https://arbitrary.test/**']) is None
    page.inspect_access.assert_awaited_once()
    assert page.context_id=='source'


@pytest.mark.asyncio
async def test_article_inspection_uses_read_only_scope_but_default_stays_strict():
    page=BackgroundPage(SimpleNamespace(),'tab');calls=[]
    async def helper(name,*args):
        calls.append((name,args));return {'classification':'none'}
    page.helper=helper
    await page.article_access({})
    assert calls==[('handlePageAccess:0',(False,True))]
    calls.clear();await page.handle_access()
    assert calls==[('handlePageAccess:0',())]


@pytest.mark.asyncio
async def test_optional_overlay_readback_does_not_reclassify_unrelated_form_label():
    page=BackgroundPage(SimpleNamespace(),'tab')
    async def access(**kwargs):return {'classification':'needs_user','reason':'blocking_prompt'}
    async def observed(*args,**kwargs):return {'url':'https://unrelated.example/report','title':'Report',
        'paragraphs':['Readable public report. '*20], 'notice':'Public report. Registration form CAPTCHA'}
    page.handle_access=access;page.call_json=observed
    _,result=await page.article_access({})
    assert result['outcome']=='success' and result['extraction_method']=='loaded-dom-under-overlay'
