import json
import pytest
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.intelligence import posts


def test_draft_pages_are_twenty_latest_first_and_owner_scoped(tmp_path):
    store=IntelligenceStore(tmp_path)
    channel=store.save_channel('owner',{'name':'AI','interests':'AI','interval_hours':0})
    with store.connect() as db:
        for n in range(45):
            draft={'id':f'd{n:02}','channel_id':channel['id'],'title':str(n),'updated_at':f'2026-10-15T00:00:{n:02}Z','content':'Draft'}
            db.execute('INSERT INTO drafts VALUES(?,?,?,?)',('owner',channel['id'],draft['id'],json.dumps(draft)))
    first=store.draft_page('owner',channel['id'])
    second=store.draft_page('owner',channel['id'],first['next_offset'])
    last=store.draft_page('owner',channel['id'],second['next_offset'])
    assert [len(p['items']) for p in [first,second,last]]==[20,20,5]
    assert first['items'][0]['id']=='d44' and last['next_offset'] is None
    assert len({d['id'] for p in [first,second,last] for d in p['items']})==45
    with pytest.raises(KeyError):store.draft_page('other',channel['id'])


def test_x_archive_loads_twenty_per_page(tmp_path):
    store=IntelligenceStore(tmp_path)
    channel=store.save_channel('owner',{'name':'AI','interests':'AI','interval_hours':0})
    with store.connect() as db:
        for n in range(21):
            page={'url':f'https://x.com/a/status/{n}','platform':'x','text':'Post'}
            db.execute('INSERT INTO pages VALUES(?,?,?,?,?)',('owner',channel['id'],page['url'],'hash',json.dumps(page)))
    first=posts.list_posts(store,'owner',channel['id'])
    last=posts.list_posts(store,'owner',channel['id'],first['next_offset'])
    assert len(first['items'])==20 and first['next_offset']==20
    assert len(last['items'])==1 and last['next_offset'] is None
