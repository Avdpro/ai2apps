from datetime import date,timedelta
from types import SimpleNamespace as NS
import pytest
from legacy_package_backend_fixture import runtime
from ai2apps.browser.shopping import replenishment_date,screen_plan
from ai2apps.browser.shopping_aaat import report,report_markdown,cart_receipt,APP,DECLARATION
from ai2apps.services import ToolProviderError

@pytest.mark.parametrize('remaining,bucket',[(-1,'overdue'),(0,'due_today'),(1,'next_3_days'),(3,'next_3_days'),(4,'later')])
def test_calendar_boundaries(remaining,bucket):
    today=date(2026,10,21);latest=today-timedelta(days=10-remaining)
    result=replenishment_date({'purchase_dates':[(latest-timedelta(days=10)).isoformat(),latest.isoformat()]},today)
    assert result['due_bucket']==bucket and result['days_until_due']==remaining
    assert result['due_date']==(today+timedelta(days=remaining)).isoformat()


def test_unknown_and_future_dates_never_become_due_today():
    row={'purchase_dates':['2026-10-20','2026-10-20','bad','2026-10-22']}
    assert replenishment_date(row,date(2026,10,21))['due_bucket']=='unknown'


def test_half_day_median_rounds_up_and_user_revision_preserves_facts():
    item={'id':'observed','purchase_dates':['2026-10-01','2026-10-04','2026-10-08']}
    facts=replenishment_date(item,date(2026,10,10))
    assert facts['interval_days']==4 and facts['due_date']=='2026-10-12'
    plan={'items':[{'id':'observed','selected':True,'quantity':1,'score':90,'reason':'requested'}],'message':'Requested'}
    result=screen_plan(plan,[item],message='Include this',today=date(2026,10,10))
    assert result['items'][0]['selected'] is True
    assert result['items'][0]['due_bucket']=='next_3_days'
    assert result['message']=='Requested'


def test_owner_totals_use_minor_units_and_unknown_prices_remain_unknown():
    value=report({'items':[{'id':'a','quantity':3,'selected':True},{'id':'b','quantity':2,'selected':True}]},
        [{'id':'a','title':'A','last_unit_price_minor':552,'last_price_currency':'USD'}, {'id':'b','title':'B'}])
    assert value['selected_totals_minor']=={'USD':1656}
    assert value['unknown_selected_prices']==1
    assert value['bucket_counts']['unknown']==2
    assert 'USD 16.56' in report_markdown(value)


def test_cart_receipt_exact_confirmation_and_single_invocation(runtime):
    provider=APP+'.shopping.prepare_cart';args={'profile':'default','source_tasks':['observed'],'selected':[{'id':'B000000001','quantity':1}]}
    item=NS(id='receipt',request={'version':1},ui_hints={'provider':provider,'provider_version':'1','app_id':APP,'mini_app_id':'ai2apps.shopping-pro'},status=NS(value='submitted'),response={'status':'completed','result':{'capability':'shopping.prepare_cart','provider':provider,'configure_only':True,'user_confirmed':True,'arguments':args}})
    items=[item]
    rt=NS(database=runtime.database,agents=NS(get_run=lambda id:NS(id=id,session_id='session'),list_interactions=lambda id:items),
          app_capability_router=NS(providers={provider:NS(version='1')}))
    ctx=NS(invocation_id='invoke',trace_id='run',session_id='session')
    cart_receipt(rt,args,ctx);cart_receipt(rt,args,ctx)
    with pytest.raises(ToolProviderError):cart_receipt(rt,args,NS(invocation_id='other',trace_id='run',session_id='session'))
    with pytest.raises(ToolProviderError):cart_receipt(rt,{**args,'profile':'another'},ctx)
    with pytest.raises(ToolProviderError):cart_receipt(rt,args,NS(invocation_id='invoke',trace_id='run',session_id='other'))
    item.status=NS(value='cancelled')
    with pytest.raises(ToolProviderError):cart_receipt(rt,args,ctx)
    assert 'shopping.refresh_list' in [c for workflow in DECLARATION['workflows'] for c in workflow['capabilities']]

