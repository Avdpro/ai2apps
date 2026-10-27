import json
from types import SimpleNamespace as NS
import pytest
from ai2apps.intelligence import entities,entity_attributes as attrs
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.tests.test_intelligence_api import client


def setup(tmp_path):
    store=IntelligenceStore(tmp_path);repo=entities.Repository(store)
    channel=store.save_channel('owner',{'name':'Watches','interests':'Watch X','interval_hours':0})
    store.save_source('owner',channel['id'],{'name':'Source','url':'https://example.com/','enabled':True,'kind':'website'})
    articles=[]
    for n,text in enumerate(['Watch X thickness is 12.98 mm.','Watch X thickness is 12.98毫米.']):
        run=store.claim('owner',channel['id'])
        store.finish('owner',run['id'],[],[{'title':'Watch X '+str(n),'summary':text,'body':text,'sources':[{'url':'https://example.com/'+str(n)}]}],[])
        a=next(a for a in store.snapshot('owner')['articles'] if a['title']=='Watch X '+str(n));articles.append(a)
        repo.ingest('owner',a,entities.Extraction(entities=[entities.EntityDraft(name='Watch X',kind='model',coverage='substantive',coverage_reason='Introduces Watch X',facts=[entities.Fact(text=text,quote=text)])]))
    return store,repo,articles,repo.snapshot('owner')['entities'][0]


def attr(a,value='12.98 mm'):
    return attrs.Attribute(key='case_thickness',value=value,quote=a['body'],article_id=a['id'])


def test_validation_rejects_invented_values_quotes_conditions_and_wrong_domain():
    text='Watch X is 12.98 mm thick.'
    attrs.validate_attributes('watch',[attrs.Attribute(key='case_thickness',value='12.98 mm',quote=text)],text,'a')
    for bad in [attrs.Attribute(key='case_thickness',value='13 mm',quote=text),attrs.Attribute(key='case_thickness',value='12.98 mm',quote='Invented 12.98 mm'),attrs.Attribute(key='case_thickness',value='12.98 mm',quote=text,conditions='4-bit'),attrs.Attribute(key='parameters_total',value='12.98 mm',quote=text)]:
        with pytest.raises(ValueError):attrs.validate_attributes('watch',[bad],text,'a')
    with pytest.raises(ValueError):attrs.validate_attributes('watch',[attrs.Attribute(key='case_width',value='13 mm',quote='A case measures 113 mm.')],'A case measures 113 mm.','a')


def test_two_article_evidence_idempotence_and_owner_revision_guards(tmp_path):
    store,repo,articles,e=setup(tmp_path)
    plan=attrs.Attributes(domain='watch',attributes=[attr(articles[0]),attr(articles[1],'12.98毫米')])
    repo.save_attributes('owner',e['id'],e['revision'],articles,plan)
    updated=repo.snapshot('owner')['entities'][0];group=updated['attribute_groups'][0]
    assert not group['conflicting'] and len(group['values'])==1
    v=group['values'][0];assert v['article_count']==2 and len(v['evidence'])==2
    assert {ev['sources'][0]['url'] for ev in v['evidence']}=={'https://example.com/0','https://example.com/1'}
    repo.save_attributes('owner',e['id'],updated['revision'],articles,plan)
    assert len(repo.get('owner',e['id'])['attributes'])==2
    with pytest.raises(ValueError):repo.save_attributes('owner',e['id'],e['revision'],articles,plan)
    with pytest.raises(KeyError):repo.save_attributes('other',e['id'],0,articles,plan)


def test_conflict_and_history_are_preserved(tmp_path):
    store,repo,articles,e=setup(tmp_path)
    a=articles[1];a['body']='Watch X thickness is 13.1 mm.';a['summary']=a['body']
    with store.connect() as db:db.execute('UPDATE articles SET data=? WHERE owner=? AND id=?',(json.dumps(a),'owner',a['id']))
    repo.save_attributes('owner',e['id'],e['revision'],articles,attrs.Attributes(domain='watch',attributes=[attr(articles[0]),attr(a,'13.1 mm')]))
    group=repo.snapshot('owner')['entities'][0]['attribute_groups'][0]
    assert group['conflicting'] and len(group['values'])==2
    old=articles[0];old['body']='New article version without this measurement.'
    with store.connect() as db:db.execute('UPDATE articles SET data=? WHERE owner=? AND id=?',(json.dumps(old),'owner',old['id']))
    group=repo.snapshot('owner')['entities'][0]['attribute_groups'][0]
    assert not group['conflicting'] and any(v['historical'] for v in group['values'])


def test_ai_memory_configurations_and_missing_values_stay_separate():
    a={'id':'a','title':'Model','body':'4-bit requires 32 GB; BF16 requires 96 GB.','summary':'','updated_at':'now','sources':[]}
    assertions=[{'id':str(i),'key':'memory_required','domain':'ai_model','value':v,'conditions':c,'basis':'stated','status':'reported','article_id':'a','article_version':entities.article_signature(a),'quote':a['body']} for i,(v,c) in enumerate([('32 GB','4-bit'),('96 GB','BF16')])]
    group=attrs.aggregate(assertions,{'a':a})[0]
    assert not group['conflicting'] and len(group['values'])==2
    assert 'parameters_total' not in {g['key'] for g in attrs.aggregate(assertions,{'a':a})}


