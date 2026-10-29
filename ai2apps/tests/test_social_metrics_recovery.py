"""Read defaults, native transport availability, and bounded social projections."""
from types import SimpleNamespace as NS
import pytest
from test_app_interactions import runtime
from ai2apps.capabilities import PolicyEffect
from ai2apps.chat import ChatRepository

@pytest.mark.asyncio
@pytest.mark.parametrize('tool',['fixture.reader','different.owner.observe'])
async def test_read_only_default_is_generic_and_explicit_policy_wins(runtime,tool):
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Read default')
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.diagnostic-agent',input={})
    args=dict(run_id=run.id,agent_key='ai2apps.diagnostic-agent',tool_name=tool,
              capabilities=('network.outbound',),effects=('external_read','network'),arguments={})
    assert (await runtime.capability_policy.evaluate(**args)).effect is PolicyEffect.ALLOW
    for effects in [('external_write','network'),('network',),('external_read','secrets')]:
        assert (await runtime.capability_policy.evaluate(**{**args,'effects':effects})).effect is PolicyEffect.REQUIRE_APPROVAL
    runtime.capabilities.upsert_policy(policy_key='fixture.explicit',effect=PolicyEffect.DENY,
        capability_pattern='network.outbound',tool_pattern=tool,priority=0)
    assert (await runtime.capability_policy.evaluate(**args)).effect is PolicyEffect.DENY


def test_profile_bound_backend_disables_standalone_transport(runtime):
    from ai2apps.browser.service import install_browser_service
    from ai2apps.services import ServiceStatus,ToolCallContext
    install_browser_service(NS(backend=NS(engine='fixture-native',require_profile_binding=True)),runtime.services,runtime.service_registry)
    assert runtime.services.get_service('ai2apps.browser').status is ServiceStatus.DISABLED
    visible=runtime.tools.list_tools(ToolCallContext(caller_id='test'),include_requiring_approval=True)
    assert {t.qualified_name for t in visible if t.qualified_name.startswith('browser.')} == {'browser.complete_goal'}
    assert any(t.qualified_name=='social.account' for t in visible)


def test_social_projection_preserves_metrics_without_media_paging():
    from ai2apps.browser.social import social_result_preview
    row={'id':'p','text':'title','likes':{'count':12,'status':'observed','display':'12'},
         'images':[{'src':'huge'}]*100,'media_review':{'complete':False,'images':[{'review':'large'}]*100}}
    d=social_result_preview(NS(output={'items':[row], 'profile':'default','status':'partial','stop_reason':'post_limit'}))
    assert d['items'][0]['likes']['count']==12
    assert 'images' not in d['items'][0]
    assert d['items'][0]['media_coverage']=={'complete':False}
    assert not d['summary_truncated']
    assert social_result_preview(NS(output={'candidates':[]})) is None

@pytest.mark.asyncio
@pytest.mark.parametrize('recover_count',[None,27])
async def test_missing_like_recovery_reobserves_same_page_without_reclick(monkeypatch,recover_count):
    from ai2apps.browser import social,social_platforms as a
    from ai2apps.browser.search import XHS_NOTE_TARGET_SCRIPT
    from datetime import datetime,timezone,timedelta
    h='1234567890abcdef12345678';post='aaaaaaaaaaaaaaaaaaaaaaaa';origin='https://www.rednote.com'
    calls=[];clicks=[];visits=[]
    missing={'count':None,'status':'unavailable','reason':'like_control_not_observed'}
    class Page:
        profile_key='default';context_id='original-context'
        async def navigate(self,url):visits.append(url)
        async def scroll(self,*a):raise AssertionError('No replacement navigation')
        async def call_json(self,script,args=None):
            if script==a.POSTS_SCRIPT:return {'items':[{'id':post,'author':h,'url':origin+'/explore/'+post,'pinned':False,'likes':missing}], 'time_zone':'UTC'}
            if script==XHS_NOTE_TARGET_SCRIPT:return {'ref':'observed'}
            assert script==a.DETAIL_SCRIPT
            calls.append((self.context_id,args))
            likes=missing.copy() if len(calls)==1 or recover_count is None else {'count':recover_count,'status':'observed','display':str(recover_count)}
            return {'id':post,'author':h,'text':'Post','published_at':(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),'likes':likes}
        async def pointer_to(self,target):clicks.append(target)
    page=Page()
    async def command(method,params):assert params['context']=='original-context'
    page.connection=NS(command=command)
    async def sleep(*a):pass
    monkeypatch.setattr(social.asyncio,'sleep',sleep)
    result=(await social.execute(page,{'arguments':{'owner_action':'read_account'}},{'platform':'xiaohongshu','handle':h,'site_origin':origin,'limit':1,'days':365},None))['evidence']['result']
    assert len(clicks)==1 and len(visits)==1
    assert all(c[0]=='original-context' for c in calls)
    assert len(calls)==(4 if recover_count is None else 2)
    likes=result['items'][0]['likes'];assert likes['count']==recover_count
    if recover_count is None:assert likes['recovery']=='same_profile_reobserved'

