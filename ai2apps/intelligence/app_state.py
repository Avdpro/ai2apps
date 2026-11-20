"""Owner-declared portable navigation settings; no content or execution state."""
from ai2apps.apps.app_state import StateContract

def register(service):
    props={'channel_id':{'type':['string','null'],'maxLength':128}, 'tab':{'type':'string','enum':['articles','topics','entities','opportunities','drafts','sources','runs']}, 'article_filter':{'type':'string','enum':['all','unread','more']}, 'article_type':{'type':'string','enum':['all','webpage','post','video','audio','image','document']}}
    for field in props.values():field['x-app-state']='portable'
    service.register(StateContract('ai2apps.intelligence',None,1,'Intel Center view',
        {'type':'object','properties':props,'required':list(props),'additionalProperties':False},
        excluded_fields=('query','search','prompt','body','attachments','task_id','permissions','credentials')))
