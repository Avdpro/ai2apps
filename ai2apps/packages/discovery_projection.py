"""Discover-owned bounded catalog views. Stored source cards retain all evidence."""
import hashlib
import json
from packaging.version import Version,InvalidVersion


def candidate_id(card):
    fields=[card.get(k) for k in ('package_id','version','kind','identity','mini_app_id','installation_target')]
    return hashlib.sha256(json.dumps(fields,sort_keys=True).encode()).hexdigest()[:32]


def latest(cards):
    groups={}
    def version(card):
        try:return (1,Version(card['version']))
        except InvalidVersion:return (0,card['version'])
    for card in cards:
        key=(card['package_id'],card['kind'],card.get('identity') or card.get('mini_app_id'))
        groups.setdefault(key,[]).append(card)
    # Prefer a known compatible match over an unverified newer release.
    return [max(values,key=lambda c:(c['match']['status']=='match',version(c))) for values in groups.values()]


def summary(card,all_cards):
    keys=('package_id','version','kind','identity','mini_app_id','name','agent_support','runtime_verified','tags','publisher')
    out={k:card[k] for k in keys if k in card}
    out.update(candidate_id=candidate_id(card),description=card.get('description','')[:200],
        match_status=card['match']['status'],matched_queries=card.get('matched_queries',[]),
        history_count=sum((v['package_id'],v.get('identity'))==(card['package_id'],card.get('identity')) for v in all_cards)-1)
    return out


def exclusions(cards):
    counts={}
    for c in cards:
        for reason in c['match'].get('exclusions',[]):
            code=reason.get('code','unknown');counts[code]=counts.get(code,0)+1
    return counts
