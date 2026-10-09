import pytest
from PIL import Image
from ai2apps.intelligence import manual_import
from ai2apps.intelligence.store import IntelligenceStore


def test_import_deduplicates_per_channel_and_queues_knowledge(tmp_path):
    store = IntelligenceStore(tmp_path)
    c = store.save_channel('a', {'name':'Test', 'interval_hours':0, 'knowledge_bucket_ids':['bucket']})
    article = dict(title='Title', summary='Summary', body='Full text', sources=[{'url':'https://example.com/a'}])
    first = store.import_article('a',c['id'],article,'https://example.com/a')
    second = store.import_article('a',c['id'],article,'https://example.com/a')
    assert first['id'] == second['id']
    assert first['manual_import']
    assert len(store.knowledge_jobs('a',c['id'])) == 1
    with pytest.raises(KeyError):
        store.import_article('b',c['id'],article,'x')


def test_file_parsing_and_asset_isolation(tmp_path):
    md = tmp_path/'a.md'; md.write_text('# 标题\n\n内容')
    assert '内容' in manual_import.parse_file(md,'a.md')[0]
    image = tmp_path/'a.png'; Image.new('RGB',(4,4)).save(image)
    assert manual_import.parse_file(image,'a.png')[1] == 'image'
    with pytest.raises(Exception):
        manual_import.parse_file(md,'bad.png')
    store = IntelligenceStore(tmp_path/'store')
    assert manual_import.asset_path(store,'a','a'*64) != manual_import.asset_path(store,'b','a'*64)
    with pytest.raises(ValueError):
        manual_import.asset_path(store,'a','../bad')

from ai2apps.tests.test_intelligence_api import client
from ai2apps.intelligence import service


def test_manual_import_routes(client, monkeypatch):
    async def classify(runtime, request, principal, channel, sections, articles):
        return {'manual': sections[0]['id']}
    monkeypatch.setattr(service, 'classify_articles', classify)
    c = client.post('/intelligence/channels',json={'name':'腕表','interests':'机芯新品'}).json()
    base = '/intelligence/channels/' + c['id']
    result = client.post(base+'/import-file', files={'file':('notes.md', '# Notes\n\nOriginal text', 'text/markdown')})
    assert result.status_code == 200, result.text
    article = result.json()
    assert 'Original text' in article['body']
    resource = article['sources'][0]['url'].removeprefix('/v1/platform')
    download = client.get(resource)
    assert download.status_code == 200
    assert 'Original text' in download.text
    body = {'page': {'source_id':'','url':'https://example.com/story','title':'Story','text':'Full article'}}
    result = client.post(base+'/import-url',json=body)
    assert result.status_code == 200, result.text
    assert client.post(base+'/import-url',json=body).json()['id'] == result.json()['id']
    assert client.post(base+'/import-file',files={'file':('bad.png',b'not image','image/png')}).status_code == 422


def test_image_summary_is_opt_in_and_upgrades_original(client, monkeypatch):
    import io
    async def classify(runtime, request, principal, channel, sections, articles):
        return {'manual': sections[0]['id']}
    monkeypatch.setattr(service, 'classify_articles', classify)
    calls = []
    async def summarize(*args):
        calls.append(True)
        return {'title':'图中腕表','summary':'可见表盘','body':'只描述可见内容'}
    monkeypatch.setattr(manual_import, 'summarize_image', summarize)
    c = client.post('/intelligence/channels',json={'name':'腕表','interests':'新品'}).json()
    url = '/intelligence/channels/'+c['id']+'/import-file'
    output = io.BytesIO(); Image.new('RGB',(4,4)).save(output,format='PNG')
    files = {'file':('watch.png',output.getvalue(),'image/png')}
    original = client.post(url,files=files).json()
    assert not calls and not original.get('image_ai_summary')
    result = client.post(url,files=files,data={'summarize_image':'true'})
    assert result.status_code == 200, result.text
    assert calls and result.json()['id'] == original['id']
    assert result.json()['image_ai_summary'] and result.json()['body'] == '只描述可见内容'
