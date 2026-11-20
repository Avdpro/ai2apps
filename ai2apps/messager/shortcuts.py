"""Owner-only App-State shortcuts. Launches are UI intents, never Agent Tasks."""
import json,uuid,time,logging
from threading import RLock
_lock=RLock()
from ai2apps.apps.state_setup import get_app_state
from ai2apps.apps.app_state import digest,StateError
from .creation import BotCreateDraft,create

class AppShortcuts:
    def __init__(self,runtime):
        self.runtime,self.db=runtime,runtime.database
        logging.getLogger(__name__).info('ASC-Bot v1 loaded; source=%s',__file__)
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_shortcut_launches(
                id TEXT PRIMARY KEY,actor TEXT NOT NULL,installation TEXT NOT NULL,bot_id TEXT NOT NULL,
                definition_digest TEXT NOT NULL,packet_json TEXT NOT NULL,request_id TEXT NOT NULL,
                expires REAL NOT NULL,instance_id TEXT,status TEXT NOT NULL,UNIQUE(actor,installation,request_id))''')

    def create(self,p,body):
        packet=get_app_state(self.runtime).validate(p,body.source_instance_id,body.packet)['packet']
        draft=BotCreateDraft(request_id=body.request_id,bot_type='asc',definition={'execution_mode':'app_shortcut','config':{'state':packet}},
            name=body.name,duty='Open the saved App view; input and execution remain in its UI.',avatar=body.avatar,
            apps=[],access_review_hash=self.runtime.messager_bot_app_access.creation_catalog()['review_hash'])
        return create(self.runtime,p.actor_user_id,draft,source_principal=p,source_instance_id=body.source_instance_id)

    def definition(self,p,bot):
        d=self.runtime.messager_bots.definition(p.actor_user_id,bot)
        if d['execution_mode']!='app_shortcut':raise ValueError('Select an ASC-Bot')
        return d

    def launch(self,p,bot,request_id):
        d=self.definition(p,bot);packet=d['config']['state'];signature=digest(d)
        # Portable schema is rechecked when an owned target App instance claims it.
        get_app_state(self.runtime).describe(**{k:packet['target'][k] for k in ('app_id','mini_app_id')})
        with self.db.transaction(write=True) as db:
            db.execute('DELETE FROM messager_shortcut_launches WHERE expires<?',(time.time()-86400,))
            row=db.execute('SELECT * FROM messager_shortcut_launches WHERE actor=? AND installation=? AND request_id=?',(p.actor_user_id,p.installation_id,request_id)).fetchone()
            if row:
                if row['bot_id']!=bot or row['definition_digest']!=signature:raise ValueError('Launch request changed')
                ref=row['id']
            else:
                ref='ascl_'+uuid.uuid4().hex
                db.execute("INSERT INTO messager_shortcut_launches VALUES(?,?,?,?,?,?,?,?,NULL,'pending')",(ref,p.actor_user_id,p.installation_id,bot,signature,json.dumps(packet),request_id,time.time()+900))
        return self.get(p,ref)

    def get(self,p,ref):
        with self.db.transaction() as db:row=db.execute('SELECT * FROM messager_shortcut_launches WHERE id=? AND actor=? AND installation=?',(ref,p.actor_user_id,p.installation_id)).fetchone()
        if not row:raise PermissionError('Shortcut launch unavailable')
        if row['expires']<time.time():raise StateError('shortcut_expired','Open the shortcut again; this launch expired')
        if digest(self.definition(p,row['bot_id']))!=row['definition_digest']:raise StateError('shortcut_changed','Shortcut settings changed; open it again')
        packet=json.loads(row['packet_json'])
        if p.authentication_type=='owner_home_lease':
            from ai2apps.remote.mobile_apps import app_enabled
            if not app_enabled(self.runtime,p,packet['target']['app_id']):raise PermissionError('Target App is disabled for Mobile')
        return {'id':ref,'bot_id':row['bot_id'],'target':packet['target'],'status':row['status']}

    def claim(self,p,ref,instance):
        value=self.get(p,ref)
        with self.db.transaction(write=True) as db:
            row=db.execute('SELECT * FROM messager_shortcut_launches WHERE id=? AND actor=? AND installation=?',(ref,p.actor_user_id,p.installation_id)).fetchone()
            from .bot_types import projection
            current=db.execute('''SELECT d.definition_json,d.revision FROM messager_bot_definitions d JOIN messager_bots b ON b.id=d.bot_id AND b.actor=d.actor WHERE d.actor=? AND d.bot_id=? AND NOT EXISTS(SELECT 1 FROM messager_bot_archive a WHERE a.bot_id=d.bot_id AND a.deleted=1)''',(p.actor_user_id,row['bot_id'])).fetchone()
            if not current or digest(projection(current[0],current[1]))!=row['definition_digest']:raise StateError('shortcut_changed','Shortcut was removed or changed')
            if row['instance_id'] and row['instance_id']!=instance:raise PermissionError('Shortcut already belongs to another App instance')
            packet=json.loads(row['packet_json']);validated=get_app_state(self.runtime).validate(p,instance,packet)
            db.execute("UPDATE messager_shortcut_launches SET instance_id=?,status='claimed' WHERE id=?",(instance,ref))
        return {**value,**validated,'status':'claimed'}


def service(runtime):
    with _lock:
        if not getattr(runtime,'messager_shortcuts',None):runtime.messager_shortcuts=AppShortcuts(runtime)
        return runtime.messager_shortcuts
