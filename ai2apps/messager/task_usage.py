"""Read-only attribution of durable Bot Task usage, across delegated Runs."""
import json
from decimal import Decimal, InvalidOperation

# Platform bookkeeping does not perform billable work. Owner operations without
# receipts stay unknown: a tool's name or effect declaration is not a price.
_BOOKKEEPING = frozenset({
    'app.describe', 'capability.describe', 'app.collect_parameters', 'app.interact',
    'agent.ask_user', 'agent.current_time', 'agent.read_context_checkpoint',
    'agent.read_session_memory', 'agent.read_tool_result',
    'messager.bot.delegate', 'messager.bot.directory',
})
_BUCKETS = ('task', 'aaat', 'delegated')


def _object(value):
    return value if isinstance(value, dict) else {}


def _count(value, *keys):
    return next((value[k] for k in keys if type(value.get(k)) is int and value[k] >= 0), None)


def _points(value):
    if type(value) not in (str, int, float):
        return None
    try:
        raw = str(value)
        if len(raw) > 64:
            return None
        number = Decimal(raw)
        # Tool receipts are provider data. Keep pathological numeric exponents
        # from expanding into unbounded response strings.
        return number if number.is_finite() and number >= 0 and abs(number.as_tuple().exponent) <= 32 else None
    except InvalidOperation:
        return None


def _request_id(value):
    return value if isinstance(value, str) and 0 < len(value) <= 256 else None


def _receipt(payload, usage):
    points = _object(payload.get('points'))
    cloud_charge = payload.get('charged') if _request_id(payload.get('requestId')) else None
    charge = _points(points.get('charged', cloud_charge if cloud_charge is not None else usage.get('points_charged')))
    if payload.get('usageEstimated') is True:
        return None, None, None, charge
    prompt = _count(usage, 'prompt_tokens', 'input_tokens', 'inputTokens')
    completion = _count(usage, 'completion_tokens', 'output_tokens', 'outputTokens')
    # Cloud's camelCase text and image token fields are disjoint. OpenAI-style
    # totals and nested token details already include image/cached tokens.
    if prompt is not None and 'inputTokens' in usage:
        prompt += _count(usage, 'imageInputTokens') or 0
    if completion is not None and 'outputTokens' in usage:
        completion += _count(usage, 'imageOutputTokens') or 0
    return _count(usage, 'total_tokens', 'totalTokens'), prompt, completion, charge


def _merge(old, new):
    return tuple(left if left is not None else right for left, right in zip(old, new))


def _observations(output, error):
    # Only read accounting fields in the journaled result or structured error.
    # Text, artifact metadata, read-back results and nested business data are
    # not billing records.
    details = _object(error.get('details'))
    usage = _object(output.get('usage'))
    cloud = output.get('ai2apps_cloud')
    if isinstance(cloud, dict):
        cloud = [cloud]
    elif not isinstance(cloud, list):
        cloud = []
    keyed = {}
    for value in [*cloud, details]:
        value = _object(value)
        key = _request_id(value.get('requestId'))
        if key:
            receipt = _receipt(value, _object(value.get('usage')))
            # Later journal phases take precedence, with earlier observations
            # filling only missing fields.
            keyed[key] = _merge(receipt, keyed.get(key, (None,) * 4))
    key = _request_id(output.get('requestId')) or _request_id(usage.get('request_id'))
    primary = _receipt(output, usage)
    if key:
        keyed[key] = _merge(primary, keyed.get(key, (None,) * 4))
    elif len(keyed) == 1:
        only = next(iter(keyed))
        keyed[only] = _merge(primary, keyed[only])
    if keyed:
        return list(keyed.items())
    return [(None, primary)]


