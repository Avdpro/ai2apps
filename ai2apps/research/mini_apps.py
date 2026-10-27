"""AaAT adapters for installed Search All / Web Reader, using shared Browser Tasks."""
from __future__ import annotations
import asyncio
import hashlib
import json
import time
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, UTC
from urllib.parse import urlsplit
from ai2apps.core import ResourceNotFoundError
from ai2apps.identity import IdentityRepository, RequestPrincipal
from ai2apps.services import ToolProviderError
from ai2apps.services.capability_routing import CapabilityProvider, ProviderUnavailable
from ai2apps.browser.mini_apps import WebAgentMiniAppBroker
from .provider import SafeHttpClient, _source_id

HOST='ai2apps.ai-browser'
SEARCH='ai2apps.search-all'
READER='ai2apps.web-reader'


def search_execution_policy(mounted, capability, mode):
    """Fast search opts out of vision; other callers keep owner/default policy."""
    if mode != 'fast':return {'allow_user_intervention':False,'timeout_seconds':10}
    from ai2apps.agent_builder.execution_policy import combine_minimum, resolve_policy
    entry=next(c for c in mounted.declaration['web_agent']['capabilities'] if c['id']==capability)
    minimum=combine_minimum(mounted.declaration['web_agent'].get('minimum_execution_policy'),entry.get('minimum_execution_policy'))
    minimum=combine_minimum(minimum,entry['source'].get('minimum_execution_policy'))
    requested={'visual_locating':False,'visual_review':'off','allow_user_intervention':False,
        'timeout_seconds':10}
    effective=resolve_policy(requested,minimum)
    if effective['visual_locating'] or effective['visual_review']!='off':
        raise ToolProviderError('Fast search cannot use a capability requiring visual assistance')
    return requested

class WebMiniAppTaskError(ToolProviderError):
    def __init__(self, task):
        self.details = {'task_id':task['id'], 'run_id':task.get('run_id'), 'status':task['status'],
            'failure':task.get('failure') or {}, 'message':task.get('message'),
            'requires_user':bool(task.get('requires_user')), 'assistance_kind':task.get('assistance_kind',''),
            'help_url':'/apps/ai2apps.ai-browser#task='+task['id'] if task.get('requires_user') else ''}
        super().__init__('Browser task '+task['status']+': '+str((task.get('failure') or {}).get('message') or (task.get('failure') or {}).get('code') or task.get('message') or 'unknown')+' (task '+task['id']+')')


def principal_for(runtime, context):
    if not context.session_id or not context.actor_user_id or not context.installation_id:
        raise ToolProviderError('Web Mini-App calls require an owned Session and Installation')
    principal = RequestPrincipal.legacy_local() if context.actor_user_id=='local' else IdentityRepository(runtime.database).local_principal_for(context.actor_user_id)
    if principal.installation_id!=context.installation_id:raise ToolProviderError('Web Mini-App Installation mismatch')
    return principal


