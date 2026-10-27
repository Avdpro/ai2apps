import json
from types import SimpleNamespace as NS
import pytest
from ai2apps.intelligence import entities,entity_identity
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.tests.test_intelligence_api import client,channel_and_source


def setup(tmp_path):
    store=IntelligenceStore(tmp_path);repo=entities.Repository(store)
    channel=store.save_channel('owner',{'name':'Watches','interests':'Watches','interval_hours':0})
    values=[]
    with store.connect() as db:
        for id,name,kind in [('a','James Bond 版','product'),('b','James Bond','product')]:
            quote='Omega James Bond edition has a blue dial.'
            article={'id':'article-'+id,'channel_id':channel['id'],'title':name,'summary':quote,'body':quote,'updated_at':'2026-10-15','sources':[]}
            db.execute('INSERT INTO articles VALUES(?,?,?,?)',(article['id'],'owner',channel['id'],json.dumps(article)))
            e={'id':id,'name':name,'kind':kind,'aliases':[name],'facts':[{'id':'fact-'+id,'article_id':article['id'],'article_title':name,'article_version':entities.article_signature(article),'quote':quote,'text':quote,'coverage':'substantive','observed_at':'2026-10-15'}],'watched':id=='b','rule':'watch pricing' if id=='b' else '', 'revision':0,'created_at':'2026-10-15'}
            db.execute('INSERT INTO entity_dossiers VALUES(?,?,?)',('owner',id,json.dumps(e)));values.append(e)
    return store,repo,channel,values


def test_candidates_do_not_equate_variants_and_types():
    base={'id':'a','name':'M0A10870','aliases':[],'kind':'model'}
    assert not entity_identity.compatible(base,{**base,'id':'b','name':'M0A10872'})
    assert not entity_identity.compatible(base,{**base,'id':'b','kind':'brand'})
    assert not entity_identity.compatible(base,{**base,'id':'b','identity_locked':True})
    assert not entity_identity.compatible({**base,'brand':'Brand A'},{**base,'id':'b','brand':'Brand B'})
    assert entity_identity.canonical('TAG Heuer（泰格豪雅）')==entity_identity.canonical('tag heuer (泰格豪雅)')
    brands=[{'id':'brand','name':'Omega','aliases':['欧米茄'],'kind':'brand'}]
    pair=[{'id':'a','name':'Seamaster Diver','aliases':[],'kind':'product'},{'id':'b','name':'Omega Seamaster Diver','aliases':[],'kind':'product'}]
    assert any(a['id']=='a' and b['id']=='b' for _,a,b in entity_identity.candidates(brands+pair))


def test_merge_retains_facts_preferences_leads_taxonomy_and_redirects(tmp_path):
    store,repo,c,values=setup(tmp_path)
    with store.connect() as db:
        channel=json.loads(db.execute('SELECT data FROM channels WHERE id=?',(c['id'],)).fetchone()['data'])
        channel['entity_taxonomy']={'assignments':{'a':'watches'},'signatures':{'a':'old'}}
        db.execute('UPDATE channels SET data=? WHERE id=?',(json.dumps(channel),c['id']))
        lead={'id':'lead','entity_id':'a','entity_name':'Old','fact_ids':['fact-a'],'rule':'watch pricing'}
        db.execute('INSERT INTO entity_leads VALUES(?,?,?)',('owner','lead',json.dumps(lead)))
    result=repo.merge_duplicate('owner','a','b',0,0,'Same named edition in evidence')
    assert result['target_id']=='b' and repo.get('owner','a')['redirect']=='b'
    e=repo.get('owner','b');assert e['watched'] and e['rule']=='watch pricing'
    assert {f['id'] for f in e['facts']}=={'fact-a','fact-b'}
    assert 'James Bond 版' in e['aliases']
    snap=repo.snapshot('owner');assert len(snap['entities'])==1
    assert snap['opportunities'][0]['entity_id']=='b'
    assert snap['channel_taxonomies'][c['id']]['assignments']=={'b':'watches'}
    with pytest.raises(KeyError):repo.merge_duplicate('other','a','b',0,0,'x')
    with pytest.raises(ValueError):repo.merge_duplicate('owner','a','b',0,0,'x')


@pytest.mark.asyncio
async def test_reconciliation_requires_two_exact_evidence_quotes(tmp_path,monkeypatch):
    store,repo,c,values=setup(tmp_path)
    async def model(*args,**kwargs):
        data=args[5];validate=args[6];pair=data['pairs'][0]
        return validate({'decisions':[{'left_id':pair['left']['id'],'right_id':pair['right']['id'],'same_entity':True,'confidence':'high','reason':'Same brand and named edition, no differing reference or variant','left_quote':pair['left']['quotes'][0],'right_quote':'Invented evidence'}]})
    monkeypatch.setattr(entity_identity.service,'model_json',model)
    with pytest.raises(ValueError,match='exactly match'):await entity_identity.reconcile(None,None,NS(actor_user_id='owner'),repo,c['id'])
    assert not repo.get('owner','a').get('redirect')
    async def valid(*args,**kwargs):
        pair=args[5]['pairs'][0]
        return args[6]({'decisions':[{'left_id':pair['left']['id'],'right_id':pair['right']['id'],'same_entity':True,'confidence':'high','reason':'Same brand and named edition','left_quote':pair['left']['quotes'][0],'right_quote':pair['right']['quotes'][0]}]})
    monkeypatch.setattr(entity_identity.service,'model_json',valid)
    result=await entity_identity.reconcile(None,None,NS(actor_user_id='owner'),repo,c['id'])
    assert result['merged']==1


def test_future_ingest_follows_alias_redirect_without_creating_third_entry(tmp_path):
    store,repo,c,values=setup(tmp_path)
    repo.merge_duplicate('owner','a','b',0,0,'Same edition')
    article={'id':'new','channel_id':c['id'],'title':'James Bond 版','summary':'James Bond edition update.','body':'James Bond edition update.','updated_at':'2026-10-16','sources':[]}
    with store.connect() as db:db.execute('INSERT INTO articles VALUES(?,?,?,?)',(article['id'],'owner',c['id'],json.dumps(article)))
    draft=entities.EntityDraft(name='James Bond 版',kind='model',coverage='substantive',coverage_reason='Same exact edition',facts=[entities.Fact(text='An update',quote='James Bond edition update.')])
    repo.ingest('owner',article,entities.Extraction(entities=[draft]))
    result=repo.snapshot('owner')['entities']
    assert len(result)==1 and result[0]['id']=='b'
    assert len(result[0]['facts'])==3


@pytest.mark.asyncio
async def test_omitted_candidates_are_kept_separate_not_an_overall_failure(tmp_path,monkeypatch):
    store,repo,c,values=setup(tmp_path)
    async def model(*args,**kwargs):return args[6]({'decisions':[]})
    monkeypatch.setattr(entity_identity.service,'model_json',model)
    result=await entity_identity.reconcile(None,None,NS(actor_user_id='owner'),repo,c['id'])
    assert result['merged']==0 and result['unreviewed']==1
    assert len(repo.snapshot('owner')['entities'])==2


def test_reconcile_api_checks_channel_and_handles_no_candidates(client):
    channel,_=channel_and_source(client)
    assert client.post('/intelligence/channels/missing/entities/reconcile').status_code==404
    response=client.post('/intelligence/channels/'+channel['id']+'/entities/reconcile')
    assert response.status_code==200
    assert response.json()['merged']==0 and response.json()['unreviewed']==0
