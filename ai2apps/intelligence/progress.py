"""Owner presentation for the existing Intelligence task state."""

def refresh_progress(run):
    data=run.get('progress') or {}
    status=run['status']
    state='waiting' if data.get('waiting') else status if status in ('completed','partial','failed','cancelled') else 'running'
    metrics=[{'label':label,'value':data[key]} for key,label in (
        ('pages_read','已读取页面'),('articles_extracted','已提取文章'),
        ('articles_saved','已保存情报'),('sources_completed','已完成来源')) if type(data.get(key)) in (int,float)]
    return {'text':run.get('message') or '情报频道正在刷新','phase':data.get('phase','collecting'),
        'content':{'task_progress':{'schema':'ai2apps.task-progress/v1','state':state,
        'stage':str(data.get('phase','collecting'))[:100],'task_id':run['id'],
        'requires_user':bool(data.get('waiting')),
        'wait_reason':str(run.get('message',''))[:500] if state=='waiting' else '', 'metrics':metrics}}}
