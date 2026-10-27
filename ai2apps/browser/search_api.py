"""Owner-scoped search API credentials and bounded result normalization."""
import fnmatch
import json
import logging
import re
from urllib.parse import urlsplit
import httpx

class _SearchKeyLogFilter(logging.Filter):
    def filter(self, record):
        message=record.getMessage()
        if 'www.googleapis.com/customsearch/' in message or 'serpapi.com/search' in message:
            record.msg=re.sub(r'([?&](?:api_key|key)=)[^&\s"\']+',r'\1[redacted]',message)
            record.args=()
        return True

# httpx logs complete request URLs at INFO; Google/SerpAPI keys are query parameters.
logging.getLogger('httpx').addFilter(_SearchKeyLogFilter())

TOOL = 'web.search.api'
PROVIDERS = {'google', 'serpapi-google', 'serpapi-bing'}

def byok_available(runtime, owner):
    """Only an active core actor may reuse this Installation's official BYOK."""
    if getattr(runtime, 'privacy_mode', False) is True:
        return False
    manager = getattr(runtime, 'model_manager', None)
    if manager is None:
        return False
    from ai2apps.identity import IdentityRepository, RequestPrincipal, IdentityBindingError
    try:
        principal = (RequestPrincipal.legacy_local() if owner == 'local' else
                     IdentityRepository(runtime.database).local_principal_for(owner))
        if not principal.is_core:
            return False
        return any(p['id'] == 'deepseek' and p.get('enabled') and p.get('configured')
                   and str(p.get('base_url', '')).rstrip('/') in
                   ('https://api.deepseek.com', 'https://api.deepseek.com/v1')
                   for p in manager.list_cloud())
    except (ValueError, IdentityBindingError):
        return False

def deepseek_available(runtime, owner):
    from .cloud_search import cached_offer
    return (getattr(runtime,'privacy_mode',False) is not True and
            (byok_available(runtime,owner) or cached_offer(runtime,owner).get('available') is True))

def fast_source(runtime, owner):
    return 'deepseek' if deepseek_available(runtime, owner) else 'fast_api' if record(runtime, owner) else 'google'

def record(runtime, owner):
    return next((item for item in runtime.secrets.list() if item.metadata.get('search_api_owner') == owner and item.allowed_tools == (TOOL,)), None)

def status(runtime, owner):
    item = record(runtime, owner)
    available = deepseek_available(runtime, owner)
    from .cloud_search import cached_offer
    offer=cached_offer(runtime,owner)
    if getattr(runtime,'privacy_mode',False) is True:
        offer={**offer,'available':False,'reason':'SEARCH_PRIVACY_BLOCKED'}
    return {'configured': bool(item) or available, 'deepseek_available': available,
            'fast_source': fast_source(runtime, owner),
            'deepseek_cloud_available':offer.get('available') is True,
            'deepseek_route':'byok' if byok_available(runtime,owner) else 'cloud',
            'cloud_offer':offer,
            'privacy_mode': getattr(runtime, 'privacy_mode', False) is True}

async def deepseek_search(runtime, owner, query, limit, scopes, model_profile):
    from ai2apps.task_llm import effective_profile
    if effective_profile(runtime, model_profile) == 'privacy':
        raise ValueError('DeepSeek search is unavailable in privacy mode / 隐私模式下不可使用 DeepSeek 搜索')
    if not byok_available(runtime, owner):
        raise ValueError('Configure official DeepSeek BYOK; Cloud search is not available yet / 请配置官方 DeepSeek BYOK；Cloud 搜索尚未上线')
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 128:
        raise ValueError('DeepSeek search terms must contain 1–128 characters / DeepSeek 搜索词须为 1–128 个字符')
    endpoint = 'https://api.deepseek.com/v1/tools/search'
    if scopes is not None and not any(fnmatch.fnmatchcase(endpoint, scope) for scope in scopes):
        raise ValueError('Search API endpoint is outside the Agent site scope')
    # Resolve only at execution; credentials never enter declarations, tasks or results.
    key = runtime.model_manager.resolve_credential('ai2apps-cloud:deepseek')
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False, trust_env=False) as client:
            response = await client.post(endpoint, headers={'Authorization': 'Bearer ' + key},
                json={'query': query.strip(), 'count': max(1, min(50, int(limit))), 'need_content': False})
        if response.status_code != 200:
            raise ValueError('DeepSeek search HTTP ' + str(response.status_code) + ' / DeepSeek 搜索请求失败；请检查密钥、余额或限额')
        if len(response.content) > 2_000_000:
            raise ValueError('Search API response is too large')
        rows = response.json()['results']
        if not isinstance(rows, list):
            raise TypeError('Invalid results')
        items = []
        for row in rows[:max(1, min(50, int(limit)))]:
            if not isinstance(row, dict): continue
            url = row.get('url', '')
            if not isinstance(url, str): continue
            parts = urlsplit(url)
            title = str(row.get('title') or '').strip()
            if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or not title: continue
            items.append({'title': title[:500], 'url': url[:8192],
                          'summary': str(row.get('snippet') or row.get('summary') or '')[:2000]})
        return {'provider': 'deepseek', 'transport': 'api', 'items': items, 'query': query}
    except (httpx.HTTPError, TypeError, KeyError, json.JSONDecodeError):
        raise ValueError('DeepSeek search request failed / DeepSeek 搜索请求失败，请检查连接和服务配置') from None

