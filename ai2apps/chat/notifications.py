"""Chat-owned bridge from committed replies to the existing notification outbox.

No frontend, model content, or tool result can supply a recipient or destination.
The producer reconciles persisted completions after restart; the decision and
outbox insertion commit together. Historical replies are deliberately excluded.
"""
from datetime import datetime, timedelta, timezone
import logging
from ai2apps.core import utc_now_text

APP = 'ai2apps.general-chat'
ENABLED = 'chat.notifications.enabled'
QUEUED = 'chat.reply.notification_queued'
INPUT_QUEUED = 'chat.interaction.notification_queued'


def install(runtime):
    with runtime.database.transaction(write=True) as db:
        if not db.execute('SELECT 1 FROM events WHERE type=? LIMIT 1', (ENABLED,)).fetchone():
            runtime.events.append_in_transaction(db, event_type=ENABLED, subject_id=APP, payload={})
    runtime.remote.notifications.register_source(lambda: enqueue_completed_replies(runtime))
    runtime.remote.notifications.register_source(lambda: enqueue_pending_interactions(runtime))
    runtime.remote.notifications.register_delivery_guard(lambda body: interaction_still_pending(runtime, body))
    logging.getLogger(__name__).info('Chat reply and pending-interaction notification bridge loaded from %s', __file__)


def enqueue_completed_replies(runtime):
    producer = runtime.remote.notifications
    try:
        owner = producer.identity()['owner_id']
    except ValueError:
        return 0
    # No misleading legacy task link if this Cloud cannot resolve App routes.
    if not producer.supports_custom('app_route'):
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    count = 0
    with runtime.database.transaction(write=True) as db:
        rows = db.execute("""
            SELECT r.id, r.session_id, s.app_instance_id
            FROM agent_runs r JOIN sessions s ON s.id=r.session_id
            JOIN chat_thread_entries e ON e.session_id=s.id AND e.app_instance_id=s.app_instance_id
            JOIN app_instances i ON i.id=s.app_instance_id
            JOIN app_definitions a ON a.id=i.app_definition_id
            JOIN agent_definitions d ON d.id=r.agent_definition_id
            JOIN messages m ON m.id=json_extract(r.output_json,'$.message_id') AND m.session_id=s.id
            WHERE r.status='completed' AND r.parent_run_id IS NULL AND s.status='active'
              AND m.role='assistant' AND m.status='completed'
              AND ((json_type(r.output_json,'$.content')='text' AND length(trim(json_extract(r.output_json,'$.content')))>0)
                OR (json_type(r.output_json,'$.content')='array' AND json_array_length(r.output_json,'$.content')>0))
              AND i.owner_user_id=? AND a.package_id=? AND a.status='enabled'
              AND (d.agent_key='ai2apps.direct-chat' OR COALESCE(json_extract(d.manifest_json,'$.discoverable'),1)<>0)
              AND r.updated_at>=? AND r.updated_at>=(SELECT MIN(occurred_at) FROM events WHERE type=?)
              AND NOT EXISTS(SELECT 1 FROM events n WHERE n.type=? AND n.subject_id=r.id)
            ORDER BY r.updated_at LIMIT 50
        """, (owner, APP, cutoff, ENABLED, QUEUED)).fetchall()
        for row in rows:
            event_id = 'chat.reply:' + row['id']
            producer.enqueue_custom(event_id=event_id,
                content={'title': 'Chat 回复已完成', 'body': '对话有一条新回复。打开 Chat 查看。', 'locale': 'zh-CN'},
                target={'type': 'app_route', 'app_id': APP, 'route': 'conversation', 'id': row['session_id']},
                group_key='chat:' + row['session_id'], metadata={'run_id': row['id']},
                expected_owner_id=owner, connection=db)
            runtime.events.append_in_transaction(db, event_type=QUEUED, subject_id=row['id'],
                session_id=row['session_id'], app_instance_id=row['app_instance_id'],
                payload={'event_id': event_id})
            count += 1
    return count


def authorize_conversation(runtime, principal, session_id):
    from .repository import ChatRepository
    thread = ChatRepository(runtime.database, runtime.events, principal=principal).get_thread(session_id)
    if thread.session.status.value != 'active':
        raise ValueError('Notification conversation is unavailable')
    return {'notification-route': 'conversation', 'notification-resource': session_id}


