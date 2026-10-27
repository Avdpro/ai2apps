"""Automatic synthesis must explicitly decide how to use paragraph-bound photos."""
from pathlib import Path
import json
import pytest
from ai2apps.intelligence import service, article_content, manual_layout
from ai2apps.intelligence.store import IntelligenceStore

URL='https://example.org/original'
IMAGE='https://example.org/factory.jpg'

def source():
    return {'url':URL,'title':'Factory visit','text':'The author visited the factory and discussed production technology.',
      'source_name':'Source','retrieved_at':'now','images':[{'url':IMAGE,'alt':'factory 7'}],
      'source_blocks':[{'type':'paragraph','id':'sp_0','text':'The author visited the factory and discussed production technology.'},
                       {'type':'image','url':IMAGE,'paragraph_id':'sp_0','alt':'factory 7'}]}


@pytest.mark.asyncio
@pytest.mark.parametrize('decision',['place','explain','omit'])
async def test_automatic_images_need_placement_or_explicit_reason(monkeypatch,decision):
    async def model(*args,**kwargs):
        payload=args[-2];assert payload['available_images'][0]['near_text'].startswith('The author visited')
        item={'title':'Visit','summary':'Factory','body':'Author visited the factory. [1]','evidence_ids':[1]}
        if decision=='place':item['image_placements']=[{'image_id':payload['available_images'][0]['id'],'after_paragraph':0}]
        if decision=='explain':item['image_omission_reason']='The only photo context concerns a different product variant; correspondence is uncertain.'
        return args[-1]({'articles':[item]})
    monkeypatch.setattr(service,'model_json',model)
    call=service.digest_event(None,None,None,{'id':'c'},[source()],[])
    if decision=='omit':
        with pytest.raises(ValueError,match='Do not silently omit'):await call
    else:
        article=(await call)[0]
        assert sum(b['type']=='image' for b in article['content_blocks'])==(1 if decision=='place' else 0)
        article_content.validate_content(article)


@pytest.mark.asyncio
async def test_legacy_sources_without_positions_remain_compatible(monkeypatch):
    async def model(*args,**kwargs):return args[-1]({'articles':[{'title':'Visit','summary':'s','body':'Facts [1]','evidence_ids':[1]}]})
    monkeypatch.setattr(service,'model_json',model)
    page=source();page.pop('source_blocks')
    assert (await service.digest_event(None,None,None,{'id':'c'},[page],[]))[0]['body']=='Facts [1]'


def test_automatic_layout_repair_checks_source_owner_and_body_revision(tmp_path):
    store=IntelligenceStore(tmp_path);channel=store.save_channel('owner',{'name':'Factory','interval_hours':0})
    article={'title':'Visit','body':'Author visited the factory. [1]','sources':[{'url':URL}], 'images':[]}
    with store.connect() as db:db.execute('INSERT INTO articles VALUES(?,?,?,?)',('auto','owner',channel['id'],json.dumps(article)))
    old=store.get('articles','owner','auto');blocks,_=__import__('ai2apps.intelligence.article_merge',fromlist=['structure']).structure(old)
    mapping={'sp_0':blocks[0]['id']};signature=manual_layout.signature(old)
    with pytest.raises(KeyError):store.save_source_layout('foreign','auto',signature,source()['source_blocks'],mapping)
    with pytest.raises(ValueError,match='belong'):store.save_source_layout('owner','auto',signature,source()['source_blocks'],mapping,source_url='https://example.org/foreign')
    with pytest.raises(ValueError,match='manual'):store.save_manual_layout('owner','auto',signature,source()['source_blocks'],mapping)
    result=store.save_source_layout('owner','auto',signature,source()['source_blocks'],mapping,source_url=URL)
    assert result['body']==old['body'] and not result.get('manual_import')
    assert sum(b['type']=='image' for b in result['content_blocks'])==1
    article_content.validate_content(result)
