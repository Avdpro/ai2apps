"""Owner cache/partial integration; browser observations are fixtures."""
import pytest
from test_web_agent_mini_apps import broker
from test_shopping_mini_app import Page, ASIN, URL, shopping_declaration
from ai2apps.browser.shopping import execute, frequencies, cart_source, cart_report_result
from ai2apps.browser.shopping_cache import latest_history
from ai2apps.browser.tasks import BrowserTaskRepository
from ai2apps.agent_builder.compiler import compile_source


def test_cache_selection_scope_and_deleted_results(broker,monkeypatch):
    service,mount,principal=broker;repo=BrowserTaskRepository(service.runtime.database)
    def seed(owner='owner',profile='default',caller=None):
        task=repo.enqueue(owner,profile,'','history','','History',{},session_id='session',program={},caller_app_id=caller or service.caller(mount))
        repo.update(owner,task['id'],status='completed');return task['id']
    old=seed();seed(owner='foreign');seed(profile='other');seed(caller='another-mini');deleted=seed()
    def read(m,p,key):return {**repo.get(p.actor_user_id,key),'result':{} if key==deleted else {'items':[],'synced_at':'2026-10-21'}}
    monkeypatch.setattr(service,'task_declared',read)
    assert latest_history(service,mount,principal,'default')['id']==old
    assert latest_history(service,mount,principal,'other')['profile_key']=='other'


@pytest.mark.parametrize('operation,mode,action',[('history','incremental','history'),('refresh_list','incremental','history'),('refresh_list','cache','cached_history')])
def test_aaat_seeds_history_without_user_task_id(broker,monkeypatch,operation,mode,action):
    service,mount,principal=broker;mount.declaration=shopping_declaration()
    catalog=frequencies([{'id':ASIN,'url':URL,'title':'Paper','purchased_at':'January 1, 2026'}])
    monkeypatch.setattr('ai2apps.browser.shopping_cache.latest_history',lambda *a:{'status':'completed','capability':'history','profile_key':'default','result':{'items':catalog,'synced_at':'2026-10-21'}})
    params={'pages':1,**({'locale':'zh','previous_task':''} if operation=='refresh_list' else {})}
    task=service.submit_declared(mount,principal,capability=operation,parameters=params,profile='default',request_id=operation+mode,_shopping_history_mode=mode)
    program,_=BrowserTaskRepository(service.runtime.database).program('owner',task['id'])
    assert program['steps'][0]['arguments']['shopping_action']==action
    assert program['steps'][0]['arguments']['known_items']==catalog
    assert program['schema']=='ai2apps.compiled-agent/v1'
    from ai2apps.browser.shopping import history_source,refresh_source
    inputs=next(c for c in mount.declaration['web_agent']['capabilities'] if c['id']==operation)['source']['inputs']
    source=history_source(inputs,catalog) if operation=='history' else refresh_source(inputs,catalog,cache_only=mode=='cache')
    assert compile_source(source).valid


def test_full_reload_policy_is_not_an_aaat_option(broker):
    service,mount,principal=broker;mount.declaration=shopping_declaration()
    with pytest.raises(ValueError):service.submit_declared(mount,principal,capability='history',parameters={'pages':1},profile='default',request_id='bad',_shopping_history_mode='full')


@pytest.mark.asyncio
async def test_known_orders_without_prices_skip_details():
    row={'id':ASIN,'url':URL,'title':'Paper','purchased_at':'January 1, 2026','order_key':'order-one'}
    page=Page([{'cards':1,'items':[row],'detail_requests':[{'url':'https://www.amazon.com/gp/your-account/order-details?orderID=1','items':[row]}],'next_url':'https://www.amazon.com/your-orders/orders?startIndex=10'}])
    data=(await execute(page,{'shopping_action':'history','pages':6,'known_items':frequencies([row])}))['evidence']['result']
    assert data['orders_read']==0 and data['new_purchase_dates']==0 and data['stop_reason']=='known_page'
    assert page.navigate.await_count==1


@pytest.mark.asyncio
async def test_cache_only_never_reads_dom():
    page=Page([])
    data=(await execute(page,{'shopping_action':'cached_history','known_items':[],'synced_at':'old'}))['evidence']['result']
    assert data['synced_at']=='old' and data['pages_read']==0
    page.navigate.assert_not_called()


@pytest.mark.asyncio
async def test_out_of_stock_continues_to_other_items_and_partial_report():
    item={'id':ASIN,'title':'Unavailable item','url':URL,'quantity':2,'preferred_channel':'fresh','preferred_channel_url':URL+'?almBrandId=Observed'}
    page=Page([{'recognized':True,'items':[]},{'asin':ASIN,'out_of_stock':True,'availability':'Out of Stock','add':None}])
    skipped=await execute(page,{'shopping_action':'cart_item','item':item})
    assert skipped['outcome']=='success' and skipped['evidence']['result']['status']=='unavailable'
    page.pointer_to.assert_not_called()
    other={**item,'id':'B000000002','url':'https://www.amazon.com/dp/B000000002','preferred_channel':'unknown','quantity':1}
    source=cart_source({'type':'object','properties':{}},[item,other])
    assert source['steps'][0]['on']['success']=='item_1' and compile_source(source).valid
    assert source['steps'][-1]['arguments']['item_results']==['${steps.item_0.output}','${steps.item_1.output}']
    data=cart_report_result({'recognized':True,'items':[{'id':other['id'],'quantity':1}]},[other],[skipped['evidence']['result']])['evidence']['result']
    assert data['status']=='partial' and data['items'][0]['verified'] and data['skipped'][0]['reason']=='out_of_stock'