@pytest.mark.asyncio
@pytest.mark.parametrize('platform',['x','xiaohongshu','weibo'])
async def test_metrics_from_list_skip_all_detail_and_media(platform,monkeypatch):
    from ai2apps.browser import social,social_platforms as a,social_media
    h='1234567890abcdef12345678' if platform=='xiaohongshu' else 'user' if platform=='x' else '1234567890'
    counts={k:{'count':n,'display':str(n),'status':'observed'} for k,n in [('likes',7),('comments',2),('reposts',1)]}
    rows=[{'id':str(i),'author':h,'text':'List title','url':'https://example.test/'+str(i),'metrics':counts,'likes':counts['likes'],'pinned':i==0,'published_at':None} for i in range(4)]
    visits=[]
    class Page:
        profile_key='default'
        async def navigate(self,url):visits.append(url)
        async def call_json(self,script,args=None):
            assert script==(social.POSTS_SCRIPT if platform=='x' else a.POSTS_SCRIPT)
            return {'items':rows,'time_zone':'UTC'}
        async def pointer_to(self,*a):raise AssertionError('List counters must not open details')
        async def scroll(self,*a):raise AssertionError('Enough rows already present')
    def forbidden(*a):raise AssertionError('Metrics mode must not review media')
    monkeypatch.setattr(social_media,'SocialMediaReview',forbidden)
    result=(await social.execute(Page(),{'arguments':{'owner_action':'read_account'}},{'platform':platform,'handle':h,'read_mode':'metrics','selection':'recent','metrics':['likes','comments','reposts'],'limit':3},None,runtime=NS()))['evidence']['result']
    assert len(visits)==1
    assert [p['id'] for p in result['items']]==['1','2','3']
    assert all(p['metrics']['comments']['count']==2 for p in result['items'])
    assert result['media_coverage']['reason']=='metrics_only'


@pytest.mark.asyncio
async def test_recent_content_reviews_media_even_outside_default_day_window(monkeypatch):
    from ai2apps.browser import social,social_media
    row={'id':'old','author':'user','url':'https://x.com/user/status/123','published_at':'2020-01-01T00:00:00+00:00','images':[]}
    reviewed=[]
    class Media:
        extra=[]
        def __init__(self,*a):pass
        async def review(self,page,item,**kw):reviewed.append(item['id'])
        def annotate(self,item):pass
        def summary(self,items):return {'complete':True}
    class Page:
        profile_key='default'
        async def navigate(self,url):pass
        async def call_json(self,script,args=None):return {'items':[row],'time_zone':'UTC'}
    async def detail(*a):return dict(row),None
    async def photos(*a):return []
    monkeypatch.setattr(social_media,'SocialMediaReview',Media)
    monkeypatch.setattr(social,'x_detail',detail)
    monkeypatch.setattr(social,'x_photo_media',photos)
    result=(await social.execute(Page(),{'arguments':{'owner_action':'read_account'}},
        {'platform':'x','handle':'user','selection':'recent','limit':1},None,runtime=NS()))['evidence']['result']
    assert reviewed==['old'] and result['items'][0]['id']=='old'
    assert result['since'] is None


@pytest.mark.asyncio
async def test_list_time_and_counters_satisfy_date_window_without_detail(monkeypatch):
    from ai2apps.browser import social,social_platforms
    from datetime import datetime,timezone
    h='1234567890abcdef12345678'
    stamp=datetime.now(timezone.utc).isoformat()
    class Page:
        profile_key='default'
        async def navigate(self,url):pass
        async def call_json(self,script,args=None):
            assert script==social_platforms.POSTS_SCRIPT
            return {'items':[{'id':'p','author':h,'published_at':stamp,'likes':{'count':4}}],'time_zone':'UTC'}
        async def pointer_to(self,*a):raise AssertionError('List date and counters are sufficient')
    result=(await social.execute(Page(),{'arguments':{'owner_action':'read_account'}},
        {'platform':'xiaohongshu','handle':h,'read_mode':'metrics','selection':'date_window','limit':1},None))['evidence']['result']
    assert result['items'][0]['published_at']==stamp
    assert result['items'][0]['published_at_source']=='list'
    assert result['items'][0]['content_status']=='list_metrics'


@pytest.mark.parametrize('detail_time',[None,'2020-01-01T00:00:00Z'])
def test_detail_hydration_preserves_observed_list_time(detail_time):
    from ai2apps.browser.social import preserve_list_time
    item={'published_at':'2026-10-26T01:00:00Z','published_at_source':'list'}
    result=preserve_list_time(item,{'published_at':detail_time,'text':'detail'})
    assert result['published_at']==item['published_at'] and result['published_at_source']=='list'
