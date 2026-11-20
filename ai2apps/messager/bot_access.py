"""Owner-managed directed Bot use grants and private discovery boundaries."""
from contextlib import nullcontext
import logging


class BotUseAccess:
    def __init__(self,runtime,directory):
        self.runtime,self.directory,self.db=runtime,directory,runtime.database
        with self.db.transaction(write=True) as db:
            db.execute('CREATE TABLE IF NOT EXISTS messager_bot_exposure(bot TEXT PRIMARY KEY,actor TEXT NOT NULL,mode TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS messager_bot_use_state(actor TEXT PRIMARY KEY,revision INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS messager_bot_use_removed(actor TEXT NOT NULL,source TEXT NOT NULL,target TEXT NOT NULL,PRIMARY KEY(actor,source,target))')
            db.execute('CREATE TABLE IF NOT EXISTS messager_bot_use(actor TEXT NOT NULL,source TEXT NOT NULL,target TEXT NOT NULL,enabled INTEGER NOT NULL,revision INTEGER NOT NULL,PRIMARY KEY(actor,source,target))')
            db.execute('CREATE TABLE IF NOT EXISTS messager_bot_use_receipts(kind TEXT NOT NULL,ref TEXT NOT NULL,actor TEXT NOT NULL,source TEXT NOT NULL,target TEXT NOT NULL,revision INTEGER NOT NULL,PRIMARY KEY(kind,ref,source,target))')
        logging.getLogger(__name__).info('Bot exposure and directed access C4.1.2 loaded; source=%s',__file__)

    def mode(self,actor,bot):
        with self.db.transaction() as db:r=db.execute('SELECT mode FROM messager_bot_exposure WHERE actor=? AND bot=?',(actor,bot)).fetchone()
        return r[0] if r else 'public'

    def link(self,actor,source,target):
        self.directory.scope(actor,{'bot_id':source})
        self.directory.scope(actor,{'bot_id':target})
        if source==target:return {'enabled':True,'revision':0,'implicit':True}
        with self.db.transaction() as db:r=db.execute('SELECT enabled,revision FROM messager_bot_use WHERE actor=? AND source=? AND target=?',(actor,source,target)).fetchone()
        return {'enabled':bool(r['enabled']),'revision':r['revision']} if r else {'enabled':False,'revision':0}

    def visible(self,actor,source,target):
        try:return self.link(actor,source,target)['enabled'] or self.mode(actor,target)=='public'
        except (PermissionError,ValueError):return False

    def discover(self,actor,source,target):
        if not self.visible(actor,source,target):raise PermissionError('Target unavailable')
        return self.link(actor,source,target)

    def state(self,db,actor,expected=None):
        db.execute('INSERT OR IGNORE INTO messager_bot_use_state VALUES(?,1)',(actor,))
        rev=db.execute('SELECT revision FROM messager_bot_use_state WHERE actor=?',(actor,)).fetchone()[0]
        if expected is not None and expected!=rev:raise ValueError('Bot access changed; reload before editing')
        return rev

    def change(self,db,actor,source,target,enabled):
        old=self.link(actor,source,target)
        if source==target:raise ValueError('A Bot can always use itself for independent tasks')
        if enabled and db.execute('DELETE FROM messager_bot_use_removed WHERE actor=? AND source=? AND target=?',(actor,source,target)).rowcount:
            db.execute('UPDATE messager_bot_use_state SET revision=revision+1 WHERE actor=?',(actor,))
        if old['enabled']==enabled and old['revision']:return old
        revision=old['revision']+1
        db.execute('INSERT INTO messager_bot_use VALUES(?,?,?,?,?) ON CONFLICT(actor,source,target) DO UPDATE SET enabled=excluded.enabled,revision=excluded.revision',(actor,source,target,int(enabled),revision))
        db.execute('UPDATE messager_bot_use_state SET revision=revision+1 WHERE actor=?',(actor,))
        return {'enabled':enabled,'revision':revision}

    def set_link(self,actor,source,target,enabled,revision):
        with self.runtime.app_chat.lock:
            with self.db.transaction(write=True) as db:
                self.state(db,actor,revision);old=self.link(actor,source,target);value=self.change(db,actor,source,target,enabled)
            if value['revision']!=old['revision']:self.stop_pair(actor,source,target,'Bot use access revoked' if not enabled else 'Bot use access changed; previous requests remain stopped')
        return value

    def remove_link(self,actor,source,target,revision):
        # Keep the permission epoch: re-adding must never revive old receipts.
        with self.runtime.app_chat.lock:
            with self.db.transaction(write=True) as db:
                self.state(db,actor,revision)
                self.change(db,actor,source,target,False)
                db.execute('INSERT OR IGNORE INTO messager_bot_use_removed VALUES(?,?,?)',(actor,source,target))
                db.execute('UPDATE messager_bot_use_state SET revision=revision+1 WHERE actor=?',(actor,))
            self.stop_pair(actor,source,target,'Bot use access removed')

    def set_mode(self,actor,bot,mode,revision):
        if mode not in ('public','private'):raise ValueError('Choose Public or Private')
        self.directory.scope(actor,{'bot_id':bot})
        with self.runtime.app_chat.lock:
            with self.db.transaction(write=True) as db:
                self.state(db,actor,revision)
                db.execute('INSERT INTO messager_bot_exposure VALUES(?,?,?) ON CONFLICT(bot) DO UPDATE SET mode=excluded.mode',(bot,actor,mode))
                db.execute('UPDATE messager_bot_use_state SET revision=revision+1 WHERE actor=?',(actor,))
            if mode=='private':
                for b in self.directory.list(actor):
                    if b['id']!=bot and not self.link(actor,b['id'],bot)['enabled']:self.stop_pair(actor,b['id'],bot)

    def admit(self,kind,ref,actor,source,target,*,approve=False,expected=None,connection=None):
        """Persist exact pair epoch; approving is exclusively an owner UI decision."""
        with self.runtime.app_chat.lock:
            with (nullcontext(connection) if connection is not None else self.db.transaction(write=True)) as db:
                receipt=db.execute('SELECT * FROM messager_bot_use_receipts WHERE kind=? AND ref=? AND source=? AND target=?',(kind,ref,source,target)).fetchone()
                if receipt:
                    self.validate(kind,ref,actor,source,target);return
                current=self.discover(actor,source,target)
                if expected is not None and current['revision']!=expected:raise PermissionError('Bot access changed; prepare a new request')
                if not current['enabled']:
                    if not approve:raise PermissionError('Bot use needs owner approval')
                    self.state(db,actor);current=self.change(db,actor,source,target,True)
                db.execute('INSERT INTO messager_bot_use_receipts VALUES(?,?,?,?,?,?)',(kind,ref,actor,source,target,current['revision']))

    def validate(self,kind,ref,actor,source,target):
        current=self.link(actor,source,target)
        with self.db.transaction() as db:r=db.execute('SELECT actor,revision FROM messager_bot_use_receipts WHERE kind=? AND ref=? AND source=? AND target=?',(kind,ref,source,target)).fetchone()
        if not r or r['actor']!=actor or not current['enabled'] or r['revision']!=current['revision']:raise PermissionError('Bot use authorization revoked or unavailable')

    def stop_pair(self,actor,source,target,reason='Bot use access revoked'):
        # Revocation commits before cancellation. Every execution also checks its epoch.
        with self.db.transaction() as db:
            delegations=[dict(r) for r in db.execute("SELECT * FROM messager_bot_delegations WHERE actor=? AND source_bot=? AND target_bot=? AND status IN ('pending','admitting','running')",(actor,source,target))]
            consultations=[dict(r) for r in db.execute("SELECT * FROM messager_bot_consultations WHERE actor=? AND source_bot=? AND target_bot=? AND status IN ('pending','queued') AND projected=0",(actor,source,target))]
        for row in delegations:self.runtime.messager_bot_delegation.stop(row,'cancelled',reason)
        for row in consultations:
            if row['run_id']:self.runtime.agents.request_cancel(row['run_id'])
            else:
                with self.db.transaction(write=True) as db:db.execute("UPDATE messager_bot_consultations SET status='cancelled' WHERE id=? AND status='pending'",(row['id'],))
                self.runtime.messager_bot_communication.project(row|{'status':'cancelled'})
        self.runtime.agent_runtime.wake()

    def catalog(self,actor,bot):
        self.directory.scope(actor,{'bot_id':bot})
        owned={b['id']:b for b in self.directory.list(actor)}
        def item(ref,enabled):
            b=owned.get(ref)
            return {'id':ref,'name':b['name'] if b else 'Unavailable Bot','avatar':b.get('avatar') if b else None,'enabled':bool(enabled),'available':b is not None}
        with self.db.transaction(write=True) as db:
            revision=self.state(db,actor)
            outgoing=[dict(r) for r in db.execute('SELECT target,enabled FROM messager_bot_use u WHERE actor=? AND source=? AND NOT EXISTS (SELECT 1 FROM messager_bot_use_removed r WHERE r.actor=u.actor AND r.source=u.source AND r.target=u.target) ORDER BY rowid',(actor,bot))]
            incoming=[dict(r) for r in db.execute('SELECT source FROM messager_bot_use WHERE actor=? AND target=? AND enabled=1 ORDER BY rowid',(actor,bot))]
        selected={r['target'] for r in outgoing}
        return {'revision':revision,'mode':self.mode(actor,bot),'outgoing':[item(r['target'],r['enabled']) for r in outgoing],
            'incoming':[item(r['source'],True) for r in incoming],
            'candidates':[item(ref,False) for ref in owned if ref!=bot and ref not in selected],
            'caller_candidates':[item(ref,False) for ref in owned if ref!=bot and ref not in {r['source'] for r in incoming}]}