def _summary(observations):
    tokens = points = unknown_tokens = unknown_points = reported_tokens = reported_points = 0
    for total, prompt, completion, charged in observations:
        if total is not None:
            tokens += total
            reported_tokens += 1
        else:
            tokens += (prompt or 0) + (completion or 0)
            unknown_tokens += prompt is None or completion is None
            reported_tokens += prompt is not None or completion is not None
        if charged is None:
            unknown_points += 1
        else:
            points += charged
            reported_points += 1
    return {'tokens': None if unknown_tokens else tokens,
            'points': None if unknown_points else format(points, 'f'),
            'known_tokens': tokens if reported_tokens else None,
            'known_points': format(points, 'f') if reported_points else None,
            'unreported_tokens': unknown_tokens, 'unreported_points': unknown_points}


def delegated_runs(db, actor, bot_id, roots):
    frontier = {(run, bot_id) for run in roots}
    visited = set(frontier)
    descendants = set()
    while frontier:
        rows = db.execute("""
            WITH parents AS (
                SELECT json_extract(value,'$[0]') AS run, json_extract(value,'$[1]') AS bot
                FROM json_each(?)
            ), links AS (
                SELECT d.child_job,d.target_bot,COALESCE(m.session_id,d.child_job) AS logical_id
                FROM parents p JOIN messager_bot_delegations d ON d.source_run=p.run AND d.source_bot=p.bot
                LEFT JOIN messager_job_sessions m ON m.job_id=d.child_job
                WHERE d.actor=? AND d.child_job IS NOT NULL
            )
            SELECT j.bot_id,j.worker_run,j.source_run FROM links l
            JOIN messager_dialogue_jobs j ON j.actor=? AND j.bot_id=l.target_bot
            LEFT JOIN messager_job_sessions m ON m.job_id=j.id
            WHERE j.id=l.child_job OR m.session_id=l.logical_id
        """, (json.dumps(list(frontier)), actor, actor))
        found = {(row[k], row['bot_id']) for row in rows for k in ('worker_run', 'source_run') if row[k]}
        descendants.update(run for run, _ in found)
        frontier = found - visited
        visited.update(frontier)
    return descendants - roots


def task_usage(db, actor, bot_id, roots, in_window):
    descendants = delegated_runs(db, actor, bot_id, roots)
    all_runs = json.dumps(sorted(roots | descendants))
    journal = db.execute("""
        SELECT s.id,s.run_id,s.output_json,s.error_json,'model' AS source,
               COALESCE(s.started_at,r.created_at) AS stamp,NULL AS qualified_name
        FROM run_steps s JOIN agent_runs r ON r.id=s.run_id
        WHERE s.run_id IN (SELECT value FROM json_each(?))
          AND (s.kind='model' OR (s.kind='internal' AND
            (json_extract(s.input_json,'$.schema')='ai2apps.tool-approval-review/v1'
             OR json_type(s.output_json,'$.usage')='object')))
        UNION ALL
        SELECT t.id,t.trace_id,t.output_json,t.error_json,'tool',t.created_at,t.qualified_name
        FROM tool_invocations t JOIN agent_runs r ON r.id=t.trace_id AND r.session_id=t.session_id
        WHERE t.trace_id IN (SELECT value FROM json_each(?))
        ORDER BY 5,6,1
    """, (all_runs, all_runs))
    # Model steps precede tool receipts; ties follow journal time. Duplicate
    # receipts can fill gaps, but cannot move a charge to a second bucket.
    ledger = {}
    for row in journal:
        if row['qualified_name'] in _BOOKKEEPING or not in_window(row['stamp']):
            continue
        bucket = ('delegated' if row['run_id'] in descendants
                  else 'task' if row['source'] == 'model' else 'aaat')
        output, error = (_object(json.loads(row[k] or '{}')) for k in ('output_json', 'error_json'))
        for request, receipt in _observations(output, error):
            key = ('request', request) if request else (row['source'], row['id'])
            if key in ledger:
                attributed, previous = ledger[key]
                ledger[key] = attributed, _merge(previous, receipt)
            else:
                ledger[key] = bucket, receipt
    result = {bucket: _summary(value for owner, value in ledger.values() if owner == bucket)
              for bucket in _BUCKETS}
    result['total'] = _summary(value for _, value in ledger.values())
    return result
