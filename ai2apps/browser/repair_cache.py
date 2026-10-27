"""Owner-local locator hints; cached evidence never authorizes an operation."""
from __future__ import annotations
import hashlib
import json
import time
import sqlite3
from ai2apps.agent_builder.compiler import COMPILER_VERSION, POLICY_VERSION

SCHEMA='ai2apps.control-repair-cache/v1'

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def signature(control):
    # DOM refs and coordinates are document-local and must never be persisted.
    return digest({key:control.get(key) for key in ('tag','role','type','text','href','structure')})

def structure(snapshot,candidates):
    if snapshot.get('controls_truncated') or len(snapshot.get('items',[]))>=600:
        return None
    if not candidates or any(not item.get('structure') for item in snapshot.get('items',[])):
        return None
    return digest({'url':snapshot['url'],'controls':[signature(item) for item in snapshot['items']],
                   'permitted':sorted(signature(item) for item in candidates)})

class RepairCache:
    def __init__(self,database,key,version):
        self.database,self.key,self.version=database,key,version
        self.read_error=None

    @classmethod
    def for_step(cls,visual,page,step,goal,url):
        database=getattr(visual.runtime,'database',None)
        params=visual.run.input.get('parameters',{})
        owner=params.get('owner_user_id')
        if database is None or not owner:return None
        ir=params.get('ir') or {}
        step=step or {'operation':'click','arguments':{}}
        key=digest({'schema':SCHEMA,'owner':owner,
            'profile':getattr(page,'profile_key',None) or (params.get('browser_context') or {}).get('profile_key','default'),
            'caller':params.get('caller_app_id'),'program':params.get('agent_id') or params.get('draft_id') or ir.get('name'),
            'step':step.get('id') or step.get('name') or goal,'url':url})
        version=digest({'schema':SCHEMA,'source':ir.get('source_digest'),'generation':params.get('generation_id'),
            'model_profile':params.get('model_profile','normal'),
            'step':{k:v for k,v in step.items() if k!='browser_context'},'goal':goal,
            'compiler':COMPILER_VERSION,'policy':POLICY_VERSION,'scopes':visual.scopes,'verification':visual.policy})
        return cls(database,key,version)

    def read(self):
        try:
            with self.database.transaction() as c:
                row=c.execute('SELECT * FROM browser_control_repairs WHERE cache_key=?',(self.key,)).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as error:
            self.read_error=None if 'no such table' in str(error) else type(error).__name__
            return None

    def exists(self):
        row=self.read()
        if row and row['rule_version']!=self.version:self.invalidate();return False
        return row is not None

    def lookup(self,snapshot,candidates):
        row=self.read()
        if row is None:return None,'unavailable' if self.read_error else 'miss'
        if row['rule_version']!=self.version:self.invalidate();return None,'rule_version_changed'
        current=structure(snapshot,candidates)
        if current is None or row['structure_hash']!=current:
            self.invalidate();return None,'page_structure_changed'
        matches=[item for item in candidates if signature(item)==row['target_hash']]
        if len(matches)!=1:self.invalidate();return None,'target_not_unique'
        return matches[0],'hit'

    def ticket(self,snapshot,candidates,chosen):
        fingerprint=structure(snapshot,candidates)
        if fingerprint is None:return None
        return {'key':self.key,'version':self.version,'structure_hash':fingerprint,'target_hash':signature(chosen)}

    def save(self,ticket):
        with self.database.transaction(write=True) as c:
            c.execute('''CREATE TABLE IF NOT EXISTS browser_control_repairs (
                cache_key TEXT PRIMARY KEY, rule_version TEXT NOT NULL,
                structure_hash TEXT NOT NULL, target_hash TEXT NOT NULL,
                updated_at REAL NOT NULL, hits INTEGER NOT NULL DEFAULT 0)''')
            c.execute('''INSERT INTO browser_control_repairs VALUES (?,?,?,?,?,0)
                ON CONFLICT(cache_key) DO UPDATE SET rule_version=excluded.rule_version,
                structure_hash=excluded.structure_hash,target_hash=excluded.target_hash,
                updated_at=excluded.updated_at,hits=browser_control_repairs.hits+1''',
                (self.key,self.version,ticket['structure_hash'],ticket['target_hash'],time.time()))
            c.execute('DELETE FROM browser_control_repairs WHERE cache_key IN (SELECT cache_key FROM browser_control_repairs ORDER BY updated_at DESC LIMIT -1 OFFSET 2048)')

    def invalidate(self):
        if self.read() is None:return
        with self.database.transaction(write=True) as c:
            c.execute('DELETE FROM browser_control_repairs WHERE cache_key=?',(self.key,))


def settle(target,verification,database=None,*,uncertain=False):
    try:return _settle(target,verification,database,uncertain=uncertain)
    except sqlite3.Error:return 'unavailable'


def _settle(target,verification,database=None,*,uncertain=False):
    """Only a trusted executor's successful post-action verification promotes."""
    ticket=target.get('_repair_cache')
    if not ticket or database is None:return
    cache=RepairCache(database,ticket['key'],ticket['version'])
    readback=verification.get('readback') or {}
    verdict=readback.get('verified') if isinstance(readback,dict) else None
    if uncertain or verdict is False or verification.get('visually_verified') is False:
        cache.invalidate();return 'invalidated'
    if verdict is True or verification.get('visually_verified') is True:
        cache.save(ticket)
        return 'saved'
