import pytest
from ai2apps.intelligence import entities,service
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.tests.test_intelligence_api import client,channel_and_source


def seed(store,owner,channel,text='Model A costs 100.'):
    source=store.save_source(owner,channel,{'name':'Source','url':'https://example.com/news','enabled':True,'kind':'website'})
    run=store.claim(owner,channel,False)
    store.finish(owner,run['id'],[],[{'title':'Model A','summary':text,'body':text,'sources':[{'url':'https://example.com/a'}]}],[])
    return next(a for a in store.snapshot(owner)['articles'] if a['channel_id']==channel)


def plan(name='Model A'):
    return entities.Extraction(entities=[entities.EntityDraft(name=name,kind='product',coverage='substantive',coverage_reason='The article introduces this model.',facts=[entities.Fact(text='Reported price 100',quote='Model A costs 100.')])])


def test_cross_channel_sharing_isolation_and_idempotence(tmp_path):
    store=IntelligenceStore(tmp_path);repo=entities.Repository(store)
    cs=[store.save_channel('a',{'name':str(i),'interests':'Models','interval_hours':0})['id'] for i in range(2)]
    articles=[seed(store,'a',c) for c in cs]
    for a in articles:repo.ingest('a',a,plan())
    repo.ingest('a',articles[0],plan())
    result=repo.snapshot('a')['entities']
    assert len(result)==1 and len(result[0]['facts'])==2 and set(result[0]['channel_ids'])==set(cs)
    assert repo.snapshot('b')['entities']==[]
    with pytest.raises(KeyError):repo.get('b',result[0]['id'])
    assert repo.pending('a',articles)==[]
    store.delete('channels','a',cs[0])
    assert len(repo.snapshot('a')['entities'][0]['facts'])==1


def test_manual_move_and_revision_guard(tmp_path):
    store=IntelligenceStore(tmp_path);repo=entities.Repository(store)
    c=store.save_channel('a',{'name':'c','interests':'Models','interval_hours':0})['id']
    a=seed(store,'a',c);repo.ingest('a',a,plan());e=repo.snapshot('a')['entities'][0]
    body=entities.EntitySettings(name='Model A',aliases=[],watched=True,rule='price evidence',revision=e['revision'])
    repo.settings('a',e['id'],body)
    with pytest.raises(ValueError):repo.settings('a',e['id'],body)
    target=repo.create('a','Model A variant','product');fact=e['facts'][0]['id']
    with pytest.raises(KeyError):repo.move('b',e['id'],target['id'],[fact])
    repo.move('a',e['id'],target['id'],[fact])
    assert repo.get('a',target['id'])['facts'][0]['id']==fact
    assert repo.get('a',e['id'])['facts']==[]


@pytest.mark.asyncio
async def test_exact_quote_and_name_validation(monkeypatch):
    async def fake(runtime,request,principal,id,instruction,data,validate):
        for value in [ {'entities':[{'name':'Invented','kind':'product','facts':[{'text':'x','quote':'Model A costs 100.'}]}]},
                       {'entities':[{'name':'Model A','kind':'product','facts':[{'text':'x','quote':'invented quote'}]}]}]:
            with pytest.raises(ValueError):validate(value)
        return validate(plan().model_dump())
    monkeypatch.setattr(service,'model_json',fake)
    result=await entities.extract(None,None,None,{'channel_id':'c','title':'Model A','summary':'Model A costs 100.','body':''})
    assert result.entities[0].name=='Model A'


@pytest.mark.asyncio
async def test_opportunities_require_evidence_and_countercase(monkeypatch):
    async def fake(runtime,request,principal,id,instruction,data,validate):
        assert 'valuation' in instruction and 'asking prices' in instruction
        with pytest.raises(ValueError):validate({'found':True,'fact_ids':['invented']})
        with pytest.raises(ValueError):validate({'found':True,'fact_ids':['f']})
        return validate({'found':False})
    monkeypatch.setattr(service,'model_json',fake)
    result=await entities.opportunity(None,None,None,{'id':'e','name':'Model A','rule':'find value','facts':[{'id':'f'}]},[])
    assert not result.found


def test_api_manual_entities_owner_and_watch(client):
    r=client.post('/intelligence/entities',json={'name':'Example Co','kind':'company'})
    assert r.status_code==200
    e=r.json();assert client.get('/intelligence/entities').json()['entities'][0]['id']==e['id']
    assert client.put('/intelligence/entities/'+e['id'],json={'name':'Example Co','aliases':['EX'],'watched':True,'rule':'业务增长证据','revision':0}).status_code==200
    assert client.put('/intelligence/entities/not-owned',json={'name':'x','revision':0}).status_code==404