@pytest.mark.asyncio
async def test_registered_refresh_returns_owner_report_and_source_reference(runtime,monkeypatch):
    from dataclasses import replace
    from pathlib import Path
    import json
    from ai2apps.chat import ChatRepository
    from ai2apps.identity import RequestPrincipal
    from ai2apps.services.models import ToolCallContext
    from ai2apps.browser.mini_apps import WebAgentMiniAppBroker
    principal=RequestPrincipal.legacy_local()
    thread,_=ChatRepository(runtime.database,runtime.events,principal=principal).create_thread(title='Shopping fixture')
    declaration=json.loads((Path(__file__).resolve().parents[2]/'packages/ai2apps-shopping-pro/app.yaml').read_text())['mini_apps'][0]
    monkeypatch.setattr(runtime.extension_manager,'_studio_mini_app_definition',lambda *a:(None,declaration))
    catalog=[{'id':'B000000001','title':'Paper','purchase_dates':['2026-09-01','2026-09-11'],'last_unit_price_minor':100,'last_price_currency':'USD'}]
    plan={'items':[{'id':'B000000001','selected':True,'quantity':2,'score':90,'reason':'Repeat'}]}
    observed={'id':'observed','status':'completed','name':'Refresh','result':{'assigned':{'shopping_report':{'history':{'items':catalog},'plan':plan}}}}
    mounted=NS(declaration={'id':'ai2apps.shopping-pro'})
    monkeypatch.setattr(WebAgentMiniAppBroker,'registered',lambda *a:mounted)
    submitted=[]
    def submit(self,*a,**kw):submitted.append(kw);return observed
    monkeypatch.setattr(WebAgentMiniAppBroker,'submit_declared',submit)
    monkeypatch.setattr(WebAgentMiniAppBroker,'task_declared',lambda *a:observed)
    ctx=replace(ToolCallContext.from_principal(principal,caller_id='fixture',session_id=thread.session.id),invocation_id='durable')
    provider=runtime.app_capability_router.providers[APP+'.shopping.refresh_list']
    schema=(await provider.describe(principal))['effective_schema']
    assert schema['properties']['history_mode']['enum']==['incremental','cache']
    assert schema['properties']['history_mode']['default']=='incremental'
    assert 'previous_task' not in schema['properties'] and 'previous_task' not in schema['required']
    result=await provider.handler({'pages':1,'locale':'zh','previous_task':'','profile':'default'},ctx)
    assert result['report']['selected_totals_minor']=={'USD':200}
    assert result['aaat_context']['scope']['source_tasks']==['observed']
    assert submitted[0]['capability']=='refresh_list'
    assert submitted[0]['request_id']=='aaat-durable'
    # A cart confirmation authorizes cart input, not permanent browser tabs.
    monkeypatch.setattr('ai2apps.browser.shopping_aaat.cart_receipt',lambda *a,**kw:None)
    cart_provider=runtime.app_capability_router.providers[APP+'.shopping.prepare_cart']
    await cart_provider.handler({'profile':'default','source_tasks':['observed'],'selected':[{'id':'B000000001','quantity':2}]},ctx)
    assert submitted[-1]['capability']=='prepare_cart'
    assert submitted[-1].get('retain_pages',False) is False
    cart=runtime.services.get_tool('shopping.prepare_cart')
    assert 'external_write' in cart.effects

    policies=runtime.app_capability_router.active_result_policies([NS(kind='tool',tool_name='shopping.refresh_list',status=NS(value='completed'),output=result)])
    policy=next(p for p in policies if p.id=='shopping-owner-report')
    assert policy.instruction([])['role']=='system'
    completed=NS(kind='tool',tool_name='shopping.refresh_list',status=NS(value='completed'),output=result)
    failed_cart=NS(kind='tool',tool_name='shopping.prepare_cart',status=NS(value='failed'),output={})
    assert policy.finalize('Cart failed',[completed,failed_cart])==('Cart failed',None)


