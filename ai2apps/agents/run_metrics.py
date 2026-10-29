"""Observed model usage only. Missing cache/settlement never means zero."""
from decimal import Decimal, InvalidOperation


def observed_metrics(steps):
    rows=[];charges={}
    for step in steps:
        if step.kind not in ('model','internal') or not isinstance(step.output,dict):continue
        usage=step.output.get('usage')
        if not isinstance(usage,dict):continue
        def count(*keys):
            for key in keys:
                v=usage.get(key)
                if type(v) is int and v>=0:return v
            return None
        prompt=count('prompt_tokens','input_tokens');completion=count('completion_tokens','output_tokens')
        details=usage.get('prompt_tokens_details') or usage.get('input_tokens_details') or {}
        cached=details.get('cached_tokens',usage.get('prompt_cache_hit_tokens'))
        if type(cached) is not int or cached<0 or prompt is None or cached>prompt:cached=None
        cloud=step.output.get('ai2apps_cloud') or {}
        if isinstance(cloud,list):cloud=next((v for v in reversed(cloud) if isinstance(v,dict) and v.get('requestId')), {})
        if not isinstance(cloud,dict):cloud={}
        reported=usage.get('cacheUsageReported')
        cache_source=usage.get('cacheUsageSource','unknown')
        if reported is not True and cloud:
            cached=None  # historic normalized zeros have no upstream observation proof
        elif reported is False:
            cached=None
        if reported is None and not cloud and cached is not None:
            reported=True;cache_source='direct-provider-reported'
        request_id=cloud.get('requestId');points=cloud.get('points')
        charged=points.get('charged') if isinstance(points,dict) else cloud.get('charged')
        try:
            charge=Decimal(str(charged)) if charged is not None else None
            if charge is not None and (not charge.is_finite() or charge<0):charge=None
        except InvalidOperation:charge=None
        if request_id and charge is not None:charges[request_id]=charge
        elapsed=(step.finished_at-step.started_at).total_seconds() if step.finished_at and step.started_at else None
        rows.append({'step_id':step.id,'input_tokens':prompt,'cached_input_tokens':cached,
            'uncached_input_tokens':prompt-cached if prompt is not None and cached is not None else None,
            'cache_usage_reported':reported,'cache_usage_source':cache_source,
            'provider_currency_cost':None,
            'output_tokens':completion,'request_id':request_id,'charged_points':str(charge) if charge is not None else None,
            'elapsed_seconds':elapsed})
    all_cache=bool(rows) and all(v['cached_input_tokens'] is not None for v in rows)
    all_cost=bool(rows) and all(v['request_id'] in charges for v in rows)
    return {'scope':'recorded model/review steps; owner-internal model calls reported separately',
        'calls':len(rows),'input_tokens':sum(v['input_tokens'] or 0 for v in rows),
        'output_tokens':sum(v['output_tokens'] or 0 for v in rows),
        'cached_input_tokens':sum(v['cached_input_tokens'] or 0 for v in rows) if all_cache else None,
        'uncached_input_tokens':sum(v['uncached_input_tokens'] or 0 for v in rows) if all_cache else None,
        'cache_reported_calls':sum(v['cached_input_tokens'] is not None for v in rows),
        'charged_points':str(sum(charges.values(),Decimal(0))) if all_cost else None,
        'known_charged_points':str(sum(charges.values(),Decimal(0))) if charges else None,
        'cache_not_reported_calls':sum(v['cache_usage_reported'] is False for v in rows),
        'cache_unknown_calls':sum(v['cache_usage_reported'] is None for v in rows),
        'provider_currency_cost':None,
        'settled_requests':len(charges),'cost_unit':'AI2Apps Points','rows':rows}
