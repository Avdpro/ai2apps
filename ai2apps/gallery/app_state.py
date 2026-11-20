"""Owner-declared portable navigation settings; no content or execution state."""
from ai2apps.apps.app_state import StateContract

def register(service):
    props={'collection_id':{'type':'string','minLength':1,'maxLength':128}, 'kind':{'type':'string','enum':['','image','video','audio','web','document','file']}, 'view':{'type':'string','enum':['grid','list']}}
    for field in props.values():field['x-app-state']='portable'
    service.register(StateContract('ai2apps.gallery',None,1,'Gallery view',
        {'type':'object','properties':props,'required':list(props),'additionalProperties':False},
        excluded_fields=('query','search','prompt','body','attachments','task_id','permissions','credentials')))