@pytest.mark.asyncio
async def test_existing_entity_enrichment_resumes_without_repeating_ai(tmp_path,monkeypatch):
    store,repo,articles,e=setup(tmp_path);calls=[]
    async def model(*args,**kw):
        calls.append(args[5]);assert 'quantization' in args[4]
        return args[6]({'domain':'watch','attributes':[attr(articles[0]).model_dump(),attr(articles[1],'12.98毫米').model_dump()]})
    monkeypatch.setattr(entities.service,'model_json',model)
    assert await attrs.enrich(None,None,NS(actor_user_id='owner'),repo,e['id'])=={'processed':2,'remaining':0}
    assert await attrs.enrich(None,None,NS(actor_user_id='owner'),repo,e['id'])=={'processed':0,'remaining':0}
    assert len(calls)==1


def test_attribute_api_owner_check(client):
    assert client.post('/intelligence/entities/missing/attributes').status_code==404

@pytest.mark.asyncio
async def test_new_ai_model_extracts_total_active_ram_and_vram_separately(monkeypatch):
    text='Model A has 24B total parameters and 2B active parameters. 4-bit requires 32 GB RAM. 4-bit GPU requires 12 GB VRAM.'
    article={'id':'a','channel_id':'c','title':'Model A','summary':'','body':text}
    async def model(*args,**kw):
        return args[6]({'entities':[{'name':'Model A','kind':'model','coverage':'substantive','coverage_reason':'Model specifications','attribute_domain':'ai_model','facts':[{'text':'Model specifications','quote':text}], 'attributes':[
            {'key':'parameters_total','value':'24B','quote':'Model A has 24B total parameters and 2B active parameters.'},
            {'key':'parameters_active','value':'2B','quote':'Model A has 24B total parameters and 2B active parameters.'},
            {'key':'memory_required','value':'32 GB','conditions':'4-bit','quote':'4-bit requires 32 GB RAM.'},
            {'key':'vram_required','value':'12 GB','conditions':'4-bit','quote':'4-bit GPU requires 12 GB VRAM.'}]}]})
    monkeypatch.setattr(entities.service,'model_json',model)
    plan=await entities.extract(None,None,None,article)
    assert plan.entities[0].attribute_domain=='ai_model'
    values={a.key:a.value for a in plan.entities[0].attributes}
    assert values=={'parameters_total':'24B','parameters_active':'2B','memory_required':'32 GB','vram_required':'12 GB'}

def test_article_entities_api_lists_only_current_owner_evidence(client):
    from ai2apps.tests.test_intelligence_api import channel_and_source
    from ai2apps.identity import RequestPrincipal
    owner=RequestPrincipal.legacy_local().actor_user_id
    store=client.app.state.runtime.intelligence_collector.store
    repo=entities.Repository(store)
    c,_=channel_and_source(client)
    articles=[]
    for title,text in [('First','Watch X thickness is 11 mm.'),('Second','Watch X diameter is 37 mm.')]:
        run=store.claim(owner,c['id'])
        store.finish(owner,run['id'],[],[{'title':title,'summary':text,'body':text,'sources':[]}],[])
        a=next(a for a in store.snapshot(owner)['articles'] if a['title']==title)
        articles.append(a)
        key,value=('case_thickness','11 mm') if title=='First' else ('case_diameter','37 mm')
        repo.ingest(owner,a,entities.Extraction(entities=[entities.EntityDraft(name='Watch X',kind='model',coverage='substantive',coverage_reason=text,facts=[entities.Fact(text=text,quote=text)],attribute_domain='watch',attributes=[attrs.Attribute(key=key,value=value,quote=text)])]))
    first=articles[0]
    response=client.get('/intelligence/articles/'+first['id']+'/entities')
    assert response.status_code==200
    item=response.json()['items'][0]
    assert item['name']=='Watch X' and item['coverage']=='substantive'
    values={g['key']:g['values'][0] for g in item['attribute_groups']}
    assert values['case_thickness']['value']=='11 mm'
    assert values['case_thickness']['evidence'][0]['article_id']==first['id']
    assert values['case_diameter']['evidence'][0]['article_id']==articles[1]['id']
    assert client.get('/intelligence/articles/missing/entities').status_code==404
    with store.connect() as db:
        db.execute('UPDATE articles SET owner=? WHERE id=?',('other-owner',first['id']))
    assert client.get('/intelligence/articles/'+first['id']+'/entities').status_code==404
    with store.connect() as db:
        first['body']='Changed without the original fact.'
        first['summary']=''
        db.execute('UPDATE articles SET owner=?,data=? WHERE id=?',(owner,json.dumps(first),first['id']))
    assert client.get('/intelligence/articles/'+first['id']+'/entities').json()['items']==[]

