import pytest
from ai2apps.intelligence.store import IntelligenceStore


def test_section_order_persists_and_validates(tmp_path):
    store = IntelligenceStore(tmp_path)
    sections = [{'id': 'a', 'name': '新品'}, {'id': 'b', 'name': '评测'}]
    channel = store.save_channel('owner', {'name': '腕表', 'interval_hours': 0, 'sections': sections})
    store.reorder_sections('owner', channel['id'], ['b', 'a'])
    assert store.get('channels', 'owner', channel['id'])['sections'] == sections[::-1]
    for invalid in [['a'], ['a', 'a'], ['a', 'unknown']]:
        with pytest.raises(ValueError):
            store.reorder_sections('owner', channel['id'], invalid)
    with pytest.raises(KeyError):
        store.reorder_sections('other', channel['id'], ['a', 'b'])
    assert store.get('channels', 'owner', channel['id'])['sections'] == sections[::-1]


def test_edit_sections_preserves_articles_and_rejects_stale_changes(tmp_path):
    store = IntelligenceStore(tmp_path)
    sections = [{'id':'a','name':'新品','description':'发布'}, {'id':'b','name':'评测','description':'体验'}]
    c = store.save_channel('owner', {'name':'Watch','interval_hours':0,'sections':sections})
    a = store.import_article('owner',c['id'], {'title':'A','summary':'A','body':'A','sources':[], 'section_id':'a'},'a')
    changed = [{'id':'b','name':'上手','description':'深入评测'}, {'id':'c','name':'市场','description':'价格'}]
    store.save_channel('owner',{'interval_hours':0,'sections':changed,'expected_sections':sections},c['id'])
    assert store.get('articles','owner',a['id'])['section_id'] is None
    assert store.get('articles','owner',a['id'])['body'] == 'A'
    assert store.get('channels','owner',c['id'])['sections'] == changed
    with pytest.raises(ValueError):
        store.save_channel('owner',{'interval_hours':0,'sections':sections,'expected_sections':sections},c['id'])
    store.save_channel('owner',{'interval_hours':0,'name':'Renamed'},c['id'])
    assert store.get('channels','owner',c['id'])['sections'] == changed


def test_section_validation():
    from ai2apps.intelligence.models import ChannelInput
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ChannelInput(name='Watch',interests='Watch',sections=[{'id':'a','name':' ','description':'test'}])
    with pytest.raises(ValidationError):
        ChannelInput(name='Watch',interests='Watch',sections=[{'id':str(i),'name':'Same','description':'test'} for i in range(2)])
