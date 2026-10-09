import pytest
from ai2apps.intelligence.models import SourceInput, ChannelInput
from ai2apps.intelligence.store import IntelligenceStore


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
