"""Internal P0 ingress for explicitly grouped, committed multimodal input.

This owner adapter admits ordinary Bot turns only. It neither interprets task
intent nor answers approvals. Media, controller leases and public routes are
deliberately outside this first slice; callers must not expose it as a gateway.
"""
import json
from uuid import uuid4

from ai2apps.storage.records import canonical_json


class RealtimeInputs:
    MAX_INPUTS = 16
    MAX_ATTACHMENTS = 8
    MAX_TEXT = 16000

    def __init__(self, dialogue):
        self.dialogue = dialogue
        self.runtime = dialogue.runtime
        self.db = dialogue.db
        self.lock = self.runtime.app_chat.lock
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_realtime_groups(
                id TEXT PRIMARY KEY, actor TEXT NOT NULL, installation TEXT NOT NULL,
                client_scope TEXT NOT NULL, bot_id TEXT NOT NULL, session_id TEXT NOT NULL,
                create_key TEXT NOT NULL, config_json TEXT NOT NULL,
                state TEXT NOT NULL, revision INTEGER NOT NULL, frozen_json TEXT,
                run_id TEXT, UNIQUE(installation,client_scope,session_id,create_key))''')
            db.execute('''CREATE TABLE IF NOT EXISTS messager_realtime_inputs(
                group_id TEXT NOT NULL,input_id TEXT NOT NULL,ordinal INTEGER NOT NULL,
                value_json TEXT NOT NULL,PRIMARY KEY(group_id,input_id))''')

    @staticmethod
    def _key(value):
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ValueError('A nonempty identifier of at most 200 characters is required')
        return value

    def _scope(self, principal, bot_id, sid):
        binding = self.runtime.app_chat.access(principal, sid)
        if binding['registration'] != 'ai2apps.messager.bots' or binding['scope'] != {'bot_id': bot_id}:
            raise PermissionError('Main Bot conversation required')
        if self.dialogue.directory.definition(principal.actor_user_id, bot_id)['execution_mode'] != 'agent':
            raise PermissionError('Realtime P0 ingress requires an Agent Bot')

    def _get(self, principal, group_id):
        with self.db.transaction() as db:
            row = db.execute('SELECT * FROM messager_realtime_groups WHERE id=?', (group_id,)).fetchone()
        if row is None or (row['actor'], row['installation'], row['client_scope']) != (
            principal.actor_user_id, principal.installation_id, principal.client_scope
        ):
            raise PermissionError('Input group unavailable')
        row = dict(row)
        self._scope(principal, row['bot_id'], row['session_id'])
        return row

    def create(self, principal, bot_id, sid, request_id, *, model, task_session_id=None,
               language='zh', client_timezone=None):
        """An explicit UI action owns the group; model output cannot create one."""
        self._key(request_id)
        self._key(model)
        if not isinstance(language, str) or len(language) > 32:
            raise ValueError('Invalid language')
        if client_timezone is not None and (not isinstance(client_timezone, str) or len(client_timezone) > 100):
            raise ValueError('Invalid timezone')
        config = canonical_json(dict(model=model, task_session_id=task_session_id,
                                     language=language, client_timezone=client_timezone))
        with self.lock:
            self._scope(principal, bot_id, sid)
            if task_session_id:
                self.dialogue.sessions.get(principal.actor_user_id, bot_id, task_session_id, sid)
            with self.db.transaction(write=True) as db:
                old = db.execute('''SELECT * FROM messager_realtime_groups WHERE
                    installation=? AND client_scope=? AND session_id=? AND create_key=?''',
                    (principal.installation_id, principal.client_scope, sid, request_id)).fetchone()
                if old:
                    if old['actor'] != principal.actor_user_id or old['config_json'] != config or old['bot_id'] != bot_id:
                        raise ValueError('Create key belongs to different input')
                    return old['id']
                ref = 'rtg_' + uuid4().hex
                db.execute('INSERT INTO messager_realtime_groups VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                           (ref, principal.actor_user_id, principal.installation_id, principal.client_scope,
                            bot_id, sid, request_id, config, 'open', 0, None, None))
                return ref

    def add(self, principal, group_id, input_id, *, source, text='', attachment_ids=(), final=True):
        """Only final speech is durable; partial captions stay in the adapter."""
        self._key(input_id)
        if source not in ('speech', 'text', 'attachment') or final is not True:
            raise ValueError('Only committed speech, text or attachment input is accepted')
        if not isinstance(text, str) or len(text) > self.MAX_TEXT:
            raise ValueError('Input text exceeds the group limit')
        if not isinstance(attachment_ids, (list, tuple)) or len(attachment_ids) > self.MAX_ATTACHMENTS:
            raise ValueError('Too many attachments')
        for ref in attachment_ids:
            self._key(ref)
        if not text.strip() and not attachment_ids:
            raise ValueError('Empty input')
        value = canonical_json(dict(source=source, text=text, attachment_ids=list(dict.fromkeys(attachment_ids))))
        with self.lock:
            row = self._get(principal, group_id)
            with self.db.transaction(write=True) as db:
                old = db.execute('SELECT value_json FROM messager_realtime_inputs WHERE group_id=? AND input_id=?',
                                 (group_id, input_id)).fetchone()
                if old:
                    if old[0] != value:
                        raise ValueError('Input ID belongs to different content')
                    return row['revision']
                if row['state'] != 'open':
                    raise ValueError('Input group is closed')
                values = [json.loads(r[0]) for r in db.execute(
                    'SELECT value_json FROM messager_realtime_inputs WHERE group_id=? ORDER BY ordinal', (group_id,))]
                if len(values) >= self.MAX_INPUTS or sum(len(v['text']) for v in values) + len(text) > self.MAX_TEXT:
                    raise ValueError('Input group limit exceeded')
                refs = set(attachment_ids).union(*(set(v['attachment_ids']) for v in values))
                if len(refs) > self.MAX_ATTACHMENTS:
                    raise ValueError('Too many group attachments')
                # Authorization is checked before storing any attachment reference.
                for ref in refs:
                    self.runtime.documents.get(row['session_id'], ref)
                revision = row['revision'] + 1
                db.execute('INSERT INTO messager_realtime_inputs VALUES(?,?,?,?)',
                           (group_id, input_id, revision, value))
                db.execute('UPDATE messager_realtime_groups SET revision=? WHERE id=?', (revision, group_id))
                return revision

    def close(self, principal, group_id, expected_revision):
        """Freeze membership and file identity without automatically dispatching."""
        with self.lock:
            row = self._get(principal, group_id)
            if row['revision'] != expected_revision:
                raise ValueError('Input group revision changed')
            if row['state'] != 'open':
                return
            with self.db.transaction() as db:
                parts = [json.loads(r[0]) for r in db.execute(
                    'SELECT value_json FROM messager_realtime_inputs WHERE group_id=? ORDER BY ordinal', (group_id,))]
            if not parts:
                raise ValueError('Empty input group')
            refs = list(dict.fromkeys(ref for p in parts for ref in p['attachment_ids']))
            identities = {}
            for ref in refs:
                item = self.runtime.documents.get(row['session_id'], ref)
                identities[ref] = [item.sha256, item.media_type, item.size_bytes]
            frozen = canonical_json(dict(text='\n'.join(p['text'] for p in parts if p['text']),
                                         attachments=refs, identities=identities))
            with self.db.transaction(write=True) as db:
                db.execute("UPDATE messager_realtime_groups SET state='pending',frozen_json=? WHERE id=?",
                           (frozen, group_id))

    def dispatch(self, principal, group_id):
        """Replay the original admission key after a crash, never a new task key.

        BotDialogue owns durable deduplication. No database transaction spans its
        admission and this adapter's receipt: that crash window is intentional.
        """
        with self.lock:
            row = self._get(principal, group_id)
            if row['state'] == 'open':
                raise ValueError('Close the input group before admission')
            if row['run_id']:
                return {'state': 'accepted', 'dialogue_run_id': row['run_id']}
            config = json.loads(row['config_json'])
            frozen = json.loads(row['frozen_json'])
            request_id = 'realtime-group:' + group_id
            # A prior admission takes precedence over later attachment deletion or
            # parse failure. Ask the owner to validate the unchanged signature.
            with self.db.transaction() as db:
                admitted = db.execute('SELECT run_id FROM messager_dialogue_turns WHERE session_id=? AND request_id=?',
                                      (row['session_id'], request_id)).fetchone()
            if not admitted:
                pending, failed = [], []
                for ref in frozen['attachments']:
                    item = self.runtime.documents.get(row['session_id'], ref)
                    if [item.sha256, item.media_type, item.size_bytes] != frozen['identities'][ref]:
                        raise ValueError('Frozen attachment content changed')
                    if item.status == 'failed':
                        failed.append(ref)
                    elif item.status != 'ready':
                        pending.append(ref)
                if failed or pending:
                    return {'state': 'attachment_failed' if failed else 'waiting_attachments',
                            'attachment_ids': failed or pending}
            run_id = self.dialogue.submit(principal, row['bot_id'], row['session_id'], request_id,
                                          frozen['text'], config['model'], frozen['attachments'],
                                          config['task_session_id'], config['language'],
                                          client_timezone=config['client_timezone'])
            self._save_receipt(group_id, run_id)
            return {'state': 'accepted', 'dialogue_run_id': run_id}

    def _save_receipt(self, group_id, run_id):
        with self.db.transaction(write=True) as db:
            db.execute("UPDATE messager_realtime_groups SET state='accepted',run_id=? WHERE id=?", (run_id, group_id))
