"""Typed, quoted entity attributes; aggregate evidence without guessing specifications."""
import re
import unicodedata
from collections import defaultdict
from typing import Literal
from pydantic import BaseModel,Field

# Presets provide stable keys and aliases, not an exhaustive list of domains/fields.
import json
from pathlib import Path
from typing import Annotated
SCHEMAS=json.loads(Path(__file__).with_name('entity_attribute_schemas.json').read_text())
DOMAINS={domain:list(schema['fields']) for domain,schema in SCHEMAS.items()}
DOMAINS['other']=[]  # compatibility with existing dossiers
Domain=Annotated[str,Field(min_length=1,max_length=64,pattern=r'^[a-z][a-z0-9_]*$')]
SCHEMA_REVISION=2


def canonical_key(domain,key):
    fields=SCHEMAS.get(domain,{}).get('fields',{})
    for name,definition in fields.items():
        if key==name or key in definition.get('aliases',[]):return name
    return key


def checked_article(entity,article):
    from .entities import article_signature
    return entity.get('attribute_schema_revision',0)>=SCHEMA_REVISION and entity.get('attributes_checked',{}).get(article['id'])==article_signature(article)


class Attribute(BaseModel):
    key: str = Field(min_length=1,max_length=60,pattern=r'^[a-z][a-z0-9_]*$')
    label: str = Field(default='',max_length=100)
    unit: str = Field(default='',max_length=60)
    value: str = Field(min_length=1,max_length=300)
    quote: str = Field(min_length=4,max_length=1200)
    context_quote: str = Field(default='',max_length=1200)
    conditions: str = Field(default='',max_length=400)
    basis: Literal['stated','measured','estimated'] = 'stated'
    status: Literal['reported','opinion','rumour'] = 'reported'
    article_id: str = Field(default='',max_length=100)

class Attributes(BaseModel):
    domain: Domain = 'other'
    attributes: list[Attribute] = Field(default_factory=list,max_length=60)


def normalized(value):
    value=unicodedata.normalize('NFKC',value).casefold()
    value=re.sub(r'\s+','',value)
    for old,new in [('毫米','mm'),('小时','h'),('秒/日','s/day'),('秒每天','s/day')]:value=value.replace(old,new)
    return value


def validate_attributes(domain,attributes,text,article_id):
    for attr in attributes:
        key=canonical_key(domain,attr.key)
        fields=SCHEMAS.get(domain,{}).get('fields',{})
        reserved={k for d,v in DOMAINS.items() if d!=domain for k in v}
        if domain in SCHEMAS and key not in fields and key in reserved:raise ValueError('Attribute is not valid for the entity domain')
        if key not in fields and not attr.label.strip():raise ValueError('Custom attributes need a descriptive label')
        attr.key=key
        if attr.unit and normalized(attr.unit) not in normalized(attr.value):raise ValueError('Attribute units must occur in the quoted value')
        if attr.article_id and attr.article_id!=article_id:raise ValueError('Unknown attribute article')
        if attr.quote not in text or (attr.context_quote and attr.context_quote not in text):raise ValueError('Attributes need exact article quotes')
        value=normalized(attr.value)
        if not value:raise ValueError('Attribute value cannot be blank')
        pattern=re.escape(value)
        if value[0].isdigit():pattern=r'(?<![\d.])'+pattern
        if value[-1].isdigit():pattern+=r'(?![\d.])'
        if not re.search(pattern,normalized(attr.quote)):raise ValueError('Attribute value must be explicitly present in its quote')
        if attr.conditions and normalized(attr.conditions) not in normalized(attr.quote+' '+attr.context_quote):raise ValueError('Attribute conditions need quoted evidence')

INSTRUCTION=(
 'Extract structured attributes only for this EXACT entity, with one exact quote per assertion. '
 'Entity kind (model/product/company/person/etc) is independent of domain; model is not synonymous with AI. '
 'Choose a stable snake_case domain describing the subject, e.g. automotive, watch, ai_model, camera, software, energy or any other appropriate field. '
 'Presets and stable attribute keys (not an exhaustive allowlist): '+str(DOMAINS)+'. '
 'Reuse these keys when semantics match. For other properties use a stable descriptive snake_case key and a concise localized label. '
 'Do not generate keys containing a particular entity name, numeric value or unit. Keep a stable key across articles. '
 'unit is optional: copy it literally from value, never convert units. Every custom attribute requires label. '
 'Automotive range and consumption must preserve quoted test cycle, trim, battery, conditions and stated/measured basis. '
 'Distinguish dial diameter/width from case diameter/width, strap width from lug width, and case thickness from crystal or movement thickness. '
 'Watch accuracy is rate deviation (such as seconds per day), not movement beat frequency or certification alone. '
 'Never attach a competitor, series sibling, different reference, color, size or version specification to this entity. '
 'For AI distinguish total vs active MoE parameters, RAM vs VRAM vs disk size, minimum vs recommended memory and context length. '
 'Memory assertions must retain any explicitly stated quantization, precision, hardware, context length and inference setup as conditions/context_quote. '
 'Copy value literally including units/ranges/qualifiers; do not calculate, estimate or convert missing measurements. '
 'conditions must be a literal quoted phrase; context_quote is an exact excerpt qualifying identity/setup. '
 'Keep manufacturer specifications separate from measured results and explicit estimates using basis stated/measured/estimated. '
 'reported means the article reports it, not independently verified; keep opinions/rumours marked. '
 'Retain competing reported values as separate assertions. Missing properties are omitted, never zero or invented. ')