def test_lead_dedup_feedback_and_stale_rule(tmp_path):
    store=IntelligenceStore(tmp_path);repo=entities.Repository(store)
    c=store.save_channel('a',{'name':'c','interests':'Models','interval_hours':0})['id']
    a=seed(store,'a',c);repo.ingest('a',a,plan());e=repo.snapshot('a')['entities'][0]
    e=repo.settings('a',e['id'],entities.EntitySettings(name=e['name'],watched=True,rule='price',revision=e['revision']))
    lead=entities.Lead(found=True,title='Research',change='Reported price',relevance='Matches',conditions='Verify price',counterevidence='No transaction data',next_steps='Check actual sales',fact_ids=[e['facts'][0]['id']])
    repo.save_lead('a',e,'digest',lead);repo.save_lead('a',e,'digest',lead)
    rows=repo.snapshot('a')['opportunities'];assert len(rows)==1
    repo.lead_status('a',rows[0]['id'],'ignored','No purchase intent')
    assert repo.snapshot('a')['opportunities'][0]['feedback_reason']=='No purchase intent'
    repo.settings('a',e['id'],entities.EntitySettings(name=e['name'],watched=True,rule='different',revision=e['revision']))
    assert repo.snapshot('a')['opportunities'][0]['stale']
    with pytest.raises(KeyError):repo.lead_status('b',rows[0]['id'],'read','')


def test_manual_merge_redirects_future_evidence(tmp_path):
    store=IntelligenceStore(tmp_path);repo=entities.Repository(store)
    c=store.save_channel('a',{'name':'c','interests':'Models','interval_hours':0})['id']
    article=seed(store,'a',c);repo.ingest('a',article,plan());source=repo.snapshot('a')['entities'][0]
    target=repo.create('a','Correct model identity','product')
    repo.move('a',source['id'],target['id'],[source['facts'][0]['id']])
    c2=store.save_channel('a',{'name':'c2','interests':'Models','interval_hours':0})['id']
    article2=seed(store,'a',c2);repo.ingest('a',article2,plan())
    result=repo.snapshot('a')['entities']
    assert len(result)==1 and result[0]['id']==target['id'] and len(result[0]['facts'])==2


def test_dismiss_blocks_future_aliases_across_channels_and_can_restore(tmp_path):
    store=IntelligenceStore(tmp_path);repo=entities.Repository(store)
    c1=store.save_channel('a',{'name':'One','interests':'Models','interval_hours':0})['id']
    c2=store.save_channel('a',{'name':'Two','interests':'Models','interval_hours':0})['id']
    first=seed(store,'a',c1)
    repo.ingest('a',first,plan())
    entity=repo.snapshot('a')['entities'][0]
    with pytest.raises(KeyError):repo.dismiss('other',entity['id'])
    repo.dismiss('a',entity['id'])
    assert repo.snapshot('a')['entities']==[]
    assert repo.snapshot('a')['dismissed_entities'][0]['name']=='Model A'
    second=seed(store,'a',c2)
    draft=plan();draft.entities[0].name='New Alias';draft.entities[0].aliases=['Model A']
    repo.ingest('a',second,draft)
    assert repo.snapshot('a')['entities']==[]
    assert 'New Alias' in repo.snapshot('a')['dismissed_entities'][0]['aliases']
    repo.dismiss('a',entity['id'],False)
    assert len(repo.snapshot('a')['entities'])==1
    assert repo.snapshot('a')['dismissed_entities']==[]


def test_dismiss_restore_api(client):
    entity=client.post('/intelligence/entities',json={'name':'Ignore test','kind':'person'}).json()
    assert client.post('/intelligence/entities/'+entity['id']+'/dismiss').status_code==200
    snapshot=client.get('/intelligence/entities').json()
    assert not snapshot['entities']
    assert snapshot['dismissed_entities'][0]['id']==entity['id']
    assert client.post('/intelligence/entities/'+entity['id']+'/restore').status_code==200
    assert client.get('/intelligence/entities').json()['entities'][0]['id']==entity['id']


