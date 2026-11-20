"""Local-only self notifications. No Cloud/WeChat send authority is implied."""
import json,time,uuid
from ai2apps.events.actions import HookAction
from ai2apps.system_tasks.sessions import execution_principal


def install(runtime):
    def prepare(actor,value):
        if not isinstance(value,dict) or set(value)-{'title','include_review'}:raise ValueError('Invalid local notification')
        title=value.get('title','Bot 事件处理已完成')
        if not isinstance(title,str) or not 1<=len(title.strip())<=120:raise ValueError('Notification title required')
        if type(value.get('include_review',True)) is not bool:raise ValueError('Invalid review inclusion')
        principal=execution_principal(runtime,actor)
        definition=runtime.extension_manager._active_app_definition('ai2apps.messager')
        if definition is None or definition['status']!='enabled':raise PermissionError('Action App unavailable')
        runtime.extension_manager._require_app_access(definition,principal)
        return {'title':title.strip(),'include_review':value.get('include_review',True)}
    async def execute(work,args,evidence,key):
        prepare(work.actor,args);work.check()
        content={'title':args['title'],'body':str(evidence.get('content',''))[:10000] if args['include_review'] else '',
            'session_id':evidence.get('session_id'),'run_id':evidence.get('run_id'),'event_id':work.event['id']}
        body=json.dumps(content,ensure_ascii=False,sort_keys=True)
        with runtime.database.transaction(write=True) as db:
            old=db.execute('SELECT * FROM hook_local_notices WHERE owner=? AND operation_key=?',(work.actor,key)).fetchone()
            if old:
                if old['content_json']!=body:raise ValueError('Notification operation receipt conflict')
                nid=old['id']
            else:
                nid='hn_'+uuid.uuid4().hex
                db.execute('INSERT INTO hook_local_notices VALUES(?,?,?,?,?,?,NULL)',(nid,work.actor,key,work.row['id'],body,time.time()))
        return {'receipt_id':nid,'status':'saved','notification_id':nid}
    runtime.hook_actions.register(HookAction('notification.local','1','站内通知（仅当前用户、本机）',prepare,execute,recoverable=True))
