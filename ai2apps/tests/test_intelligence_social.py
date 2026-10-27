import pytest
from ai2apps.intelligence.models import SourceInput, ChannelInput
from ai2apps.intelligence.store import IntelligenceStore


def test_fifteen_minute_social_interval_persists_and_does_not_extend_on_skip(tmp_path):
    import time
    store = IntelligenceStore(tmp_path)
    channel = store.save_channel('alice', ChannelInput(name='AI', interests='news').model_dump())
    source = SourceInput(name='OpenAI', url='https://youtube.com/@OpenAI', social_interval_hours=0.25)
    saved = store.save_source('alice', channel['id'], source.model_dump())
    before = time.time()
    admitted = store.claim_social('alice', saved['id'])
    assert admitted['allowed']
    assert before + 900 <= admitted['next_at'] <= time.time() + 900
    store.finish_social('alice', saved['id'], admitted['token'], 'success')
    reopened = IntelligenceStore(tmp_path)
    assert reopened.get('sources', 'alice', saved['id'])['social_interval_hours'] == 0.25
    deferred = reopened.claim_social('alice', saved['id'])
    assert not deferred['allowed']
    assert deferred['next_at'] == admitted['next_at']


def test_youtube_source_normalizes_stable_video_ids_and_channel_tabs():
    s=SourceInput(name='OpenAI',url='https://youtube.com/@OpenAI')
    assert s.kind=='social' and s.url=='https://www.youtube.com/@OpenAI/videos'
    for url in ['https://youtu.be/abcdefghijk?t=20','https://www.youtube.com/shorts/abcdefghijk','https://youtube.com/watch?v=abcdefghijk&list=anything']:
        assert SourceInput(name='Video',url=url).url=='https://www.youtube.com/watch?v=abcdefghijk'
    with pytest.raises(ValueError):SourceInput(name='wrong',url='https://www.youtube.com/')
    with pytest.raises(ValueError):SourceInput(name='wrong',url='https://youtube.com/watch?v=bad')


def test_social_cooldown_serialization_persistence_owner_and_backoff(tmp_path):
    store=IntelligenceStore(tmp_path)
    c=store.save_channel('alice',ChannelInput(name='AI',interests='发布').model_dump())
    source=SourceInput(name='OpenAI',url='https://youtube.com/@OpenAI',social_interval_hours=1).model_dump()
    a=store.save_source('alice',c['id'],source)
    b=store.save_source('alice',c['id'],{**source,'name':'Other','url':'https://www.youtube.com/@Other/videos','profile_key':'a'*32})
    lease=store.claim_social('alice',a['id']);assert lease['allowed']
    assert not store.claim_social('alice',a['id'])['allowed']
    assert not store.claim_social('alice',b['id'])['allowed'] # platform lock crosses Profiles
    with pytest.raises(KeyError):store.claim_social('bob',a['id'])
    with pytest.raises(ValueError):store.finish_social('alice',a['id'],'wrong','success')
    result=store.finish_social('alice',a['id'],lease['token'],'needs_user');assert result['paused']
    store=IntelligenceStore(tmp_path)
    assert not store.claim_social('alice',a['id'])['allowed']
    store.save_source('alice',c['id'],source,a['id'])
    assert store.get('sources','alice',a['id'])['social_paused']
    store.resume_social('alice',a['id'])
    assert not store.claim_social('alice',a['id'])['allowed'] # resume never removes cooldown


def test_youtube_search_and_topic_sources_preserve_query_and_filters():
    from urllib.parse import parse_qs, urlsplit
    search=SourceInput(name='腕表',url='https://youtube.com/results?search_query=%E8%85%95%E8%A1%A8&sp=CAI%3D&utm_source=test')
    assert search.kind=='social'
    assert parse_qs(urlsplit(search.url).query)=={'search_query':['腕表'],'sp':['CAI=']}
    assert SourceInput(name='topic',url='https://www.youtube.com/hashtag/watches').url=='https://www.youtube.com/hashtag/watches'
    for url in ['https://youtube.com/results','https://youtube.com/results?search_query=%20','https://youtube.com/hashtag/','https://youtube.com/hashtag/a%2Fb']:
        with pytest.raises(ValueError):SourceInput(name='invalid',url=url)


def test_weibo_account_topic_and_shared_platform_identity():
    from ai2apps.intelligence.social import site_key
    from urllib.parse import parse_qs, urlsplit
    account=SourceInput(name='RADO',url='https://weibo.com/1938210792?refer=search')
    assert account.kind=='social' and account.url=='https://weibo.com/u/1938210792'
    topic=SourceInput(name='腕表',url='https://s.weibo.com/weibo?q=%23%E8%85%95%E8%A1%A8%23&Refer=index')
    assert parse_qs(urlsplit(topic.url).query)=={'q':['#腕表#']}
    assert site_key(account.model_dump())==site_key(topic.model_dump())=='weibo.com'
    for url in ['https://weibo.com/','https://weibo.com/u/notuid','https://s.weibo.com/weibo?q=','https://weibo.com/1938210792/RgmEW4ck2']:
        with pytest.raises(ValueError):SourceInput(name='invalid',url=url)


