"""Owner-scoped search preparation and explicit, immutable confirmation receipts."""
from copy import deepcopy
from datetime import datetime, UTC
import hashlib
import json
import uuid
from jsonschema import Draft202012Validator
from ai2apps.services import ToolProviderError
from ai2apps.browser.custom_search import CustomSearchRepository
from ai2apps.browser.search_api import fast_source, deepseek_available
from ai2apps.browser.profiles import BrowserProfileRepository
from ai2apps.browser.mini_apps import WebAgentMiniAppBroker

MINI='ai2apps.search-all'

def initialize(database):
    from ai2apps.browser.cloud_search import initialize as cloud_initialize
    cloud_initialize(database)
    with database.transaction() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS search_preparations (
            id TEXT PRIMARY KEY, actor TEXT NOT NULL, installation TEXT NOT NULL,
            scope TEXT NOT NULL, session_id TEXT NOT NULL, origin_run TEXT NOT NULL,
            profile TEXT NOT NULL, original_query TEXT NOT NULL, locale TEXT NOT NULL,
            task_id TEXT NOT NULL, digest TEXT NOT NULL, confirmed_json TEXT,
            created_at TEXT NOT NULL, UNIQUE(actor,installation,scope,id))''')

def choices(runtime,principal,mounted):
    entries=mounted.declaration['web_agent']['capabilities']
    result=[{'id':c['id'],'name':c.get('title') or c['id']} for c in entries
        if any(s.get('operation')=='extract_list' for s in c['source']['steps'])]
    if deepseek_available(runtime, principal.actor_user_id) and any(c['id']=='deepseek' for c in entries):
        result.append({'id':'deepseek','name':'DeepSeek'})
    result.extend({'id':c['id'],'name':c['name']} for c in CustomSearchRepository(runtime.database).list(principal.actor_user_id))
    return result

def owned(runtime,principal,identifier,*,scope=None,session_id=None):
    with runtime.database.transaction() as db:
        row=db.execute('SELECT * FROM search_preparations WHERE id=?',(identifier,)).fetchone()
    if not row or (row['actor'],row['installation'])!=(principal.actor_user_id,principal.installation_id):
        raise ValueError('Search preparation not found')
    if scope is not None and row['scope']!=scope:raise ValueError('Search preparation scope changed')
    if session_id is not None and row['session_id']!=session_id:raise ValueError('Search preparation Session changed')
    return dict(row)

def begin(runtime,principal,mounted,*,scope,session_id,query,profile='default',locale='zh',request_id,origin_run='',fast=False):
    if mounted.declaration['id']!=MINI:raise ValueError('Search preparation requires Search All')
    if not isinstance(query,str) or not 1<=len(query.strip())<=1024:raise ValueError('Search query must contain 1–1024 characters')
    if not isinstance(locale,str) or len(locale)>32:raise ValueError('Invalid search locale')
    BrowserProfileRepository(runtime.database).require(principal.actor_user_id,profile)
    identifier='sp_'+hashlib.sha256((principal.actor_user_id+'\0'+principal.installation_id+'\0'+scope+'\0'+request_id).encode()).hexdigest()[:40]
    with runtime.database.transaction() as db:old=db.execute('SELECT * FROM search_preparations WHERE id=?',(identifier,)).fetchone()
    if old:
        if (not old['task_id'])!=fast:raise ValueError('Search preparation mode changed; use a new request ID')
        if (old['original_query'],old['profile'],old['session_id'],old['origin_run'],old['locale'])!=(query.strip(),profile,session_id,origin_run,locale):
            raise ValueError('Search preparation request changed; use a new request ID')
        return view(runtime,principal,mounted,identifier,scope=scope)
    # The plan is a shared durable AI-only Task, never a source-search submission.
    task=({'id':''} if fast else WebAgentMiniAppBroker(runtime).submit_declared(mounted,principal,capability='plan',
        parameters={'query':query.strip(),'locale':locale},profile=profile,request_id=identifier))
    with runtime.database.transaction() as db:
        db.execute('INSERT OR IGNORE INTO search_preparations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (identifier,principal.actor_user_id,principal.installation_id,scope,session_id,origin_run,profile,
             query.strip(),locale,task['id'],mounted.mount['effective_digest'],None,datetime.now(UTC).isoformat()))
    return view(runtime,principal,mounted,identifier,scope=scope)

def view(runtime,principal,mounted,identifier,*,scope=None):
    row=owned(runtime,principal,identifier,scope=scope)
    if mounted.mount['effective_digest']!=row['digest']:raise ValueError('Search Package changed; prepare again')
    task=(WebAgentMiniAppBroker(runtime).task_declared(mounted,principal,row['task_id']) if row['task_id'] else
        {'id':'','status':'completed','result':{'optimized_query':row['original_query'],'sources':[fast_source(runtime,principal.actor_user_id)],
          'limit':5,'x_sort':'top','xiaohongshu_sort':'general','reason':'Fast search / 快速搜索：直接使用输入的搜索词，不调用 LLM 优化。'}})
    available=choices(runtime,principal,mounted)
    fast=fast_source(runtime,principal.actor_user_id)
    result={'id':identifier,'task_id':task['id'],'status':task['status'],'original_query':row['original_query'],
        'profile':row['profile'],'choices':available,'fast_source':fast,'confirmed':bool(row['confirmed_json'])}
    from ai2apps.browser.search_api import status
    result['cloud_offer']=status(runtime,principal.actor_user_id).get('cloud_offer',{})
    if task['status']=='completed':
        plan=deepcopy(task.get('result') or {})
        ids={c['id'] for c in available}
        if not row['task_id']:ids.add('fast_api')
        # Configuration may change while planning. Never preserve an unavailable API choice.
        if isinstance(plan.get('sources'),list) and 'deepseek' not in ids:
            plan['sources']=[s for s in plan['sources'] if s!='deepseek']
            if not plan['sources']:plan['sources']=['google']
        if (not isinstance(plan.get('optimized_query'),str) or not 1<=len(plan['optimized_query'].strip())<=1024
            or not isinstance(plan.get('sources'),list) or not 1<=len(plan['sources'])<=3
            or len(set(plan['sources']))!=len(plan['sources']) or not set(plan['sources'])<=ids
            or plan.get('x_sort') not in ('top','latest') or plan.get('xiaohongshu_sort') not in ('general','latest','likes')
            or type(plan.get('limit')) is not int or not 3<=plan['limit']<=10
            or not isinstance(plan.get('reason'),str) or len(plan['reason'])>400):
            raise ValueError('Invalid search preparation result')
        result.update(query=plan['optimized_query'].strip(),sources=plan['sources'],limit=plan['limit'],
            x_sort=plan['x_sort'],xiaohongshu_sort=plan['xiaohongshu_sort'],reason=plan['reason'])
    elif task['status'] in ('failed','cancelled','interrupted'):
        result['message']='Search preparation '+task['status']
    return result

def schema(available):
    return {'type':'object','properties':{
        'query':{'type':'string','minLength':1,'maxLength':1024},
        'mode':{'type':'string','enum':['fast','preferred','custom'],'default':'preferred'},
        'sources':{'type':'array','items':{'type':'string','enum':[c['id'] for c in available]},'minItems':1,'maxItems':10,'uniqueItems':True},
        'limit':{'type':'integer','minimum':1,'maximum':10,'default':5},
        'profile':{'type':'string','default':'default'},'preparation_id':{'type':'string','minLength':1},
        'x_sort':{'type':'string','enum':['top','latest'],'default':'top'},
        'xiaohongshu_sort':{'type':'string','enum':['general','latest','likes'],'default':'general'},
        'exclude_ads':{'type':'boolean','default':True},'retain_pages':{'type':'boolean','default':False},
        'cloud_consent':{'type':'boolean','default':False},
        'cloud_price_version':{'type':'string','maxLength':100,'default':''},
        'cloud_max_points':{'type':'string','maxLength':20,'default':''}},
        'required':['query','mode','sources','preparation_id','profile','limit'],'additionalProperties':False}

def execution_preparation(runtime,principal,mounted,identifier,request_id,*,scope):
    """A new user search gets a new receipt, while transport retries reuse it.

    Reuse the completed planning Task, never rewrite an earlier confirmation.
    Agent-owned confirmations must continue through their original Run guards.
    """
    row=owned(runtime,principal,identifier,scope=scope)
    if row['origin_run']:raise ValueError('Agent search confirmations cannot be copied')
    if not isinstance(request_id,str) or not 1<=len(request_id)<=100:raise ValueError('Invalid search request ID')
    prepared=view(runtime,principal,mounted,identifier,scope=scope)
    if prepared['status']!='completed':raise ValueError('Search preparation is not complete')
    child='sp_'+hashlib.sha256((identifier+'\0execution\0'+request_id).encode()).hexdigest()[:40]
    with runtime.database.transaction(write=True) as db:
        existing=db.execute('SELECT id FROM search_preparations WHERE id=?',(child,)).fetchone()
        if not existing:
            for key in ('confirmed-search:','search-summary:'):
                active=db.execute('SELECT status FROM agent_runs WHERE session_id=? AND idempotency_key=?',
                    (row['session_id'],key+identifier)).fetchone()
                if active and active['status'] not in ('completed','failed','cancelled','expired'):
                    raise ValueError('Previous search is still active / 上一次搜索仍在执行')
            db.execute('INSERT INTO search_preparations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (child,row['actor'],row['installation'],row['scope'],row['session_id'],'',row['profile'],
                 row['original_query'],row['locale'],row['task_id'],row['digest'],None,datetime.now(UTC).isoformat()))
    owned(runtime,principal,child,scope=scope,session_id=row['session_id'])
    return child

def confirm(runtime,principal,mounted,identifier,values,*,scope):
    row=owned(runtime,principal,identifier,scope=scope)
    prepared=view(runtime,principal,mounted,identifier,scope=scope)
    if prepared['status']!='completed':raise ValueError('Search preparation is not complete')
    payload=deepcopy(values)
    payload['preparation_id']=identifier
    if payload.get('profile')!=row['profile']:raise ValueError('Browser Profile changed; prepare again')
    available=prepared['choices']
    if payload.get('mode')=='fast':
        available=[*available,{'id':'fast_api','name':'Search API'}]
        if payload.get('sources')!=[prepared['fast_source']]:raise ValueError('Fast search source changed; review again')
    Draft202012Validator(schema(available)).validate(payload)
    if not payload['query'].strip():raise ValueError('Search query is empty')
    if 'deepseek' in payload['sources'] and len(payload['query'].strip())>128:
        raise ValueError('DeepSeek search terms must contain at most 128 characters / DeepSeek 搜索词最多 128 个字符')
    encoded=json.dumps(payload,sort_keys=True,ensure_ascii=False)
    with runtime.database.transaction(write=True) as db:
        current=db.execute('SELECT confirmed_json FROM search_preparations WHERE id=?',(identifier,)).fetchone()
        if current['confirmed_json'] and current['confirmed_json']!=encoded:raise ValueError('Confirmed search cannot be changed; prepare a new search')
        if not current['confirmed_json']:
            from ai2apps.browser.cloud_search import pin
            pin(runtime,principal,identifier,payload,db)
        db.execute('UPDATE search_preparations SET confirmed_json=? WHERE id=?',(encoded,identifier))
    return {**payload,'confirmation_id':identifier}

def require_confirmation(runtime,principal,arguments,*,session_id,run_id=None):
    identifier=arguments.get('confirmation_id')
    if not identifier:raise ToolProviderError('Collect and confirm search parameters before searching')
    try:row=owned(runtime,principal,identifier,session_id=session_id)
    except ValueError as error:raise ToolProviderError(str(error)) from error
    if row['origin_run'] and run_id not in (row['origin_run'],None):raise ToolProviderError('Search confirmation belongs to another Run')
    if not row['confirmed_json']:raise ToolProviderError('User has not clicked Search')
    confirmed=json.loads(row['confirmed_json'])
    for key,value in arguments.items():
        if key not in ('confirmation_id','provider') and (key not in confirmed or confirmed[key]!=value):
            raise ToolProviderError('Search arguments changed after user confirmation')
    return confirmed,row
