import copy
import pytest
from pydantic import ValidationError
from ai2apps.intelligence import service, article_content
from ai2apps.intelligence.models import ArticleDraft, ChannelInput
from ai2apps.intelligence.store import IntelligenceStore


def pages():
    return [dict(url='https://example.org/'+str(i), title='Source '+str(i),source_name='Source',retrieved_at='now',text='A report about the watch.',
                 images=[{'url':'https://cdn.example.org/'+str(i)+'.jpg','alt':'Dial detail'}]) for i in (1,2)]


async def generate(monkeypatch,placement,refs=None):
    data=pages(); key=article_content.image_id(data[1]['url'],data[1]['images'][0]['url'])
    async def model(runtime,request,principal,channel,instruction,payload,validate,**kwargs):
        assert any(i['id']==key for i in payload['available_images'])
        assert all('images' not in p for p in payload['evidence'])
        return validate({'articles':[{'title':'Report','summary':'Summary','body':'First paragraph.[2]\n\nSecond paragraph.[2]',
          'evidence_ids':refs or [2], 'primary_evidence_id':2,'image_placements':placement(key)}]})
    monkeypatch.setattr(service,'model_json',model)
    return (await service.digest_event(None,None,None,{'id':'c'},data,[]))[0]


@pytest.mark.asyncio
async def test_multi_source_placement_resolves_known_image_and_renumbers_text(monkeypatch):
    article=await generate(monkeypatch,lambda key:[{'after_paragraph':0,'image_id':key}])
    assert article['body']=='First paragraph.[1]\n\nSecond paragraph.[1]'
    blocks=article['content_blocks'];assert [b['type'] for b in blocks]==['paragraph','image','paragraph']
    assert blocks[0]['text']=='First paragraph.[1]'
    assert article['images'][0]['source_url']=='https://example.org/2'
    assert article['images'][0]['id']==blocks[1]['image_id']
    article_content.validate_content(article)


@pytest.mark.asyncio
@pytest.mark.parametrize('kind',['invented','wrong_source','bad_index','duplicate','url_field','paragraph_source'])
async def test_invalid_placement_is_rejected_by_model_validator(monkeypatch,kind):
    def placement(key):
        entry={'after_paragraph':0,'image_id':key}
        if kind=='invented':entry['image_id']='img_'+'0'*24
        if kind=='wrong_source':entry['image_id']=article_content.image_id('https://example.org/1','https://cdn.example.org/1.jpg')
        if kind=='bad_index':entry['after_paragraph']=2
        if kind=='url_field':entry['url']='https://evil.example/image.jpg'
        if kind=='paragraph_source':entry['image_id']=article_content.image_id('https://example.org/1','https://cdn.example.org/1.jpg')
        return [entry,entry] if kind=='duplicate' else [entry]
    with pytest.raises((ValueError,ValidationError)):
        await generate(monkeypatch,placement,refs=[1,2] if kind=='paragraph_source' else None)


@pytest.mark.asyncio
async def test_legacy_text_generation_remains_compatible(monkeypatch):
    article=await generate(monkeypatch,lambda key:[])
    assert all(b['type']=='paragraph' for b in article['content_blocks'])
    assert article['body'].endswith('[1]')


@pytest.mark.asyncio
async def test_storage_roundtrip_history_plain_update_and_gallery_recovery(tmp_path,monkeypatch):
    article=await generate(monkeypatch,lambda key:[{'after_paragraph':0,'image_id':key}])
    store=IntelligenceStore(tmp_path);channel=store.save_channel('owner',ChannelInput(name='News',interests='Watches',interval_hours=0).model_dump())
    store.save_source('owner',channel['id'],{'name':'Source','url':'https://example.org/news','kind':'website','enabled':True})
    run=store.claim('owner',channel['id']);store.finish('owner',run['id'],[],[copy.deepcopy(article)],[])
    saved=store.snapshot('owner')['articles'][0]
    assert saved['content_blocks']==article['content_blocks']
    store.save_images('owner',saved['id'],'https://example.org/2',[{'url':'https://cdn.example.org/new.jpg'}])
    refreshed=store.get('articles','owner',saved['id']);article_content.validate_content(refreshed)
    assert article['images'][0] in refreshed['images']
    run=store.claim('owner',channel['id'])
    store.finish('owner',run['id'],[],[{'title':'Update','summary':'New','body':'Plain update [1]','sources':article['sources'],'update_article_id':saved['id']}],[])
    changed=store.get('articles','owner',saved['id'])
    assert 'content_blocks' not in changed
    assert changed['versions'][-1]['content_blocks']==article['content_blocks']
    assert changed['versions'][-1]['images']
    with pytest.raises(KeyError):store.get('articles','other',saved['id'])


@pytest.mark.asyncio
async def test_storage_rejects_text_drift_or_unrelated_source(tmp_path,monkeypatch):
    article=await generate(monkeypatch,lambda key:[{'after_paragraph':0,'image_id':key}])
    for bad in ['body','sources','url']:
        value=copy.deepcopy(article)
        if bad=='body':value['body']='Different body [1]'
        elif bad=='sources':value['sources']=[]
        else:value['images'][0]['url']='javascript:alert(1)'
        with pytest.raises(ValueError):article_content.validate_content(value)
