"""Source-ordered manual article layout; translation retains paragraph identity."""
import copy
import hashlib
import re
from . import article_content as content, article_merge as merge
from .models import cover_url


def source_paragraphs(article):
    blocks=article.get('source_blocks') or []
    paragraphs=[{'id':b.get('id'),'text':b.get('text','').strip()} for b in blocks if b.get('type')=='paragraph' and b.get('text','').strip()]
    if not paragraphs:
        paragraphs=[{'id':'sp_'+str(i),'text':text} for i,text in enumerate(content.paragraphs(article['body']))]
    ids=[p['id'] for p in paragraphs]
    if any(not isinstance(i,str) or not i for i in ids) or len(set(ids))!=len(ids):raise ValueError('Source paragraph IDs must be nonempty and unique')
    return paragraphs


def batches(paragraphs, limit=6000):
    """Pack complete paragraphs; never split words or drop the long-paragraph tail."""
    batch=[];size=0
    for paragraph in paragraphs:
        if batch and size+len(paragraph['text'])>limit:
            yield batch;batch=[];size=0
        batch.append(paragraph);size+=len(paragraph['text'])
    if batch:yield batch


def signature(article):
    return hashlib.sha256(__import__('json').dumps({k:article.get(k) for k in ('body','sources','content_blocks','images','cover_image')},ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def attach(article, mapping, *, source_url=None):
    """Use only owner-supplied source extraction URLs and existing paragraph IDs."""
    result=copy.deepcopy(article)
    blocks,sections=merge.structure(result)
    paragraphs={b['id']:b for b in blocks if b['type']=='paragraph'}
    basis=result.get('editorial_basis') or {}
    source_url=source_url or (basis['source_url'] if basis.get('forced_manual') else result['sources'][0]['url'])
    if source_url not in {s['url'] for s in result['sources']}:raise ValueError('Layout source must belong to this article')
    source_number=next(i+1 for i,s in enumerate(result['sources']) if s['url']==source_url)
    valid_source_ids={b.get('id') for b in result.get('source_blocks',[]) if b.get('type')=='paragraph'}
    if not set(mapping).issubset(valid_source_ids) or not set(mapping.values()).issubset(paragraphs):raise ValueError('Layout mapping must use supplied source and article paragraph IDs')
    pool={};placements={};seen=set();cover=(result.get('cover_image') or {}).get('url')
    for b in result.get('source_blocks',[]):
        if b.get('type')!='image':continue
        pid=mapping.get(b.get('paragraph_id'))
        url=cover_url(b.get('url',''))
        if not pid or not url or url==cover or url in seen:continue
        if source_number not in merge.references(paragraphs[pid]['text']):raise ValueError('Source-positioned image paragraph must cite its original source')
        if len(seen)>=24:break
        seen.add(url);key=content.image_id(source_url,url)
        pool[url]={'id':key,'url':url,'source_url':source_url,'alt':str(b.get('alt',''))[:300]}
        placements.setdefault(pid,[]).append({'type':'image','image_id':key,'paragraph_id':pid})
    # Keep other already-valid source images and supplemental paragraph bindings.
    for image in result.get('images',[]):
        if image.get('url') not in pool:pool[image['url']]={**image,'id':image.get('id') or content.image_id(image['source_url'],image['url'])}
    old_bindings={}
    for block in blocks:
        if block['type']=='image':old_bindings.setdefault(block['paragraph_id'],[]).append(block)
    output=[];used=set()
    for block in blocks:
        if block['type']!='paragraph':continue
        output.append(block)
        for image in placements.get(block['id'],[])+old_bindings.get(block['id'],[]):
            if image['image_id'] not in used and len(used)<24:output.append(image);used.add(image['image_id'])
    result.update(content_schema=merge.SCHEMA,content_blocks=output,editorial_sections=sections,images=list(pool.values())[:48],source_paragraph_map=dict(mapping))
    content.validate_content(result)
    return result


def seed_layout(article):
    """After translation, original image positions are mandatory, not model options."""
    result=copy.deepcopy(article)
    translations=result.get('translation_paragraphs',[])
    if not translations:return result
    paragraphs=content.paragraphs(result['body'])
    if len(paragraphs)!=len(translations):raise ValueError('Translated paragraph identities differ from article body')
    blocks,sections=merge.structure(result)
    ids=[b['id'] for b in blocks if b['type']=='paragraph']
    mapping={p['source_paragraph_id']:pid for p,pid in zip(translations,ids)}
    result.update(content_schema=merge.SCHEMA,content_blocks=blocks,editorial_sections=sections)
    return attach(result,mapping)