def configure(runtime, owner, provider, key, cx=''):
    if provider not in PROVIDERS or not key.strip() or (provider == 'google' and not cx.strip()):
        raise ValueError('A supported provider, API key and Google engine ID (when applicable) are required')
    value=json.dumps({'provider':provider,'key':key.strip(),'cx':cx.strip()})
    previous=record(runtime,owner)
    # Replace the protected value; provider is derived from it, not a task input.
    if previous:
        runtime.secrets.replace(previous.id,value)
    else:
        runtime.secrets.create(name='Search API '+owner,purpose='User-configured web search',value=value,allowed_tools=(TOOL,),metadata={'search_api_owner':owner})
    return {'configured':True}

async def search(runtime, owner, query, limit, scopes=None, *, provider=None, model_profile='normal',receipt_id='',task_id='',recover=False):
    if provider == 'deepseek':
        from . import cloud_search
        selected=cloud_search.route(runtime,owner,receipt_id) if receipt_id else None
        if selected and selected['route']=='cloud':
            endpoint=str(getattr(runtime.cloud,'base_url','https://coder.ai2apps.com')).rstrip('/')+'/v1/search/deepseek/requests'
            if scopes is not None and not any(fnmatch.fnmatchcase(endpoint,scope) for scope in scopes):
                raise ValueError('Search API endpoint is outside the Agent site scope')
            return await cloud_search.execute(runtime,owner,query,limit,receipt_id,task_id,model_profile,recover=recover)
        if recover:return None
        return await deepseek_search(runtime, owner, query, limit, scopes, model_profile)
    item=record(runtime,owner)
    if not item: raise ValueError('Search API is not configured')
    config=json.loads(runtime.secrets.inject_arguments({'config':item.uri},TOOL).arguments['config'])
    provider=config['provider'];limit=max(1,min(20,int(limit)))
    params={'q':query}
    if provider=='google':
        endpoint='https://www.googleapis.com/customsearch/v1';params.update(key=config['key'],cx=config['cx'],num=min(10,limit))
    else:
        endpoint='https://serpapi.com/search.json';params.update(api_key=config['key'],engine='bing' if provider=='serpapi-bing' else 'google',num=limit,count=limit)
    if scopes is not None and not any(fnmatch.fnmatchcase(endpoint,scope) for scope in scopes):
        raise ValueError('Search API endpoint is outside the Agent site scope')
    try:
        async with httpx.AsyncClient(timeout=20,follow_redirects=False,trust_env=False) as client:
            response=await client.get(endpoint,params=params)
            if response.status_code!=200: raise ValueError('Search API returned HTTP '+str(response.status_code)+'; check key, access and quota')
            if len(response.content)>2_000_000:raise ValueError('Search API response is too large')
            payload=response.json()
        if payload.get('error'):raise ValueError('Search API rejected the request; check key, access and quota')
        rows=payload.get('items' if provider=='google' else 'organic_results',[])
        items=[]
        for row in rows[:limit]:
            url=row.get('link','');parts=urlsplit(url)
            if parts.scheme not in ('https','http') or not parts.hostname or parts.username or parts.password:continue
            title=str(row.get('title','')).strip()
            if title:items.append({'title':title[:500],'url':url,'summary':str(row.get('snippet',''))[:2000]})
        return {'provider':'bing' if provider=='serpapi-bing' else 'google','transport':'api','items':items,'query':query}
    except (httpx.HTTPError,json.JSONDecodeError,TypeError,KeyError):
        # Never return raw HTTP exceptions: their request URLs may contain keys.
        raise ValueError('Search API request failed; check connection and provider configuration') from None
