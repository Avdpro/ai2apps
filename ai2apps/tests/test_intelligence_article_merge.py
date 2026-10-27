"""Incremental composition fixtures; no live model calls."""
import copy
from types import SimpleNamespace as NS
import pytest
from ai2apps.intelligence import article_merge as merge, article_content as content, service, manual_import
from ai2apps.intelligence.models import ArticleDraft
from ai2apps.intelligence.store import IntelligenceStore

URL='https://example.com/specialist'
NEW='https://example.com/roundup'
IMAGE='https://example.com/movement.jpg'

def previous():
    old={'id':'old','title':'Watch A','summary':'Watch A review','body':'Movement detail [1]\n\nComfort detail [1]',
         'sources':[{'url':URL,'title':'Watch A review','source_name':'Review','retrieved_at':'now'}],
         'images':[{'id':content.image_id(URL,IMAGE),'url':IMAGE,'source_url':URL,'alt':'movement'}],
         'cover_image':{'url':'https://example.com/cover.jpg','source_url':URL},
         'editorial_basis':{'source_url':URL,'subject':'Watch A','detail_score':4}}
    old['content_blocks'],old['editorial_sections']=merge.structure(old,['Movement','Wear'])
    old['content_blocks'].insert(1,{'type':'image','image_id':old['images'][0]['id'],'paragraph_id':old['content_blocks'][0]['id']})
    old['content_schema']=merge.SCHEMA
    return old

def page():return {'url':NEW,'title':'Roundup Watch A','text':'Watch A now has a blue dial.', 'image_url':'https://example.com/new.jpg','images':[], 'source_name':'News','retrieved_at':'now'}

def draft(**kw):return ArticleDraft.model_validate({'title':'Watch A','summary':'s','evidence_ids':[1],'update_article_id':'old',**kw})

def test_legacy_upgrade_stable_ids_and_source_remap():
    old=previous();pages,contexts=merge.prepare([old],[page()])
    context=contexts['old']
    assert context['blocks'][0]['id']==old['content_blocks'][0]['id']
    assert context['blocks'][0]['text']=='Movement detail [2]'
    assert pages[1]['retained_only']
    item=draft();blocks,sections,audit=merge.apply(item,context,pages,{})
    assert item.body=='Movement detail [2]\n\nComfort detail [2]'
    assert item.evidence_ids==[1,2] and blocks[1]['image_id']==old['images'][0]['id']


def test_patch_additions_keep_order_and_untouched_images():
    old=previous();pages,contexts=merge.prepare([old],[page()]);context=contexts['old'];pid=context['blocks'][0]['id']
    item=draft(merge_changes=[{'operation':'add','after_id':pid,'text':t+' [1]','section_title':'Dial','reason':'new detail','proofs':[{'evidence_id':1,'quote':'now has a blue dial'}]} for t in ('Blue dial','Dial update')])
    blocks,sections,audit=merge.apply(item,context,pages,{})
    assert [b['text'] for b in blocks if b['type']=='paragraph']==['Movement detail [2]','Blue dial [1]','Dial update [1]','Comfort detail [2]']
    assert blocks[1]['type']=='image' and len(audit)==2


@pytest.mark.parametrize('proof,match',[('invented original quote','absent'),('',None)])
def test_new_assertions_require_original_proof(proof,match):
    pages,contexts=merge.prepare([previous()],[page()])
    kwargs={'proofs':[{'evidence_id':1,'quote':proof}]} if proof else {}
    item=draft(merge_changes=[{'operation':'add','text':'Blue [1]','reason':'new',**kwargs}])
    with pytest.raises(ValueError):merge.apply(item,contexts['old'],pages,{})


@pytest.mark.asyncio
@pytest.mark.parametrize('focus,new_cover',[('mention',False),('uncertain',False),('dedicated',True)])
async def test_cover_policy_and_preserved_layout(monkeypatch,focus,new_cover):
    old=previous()
    async def model(*args,**kwargs):
        data=args[-2];assert data['previous_articles'][0]['canonical_body']=='Movement detail [2]\n\nComfort detail [2]'
        return args[-1]({'articles':[{'title':'Watch A','summary':'s','evidence_ids':[1,2],'primary_evidence_id':2,'update_article_id':'old',
          'source_focus':[{'evidence_id':1,'focus':focus,'subject_quote':'Watch A','detail_score':3,'reason':'scope'}]}]})
    monkeypatch.setattr(service,'model_json',model)
    result=(await service.digest_event(None,None,None,{'id':'c'},[page()],[old],{'evidence_ids':[1],'section_id':None,'update_article_id':'old'}))[0]
    assert result['cover_image']['url']==('https://example.com/new.jpg' if new_cover else old['cover_image']['url'])
    assert result['editorial_basis']==old['editorial_basis']
    assert result['content_blocks'][0]['id']==old['content_blocks'][0]['id']
    assert result['content_blocks'][1]['image_id']==old['images'][0]['id']
    assert result['body']=='Movement detail [2]\n\nComfort detail [2]'
    content.validate_content(result)


def test_manual_forced_backbone_cannot_be_replaced_or_reorganized():
    old=previous();old['_forced_backbone']=URL
    pages,contexts=merge.prepare([old],[page()]);pid=contexts['old']['blocks'][0]['id']
    for op in ('remove','replace','move'):
        item=draft(merge_changes=[{'operation':op,'paragraph_id':pid,'text':'Blue [1]','reason':'change','proofs':[{'evidence_id':1,'quote':'now has a blue dial'}]}])
        with pytest.raises(ValueError,match='Manual import'):merge.apply(item,contexts['old'],pages,{})


