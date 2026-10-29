"""Search All's shared preparation inside the durable Agent parameter form."""

FORM_LABELS = {'query': {'zh': '搜索词', 'en': 'Search terms'}, 'mode': {'zh': '搜索模式', 'en': 'Search mode'}, 'sources': {'zh': '搜索源', 'en': 'Sources'}, 'limit': {'zh': '每源结果数', 'en': 'Results per source'}, 'profile': {'zh': '浏览器分身', 'en': 'Browser profile'}, 'exclude_ads': {'zh': '剔除广告', 'en': 'Exclude ads'}, 'x_sort': {'zh': 'X 排序', 'en': 'X order'}, 'xiaohongshu_sort': {'zh': '小红书排序', 'en': 'Xiaohongshu order'}, 'retain_pages': {'zh': '完成后保留页面', 'en': 'Keep pages after completion'}, 'locale': {'zh': '输出语言', 'en': 'Output language'}}
from dataclasses import replace
from fastapi import HTTPException
from jsonschema import ValidationError
from ai2apps.agents.parameter_forms import FORMS, schema_fields
from ai2apps.browser.mini_apps import WebAgentMiniAppBroker
from ai2apps.browser.profiles import BrowserProfileRepository
from . import search_preparation as prep

PROVIDER='ai2apps.search-all.search'

def mounted(runtime,principal,item,session_id):
    return WebAgentMiniAppBroker(runtime).registered(prep.MINI,principal,session_id)

async def describe(runtime,principal,form,values,item):
    from ai2apps.browser.search_api import status,byok_available
    if not byok_available(runtime,principal.actor_user_id):
        from ai2apps.browser.cloud_search import refresh_offer
        await refresh_offer(runtime,principal.actor_user_id)
    if form.key in runtime.app_capability_router.disabled(principal.actor_user_id,principal.installation_id):raise HTTPException(409,'Provider disabled')
    from ai2apps.api.ownership import authorize_agent_run
    # Interaction ownership is checked by the outer parameter API.
    with runtime.database.transaction() as db:
        row=db.execute('SELECT run_id FROM agent_interactions WHERE id=?',(item.id,)).fetchone()
    run=runtime.agents.get_run(row['run_id'])
    mini=mounted(runtime,principal,item,run.session_id)
    available=prep.choices(runtime,principal,mini)
    schema=prep.schema(available+[{'id':'fast_api','name':'Search API'}])
    schema['properties']['mode']['default']='fast'
    schema['properties']['preparation_ready']={'type':'boolean'}
    fields=[f for f in schema_fields(schema) if f['key'] not in ('preparation_id','preparation_ready','cloud_price_version','cloud_max_points')]
    for field in fields:
        field['label']=FORM_LABELS.get(field['key'],field['key'])
        if field['key']=='cloud_consent':
            points=status(runtime,principal.actor_user_id).get('cloud_offer',{}).get('points_per_search','1')
            field['label']={'zh':f'允许 DeepSeek Cloud 搜索，成功非空每次最多 {points} Point；失败、超时或空结果不收费。BYOK 优先，不自动切换付费路径。',
                            'en':f'Authorize DeepSeek Cloud search: up to {points} Point per successful non-empty search; failures, timeouts and empty results are free. BYOK is preferred; no automatic paid fallback.'}
        if field['key']=='mode':field['options']=[{'value':k,'label':v} for k,v in [('fast',{'zh':'快速','en':'Fast'}),('preferred',{'zh':'优选','en':'Preferred'}),('custom',{'zh':'自定义','en':'Custom'})]]
        if field['key'] in ('x_sort','xiaohongshu_sort'):field['options']=[{**o,'label':{'zh':{'latest':'最新','relevance':'相关度','popular':'热门','top':'热门','likes':'点赞最多','general':'综合'}.get(o['value'],o['value']),'en':{'latest':'Latest','relevance':'Relevance','popular':'Popular','top':'Top','likes':'Most liked','general':'General'}.get(o['value'],o['value'])}} for o in field.get('options',[])]
        if field['key']=='sources':field.update(type='multiselect',options=[{'value':c['id'],'label':{'xiaohongshu':{'zh':'小红书','en':'Xiaohongshu'},'weibo':{'zh':'微博','en':'Weibo'}}.get(c['id'],c['name'])} for c in available])
        if field['key']=='profile':field.update(type='select',options=[{'value':p.key,'label':p.name} for p in BrowserProfileRepository(runtime.database).list_for_user(principal.actor_user_id)])
    return {'schema':schema,'fields':fields,'search_workflow':True,'submit_label':{'zh':'搜索','en':'Search'},
        'cloud_offer':status(runtime,principal.actor_user_id).get('cloud_offer',{}),
        'fast_source':status(runtime,principal.actor_user_id)['fast_source']}

async def complete(runtime,principal,form,values,run):
    if form.key in runtime.app_capability_router.disabled(principal.actor_user_id,principal.installation_id):raise HTTPException(409,'Provider disabled')
    if 'deepseek' in values.get('sources',[]):
        from ai2apps.browser.search_api import byok_available
        if not byok_available(runtime,principal.actor_user_id):
            from ai2apps.browser.cloud_search import refresh_offer
            await refresh_offer(runtime,principal.actor_user_id)
    try:record=prep.owned(runtime,principal,values.get('preparation_id',''),session_id=run.session_id)
    except ValueError as error:raise HTTPException(422,str(error)) from error
    if record['origin_run']!=run.id:raise HTTPException(409,'Search preparation Run changed')
    item=next((i for i in runtime.agents.list_interactions(run.id) if record['scope']=='interaction:'+i.id and i.status.value=='pending' and i.ui_hints.get('provider')==form.key),None)
    if item is None:raise HTTPException(409,'Search preparation interaction changed')
    mini=mounted(runtime,principal,item,run.session_id)
    values={k:v for k,v in values.items() if k!='preparation_ready'}
    try:arguments=prep.confirm(runtime,principal,mini,values['preparation_id'],values,scope='interaction:'+item.id)
    except (ValueError,KeyError,ValidationError) as error:raise HTTPException(422,str(error)) from error
    return {'capability':'web.search','provider':form.key,'arguments':{**arguments,'provider':form.key},'configure_only':True}

def install(runtime):
    form=FORMS[PROVIDER]
    FORMS[PROVIDER]=replace(form,describe=describe,complete=complete,related_capabilities=(),continuation=None)


def begin_form(runtime,principal,item,run,values,revision):
    """The owner chooses preparation policy; the generic form API only delegates."""
    return prep.begin(runtime,principal,mounted(runtime,principal,item,run.session_id),
        scope='interaction:'+item.id,session_id=run.session_id,origin_run=run.id,
        query=values.get('query',''),profile=values.get('profile','default'),
        locale=values.get('locale','zh'),request_id=str(revision),fast=values.get('mode','fast')=='fast')
