"""Generic WebAgent verification policy; declarations impose monotonic floors.

Only trusted source/Task metadata is consumed, never page content or Tool output.
"""
from __future__ import annotations
import math

REVIEW_LEVELS = ('off', 'on_recovery', 'always')
DEFAULT = {'visual_locating': True, 'visual_review': 'on_recovery',
           'allow_visual_state_confirmation': False, 'readback': True,
           'allow_user_intervention': True, 'timeout_seconds': None,
           'recovery_timeout_seconds': None, 'max_recovery_attempts': None}
CAPS = ('timeout_seconds','recovery_timeout_seconds','max_recovery_attempts')

def tighter(left, right):
    return right if left is None else left if right is None else min(left,right)


def validate_policy(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT):
        raise ValueError('Invalid execution_policy fields')
    for key, item in value.items():
        if key in CAPS:
            if item is not None and (isinstance(item,bool) or not isinstance(item,(int,float)) or not math.isfinite(item) or item<0
                    or (key=='timeout_seconds' and item==0) or (key=='max_recovery_attempts' and type(item) is not int)):
                raise ValueError('Invalid '+key)
        elif key == 'visual_review':
            if item not in REVIEW_LEVELS:
                raise ValueError('Invalid visual_review')
        elif type(item) is not bool or (key == 'readback' and not item):
            raise ValueError('Readback is mandatory; policy flags must be booleans')
    return dict(value)


def resolve_policy(requested=None, minimum=None):
    result = {**DEFAULT, **validate_policy({} if requested is None else requested)}
    floor = validate_policy({} if minimum is None else minimum)
    for key, value in floor.items():
        if key in CAPS:
            result[key] = tighter(result.get(key),value)
        elif key=='allow_user_intervention':
            result[key] = result[key] and value
        elif key == 'visual_review':
            result[key] = REVIEW_LEVELS[max(REVIEW_LEVELS.index(result[key]), REVIEW_LEVELS.index(value))]
        else:
            result[key] = result[key] or value
    return result


def inherit_policy(parent, child, minimum=None):
    """Nested capabilities cannot lower their own or their caller's floor."""
    result=resolve_policy(child, parent)
    parent=resolve_policy(parent)
    # Explicitly disabled vision is a caller constraint, never permission for a
    # nested capability to turn it back on. Mandatory owner checks cannot waive it.
    floor=validate_policy(minimum or {})
    if not parent['visual_locating']:
        if floor.get('visual_locating'):raise ValueError('Nested owner requires disabled visual locating')
        result['visual_locating']=False
    if parent['visual_review']=='off':
        if floor.get('visual_review','off')!='off':raise ValueError('Nested owner requires disabled visual review')
        result['visual_review']='off'
    return result


def readback_verdict(value):
    """Explicit owner contradiction wins; only unknown may use visual evidence."""
    if isinstance(value, dict) and type(value.get('verified')) is bool:
        return value['verified']
    return None


def verified_state(value, visual, policy):
    verdict = readback_verdict(value)
    return verdict if verdict is not None else bool(policy['allow_visual_state_confirmation'] and visual)


def combine_minimum(left=None, right=None):
    result=validate_policy(left or {})
    for key,value in validate_policy(right or {}).items():
        if key in CAPS:
            result[key]=tighter(result.get(key),value)
        elif key=='allow_user_intervention':
            result[key]=result.get(key,True) and value
        elif key=='visual_review':
            result[key]=REVIEW_LEVELS[max(REVIEW_LEVELS.index(result.get(key,'off')), REVIEW_LEVELS.index(value))]
        else:result[key]=result.get(key,False) or value
    return result
