"""Chat-owned direct model turns on the existing durable Run scheduler.

No Tool discovery or General Agent prompt participates in this executor.
HTTP connections observe a Run; they never own its lifetime.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from ai2apps.agents.models import CompleteAction, FailAction, ModelCallAction, AgentRunStatus
from ai2apps.core import ResourceConflictError, ResourceNotFoundError, RevisionConflictError, new_entity_id, EntityIdKind, utc_now_text

KEY = 'ai2apps.direct-chat'
EXECUTOR = 'builtin:direct-chat'
TERMINAL = {'completed', 'failed', 'cancelled', 'interrupted'}
# Only model parameters, never Tools, identity, endpoints or callbacks.
OPTIONS = {'model', 'messages', 'temperature', 'top_p', 'top_k', 'min_p', 'max_tokens',
           'max_completion_tokens', 'presence_penalty', 'frequency_penalty', 'repetition_penalty',
           'seed', 'stop', 'reasoning_effort', 'chat_template_kwargs',
           'thinking_budget', 'ai2apps_engine_boost', 'ai2apps_l1_mode', 'ai2apps_kv_policy',
           'ai2apps_fusion_gate_policy', 'ai2apps_fusion_mid_generation_review',
           'ai2apps_fusion_thinking_audit', 'ai2apps_fusion_reviewer_guidance',
           'ai2apps_fusion_checkpoint_tokens', 'ai2apps_fusion_generator_l1_mode',
           'ai2apps_fusion_generator_engine_boost', 'ai2apps_fusion_reviewer_l1_mode',
           'ai2apps_fusion_reviewer_engine_boost'}


def install(runtime):
    runtime.agents.ensure_definition(agent_key=KEY, package_version='1.0.0',
        display_name='Chat', description='Durable direct model reply without Tools.',
        executor_key=EXECUTOR, max_steps=4, timeout_seconds=7200,
        manifest={'builtin': True, 'discoverable': False, 'allowed_tools': []})
    runtime.agent_runtime.bind_executor(EXECUTOR, DirectChatExecutor(runtime))


def runs(runtime, thread_id):
    definition = runtime.agents.get_definition(KEY)
    return runtime.agents.list_runs(session_id=thread_id, agent_definition_id=definition.id, limit=100)


def submit(runtime, repository, thread_id, *, request_id, expected_revision, request,
           anchor_message_id=None, presentation=None):
    repository.get_thread(thread_id)  # Actor AND client-scope ownership.
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
        raise ValueError('A stable Chat request_id is required')
    validate_request(request)
    presentation = presentation or {}
    if not isinstance(presentation, dict) or set(presentation) - {'modelId','modelDisplay','profileName','systemPrompt','generation','capturedAt','knowledge'} or len(json.dumps(presentation).encode()) > 32768:
        raise ValueError('Invalid Chat presentation metadata')
    payload = {'request': request, 'expected_revision': expected_revision, 'request_id': request_id,
               'anchor_message_id': anchor_message_id, 'presentation': presentation}
    key = 'chat-turn:' + request_id
    with runtime.database.transaction(write=True) as db:
        existing = db.execute('SELECT * FROM agent_runs WHERE session_id=? AND idempotency_key=?',
                              (thread_id, key)).fetchone()
        if not existing:
            row = db.execute('SELECT revision,status FROM sessions WHERE id=?', (thread_id,)).fetchone()
            if row['status'] != 'active':
                raise ResourceConflictError('Chat thread is not active')
            if row['revision'] != expected_revision:
                raise RevisionConflictError(thread_id, expected_revision, row['revision'])
            if db.execute("SELECT 1 FROM agent_runs WHERE session_id=? AND status NOT IN ('completed','failed','cancelled','interrupted')", (thread_id,)).fetchone():
                raise ResourceConflictError('A reply is already running in this Chat thread')
            anchor = db.execute("SELECT id FROM messages WHERE session_id=? AND role='user' AND (? IS NULL OR id=? OR json_extract(metadata_json,'$.id')=?) ORDER BY sequence DESC LIMIT 1",
                (thread_id,anchor_message_id,anchor_message_id,anchor_message_id)).fetchone()
            if anchor is None:
                raise ResourceConflictError('The user message must be saved before generating its reply')
            payload['_anchor_id'] = anchor['id']
        else:
            payload['_anchor_id'] = json.loads(existing['input_json']).get('_anchor_id')
        run, _ = runtime.agents.create_run(session_id=thread_id, agent_key=KEY, input=payload,
                                           idempotency_key=key, connection=db)
    runtime.agent_runtime.wake()
    return run


def validate_request(request):
    if not isinstance(request, dict) or set(request) - OPTIONS:
        raise ValueError('Unsupported direct Chat model parameters')
    if not isinstance(request.get('model'), str) or not request['model'].strip():
        raise ValueError('Chat model is required')
    messages = request.get('messages')
    if not isinstance(messages, list) or not messages or len(messages) > 10000:
        raise ValueError('Chat messages are required')
    if any(not isinstance(m, dict) or m.get('role') not in {'system', 'developer', 'user', 'assistant'}
           or set(m) - {'role', 'content', 'name'} for m in messages):
        raise ValueError('Direct Chat cannot invoke Tools')
    if len(json.dumps(request, ensure_ascii=False).encode()) > 32 * 1024 * 1024:
        raise ValueError('Chat request is too large')


def snapshot(runtime, run):
    line = runtime.agents.get_status_line(run.id)
    return {'id': run.id, 'session_id': run.session_id, 'status': run.status.value,
            'revision': run.revision, 'request_id': run.input['request_id'],
            'model': run.input['request']['model'], 'output': run.output, 'error': run.error,
            'created_at': run.created_at.isoformat(), 'updated_at': run.updated_at.isoformat(),
            'status_line': None if line is None else {'text': line.text, 'phase': line.phase,
                'revision': line.revision, 'content': line.content}}


def get(runtime, repository, thread_id, run_id):
    repository.get_thread(thread_id)
    run = runtime.agents.get_run(run_id)
    if run.session_id != thread_id or run.agent_definition_id != runtime.agents.get_definition(KEY).id:
        raise ResourceNotFoundError('chat_turn', run_id)
    return run


class DirectChatExecutor:
    def __init__(self, runtime):
        self.runtime = runtime

    def __call__(self, context):
        try:
            validate_request(context.run.input.get('request'))
        except ValueError as error:
            return FailAction('invalid_chat_request', str(error))
        step = next((s for s in context.steps if s.kind == 'model' and s.status.value == 'completed'), None)
        if step is None:
            return ModelCallAction('reply', {**context.run.input['request'], 'stream': False,
                'ai2apps_idempotency_key': 'chat-turn:' + context.run.id})
        result = step.output or {}
        choices = result.get('choices') or []
        choice = choices[0] if choices else {}
        message = choice.get('message') or {}
        if choice.get('finish_reason') is None:
            return FailAction('incomplete_chat_reply', 'The model response ended without a completion marker')
        if message.get('tool_calls'):
            return FailAction('unexpected_tool_call', 'Direct Chat does not execute Tools')
        content = message.get('content') or message.get('refusal') or ''
        if not content or (isinstance(content, str) and not content.strip()):
            return FailAction('empty_chat_reply', 'The model returned no answer')
        # Commit the answer and revision together. A stale UI snapshot can never
        # overwrite this append after reconnecting. Replaying finalization is safe.
        run = context.run
        with self.runtime.database.transaction(write=True) as db:
            state = db.execute('SELECT status,cancel_requested FROM agent_runs WHERE id=?', (run.id,)).fetchone()
            session = db.execute('SELECT status,app_instance_id FROM sessions WHERE id=?', (run.session_id,)).fetchone()
            if state['cancel_requested'] or state['status'] == 'cancelled' or session['status'] != 'active':
                return FailAction('chat_turn_cancelled', 'Chat reply was cancelled')
            old = db.execute('SELECT id FROM messages WHERE session_id=? AND idempotency_key=?',
                             (run.session_id, 'chat-turn:' + run.id + ':assistant')).fetchone()
            mid = old['id'] if old else new_entity_id(EntityIdKind.MESSAGE)
            usage = result.get('usage') or {}
            elapsed = max(0, (datetime.now(timezone.utc) - run.created_at).total_seconds())
            metrics = result.get('ai2apps_metrics') or {}
            recent_stats = {'avg_prefill_tps': usage.get('prompt_tokens_per_second') or 0,
                'avg_generation_tps': usage.get('generation_tokens_per_second') or 0,
                'prompt_tokens': usage.get('prompt_tokens') or 0, 'total_tokens': usage.get('completion_tokens') or 0,
                'thinking_tokens': (usage.get('completion_tokens_details') or {}).get('reasoning_tokens') or 0,
                'total_time': elapsed, 'thinking_time': metrics.get('thinking_time') or 0}
            output = {'message_id': mid, 'content': content, 'reasoning_content': message.get('reasoning_content', ''),
                      'finish_reason': choice.get('finish_reason'), 'usage': result.get('usage'),
                      'model': run.input['request']['model'], 'ai2apps_cloud': result.get('ai2apps_cloud', [])}
            if old is None:
                now = utc_now_text()
                metadata = {'id': mid, 'chat_turn_id': run.id, 'execution_mode': 'chat',
                            'model': output['model'], '_thinking': output['reasoning_content'],
                            'reasoning_content': output['reasoning_content'],
                            '_recentStats': recent_stats,
                            'meta': {**run.input.get('presentation', {}), 'usage': output['usage'],
                                     'finish_reason': output['finish_reason'], 'ai2apps_cloud': output['ai2apps_cloud']}}
                anchor = db.execute("SELECT id,sequence,metadata_json FROM messages WHERE session_id=? AND id=? AND role='user'", (run.session_id,run.input.get('_anchor_id'))).fetchone()
                if anchor is None:
                    return FailAction('chat_input_missing', 'The original user message no longer exists')
                boundary = db.execute("SELECT MIN(sequence) FROM messages WHERE session_id=? AND role='user' AND sequence>?", (run.session_id,anchor['sequence'])).fetchone()[0]
                seq = boundary or db.execute('SELECT COALESCE(MAX(sequence),0)+1 FROM messages WHERE session_id=?', (run.session_id,)).fetchone()[0]
                if boundary is not None:
                    shift = db.execute('SELECT MAX(sequence)+1 FROM messages WHERE session_id=?', (run.session_id,)).fetchone()[0]
                    db.execute('UPDATE messages SET sequence=sequence+? WHERE session_id=? AND sequence>=?', (shift,run.session_id,seq))
                    db.execute('UPDATE messages SET sequence=sequence-?+1 WHERE session_id=? AND sequence>=?', (shift,run.session_id,seq+shift))
                anchor_meta = json.loads(anchor['metadata_json'])
                anchor_meta['_activeVariantId'] = mid
                db.execute('UPDATE messages SET metadata_json=? WHERE id=?', (json.dumps(anchor_meta),anchor['id']))
                db.execute("INSERT INTO messages(id,session_id,sequence,role,status,idempotency_key,metadata_json,created_at,updated_at) VALUES (?,?,?,'assistant','completed',?,?,?,?)",
                    (mid, run.session_id, seq, 'chat-turn:' + run.id + ':assistant', json.dumps(metadata), now, now))
                db.execute("INSERT INTO message_parts(id,message_id,position,kind,content_json,created_at) VALUES (?,?,0,'chat_ui_content',?,?)",
                    (new_entity_id(EntityIdKind.MESSAGE_PART), mid, json.dumps({'content': content}), now))
                db.execute('UPDATE sessions SET revision=revision+1,updated_at=? WHERE id=?', (now, run.session_id))
                db.execute('UPDATE chat_thread_entries SET updated_at=? WHERE session_id=?', (now, run.session_id))
                self.runtime.events.append_in_transaction(db, event_type='chat.turn.reply_saved', subject_id=run.id,
                    app_instance_id=session['app_instance_id'], session_id=run.session_id,
                    payload={'message_id': mid})
            self.runtime.agents.transition(run.id, expected={AgentRunStatus.RUNNING},
                status=AgentRunStatus.COMPLETED, output=output, connection=db)
        return CompleteAction(output)
