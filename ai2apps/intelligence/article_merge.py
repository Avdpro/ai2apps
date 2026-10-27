"""Owner-only incremental editorial composition. Generated old prose is not evidence."""
import copy
import hashlib
import re
from . import article_content as content

SCHEMA = 'ai2apps.article-content/v2'


def identity(prefix, value):
    return prefix + hashlib.sha256(value.encode()).hexdigest()[:24]


def structure(article, topics=()):
    """Give legacy/v1 paragraphs persistent identities without changing their text."""
    if article.get('content_schema') == SCHEMA:
        return copy.deepcopy(article['content_blocks']), copy.deepcopy(article.get('editorial_sections',[]))
    parts=content.paragraphs(article.get('body',''))
    topics=list(topics) if topics else ['']*len(parts)
    if len(topics)!=len(parts):raise ValueError('paragraph_topics must correspond to every body paragraph')
    sections=[];blocks=[];last=None;index=0
    for part,title in zip(parts,topics):
        sid=identity('sec_',title.strip())
        if not any(s['id']==sid for s in sections):sections.append({'id':sid,'title':title.strip()})
        pid=identity('p_',str(article.get('id','new'))+'\n'+str(index)+'\n'+part)
        blocks.append({'type':'paragraph','id':pid,'section_id':sid,'text':part});last=pid;index+=1
        if article.get('content_schema')==content.SCHEMA:
            old=article.get('content_blocks',[])
            seen=-1
            for block in old:
                if block['type']=='paragraph':seen+=1
                elif seen==index-1:blocks.append({'type':'image','image_id':block['image_id'],'paragraph_id':last})
    return blocks,sections


def references(text):return {int(i) for i in re.findall(r'\[(\d+)\]',text)}
def remap(text, mapping):
    return re.sub(r'\[(\d+)\]',lambda m:'['+str(mapping[int(m[1])])+']',text)


def validate_focus(article,pages):
    seen=set()
    for item in article.source_focus:
        if item.evidence_id in seen or item.evidence_id>len(pages):raise ValueError('source_focus must use unique supplied evidence IDs')
        seen.add(item.evidence_id)
        page=pages[item.evidence_id-1]
        if item.focus=='dedicated':
            quote=' '.join(item.subject_quote.split()).casefold()
            evidence=' '.join((page.get('title','')+' '+page.get('text','')).split()).casefold()
            if not quote or quote not in evidence or page.get('retained_only'):
                raise ValueError('Dedicated source classification needs an exact subject_quote from supplied original title/text')
    return {f.evidence_id:f for f in article.source_focus}


def prepare(previous,pages):
    """Append source evidence only for already selected update targets, with bounded caches."""
    result=copy.deepcopy(pages); contexts={};by_url={p['url']:i+1 for i,p in enumerate(result)}
    for old in previous:
        if not old.get('body'):continue
        mapping={};budget=60000
        cache=old.get('_cached_pages',{})
        basis=(old.get('editorial_basis') or {}).get('source_url')
        for local,source in enumerate(old.get('sources',[]),1):
            url=source.get('url')
            if not url:continue
            if url not in by_url:
                stored=cache.get(url);text=stored.get('text','') if stored else ''
                cap=min(budget,20000 if url==basis else 6000);excerpt=text[:max(0,cap)];budget-=len(excerpt)
                page={**source,**(stored or {}),'url':url,'text':excerpt,'title':source.get('title',''),
                      'source_name':source.get('source_name',''),'retrieved_at':source.get('retrieved_at',''),
                      'retained_only':not bool(excerpt),'historical_evidence':True}
                if len(text)>len(excerpt):page['coverage']='preview'
                page['images']=[{k:i.get(k,'') for k in ('url','alt')} for i in old.get('images',[]) if i.get('source_url')==url]
                if old.get('cover_image',{}).get('source_url')==url:page['image_url']=old['cover_image']['url']
                result.append(page);by_url[url]=len(result)
            mapping[local]=by_url[url]
        blocks,sections=structure(old)
        for b in blocks:
            if b['type']=='paragraph':
                if not references(b['text']).issubset(mapping):raise ValueError('Old article has unresolved source references; cannot safely merge')
                b['text']=remap(b['text'],mapping)
        contexts[old['id']]={'article':old,'blocks':blocks,'sections':sections,'source_mapping':mapping,
                             'body':'\n\n'.join(b['text'] for b in blocks if b['type']=='paragraph')}
    return result,contexts