def test_owner_table_binds_observed_images_urls_and_calendar_fields():
    from ai2apps.browser.shopping_aaat import table_view
    from ai2apps.services.aaat import validate_view
    catalog=[{'id':'one','title':'Paper','url':'https://www.amazon.com/dp/B000000001','image_url':'https://m.media-amazon.com/images/I/paper.jpg','preferred_channel':'fresh','last_unit_price_minor':552,'last_price_currency':'USD'}]
    rows=[{'id':'one','quantity':2,'selected':True,'due_date':'2026-10-25','due_bucket':'later'}]
    value=validate_view(table_view(catalog,rows))
    assert value['items'][0]['image']['url']==catalog[0]['image_url']
    assert value['items'][0]['url']==catalog[0]['url']
    assert value['items'][0]['fields']['bucket']=='3天以后'
    assert value['items'][0]['fields']['price']=='USD 5.52' and value['items'][0]['fields']['subtotal']=='USD 11.04'
    catalog[0]['image_url']='https://evil.example/a.jpg'
    assert 'image' not in table_view(catalog,rows)['items'][0]
    assert table_view(catalog,[{'id':'invented','quantity':1}])['items']==[]

@pytest.mark.asyncio
async def test_owned_thumbnail_checks_observation_scope_before_fetch(runtime,monkeypatch):
    from ai2apps.browser.shopping_aaat import owned_product_image,table_view
    from ai2apps.browser.tasks import BrowserTaskRepository
    from ai2apps.api import ownership
    checked=[];fetched=[]
    principal=NS(actor_user_id='owner')
    task={'status':'completed','capability':'history','session_id':'session','run_id':'run'}
    def get(self,owner,identifier):
        if owner!='owner' or identifier!='task':raise KeyError(identifier)
        return task
    monkeypatch.setattr(BrowserTaskRepository,'get',get)
    monkeypatch.setattr(BrowserTaskRepository,'program',lambda *a:({},'web-mini-app:instance:ai2apps.shopping-pro'))
    monkeypatch.setattr(ownership,'authorize_session',lambda *a:checked.append(a[-1]))
    catalog=[{'id':'product','title':'Paper','url':'https://www.amazon.com/dp/B000000001','_source_task':'task','image_url':'https://m.media-amazon.com/images/I/a.jpg'}]
    monkeypatch.setattr(runtime.agents,'get_run',lambda *a:NS(output={'result':{'items':catalog}}))
    async def images(rows):fetched.extend(rows);return [{'image_data_url':'data:image/jpeg;base64,aA=='}]
    monkeypatch.setattr('ai2apps.browser.product_images.product_images',images)
    assert await owned_product_image(runtime,principal,'task','product')=='data:image/jpeg;base64,aA=='
    assert checked==['session'] and len(fetched)==1
    image=table_view(catalog,[{'id':'product','quantity':1}])['items'][0]['image']['url']
    assert image=='/v1/platform/studios/ai2apps.ai-browser/shopping/tasks/task/products/product/image'
    with pytest.raises(KeyError):await owned_product_image(runtime,NS(actor_user_id='other'),'task','product')
    task['status']='failed'
    with pytest.raises(ToolProviderError):await owned_product_image(runtime,principal,'task','product')
    assert len(fetched)==1