def test_entity_images_cover_exclusion_and_owner_scope(tmp_path):
    store=IntelligenceStore(tmp_path);repo=entities.Repository(store)
    c=store.save_channel('a',{'name':'c','interests':'Models','interval_hours':0})['id']
    a=seed(store,'a',c);repo.ingest('a',a,plan())
    images=[{'url':'https://example.com/one.jpg','alt':'one'},{'url':'https://example.com/two.jpg','alt':'two'}]
    store.save_images('a',a['id'],'https://example.com/a',images,images[0]['url'])
    a=store.snapshot('a')['articles'][0]
    extraction=plan();extraction.entities[0].image_ids=[i['id'] for i in entities.image_candidates(a)]
    repo.ingest('a',a,extraction)
    e=repo.snapshot('a')['entities'][0]
    assert len(e['images'])==2
    assert e['cover_image']['url']==images[0]['url']
    selected=e['images'][1]['id']
    body=entities.EntityImageSettings(image_id=selected,action='cover')
    with pytest.raises(KeyError):repo.image_settings('b',e['id'],body)
    repo.image_settings('a',e['id'],body)
    assert repo.snapshot('a')['entities'][0]['cover_image']['id']==selected
    repo.image_settings('a',e['id'],entities.EntityImageSettings(image_id=selected,action='remove'))
    store.save_images('a',a['id'],'https://example.com/a',images)
    after=entities.Repository(store).snapshot('a')['entities'][0]
    assert len(after['images'])==1 and after['cover_image']['url']==images[0]['url']
    assert len(store.snapshot('a')['articles'][0]['images'])==2
    with pytest.raises(ValueError):repo.image_settings('a',e['id'],body)


def test_mentions_do_not_inherit_article_images_and_can_be_promoted(tmp_path):
    store=IntelligenceStore(tmp_path);repo=entities.Repository(store)
    c=store.save_channel('a',{'name':'c','interests':'Models','interval_hours':0})['id']
    article=seed(store,'a',c)
    store.save_images('a',article['id'],'https://example.com/a',[{'url':'https://example.com/other.jpg','alt':'Other model'}])
    article=store.snapshot('a')['articles'][0]
    extraction=plan();extraction.entities[0].coverage='mention';extraction.entities[0].coverage_reason='Only a competitor price comparison'
    repo.ingest('a',article,extraction)
    e=repo.snapshot('a')['entities'][0]
    assert e['dossier_status']=='mention' and e['images']==[] and e['cover_image'] is None
    assert not repo.pending('a',[article])
    repo.settings('a',e['id'],entities.EntitySettings(name=e['name'],aliases=e['aliases'],watched=True,revision=e['revision']))
    e=repo.snapshot('a')['entities'][0]
    assert e['dossier_status']=='substantive' and not e['images']
    # A new article with substantive coverage promotes the same shared entity.
    c2=store.save_channel('a',{'name':'second','interests':'Models','interval_hours':0})['id']
    second=seed(store,'a',c2);repo.ingest('a',second,plan())
    assert len(repo.snapshot('a')['entities'])==1
    assert repo.snapshot('a')['entities'][0]['id']==e['id']


def test_new_relevance_pass_preserves_manual_cover_and_exclusions(tmp_path):
    store=IntelligenceStore(tmp_path);repo=entities.Repository(store)
    c=store.save_channel('a',{'name':'c','interests':'Models','interval_hours':0})['id']
    article=seed(store,'a',c)
    store.save_images('a',article['id'],'https://example.com/a',[{'url':'https://example.com/a.jpg','alt':'Model A'}])
    article=store.snapshot('a')['articles'][0];extraction=plan()
    extraction.entities[0].image_ids=[entities.image_candidates(article)[0]['id']]
    repo.ingest('a',article,extraction);e=repo.snapshot('a')['entities'][0]
    image_id=e['images'][0]['id']
    repo.image_settings('a',e['id'],entities.EntityImageSettings(image_id=image_id,action='cover'))
    store.save_images('a',article['id'],'https://example.com/a',[{'url':'https://example.com/new.jpg','alt':'Other'}])
    article=store.snapshot('a')['articles'][0]
    assert repo.pending('a',[article])
    mention=plan();mention.entities[0].coverage='mention'
    repo.ingest('a',article,mention)
    assert repo.snapshot('a')['entities'][0]['cover_image']['id']==image_id


@pytest.mark.asyncio
async def test_existing_dossier_review_preserves_evidence(monkeypatch,tmp_path):
    store=IntelligenceStore(tmp_path);repo=entities.Repository(store)
    c=store.save_channel('a',{'name':'c','interests':'Models','interval_hours':0})['id']
    article=seed(store,'a',c);repo.ingest('a',article,plan())
    e=repo.snapshot('a')['entities'][0]
    async def fake(runtime,request,principal,id,instruction,data,validate):
        assert data['entities'][0]['id']==e['id']
        return validate({'decisions':[{'entity_id':e['id'],'coverage':'mention','coverage_reason':'Competitor price comparison','image_ids':[]}]})
    monkeypatch.setattr(service,'model_json',fake)
    from types import SimpleNamespace
    result=await entities.extract_or_review(None,None,SimpleNamespace(actor_user_id='a'),article,repo)
    assert result.entities[0].name==e['name']
    assert result.entities[0].facts[0].quote==e['facts'][0]['quote']
    assert result.entities[0].coverage=='mention'