def apply(article,context,pages,focus):
    blocks=copy.deepcopy(context['blocks']);sections=copy.deepcopy(context['sections']);audit=[]
    original_ids={b['id'] for b in blocks if b['type']=='paragraph'}
    touched=set();available=set(article.evidence_ids);insertion_tails={}
    for index,change in enumerate(article.merge_changes):
        target=change.paragraph_id
        if context['article'].get('_forced_backbone') and change.operation!='add':
            raise ValueError('Manual import preserves its selected backbone; only supplemental additions are allowed')
        if change.operation!='add' and (target not in original_ids or target in touched):raise ValueError('Merge target must be an existing unchanged paragraph ID, used at most once')
        if change.operation!='add':touched.add(target)
        proofs=set()
        for proof in change.proofs:
            if proof.evidence_id not in available or proof.evidence_id>len(pages):raise ValueError('Merge proof must cite supplied article evidence')
            page=pages[proof.evidence_id-1]
            if page.get('retained_only') or ' '.join(proof.quote.split()).casefold() not in ' '.join(page.get('text','').split()).casefold():raise ValueError('Merge proof quote is absent from original evidence')
            proofs.add(proof.evidence_id)
        if change.operation in ('add','replace','remove') and not proofs:raise ValueError('Content changes/removals need exact original-evidence proof quotes')
        if change.operation in ('add','replace'):
            if not change.text.strip() or len(content.paragraphs(change.text))!=1:raise ValueError('Each change must contain exactly one paragraph')
            refs=references(change.text)
            if not refs or not refs.issubset(proofs):raise ValueError('Every changed-paragraph citation needs a corresponding original-evidence proof')
        paragraph=next((b for b in blocks if b.get('id')==target),None)
        if change.operation=='remove':
            blocks=[b for b in blocks if b is not paragraph and b.get('paragraph_id')!=target]
        elif change.operation=='replace':
            paragraph['text']=change.text.strip()
            # A retained image may only stay with a paragraph still citing its source.
            source_ids=context['source_mapping']
            old_images={i.get('id') or content.image_id(i['source_url'],i['url']):i for i in context['article'].get('images',[])}
            def keep(b):
                if b.get('paragraph_id')!=target:return True
                image=old_images.get(b['image_id']);source=image and next((i+1 for i,p in enumerate(pages) if p['url']==image['source_url']),None)
                return source in references(paragraph['text'])
            blocks=[b for b in blocks if keep(b)]
        else:
            after=change.after_id
            if change.operation=='add':after=insertion_tails.get(after,after)
            if after==target:raise ValueError('A paragraph cannot follow itself')
            if after is not None and not any(b.get('id')==after for b in blocks):raise ValueError('after_id must reference a retained paragraph')
            if change.operation=='add':
                target=identity('p_',context['article']['id']+'\n'+str(index)+'\n'+change.text)
                paragraph={'type':'paragraph','id':target,'section_id':identity('sec_',change.section_title.strip()),'text':change.text.strip()}
                moving=[paragraph]
            else:
                moving=[b for b in blocks if b is paragraph or b.get('paragraph_id')==target]
                blocks=[b for b in blocks if b not in moving]
            if change.section_title:
                sid=identity('sec_',change.section_title.strip());paragraph['section_id']=sid
                if not any(s['id']==sid for s in sections):sections.append({'id':sid,'title':change.section_title.strip()})
            if not any(s['id']==paragraph['section_id'] for s in sections):sections.append({'id':paragraph['section_id'],'title':change.section_title.strip()})
            at=0 if after is None else next(i for i,b in enumerate(blocks) if b.get('id')==after)+1
            while at<len(blocks) and blocks[at].get('paragraph_id')==after:at+=1
            blocks[at:at]=moving
            if change.operation=='add':insertion_tails[change.after_id]=target
        audit.append({'operation':change.operation,'paragraph_id':target,'reason':change.reason,'evidence_ids':sorted(proofs)})
    if len(blocks)>128:raise ValueError('At most 128 paragraph/image blocks per article')
    if not any(b['type']=='paragraph' for b in blocks):raise ValueError('Merge cannot remove the entire article')
    article.body='\n\n'.join(b['text'] for b in blocks if b['type']=='paragraph')
    if len(article.body)>40000:raise ValueError('Merged article exceeds 40000 characters; split changes, do not truncate')
    # Keep every retained old source; no old generated prose is introduced as new evidence.
    retained=set().union(*(references(b['text']) for b in blocks if b['type']=='paragraph'))
    article.evidence_ids=list(dict.fromkeys(article.evidence_ids+sorted(retained)))
    return blocks,sections,audit


def choose_basis(article,pages,focus,old=None,*,forced_url=None,new_count=0):
    candidates=[(i,f) for i,f in focus.items() if f.focus=='dedicated' and i in article.evidence_ids and not pages[i-1].get('retained_only')]
    old_basis=copy.deepcopy((old or {}).get('editorial_basis') or {})
    best=max(candidates,key=lambda pair:pair[1].detail_score,default=None)
    if forced_url:
        return {'subject':article.subject or article.title,'source_url':forced_url,'forced_manual':True,'detail_score':5}
    if best and (not old_basis or best[1].detail_score>old_basis.get('detail_score',-1)):
        return {'subject':article.subject or article.title,'source_url':pages[best[0]-1]['url'],'detail_score':best[1].detail_score,'focus':'dedicated'}
    return old_basis or {'subject':article.subject or article.title,'source_url':pages[(article.primary_evidence_id or article.evidence_ids[0])-1]['url'],'detail_score':0,'focus':'uncertain'}
