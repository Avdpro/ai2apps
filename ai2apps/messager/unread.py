"""Owner-scoped display cursors; never changes Agent context or execution state."""
from ai2apps.core import utc_now_text

REGISTRATION = 'ai2apps.messager.bots'


class BotUnread:
    def __init__(self, directory):
        self.directory, self.db = directory, directory.db
        with self.db.transaction(write=True) as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='messager_bot_read_cursors'").fetchone()
            db.execute('''CREATE TABLE IF NOT EXISTS messager_bot_read_cursors(
                actor TEXT NOT NULL,bot_id TEXT NOT NULL,session_id TEXT NOT NULL,
                sequence INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL,
                PRIMARY KEY(actor,bot_id,session_id))''')
            if not exists:
                # Existing history predates read tracking. Start from the current end once.
                db.execute('''INSERT INTO messager_bot_read_cursors
                    SELECT s.owner,json_extract(s.scope_json,'$.bot_id'),s.session_id,
                        COALESCE(MAX(m.sequence),0),?
                    FROM app_chat_sessions s LEFT JOIN messages m ON m.session_id=s.session_id
                    WHERE s.registration=? AND json_extract(s.scope_json,'$.bot_id') IS NOT NULL
                    GROUP BY s.session_id''', (utc_now_text(), REGISTRATION))

    def counts(self, actor):
        with self.db.transaction() as db:
            return {r['bot_id']: r['n'] for r in db.execute('''
                SELECT json_extract(s.scope_json,'$.bot_id') AS bot_id,COUNT(m.id) AS n
                FROM app_chat_sessions s JOIN messages m ON m.session_id=s.session_id
                LEFT JOIN messager_bot_read_cursors c ON c.actor=s.owner
                    AND c.session_id=s.session_id AND c.bot_id=json_extract(s.scope_json,'$.bot_id')
                WHERE s.owner=? AND s.registration=?
                    AND json_extract(s.scope_json,'$.dialogue_job') IS NULL
                    AND json_extract(s.scope_json,'$.archive_id') IS NULL
                    AND m.role='assistant'
                    AND m.status='completed' AND m.sequence>COALESCE(c.sequence,0)
                GROUP BY json_extract(s.scope_json,'$.bot_id')''', (actor, REGISTRATION))}

    def state(self, actor, bot_id, sid, through=None):
        self.directory.scope(actor, {'bot_id': bot_id})
        with self.db.transaction(write=through is not None) as db:
            source = db.execute('''SELECT 1 FROM app_chat_sessions WHERE session_id=? AND owner=?
                AND registration=? AND json_extract(scope_json,'$.bot_id')=?
                AND json_extract(scope_json,'$.archive_id') IS NULL
                AND json_extract(scope_json,'$.dialogue_job') IS NULL''', (sid, actor, REGISTRATION, bot_id)).fetchone()
            if not source:
                raise PermissionError('Bot conversation unavailable')
            latest = db.execute('SELECT COALESCE(MAX(sequence),0) FROM messages WHERE session_id=?', (sid,)).fetchone()[0]
            if through is not None:
                if type(through) is not int or not 0 <= through <= latest:
                    raise ValueError('Invalid read position')
                db.execute('''INSERT INTO messager_bot_read_cursors VALUES(?,?,?,?,?)
                    ON CONFLICT(actor,bot_id,session_id) DO UPDATE SET
                    sequence=MAX(sequence,excluded.sequence),updated_at=excluded.updated_at''',
                    (actor, bot_id, sid, through, utc_now_text()))
            row = db.execute('SELECT sequence FROM messager_bot_read_cursors WHERE actor=? AND bot_id=? AND session_id=?', (actor, bot_id, sid)).fetchone()
            sequence = row[0] if row else 0
            unread = db.execute('''SELECT COUNT(*),MIN(sequence) FROM messages
                WHERE session_id=? AND role='assistant' AND status='completed' AND sequence>?''', (sid, sequence)).fetchone()
            return {'session_id': sid, 'read_sequence': sequence, 'latest_sequence': latest,
                    'unread_count': unread[0], 'first_unread_sequence': unread[1]}
