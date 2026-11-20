"""Actor-owned per-Bot voice preferences; voice assets remain Voice Studio-owned."""
import json
import logging
from ai2apps.core import RepositoryError
from ai2apps.readaloud.repository import ReadAloudRepository

logging.getLogger(__name__).info('Messager Bot voice settings loaded from %s', __file__)

DEFAULT = {'mode': 'default', 'model_id': None, 'voice': None, 'profile_id': None}

class BotVoice:
    def __init__(self, directory, runtime):
        self.directory, self.runtime = directory, runtime

    def get(self, actor, bot_id):
        self.directory.scope(actor, {'bot_id': bot_id})
        with self.directory.db.transaction() as db:
            row = db.execute('SELECT settings_json,revision FROM messager_bot_voice WHERE bot_id=? AND actor=?', (bot_id, actor)).fetchone()
        return {**(json.loads(row['settings_json']) if row else DEFAULT), 'revision': row['revision'] if row else 0}

    def validate(self, actor, settings):
        value = {key: settings.get(key) for key in DEFAULT}
        if value['mode'] == 'default':
            if any(value[key] for key in ('model_id','voice','profile_id')):
                raise ValueError('Default voice cannot include overrides')
            return dict(DEFAULT)
        model_id = value['model_id']
        if value['mode'] == 'profile':
            if model_id or value['voice'] or not value['profile_id']:
                raise ValueError('Select a Voice Studio character without model overrides')
            profile = ReadAloudRepository(self.runtime.database, self.runtime.events).get_voice_profile(actor, value['profile_id'])
            if profile['status'] != 'ready' or not ((profile.get('training') or {}).get('samples') or (profile.get('training') or {}).get('design', {}).get('description')):
                raise ValueError('Character has no ready voice configuration')
            model_id = profile.get('model_id')
        elif value['mode'] != 'model' or not model_id or value['profile_id']:
            raise ValueError('Select a speech model and preset')
        invocations = getattr(self.runtime, 'model_invocations', None)
        model = invocations.model(model_id) if invocations else None
        if not model or model.model_type != 'audio_tts' or not model.checkpoint_ready:
            raise ValueError('Speech model is not ready')
        if value['mode'] == 'model':
            tts = (model.audio_capabilities or {}).get('tts', {})
            voices = tts.get('named_voices', {}).get('voices', [])
            if tts.get('instructions', {}).get('required') or (tts.get('voice_profiles', {}).get('reference_audio') and not voices):
                raise ValueError('This model requires a Voice Studio character')
            if (voices and value['voice'] not in voices) or (not voices and value['voice']):
                raise ValueError('Select a preset supported by this model')
        return value

    def save(self, actor, bot_id, settings, revision):
        self.directory.scope(actor, {'bot_id': bot_id})
        value = self.validate(actor, settings)
        with self.directory.db.transaction(write=True) as db:
            row = db.execute('SELECT revision FROM messager_bot_voice WHERE bot_id=? AND actor=?', (bot_id, actor)).fetchone()
            current = row['revision'] if row else 0
            if current != revision:
                raise RuntimeError('Voice settings changed; reload before saving')
            db.execute('INSERT INTO messager_bot_voice VALUES(?,?,?,?) ON CONFLICT(bot_id) DO UPDATE SET settings_json=excluded.settings_json,revision=excluded.revision', (bot_id,actor,json.dumps(value),current+1))
        return {**value, 'revision': current+1}

    def playback(self, actor, bot_id):
        selected = self.get(actor, bot_id)
        with self.directory.db.transaction() as db:
            row = db.execute('SELECT settings_json FROM messager_bot_voice_last WHERE bot_id=? AND actor=?', (bot_id, actor)).fetchone()
        candidates = []
        for source, value in [('selected', selected), ('previous', json.loads(row['settings_json']) if row else None)]:
            if not value:
                continue
            try:
                self.validate(actor, value)
            except (ValueError, RepositoryError):
                continue
            if not any(all(item['settings'].get(key) == value.get(key) for key in DEFAULT) for item in candidates):
                candidates.append({'source': source, 'settings': value})
        if not any(item['settings']['mode'] == 'default' for item in candidates):
            candidates.append({'source': 'default', 'settings': dict(DEFAULT)})
        return {'candidates': candidates}

    def used(self, actor, bot_id, revision):
        selected = self.get(actor, bot_id)
        if selected['revision'] != revision:
            return {'recorded': False}
        value = self.validate(actor, selected)
        if value['mode'] == 'default':
            return {'recorded': False}
        with self.directory.db.transaction(write=True) as db:
            current = db.execute('SELECT revision FROM messager_bot_voice WHERE bot_id=? AND actor=?', (bot_id,actor)).fetchone()
            if not current or current['revision'] != revision:
                return {'recorded': False}
            db.execute('INSERT INTO messager_bot_voice_last VALUES(?,?,?) ON CONFLICT(bot_id) DO UPDATE SET settings_json=excluded.settings_json', (bot_id, actor, json.dumps(value)))
        return {'recorded': True}