async def wait_task(runtime, broker, mounted, principal, task, context, deadline, stop_on_assistance=False):
    """Observe an owned task; search/fetch opt out of every human wait."""
    from ai2apps.browser.tasks import BrowserTaskRepository
    owner=principal.actor_user_id
    seen=None
    try:
        async with runtime.notifications.subscribe() as wake:
            while True:
                task=broker.task_declared(mounted,principal,task['id'])
                state = task['status']
                waiting = state == 'waiting_input'
                # Search/fetch are unattended: never forward an interaction or
                # preserve its child Run. The workflow records this failed read
                # and selects another confirmed candidate instead.
                if stop_on_assistance and state!='completed' and task.get('requires_user'):
                    raise WebMiniAppTaskError({**task,'requires_user':False,
                        'message':'Page skipped: interactive access is required',
                        'failure':{'code':'read_requires_interaction','message':'Page skipped: interactive access is required'}})
                snapshot = {'schema':'ai2apps.task-progress/v1',
                    'state':'waiting' if waiting else 'failed' if state=='interrupted' else state if state in {'queued','completed','failed','cancelled'} else 'running',
                    'stage':state,'task_id':task['id'],'requires_user':False if stop_on_assistance else bool(task.get('requires_user')),
                    'wait_reason':str(task.get('message') or '')[:500] if waiting else '', 'metrics':[]}
                update = task.get('progress_snapshot') or {
                    'text':task.get('name') or mounted.declaration.get('title') or 'Browser task', 'phase':'tool',
                    'content':{'task_progress':snapshot}}
                # Lifecycle and identity come from the task repository, never
                # from an earlier producer snapshot or a presentation callback.
                portable={**update.get('content',{}).get('task_progress',{}),
                    **{k:snapshot[k] for k in ('schema','task_id','state','requires_user','wait_reason')}}
                if state=='completed' and update.get('content',{}).get('task_progress',{}).get('state')=='partial':
                    portable['state']='partial'
                update={**update,'content':{**update.get('content',{}),'task_progress':portable}}
                if waiting and task.get('requires_user'):
                    update['text']=str(task.get('message') or '等待用户协助')[:2000]
                forwarded={**update,'content':{**update.get('content',{}),
                    'app_id':HOST,'mini_app_id':mounted.declaration['id'],'browser_task_id':task['id'],'status':state}}
                if waiting and not stop_on_assistance and task.get('requires_user'):
                    forwarded['content']['reading_assistance']=[WebMiniAppTaskError(task).details]
                if stop_on_assistance:
                    forwarded['content'].pop('reading_assistance',None)
                current=json.dumps(forwarded,sort_keys=True,ensure_ascii=False)
                if current!=seen:
                    await context.report_progress(forwarded['text'], phase=forwarded.get('phase','tool'),
                        progress=forwarded.get('progress'),content=forwarded['content'])
                    seen=current
                if task['status']=='completed':return task
                if task['status'] in {'failed','cancelled','interrupted'}:
                    raise WebMiniAppTaskError({**task,'requires_user':False} if stop_on_assistance else task)
                # Human assistance is a durable wait, not a failed Tool call.
                # Its owner prompt is already forwarded above. Only the task's
                # normal interaction can resume execution; this observer must
                # neither approve it nor submit another operation.
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('Web Mini-App task deadline exceeded: '+task['id'])
                try:await asyncio.wait_for(wake.get(),timeout=min(remaining,2))
                except TimeoutError:pass
    except BaseException:
        # Cancellation/timeout must not leave a private execution loop behind.
        current=BrowserTaskRepository(runtime.database,runtime.events).get(owner,task['id'])
        if current['status'] not in {'completed','failed','cancelled'} and not (current['status']=='waiting_input' and not stop_on_assistance and current.get('requires_user')):
            from ai2apps.browser.task_tree import TaskTreeRepository
            for run_id in TaskTreeRepository(runtime.database,runtime.events).cancel(owner,current['execution_task_id']):
                runtime.agent_runtime.cancel(run_id)
        raise



def merge_search_groups(groups):
    results=[];seen={}
    # limit is per source. Interleave before choosing article-reading candidates,
    # so a slow or first-listed source cannot consume the entire read budget.
    for index in range(max((len(rows) for _,_,rows in groups),default=0)):
        for source,task_id,rows in groups:
            if index>=len(rows):continue
            item=rows[index];url=str(item.get('url',''))
            if not url.startswith(('https://','http://')):continue
            origin={'source':source,'browser_task_id':task_id}
            if url in seen:
                if origin not in seen[url]['sources']:seen[url]['sources'].append(origin)
                continue
            value={'source_id':_source_id(url),'title':str(item.get('title') or url),
                'url':url,'snippet':str(item.get('summary') or item.get('snippet') or ''),
                'search_source':source,'browser_task_id':task_id,'sources':[origin]}
            value.update({key:item[key] for key in ('search_url','redirect_chain','resolution_error') if key in item})
            seen[url]=value;results.append(value)
    return results

