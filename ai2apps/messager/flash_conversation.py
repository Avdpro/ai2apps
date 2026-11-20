"""Owner conversation control for fixed Flash workflows; never an execution planner."""
import asyncio
import json
from .app_access import digest
from .flash_plans import CompileRequest,compile_plan,model_json,Plan,validate_input


def _valid_intent(value):
    intent=value.get('intent')
    if intent=='edit':
        role=value.get('role')
        return isinstance(role,str) and bool(role.strip()) and len(role)<=600
    return intent in ('execute','help','adapt','reject')


async def submit(runtime,principal,bot_id,body):
    binding=runtime.app_chat.access(principal,body.session_id)
    if binding['registration']!='ai2apps.messager.bots' or binding['scope']!={'bot_id':bot_id}:raise PermissionError('Main Bot conversation required')
    runtime.messager_bots.scope(principal.actor_user_id,{'bot_id':bot_id})
    signature=digest(body.model_dump())
    with runtime.database.transaction(write=True) as db:
        db.execute('CREATE TABLE IF NOT EXISTS messager_flash_conversation_requests(actor TEXT,bot_id TEXT,request_id TEXT,signature TEXT,response_json TEXT,PRIMARY KEY(actor,bot_id,request_id))')
        prior=db.execute('SELECT signature,response_json FROM messager_flash_conversation_requests WHERE actor=? AND bot_id=? AND request_id=?',(principal.actor_user_id,bot_id,body.request_id)).fetchone()
    if prior:
        if prior['signature']!=signature:raise ValueError('This request ID belongs to another message')
        return json.loads(prior['response_json'])
    definition=runtime.messager_bots.definition(principal.actor_user_id,bot_id)
    if definition['execution_mode']!='flash':raise ValueError('Flash-Bot required')
    workflow=runtime.messager_flash.workflow(definition['config'])
    files=[runtime.documents.get(body.session_id,ref) for ref in body.attachments]
    valid=True
    try:
        if definition['config'].get('plan'):
            validate_input(Plan.model_validate(definition['config']['plan']),body.text,files)
        else:workflow.validate(body.text,files)
    except ValueError:valid=False
    if valid and (files or (definition['config'].get('plan') or {}).get('input_kind')=='expression' or not definition['config'].get('plan')):
        return {'kind':'execution','run_id':runtime.messager_flash.submit(principal,bot_id,body.session_id,body.request_id,body.text,body.attachments,body.task_session_id,body.language)}
    # Text shares one conversation entry: classify intent before treating valid
    # text as transformation input. Structured file/expression input stays cheap.
    if not hasattr(runtime.messager_flash,'conversation_locks'):runtime.messager_flash.conversation_locks={}
    locks=runtime.messager_flash.conversation_locks
    key=(principal.actor_user_id,bot_id,body.request_id)
    lock=locks.setdefault(key,asyncio.Lock())
    try:
        async with lock:return await _decide(runtime,principal,bot_id,body,definition,workflow,files,valid)
    finally:
        if not lock.locked() and not getattr(lock,'_waiters',None):locks.pop(key,None)