@pytest.mark.asyncio
async def test_channel_backfill_resumes_skips_failed_entities_and_nonproducts(tmp_path,monkeypatch):
    store,repo,articles,e=setup(tmp_path)
    calls=[]
    async def fail(*args):
        calls.append(args[-1]);raise ValueError('model failure')
    monkeypatch.setattr(attrs,'enrich',fail)
    result=await attrs.backfill_channel(None,None,NS(actor_user_id='owner'),repo,articles[0]['channel_id'])
    assert result['failed'][0]['id']==e['id'] and result['processed']==0
    result=await attrs.backfill_channel(None,None,NS(actor_user_id='owner'),repo,articles[0]['channel_id'],[e['id']])
    assert result=={'processed':0,'remaining':0,'failed':[]} and len(calls)==1
    with pytest.raises(KeyError):await attrs.backfill_channel(None,None,NS(actor_user_id='other'),repo,articles[0]['channel_id'])

@pytest.mark.asyncio
async def test_backfill_timeout_is_explicit_and_resumable(tmp_path,monkeypatch):
    store,repo,articles,e=setup(tmp_path)
    async def timeout(*args):raise TimeoutError()
    monkeypatch.setattr(attrs,'enrich',timeout)
    result=await attrs.backfill_channel(None,None,NS(actor_user_id='owner'),repo,articles[0]['channel_id'])
    assert result['retry_later'] is True
    assert result['failed'][0]['error']=='TimeoutError'
    assert not repo.get('owner',e['id']).get('attributes_checked')


def test_open_domains_custom_attributes_and_explicit_units():
    text='Camera Z sensor resolution is 48 MP.'
    attribute=attrs.Attribute(key='sensor_resolution',label='Sensor resolution',value='48 MP',unit='MP',quote=text)
    plan=attrs.Attributes(domain='camera',attributes=[attribute])
    attrs.validate_attributes(plan.domain,plan.attributes,text,'a')
    assert entities.EntityDraft(name='Camera Z',kind='model',attribute_domain='camera',facts=[entities.Fact(text=text,quote=text)]).attribute_domain=='camera'
    for bad in [attrs.Attribute(key='sensor_resolution',value='48 MP',quote=text),attrs.Attribute(key='sensor_resolution',label='Resolution',value='48 MP',unit='GB',quote=text)]:
        with pytest.raises(ValueError):attrs.validate_attributes('camera',[bad],text,'a')
    with pytest.raises(ValueError):attrs.Attributes(domain='not a domain')


def test_automotive_aliases_custom_extension_and_range_conditions():
    text='Car A wheelbase is 2900 mm. WLTP range is 600 km. CLTC range is 720 km.'
    wheelbase=attrs.Attribute(key='wheel_base',value='2900 mm',unit='mm',quote=text)
    attrs.validate_attributes('automotive',[wheelbase],text,'a')
    assert wheelbase.key=='wheelbase'
    article={'id':'a','title':'Car A','body':text,'updated_at':'now','summary':'','sources':[]}
    assertions=[]
    for value,condition in [('600 km','WLTP'),('720 km','CLTC')]:
        a=attrs.Attribute(key='range',value=value,unit='km',conditions=condition,quote=text)
        attrs.validate_attributes('automotive',[a],text,'a')
        assertions.append({**a.model_dump(),'id':value,'domain':'automotive','article_id':'a','article_version':entities.article_signature(article)})
    group=attrs.aggregate(assertions,{'a':article})[0]
    assert len(group['values'])==2 and not group['conflicting']
    assert group['labels']['zh']=='\u7eed\u822a\u91cc\u7a0b'
    custom=attrs.Attribute(key='turning_radius',label='Turning radius',value='5.4 m',quote='Turning radius is 5.4 m.')
    attrs.validate_attributes('automotive',[custom],custom.quote,'a')


def test_generic_attribute_persistence_domain_separation_and_revision_upgrade(tmp_path):
    store,repo,articles,e=setup(tmp_path)
    article=articles[0]
    plan=attrs.Attributes(domain='manufacturing',attributes=[attrs.Attribute(key='specification',label='Specification',value='12.98 mm',unit='mm',quote=article['body'],article_id=article['id'])])
    repo.save_attributes('owner',e['id'],e['revision'],[article],plan)
    saved=repo.get('owner',e['id'])
    assert attrs.checked_article(saved,article)
    saved.pop('attribute_schema_revision')
    assert not attrs.checked_article(saved,article)
    group=repo.snapshot('owner')['entities'][0]['attribute_groups'][0]
    assert group['label']=='Specification' and group['values'][0]['unit']=='mm'
    records=[{**repo.get('owner',e['id'])['attributes'][0],'domain':domain,'id':domain} for domain in ['manufacturing','camera']]
    assert len(attrs.aggregate(records,{article['id']:article}))==2