def _pending(db, interaction_id, owner=None):
    row = db.execute("""
        SELECT x.id,x.run_id,x.kind,r.session_id,s.app_instance_id,i.owner_user_id
        FROM agent_interactions x JOIN agent_runs r ON r.id=x.run_id
        JOIN sessions s ON s.id=r.session_id
        JOIN chat_thread_entries e ON e.session_id=s.id AND e.app_instance_id=s.app_instance_id
        JOIN app_instances i ON i.id=s.app_instance_id
        JOIN app_definitions a ON a.id=i.app_definition_id
        WHERE x.id=? AND x.status='pending' AND x.deadline_at>?
          AND r.status IN ('waiting_input','waiting_capability') AND r.cancel_requested=0 AND r.deadline_at>?
          AND s.status='active' AND a.status='enabled' AND a.package_id=?
          AND (? IS NULL OR i.owner_user_id=?)
    """, (interaction_id, utc_now_text(), utc_now_text(), APP, owner, owner)).fetchone()
    if row is None:
        return None
    # A child interaction is actionable only while its entire delegation is alive.
    stopped = db.execute("""WITH RECURSIVE lineage AS (
        SELECT id,parent_run_id,status,cancel_requested FROM agent_runs WHERE id=?
        UNION ALL SELECT p.id,p.parent_run_id,p.status,p.cancel_requested FROM agent_runs p JOIN lineage c ON p.id=c.parent_run_id
    ) SELECT 1 FROM lineage WHERE status IN ('completed','failed','cancelled','interrupted') OR cancel_requested<>0 LIMIT 1""", (row['run_id'],)).fetchone()
    return None if stopped else row


def enqueue_pending_interactions(runtime):
    producer = runtime.remote.notifications
    try:
        owner = producer.identity()['owner_id']
    except ValueError:
        return 0
    if not producer.supports_custom('app_route'):
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    count = 0
    with runtime.database.transaction(write=True) as db:
        candidates = db.execute("""SELECT x.id FROM agent_interactions x
            JOIN agent_runs r ON r.id=x.run_id JOIN sessions s ON s.id=r.session_id
            JOIN app_instances i ON i.id=s.app_instance_id
            JOIN chat_thread_entries e ON e.session_id=s.id AND e.app_instance_id=s.app_instance_id
            WHERE x.status='pending' AND x.created_at>=? AND i.owner_user_id=? AND x.deadline_at>?
              AND r.status IN ('waiting_input','waiting_capability') AND r.cancel_requested=0 AND r.deadline_at>?
              AND s.status='active'
              AND NOT EXISTS(SELECT 1 FROM events n WHERE n.type=? AND n.subject_id=x.id)
            ORDER BY x.created_at LIMIT 50""", (cutoff, owner, utc_now_text(), utc_now_text(), INPUT_QUEUED)).fetchall()
        for item in candidates:
            row = _pending(db, item['id'], owner)
            if row is None:
                continue
            event_id = 'chat.interaction:' + row['id']
            producer.enqueue_custom(event_id=event_id,
                content={'title': 'Chat 需要你确认' if row['kind']=='approval' else 'Chat 需要你填写信息',
                         'body': '对话正在等待你的操作。打开原对话查看并处理。', 'locale': 'zh-CN'},
                target={'type':'app_route','app_id':APP,'route':'interaction','id':row['id']},
                group_key='chat:' + row['session_id'], metadata={'run_id':row['run_id']},
                expected_owner_id=owner, connection=db)
            runtime.events.append_in_transaction(db, event_type=INPUT_QUEUED, subject_id=row['id'],
                session_id=row['session_id'], app_instance_id=row['app_instance_id'], payload={'event_id':event_id})
            count += 1
    return count


def interaction_still_pending(runtime, body):
    if not str(body.get('event_id','')).startswith('chat.interaction:'):
        return True
    destination = body.get('target') or {}
    owner = runtime.remote.notifications.identity()['owner_id']
    with runtime.database.transaction() as db:
        row = _pending(db, destination.get('id'), owner)
    return bool(row and body['event_id']=='chat.interaction:'+row['id']
        and destination=={'type':'app_route','app_id':APP,'route':'interaction','id':row['id']}
        and body.get('metadata',{}).get('run_id')==row['run_id'])


def authorize_interaction(runtime, principal, interaction_id):
    with runtime.database.transaction() as db:
        row = _pending(db, interaction_id, principal.actor_user_id)
    if row is None:
        raise ValueError('This interaction is no longer waiting for input')
    authorize_conversation(runtime, principal, row['session_id'])
    return {'notification-route':'interaction','notification-resource':row['id'],
            'notification-session':row['session_id'],'notification-run':row['run_id']}