@pytest.mark.asyncio
async def test_all_unavailable_finishes_without_cart_action():
    page=Page([]);skipped={'id':ASIN,'quantity':1,'status':'unavailable','reason':'out_of_stock'}
    data=(await execute(page,{'shopping_action':'cart_report','items':[{'id':ASIN,'quantity':1}],'item_results':[skipped]}))['evidence']['result']
    assert data['status']=='partial' and data['items']==[]
    page.navigate.assert_not_called();page.pointer_to.assert_not_called()


def test_partial_never_masks_unknown_quantity():
    result=cart_report_result({'recognized':True,'items':[{'id':ASIN,'quantity':1}]},[{'id':ASIN,'quantity':2}],[])
    assert result['outcome']=='needs_user' and result['evidence']['observed_quantity']==1


@pytest.mark.parametrize('visible,stock',[(True,True),(False,False)])
@pytest.mark.parametrize('selector',['#availability','[data-feature-name=almOutOfStockBuyBox]'])
@pytest.mark.parametrize('stock_asin',['B000123456','B000999999'])
def test_stock_detection_uses_visible_availability_not_recommendation_text(visible,stock,selector,stock_asin):
    import json,subprocess
    from ai2apps.browser.shopping import CONTROLS_SCRIPT,CHANNEL_HELPER,SHOPPING_DOM_HELPER
    script=r'''
const ai2appsDOMVisible=e=>!!e&&e.visible!==false;
const availability={visible:VISIBLE,textContent:'Out\n of   Stock',getAttribute:n=>n==='data-csa-c-asin'?STOCK_ASIN:null};
const document={body:{textContent:'Out of Stock recommendation'},title:'Product',getElementById:()=>null,querySelector:()=>null,querySelectorAll:s=>s.split(',').includes(STOCK_SELECTOR)?[availability]:[]};
const location={pathname:'/dp/B000123456'};
'''.replace('VISIBLE','true' if visible else 'false').replace('STOCK_SELECTOR',json.dumps(selector)).replace('STOCK_ASIN',json.dumps(stock_asin))+CHANNEL_HELPER+SHOPPING_DOM_HELPER+'console.log(JSON.stringify(('+CONTROLS_SCRIPT+')()));'
    result=json.loads(subprocess.check_output(['node','-e',script],text=True))
    assert result['out_of_stock'] is (stock and stock_asin=='B000123456')


@pytest.mark.asyncio
@pytest.mark.parametrize('anchor',['increment','quantity_control','row_rect'])
async def test_existing_cart_review_scrolls_to_observed_product_and_rereads(anchor):
    from types import SimpleNamespace as NS
    from unittest.mock import AsyncMock
    from ai2apps.browser.shopping import verify_existing_cart
    data={'recognized':True,'items':[{'id':ASIN,'quantity':2,anchor:{'x':10,'y':1800,'width':40,'height':30}}]}
    page=Page([data,{'height':800},{'recognized':True,'items':[{'id':ASIN,'quantity':2}]}])
    page.scroll=AsyncMock()
    page.visual_recovery=NS(policy={'visual_review':'always'},verify=AsyncMock(return_value={'state_verified':True,'visually_verified':True,'evidence':[]}))
    result=await verify_existing_cart(page,{'id':ASIN,'quantity':2},2)
    page.scroll.assert_awaited_once_with(1415)
    page.pointer_to.assert_not_called()
    assert result['evidence']['result']['already_present']


def test_assistance_preserves_dom_quantity_and_specific_visual_cause():
    from ai2apps.browser.shopping import assistance_message
    text=assistance_message({'reason':'amazon_cart_add_unverified','expected_quantity':2,'observed_quantity':2,
        'verification_reason':'视觉复检未确认；本次未加购'}, {'item':{'title':'Observed product','quantity':2}})
    assert '程序本次读取数量 2' in text and '视觉复检未确认' in text

@pytest.mark.asyncio
async def test_existing_extra_units_review_actual_count_and_requested_minimum():
    from types import SimpleNamespace as NS
    from unittest.mock import AsyncMock
    from ai2apps.browser.shopping import verify_existing_cart
    page=Page([{'recognized':True,'items':[{'id':ASIN,'quantity':2}]}])
    review=AsyncMock(return_value={'state_verified':True,'visually_verified':True,'evidence':[]})
    page.visual_recovery=NS(policy={'visual_review':'always'},verify=review)
    result=await verify_existing_cart(page,{'id':ASIN,'title':'Observed product','quantity':1},2)
    assert result['outcome']=='success' and result['evidence']['result']['quantity']==2
    assert 'observed quantity 2' in review.call_args.args[1]
    assert 'requested minimum is 1' in review.call_args.args[1]
    assert review.call_args.args[2]['verified'] is True
    page.pointer_to.assert_not_called()
