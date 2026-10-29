"""Todo owner: scope and UI semantics, shared business services with AaAT/UI."""
from ai2apps.app_chat.service import AppChatOwner
from ai2apps.todo.aaat import store,DECLARATION

UI_SCHEMA={'type':'object','properties':{
    'action':{'enum':['read','select_project','set_search','set_filter','expand_project']},
    'task_id':{'type':'string'},'query':{'type':'string','maxLength':500},
    'filter':{'enum':['all','open','scheduled','completed','priority-U','priority-S','priority-A','priority-B','priority-C','priority-D']}},'required':['action'],'additionalProperties':False,
    'allOf':[{'if':{'properties':{'action':{'enum':['select_project','expand_project']}}},'then':{'required':['task_id']}},
        {'if':{'properties':{'action':{'const':'set_search'}}},'then':{'required':['query']}},
        {'if':{'properties':{'action':{'const':'set_filter'}}},'then':{'required':['filter']}}]}


def install(runtime):
    from ai2apps.services import ToolProviderError
    names=('todo.resolve_directory','todo.search','todo.get','todo.create','todo.update','todo.resolve_project','todo.project_stats','todo.children','todo.ui')
    def validate(actor,scope):
        if set(scope)-{'directory_id'} or not scope.get('directory_id'):raise ValueError('Select a Todo directory before starting Chat')
        snapshot=store(runtime).snapshot(actor)
        if not any(d['id']==scope['directory_id'] for d in snapshot['directories']):raise PermissionError('Directory not found')
        return {'directory_id':scope['directory_id']}
    def authorize(actor,scope,name,args):
        payload={k:v for k,v in args.items() if k not in ('provider','parameters')};payload.update(args.get('parameters',{}))
        directory=scope['directory_id']
        if payload.get('directory_id',directory)!=directory:raise ToolProviderError('Project is outside this conversation directory')
        for key in ('task_id','project_id','parent_id'):
            if payload.get(key) and store(runtime).get(actor,payload[key])['directory_id']!=directory:raise ToolProviderError('Project is outside this conversation directory')
        if name=='todo.update' and payload.get('patch',{}).get('directory_id',directory)!=directory:raise ToolProviderError('Moving projects outside Chat scope is unavailable')
    runtime.app_chat.register(AppChatOwner(id='ai2apps.todo.chat',app_id='ai2apps.todo',version='1',
        capabilities=names,validate_scope=validate,authorize_call=authorize,ui_schema=UI_SCHEMA,
        instructions='\n'.join(DECLARATION['instructions'])+'\nThis conversation is limited to its fixed directory. Use todo.search for lists; directory_id is filled by the owner. todo.update accepts a precise patch and current task revision. UI actions only change presentation, never task data. Dirty UI edits must not be overwritten.'))