class WebMiniAppAdapters:
    def __init__(self,runtime):self.runtime=runtime;self.broker=WebAgentMiniAppBroker(runtime)

    def resolve(self,mini,context):
        principal=principal_for(self.runtime,context)
        try:mounted=self.broker.registered(mini,principal,context.session_id)
        except ResourceNotFoundError as error:raise ProviderUnavailable('Mini-App is not installed: '+mini) from error
        return principal,mounted

    async def search(self,args,context):
        principal,mounted=self.resolve(SEARCH,context)
        if getattr(self,'expected_search_digest',mounted.mount['effective_digest'])!=mounted.mount['effective_digest']:
            raise ToolProviderError('Search Package changed after confirmation; prepare a new search')
        entries={c['id']:c for c in mounted.declaration['web_agent']['capabilities']}
        sources=args.get('sources') or ['google','bing']
        # Sources must be declared read-only query/search entries, not planning,
        # summary, or arbitrary model-supplied WebAgent programs.
        for source in sources:
            entry=entries.get(source)
            if source.startswith('custom_'):
                from ai2apps.browser.custom_search import CustomSearchRepository, search_source
                config=CustomSearchRepository(self.runtime.database).get(principal.actor_user_id,source)
                if config:entries[source]=entry={'source':search_source(config),'title':config['name']}
            if not entry or not any(s.get('operation') in {'extract_list','search.api'} for s in entry['source']['steps']):
                raise ValueError('Not a declared search source: '+source)
        from jsonschema import Draft202012Validator
        prepared={}
        for source in sources:
            schema=entries[source]['source']['inputs']
            parameters={k:deepcopy(v['default']) for k,v in schema.get('properties',{}).items() if 'default' in v}
            parameters.update(query=args['query'],limit=args.get('limit',5))
            if source=='deepseek':parameters['receipt_id']=args.get('confirmation_id','')
            for key in ('exclude_ads','x_sort','xiaohongshu_sort'):
                if key in schema.get('properties',{}) and key in args:parameters[key]=args[key]
            Draft202012Validator(schema).validate(parameters)
            prepared[source]=parameters
        batch=hashlib.sha256(str(context.invocation_id or context.trace_id or repr(args)).encode()).hexdigest()[:32]
        deadline=time.monotonic()+10
        finished=0
        source_states={source:{'source':source,'display_name':entries[source].get('title',source),'status':'queued','count':0} for source in sources}
        if 'deepseek' in sources and args.get('confirmation_id'):
            from ai2apps.browser.cloud_search import route
            if route(self.runtime,principal.actor_user_id,args['confirmation_id'])['route']=='cloud':
                source_states['deepseek']['transport']='cloud'
        early_failures=[]
        async def resolved_rows(source,rows):
            if source == 'google':
                from .search_urls import resolve_google_url, google_redirect, article_first
                async def resolve(item):
                    if not google_redirect(str(item.get('url',''))):return item
                    try:
                        return {**item, **await asyncio.wait_for(asyncio.to_thread(resolve_google_url,item['url']),
                            timeout=max(.01,min(1.5,deadline-time.monotonic())))}
                    except Exception as error:
                        detail={'code':type(error).__name__, 'message':str(error),'phase':'resolve_redirect','url':item['url']}
                        early_failures.append({'source':source, **detail})
                        return {**item,'resolution_error':detail}
                await context.report_progress('正在解析 Google 文章地址 / Resolving Google destinations',phase='search',
                    content={'source_statuses':deepcopy(list(source_states.values())),'results':merge_search_groups([completed_groups[s] for s in sources if s in completed_groups])})
                rows = sorted(await asyncio.gather(*(resolve(item) for item in rows)),key=article_first)
            return rows
        completed_groups={}
        async def one(source):
            nonlocal finished
            parameters=prepared[source]
            task=self.broker.submit_declared(mounted,principal,capability=source,parameters=parameters,profile=args.get('profile','default'),
                request_id='aaat-'+batch+'-'+source,batch_id='aaat-'+batch,batch_size=len(sources),retain_pages=args.get('retain_pages',False),
                execution_policy=search_execution_policy(mounted,source,args.get('mode')))
            source_states[source]['browser_task_id']=task['id']
            async def source_progress(update):
                source_states[source].update(status=update.get('content',{}).get('status','running'),requires_user=bool(update.get('content',{}).get('task_progress',{}).get('requires_user')))
                await context.report_progress(update.get('text','Search All'),phase='search',
                    progress=.05+.2*finished/len(sources),content={**update.get('content',{}),'source_statuses':deepcopy(list(source_states.values())),'results':merge_search_groups([completed_groups[s] for s in sources if s in completed_groups])})
            try:
                observed=await wait_task(self.runtime,self.broker,mounted,principal,task,replace(context,progress_reporter=source_progress),deadline,True)
                raw=observed.get('result') or {}
                rows=await resolved_rows(source,deepcopy(raw.get('items',raw.get('results',[]))))
                observed={**observed,'result':{**raw,'items':rows}}
                completed_groups[source]=(source,task['id'],rows)
                source_states[source].update(status='completed',count=len(rows))
                if raw.get('transport')=='cloud':
                    source_states[source].update(transport='cloud',usage=raw.get('usage',{}))
                return observed
            except BaseException:
                source_states[source]['status']='failed'
                raise
            finally:
                finished+=1
                await context.report_progress(f'搜索来源 {finished}/{len(sources)} · '+source,phase='search',
                    progress=.05+.2*finished/len(sources),content={'completed':finished,'total':len(sources),'search_source':source,'browser_task_id':task['id'],'source_statuses':deepcopy(list(source_states.values())),'results':merge_search_groups([completed_groups[s] for s in sources if s in completed_groups])})
        async def bounded_one(source):
            async with asyncio.timeout(10):
                return await one(source)
        observations=await asyncio.gather(*(bounded_one(source) for source in sources),return_exceptions=True)
        results=[];tasks=[];failures=list(early_failures);groups=[]
        for source,observed in zip(sources,observations):
            if isinstance(observed,BaseException):
                source_states[source]['status']='failed'
                failures.append({'source':source,'message':str(observed)[:500],**getattr(observed,'details',{})});continue
            tasks.append(observed['id']);raw=observed.get('result') or {}
            rows = deepcopy(raw.get('items',raw.get('results',[])))
            groups.append((source,observed['id'],rows))
        results=merge_search_groups(groups)
        if not results:
            error=ToolProviderError('Search All: no usable results. '+'; '.join(str(f.get('source',''))+': '+str(f.get('message','')) for f in failures)[:600])
            error.details={'source_failures':failures}
            raise error
        return {'query':args['query'],'results':results,'items':results,'count':len(results),'sources':sources,
            'source_statuses':list(source_states.values()),'browser_task_ids':tasks,'failures':failures,
            'read_limit':3 if args.get('mode')=='fast' else 5,
            'app_id':HOST,'mini_app_id':SEARCH,'provider_package_id':mounted.mount['app_key'],'untrusted':True}

    async def fetch(self,args,context):
        async with asyncio.timeout(10):
            return await self._fetch(args,context)

    async def _fetch(self,args,context):
        from .search_urls import google_redirect, resolve_google_url
        resolution = await asyncio.to_thread(resolve_google_url,args['url']) if google_redirect(args['url']) else {}
        url=await asyncio.to_thread(SafeHttpClient()._validate_url,resolution.get('url',args['url']))
        principal,mounted=self.resolve(READER,context)
        mounted=deepcopy(mounted)
        entry=next(c for c in mounted.declaration['web_agent']['capabilities'] if c['id']=='article')
        # Narrow the declared public-web reader to this requested public origin.
        from ai2apps.browser.background_executor import scope_allows
        if not scope_allows(url,entry['source']['site_scope']):raise ValueError('URL is outside the installed Web Reader declaration')
        parsed=urlsplit(url);entry['source']['site_scope']=[f'{parsed.scheme}://{parsed.netloc}/**']
        parameters={'url':url}
        if 'max_chars' in entry['source']['inputs']['properties']:parameters['max_chars']=args.get('max_chars',60000)
        key=hashlib.sha256(str(context.invocation_id or context.trace_id or repr(args)).encode()).hexdigest()[:32]
        task=self.broker.submit_declared(mounted,principal,capability='article',parameters=parameters,profile=args.get('profile','default'),request_id='aaat-'+key,
            execution_policy=search_execution_policy(mounted,'article',args.get('mode')))
        observed=await wait_task(self.runtime,self.broker,mounted,principal,task,context,time.monotonic()+10,True)
        raw=observed.get('result') or {}
        text=raw.get('text') or raw.get('content') or raw.get('article',{}).get('text') or ''
        unavailable_titles={'not found','404 not found','page not found','document not found','403 forbidden','access denied','service unavailable'}
        status=raw.get('status_code') or raw.get('http_status')
        if str(raw.get('title','')).strip().lower() in unavailable_titles or (isinstance(status,int) and status>=400):
            raise ToolProviderError('Web Reader page unavailable ('+str(raw.get('title') or status)+'): '+url+'; task '+observed['id'])
        if not isinstance(text,str) or not text.strip():raise ToolProviderError('Web Reader returned no readable article text: '+observed['id'])
        maximum=args.get('max_chars',60000)
        if not scope_allows(raw.get('url') or url,entry['source']['site_scope']):
            raise ToolProviderError('Web Reader result left its validated article origin: '+str(raw.get('url')))
        return {**resolution,'source_id':_source_id(raw.get('url') or url),'url':raw.get('url') or url,'title':raw.get('title') or '',
            'text':text[:maximum],'truncated':len(text)>maximum or bool(raw.get('truncated')),'fetched_at':datetime.now(UTC).isoformat(),
            **{k:raw[k] for k in ('content_kind','content_sections','content_warnings','extraction_method',
                'subtitle_discovery','subtitle_tracks','subtitle_cues','subtitle_text','subtitle_track','subtitle_video_url') if k in raw},
            'browser_task_id':observed['id'],'app_id':HOST,'mini_app_id':READER,'provider_package_id':mounted.mount['app_key'],'untrusted':True}


