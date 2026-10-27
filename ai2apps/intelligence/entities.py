"""Owner-scoped, cross-channel entity dossiers and evidence-bound opportunity leads."""
import hashlib
import json
import uuid
import re
from .entity_identity import canonical, references
from .entity_attributes import Domain, SCHEMA_REVISION, Attribute, Attributes, INSTRUCTION as ATTRIBUTE_INSTRUCTION, validate_attributes, aggregate
from urllib.parse import urlsplit
from .models import cover_url
from typing import Literal
from pydantic import BaseModel, Field
from . import service
from .store import stamp


def normalized(value):
    return ' '.join(value.casefold().split())


def signature(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


class Fact(BaseModel):
    text: str = Field(min_length=1,max_length=600)
    quote: str = Field(min_length=4,max_length=800)
    status: Literal['reported','opinion','rumour'] = 'reported'


class EntityDraft(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    kind: Literal['company','brand','product','model','person','organization','event','industry']
    aliases: list[str] = Field(default_factory=list,max_length=10)
    coverage: Literal['substantive','mention'] = 'mention'
    coverage_reason: str = Field(default='',max_length=600)
    brand: str = Field(default='',max_length=160)
    reference: str = Field(default='',max_length=160)
    image_ids: list[str] = Field(default_factory=list,max_length=48)
    attribute_domain: Domain = 'other'
    attributes: list[Attribute] = Field(default_factory=list,max_length=30)
    facts: list[Fact] = Field(min_length=1,max_length=8)


class Extraction(BaseModel):
    entities: list[EntityDraft] = Field(default_factory=list,max_length=12)


class EntitySettings(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    aliases: list[str] = Field(default_factory=list,max_length=20)
    watched: bool = False
    rule: str = Field(default='',max_length=2000)
    revision: int


class EntityImageSettings(BaseModel):
    image_id: str = Field(min_length=64, max_length=64)
    action: Literal['cover', 'remove']


def related_images(entity, articles):
    result={}
    excluded=set(entity.get('excluded_image_ids', []))
    for article_id in dict.fromkeys(f['article_id'] for f in entity['facts']):
        article=articles.get(article_id)
        if not article: continue
        for image in [article.get('cover_image') or {}, *article.get('images', [])]:
            url=image.get('url', '')
            try: url=cover_url(url)
            except ValueError: continue
            if not url or re.fullmatch(r"(?:tvax|tva|tvaxww)\d*\.sinaimg\.cn", urlsplit(url).hostname or ""): continue
            key=hashlib.sha256(url.encode()).hexdigest()
            if key in excluded: continue
            approved={key for f in entity['facts'] if f['article_id']==article_id and f.get('coverage')=='substantive' and not f.get('historical') for key in f.get('image_ids',[])}
            if key!=entity.get('cover_image_id') and key not in approved:continue
            origin={'article_id':article_id,'article_title':article['title'],'source_url':image.get('source_url','')}
            if key not in result:
                result[key]={'id':key,'url':url,'alt':image.get('alt',''),**origin,'origins':[]}
            if origin not in result[key]['origins']:result[key]['origins'].append(origin)
    return list(result.values())


class Lead(BaseModel):
    found: bool
    title: str = Field(default='',max_length=180)
    change: str = Field(default='',max_length=1000)
    relevance: str = Field(default='',max_length=1000)
    conditions: str = Field(default='',max_length=1000)
    counterevidence: str = Field(default='',max_length=1000)
    next_steps: str = Field(default='',max_length=1000)
    fact_ids: list[str] = Field(default_factory=list,max_length=20)


class Answer(BaseModel):
    text: str = Field(min_length=1,max_length=6000)
    fact_ids: list[str] = Field(default_factory=list,max_length=30)


class Repository:
    def __init__(self, store):
        self.store=store
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS entity_dossiers(owner TEXT NOT NULL,id TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(owner,id));
                CREATE TABLE IF NOT EXISTS entity_articles(owner TEXT NOT NULL,article TEXT NOT NULL,signature TEXT NOT NULL,PRIMARY KEY(owner,article));
                CREATE TABLE IF NOT EXISTS entity_leads(owner TEXT NOT NULL,id TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(owner,id));
            ''')

    def snapshot(self,owner):
        state=self.store.snapshot(owner)
        articles={a['id']:a for a in state['articles']}
        with self.store.connect() as db:
            entities=[json.loads(r['data']) for r in db.execute('SELECT data FROM entity_dossiers WHERE owner=?',(owner,))]
            leads=[json.loads(r['data']) for r in db.execute('SELECT data FROM entity_leads WHERE owner=? ORDER BY rowid DESC',(owner,))]
        for e in entities:
            e['facts']=[{**f,'sources':articles[f['article_id']].get('sources',[]),
                         'channel_id':articles[f['article_id']]['channel_id'],
                         'historical': f['article_version']!=article_signature(articles[f['article_id']])}
                        for f in e['facts'] if f['article_id'] in articles]
            current=[f for f in e['facts'] if not f.get('historical')]
            e['dossier_status']='substantive' if e.get('watched') or e.get('manual') or any(f.get('coverage')=='substantive' for f in current) else ('pending' if any('coverage' not in f for f in current) else 'mention')
            e['attribute_groups']=aggregate(e.get('attributes',[]),articles)
            e['images']=related_images(e,articles)
            e['cover_image']=next((i for i in e['images'] if i['id']==e.get('cover_image_id')),next(iter(e['images']),None))
            e['channel_ids']=list(dict.fromkeys(f['channel_id'] for f in e['facts']))
        dismissed=[{'id':e['id'],'name':e['name'],'aliases':e['aliases']} for e in entities if e.get('dismissed')]
        blocked={normalized(n) for e in dismissed for n in [e['name'],*e['aliases']]}
        entities=[e for e in entities if not blocked.intersection(normalized(n) for n in [e['name'],*e['aliases']]) and not e.get('redirect') and (e['facts'] or e.get('watched') or e.get('manual'))]
        allowed={f['id'] for e in entities for f in e['facts']}
        valid={e['id']:e for e in entities}
        leads=[{**l,'stale':l.get('rule','')!=valid[l['entity_id']].get('rule','')} for l in leads
               if l['entity_id'] in valid and l['fact_ids'] and set(l['fact_ids']).issubset(allowed)]
        return {'entities':entities,'dismissed_entities':dismissed,'opportunities':leads[:200], 'channel_taxonomies':{c['id']:c.get('entity_taxonomy') for c in state['channels']}}

    def image_settings(self, owner, id, body):
        visible=next((e for e in self.snapshot(owner)['entities'] if e['id']==id),None)
        if not visible: raise KeyError('实体不存在或不可见')
        if body.image_id not in {i['id'] for i in visible['images']}: raise ValueError('图片已移除或不属于该实体')
        with self.store.connect() as db:
            row=db.execute('SELECT data FROM entity_dossiers WHERE owner=? AND id=?',(owner,id)).fetchone()
            if not row: raise KeyError('实体不存在')
            value=json.loads(row['data'])
            if body.action=='remove':
                value['excluded_image_ids']=list(set(value.get('excluded_image_ids',[]))|{body.image_id})
                if value.get('cover_image_id')==body.image_id:value.pop('cover_image_id')
            else:
                if body.image_id in value.get('excluded_image_ids',[]):raise ValueError('图片已移除')
                value['cover_image_id']=body.image_id
            value['revision']+=1
            db.execute('UPDATE entity_dossiers SET data=? WHERE owner=? AND id=?',(json.dumps(value),owner,id))
        return {'ok':True}

    def dismiss(self, owner, id, dismissed=True):
        with self.store.connect() as db:
            row=db.execute('SELECT data FROM entity_dossiers WHERE owner=? AND id=?',(owner,id)).fetchone()
            if not row:raise KeyError('实体不存在或不属于当前用户')
            value=json.loads(row['data'])
            value['dismissed']=dismissed
            if dismissed:value['watched']=False
            value['revision']+=1;value['updated_at']=stamp()
            value.pop('evaluated_signature',None)
            db.execute('UPDATE entity_dossiers SET data=? WHERE owner=? AND id=?',(json.dumps(value),owner,id))
        return {'ok':True}

    def get(self,owner,id):
        with self.store.connect() as db:
            row=db.execute('SELECT data FROM entity_dossiers WHERE owner=? AND id=?',(owner,id)).fetchone()
        if not row: raise KeyError('实体不存在或不属于当前用户')
        return json.loads(row['data'])

    def pending(self,owner,articles):
        with self.store.connect() as db:
            done={r['article']:r['signature'] for r in db.execute('SELECT * FROM entity_articles WHERE owner=?',(owner,))}
            # Upgrade exact legacy cache hits without asking the model to repeat
            # already validated extraction. Changed legacy evidence stays pending.
            for article in articles:
                legacy=signature(['entity-attributes-v2',article_signature(article),image_candidates(article)])
                if done.get(article['id'])==legacy:
                    current=extraction_signature(article)
                    db.execute('UPDATE entity_articles SET signature=? WHERE owner=? AND article=? AND signature=?',
                        (current,owner,article['id'],legacy))
                    done[article['id']]=current
        pending=[a for a in articles if done.get(a['id'])!=extraction_signature(a)]
        known={f['article_id'] for e in self.snapshot(owner)['entities'] for f in e['facts']}
        return sorted(pending,key=lambda a:a['id'] not in known)

    def ingest(self,owner,article,plan):
        version=article_signature(article)
        with self.store.connect() as db:
            current=db.execute('SELECT data FROM articles WHERE owner=? AND id=?',(owner,article['id'])).fetchone()
            if not current or extraction_signature(json.loads(current['data']))!=extraction_signature(article):
                raise ValueError('文章已变化，请重新整理')
            row=db.execute('SELECT signature FROM entity_articles WHERE owner=? AND article=?',(owner,article['id'])).fetchone()
            if row and row['signature']==extraction_signature(article): return
            existing=[json.loads(r['data']) for r in db.execute('SELECT data FROM entity_dossiers WHERE owner=?',(owner,))]
            for old in existing:
                for f in old['facts']:
                    if f['article_id']==article['id']:
                        f.update(coverage='mention',coverage_reason='本轮未获得实质介绍证据',image_ids=[])
                db.execute('UPDATE entity_dossiers SET data=? WHERE owner=? AND id=?',(json.dumps(old),owner,old['id']))
            for draft in plan.entities:
                names={canonical(n) for n in [draft.name,*draft.aliases]}
                blocked=[e for e in existing if e.get('dismissed') and names.intersection(canonical(n) for n in [e['name'],*e['aliases']])]
                if blocked:
                    for e in blocked:
                        e['aliases']=list(dict.fromkeys([*e['aliases'],draft.name,*draft.aliases]))
                        db.execute('UPDATE entity_dossiers SET data=? WHERE owner=? AND id=?',(json.dumps(e),owner,e['id']))
                    continue
                matches=[e for e in existing if (e['kind']==draft.kind or {draft.kind,e['kind']}=={'product','model'}) and (not draft.brand or not e.get('brand') or canonical(draft.brand)==canonical(e['brand'])) and (not draft.reference or not e.get('reference') or canonical(draft.reference)==canonical(e['reference'])) and names.intersection(canonical(n) for n in [e['name'],*e['aliases']])]
                draft_refs=references(draft.model_dump())
                matches=[e for e in matches if not draft_refs or not references(e) or draft_refs.intersection(references(e))]
                resolved={}
                for match in matches:
                    visited=set()
                    while match.get('redirect'):
                        if match['id'] in visited:raise ValueError('实体归属存在循环，请修正档案')
                        visited.add(match['id']);match=next(x for x in existing if x['id']==match['redirect'])
                    resolved[match['id']]=match
                matches=list(resolved.values())
                # Ambiguous aliases never silently merge two records.
                if len(matches)==1:
                    e=matches[0]
                    visited=set()
                    while e.get('redirect'):
                        if e['id'] in visited: raise ValueError('实体归属存在循环，请修正档案')
                        visited.add(e['id'])
                        e=next(x for x in existing if x['id']==e['redirect'])
                else:
                    e={'id':uuid.uuid4().hex,'name':draft.name,'kind':draft.kind,'aliases':[], 'facts':[],
                       'watched':False,'rule':'','revision':0,'created_at':stamp()}
                    existing.append(e)
                if e.get('dismissed'):continue
                if not e.get('identity_locked'):
                    if draft.kind == 'model' and e['kind'] == 'product':
                        e['kind'] = 'model'
                    e['aliases']=list(dict.fromkeys([*e['aliases'],draft.name,*draft.aliases]))[:20]
                for field in ('brand','reference'):
                    if getattr(draft,field,'') and not e.get(field):e[field]=getattr(draft,field)
                for fact in draft.facts:
                    target=e.get('fact_moves',{}).get(signature([article['id'],fact.quote]))
                    dest=next((x for x in existing if x['id']==target),e)
                    if dest.get('dismissed'):continue
                    fid=signature([dest['id'],article['id'],version,fact.text,fact.quote])[:32]
                    metadata={'coverage':draft.coverage,'coverage_reason':draft.coverage_reason,'image_ids':draft.image_ids if draft.coverage=='substantive' else []}
                    for previous in dest['facts']:
                        if previous['id']==fid:previous.update(metadata)
                    if not any(f['id']==fid for f in dest['facts']):
                        dest['facts'].append({**fact.model_dump(),**metadata,'id':fid,'article_id':article['id'],'article_title':article['title'],
                                           'article_version':version,'observed_at':article['updated_at'],'recorded_at':stamp()})
                    if dest is not e:
                        dest['revision']+=1;dest['updated_at']=stamp()
                        db.execute('UPDATE entity_dossiers SET data=? WHERE owner=? AND id=?',(json.dumps(dest),owner,dest['id']))
                if draft.attribute_domain!='other' or draft.attributes:
                    validate_attributes(draft.attribute_domain,draft.attributes,'\n'.join(article.get(k,'') for k in ('title','summary','body')),article['id'])
                    self._record_attributes(e,article,draft.attribute_domain,draft.attributes)
                e['revision']+=1;e['updated_at']=stamp()
                db.execute('INSERT INTO entity_dossiers VALUES(?,?,?) ON CONFLICT(owner,id) DO UPDATE SET data=excluded.data',(owner,e['id'],json.dumps(e)))
            db.execute('INSERT INTO entity_articles VALUES(?,?,?) ON CONFLICT(owner,article) DO UPDATE SET signature=excluded.signature',(owner,article['id'],extraction_signature(article)))

    @staticmethod
    def _record_attributes(entity,article,domain,attributes):
        # Retain old versions; re-extraction replaces assertions only for this version.
        version=article_signature(article)
        entity['attributes']=[a for a in entity.get('attributes',[]) if not (a['article_id']==article['id'] and a['article_version']==version)]
        for attr in attributes:
            value={**attr.model_dump(),'domain':domain,'article_id':article['id'],'article_version':version,'observed_at':article['updated_at']}
            value['id']=signature([entity['id'],article['id'],version,domain,attr.key,attr.label,attr.unit,attr.value,attr.conditions,attr.basis,attr.status,attr.quote,attr.context_quote])[:32]
            if not any(a['id']==value['id'] for a in entity['attributes']):entity['attributes'].append(value)
        entity['attribute_domain']=domain
        entity['attribute_schema_revision']=SCHEMA_REVISION
        entity.setdefault('attributes_checked',{})[article['id']]=version

    def save_attributes(self,owner,id,revision,articles,plan):
        with self.store.connect() as db:
            row=db.execute('SELECT data FROM entity_dossiers WHERE owner=? AND id=?',(owner,id)).fetchone()
            if not row:raise KeyError('实体不存在')
            entity=json.loads(row['data'])
            if entity['revision']!=revision or entity.get('redirect') or entity.get('dismissed'):raise ValueError('档案已变化，请重新提取属性')
            allowed={f['article_id'] for f in entity['facts']}
            if any(a.article_id not in {v['id'] for v in articles} for a in plan.attributes):raise ValueError('Unknown attribute article')
            for article in articles:
                current=db.execute('SELECT * FROM articles WHERE owner=? AND id=?',(owner,article['id'])).fetchone()
                if article['id'] not in allowed or not current or article_signature(self.store.unpack(current))!=article_signature(article):raise ValueError('引用文章已变化，请重新提取')
                attrs=[a for a in plan.attributes if a.article_id==article['id']]
                validate_attributes(plan.domain,attrs,'\n'.join(article.get(k,'') for k in ('title','summary','body')),article['id'])
                self._record_attributes(entity,article,plan.domain,attrs)
            entity['revision']+=1;entity['updated_at']=stamp()
            db.execute('UPDATE entity_dossiers SET data=? WHERE owner=? AND id=?',(json.dumps(entity),owner,id))
        return entity

    def merge_duplicate(self,owner,left,right,left_revision,right_revision,reason):
        from .entity_identity import compatible
        if left==right:raise ValueError('请选择不同实体')
        with self.store.connect() as db:
            values={r['id']:json.loads(r['data']) for r in db.execute('SELECT * FROM entity_dossiers WHERE owner=? AND id IN (?,?)',(owner,left,right))}
            if len(values)!=2:raise KeyError('实体不存在或不属于当前用户')
            a,b=values[left],values[right]
            if a['revision']!=left_revision or b['revision']!=right_revision:raise ValueError('档案已变化，请重新核对')
            if not compatible(a,b):raise ValueError('实体类型、型号或用户设置不允许自动合并')
            # Preserve the followed/older entry, so existing links remain useful.
            a,b=sorted([a,b],key=lambda e:(not e.get('watched'),e.get('created_at',''),e['id']))
            a['aliases']=list(dict.fromkeys([*a['aliases'],b['name'],*b['aliases']]))[:20]
            known={f['id'] for f in a['facts']}
            a['facts'] += [f for f in b['facts'] if f['id'] not in known]
            a['watched']=bool(a.get('watched') or b.get('watched'))
            attr_ids={v['id'] for v in a.get('attributes',[])}
            a.setdefault('attributes',[]).extend(v for v in b.get('attributes',[]) if v['id'] not in attr_ids)
            # Missing checkpoint entries are intentionally reviewed again after merging.
            a['attributes_checked']={}
            if not a.get('attribute_domain') or a['attribute_domain']=='other':a['attribute_domain']=b.get('attribute_domain','other')
            for field in ('rule','brand','reference','cover_image_id'):
                if not a.get(field) and b.get(field):a[field]=b[field]
            a['excluded_image_ids']=list(set(a.get('excluded_image_ids',[]))|set(b.get('excluded_image_ids',[])))
            if a.get('cover_image_id') in a['excluded_image_ids']:a.pop('cover_image_id',None)
            a.setdefault('fact_moves',{}).update(b.get('fact_moves',{}))
            a['fact_moves']={k:a['id'] if v==b['id'] else v for k,v in a['fact_moves'].items()}
            for row in db.execute('SELECT id,data FROM entity_dossiers WHERE owner=?',(owner,)).fetchall():
                value=json.loads(row['data'])
                if value['id'] in (a['id'],b['id']):continue
                moves=value.get('fact_moves',{})
                changed=False
                for k,v in moves.items():
                    if v==b['id']:moves[k]=a['id'];changed=True
                if value.get('redirect')==b['id']:value['redirect']=a['id'];changed=True
                if changed:db.execute('UPDATE entity_dossiers SET data=? WHERE owner=? AND id=?',(json.dumps(value),owner,value['id']))
            b['redirect']=a['id']
            audit={'source_id':b['id'],'target_id':a['id'],'reason':reason,'merged_at':stamp()}
            a.setdefault('identity_merges',[]).append(audit);b['identity_merge']=audit
            for value in (a,b):
                value['revision']+=1;value['updated_at']=stamp();value.pop('evaluated_signature',None)
                db.execute('UPDATE entity_dossiers SET data=? WHERE owner=? AND id=?',(json.dumps(value),owner,value['id']))
            for row in db.execute('SELECT id,data FROM entity_leads WHERE owner=?',(owner,)).fetchall():
                lead=json.loads(row['data'])
                if lead['entity_id']==b['id']:
                    lead.update(entity_id=a['id'],entity_name=a['name'])
                    db.execute('UPDATE entity_leads SET data=? WHERE owner=? AND id=?',(json.dumps(lead),owner,row['id']))
            for row in db.execute('SELECT id,data FROM channels WHERE owner=?',(owner,)).fetchall():
                channel=json.loads(row['data']);taxonomy=channel.get('entity_taxonomy') or {}
                if b['id'] in taxonomy.get('assignments',{}):
                    assignment=taxonomy['assignments'].pop(b['id']);taxonomy['assignments'].setdefault(a['id'],assignment)
                    taxonomy.get('signatures',{}).pop(b['id'],None)
                    db.execute('UPDATE channels SET data=? WHERE owner=? AND id=?',(json.dumps(channel),owner,row['id']))
        return audit

    def settings(self,owner,id,body):
        with self.store.connect() as db:
            row=db.execute('SELECT data FROM entity_dossiers WHERE owner=? AND id=?',(owner,id)).fetchone()
            if not row: raise KeyError('实体不存在')
            e=json.loads(row['data'])
            if e['revision']!=body.revision: raise ValueError('档案已更新，请重新打开后保存')
            if not body.name.strip() or any(not a.strip() or len(a)>160 for a in body.aliases): raise ValueError('名称或别名无效')
            e.update(body.model_dump());e['name']=e['name'].strip();e['revision']+=1;e['identity_locked']=True;e.pop('evaluated_signature',None)
            db.execute('UPDATE entity_dossiers SET data=? WHERE owner=? AND id=?',(json.dumps(e),owner,id))
        return e

    def create(self,owner,name,kind):
        if not name.strip(): raise ValueError('名称不能为空')
        value={'id':uuid.uuid4().hex,'name':name.strip(),'kind':kind,'aliases':[],'facts':[],
               'watched':False,'rule':'','manual':True,'identity_locked':True,'revision':0,'created_at':stamp()}
        with self.store.connect() as db:
            db.execute('INSERT INTO entity_dossiers VALUES(?,?,?)',(owner,value['id'],json.dumps(value)))
        return value

    def move(self,owner,source,target,fact_ids):
        if source==target: raise ValueError('请选择不同的目标实体')
        with self.store.connect() as db:
            rows={r['id']:json.loads(r['data']) for r in db.execute('SELECT * FROM entity_dossiers WHERE owner=? AND id IN (?,?)',(owner,source,target))}
            if len(rows)!=2: raise KeyError('实体不存在')
            a,b=rows[source],rows[target]
            if not fact_ids or not set(fact_ids).issubset({f['id'] for f in a['facts']}): raise ValueError('请选择当前实体中的事实')
            moving=[f for f in a['facts'] if f['id'] in fact_ids]
            b['facts'] += [f for f in moving if f['id'] not in {x['id'] for x in b['facts']}]
            a['facts']=[f for f in a['facts'] if f['id'] not in fact_ids]
            for f in moving:
                a.setdefault('fact_moves',{})[signature([f['article_id'],f['quote']])]=target
            if not a['facts'] and a['kind']==b['kind']:
                if b.get('redirect'): raise ValueError('目标实体已合并，请选择有效档案')
                a['redirect']=target
                attr_ids={v['id'] for v in b.get('attributes',[])}
                b.setdefault('attributes',[]).extend(v for v in a.get('attributes',[]) if v['id'] not in attr_ids)
                b['attributes_checked']={}
            for e in [a,b]:
                e['revision']+=1;e['identity_locked']=True;e.pop('evaluated_signature',None)
                db.execute('UPDATE entity_dossiers SET data=? WHERE owner=? AND id=?',(json.dumps(e),owner,e['id']))
            # Old opportunity interpretations may no longer identify the correct entity.
            db.execute('DELETE FROM entity_leads WHERE owner=? AND (json_extract(data,\'$.entity_id\')=? OR json_extract(data,\'$.entity_id\')=?)',(owner,source,target))
        return {'ok':True}

    def save_lead(self,owner,entity,digest,lead):
        with self.store.connect() as db:
            row=db.execute('SELECT data FROM entity_dossiers WHERE owner=? AND id=?',(owner,entity['id'])).fetchone()
            if not row or json.loads(row['data'])['revision']!=entity['revision']: raise ValueError('实体已变化，请重新分析')
            current=json.loads(row['data']);current['evaluated_signature']=digest
            db.execute('UPDATE entity_dossiers SET data=? WHERE owner=? AND id=?',(json.dumps(current),owner,entity['id']))
            if lead.found:
                id=signature([entity['id'],digest])[:32]
                value={**lead.model_dump(),'id':id,'entity_id':entity['id'],'entity_name':entity['name'],'rule':entity['rule'], 'status':'new','created_at':stamp()}
                db.execute('INSERT OR IGNORE INTO entity_leads VALUES(?,?,?)',(owner,id,json.dumps(value)))

    def lead_status(self,owner,id,status,reason):
        with self.store.connect() as db:
            row=db.execute('SELECT data FROM entity_leads WHERE owner=? AND id=?',(owner,id)).fetchone()
            if not row: raise KeyError('机会线索不存在')
            value=json.loads(row['data']);value.update(status=status,feedback_reason=reason)
            db.execute('UPDATE entity_leads SET data=? WHERE owner=? AND id=?',(json.dumps(value),owner,id))
        return value


def article_signature(article):
    return signature({k:article.get(k) for k in ('title','summary','body','updated_at','sources')})


def image_candidates(article):
    images={}
    for image in [article.get('cover_image') or {},*article.get('images',[])]:
        url=cover_url(image.get('url',''))
        if not url:continue
        key=hashlib.sha256(url.encode()).hexdigest()
        # Empty cover metadata must not erase a caption from the body image.
        if key not in images or image.get('alt'):
            images[key]={'id':key,'caption':image.get('alt',''),'url':url}
    return list(images.values())


def extraction_signature(article):
    # Cache only extraction evidence; preserve separate historical versions.
    return signature(['entity-attributes-v3', {k:article.get(k) for k in
        ('title','summary','body')},image_candidates(article)])


async def extract(runtime,request,principal,article):
    text='\n'.join(article.get(k,'') for k in ('title','summary','body'))
    candidates=image_candidates(article)
    allowed_images={i['id'] for i in candidates if i['caption'].strip()}
    def validate(value):
        plan=Extraction.model_validate(value)
        seen=set()
        for e in plan.entities:
            if not e.coverage_reason.strip():raise ValueError('Coverage needs an evidence-based reason')
            if not set(e.image_ids).issubset(allowed_images):raise ValueError('Images need supplied identifying captions')
            if e.coverage=='mention' and e.image_ids:raise ValueError('Incidental mentions must not inherit images')
            if (e.kind,normalized(e.name)) in seen: raise ValueError('Duplicate entity')
            seen.add((e.kind,normalized(e.name)))
            if e.name.casefold() not in text.casefold(): raise ValueError('Entity name absent from ARTICLE text: '+repr(e.name)+'. Copy a literal name from article text, never from image captions, or omit this entity.')
            if any(not a.strip() or len(a)>160 or a.casefold() not in text.casefold() for a in e.aliases): raise ValueError('Aliases must appear in evidence')
            if any(v and v.casefold() not in text.casefold() for v in [e.brand,e.reference]):raise ValueError('Brand and reference must occur in evidence')
            validate_attributes(e.attribute_domain,e.attributes,text,article.get('id',''))
            if any(f.quote not in text for f in e.facts): raise ValueError('Quotes must be exact excerpts')
        return plan
    return await service.model_json(runtime,request,principal,article['channel_id'],
        'Extract concrete entity dossiers from this collected article, not from external knowledge. '
        'Use kind=model for AI models and their versions, product for hardware/software products, event for events. '
        'Classify coverage by semantic substance, never name frequency or fact count: substantive means this article actually introduces or discusses this specific entity with meaningful detail. '
        'A competitor price/size comparison, passing example, name-drop or background mention is mention, even if it provides a concrete fact. Preserve these as mention records. '
        'Explain coverage_reason using this article. Assign image_ids ONLY when the supplied image caption identifies this exact entity (including a clear bilingual name equivalence); '
        'never inherit all article images or its cover. An image of another model/brand/person is not this entity. Empty or ambiguous captions mean no assignment. '
        'Do not claim visual inspection; only captions are supplied. Mentions get no image_ids. '
        'Separate brand, product series and exact model/size/variant; never merge different model numbers. '
        'Include brand and reference only when explicitly stated in the article, copying their literal spelling; otherwise use empty strings. '
        'List literal alternative spellings and bilingual equivalents as aliases only when this article establishes the same entity. '
        'When a reference number identifies the same watch as its full model name, put that literal reference in aliases/reference, not a second dossier. '
        'Do not create another dossier for a generic color/material description of an already extracted exact model. '
        'Extract series separately only when the text substantively discusses the series itself; background series membership is a mention. '
        'Image captions are ONLY for matching images to entities already evidenced in article text; NEVER extract additional entities from captions or URLs. '
        'Copy names and aliases exactly from article text without translating, expanding brand prefixes or changing spacing. '
        'Names and aliases must occur literally in the article. Avoid generic categories and publication names unless the article is about them. '
        +ATTRIBUTE_INSTRUCTION+'Use attribute_domain (not domain) in each entity object. Use kind=model for a specific model/version in ANY domain, product for a general product; kind and attribute_domain are independent. '
        'Each fact needs an exact supporting quote from supplied text. Preserve qualifiers, dates, units and distinction between asking and transaction prices. '
        'reported means reported by this article, NOT independently verified. Use opinion or rumour appropriately. '
        'Do not infer a release date from collection time. Return empty entities if unsupported. Schema: '+json.dumps(Extraction.model_json_schema()),
        {'article':text[:30000],'images':candidates},validate)


class RelevanceDecision(BaseModel):
    entity_id: str
    attribute_domain: Domain = 'other'
    attributes: list[Attribute] = Field(default_factory=list,max_length=30)
    coverage: Literal['substantive','mention']
    coverage_reason: str = Field(min_length=1,max_length=600)
    image_ids: list[str] = Field(default_factory=list,max_length=48)


class RelevanceReview(BaseModel):
    decisions: list[RelevanceDecision]


async def extract_or_review(runtime,request,principal,article,repo):
    version=article_signature(article)
    existing=[]
    for e in repo.snapshot(principal.actor_user_id)['entities']:
        relevant=[f for f in e['facts'] if f['article_id']==article['id'] and f['article_version']==version]
        if relevant:existing.append((e,relevant))
    if not existing:return await extract(runtime,request,principal,article)
    allowed={e['id'] for e,f in existing}
    images=image_candidates(article)
    image_ids={i['id'] for i in images if i['caption'].strip()}
    def validate(value):
        review=RelevanceReview.model_validate(value)
        if len(review.decisions)!=len(allowed) or {d.entity_id for d in review.decisions}!=allowed:raise ValueError('Review every supplied entity exactly once')
        for d in review.decisions:
            if not set(d.image_ids).issubset(image_ids):raise ValueError('Only supplied captioned image IDs may be assigned')
            if d.coverage=='mention' and d.image_ids:raise ValueError('Incidental mentions have no images')
            validate_attributes(d.attribute_domain,d.attributes,'\n'.join(article.get(k,'') for k in ('title','summary','body')),article['id'])
        return review
    result=await service.model_json(runtime,request,principal,article['channel_id'],
        'Review existing entity dossiers against the article. Do NOT rewrite names or facts. '
        'substantive means meaningful introduction or discussion of this specific entity. A competitor price/size comparison, '
        'background reference, example or name-drop is mention, even if it has a concrete fact. Never use frequency or fact count as a threshold. '
        'Give a localized coverage_reason grounded in this article. Assign image_ids only when the caption explicitly identifies this exact entity '
        '(clear bilingual name equivalents are allowed). Never inherit the article cover or all article images. '
        'Do not assign pictures of other models, brands or people; ambiguous or missing captions mean no image. '
        +ATTRIBUTE_INSTRUCTION+'Use attribute_domain in each decision. '
        'No pixels were provided, so do not claim visual recognition. mention must have empty image_ids. Schema: '+json.dumps(RelevanceReview.model_json_schema()),
        {'article':{k:article.get(k,'') for k in ('title','summary','body')},
         'entities':[{'id':e['id'],'name':e['name'],'aliases':e['aliases'],'facts':[f['quote'] for f in facts]} for e,facts in existing],
         'images':images},validate)
    decisions={d.entity_id:d for d in result.decisions}
    return Extraction.model_construct(entities=[EntityDraft.model_construct(name=e['name'],kind=e['kind'],aliases=e['aliases'],
        facts=[Fact(text=f['text'],quote=f['quote'],status=f['status']) for f in facts],
        coverage=decisions[e['id']].coverage,coverage_reason=decisions[e['id']].coverage_reason,image_ids=decisions[e['id']].image_ids,attribute_domain=decisions[e['id']].attribute_domain,attributes=decisions[e['id']].attributes)
        for e,facts in existing])


async def opportunity(runtime,request,principal,entity,previous):
    facts=[f for f in entity['facts'] if not f.get('historical')][-60:]
    allowed={f['id'] for f in facts}
    def validate(value):
        lead=Lead.model_validate(value)
        if not set(lead.fact_ids).issubset(allowed) or len(set(lead.fact_ids))!=len(lead.fact_ids): raise ValueError('Invalid evidence IDs')
        if lead.found and (not lead.fact_ids or any(not getattr(lead,k).strip() for k in ('title','change','relevance','conditions','counterevidence','next_steps'))): raise ValueError('Lead needs evidence and all assessment fields')
        return lead
    return await service.model_json(runtime,request,principal,'entity-'+entity['id'],
        'Evaluate this user watch rule against dossier evidence. Return found=false unless a substantive new opportunity lead matches the rule. '
        'Compare previous leads and ignore repetitive or previously dismissed interpretations; consider dismissal reasons. '
        'These are research leads, NOT buy/sell recommendations. Separate observed change, inferred relevance, conditions, counterevidence and next verification steps. '
        'Never invent market price, valuation, financial return, certainty or timeliness. Without dated reliable market/valuation evidence do not claim cheap, underpriced, profitable or entry timing. '
        'Treat asking prices separately from actual transactions. Old news is not a new event because it was collected today. '
        'Surface evidence gaps and contradictory facts. If no contrary evidence exists, say it is unverified, not that there is no risk. '
        'Cite ONLY supplied fact_ids. Schema: '+json.dumps(Lead.model_json_schema()),
        {'entity':entity['name'],'rule':entity['rule'],'facts':facts,'previous_leads':previous[-20:]},validate)


async def answer(runtime,request,principal,entity,question):
    facts=entity['facts'][-60:];allowed={f['id'] for f in facts}
    def validate(value):
        result=Answer.model_validate(value)
        if not set(result.fact_ids).issubset(allowed): raise ValueError('Unknown fact citation')
        if facts and not result.fact_ids: raise ValueError('Cite evidence or explicitly ask a question with cited context')
        return result.model_dump()
    return await service.model_json(runtime,request,principal,'entity-'+entity['id'],
        'Answer about this entity using ONLY dossier evidence across the supplied channels. Explain missing evidence and conflicting/historical claims. '
        'Do not browse or invent facts. Return supporting fact_ids. Schema: '+json.dumps(Answer.model_json_schema()),
        {'entity':entity['name'],'question':question,'facts':facts},validate)
