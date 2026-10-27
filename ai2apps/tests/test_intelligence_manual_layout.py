from types import SimpleNamespace as NS
import pytest
from ai2apps.intelligence import manual_import, manual_layout, article_content, article_merge, service
from ai2apps.intelligence.store import IntelligenceStore

URL='https://example.com/source'

def article():
    return {'title':'Original','body':'First original paragraph.\n\nSecond original paragraph.','summary':'summary',
      'sources':[{'url':URL,'title':'Original','retrieved_at':'now','source_name':'Manual'}],
      'images':[], 'source_blocks':[{'type':'paragraph','id':'sp_0','text':'First original paragraph.'},
       {'type':'image','url':'https://example.com/first.jpg','alt':'Original first picture','paragraph_id':'sp_0'},
       {'type':'paragraph','id':'sp_2','text':'Second original paragraph.'},
       {'type':'image','url':'https://example.com/second.jpg','alt':'Original second picture','paragraph_id':'sp_2'}]}


@pytest.mark.asyncio
async def test_translation_and_manual_composition_retain_source_pictures_without_optional_placement(monkeypatch,tmp_path):
    calls=[]
    async def model(*args,**kwargs):
        assert kwargs['stage']=='translation';data=args[-2];calls.append(data)
        return args[-1]({'title':'译文','summary':'摘要','paragraphs':[{'id':p['id'],'text':'翻译 '+p['text']} for p in data['paragraphs']]})
    monkeypatch.setattr(service,'model_json',model)
    store=IntelligenceStore(tmp_path);channel=store.save_channel('owner',{'name':'Test','interval_hours':0})
    translated=await manual_import.translate_article(None,None,None,channel,article())
    result=await manual_import.compose_backbone(None,None,NS(actor_user_id='owner'),channel,translated,store)
    assert len(calls)==1  # Pictures alone never trigger another model pass.
    assert [b['type'] for b in result['content_blocks']]==['paragraph','image','paragraph','image']
    assert len(result['images'])==2 and result['original_content']['body']==article()['body']
    assert result['content_blocks'][1]['paragraph_id']==result['content_blocks'][0]['id']
    assert result['content_blocks'][3]['paragraph_id']==result['content_blocks'][2]['id']
    article_content.validate_content(result)


@pytest.mark.asyncio
@pytest.mark.parametrize('bad',['missing','reordered','merged'])
async def test_translation_refuses_lost_identity_or_paragraphs(monkeypatch,bad):
    async def model(*args,**kwargs):
        parts=[{'id':p['id'],'text':p['text']} for p in args[-2]['paragraphs']]
        if bad=='missing':parts=parts[:1]
        if bad=='reordered':parts.reverse()
        if bad=='merged':parts=[]
        return args[-1]({'title':'t','summary':'s','paragraphs':parts,'body':'Merged entire article'})
    monkeypatch.setattr(service,'model_json',model)
    with pytest.raises(ValueError):await manual_import.translate_article(None,None,None,{'id':'c'},article())


def test_complete_paragraph_batching_has_no_character_loss():
    parts=[{'id':str(i),'text':str(i)*size} for i,size in enumerate([100,5900,200,9000,20])]
    batches=list(manual_layout.batches(parts))
    assert [p for b in batches for p in b]==parts
    assert any(len(b)==1 and len(b[0]['text'])==9000 for b in batches)


def test_legacy_layout_repair_is_guarded_preserves_text_and_history(tmp_path):
    store=IntelligenceStore(tmp_path);c=store.save_channel('owner',{'name':'Test','interval_hours':0})
    data=article();data['body']='First translation [1]\n\nSecond translation [1]';data['source_blocks']=[]
    old=store.import_article('owner',c['id'],data,URL)
    blocks,_=article_merge.structure(old);mapping={'sp_0':blocks[0]['id'],'sp_2':blocks[1]['id']}
    with pytest.raises(KeyError):store.save_manual_layout('other',old['id'],manual_layout.signature(old),article()['source_blocks'],mapping)
    with pytest.raises(ValueError,match='Article changed'):store.save_manual_layout('owner',old['id'],'stale',article()['source_blocks'],mapping)
    result=store.save_manual_layout('owner',old['id'],manual_layout.signature(old),article()['source_blocks'],mapping)
    assert result['body']==old['body'] and result['sources']==old['sources'] and result['title']==old['title']
    assert result['versions'][-1]['body']==old['body']
    assert sum(b['type']=='image' for b in result['content_blocks'])==2
    article_content.validate_content(result)