def test_pre_navigation_browser_failure_releases_only_its_reservation(tmp_path):
    store=IntelligenceStore(tmp_path);c=store.save_channel('alice',ChannelInput(name='test',interests='watch').model_dump())
    s=store.save_source('alice',c['id'],SourceInput(name='topic',url='https://s.weibo.com/weibo?q=watch').model_dump())
    first=store.claim_social('alice',s['id']);store.finish_social('alice',s['id'],first['token'],'not_started')
    next_run=store.claim_social('alice',s['id']);assert next_run['allowed']
    with pytest.raises(ValueError):store.finish_social('alice',s['id'],first['token'],'not_started')
    store.finish_social('alice',s['id'],next_run['token'],'failed');assert not store.claim_social('alice',s['id'])['allowed']


def test_manual_social_refresh_waits_one_minute_and_preserves_schedule(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    import ai2apps.intelligence.store as module
    clock = [100000.0]
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromtimestamp(clock[0], tz or timezone.utc)
    monkeypatch.setattr(module, 'datetime', Clock)
    store=IntelligenceStore(tmp_path)
    c=store.save_channel('alice',ChannelInput(name='test',interests='watch').model_dump())
    s=store.save_source('alice',c['id'],SourceInput(name='X',url='https://x.com/F1',x_mode='accounts',x_values=['F1']).model_dump())
    first=store.claim_social('alice',s['id'],manual=True)
    assert first['allowed']
    assert not store.claim_social('alice',s['id'],manual=True)['allowed']
    store.finish_social('alice',s['id'],first['token'],'success')
    clock[0]+=59
    assert not store.claim_social('alice',s['id'],manual=True)['allowed']
    clock[0]+=1
    assert not store.claim_social('alice',s['id'])['allowed']
    second=store.claim_social('alice',s['id'],manual=True)
    assert second['allowed']
    store.finish_social('alice',s['id'],second['token'],'failed')
    clock[0]+=59
    assert not store.claim_social('alice',s['id'],manual=True)['allowed']
    clock[0]+=1
    third=store.claim_social('alice',s['id'],manual=True)
    assert third['allowed']
    store.finish_social('alice',s['id'],third['token'],'not_started')
    assert store.claim_social('alice',s['id'],manual=True)['allowed']


def test_legacy_schedule_cooldown_does_not_block_manual_refresh(tmp_path):
    import json
    from datetime import datetime, timezone
    store=IntelligenceStore(tmp_path)
    c=store.save_channel('alice',ChannelInput(name='test',interests='watch').model_dump())
    s=store.save_source('alice',c['id'],SourceInput(name='X',url='https://x.com/F1',x_mode='accounts',x_values=['F1']).model_dump())
    now=datetime.now(timezone.utc).timestamp()
    s['social_next_at']=now+21600
    s['social_failures']=1
    with store.connect() as db:
        db.execute('UPDATE sources SET data=? WHERE owner=? AND id=?',(json.dumps(s),'alice',s['id']))
    with store.connect() as db:
        db.execute('INSERT INTO social_limits VALUES(?,?,?)',('alice','x.com',json.dumps({'source_id':s['id'],'next_at':now+3000,'lease_until':0,'token':''})))
    assert not store.claim_social('alice',s['id'])['allowed']
    assert store.claim_social('alice',s['id'],manual=True)['allowed']


@pytest.mark.parametrize('outcome',['rate_limited','needs_user'])
def test_manual_retry_keeps_explicit_platform_protection(tmp_path, outcome):
    store=IntelligenceStore(tmp_path)
    c=store.save_channel('alice',ChannelInput(name='test',interests='watch').model_dump())
    s=store.save_source('alice',c['id'],SourceInput(name='X',url='https://x.com/F1',x_mode='accounts',x_values=['F1']).model_dump())
    lease=store.claim_social('alice',s['id'],manual=True)
    store.finish_social('alice',s['id'],lease['token'],outcome)
    store.resume_social('alice',s['id'])
    assert not store.claim_social('alice',s['id'],manual=True)['allowed']


def test_xiaohongshu_sort_roundtrip(tmp_path):
    from ai2apps.intelligence.models import SourceInput
    from ai2apps.intelligence.social import xiaohongshu_search_url
    source=SourceInput(name='腕表',url='https://www.xiaohongshu.com/search_result?keyword=watch')
    assert source.kind=='social' and source.xiaohongshu_sort=='latest'
    assert xiaohongshu_search_url('https://evil.example/search_result?keyword=watch') is None
    with pytest.raises(ValueError):SourceInput(name='test',url=source.url,xiaohongshu_sort='popular')
    store=IntelligenceStore(tmp_path)
    c=store.save_channel('alice',ChannelInput(name='test',interests='test').model_dump())
    saved=store.save_source('alice',c['id'],source.model_dump())
    edited=SourceInput(**{**source.model_dump(),'xiaohongshu_sort':'general'})
    store.save_source('alice',c['id'],edited.model_dump(),saved['id'])
    assert store.get('sources','alice',saved['id'])['xiaohongshu_sort']=='general'
