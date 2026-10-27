"""DeepSeek Search owner adapter: Device transport, priced receipts and recovery.

Cloud protocol 1.78.0. No credential, actor override or arbitrary endpoint is
accepted from a Mini-App, model or task parameter.
"""
import asyncio
import hashlib
import json
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
import httpx
from ai2apps.identity import IdentityRepository, RequestPrincipal
from ai2apps.task_llm import effective_profile

ROOT='/v1/search/deepseek'
PENDING={'reserved','in_progress','indeterminate'}
TERMINAL={'completed','failed','cancelled'}
_poll_delay=asyncio.sleep

class CloudSearchError(ValueError):
    pass

def initialize(database):
    with database.transaction(write=True) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS deepseek_search_routes (
            receipt_id TEXT PRIMARY KEY, owner TEXT NOT NULL, installation TEXT NOT NULL,
            route TEXT NOT NULL, price_version TEXT NOT NULL, points TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS deepseek_cloud_search_requests (
            task_id TEXT PRIMARY KEY, owner TEXT NOT NULL, installation TEXT NOT NULL,
            receipt_id TEXT NOT NULL UNIQUE, request_id TEXT NOT NULL UNIQUE,
            query TEXT NOT NULL, count INTEGER NOT NULL, price_version TEXT NOT NULL,
            state TEXT NOT NULL, response_json TEXT, updated_at REAL NOT NULL)''')

def principal_for(runtime,owner):
    return RequestPrincipal.legacy_local() if owner=='local' else IdentityRepository(runtime.database).local_principal_for(owner)

def privacy_guard(runtime,profile='normal'):
    if effective_profile(runtime,profile)=='privacy':
        raise CloudSearchError('SEARCH_PRIVACY_BLOCKED / 隐私模式下不可使用 DeepSeek 外部搜索')
    if getattr(runtime,'offline_mode',False) is True:
        raise CloudSearchError('SEARCH_UNAVAILABLE / 离线模式下不可使用 Cloud 搜索')

def cached_offer(runtime,owner):
    entry=getattr(runtime,'_deepseek_search_offers',{}).get(owner)
    return dict(entry[1]) if entry and time.monotonic()-entry[0]<60 else {'available':False,'reason':'not_probed'}

async def call(runtime,owner,method,path,body=None):
    principal=principal_for(runtime,owner)
    try:headers=runtime.cloud_ai_authorization_headers(principal)
    except Exception:raise CloudSearchError('SEARCH_INSTALLATION_REQUIRED') from None
    if not headers.get('Authorization','').startswith('Device '):
        raise CloudSearchError('SEARCH_INSTALLATION_REQUIRED / 请登录并绑定 Cloud Installation')
    response=await runtime.cloud.request(method,path,json=body,headers=headers)
    try:
        if len(response.content)>2_000_000:raise CloudSearchError('SEARCH_INVALID_RESPONSE')
        try:payload=response.json()
        except (ValueError,TypeError):raise CloudSearchError('SEARCH_INVALID_RESPONSE') from None
        if response.status_code not in (200,202):
            error=payload.get('error',{}) if isinstance(payload,dict) else {}
            code=error.get('code') if isinstance(error,dict) else None
            # Only bounded protocol identifiers; never return raw provider/server exceptions.
            code=code if isinstance(code,str) and code.isascii() and len(code)<100 and all(c.isalnum() or c=='_' for c in code) else 'SEARCH_HTTP_'+str(response.status_code)
            raise CloudSearchError(code)
        if not isinstance(payload,dict):raise CloudSearchError('SEARCH_INVALID_RESPONSE')
        return payload
    finally:await response.aclose()

async def refresh_offer(runtime,owner):
    result={'available':False,'reason':'unavailable'}
    try:
        privacy_guard(runtime)
        result=await asyncio.wait_for(call(runtime,owner,'GET',ROOT+'/capabilities'),15)
        price=str(result['points_per_search'])
        if (result.get('provider')!='deepseek' or result.get('transport')!='cloud'
            or not isinstance(result.get('price_version'),str) or not result['price_version']
            or len(result['price_version'])>80 or not price.isascii() or not price.isdigit() or int(price)<1
            or type(result.get('available')) is not bool or result.get('max_query_chars')!=128 or result.get('max_results')!=50
            or result.get('privacy_mode_allowed') is not False):raise CloudSearchError('SEARCH_INVALID_RESPONSE')
        result={k:result[k] for k in ('available','reason','price_version','points_per_search','max_query_chars','max_results') if k in result}
        result['points_per_search']=str(result['points_per_search'])
    except asyncio.CancelledError:raise
    except Exception as error:
        result={'available':False,'reason':str(error) if isinstance(error,CloudSearchError) else 'SEARCH_UNAVAILABLE'}
    if not hasattr(runtime,'_deepseek_search_offers'):runtime._deepseek_search_offers={}
    runtime._deepseek_search_offers[owner]=(time.monotonic(),result)
    return dict(result)

def route(runtime,owner,receipt_id):
    initialize(runtime.database)
    principal=principal_for(runtime,owner)
    with runtime.database.transaction() as db:
        row=db.execute('SELECT * FROM deepseek_search_routes WHERE receipt_id=?',(receipt_id,)).fetchone()
    if not row or (row['owner'],row['installation'])!=(owner,principal.installation_id):
        raise CloudSearchError('SEARCH_CONFIRMATION_REQUIRED / 请先确认搜索及费用')
    return dict(row)

def pin(runtime,principal,receipt_id,payload,db):
    """Called within the same transaction as immutable user confirmation."""
    if 'deepseek' not in payload['sources']:return
    from .search_api import byok_available
    privacy_guard(runtime)
    if byok_available(runtime,principal.actor_user_id):
        selected,version,points='byok','','0'
    else:
        offer=cached_offer(runtime,principal.actor_user_id)
        if not offer.get('available'):raise CloudSearchError('SEARCH_UNAVAILABLE / Cloud 搜索当前不可用')
        if (payload.get('cloud_consent') is not True or payload.get('cloud_price_version')!=offer['price_version']
            or payload.get('cloud_max_points')!=offer['points_per_search']):
            raise CloudSearchError('SEARCH_PRICE_CONFIRMATION_REQUIRED / 请确认当前 Cloud 搜索费用')
        selected,version,points='cloud',offer['price_version'],offer['points_per_search']
    existing=db.execute('SELECT * FROM deepseek_search_routes WHERE receipt_id=?',(receipt_id,)).fetchone()
    values=(receipt_id,principal.actor_user_id,principal.installation_id,selected,version,points)
    if existing:
        # An accepted route must not change when configuration later changes.
        return
    db.execute('INSERT INTO deepseek_search_routes VALUES (?,?,?,?,?,?)',values)

def owned_request(runtime,owner,task_id):
    initialize(runtime.database)
    principal=principal_for(runtime,owner)
    with runtime.database.transaction() as db:
        row=db.execute('SELECT * FROM deepseek_cloud_search_requests WHERE task_id=?',(task_id,)).fetchone()
    if not row or (row['owner'],row['installation'])!=(owner,principal.installation_id):raise CloudSearchError('SEARCH_REQUEST_NOT_FOUND')
    return dict(row)

def save(runtime,task_id,state,payload=None):
    with runtime.database.transaction(write=True) as db:
        db.execute('UPDATE deepseek_cloud_search_requests SET state=?,response_json=?,updated_at=? WHERE task_id=?',
                   (state,json.dumps(payload,ensure_ascii=False) if payload is not None else None,time.time(),task_id))

def normalize(payload,row):
    if payload.get('provider')!='deepseek' or payload.get('transport')!='cloud' or payload.get('status') not in PENDING|TERMINAL:
        raise CloudSearchError('SEARCH_INVALID_RESPONSE')
    usage=payload.get('usage') or {}
    if usage.get('request_id')!=row['request_id'] or usage.get('price_version')!=row['price_version']:
        raise CloudSearchError('SEARCH_INVALID_RESPONSE')
    try:
        raw=usage['points_charged']
        if not isinstance(raw,str) or not raw.isascii() or not raw.isdigit():raise InvalidOperation
        charged=Decimal(raw)
        if not charged.is_finite() or charged<0:raise InvalidOperation
    except (InvalidOperation,KeyError,TypeError):raise CloudSearchError('SEARCH_INVALID_RESPONSE') from None
    selected=Decimal(row.get('max_points','1'))
    if charged>selected:raise CloudSearchError('SEARCH_INVALID_BILLING')
    items=payload.get('items',[])
    if not isinstance(items,list) or len(items)>row['count']:raise CloudSearchError('SEARCH_INVALID_RESPONSE')
    if payload['status']=='completed' and not items and (charged!=0 or usage.get('billing_status')!='released'):
        raise CloudSearchError('SEARCH_INVALID_BILLING')
    clean=[]
    for item in items:
        if not isinstance(item,dict):raise CloudSearchError('SEARCH_INVALID_RESPONSE')
        url=item.get('url','');parts=urlsplit(url)
        if parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.password:continue
        clean.append({'title':str(item.get('title',''))[:500],'url':url[:8192],'summary':str(item.get('summary',''))[:2000]})
    return {'provider':'deepseek','transport':'cloud','status':payload['status'],'items':clean,
        'usage':{k:usage[k] for k in ('request_id','price_version','points_charged','billing_status') if k in usage},
        'error_code':str(payload.get('error_code') or '')[:100]}

async def observe(runtime,owner,task_id,*,action='GET'):
    row=owned_request(runtime,owner,task_id)
    privacy_guard(runtime)
    path=ROOT+'/requests/'+row['request_id']
    if action=='cancel':method,path='POST',path+'/cancel'
    elif action=='delete':method,path='DELETE',path+'/result'
    else:method='GET'
    payload=await asyncio.wait_for(call(runtime,owner,method,path),20)
    if action=='delete':
        previous=json.loads(row['response_json'] or '{}')
        result={'status':'deleted','request_id':row['request_id'],'usage':previous.get('usage',{})}
        save(runtime,task_id,'deleted',result);return result
    row['max_points']=route(runtime,owner,row['receipt_id'])['points']
    result=normalize(payload,row);save(runtime,task_id,result['status'],result)
    return result

async def _execute(runtime,owner,query,count,receipt_id,task_id,profile='normal',*,recover=False):
    privacy_guard(runtime,profile)
    selected=route(runtime,owner,receipt_id)
    if selected['route']!='cloud':raise CloudSearchError('SEARCH_ROUTE_CHANGED')
    principal=principal_for(runtime,owner)
    with runtime.database.transaction() as db:
        confirmation=db.execute('SELECT confirmed_json FROM search_preparations WHERE id=?',(receipt_id,)).fetchone()
    approved=json.loads(confirmation['confirmed_json'] or '{}') if confirmation else {}
    if (approved.get('query'),approved.get('limit'))!=(query,count) or 'deepseek' not in approved.get('sources',[]):
        raise CloudSearchError('SEARCH_CONFIRMATION_CHANGED')
    if not isinstance(query,str) or not 1<=len(query.strip())<=128 or not 1<=count<=50:
        raise CloudSearchError('INVALID_SEARCH_REQUEST')
    initialize(runtime.database)
    principal=principal_for(runtime,owner)
    request_id='search-'+hashlib.sha256((principal.installation_id+'\0'+owner+'\0'+receipt_id).encode()).hexdigest()[:48]
    with runtime.database.transaction(write=True) as db:
        row=db.execute('SELECT * FROM deepseek_cloud_search_requests WHERE receipt_id=?',(receipt_id,)).fetchone()
        if row is None:
            if recover:return None
            db.execute('INSERT INTO deepseek_cloud_search_requests VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (task_id,owner,principal.installation_id,receipt_id,request_id,query,count,selected['price_version'],'prepared',None,time.time()))
        else:task_id=row['task_id']
    row=owned_request(runtime,owner,task_id)
    row['max_points']=selected['points']
    if (row['query'],row['count'],row['receipt_id'])!=(query,count,receipt_id):raise CloudSearchError('SEARCH_IDEMPOTENCY_CONFLICT')
    if row['response_json'] and row['state'] in TERMINAL:
        result=json.loads(row['response_json'])
        if 'status' not in result:raise CloudSearchError(result.get('error_code') or 'SEARCH_FAILED')
    else:
        result=None
        if row['state']=='prepared' and not recover:
            # Fresh capability/price check before committing the one allowed POST.
            offer=await refresh_offer(runtime,owner)
            privacy_guard(runtime,profile)
            if not offer.get('available'):raise CloudSearchError('SEARCH_UNAVAILABLE')
            if (offer['price_version'],offer['points_per_search'])!=(selected['price_version'],selected['points']):raise CloudSearchError('SEARCH_PRICE_CHANGED')
            with runtime.database.transaction(write=True) as db:
                claimed=db.execute("UPDATE deepseek_cloud_search_requests SET state='submitting',updated_at=? WHERE task_id=? AND state='prepared'",(time.time(),task_id)).rowcount
            if claimed:
                try:
                    payload=await asyncio.wait_for(call(runtime,owner,'POST',ROOT+'/requests',{
                        'query':query,'count':count,'request_id':request_id,'price_version':selected['price_version'],'privacy_mode':False}),35)
                    result=normalize(payload,row);save(runtime,task_id,result['status'],result)
                except asyncio.CancelledError:raise
                except CloudSearchError as error:
                    if str(error) not in ('SEARCH_RESULT_PENDING','SEARCH_IN_PROGRESS','AI_ACCOUNT_REQUIRES_RECONCILIATION'):
                        save(runtime,task_id,'failed',{'error_code':str(error)})
                        raise
                except (httpx.HTTPError,TimeoutError):
                    save(runtime,task_id,'indeterminate')
        deadline=time.monotonic()+210
        while result is None or result['status'] in PENDING:
            privacy_guard(runtime,profile)
            if time.monotonic()>deadline:raise CloudSearchError('SEARCH_RESULT_PENDING / 请求仍在结算，请回读原请求')
            await _poll_delay(2)
            try:result=await observe(runtime,owner,task_id)
            except (httpx.HTTPError,TimeoutError):continue
    if result['status']!='completed':raise CloudSearchError(result.get('error_code') or 'SEARCH_'+result['status'].upper())
    return {**result,'query':query}

async def execute(runtime,owner,query,count,receipt_id,task_id,profile='normal',*,recover=False):
    try:return await _execute(runtime,owner,query,count,receipt_id,task_id,profile,recover=recover)
    except asyncio.CancelledError:
        try:
            initialize(runtime.database)
            with runtime.database.transaction() as db:
                row=db.execute('SELECT task_id FROM deepseek_cloud_search_requests WHERE receipt_id=?',(receipt_id,)).fetchone()
            if row:await asyncio.shield(observe(runtime,owner,row['task_id'],action='cancel'))
        except Exception:pass
        raise
