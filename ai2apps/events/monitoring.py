"""Owner-scoped operational projections. Observing never drives execution."""
from datetime import datetime,timezone
import json,time,logging
logging.getLogger(__name__).info("Hook monitoring loaded; source=%s",__file__)
from .hooks import HookError


def monitor(hooks,actor,*,limit=50):
    now=hooks.clock();dbase=hooks.db
    with dbase.transaction() as db:
        rules=[dict(r) for r in db.execute('''SELECT r.*,v.spec_json,v.cursor,v.start_sequence FROM hook_rules r
            JOIN hook_rule_revisions v ON v.rule_id=r.id AND v.revision=r.revision WHERE r.owner=? AND r.status!='deleted' ORDER BY r.created DESC LIMIT 100''',(actor,))]
        floor=db.execute('SELECT floor_sequence FROM business_event_retention WHERE id=1').fetchone()[0]
        rows=[dict(r) for r in db.execute('''SELECT d.*,r.owner,r.status AS rule_status,v.spec_json,e.state AS execution_state,
            e.task_id,e.error,e.result_json,e.created AS queued_at,e.started,e.updated,s.status AS task_status
            FROM hook_deliveries d JOIN hook_rules r ON r.id=d.rule_id
            JOIN hook_rule_revisions v ON v.rule_id=d.rule_id AND v.revision=d.rule_revision
            LEFT JOIN hook_executions e ON e.delivery_id=d.id LEFT JOIN system_tasks s ON s.id=e.task_id
            WHERE r.owner=? ORDER BY d.event_sequence DESC LIMIT ?''',(actor,limit))]
        counts={r[0]:r[1] for r in db.execute('''SELECT COALESCE(e.state,'matched'),count(*) FROM hook_deliveries d
            JOIN hook_rules r ON r.id=d.rule_id LEFT JOIN hook_executions e ON e.delivery_id=d.id WHERE r.owner=? GROUP BY COALESCE(e.state,'matched')''',(actor,))}
        step_counts={r[0]:r[1] for r in db.execute('''SELECT a.state,count(*) FROM hook_action_steps a JOIN hook_deliveries d ON d.id=a.delivery_id
            JOIN hook_rules r ON r.id=d.rule_id WHERE r.owner=? GROUP BY a.state''',(actor,))}
        oldest=db.execute("""SELECT min(d.created) FROM hook_deliveries d JOIN hook_rules r ON r.id=d.rule_id JOIN hook_rule_revisions v ON v.rule_id=d.rule_id AND v.revision=d.rule_revision LEFT JOIN hook_executions e ON e.delivery_id=d.id WHERE r.owner=? AND json_extract(v.spec_json,'$.mode')='background' AND (e.state IS NULL OR e.state IN ('admitting','queued','running','needs_user'))""",(actor,)).fetchone()[0]
        unread=db.execute('SELECT count(*) FROM hook_local_notices WHERE owner=? AND read_at IS NULL',(actor,)).fetchone()[0]
        for rule in rules:
            spec=json.loads(rule.pop('spec_json'));rule['consumer']=spec['consumer'];rule['event_type']=spec['event_type'];rule['event_title']=hooks.business.types.get(spec['event_type']).title if spec['event_type'] in hooks.business.types else '';rule['mode']=spec['mode']
            rule['expires_at']=spec.get('execution',{}).get('expires_at');rule['actions']=spec.get('execution',{}).get('actions',[])
            rule['quota']={'max_deliveries':hooks.MAX_MATCHES,'matched':db.execute('SELECT count(*) FROM hook_deliveries WHERE rule_id=?',(rule['id'],)).fetchone()[0]}
            rule['cursor_gap']=rule['cursor']<floor
            rule['scan_backlog']=db.execute('SELECT count(*) FROM business_event_facts WHERE owner=? AND type=? AND sequence>?',(actor,spec['event_type'],rule['cursor'])).fetchone()[0]
            rule['delegation']='expired' if rule['expires_at'] and rule['expires_at']<=now else 'expiring' if rule['expires_at'] and rule['expires_at']-now<3600 else 'valid'
    deliveries=[];latencies=[];ages=[]
    for row in rows:
        spec=json.loads(row.pop('spec_json'));row.pop('owner')
        result=json.loads(row.pop('result_json') or '{}')
        row['attention_reason']=str(result.get('reason') or '')[:120] if isinstance(result,dict) else ''
        state=row['execution_state'] or ('waiting' if spec['mode']=='background' else 'observed')
        if state in ('admitting','queued') and row['task_status'] in ('running','waiting_resource','waiting_user','cancelling'):state=row['task_status']
        row['state']=state;row['consumer']=spec['consumer'];row['event_type']=spec['event_type'];row['age_seconds']=max(0,now-row['created'])
        if state in ('waiting','admitting','queued','running','waiting_resource','waiting_user'):ages.append(row['age_seconds'])
        try:
            # No cached private body, evidence or result is part of a status list.
            hooks._validate(actor,spec);event=hooks.business.read(actor,row['event_id'])
            recorded=datetime.fromisoformat(event['recorded_at'].replace('Z','+00:00')).timestamp()
            row['match_latency_seconds']=max(0,row['created']-recorded);latencies.append(row['match_latency_seconds'])
            row['source_available']=True
        except (ValueError,PermissionError,KeyError):row['source_available']=False
        deliveries.append(row)
    return {'rules':rules,'deliveries':deliveries,'summary':{'rules':len(rules),'states':counts,'action_states':step_counts,
        'oldest_pending_seconds':max(0,now-oldest) if oldest is not None else 0,'sample_match_latency_max_seconds':max(latencies,default=0),
        'latency_sample_size':len(latencies),'unread_notices':unread,'rules_with_cursor_gap':sum(r['cursor_gap'] for r in rules),
        'expired_delegations':sum(r['delegation']=='expired' for r in rules),'rule_limit':hooks.MAX_RULES},'retention':{'floor_sequence':floor,'automatic_pruning':False},'observed_at':now}


def steps(hooks,actor,delivery):
    with hooks.db.transaction() as db:
        row=db.execute('SELECT r.owner FROM hook_deliveries d JOIN hook_rules r ON r.id=d.rule_id WHERE d.id=? AND r.owner=?',(delivery,actor)).fetchone()
        if not row:raise HookError('rule_not_found','Delivery unavailable')
        rows=[dict(r) for r in db.execute('SELECT * FROM hook_action_steps WHERE delivery_id=? ORDER BY step',(delivery,))]
    # Receipts expose created IDs, never source bodies or model prompts.
    for row in rows:row['result']=json.loads(row.pop('result_json') or 'null');row.pop('signature')
    return {'items':rows}


def notices(hooks,actor):
    with hooks.db.transaction() as db:
        rows=[dict(r) for r in db.execute('SELECT * FROM hook_local_notices WHERE owner=? ORDER BY created DESC LIMIT 100',(actor,))]
    for row in rows:
        content=json.loads(row.pop('content_json'));row.pop('operation_key')
        try:hooks.business.read(actor,content['event_id']);row['content']=content
        except (PermissionError,KeyError):row['content']={'title':'来源已不可用','body':''}
    return {'items':rows}


def read_notice(hooks,actor,nid):
    with hooks.db.transaction(write=True) as db:
        n=db.execute('UPDATE hook_local_notices SET read_at=COALESCE(read_at,?) WHERE owner=? AND id=?',(time.time(),actor,nid)).rowcount
    if not n:raise HookError('rule_not_found','Notice unavailable')
    return {'read':True}
