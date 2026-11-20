"""Todo owns task creation authority and cross-database creation receipts."""
from ai2apps.events.actions import HookAction
from ai2apps.system_tasks.sessions import execution_principal
from .aaat import store


def install(runtime):
    def prepare(actor,value):
        if not isinstance(value,dict) or set(value)-{'title','directory_id','include_review'}:raise ValueError('Invalid Todo action')
        title=value.get('title','跟进 Bot 事件摘要')
        directory=value.get('directory_id')
        if not isinstance(title,str) or not 1<=len(title.strip())<=200:raise ValueError('Todo title required')
        if directory is not None and (not isinstance(directory,str) or directory not in {d['id'] for d in store(runtime).snapshot(actor)['directories']}):
            raise PermissionError('Todo directory unavailable')
        if type(value.get('include_review',True)) is not bool:raise ValueError('Invalid review inclusion')
        principal=execution_principal(runtime,actor)
        definition=runtime.extension_manager._active_app_definition('ai2apps.todo')
        if definition is None or definition['status']!='enabled':raise PermissionError('Action App unavailable')
        runtime.extension_manager._require_app_access(definition,principal)
        return {'title':title.strip(),'directory_id':directory,'include_review':value.get('include_review',True)}
    async def execute(work,args,evidence,key):
        prepare(work.actor,args);work.check()
        description='事件：'+work.event['id']+'\n来源对象：'+work.event['subject']['id']
        if args['include_review']:description+='\n\n'+str(evidence.get('content',''))[:10000]
        value={'title':args['title'],'description':description,'directory_id':args['directory_id'] or '', 'priority':'B'}
        task=store(runtime).save(work.actor,value,creation_key=key,create_inbox=args['directory_id'] is None)
        return {'receipt_id':task['id'],'status':'created','task_id':task['id'],'title':task['title']}
    runtime.hook_actions.register(HookAction('todo.create','1','创建 Todo（指定目录或收件箱）',prepare,execute,recoverable=True))