def aggregate(assertions,articles):
    groups={}
    for a in assertions:
        article=articles.get(a['article_id'])
        if not article:continue
        from .entities import article_signature
        historical=a['article_version']!=article_signature(article)
        key=canonical_key(a['domain'],a['key'])
        group=groups.setdefault((a['domain'],key),{'key':key,'domain':a['domain'],'label':a.get('label') or SCHEMAS.get(a['domain'],{}).get('fields',{}).get(key,{}).get('label',key),'labels':SCHEMAS.get(a['domain'],{}).get('fields',{}).get(key,{}).get('labels',{}),'values':{}})
        identity=(normalized(a['value']),normalized(a.get('conditions','')),a.get('basis','stated'),a.get('status','reported'))
        value=group['values'].setdefault(identity,{'value':a['value'],'conditions':a.get('conditions',''),'basis':a.get('basis','stated'),'status':a.get('status','reported'),'unit':a.get('unit',''),'evidence':[]})
        evidence={k:a.get(k,'') for k in ('id','article_id','article_version','quote','context_quote','observed_at')}
        evidence.update(article_title=article['title'],sources=article.get('sources',[]),historical=historical)
        if not any(e['id']==evidence['id'] for e in value['evidence']):value['evidence'].append(evidence)
    result=[]
    for group in groups.values():
        values=list(group['values'].values());current=defaultdict(set)
        for value in values:
            value['historical']=all(e['historical'] for e in value['evidence'])
            value['article_count']=len({e['article_id'] for e in value['evidence'] if not e['historical']})
            if not value['historical'] and value['status']=='reported':current[(normalized(value['conditions']),value['basis'])].add(normalized(value['value']))
        group.update(values=values,conflicting=any(len(v)>1 for v in current.values()));result.append(group)
    return sorted(result,key=lambda g:(g['domain'],DOMAINS.get(g['domain'],[]).index(g['key']) if g['key'] in DOMAINS.get(g['domain'],[]) else 10000,g['key']))


async def enrich(runtime,request,principal,repo,id):
    from . import service,entities
    import json
    owner=principal.actor_user_id;e=repo.get(owner,id)
    if e.get('redirect') or e.get('dismissed'):raise ValueError('请选择有效实体')
    ids={f['article_id'] for f in e['facts']}
    articles=[a for a in repo.store.snapshot(owner)['articles'] if a['id'] in ids]
    pending=[a for a in articles if not checked_article(e,a)]
    batch=sorted(pending,key=lambda a:a['updated_at'],reverse=True)[:8]
    if not batch:return {'processed':0,'remaining':0}
    texts={a['id']:'\n'.join(a.get(k,'') for k in ('title','summary','body')) for a in batch}
    def validate(value):
        plan=Attributes.model_validate(value)
        for attr in plan.attributes:
            if attr.article_id not in texts:raise ValueError('Every attribute needs a supplied article ID')
            validate_attributes(plan.domain,[attr],texts[attr.article_id],attr.article_id)
        return plan
    result=await service.model_json(runtime,request,principal,batch[0]['channel_id'],INSTRUCTION+
        'For every assertion return its supplied article_id. Read ALL supplied articles; aggregate evidence later in code. Schema: '+json.dumps(Attributes.model_json_schema()),
        {'entity':{k:e.get(k) for k in ('name','kind','aliases','brand','reference','attribute_domain')},'articles':[{'id':a['id'],'text':texts[a['id']][:30000]} for a in batch]},validate,stage='entity_attributes')
    repo.save_attributes(owner,id,e['revision'],batch,result)
    return {'processed':len(batch),'remaining':max(0,len(pending)-len(batch))}


async def backfill_channel(runtime,request,principal,repo,channel_id,skip_ids=()):
    """One resumable entity per call; successful article checkpoints avoid repeat AI work."""
    from .entities import article_signature
    owner=principal.actor_user_id
    repo.store.get('channels',owner,channel_id)
    articles={a['id']:a for a in repo.store.snapshot(owner)['articles']}
    pending=[]
    for e in repo.snapshot(owner)['entities']:
        if e['id'] in skip_ids or e.get('dossier_status')!='substantive':continue
        linked=[articles[f['article_id']] for f in e['facts'] if not f.get('historical') and f['article_id'] in articles]
        if not any(a['channel_id']==channel_id for a in linked):continue
        if any(not checked_article(e,a) for a in linked):pending.append(e)
    if not pending:return {'processed':0,'remaining':0,'failed':[]}
    pending.sort(key=lambda e:max((articles[f['article_id']].get('updated_at','') for f in e['facts'] if f['article_id'] in articles),default=''),reverse=True)
    e=pending[0]
    try:
        result=await enrich(runtime,None,principal,repo,e['id'])
        return {'processed':1,'remaining':len(pending)-1+bool(result['remaining']),'failed':[],'entity_name':e['name']}
    except Exception as error:
        import logging
        logging.getLogger(__name__).warning('Entity parameter backfill failed entity=%s error=%s',e['name'],type(error).__name__)
        return {'processed':0,'remaining':len(pending)-1,'failed':[{'id':e['id'],'name':e['name'],'error':str(error) or type(error).__name__}],'retry_later':isinstance(error,TimeoutError)}
