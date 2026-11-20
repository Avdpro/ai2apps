"""Messager-owned, time-bounded attribution; missing prices are never zero."""
import json
from collections import Counter
from datetime import UTC,datetime,timedelta
from decimal import Decimal,InvalidOperation
from types import SimpleNamespace
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from ai2apps.agents.run_metrics import observed_metrics
from .task_usage import task_usage


def time_window(period,timezone_name,now=None):
    if period not in ('all','today','7d','30d'):raise ValueError('Unknown statistics period')
    try:zone=ZoneInfo(timezone_name)
    except (ValueError,ZoneInfoNotFoundError):raise ValueError('Unknown statistics timezone') from None
    end=(now or datetime.now(UTC)).astimezone(zone)
    start=None if period=='all' else end.replace(hour=0,minute=0,second=0,microsecond=0) if period=='today' else end-timedelta(days=7 if period=='7d' else 30)
    return start,end


def statistics(runtime,actor,bot_id,*,period='all',timezone_name='UTC',task_session_id=None,todo_task_id=None,now=None):
    if task_session_id and todo_task_id:raise ValueError('Choose one task identity')
    runtime.messager_bots.scope(actor,{'bot_id':bot_id})
    start,end=time_window(period,timezone_name,now)
    task_ids=None;run_ids=None
    if task_session_id:
        runtime.messager_dialogue.sessions.get(actor,bot_id,task_session_id)
        with runtime.database.transaction() as db:
            jobs=db.execute('SELECT j.task_id,j.worker_run,j.source_run FROM messager_dialogue_jobs j JOIN messager_job_sessions m ON m.job_id=j.id WHERE m.session_id=? AND j.actor=? AND j.bot_id=?',(task_session_id,actor,bot_id)).fetchall()
        task_ids={r['task_id'] for r in jobs if r['task_id']};run_ids={r[k] for r in jobs for k in ('source_run','worker_run') if r[k]}
    todo_rows=[]
    if runtime.todo:
        with runtime.todo.store.connect() as db:
            owned={r[0] for r in db.execute('SELECT task_id FROM task_execution_lanes WHERE owner=? AND lane=?',(actor,'messager-bot:'+bot_id))}
            if todo_task_id:
                if todo_task_id not in owned:raise PermissionError('Task unavailable')
                task_ids={todo_task_id};run_ids=set()
            for row in db.execute('SELECT r.* FROM runs r JOIN task_execution_lanes l ON l.owner=r.owner AND l.task_id=r.task_id WHERE l.owner=? AND l.lane=?',(actor,'messager-bot:'+bot_id)):
                if task_ids is None or row['task_id'] in task_ids:todo_rows.append(dict(row))
    elif todo_task_id:raise PermissionError('Task unavailable')
    for row in todo_rows:
        data=json.loads(row['data']);ref=data.get('agent_run_id')
        if ref and run_ids is not None:run_ids.add(ref)
    # Linked Todo executions may use another owner registration. Their exact Run
    # IDs come only from this actor's Bot execution lane, never from query input.
    extra={json.loads(r['data']).get('agent_run_id') for r in todo_rows}-{None}
    def in_window(stamp):
        if not stamp:return start is None
        moment=datetime.fromisoformat(stamp.replace('Z','+00:00'))
        if moment.tzinfo is None:moment=moment.replace(tzinfo=UTC)
        return (start is None or moment>=start) and moment<=end
    with runtime.database.transaction() as db:
        rows=db.execute('''SELECT s.id,s.kind,s.output_json,s.error_json,s.started_at,s.finished_at,r.id AS run_id,r.created_at,c.owner,c.registration,c.scope_json
            FROM run_steps s JOIN agent_runs r ON r.id=s.run_id LEFT JOIN app_chat_sessions c ON c.session_id=r.session_id
            WHERE s.kind IN ('model','internal') AND ((c.owner=? AND c.registration=? AND json_extract(c.scope_json,'$.bot_id')=?) OR r.id IN (SELECT value FROM json_each(?)))
              AND (? IS NULL OR r.id IN (SELECT value FROM json_each(?)))
            ORDER BY s.rowid''',(actor,'ai2apps.messager.bots',bot_id,json.dumps(list(extra)),
                                  1 if run_ids is not None else None,json.dumps(list(run_ids or ())))).fetchall()
        breakdown=task_usage(db,actor,bot_id,run_ids,in_window) if run_ids is not None else None
    steps=[];currencies={};currency_requests=set();missing=0;failed_billed=0
    for row in rows:
        if not in_window(row['started_at'] or row['created_at']):continue
        output=json.loads(row['output_json'] or '{}')
        if not isinstance(output,dict):output={}
        # Failed format validation can still be billed. Preserve the Cloud's
        # explicit settled error receipt; never retry or infer a successful reply.
        error=json.loads(row['error_json'] or '{}');details=error.get('details',{}) if isinstance(error,dict) else {}
        if not output.get('usage') and isinstance(details,dict) and isinstance(details.get('usage'),dict):
            u=details['usage'];output={'usage':{'prompt_tokens':u.get('inputTokens'),'completion_tokens':u.get('outputTokens')},'ai2apps_cloud':details}
            failed_billed+=bool(details.get('requestId') and details.get('points'))
        usage=output.get('usage');usage=usage if isinstance(usage,dict) else {}
        if row['kind']=='model' and not (any(type(usage.get(k)) is int and usage[k]>=0 for k in ('prompt_tokens','input_tokens')) and any(type(usage.get(k)) is int and usage[k]>=0 for k in ('completion_tokens','output_tokens'))):missing+=1
        steps.append(SimpleNamespace(id=row['id'],kind=row['kind'],output=output,started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,finished_at=datetime.fromisoformat(row['finished_at']) if row['finished_at'] else None))
        cost=usage.get('providerCurrencyCost')
        if isinstance(cost,dict) and isinstance(cost.get('currency'),str):
            try:amount=Decimal(str(cost['amount']))
            except (InvalidOperation,KeyError):continue
            if amount.is_finite() and amount>=0:
                key=output.get('id') or row['id']
                if key not in currency_requests:
                    currency_requests.add(key);unit=cost['currency'][:12];currencies[unit]=currencies.get(unit,Decimal(0))+amount
    metrics=observed_metrics(steps);counts=Counter();seen_tasks=set()
    for row in todo_rows:
        data=json.loads(row['data'])
        if in_window(data.get('started_at') or data.get('queued_at') or data.get('created_at')):counts[row['status']]+=1;seen_tasks.add(row['task_id'])
    return {'period':period,'timezone':timezone_name,'start':start.isoformat() if start else None,'end':end.isoformat(),'task_session_id':task_session_id,'todo_task_id':todo_task_id,
        **({'task_usage':breakdown} if breakdown is not None else {}),
        'tasks':len(seen_tasks),'executions':sum(counts.values()),'completed':counts['completed'],'active':sum(counts[k] for k in ('queued','running','planning','waiting_input','waiting_capability')),'failed':sum(counts[k] for k in ('failed','interrupted','timed_out')),'cancelled':counts['cancelled'],
        'usage':{**{k:metrics[k] for k in ('calls','input_tokens','output_tokens','known_charged_points','settled_requests')},'unreported_model_calls':missing,'failed_billed_calls':failed_billed,'currency_costs':{k:str(v) for k,v in currencies.items()},'scope':'Own recorded model/review calls including billed failures; excludes other Bots and unreported tool charges.'}}
