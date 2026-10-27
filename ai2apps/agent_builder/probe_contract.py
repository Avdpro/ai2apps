"""Probe evidence constrains generated control bindings, never grants authority."""
from __future__ import annotations
from collections import Counter
import re

CONTROL_OPERATIONS=frozenset({'click','delete','input','hover'})

def controls(probe):
    result=[]
    for item in (probe.get('items') or probe.get('controls') or []) or []:
        if isinstance(item,dict) and isinstance(item.get('ref'),str):
            result.append(item)
    return result[:600]

def coverage(probe):
    rows=controls(probe)
    return {'schema':'ai2apps.probe-controls/v1','count':len(rows),
            'tags':dict(Counter(str(row.get('tag','')).lower() for row in rows)),
            'custom_controls':sum(str(row.get('tag','')).lower() in ('div','span') for row in rows),
            'bounded':len(rows)>=600}

def validate_step(step,probe):
    """Validate only explicit observed refs; do not guess targets from labels."""
    if step.get('operation') not in CONTROL_OPERATIONS:return []
    target=step.get('target') or {}
    if isinstance(target,str):target={'intent':target}
    if not isinstance(target,dict):return [{'code':'probe_target_invalid','message':'Target must be a binding or intent.'}]
    hint=target.get('ref') or target.get('intent') or target.get('accessible_name') or ''
    refs={str(target['ref'])} if target.get('ref') else set(re.findall(r'\be\d+\b',str(hint)))
    if not refs:return []
    rows={row['ref']:row for row in controls(probe)}
    if len(refs)!=1 or not refs.issubset(rows):return [{'code':'probe_target_not_observed','message':'Generated target must be one interactive ref in the selected Probe, including DIV/SPAN controls.'}]
    item=rows[next(iter(refs))]
    if item.get('disabled') or item.get('sensitive'):return [{'code':'probe_target_unavailable','message':'Probe target is disabled or sensitive.'}]
    if step.get('operation')=='input' and not (item.get('editable') or item.get('tag') in ('input','textarea','select') or item.get('role')=='textbox' or item.get('type')=='file'):
        return [{'code':'probe_target_not_editable','message':'Input requires an observed editable control.'}]
    return []
