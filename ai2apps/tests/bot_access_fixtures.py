"""Explicitly restricted Bots for legacy/interface and approval regression scenarios."""
import json

def restricted_bot(runtime, bot, *, legacy_read=False):
    # These scenarios test no-App-grant admission, rather than the product defaults.
    with runtime.database.transaction(write=True) as db:
        db.execute("UPDATE messager_bot_app_access SET grants_json='{}' WHERE bot_id=? AND actor='local'", (bot['id'],))
        if legacy_read:
            permissions=runtime.messager_bot_permissions
            grant={'intelligence.read':{'foreground':True,'background':False,'providers':{p.id:p.version for p in permissions.providers(permissions.profiles['intelligence.read'])}}}
            db.execute('UPDATE messager_bot_permissions SET grants_json=? WHERE bot_id=? AND actor=?',(json.dumps(grant),bot['id'],'local'))
    return bot