async def _decide(runtime,principal,bot_id,body,definition,workflow,files,valid):
    actor=principal.actor_user_id
    signature=digest(body.model_dump())
    with runtime.database.transaction(write=True) as db:
        db.execute('CREATE TABLE IF NOT EXISTS messager_flash_conversation_requests(actor TEXT,bot_id TEXT,request_id TEXT,signature TEXT,response_json TEXT,PRIMARY KEY(actor,bot_id,request_id))')
        prior=db.execute('SELECT signature,response_json FROM messager_flash_conversation_requests WHERE actor=? AND bot_id=? AND request_id=?',(actor,bot_id,body.request_id)).fetchone()
    if prior:
        if prior['signature']!=signature:raise ValueError('This request ID belongs to another message')
        return json.loads(prior['response_json'])
    bot=next(b for b in runtime.messager_bots.list(actor) if b['id']==bot_id)
    model=definition['config'].get('model')
    if not model:
        from .conversation_profile import settings
        model=settings(runtime,actor,bot_id)['effective_model']
    usage=workflow.usage if hasattr(workflow,'usage') else workflow.description
    result={'kind':'help','message':'这条输入不符合当前工作流要求。 / This input does not match the workflow. '+usage}
    try:
        if model and len(body.text)<=2000:
            decision=await model_json(runtime,principal,model,[
                {'role':'system','content':'Classify an owner message sent to a fixed Flash-Bot. Do not execute tools. Return JSON {"intent":"execute|edit|help|adapt|reject","message":"concise explanation in user language","role":"complete revised Role <=600 characters, edit only"}. An edit changes future workflow behavior; preserve all existing requirements except explicit requested changes. Help asks usage. Adapt is ONLY natural language execution input for an existing expression/text contract with adapt_input enabled. A missing file cannot be invented. Never turn a rejected execution into a workflow change unless the owner actually requests changing its behavior. Execute means ordinary input for the CURRENT workflow, including quoted text that mentions changes. Edit means the owner clearly requests changing this Bot or its future workflow. If the distinction is ambiguous, ask one concise clarification; do not run or modify anything. There is no edit mode switch. Do not promise that anything ran or was updated.'},
                {'role':'user','content':json.dumps({'message':body.text,'role':bot['duty'],'workflow':definition['config'].get('plan'),'usage':usage,'attachments':[{'filename':f.filename,'media_type':f.media_type} for f in files]},ensure_ascii=False)}],purpose='conversation',max_tokens=1200,validate=_valid_intent)
            intent=decision.get('intent')
            if intent=='edit':
                role=decision['role'].strip()
                apps=[{'app_id':a['app_id'],'enabled':True} for a in runtime.messager_bot_app_access.catalog(actor,bot_id)['items'] if a.get('enabled')]
                draft=await compile_plan(runtime,principal,CompileRequest(role=role,model=model,apps=apps),previous_role=bot['duty'],change_request=body.text)
                result={'kind':'workflow_review','draft':draft,'expected_revision':definition['revision'],
                        'previous_plan':definition['config'].get('plan'),
                        'message':'已生成工作流修改草案，请审阅并确认后启用。当前流程尚未改变，本次没有执行任务。 / A revised workflow is ready for review. The current workflow is unchanged; no task was run.'}
            elif (intent=='execute' and valid) or (intent=='adapt' and (definition['config'].get('plan') or {}).get('adapt_input')):
                return {'kind':'execution','run_id':runtime.messager_flash.submit(principal,bot_id,body.session_id,body.request_id,body.text,body.attachments,body.task_session_id,body.language)}
            else:
                explanation=decision.get('message')
                if isinstance(explanation,str) and explanation.strip():result['message']=explanation[:1000]+'\n'+usage
        elif valid:
            return {'kind':'execution','run_id':runtime.messager_flash.submit(principal,bot_id,body.session_id,body.request_id,body.text,body.attachments,body.task_session_id,body.language)}
    except ValueError as exc:
        result={'kind':'help','message':str(exc)[:1200]}
    # Durable replies and idempotent review drafts, without creating a Todo/Run.
    origin='flash-conversation:'+bot_id+':'+body.request_id
    runtime.messager_dialogue.append(body.session_id,'user',body.text,origin+':user',
                                     {'origin':'flash_workflow_conversation','client_request_id':body.request_id})
    runtime.messager_dialogue.append(body.session_id,'assistant',result['message'],origin+':reply',{'origin':'flash_workflow_conversation'})
    with runtime.database.transaction(write=True) as db:
        db.execute('INSERT INTO messager_flash_conversation_requests VALUES(?,?,?,?,?)',(actor,bot_id,body.request_id,signature,json.dumps(result)))
    return result
