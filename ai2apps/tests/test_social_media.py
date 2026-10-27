import base64,io,json
from types import SimpleNamespace as NS
from contextlib import contextmanager
import sqlite3
import pytest
from PIL import Image
from ai2apps.browser.media_review import MediaLedger,prepare_image,image_key
from ai2apps.browser.social_media import SocialMediaReview,TARGET

class DB:
    def __init__(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
    @contextmanager
    def transaction(self,write=False):
        with self.c:yield self.c

def picture():
    b=io.BytesIO();Image.new('RGB',(2000,1800),'red').save(b,'PNG');return base64.b64encode(b.getvalue()).decode()

def test_ledger_cap_restart_cache_actor_scope_and_query_dedup():
    db=DB();a=MediaLedger(db,'actor-a','task-a')
    assert image_key('https://cdn.example/image?id=a')!=image_key('https://cdn.example/image?id=b')
    assert image_key('https://cdn.example/image#one')==image_key('https://cdn.example/image#two')
    for i in range(50):assert a.reserve(str(i),100)
    assert not a.reserve('new',1) and not a.reserve('1',1)
    a.save('1',{'visible_text':'observed'})
    assert MediaLedger(db,'actor-a','task-a').get('1')['visible_text']=='observed'
    assert MediaLedger(db,'actor-b','task-b').get('1') is None
    b=MediaLedger(db,'actor-a','task-b');assert b.get('1') and b.reserve('new',1)
    assert not b.reserve('oversize',10_000_001)

def test_image_resize_and_invalid_source():
    url,size=prepare_image(picture())
    with Image.open(io.BytesIO(base64.b64decode(url.split(',')[1]))) as im:assert max(im.size)==1280
    assert size<1_000_000
    with pytest.raises(ValueError):image_key('https://user:password@example.com/image')
    with pytest.raises(ValueError):prepare_image('invalid data')

def reviewer(vision=True):
    run=NS(id='child',session_id='session',input={'parameters':{'owner_user_id':'actor','browser_task_id':'task'}})
    rt=NS(database=DB(),model_manager=NS(list_cloud=lambda:[{'id':'fixture','models':[{'id':'current','enabled':True,'capabilities':{'imageInput':vision}}]}]))
    return SocialMediaReview(rt,run,{'platform':'fixture','handle':'account','profile':'default','current_model':'cloud/fixture/current','reading_goal':'Question'})

@pytest.mark.asyncio
async def test_first_two_then_ai_extra_and_continuation_never_replays_seen(monkeypatch):
    media=reviewer();calls=[];updates=[]
    async def progress(post):updates.append([r['status'] for r in media.records(post)])
    media.progress=progress
    async def decide(post,pictures):
        calls.append([k for k,_ in pictures])
        return {'images':[{'image_key':k,'visible_text':'Russell','description':'label','uncertainty':'','usable':True} for k,_ in pictures],'request_more':True}
    media.decide=decide
    class Page:
        context_id='context'
        async def call_json(self,*args):return {'x':0,'y':0,'width':100,'height':100}
        connection=NS(command=None)
    async def capture(*args,**kw):return {'data':picture()}
    page=Page();page.connection=NS(command=capture)
    post={'id':'post','images':[{'src':f'https://example.com/{i}','ref':str(i),'index':i} for i in range(5)]}
    await media.review(page,post);assert len(calls[0])==2 and media.extra==['post']
    await media.review(page,post,extra=True);assert len(calls[1])==2
    await media.review(page,post,extra=True);assert len(calls[2])==1 and post['media_review']['complete']
    await media.review(page,post);assert len(calls)==3 and media.ledger.usage()['n']==5
    assert media.summary([post])['seen']==5
    assert updates[0].count('seen')==0 and updates[1].count('seen')==2 and updates[-1].count('seen')==5
    next_run=NS(id='next',session_id=media.run.session_id,input={'parameters':{'owner_user_id':'actor','browser_task_id':'next-task'}})
    continued=SocialMediaReview(media.runtime,next_run,media.inputs)
    await continued.review(None,post)
    assert continued.ledger.usage()['n']==0 and post['media_review']['complete']

@pytest.mark.asyncio
async def test_missing_vision_does_not_change_model_or_claim_seen():
    media=reviewer(False);post={'id':'post','images':[{'src':'https://example.com/1'}]}
    await media.review(None,post)
    assert not post['media_review']['complete']
    assert post['media_review']['images'][0]['status']=='unseen'
    assert media.model=='cloud/fixture/current' and media.reason=='current_model_has_no_declared_vision'

@pytest.mark.asyncio
async def test_failed_or_unknown_model_attempt_is_not_automatically_repeated():
    media=reviewer();calls=[]
    async def fail(*args):calls.append(1);raise TimeoutError()
    media.decide=fail
    async def rect(*args):return {'x':0,'y':0,'width':100,'height':100}
    async def capture(*args,**kwargs):return {'data':picture()}
    page=NS(call_json=rect,context_id='ctx',connection=NS(command=capture))
    post={'id':'p','images':[{'src':'https://example.com/p','ref':'p'}]}
    await media.review(page,post);await media.review(page,post)
    assert len(calls)==1 and not post['media_review']['complete']
    assert post['media_review']['images'][0]['status']=='unseen'

@pytest.mark.asyncio
async def test_current_model_receives_images_and_rejects_fabricated_review_keys():
    media=reviewer();seen=[]
    async def invoke(payload,context):
        seen.append(payload)
        return {'choices':[{'message':{'content':json.dumps({'images':[{'image_key':'invented','visible_text':'x','description':'x','uncertainty':''}],'request_more':False})}}]}
    media.runtime.model_invocations=NS(context_for_actor=lambda *a,**k:object(),invoke_agent_cloud_json=invoke)
    with pytest.raises(ValueError,match='keys do not match'):
        await media.decide({'id':'p','images':[]},[('observed','data:image/jpeg;base64,AA==')])
    assert seen[0]['model']=='cloud/fixture/current'
    assert seen[0]['messages'][1]['content'][-1]['type']=='image_url'

@pytest.mark.asyncio
async def test_unreadable_capture_stays_unseen_and_is_not_successfully_cached():
    media=reviewer()
    async def decide(post,pictures):
        return {'images':[{'image_key':k,'visible_text':'','description':'blank','uncertainty':'loading','usable':False} for k,_ in pictures],'request_more':False}
    media.decide=decide
    async def rect(*a):return {'x':0,'y':0,'width':100,'height':100}
    async def capture(*a,**k):return {'data':picture()}
    post={'id':'p','images':[{'src':'https://example.com/blank','ref':'b'}]}
    await media.review(NS(call_json=rect,connection=NS(command=capture),context_id='ctx'),post)
    assert media.ledger.usage()['n']==1
    assert media.ledger.get(media.key(post,post['images'][0])) is None
    assert not post['media_review']['complete']
    assert post['media_review']['images'][0]['unseen_reason']=='model_could_not_read_image'

def test_owner_signed_cdn_urls_reuse_stable_asset_identity():
    media=reviewer();media.inputs['platform']='xiaohongshu'
    p={'id':'p'}
    a={'src':'https://sns-web-i1.rednotecdn.com/old/signature/asset123!webp_small'}
    b={'src':'https://sns-web-i9.rednotecdn.com/new/rotated/asset123!webp_large'}
    assert media.key(p,a)==media.key(p,b)
    b['src']='https://sns-web-i9.rednotecdn.com/new/rotated/otherasset!webp_large'
    assert media.key(p,a)!=media.key(p,b)


def test_owner_x_render_variants_deduplicate_but_unknown_query_assets_do_not():
    media=reviewer();media.inputs['platform']='x';post={'id':'p'}
    a={'src':'https://pbs.twimg.com/media/asset?format=jpg&name=small'}
    b={'src':'https://pbs.twimg.com/media/asset?format=jpg&name=large'}
    assert media.key(post,a)==media.key(post,b)
    assert media.key(post,{'src':'https://unknown.example/image?id=1'})!=media.key(post,{'src':'https://unknown.example/image?id=2'})

@pytest.mark.asyncio
async def test_json_syntax_repair_uses_text_only_and_preserves_observed_evidence():
    media=reviewer();calls=[]
    result={'images':[{'image_key':'observed','visible_text':'label','description':'watch','uncertainty':'','usable':True}],'request_more':False}
    async def invoke(payload,context):
        calls.append(payload)
        content=json.dumps(result)
        if len(calls)==1:content=content[:-1]+',}'
        return {'choices':[{'message':{'content':content}}]}
    media.runtime.model_invocations=NS(context_for_actor=lambda *a,**k:object(),invoke_agent_cloud_json=invoke)
    value=await media.decide({'id':'p','images':[]},[('observed','data:image/jpeg;base64,AA==')])
    assert value['images'][0]['visible_text']=='label' and len(calls)==2
    assert any(c.get('type')=='image_url' for m in calls[0]['messages'] if isinstance(m['content'],list) for c in m['content'])
    assert not any(c.get('type')=='image_url' for m in calls[1]['messages'] if isinstance(m['content'],list) for c in m['content'])

def test_unseen_reasons_cover_unattempted_extra_and_deadline():
    media=reviewer();post={'id':'p','images':[{'src':'https://example.com/1','index':0},{'src':'https://example.com/3','index':2}]}
    assert [r['unseen_reason'] for r in media.records(post)]==['image_review_not_attempted','default_per_post_limit']
    media.deadline=0
    assert all(r['unseen_reason']=='image_review_time_limit' for r in media.records(post))
    post['images'][0]['unseen_reason']='post_detail_author_unverified'
    assert media.records(post)[0]['unseen_reason']=='post_detail_author_unverified'

@pytest.mark.asyncio
async def test_x_detail_retry_and_identity_failure_do_not_use_stale_timeline_refs(monkeypatch):
    from ai2apps.browser.social import x_detail
    async def sleep(*a):pass
    monkeypatch.setattr('ai2apps.browser.social.asyncio.sleep',sleep)
    answers=[{'reason':'post_detail_not_loaded'},{'item':{'id':'123','author':'user','images':[{'src':'https://pbs.twimg.com/media/new','ref':'fresh'}]}}]
    async def call(*a):return answers.pop(0)
    fresh,reason=await x_detail(NS(call_json=call),{'id':'123'},'user')
    assert fresh['images'][0]['ref']=='fresh' and reason is None
    calls=[]
    async def wrong(*a):calls.append(1);return {'reason':'post_detail_identity_mismatch'}
    fresh,reason=await x_detail(NS(call_json=wrong),{'id':'123'},'user')
    assert fresh is None and reason=='post_detail_identity_mismatch' and len(calls)==1

@pytest.mark.asyncio
async def test_observed_x_cdn_image_reacquires_pixels_without_stale_ref_or_video_playback(monkeypatch):
    from ai2apps.browser.social_media import IMAGE_DOCUMENT
    media=reviewer();media.inputs['platform']='x';visits=[]
    async def sleep(*a):pass
    monkeypatch.setattr('ai2apps.browser.social_media.asyncio.sleep',sleep)
    async def query(script,*args):return {'x':0,'y':0,'width':100,'height':100} if script==IMAGE_DOCUMENT else None
    async def navigate(url):visits.append(url)
    async def capture(*a,**kw):return {'data':picture()}
    page=NS(call_json=query,navigate=navigate,context_id='same-default-context',connection=NS(command=capture))
    image={'src':'https://pbs.twimg.com/media/observed.jpg','ref':'stale'}
    result,partial=await media.capture(page,image)
    assert result['data'] and not partial and visits==[image['src']]
    assert image['readback']=='observed_image_document'
    for url in ['https://evil.test/media/a','https://pbs.twimg.com.evil.test/media/a','https://pbs.twimg.com/video/a','https://user:pass@pbs.twimg.com/media/a']:
        assert (await media.capture(page,{'src':url,'ref':'stale'}))[0] is None
    assert len(visits)==1

def test_media_coverage_empty_posts_are_complete_and_unseen_reasons_are_counted():
    media=reviewer();empty={'id':'text-only','images':[]};media.annotate(empty)
    assert media.summary([empty])['complete']
    missing={'id':'missing','images':[{'src':'https://example.com/a','index':0,'unseen_reason':'post_media_not_loaded'}]};media.annotate(missing)
    result=media.summary([empty,missing]);assert result['seen']==0 and result['unseen']==1
    assert result['unseen_reasons']=={'post_media_not_loaded':1} and not result['complete']

@pytest.mark.asyncio
async def test_detail_quote_media_is_not_required_to_belong_to_reply(monkeypatch):
    from ai2apps.browser.social import x_detail
    calls=[]
    async def call(*args):
        calls.append(args)
        return {'item':{'id':'20','images':[],'related_posts':[{'id':'10','images':[{'src':'https://pbs.twimg.com/media/original.jpg'}]}]}}
    fresh,reason=await x_detail(NS(call_json=call),{'id':'20','images':[{'src':'timeline-quote'}]},'reader')
    assert reason is None and fresh['related_posts'][0]['id']=='10' and len(calls)==1

@pytest.mark.asyncio
async def test_original_card_reads_observed_destination_and_rejects_source_or_foreign_url(monkeypatch):
    from ai2apps.browser import social
    async def sleep(*a):pass
    monkeypatch.setattr(social.asyncio,'sleep',sleep)
    calls=[]
    class Page:
        destination='https://x.com/original/status/10'
        async def call_json(self,script,args=None):
            if script==social.X_ORIGINAL_TARGET_SCRIPT:return {'rect':{'x':0,'y':0,'width':10,'height':10}}
            return {'url':self.destination}
        async def pointer_to(self,target):calls.append(target)
    async def detail(page,item,author):return {**item,'author':author,'text':'original','images':[],'related_posts':[{'id':'ancestor'}]},None
    monkeypatch.setattr(social,'x_detail',detail)
    page=Page();related={'relation':'quoted','observed_ref':'bound-card','images':[{'src':'https://pbs.twimg.com/media/observed.jpg','ref':'stale'}]}
    await social.x_original_card(page,related,'20')
    assert related['id']=='10' and related['author']=='original' and related['context_status']=='observed'
    assert 'related_posts' not in related and 'observed_ref' not in related
    assert related['images'][0]['ref']=='' and related['images'][0]['detail_read_reason']=='original_media_not_loaded'
    for url in ('https://evil.test/original/status/10','https://x.com/source/status/20','https://x.com/original'):
        page.destination=url;related={'relation':'quoted','observed_ref':'bound-card'}
        await social.x_original_card(page,related,'20')
        assert 'id' not in related and related['reason']=='original_card_navigation_unverified'
