"""Evidence-bound entity equivalence; similar spelling only proposes candidates."""
import difflib
import re
import unicodedata
from pydantic import BaseModel, Field
from . import service


def canonical(value):
    value=unicodedata.normalize('NFKC',value).casefold()
    return ''.join(c for c in value if c.isalnum())


def references(entity):
    values=[entity.get('reference',''),entity['name']]
    return {canonical(code) for value in values for code in re.findall(r'\b(?=[A-Za-z0-9.-]*\d)[A-Za-z][A-Za-z0-9]*(?:[.-][A-Za-z0-9]+)*\b|\b\d+(?:\.\d+){2,}\b',value)}


def compatible(a,b):
    if a['kind']!=b['kind'] and {a['kind'],b['kind']}!={'product','model'}:return False
    if a.get('identity_locked') or b.get('identity_locked') or a.get('redirect') or b.get('redirect') or a.get('dismissed') or b.get('dismissed'):return False
    if a.get('rule') and b.get('rule') and a['rule']!=b['rule']:return False
    if a.get('brand') and b.get('brand') and canonical(a['brand'])!=canonical(b['brand']):return False
    refs_a,refs_b=references(a),references(b)
    if refs_a and refs_b and not refs_a.intersection(refs_b):return False
    return True


def candidates(entities):
    brands=[canonical(n) for e in entities if e['kind']=='brand' for n in [e['name'],*e.get('aliases',[])] if len(canonical(n))>=3]
    def names(e):
        result={canonical(n) for n in [e['name'],*e.get('aliases',[])] if len(canonical(n))>=4}
        for name in list(result):
            for brand in brands:
                if name.startswith(brand) and len(name)>len(brand)+3:result.add(name[len(brand):])
        return result
    result=[]
    for i,a in enumerate(entities):
        for b in entities[i+1:]:
            if not compatible(a,b):continue
            an,bn=names(a),names(b)
            score=max((1 if x==y else difflib.SequenceMatcher(None,x,y).ratio() for x in an for y in bn),default=0)
            if score>=.78:result.append((score,a,b))
    return sorted(result,key=lambda row:(-row[0],row[1]['id'],row[2]['id']))


class Decision(BaseModel):
    left_id: str
    right_id: str
    same_entity: bool
    confidence: str = Field(pattern='^(high|uncertain)$')
    reason: str = Field(min_length=1,max_length=600)
    left_quote: str = Field(default='',max_length=800)
    right_quote: str = Field(default='',max_length=800)


class Decisions(BaseModel):
    decisions: list[Decision] = Field(max_length=20)


async def reconcile(runtime,request,principal,repo,channel_id):
    import json
    snapshot=repo.snapshot(principal.actor_user_id)
    scoped=[e for e in snapshot['entities'] if channel_id in e['channel_ids'] and any(not f.get('historical') for f in e['facts'])]
    pairs=candidates(scoped);merged=[];reviewed=0
    for offset in range(0,len(pairs),20):
        batch=pairs[offset:offset+20]
        allowed={frozenset((a['id'],b['id'])):(a,b) for _,a,b in batch}
        def quotes(e):return list(dict.fromkeys(f['quote'] for f in e['facts'] if not f.get('historical')))[:8]
        def brief(e):return {k:e.get(k) for k in ('id','name','kind','aliases','brand','reference')}|{'quotes':quotes(e)}
        def validate(value):
            plan=Decisions.model_validate(value);seen=set()
            # Omitted candidates remain separate; never infer equivalence from absence.
            for d in plan.decisions:
                key=frozenset((d.left_id,d.right_id))
                if key not in allowed or key in seen:raise ValueError('Unknown or repeated pair')
                seen.add(key)
                a,b=allowed[key]
                if a['id']!=d.left_id:a,b=b,a
                if d.same_entity:
                    if d.confidence!='high' or len(d.left_quote)<4 or len(d.right_quote)<4:raise ValueError('Equivalence requires high confidence and two quotes')
                    if d.left_quote not in quotes(a) or d.right_quote not in quotes(b):raise ValueError('Equivalence quotes must exactly match supplied evidence')
            return plan
        plan=await service.model_json(runtime,request,principal,channel_id,
            'Resolve duplicate dossiers using ONLY their supplied article quotes. Names/aliases are candidate clues, not proof. '
            'Require positive evidence of the SAME referent: brand/manufacturer, exact model/reference and identity level. '
            'Brand alone, similar names, shared article/quote/movement or series membership NEVER imply equality. '
            'Keep brand vs person, series vs model, movement vs watch, different reference numbers, sizes, dial colors, materials, generations and editions separate. '
            'A bare model and brand-prefixed spelling may match only if quotes establish the same brand/model/variant. '
            'A generic name and a named variant do NOT match without evidence that the generic dossier refers exclusively to that exact variant. '
            'Bilingual names or redundant edition suffixes may match when evidence establishes equality. If ambiguous set same_entity=false/confidence=uncertain. '
            'For every true decision copy one exact quote from EACH dossier and explain the identity evidence. No external knowledge. '
            'Return one decision for every pair. Schema: '+json.dumps(Decisions.model_json_schema()),
            {'pairs':[{'left':brief(a),'right':brief(b)} for _,a,b in batch]},validate,stage='entity_identity')
        reviewed+=len(plan.decisions)
        for d in plan.decisions:
            if not d.same_entity:continue
            a,b=allowed[frozenset((d.left_id,d.right_id))]
            try:
                repo.merge_duplicate(principal.actor_user_id,a['id'],b['id'],a['revision'],b['revision'],d.reason)
                merged.append({'left_id':a['id'],'right_id':b['id'],'reason':d.reason})
            except ValueError:
                # Earlier merges or concurrent user edits require a fresh review.
                continue
    return {'merged':len(merged),'reviewed':reviewed,'candidates':len(pairs),'unreviewed':len(pairs)-reviewed,'merges':merged}