def test_cart_report_alias_preserves_exact_observed_selection_and_strict_schema():
    import json
    from pathlib import Path
    from jsonschema import Draft202012Validator
    from ai2apps.browser.shopping_aaat import cart_values
    declaration=json.loads((Path(__file__).resolve().parents[2]/'packages/ai2apps-shopping-pro/app.yaml').read_text())['mini_apps'][0]
    schema=next(c for c in declaration['web_agent']['capabilities'] if c['id']=='prepare_cart')['source']['inputs']
    items=[{'id':id,'quantity':2} for id in ['B0CJJZ22BB','B07ZLFPXHC','B08X283B8L']]
    values=cart_values(None,None,None,{'items':items,'source_tasks':['observed']},None)
    assert values=={'selected':items,'source_tasks':['observed']}
    Draft202012Validator(schema).validate(values)
    assert cart_values(None,None,None,dict(values),None)==values
    with pytest.raises(ValueError):cart_values(None,None,None,{**values,'items':[{'id':'B0CJJZ22BB','quantity':1}]},None)
    assert list(Draft202012Validator(schema).iter_errors({**values,'unexpected':True}))
    assert list(Draft202012Validator(schema).iter_errors({**values,'selected':[{'id':'B0CJJZ22BB','quantity':11}]}))

@pytest.mark.asyncio
async def test_cart_alias_renders_three_named_rows_and_binds_confirmation_without_cart_write(runtime,monkeypatch):
    import json,httpx
    from pathlib import Path
    from fastapi import FastAPI
    import test_parameter_forms
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.identity import RequestPrincipal
    from ai2apps.browser.mini_apps import WebAgentMiniAppBroker
    from test_app_interactions import wait
    declaration=json.loads((Path(__file__).resolve().parents[2]/'packages/ai2apps-shopping-pro/app.yaml').read_text())['mini_apps'][0]
    monkeypatch.setattr(runtime.extension_manager,'_studio_mini_app_definition',lambda *a:(None,declaration))
    ids=['B0CJJZ22BB','B07ZLFPXHC','B08X283B8L'];catalog=[{'id':id,'title':'Observed product '+str(i)} for i,id in enumerate(ids)]
    monkeypatch.setattr(WebAgentMiniAppBroker,'registered',lambda *a: NS())
    monkeypatch.setattr(WebAgentMiniAppBroker,'task_declared',lambda *a:{'result':{'items':catalog}})
    writes=[];monkeypatch.setattr(WebAgentMiniAppBroker,'submit_declared',lambda *a,**k:writes.append(k))
    values={'items':[{'id':id,'quantity':2} for id in ids],'source_tasks':['observed'],'profile':'default'}
    monkeypatch.setattr(test_parameter_forms,'ARGS',{'request_id':'cart-alias','capability':'shopping.prepare_cart','values':values})
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=test_parameter_forms.setup(runtime);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        item=runtime.agents.list_interactions(run.id)[0];url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            response=await client.get(url);assert response.status_code==200,response.text
            state=response.json();assert state['invalid']==[] and state['missing']==[]
            assert state['values']['selected']==values['items'] and 'items' not in state['values']
            field=next(f for f in state['descriptor']['fields'] if f['key']=='selected')
            assert field['presentation']=='records' and len(field['columns'][0]['options'])==3
            assert all('Observed product 0' in state['description'][locale] for locale in ('zh','en'))
            confirmed=await client.post(url+'/submit',json={'revision':state['revision'],'values':state['values']})
            assert confirmed.status_code==200,confirmed.text
            assert confirmed.json()['result']['arguments']['selected']==values['items']
            assert writes==[]  # A form receipt alone must never mutate the cart.
    finally:await runtime.stop_background_tasks()


def test_discovery_never_launches_a_missing_instance(runtime,monkeypatch):
    from unittest.mock import Mock
    from ai2apps.browser.shopping_cache import discovery_mount
    from ai2apps.browser.mini_apps import WebAgentMiniAppBroker
    monkeypatch.setattr('ai2apps.api.ownership.authorize_session',lambda *a:None)
    monkeypatch.setattr(runtime.extension_manager,'_studio_mini_app_definition',lambda *a:({'package_id':'fixture.not-launched','effective_digest':'pinned'},{}))
    launch=Mock(side_effect=AssertionError('Discovery must be read-only'))
    monkeypatch.setattr(runtime.extension_manager,'launch_app',launch)
    assert discovery_mount(WebAgentMiniAppBroker(runtime),NS(actor_user_id='owner'),'session') is None
    launch.assert_not_called()
