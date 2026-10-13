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

def record(runtime, owner):
    return next((item for item in runtime.secrets.list() if item.metadata.get('search_api_owner') == owner and item.allowed_tools == (TOOL,)), None)

def status(runtime, owner):
    item = record(runtime, owner)
    return {'configured': bool(item)}

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

async def search(runtime, owner, query, limit, scopes=None):
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
