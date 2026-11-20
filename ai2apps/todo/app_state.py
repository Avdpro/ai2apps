"""Owner-declared portable navigation settings; no content or execution state."""
from ai2apps.apps.app_state import StateContract

def register(service):
    props={'directory_id':{'type':['string','null'],'maxLength':128}}
    for field in props.values():field['x-app-state']='portable'
    service.register(StateContract('ai2apps.todo',None,1,'Todo directory',
        {'type':'object','properties':props,'required':list(props),'additionalProperties':False},
        excluded_fields=('query','search','prompt','body','attachments','task_id','permissions','credentials')))