def install_mini_app_providers(runtime_provider,router):
    from ai2apps.services.aaat import AgentResultPolicy, InvocationPolicyError
    from .citations import citation_instruction, bind_final, report_preview, READ_TOOLS
    router.register_result_policy(AgentResultPolicy('citation_binding',citation_instruction,bind_final,report_preview,tuple(sorted(READ_TOOLS))))
    async def confirmed_invocation(arguments,context):
        if not arguments.get('confirmation_id'):return False
        from .search_preparation import require_confirmation
        from types import SimpleNamespace
        try:
            require_confirmation(SimpleNamespace(database=runtime_provider().database),principal_for(runtime_provider(),context),
                arguments,session_id=context.session_id,run_id=context.trace_id)
        except ToolProviderError as error:
            raise InvocationPolicyError('search_confirmation_changed',str(error)+'; retry with only the original confirmation_id and provider. Do not reopen or alter the confirmed form.') from error
        return True
    for mini,capability,operation in [(SEARCH,'web.search','search'),(READER,'web.fetch','fetch')]:
        async def handler(args,context,operation=operation):
            if operation=='search':
                from .search_workflow import invoke
                return await invoke(runtime_provider(),args,context)
            return await getattr(WebMiniAppAdapters(runtime_provider()),operation)(args,context)
        async def describe(principal, model=None, mini=mini):
            runtime=runtime_provider()
            try:_,declaration=runtime.extension_manager._studio_mini_app_definition(HOST,mini,principal)
            except ResourceNotFoundError:
                return {'effective_schema':{'type':'object','properties':{},'additionalProperties':True},'selection_required':False,'warnings':['Mini-App not installed; execution will use an available Provider.']}
            if mini==SEARCH:
                from ai2apps.browser.search_api import deepseek_available,byok_available
                if not byok_available(runtime,principal.actor_user_id):
                    from ai2apps.browser.cloud_search import refresh_offer
                    await refresh_offer(runtime,principal.actor_user_id)
                sources=[entry['id'] for entry in declaration['web_agent']['capabilities'] if any(step.get('operation') in {'extract_list','search.api'} for step in entry['source']['steps'])
                         and (entry['id']!='deepseek' or deepseek_available(runtime,principal.actor_user_id))]
                properties={'query':{'type':'string','minLength':1,'maxLength':1024},'limit':{'type':'integer','minimum':1,'maximum':10,'default':5},
                    'sources':{'type':'array','items':{'type':'string','enum':sources},'minItems':1,'maxItems':4,'uniqueItems':True,'default':['google','bing']}}
                required=['query']
            else:
                properties={'url':{'type':'string','minLength':1},'max_chars':{'type':'integer','minimum':1000,'maximum':100000,'default':60000}}
                required=['url']
            properties['profile']={'type':'string','default':'default'}
            from ai2apps.agents.parameter_forms import schema_fields, present_fields
            contract={'type':'object','properties':properties,'required':required,'additionalProperties':False}
            labels={k:{'zh':z,'en':e} for k,z,e in [('query','搜索词','Search terms'),('limit','结果数量','Result limit'),('sources','搜索源','Sources'),('url','网页链接','Page URL'),('max_chars','最大字符数','Maximum characters'),('profile','浏览器分身','Browser profile')]}
            return {'effective_schema':contract,'fields':present_fields(schema_fields(contract),labels),'selection_required':mini==SEARCH}
        router.register(CapabilityProvider(mini+'.'+operation,capability,HOST,handler,mini_app_id=mini,priority=50,describe=describe,
            invocation_policy=confirmed_invocation if mini==SEARCH else None,
            agent_context=({'schema':'ai2apps.aaat-declaration/v1','instructions':[
                'Search All returns a completed body-based report with validated citations. Preserve limitations and use body-based findings; snippets and video titles are not article evidence.',
                'This is cross-source or topic search, not an account timeline viewer. For a named social account and its recent posts, discover the dedicated social account capability first; account resolution and confirmation belong to that owner.',
                'If the result preview contains a report, use that report without rereading raw bodies unless additional evidence is needed.',
                'Call confirmed searches with their exact returned arguments or only confirmation_id and provider. Never modify confirmed parameters or collect the same confirmation again.']}
                if mini==SEARCH else None),
            display_name={'zh':'一搜到底' if mini==SEARCH else '网页阅读器','en':'Search All' if mini==SEARCH else 'Web Reader'},
            summary=({'zh':'通过 AI 浏览器并行搜索已安装声明中的来源，合并结果并保留来源和任务记录。',
                      'en':'Search declared sources through AI Browser, merging results with source and task provenance.'}
                     if mini==SEARCH else
                     {'zh':'通过 AI 浏览器读取公开网页正文，保留来源网址和任务记录。',
                      'en':'Read public webpage text through AI Browser with source URL and task provenance.'})))
