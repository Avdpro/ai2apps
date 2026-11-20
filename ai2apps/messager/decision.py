"""Bot-owned decision envelope validation, before memory, plans or Task admission."""
import json

KINDS={'reply','task','continue','plan_update','clarify','recall'}
FIELDS={'kind','text','title','plan_title','step_label','target_session_id','task_id','schedule',
        'memory_candidates','use_memories','recall_query','access_requirements','instruction_change','replacement_instructions'}


def parse_decision(content):
    value=json.loads(content,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
    if not isinstance(value,dict) or set(value)-FIELDS:
        raise ValueError('Invalid decision object')
    if value.get('kind') not in KINDS or not isinstance(value.get('text'),str) or not 1<=len(value['text'].strip())<=12000:
        raise ValueError('Invalid decision kind or text')
    for name,limit in [('title',200),('plan_title',200),('step_label',500),('target_session_id',200),('task_id',200),('recall_query',160),('instruction_change',12000),('replacement_instructions',12000)]:
        if value.get(name) is not None and (not isinstance(value[name],str) or not value[name].strip() or len(value[name])>limit):
            raise ValueError('Invalid decision field')
    for name,limit in [('memory_candidates',3),('access_requirements',16)]:
        if name in value and (not isinstance(value[name],list) or len(value[name])>limit or not all(isinstance(x,dict) for x in value[name])):
            raise ValueError('Invalid decision list')
    ids=value.get('use_memories',[])
    if not isinstance(ids,list) or len(ids)>4 or not all(isinstance(x,str) and 1<=len(x)<=200 for x in ids):
        raise ValueError('Invalid memory selection')
    schedule=value.get('schedule')
    if schedule is not None:
        from ai2apps.todo.models import Schedule
        if not isinstance(schedule,dict) or set(schedule)-set(Schedule.model_fields):
            raise ValueError('Invalid schedule')
        for name,item in schedule.items():
            if name in {'hour','minute','weekday','day'}:
                limit={'hour':23,'minute':59,'weekday':6,'day':31}[name]
                if type(item) is not int or not (1 if name=='day' else 0)<=item<=limit:raise ValueError('Invalid schedule number')
            elif name=='auto_execute':
                if type(item) is not bool:raise ValueError('Invalid schedule flag')
            elif not isinstance(item,str):raise ValueError('Invalid schedule text')
        if 'frequency' in schedule and schedule['frequency'] not in {'off','once','hourly','daily','weekly','monthly'}:raise ValueError('Invalid frequency')
    if value['kind']=='recall' and not value.get('recall_query'):raise ValueError('Missing recall query')
    if value['kind']=='plan_update' and not value.get('task_id'):raise ValueError('Missing plan identity')
    instruction_fields = ('instruction_change', 'replacement_instructions')
    instruction_edits = sum(value.get(name) is not None for name in instruction_fields)
    if instruction_edits > 1:
        raise ValueError('Choose one execution instruction edit')
    if (instruction_edits or value.get('plan_title') is not None) and value['kind']!='plan_update':
        raise ValueError('Execution instruction and plan title edits require a plan update')
    for item in value.get('access_requirements',[]):
        if set(item)-{'capability','provider','reason','conditional'} or not all(isinstance(item.get(k),str) and 1<=len(item[k])<=1000 for k in ('capability','provider','reason')) or ('conditional' in item and type(item['conditional']) is not bool):
            raise ValueError('Invalid access requirement')
    value['text']=value['text'].strip()
    return value