def test_twenty_four_source_photos_and_cover_dedup_are_supported():
    data=article();data['body']='Translated [1]';data['translation_paragraphs']=[{'source_paragraph_id':'sp_0','text':'Translated'}]
    data['source_blocks']=[{'type':'paragraph','id':'sp_0','text':'Original'}]+[{'type':'image','url':f'https://example.com/{i}.jpg','paragraph_id':'sp_0'} for i in range(25)]
    data['cover_image']={'url':'https://example.com/0.jpg','source_url':URL}
    result=manual_layout.seed_layout(data)
    assert sum(b['type']=='image' for b in result['content_blocks'])==24
    assert not any(i['url']=='https://example.com/0.jpg' for i in result['images'])
    article_content.validate_content(result)


@pytest.mark.asyncio
async def test_legacy_text_only_client_still_imports_complete_translation(monkeypatch,tmp_path):
    async def model(*args,**kwargs):return args[-1]({'title':'Title','summary':'Summary','paragraphs':args[-2]['paragraphs']})
    monkeypatch.setattr(service,'model_json',model)
    store=IntelligenceStore(tmp_path);channel=store.save_channel('owner',{'name':'Test','interval_hours':0})
    source=article();source.pop('source_blocks')
    translated=await manual_import.translate_article(None,None,None,channel,source)
    result=await manual_import.compose_backbone(None,None,NS(actor_user_id='owner'),channel,translated,store)
    assert result['body']=='First original paragraph. [1]\n\nSecond original paragraph. [1]'
    article_content.validate_content(result)


from ai2apps.tests.test_intelligence_api import client


def test_real_import_route_saves_source_ordered_pictures_without_model_placements(client,monkeypatch):
    calls=[]
    async def model(*args,**kwargs):
        assert kwargs['stage']=='translation';calls.append(args[-2]);return args[-1]({'title':'Translated','summary':'Summary','paragraphs':args[-2]['paragraphs']})
    async def classify(runtime,request,principal,channel,sections,articles):return {'manual':sections[0]['id']}
    monkeypatch.setattr(service,'model_json',model);monkeypatch.setattr(service,'classify_articles',classify)
    channel=client.post('/intelligence/channels',json={'name':'Test','interests':'Watches'}).json()
    raw=article();result=client.post('/intelligence/channels/'+channel['id']+'/import-url',json={'page':{'source_id':'','url':URL,'title':raw['title'],'text':raw['body'],'source_blocks':raw['source_blocks']}})
    assert result.status_code==200,result.text
    saved=result.json();assert len(calls)==1
    assert [b['type'] for b in saved['content_blocks']]==['paragraph','image','paragraph','image']
    assert len(saved['images'])==2 and saved['manual_import']
    article_content.validate_content(saved)


def test_automatic_update_retains_manual_provenance_and_layout(tmp_path):
    from ai2apps.intelligence.models import SourceInput
    store=IntelligenceStore(tmp_path);c=store.save_channel('owner',{'name':'Test','interval_hours':0})
    store.save_source('owner',c['id'],SourceInput(name='News',url='https://example.com/news').model_dump())
    data=article();data['body']='Translated [1]';data['source_blocks']=[data['source_blocks'][0],data['source_blocks'][1]]
    data['translation_paragraphs']=[{'source_paragraph_id':'sp_0','text':'Translated'}];data['manual_backbone']=True
    data['editorial_basis']={'forced_manual':True,'source_url':URL,'detail_score':5};data=manual_layout.seed_layout(data)
    old=store.import_article('owner',c['id'],data,URL)
    updated={k:v for k,v in old.items() if k not in ('manual_import','manual_backbone','import_identity','source_blocks','translation_paragraphs','source_paragraph_map')}
    updated['update_article_id']=old['id'];updated['summary']='Updated summary'
    run=store.claim('owner',c['id']);store.finish('owner',run['id'],[],[updated],[])
    result=store.get('articles','owner',old['id'])
    assert result['manual_import'] and result['manual_backbone'] and result['import_identity']==URL
    assert result['source_paragraph_map']==old['source_paragraph_map'] and result['source_blocks']==old['source_blocks']
    article_content.validate_content(result)
