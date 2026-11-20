"""Owner-declared portable navigation settings; no content or execution state."""
from ai2apps.apps.app_state import StateContract

def register(service):
    props={'bucket_id':{'type':'string','maxLength':128}, 'kind':{'type':'string','enum':['','note','webpage','document','chat','artifact','image']}, 'view':{'type':'string','enum':['ask','library']}}
    for field in props.values():field['x-app-state']='portable'
    service.register(StateContract('ai2apps.knowledge',None,1,'Knowledge view',
        {'type':'object','properties':props,'required':list(props),'additionalProperties':False},
        excluded_fields=('query','search','prompt','body','attachments','task_id','permissions','credentials')))
