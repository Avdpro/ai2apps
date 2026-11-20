"""Bot-owned streaming speech configuration and leased ordinary-turn ingress.

Media uses the existing authenticated ASR/TTS endpoints. This owner never answers
approval interactions or interprets task commands; BotDialogue remains authority.
"""
import json
import time
import logging
from uuid import uuid4
from ai2apps.core import RepositoryError

from .voice import BotVoice


class BotRealtime:
    LEASE_SECONDS = 45
    MAX_SECONDS = 3600
    FIELDS = ('stt_model_id', 'tts_model_id', 'voice', 'profile_id')

    def __init__(self, dialogue):
        self.dialogue = dialogue
        self.runtime, self.db = dialogue.runtime, dialogue.db
        self.lock = self.runtime.app_chat.lock
        logging.getLogger(__name__).info('Bot realtime voice owner loaded from %s', __file__)
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_realtime_settings(
                bot_id TEXT PRIMARY KEY, actor TEXT NOT NULL, value_json TEXT NOT NULL,
                revision INTEGER NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS messager_voice_sessions(
                id TEXT PRIMARY KEY, actor TEXT NOT NULL, installation TEXT NOT NULL,
                client_scope TEXT NOT NULL, bot_id TEXT NOT NULL, session_id TEXT NOT NULL,
                controller TEXT NOT NULL, config_json TEXT NOT NULL, created REAL NOT NULL,
                expires REAL NOT NULL, closed INTEGER NOT NULL DEFAULT 0)''')
            db.execute('CREATE INDEX IF NOT EXISTS messager_voice_lease ON messager_voice_sessions(actor,installation,expires)')

    def _input(self, value):
        if not value.get('stt_model_id'):raise ValueError('Select a speech recognition model')
        stt = self.runtime.model_invocations.model(value.get('stt_model_id'))
        if not stt or stt.model_type != 'audio_stt' or not stt.checkpoint_ready or getattr(stt,'is_hidden',False):
            raise ValueError('Speech recognition model is not ready')

    def _speech(self, actor, value):
        if not value.get('tts_model_id'):
            if value.get('voice') or value.get('profile_id'):raise ValueError('Select a speech model for this voice')
            return False
        speech={'mode':'profile' if value.get('profile_id') else 'model',
            'model_id':None if value.get('profile_id') else value['tts_model_id'],
            'profile_id':value.get('profile_id'),'voice':value.get('voice')}
        BotVoice(self.dialogue.directory,self.runtime).validate(actor,speech)
        if value.get('profile_id'):
            from ai2apps.readaloud.repository import ReadAloudRepository
            profile=ReadAloudRepository(self.runtime.database,self.runtime.events).get_voice_profile(actor,value['profile_id'])
            if profile['model_id']!=value['tts_model_id']:raise ValueError('Voice character belongs to another model')
        return True

    def validate(self, actor, value, *, input_required=True):
        value={k:value.get(k) for k in self.FIELDS}
        if input_required or value['stt_model_id']:self._input(value)
        self._speech(actor,value)
        if not value['stt_model_id'] and not value['tts_model_id']:raise ValueError('Select at least one speech model')
        return value

    def get(self, actor, bot_id):
        self.dialogue.directory.scope(actor, {'bot_id': bot_id})
        with self.db.transaction() as db:
            row = db.execute('SELECT * FROM messager_realtime_settings WHERE bot_id=? AND actor=?', (bot_id, actor)).fetchone()
        value = json.loads(row['value_json']) if row else dict.fromkeys(self.FIELDS)
        profile_updated_at=None
        ready,speech_ready=False,False
        reason,speech_reason='',''
        if row:
            try:self._input(value);ready=True
            except (ValueError,KeyError,PermissionError,RepositoryError) as error:reason=str(error)
            try:
                speech_ready=self._speech(actor,value)
                if speech_ready and value['profile_id']:
                    from ai2apps.readaloud.repository import ReadAloudRepository
                    profile_updated_at=ReadAloudRepository(self.runtime.database,self.runtime.events).get_voice_profile(actor,value['profile_id'])['updated_at']
            except (ValueError,KeyError,PermissionError,RepositoryError) as error:speech_reason=str(error)
        return {**value,'revision':row['revision'] if row else 0,'configured':bool(row),
            'ready':ready,'reason':reason,'route':'asr-bot-tts' if speech_ready else 'asr-bot','profile_updated_at':profile_updated_at,
            'speech_ready':speech_ready,'speech_reason':speech_reason}

    def save(self, actor, bot_id, value, revision):
        with self.lock:
            self.dialogue.directory.scope(actor, {'bot_id': bot_id})
            value = self.validate(actor, value, input_required=False)
            with self.db.transaction(write=True) as db:
                if db.execute('SELECT 1 FROM messager_voice_sessions WHERE actor=? AND bot_id=? AND closed=0 AND expires>?',
                              (actor, bot_id, time.time())).fetchone():
                    raise ValueError('End the active conversation before changing its voice')
                old = db.execute('SELECT revision FROM messager_realtime_settings WHERE bot_id=?', (bot_id,)).fetchone()
                if (old['revision'] if old else 0) != revision:
                    raise ValueError('Realtime settings changed; reload before saving')
                db.execute('INSERT INTO messager_realtime_settings VALUES(?,?,?,?) ON CONFLICT(bot_id) DO UPDATE SET value_json=excluded.value_json,revision=excluded.revision',
                           (bot_id, actor, json.dumps(value), revision + 1))
            return self.get(actor, bot_id)

    def start(self, principal, bot_id, sid, controller, revision, model, language, timezone):
        with self.lock:
            self.dialogue.realtime_inputs._scope(principal, bot_id, sid)
            settings = self.get(principal.actor_user_id, bot_id)
            if not settings['ready'] or settings['revision'] != revision:
                raise ValueError('Realtime configuration is not ready or has changed')
            # The existing Bot owner validates the selected execution model.
            now = time.time()
            config = {**settings, 'model': model, 'language': language, 'timezone': timezone}
            with self.db.transaction(write=True) as db:
                old = db.execute('''SELECT * FROM messager_voice_sessions WHERE actor=? AND installation=?
                    AND closed=0 AND expires>?''', (principal.actor_user_id, principal.installation_id, now)).fetchone()
                if old:
                    if (old['controller'], old['bot_id'], old['session_id'], old['client_scope']) != (controller, bot_id, sid, principal.client_scope):
                        raise ValueError('Another window owns the microphone conversation')
                    if json.loads(old['config_json']) != config:
                        raise ValueError('End the active conversation before changing its configuration')
                    return {'id': old['id'], 'settings': json.loads(old['config_json']), 'lease_seconds': self.LEASE_SECONDS}
                ref = 'bvs_' + uuid4().hex
                db.execute('INSERT INTO messager_voice_sessions VALUES(?,?,?,?,?,?,?,?,?,?,0)',
                           (ref, principal.actor_user_id, principal.installation_id, principal.client_scope,
                            bot_id, sid, controller, json.dumps(config), now, now + self.LEASE_SECONDS))
            return {'id': ref, 'settings': config, 'lease_seconds': self.LEASE_SECONDS}

    def _session(self, principal, bot_id, ref, controller, *, closing=False):
        with self.db.transaction() as db:
            row = db.execute('SELECT * FROM messager_voice_sessions WHERE id=?', (ref,)).fetchone()
        if row is None or (row['actor'], row['installation'], row['client_scope'], row['bot_id'], row['controller']) != (
                principal.actor_user_id, principal.installation_id, principal.client_scope, bot_id, controller):
            raise PermissionError('Voice conversation unavailable')
        self.dialogue.realtime_inputs._scope(principal, bot_id, row['session_id'])
        if not closing and (row['closed'] or row['expires'] <= time.time() or row['created'] + self.MAX_SECONDS <= time.time()):
            raise ValueError('Voice conversation expired; start again')
        return dict(row)

    def touch(self, principal, bot_id, ref, controller):
        with self.lock:
            row = self._session(principal, bot_id, ref, controller)
            with self.db.transaction(write=True) as db:
                db.execute('UPDATE messager_voice_sessions SET expires=? WHERE id=?',
                           (min(time.time() + self.LEASE_SECONDS, row['created'] + self.MAX_SECONDS), ref))
        return {'active': True}

    def close(self, principal, bot_id, ref, controller):
        with self.lock:
            self._session(principal, bot_id, ref, controller, closing=True)
            with self.db.transaction(write=True) as db:
                db.execute('UPDATE messager_voice_sessions SET closed=1 WHERE id=?', (ref,))
        return {'closed': True}

    def submit(self, principal, bot_id, ref, controller, turn_id, text, attachments=()):
        with self.lock:
            row = self._session(principal, bot_id, ref, controller)
            config = json.loads(row['config_json'])
            # Use the same durable receiver key on retries, with original input
            # conflict guards; closing the voice session never cancels this Run.
            inputs = self.dialogue.realtime_inputs
            group = inputs.create(principal, bot_id, row['session_id'], ref + ':' + turn_id,
                model=config['model'], language=config['language'], client_timezone=config['timezone'])
            revision = inputs.add(principal, group, turn_id, source='speech', text=text,
                                  attachment_ids=attachments)
            inputs.close(principal, group, revision)
            return {**inputs.dispatch(principal, group), 'request_id': 'realtime-group:' + group}
