"""Article dialogue routes share the Intelligence owner/access dependency."""
import asyncio
from fastapi import HTTPException, Response
from ai2apps.intelligence import article_chat as chat
from ai2apps.services import ToolProviderError


def install(router,runtime_provider,store,dep):
    def repo():return chat.Repository(store())
    def checked(call,*args,**kwargs):
        try:return call(*args,**kwargs)
        except KeyError as e:raise HTTPException(404,'Article conversation not found') from e
        except (ValueError,ToolProviderError) as e:raise HTTPException(409,str(e)) from e
    def session(runtime,principal):
        from ai2apps.system_tasks.sessions import execution_session
        return execution_session(runtime,principal.actor_user_id,'ai2apps.intelligence')
    def search_mount(runtime,principal):
        from ai2apps.browser.mini_apps import WebAgentMiniAppBroker
        return WebAgentMiniAppBroker(runtime).registered('ai2apps.search-all',principal,session(runtime,principal))
    def scope(id,thread):return 'intelligence.article-chat:'+id+':'+thread

    @router.get('/articles/{id}/chat/models')
    async def models(id:str,principal=dep):
        checked(store().get,'articles',principal.actor_user_id,id)
        return await chat.conversation_models(runtime_provider(),principal)

    @router.get('/articles/{id}/chat')
    def get(id:str,purpose:str="explain",principal=dep):
        value=checked(repo().get,principal.actor_user_id,id,purpose)
        if value.get('busy'):
            action=repo().action(principal.actor_user_id,id,value['busy'])
            value['action']=action
            if action and action.get('task_id'):
                task=runtime_provider().system_tasks.get(principal.actor_user_id,action['task_id'])
                value['progress']=task.get('message','')
            value['progress_content']=task.get('progress') or {}
        return value

    @router.post('/articles/{id}/chat/actions')
    async def action(id:str,body:chat.Action,principal=dep):
        r=repo();owner=principal.actor_user_id;runtime=runtime_provider()
        checked(r.require,owner,id,body.thread)
        if body.mode=='answer' and not body.question.strip():raise HTTPException(422,'Question is required')
        if body.confirmation_id:
            if body.mode!='answer':raise HTTPException(422,'Search is only allowed for an explicit question')
            checked(chat.confirmed_fast_search,runtime,principal,id,body.thread,body.confirmation_id,session(runtime,principal))
        if body.model:
            catalog=await chat.conversation_models(runtime,principal)
            if body.model not in {m['id'] for m in catalog['models']}:raise HTTPException(409,'Conversation model is unavailable')
        args=body.model_dump(exclude_defaults=True);args.update(thread=body.thread,request_id=body.request_id,mode=body.mode,question=body.question,confirmation_id=body.confirmation_id);old=checked(r.reserve,owner,id,args)
        if old.get('task_id'):return old
        try:
            task=runtime.system_tasks.submit(owner,'ai2apps.intelligence','intelligence.article_chat',
                '文章对话 · '+store().get('articles',owner,id)['title'],{'article_id':id,'request_id':body.request_id},
                dedup_key='article-chat:'+id+':'+body.thread+':'+body.request_id)
            r.attach(owner,id,body.request_id,task['id'])
            return r.action(owner,id,body.request_id)
        except Exception as e:
            r.finish(owner,id,body.request_id,error=str(e)[:500]);raise

    @router.get('/articles/{id}/chat/actions/{request_id}')
    def result(id:str,request_id:str,principal=dep):
        value=checked(repo().action,principal.actor_user_id,id,request_id)
        if not value:raise HTTPException(404,'Article conversation action not found')
        if value.get('task_id'):
            task=runtime_provider().system_tasks.get(principal.actor_user_id,value['task_id'])
            if task['status'] in ('failed','cancelled','partial','interrupted') and value['status']=='queued':
                repo().finish(principal.actor_user_id,id,request_id,error=task.get('message') or task['status'])
                value=repo().action(principal.actor_user_id,id,request_id)
            value['progress']=task.get('message','')
            value['progress_content']=task.get('progress') or {}
        return value

    @router.post('/articles/{id}/chat/reset')
    def reset(id:str,body:chat.Reset,principal=dep):
        r=repo();owner=principal.actor_user_id;previous=checked(r.require,owner,id,body.thread)
        active=r.action(owner,id,previous['busy']) if previous['busy'] else None
        value=checked(r.reset,owner,id,body.thread)
        if active and active.get('task_id'):
            try:runtime_provider().system_tasks.cancel(owner,active['task_id'])
            except ValueError:pass
        return value

    @router.post('/articles/{id}/chat/research-handoff')
    def research_handoff(id:str,body:chat.ResearchHandoff,principal=dep):
        return checked(chat.research_handoff,runtime_provider(),principal,store(),id,body)

    @router.post('/articles/{id}/chat/search')
    def prepare(id:str,body:chat.Search,principal=dep):
        checked(repo().require,principal.actor_user_id,id,body.thread)
        from ai2apps.research import search_preparation as prep
        runtime=runtime_provider();mounted=search_mount(runtime,principal)
        return checked(prep.begin,runtime,principal,mounted,scope=scope(id,body.thread),session_id=session(runtime,principal),
            query=body.query,profile=body.profile,locale=store().get('channels',principal.actor_user_id,store().get('articles',principal.actor_user_id,id)['channel_id']).get('output_language') or 'zh',request_id=body.request_id,fast=True)

    @router.get('/articles/{id}/chat/search/{preparation_id}')
    def prepared(id:str,preparation_id:str,thread:str,principal=dep):
        checked(repo().require,principal.actor_user_id,id,thread)
        from ai2apps.research import search_preparation as prep
        runtime=runtime_provider()
        return checked(prep.view,runtime,principal,search_mount(runtime,principal),preparation_id,scope=scope(id,thread))

    @router.post('/articles/{id}/chat/search/confirm')
    def confirm(id:str,body:chat.Confirm,principal=dep):
        checked(repo().require,principal.actor_user_id,id,body.thread)
        from ai2apps.research import search_preparation as prep
        runtime=runtime_provider();mounted=search_mount(runtime,principal)
        row=checked(prep.owned,runtime,principal,body.preparation_id,scope=scope(id,body.thread),session_id=session(runtime,principal))
        # Fast source is selected by the shared search policy; the client cannot expand it.
        return checked(prep.confirm,runtime,principal,mounted,body.preparation_id,
            {'query':body.query,'sources':[body.source],'profile':row['profile'],'mode':'fast','limit':8,
             'cloud_consent':body.cloud_consent,'cloud_price_version':body.cloud_price_version,'cloud_max_points':body.cloud_max_points,
             'exclude_ads':True,'retain_pages':False,'x_sort':'top','xiaohongshu_sort':'general'},scope=scope(id,body.thread))