def test_manual_import_not_absorbed_by_auto_article(tmp_path):
    store=IntelligenceStore(tmp_path);channel=store.save_channel('owner',{'name':'Watches','interval_hours':0})
    import json
    auto=previous()
    with store.connect() as db:db.execute('INSERT INTO articles VALUES(?,?,?,?)',('old','owner',channel['id'],json.dumps(auto)))
    article={'title':'Manual','summary':'s','body':'User selected original','sources':[{'url':URL}], 'manual_backbone':True}
    manual=store.import_article('owner',channel['id'],article,URL)
    assert manual['manual_import'] and len(store.snapshot('owner')['articles'])==2
    assert store.import_article('owner',channel['id'],article,URL)['id']==manual['id']


@pytest.mark.asyncio
async def test_manual_no_reference_still_creates_source_bound_backbone(tmp_path):
    store=IntelligenceStore(tmp_path);channel=store.save_channel('owner',{'name':'Watches','interval_hours':0})
    article={'title':'Specialist','body':'Full translated detail','summary':'s','sources':[{'url':URL}], 'images':[], 'original_content':{'body':'Original text'}}
    result=await manual_import.compose_backbone(None,None,NS(actor_user_id='owner'),channel,article,store)
    assert result['manual_backbone'] and result['editorial_basis']['source_url']==URL
    assert result['body']=='Full translated detail [1]' and 'id' not in result
    content.validate_content(result)

@pytest.mark.asyncio
@pytest.mark.parametrize('cached',[True,False])
async def test_manual_related_originals_only_supplement_selected_source(tmp_path,monkeypatch,cached):
    import json
    store=IntelligenceStore(tmp_path);channel=store.save_channel('owner',{'name':'Watches','interval_hours':0})
    old=previous();old['title']='Watch A review';old['channel_id']=channel['id']
    if not cached:old.update(manual_import=True,original_content={'body':'Watch A has a precise movement.'})
    with store.connect() as db:
        db.execute('INSERT INTO articles VALUES(?,?,?,?)',('old','owner',channel['id'],json.dumps(old)))
        if cached:db.execute('INSERT INTO pages VALUES(?,?,?,?,?)',('owner',channel['id'],URL,'h',json.dumps({'url':URL,'text':'Watch A has a precise movement.','title':'Watch A review','source_name':'Review','retrieved_at':'now','image_url':'https://example.com/oldcover.jpg'})))
    async def model(*args,**kwargs):
        data=args[-2];assert data['planned_event']['update_article_id']=='manual-seed'
        assert len(data['evidence'])==2 and data['evidence'][1]['text']=='Watch A has a precise movement.'
        assert data['previous_articles'][0]['editorial_basis']['forced_manual']
        pid=data['previous_articles'][0]['paragraphs'][0]['id']
        return args[-1]({'articles':[{'title':'Watch A selected article','summary':'s','update_article_id':'manual-seed',
          'evidence_ids':[1,2],'primary_evidence_id':2,'source_focus':[{'evidence_id':i,'focus':'dedicated','subject_quote':'Watch A','detail_score':5,'reason':'Exact watch'} for i in [1,2]],
          'merge_changes':[{'operation':'add','after_id':pid,'text':'Precise movement [2]','reason':'supplement','proofs':[{'evidence_id':2,'quote':'has a precise movement'}]}]}]})
    monkeypatch.setattr(service,'model_json',model)
    article={'import_requested_url':'https://example.com/redirect','title':'Watch A selected article','body':'Selected full translation','summary':'Watch A','sources':[{'url':NEW,'title':'Watch A selected article','source_name':'Selected','retrieved_at':'now','profile_key':'owner-profile'}], 'cover_image':{'url':'https://example.com/selected.jpg','source_url':NEW},'images':[],'original_content':{'body':'Watch A selected original'}}
    result=await manual_import.compose_backbone(None,None,NS(actor_user_id='owner'),channel,article,store)
    assert result['body']=='Selected full translation [1]\n\nPrecise movement [2]'
    assert result['cover_image']==article['cover_image'] and result['primary_source_url']==NEW
    assert result['editorial_basis']['source_url']==NEW and result['sources'][0]['profile_key']=='owner-profile'
    assert result['manual_backbone'] and not result.get('update_article_id')
    assert result['import_requested_url']=='https://example.com/redirect'
    content.validate_content(result)


def test_legacy_manual_reimport_adopts_backbone_once_without_losing_user_state(tmp_path):
    store=IntelligenceStore(tmp_path);channel=store.save_channel('owner',{'name':'Watches','interval_hours':0})
    old=store.import_article('owner',channel['id'],{'title':'Old','body':'Old','sources':[{'url':URL}], 'ai_translation':True},URL)
    new=previous();new.pop('id');new['manual_backbone']=True
    result=store.import_article('owner',channel['id'],new,URL)
    assert result['id']==old['id'] and result['manual_backbone'] and result['body']==new['body']
    content.validate_content(result)
    assert len(store.snapshot('owner')['articles'])==1


def test_source_image_nearby_text_is_only_a_hint_for_collected_images():
    p=page();p['images']=[{'url':IMAGE,'alt':'Movement'}]
    p['source_blocks']=[{'type':'paragraph','id':'sp_0','text':'Original movement paragraph'},
       {'type':'image','url':IMAGE,'paragraph_id':'sp_0'},
       {'type':'image','url':'https://example.com/not-collected.jpg','paragraph_id':'sp_0'}]
    catalog=content.image_catalog([p])
    assert catalog[content.image_id(NEW,IMAGE)]['near_text']=='Original movement paragraph'
    assert all(i['url']!='https://example.com/not-collected.jpg' for i in catalog.values())
