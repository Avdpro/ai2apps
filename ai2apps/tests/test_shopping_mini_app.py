from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import json
import subprocess

import pytest

from ai2apps.browser.shopping import frequencies, product_url, execute, cart_source
from ai2apps.browser.mini_apps import validate_web_agent
from ai2apps.extensions.development import DevelopmentPackageLoader
from ai2apps.agent_builder.compiler import compile_source

ASIN='B000123456'
URL='https://www.amazon.com/dp/'+ASIN


def test_history_frequency_is_observed_and_unknown_dates_stay_unknown():
    rows=[{'id':ASIN,'url':URL,'title':'Paper','purchased_at':day} for day in ['January 1, 2026','February 1, 2026','March 1, 2026','March 1, 2026']]
    result=frequencies(rows,date(2026,4,1))[0]
    assert result['purchase_count']==3 and result['interval_days']==30
    assert result['days_since']==31
    unknown=frequencies([{**rows[0],'purchased_at':'not a date'}])[0]
    assert unknown['last_purchase'] is None and unknown['interval_days'] is None


@pytest.mark.parametrize('url',['https://evil.test/dp/'+ASIN,'https://www.amazon.com/checkout','https://user@www.amazon.com/dp/'+ASIN,URL+'?x=1'])
def test_product_urls_cannot_reach_checkout_or_other_origins(url):
    with pytest.raises(ValueError):product_url(url)


def test_package_has_privacy_and_valid_independent_capabilities():
    root=Path(__file__).resolve().parents[2]
    package=next(p for p in DevelopmentPackageLoader(root).discover() if p.package_id=='ai2apps.shopping-pro')
    mini=package.manifest['mini_apps'][0]
    assert mini['web_agent']['model_profile']=='privacy'
    assert {e['id'] for e in validate_web_agent(mini)}=={'history','recommend','revise','search_products','prepare_cart','refresh_list','gift_recommend','gift_revise','gift_prepare_cart'}
    source=cart_source(next(c for c in mini['web_agent']['capabilities'] if c['id']=='prepare_cart')['source']['inputs'],[{'id':ASIN,'url':URL,'quantity':2}])
    assert compile_source(source).valid
    assert all(s['execution']['mode']=='compiled' for s in source['steps'])


class Page:
    context_id='owned'
    def __init__(self, observations):
        self.observations=iter(observations)
        self.navigate=AsyncMock()
        self.snapshot=AsyncMock(return_value={'url':URL})
        self.pause=AsyncMock()
        self.pointer_to=AsyncMock()
        self.connection=SimpleNamespace(command=AsyncMock())
    async def call_json(self,*args):return next(self.observations)
    async def dispatch_input(self,actions):
        return await self.connection.command('input.performActions',{'context':self.context_id,'actions':actions})


@pytest.mark.asyncio
async def test_existing_cart_quantity_prevents_duplicate_addition():
    page=Page([{'recognized':True,'items':[{'id':ASIN,'quantity':3}]}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':2}})
    assert result['outcome']=='success' and result['evidence']['result']['already_present']
    page.pointer_to.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_cart_layout_does_not_add():
    page=Page([{'items':[]}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':1}})
    assert result['outcome']=='needs_user'
    page.pointer_to.assert_not_called()


@pytest.mark.asyncio
async def test_unverified_cart_click_is_never_replayed():
    page=Page([{'recognized':True,'items':[]},{'asin':ASIN,'add':{'x':1,'y':2,'width':30,'height':20},'subscription':False}, {'recognized':True,'items':[]}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':1}})
    assert result['outcome']=='needs_user'
    assert result['evidence']['reason']=='amazon_cart_add_unverified'
    page.pointer_to.assert_awaited_once()


@pytest.mark.asyncio
async def test_partial_cart_is_topped_up_without_readding_product(monkeypatch):
    monkeypatch.setattr('ai2apps.browser.shopping.asyncio.sleep',AsyncMock())
    page=Page([{'recognized':True,'items':[{'id':ASIN,'quantity':1,'increment':{'x':1,'y':2,'width':30,'height':20}}]},
               {'recognized':True,'items':[{'id':ASIN,'quantity':2}]}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':2}})
    assert result['outcome']=='success'
    assert result['evidence']['result']['quantity']==2
    page.pointer_to.assert_awaited_once()
    assert page.navigate.await_count==1


@pytest.mark.asyncio
async def test_uncertain_cart_increment_is_not_repeated(monkeypatch):
    monkeypatch.setattr('ai2apps.browser.shopping.asyncio.sleep',AsyncMock())
    row={'recognized':True,'items':[{'id':ASIN,'quantity':1,'increment':{'x':1,'y':2,'width':30,'height':20}}]}
    page=Page([row]*5)
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':2}})
    assert result['outcome']=='needs_user'
    assert result['evidence']['observed_quantity']==1
    page.pointer_to.assert_awaited_once()


@pytest.mark.asyncio
async def test_single_item_add_can_be_completed_using_cart_stepper(monkeypatch):
    monkeypatch.setattr('ai2apps.browser.shopping.asyncio.sleep',AsyncMock())
    rect={'x':1,'y':2,'width':30,'height':20}
    page=Page([{'recognized':True,'items':[]},
               {'asin':ASIN,'add':rect,'quantity':rect,'options':[1,2],'subscription':False},
               {'recognized':True,'items':[{'id':ASIN,'quantity':1,'increment':rect}]},
               {'recognized':True,'items':[{'id':ASIN,'quantity':2}]}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':2}})
    assert result['outcome']=='success'
    assert page.pointer_to.await_count==3


@pytest.mark.asyncio
async def test_amazon_redirect_outside_scope_cannot_trigger_cart_click():
    page=Page([]);page.snapshot=AsyncMock(return_value={'url':'https://evil.test/'})
    with pytest.raises(ValueError,match='outside scope'):
        await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':1}})
    page.pointer_to.assert_not_called()

from ai2apps.tests.test_web_agent_mini_apps import broker
from ai2apps.studio.capability_broker import StudioCapabilityError


def shopping_declaration():
    root=Path(__file__).resolve().parents[2]
    return next(p for p in DevelopmentPackageLoader(root).discover() if p.package_id=='ai2apps.shopping-pro').manifest['mini_apps'][0]


def test_cart_program_is_built_only_from_own_observed_product_ids(broker,monkeypatch):
    service,mount,principal=broker;mount.declaration=shopping_declaration()
    monkeypatch.setattr(service,'task',lambda *a:{'status':'completed','capability':'history','profile_key':'default','result':{'items':[{'id':ASIN,'url':URL,'title':'Paper'}]}})
    task=service.submit('mount',principal,capability='prepare_cart',parameters={'source_tasks':['observed'],'selected':[{'id':ASIN,'quantity':2}]},profile='default',request_id='cart')
    from ai2apps.browser.tasks import BrowserTaskRepository
    program,caller=BrowserTaskRepository(service.runtime.database).program('owner',task['id'])
    assert program['steps'][0]['arguments']['item']['url']==URL
    assert program['steps'][0]['arguments']['item']['quantity']==2
    assert task['browser_context']['model_profile']=='privacy'
    with pytest.raises(StudioCapabilityError):
        service.submit('mount',principal,capability='prepare_cart',parameters={'source_tasks':['observed'],'selected':[{'id':'B999999999','quantity':2}]},profile='default',request_id='fake')


def test_other_profile_history_and_normal_models_cannot_be_used(broker,monkeypatch):
    service,mount,principal=broker;mount.declaration=shopping_declaration()
    monkeypatch.setattr(service,'task',lambda *a:{'status':'completed','capability':'history','profile_key':'other','result':{'items':[]}})
    with pytest.raises(StudioCapabilityError):
        service.submit('mount',principal,capability='recommend',parameters={'source_tasks':['observed'],'locale':'zh'},profile='default',request_id='wrong-profile')
    mount.declaration['web_agent']['model_profile']='normal'
    with pytest.raises(StudioCapabilityError,match='Privacy'):
        service.submit('mount',principal,capability='history',parameters={'pages':1},profile='default',request_id='normal')


def test_large_history_is_data_not_an_oversized_ai_instruction(broker,monkeypatch):
    service,mount,principal=broker;mount.declaration=shopping_declaration()
    records=[{'id':f'B{i:09d}','url':f'https://www.amazon.com/dp/B{i:09d}','title':'Daily product '+('long name '*30)} for i in range(50)]
    monkeypatch.setattr(service,'task',lambda *a:{'status':'completed','capability':'history','profile_key':'default','result':{'items':records}})
    task=service.submit('mount',principal,capability='recommend',parameters={'source_tasks':['observed'],'locale':'zh'},profile='default',request_id='recommend-many')
    from ai2apps.browser.tasks import BrowserTaskRepository
    program,_=BrowserTaskRepository(service.runtime.database).program('owner',task['id'])
    assert len(task['input']['catalog'])==50
    assert len(program['steps'][0]['ai']['instruction'])<4000


@pytest.mark.asyncio
async def test_cart_add_uses_native_input_and_requires_observed_verification():
    page=Page([{'recognized':True,'items':[]},{'asin':ASIN,'add':{'x':1,'y':2,'width':30,'height':20},'quantity':{'x':1,'y':2,'width':30,'height':20},'options':[1,2,3],'subscription':False}, {'recognized':True,'items':[{'id':ASIN,'quantity':2}]}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':2}})
    assert result['outcome']=='success' and result['evidence']['result']['verified']
    assert page.pointer_to.await_count==2
    assert page.connection.command.await_args.args[0]=='input.performActions'


@pytest.mark.asyncio
async def test_subscriptions_are_not_added_to_cart():
    page=Page([{'recognized':True,'items':[]},{'asin':ASIN,'add':{'x':1,'y':2,'width':30,'height':20},'subscription':True}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':1}})
    assert result['outcome']=='needs_user'
    page.pointer_to.assert_not_called()


def test_incremental_history_merge_preserves_older_dates_and_deduplicates_overlap():
    from ai2apps.browser.shopping import merge_history
    old=frequencies([{'id':ASIN,'url':URL,'title':'Paper','purchased_at':d} for d in ['January 1, 2026','February 1, 2026']],date(2026,4,1))
    merged=merge_history(old,[{'id':ASIN,'url':URL,'title':'Paper','purchased_at':d} for d in ['February 1, 2026','March 1, 2026']],date(2026,4,1))
    assert merged[0]['purchase_count']==3
    assert merged[0]['purchase_dates']==['2026-01-01','2026-02-01','2026-03-01']
    assert merge_history(merged,[],date(2026,4,2))[0]['days_since']==32


def test_same_day_distinct_orders_count_once_each_and_replace_legacy_date():
    from ai2apps.browser.shopping import merge_history
    old=frequencies([{'id':ASIN,'url':URL,'title':'Paper','purchased_at':'January 1, 2026'}],date(2026,4,1))
    records=[{'id':ASIN,'url':URL,'title':'Paper','purchased_at':'January 1, 2026','order_key':key} for key in ['opaque-one','opaque-two','opaque-one']]
    merged=merge_history(old,records,date(2026,4,1))[0]
    assert merged['purchase_count']==2
    assert len(merged['purchase_dates'])==1


def test_channel_history_survives_merge_and_is_not_counted_twice():
    from ai2apps.browser.shopping import merge_history
    def record(day,key,channel,delivery):
        return {'id':ASIN,'url':URL,'title':'365 by Whole Foods','purchased_at':day,'order_key':key,'channel':channel,'delivery_window':delivery}
    first=record('2026-01-01','one','whole_foods','same_day')
    second=record('2026-02-01','two','fresh','next_day')
    old=frequencies([first,second],date(2026,4,1))
    assert old[0]['preferred_channel']=='fresh'  # Equal counts: most recent evidence.
    merged=merge_history(old,[first,record('2026-03-01','three','whole_foods','same_day')],date(2026,4,1))[0]
    assert merged['channel_counts']=={'whole_foods':2,'fresh':1}
    assert merged['preferred_channel']=='whole_foods'
    assert merged['preferred_delivery_window']=='same_day'
    assert merged['purchase_count']==3
    unknown=frequencies([{'id':ASIN,'url':URL,'title':'365 by Whole Foods','purchased_at':'2026-01-01'}],date(2026,4,1))[0]
    assert unknown['preferred_channel']=='unknown'


def test_known_order_can_be_enriched_with_channel_later():
    from ai2apps.browser.shopping import merge_history
    record={'id':ASIN,'url':URL,'title':'Paper','purchased_at':'2026-01-01','order_key':'one'}
    old=frequencies([record],date(2026,4,1))
    enriched=merge_history(old,[{**record,'channel':'fresh'}],date(2026,4,1))[0]
    assert enriched['purchase_count']==1 and enriched['preferred_channel']=='fresh'


def test_storefront_link_is_observed_and_bounded():
    from ai2apps.browser.shopping import purchase_url
    record={'id':ASIN,'url':URL,'title':'Paper','purchased_at':'2026-01-01','channel':'fresh','channel_url':URL+'?almBrandId=ObservedStore123'}
    item=frequencies([record],date(2026,4,1))[0]
    assert purchase_url(item)==record['channel_url']+'&fpw=alm'
    for bad in [URL+'?redirect=https://evil.test',URL+'?almBrandId=one&almBrandId=two',URL+'?almBrandId=one&checkout=1','https://evil.test/dp/'+ASIN+'?almBrandId=one']:
        with pytest.raises(ValueError):purchase_url({**item,'preferred_channel_url':bad})


def test_delivery_window_is_separate_from_channel_and_unknown_is_not_a_mismatch():
    from ai2apps.browser.shopping import channel_review
    item={'preferred_channel':'fresh','preferred_delivery_window':'same_day'}
    assert channel_review(item,{'channel':'fresh','delivery_window':'unknown'}) is None
    assert channel_review(item,{'channel':'fresh','delivery_window':'next_day'})['evidence']['reason']=='amazon_delivery_confirmation_required'


def test_channel_classifier_handles_observed_fresh_order_heading_and_brand_image():
    from ai2apps.browser.shopping import CHANNEL_HELPER
    script=CHANNEL_HELPER+r'''
const node=(text,alt='')=>({textContent:text,getAttribute:k=>k==='alt'?alt:null});
const root=(heading,brand)=>({querySelectorAll:s=>s==='h1,h2,h3,h4,[role="heading"]'?[node(heading)]:s==='img[alt*="brand image"]'?[node('',brand)]:[]});
console.log(JSON.stringify([shoppingChannel(root('Amazon Fresh delivery','')),shoppingChannel(root('','The brand image for your Amazon Fresh order')),shoppingChannel(root('365 by Whole Foods',''))]));
'''
    result=json.loads(subprocess.check_output(['node','-e',script],text=True))
    assert [r['channel'] for r in result]==['fresh','fresh','unknown']


@pytest.mark.asyncio
async def test_channel_mismatch_pauses_before_add_or_quantity_change():
    page=Page([{'recognized':True,'items':[{'id':ASIN,'quantity':1,'channel':'fresh'}]}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':2,'preferred_channel':'whole_foods'}})
    assert result['evidence']['reason']=='amazon_storefront_unavailable'
    page.pointer_to.assert_not_called()


@pytest.mark.asyncio
async def test_product_channel_must_be_observed_for_grocery_preference():
    page=Page([{'recognized':True,'items':[]},{'asin':ASIN,'add':{'x':1,'y':1,'width':20,'height':20}}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':1,'preferred_channel':'whole_foods','preferred_channel_url':URL+'?almBrandId=ObservedStore123'}})
    assert result['outcome']=='needs_user'
    assert result['evidence']['observed_channel']=='unknown'
    page.pointer_to.assert_not_called()


def test_refresh_list_runs_sync_and_ai_in_one_durable_program():
    mini=shopping_declaration()
    capability=next(e for e in mini['web_agent']['capabilities'] if e['id']=='refresh_list')
    assert compile_source(capability['source']).valid
    assert [s['operation'] for s in capability['source']['steps']]==['inspect','ai.transform','assign']


def test_sync_source_uses_verified_previous_history_and_rejects_other_profile(broker,monkeypatch):
    service,mount,principal=broker;mount.declaration=shopping_declaration()
    prior={'status':'completed','capability':'history','profile_key':'default','result':{'items':frequencies([{'id':ASIN,'url':URL,'title':'Paper','purchased_at':'January 1, 2026'}])}}
    monkeypatch.setattr(service,'task',lambda *a:prior)
    task=service.submit('mount',principal,capability='refresh_list',parameters={'pages':3,'locale':'zh','previous_task':'prior'},profile='default',request_id='sync')
    from ai2apps.browser.tasks import BrowserTaskRepository
    program,_=BrowserTaskRepository(service.runtime.database).program('owner',task['id'])
    assert program['steps'][0]['arguments']['known_items'][0]['purchase_count']==1
    assert task['browser_context']['model_profile']=='privacy'
    prior['profile_key']='other'
    with pytest.raises(StudioCapabilityError):
        service.submit('mount',principal,capability='refresh_list',parameters={'pages':3,'locale':'zh','previous_task':'prior'},profile='default',request_id='other')


@pytest.mark.asyncio
async def test_no_new_orders_stop_after_a_known_page_and_preserve_old_history():
    from ai2apps.browser.shopping import HISTORY_SCRIPT
    old=frequencies([{'id':ASIN,'url':URL,'title':'Paper','purchased_at':'January 1, 2026','order_key':'opaque','unit_price_text':'$5.97'}])
    page=Page([{'cards':1,'items':[{'id':ASIN,'url':URL,'title':'Paper','purchased_at':'January 1, 2026','order_key':'opaque'}],'next_url':'https://www.amazon.com/your-orders/orders?startIndex=10'}])
    result=await execute(page,{'shopping_action':'history','pages':3,'known_items':old})
    data=result['evidence']['result']
    assert data['pages_read']==1 and data['stop_reason']=='known_page'
    assert not data['bounded'] and data['new_purchase_dates']==0
    assert data['items'][0]['purchase_count']==1


def test_latest_purchase_price_keeps_currency_and_does_not_reuse_stale_price():
    from ai2apps.browser.shopping import merge_history,price_fields
    def record(day,key,text):return {'id':ASIN,'url':URL,'title':'Paper','purchased_at':day,'order_key':key,'unit_price_text':text}
    old=frequencies([record('2026-01-01','one','$5.97')],date(2026,4,1))
    merged=merge_history(old,[record('2026-02-01','two','HKD 43.10')],date(2026,4,1))[0]
    assert merged['last_unit_price_minor']==4310 and merged['last_price_currency']=='HKD'
    newer=merge_history([merged],[record('2026-03-01','three','')],date(2026,4,1))[0]
    assert newer['last_unit_price_minor'] is None
    assert price_fields({'unit_price_text':'Order total $38.83'})=={}
    assert price_fields({'unit_price_text':'$0.00'})['unit_price_minor']==0
    assert price_fields({'line_total_text':'$10.78','purchase_quantity':2})['unit_price_minor']==539
    assert price_fields({'line_total_text':'$10.78'})=={}


@pytest.mark.asyncio
async def test_history_reads_only_observed_order_details_and_enriches_latest_unit_price():
    row={'id':ASIN,'url':URL,'title':'Paper','purchased_at':'January 1, 2026','order_key':'opaque'}
    details='https://www.amazon.com/uff/your-account/order-details?orderID=observed'
    page=Page([{'cards':1,'items':[row],'detail_requests':[{'url':details,'items':[{'id':ASIN,'order_key':'opaque'}]}]},
               {'items':[{'id':ASIN,'unit_price_text':'$5.97'}]}])
    page.search_progress=AsyncMock()
    result=await execute(page,{'shopping_action':'history','pages':1})
    phases=[call.args[0]['shopping_progress']['phase'] for call in page.search_progress.await_args_list]
    assert [phase for index,phase in enumerate(phases) if not index or phase!=phases[index-1]]==['order_list','order_details','analyzing']
    assert next(call.args[0]['shopping_progress'] for call in page.search_progress.await_args_list if call.args[0]['shopping_progress']['phase']=='order_details')['total']==1
    assert result['evidence']['result']['items'][0]['last_unit_price_minor']==597
    assert page.navigate.await_args.args[0]==details


def test_fresh_price_table_ignores_nested_layout_cells():
    from ai2apps.browser.shopping import DETAIL_PRICES_SCRIPT
    script='const fn='+DETAIL_PRICES_SCRIPT+r''';
const makeRow=()=>({cells:[],querySelectorAll(){return this.cells},querySelector(){return null}});
const header=makeRow(),row=makeRow(),nested=makeRow();
const cell=(text,parent)=>({innerText:text,textContent:text,closest:()=>parent});
header.cells=['','','Quantity','Weight','Total'].map(t=>cell(t,header));
row.cells=['','Coke','2','-','$10.78'].map(t=>cell(t,row));
row.cells.splice(2,0,cell('Nested product layout',nested));
row.querySelectorAll=function(selector){return selector.includes('gridcell')?this.cells:[]};
const a={href:'https://www.amazon.com/gp/product/B000T9WM62',innerText:'Coke',parentElement:null};
row.querySelector=()=>a;
const table={querySelectorAll:()=>[header,row,nested],querySelector:()=>header};
globalThis.location={pathname:'/uff/your-account/order-details/item-details'};
globalThis.document={title:'Items',querySelector:()=>null,querySelectorAll:s=>s.startsWith('table')?[table]:[a]};
console.log(JSON.stringify(fn().items));
'''
    items=json.loads(subprocess.check_output(['node','-e',script],text=True))
    assert items==[{'id':'B000T9WM62','purchase_quantity':2,'line_total_text':'$10.78'}]


@pytest.mark.parametrize("store", ["fresh", "whole_foods"])
@pytest.mark.asyncio
async def test_store_preparation_ignores_other_store_and_verifies_target_cart(monkeypatch, store):
    monkeypatch.setattr('ai2apps.browser.shopping.asyncio.sleep',AsyncMock())
    rect={'x':1,'y':2,'width':30,'height':20}
    controls={'asin':ASIN,'add':rect,'quantity':rect,'options':[1,2],'channel':store,'grocery_add':True,'cart_url':'https://www.amazon.com/cart/fresh'}
    ordinary={'recognized':True,'items':[{'id':ASIN,'quantity':5,'channel':'amazon'}]}
    page=Page([ordinary,controls,{'recognized':True,'items':[]},controls,
        {'recognized':True,'items':[{'id':ASIN,'quantity':2,'channel':store},{'id':ASIN,'quantity':5,'channel':'amazon'}]}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':2,'preferred_channel':store,'preferred_channel_url':URL+'?almBrandId=ObservedStore123'}})
    assert result['outcome']=='success' and result['evidence']['result']['quantity']==2
    assert page.navigate.await_args.args[0]=='https://www.amazon.com/cart/fresh'
    assert page.pointer_to.await_count==2


@pytest.mark.asyncio
async def test_same_channel_cart_quantity_can_complete_without_store_link():
    page=Page([{'recognized':True,'items':[{'id':ASIN,'quantity':2,'channel':'fresh'}]}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':2,'preferred_channel':'fresh'}})
    assert result['outcome']=='success'
    page.pointer_to.assert_not_called()


def test_observed_cart_routes_reject_checkout_and_external_links():
    from ai2apps.browser.shopping import observed_cart_url
    for value in ['https://evil.test/cart/fresh','https://www.amazon.com/checkout','https://www.amazon.com/cart/checkout']:
        with pytest.raises(ValueError):observed_cart_url(value)

@pytest.mark.asyncio
async def test_fresh_popup_quantity_uses_observed_option_and_native_input(monkeypatch):
    monkeypatch.setattr('ai2apps.browser.shopping.asyncio.sleep',AsyncMock())
    rect={'x':1,'y':2,'width':30,'height':20}
    controls={'asin':ASIN,'add':rect,'quantity':rect,'quantity_mode':'popup','channel':'fresh','grocery_add':True,'cart_url':'https://www.amazon.com/cart/localmarket'}
    page=Page([{'recognized':True,'items':[]},controls,{'recognized':True,'items':[]},controls,{'options':[{'value':2,'rect':rect}]},controls,{'recognized':True,'items':[{'id':ASIN,'quantity':2,'channel':'fresh'}]}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':2,'preferred_channel':'fresh','preferred_channel_url':URL+'?almBrandId=ObservedStore123'}})
    assert result['outcome']=='success'
    assert page.pointer_to.await_count==3
    page.connection.command.assert_not_called()


def test_product_url_store_selector_is_not_proof_of_actual_buybox_channel():
    from ai2apps.browser.shopping import CHANNEL_HELPER
    script='const document={}; const location={pathname:"/dp/B000123456",href:"https://www.amazon.com/dp/B000123456?almBrandId=QW1hem9uIEZyZXNo"};'+CHANNEL_HELPER+'console.log(JSON.stringify(shoppingChannel({id:"buybox",querySelectorAll:()=>[]})));'
    result=json.loads(subprocess.check_output(['node','-e',script],text=True))
    assert result['channel']=='unknown'


def test_shopping_dom_reader_includes_open_shadow_component_controls():
    from ai2apps.browser.shopping import SHOPPING_DOM_HELPER
    script=SHOPPING_DOM_HELPER+r'''
const button={id:'fresh-button'};
const shadow={querySelectorAll:s=>s==='button'?[button]:[]};
const host={shadowRoot:shadow};
const root={querySelectorAll:s=>s==='*'?[host]:[]};
console.log(JSON.stringify(shoppingQuery(root,'button').map(e=>e.id)));
'''
    assert json.loads(subprocess.check_output(['node','-e',script],text=True))==['fresh-button']

@pytest.mark.asyncio
async def test_nonempty_unreadable_fresh_cart_does_not_add_again():
    rect={'x':1,'y':2,'width':30,'height':20}
    controls={'asin':ASIN,'add':rect,'channel':'fresh','grocery_add':True,'cart_url':'https://www.amazon.com/cart/localmarket'}
    page=Page([{'recognized':True,'items':[]},controls,{'recognized':True,'empty':False,'items':[]}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':2,'preferred_channel':'fresh','preferred_channel_url':URL+'?almBrandId=ObservedStore123'}})
    assert result['outcome']=='needs_user'
    page.pointer_to.assert_not_called()

@pytest.mark.parametrize('brand', ['V0ZNTw', 'V0ZNTw=='])
def test_whole_foods_observed_links_preserve_grocery_mode(brand):
    from ai2apps.browser.shopping import purchase_url
    link=URL+'?almBrandId='+brand
    assert purchase_url({'id':ASIN,'url':URL,'preferred_channel':'whole_foods','preferred_channel_url':link})==link+'&fpw=alm'


def test_whole_foods_wfmo_link_is_explicit_channel_evidence():
    from ai2apps.browser.shopping import CHANNEL_HELPER
    script=CHANNEL_HELPER+r'''
const link={getAttribute:k=>k==='href'?'https://www.amazon.com/alm/storefront?almBrandId=V0ZNTw%3D%3D':null,textContent:''};
const root={querySelectorAll:s=>s.startsWith('[data-component="storeName"]')?[link]:[]};
console.log(JSON.stringify(shoppingChannel(root)));
'''
    result=json.loads(subprocess.check_output(['node','-e',script],text=True))
    assert result['channel']=='whole_foods'
    assert result['delivery_window']=='unknown'


@pytest.mark.asyncio
async def test_whole_foods_never_uses_fresh_buybox(monkeypatch):
    monkeypatch.setattr('ai2apps.browser.shopping.asyncio.sleep',AsyncMock())
    rect={'x':1,'y':2,'width':30,'height':20}
    controls={'asin':ASIN,'add':rect,'channel':'fresh','grocery_add':True,'cart_url':'https://www.amazon.com/cart/localmarket'}
    page=Page([{'recognized':True,'items':[]},controls])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'quantity':2,'preferred_channel':'whole_foods','preferred_channel_url':URL+'?almBrandId=V0ZNTw'}})
    assert result['outcome']=='needs_user'
    assert result['evidence']['reason']=='amazon_channel_confirmation_required'
    page.pointer_to.assert_not_called()

@pytest.mark.asyncio
async def test_mixed_store_report_verifies_each_store_independently():
    products=[{'id':ASIN,'url':URL,'quantity':2,'preferred_channel':store,'preferred_channel_url':URL+'?almBrandId='+brand} for store,brand in [('fresh','QW1hem9uIEZyZXNo'),('whole_foods','V0ZNTw')]]
    fresh='https://www.amazon.com/cart/localmarket?almBrandId=QW1hem9uIEZyZXNo'
    whole='https://www.amazon.com/cart/localmarket?almBrandId=V0ZNTw'
    page=Page([{'grocery_add':True,'channel':'fresh','cart_url':fresh},{'recognized':True,'items':[{'id':ASIN,'channel':'fresh','quantity':2}]}, {'grocery_add':True,'channel':'whole_foods','cart_url':whole},{'recognized':True,'items':[{'id':ASIN,'channel':'whole_foods','quantity':2}]}])
    result=await execute(page,{'shopping_action':'cart_report','items':products})
    assert result['outcome']=='success'
    stores=result['evidence']['result']['stores']
    assert [(s['channel'],s['page_url']) for s in stores]==[('fresh',fresh),('whole_foods',whole)]
    page.pointer_to.assert_not_called()


@pytest.mark.asyncio
async def test_mixed_report_does_not_count_fresh_as_whole_foods():
    products=[{'id':ASIN,'url':URL,'quantity':2,'preferred_channel':'amazon'}, {'id':ASIN,'url':URL,'quantity':2,'preferred_channel':'whole_foods','preferred_channel_url':URL+'?almBrandId=V0ZNTw'}]
    page=Page([{'recognized':True,'items':[{'id':ASIN,'channel':'amazon','quantity':2}]},{'grocery_add':True,'channel':'whole_foods','cart_url':'https://www.amazon.com/cart/localmarket'},{'recognized':True,'items':[{'id':ASIN,'channel':'fresh','quantity':5}]}])
    result=await execute(page,{'shopping_action':'cart_report','items':products})
    assert result['outcome']=='needs_user'
    assert result['evidence']['preferred_channel']=='whole_foods'
    assert result['evidence']['observed_quantity']==0
    page.pointer_to.assert_not_called()


def test_defaults_require_observed_repeat_cycle_and_eighty_percent_elapsed():
    from ai2apps.browser.shopping import screen_plan
    catalog=[{'id':'due','purchase_dates':['2026-09-01','2026-09-11','2026-09-21']}, {'id':'early','purchase_dates':['2026-09-01','2026-09-21']}, {'id':'single','purchase_dates':['2026-09-01']}, {'id':'same-day','purchase_dates':['2026-09-01','2026-09-01']}]
    plan={'items':[{'id':r['id'],'quantity':1,'score':95,'selected':True,'reason':'Daily consumable'} for r in catalog],'message':'Select all','search_query':''}
    result=screen_plan(plan,catalog,'en',today=date(2026,9,29))
    assert [r['id'] for r in result['items'] if r['selected']]==['due']
    assert all(r['score']<=49 for r in result['items'] if not r['selected'])
    assert len(result['items'])==4


def test_default_cycle_gate_preserves_user_requested_revision():
    from ai2apps.browser.shopping import screen_plan
    plan={'items':[{'id':'single','quantity':2,'score':50,'selected':True,'reason':'User request'}],'message':'Added','search_query':''}
    revised=screen_plan(plan,[{'id':'single','purchase_dates':['2026-09-01']}],message='Include this item')
    assert revised['items'][0]['selected'] is True
    assert revised['message']==plan['message']
    assert revised['items'][0]['due_bucket']=='unknown'


def test_cycle_gate_cannot_force_nonconsumable_selected_by_elapsed_time():
    from ai2apps.browser.shopping import screen_plan
    plan={'items':[{'id':'device','quantity':1,'score':5,'selected':False,'reason':'Not consumable'}],'message':'','search_query':''}
    result=screen_plan(plan,[{'id':'device','purchase_dates':['2026-01-01','2026-01-11']}],today=date(2026,9,29))
    assert not result['items'][0]['selected']


def test_refresh_and_recommend_sources_apply_cycle_gate():
    from ai2apps.browser.shopping import plan_source, refresh_source
    inputs={'type':'object','properties':{'locale':{'type':'string'},'pages':{'type':'integer'}},'required':['locale']}
    for source in [plan_source(inputs,[]),refresh_source(inputs,[])]:
        assert compile_source(source).valid
        screen=next(step for step in source['steps'] if step['name']=='screen')
        assert screen['arguments']['shopping_action']=='screen_plan'
        assert screen['arguments']['message']==''
    assert 'steps.screen.output' in refresh_source(inputs,[])['steps'][-1]['arguments']['assignments'][0]['expression']

@pytest.mark.parametrize('locale,expected',[
    ('zh-TW','購買日期不足'),('zh-Hant','購買日期不足'),('ja-JP','購入日'),
    ('ko','구매 날짜'),('fr-CA','Dates insuffisantes'),('es','Fechas insuficientes'),
    ('pt-BR','Datas insuficientes'),('ru','Недостаточно дат'),('en','Not enough'),
    ('zh-CN','购买日期不足'),('unsupported','Not enough'),
])
def test_cycle_screen_messages_follow_current_locale(locale, expected):
    from ai2apps.browser.shopping import screen_plan
    result=screen_plan({'items':[{'id':ASIN,'selected':True,'quantity':1,'score':90,'reason':'model explanation'}]},
                       [{'id':ASIN,'purchase_dates':['2026-10-01']}],locale=locale,today=date(2026,10,13))
    assert expected in result['items'][0]['reason']
    assert result['items'][0]['selected'] is False
    assert result['items'][0]['reason'].endswith('model explanation')


def test_failed_ai_step_can_recover_only_successful_native_history():
    from ai2apps.browser.shopping import history_checkpoint
    history = {'items': [{'id': ASIN, 'title': 'Paper'}], 'synced_at': '2026-10-14', 'pages_read': 3}
    response = {'outcome': 'success', 'evidence': {'operation': 'inspect', 'result': history}}
    assert history_checkpoint([response]) == history
    assert history_checkpoint([{**response, 'outcome': 'failed'}]) is None
    assert history_checkpoint([{'outcome': 'success', 'evidence': {'operation': 'ai.transform', 'result': history}}]) is None


def test_recommend_reuses_failed_refresh_checkpoint_without_browser_read(broker,monkeypatch):
    service,mount,principal=broker;mount.declaration=shopping_declaration()
    prior={'status':'failed','history_checkpoint':True,'capability':'refresh_list','profile_key':'default',
        'result':{'assigned':{'shopping_report':{'history':{'items':frequencies([
            {'id':ASIN,'url':URL,'title':'Paper','purchased_at':'January 1, 2026'}])}}}}}
    monkeypatch.setattr(service,'task',lambda *a:prior)
    task=service.submit('mount',principal,capability='recommend',parameters={'source_tasks':['prior'],'locale':'zh'},profile='default',request_id='resume-plan')
    from ai2apps.browser.tasks import BrowserTaskRepository
    program,_=BrowserTaskRepository(service.runtime.database).program('owner',task['id'])
    assert all(s.get('arguments', {}).get('shopping_action') != 'history' for s in program['steps'])
    assert program['steps'][0]['operation'] == 'ai.transform'
    assert task['browser_context']['model_profile']=='privacy'
    prior['history_checkpoint']=False
    with pytest.raises(StudioCapabilityError):
        service.submit('mount',principal,capability='recommend',parameters={'source_tasks':['prior'],'locale':'zh'},profile='default',request_id='reject-plan')


@pytest.mark.parametrize('capability,parameters', [('history', {'pages':3}),
    ('refresh_list', {'pages':3,'locale':'zh','previous_task':''})])
def test_missing_privacy_model_rejected_before_task_is_queued(broker, capability, parameters):
    service,mount,principal=broker;mount.declaration=shopping_declaration()
    service.runtime.model_manager.resolve_default_model=lambda *a, **kw: None
    from ai2apps.browser.tasks import BrowserTaskRepository
    before=BrowserTaskRepository(service.runtime.database).list('owner')
    with pytest.raises(StudioCapabilityError) as error:
        service.submit('mount',principal,capability=capability,parameters=parameters,profile='default',request_id='no-model')
    assert error.value.code=='privacy_model_required'
    assert BrowserTaskRepository(service.runtime.database).list('owner')==before


@pytest.mark.asyncio
async def test_history_progress_uses_durable_page_callback():
    from ai2apps.browser.shopping import report_history_progress
    progress=[]
    async def publish(value): progress.append(value)
    page=SimpleNamespace(search_progress=publish)
    await report_history_progress(page,'order_list',page=1,page_limit=3)
    await report_history_progress(page,'order_details',page=1,current=2,total=8)
    await report_history_progress(page,'analyzing',orders_read=8)
    phases=[p['shopping_progress']['phase'] for p in progress]
    assert [phase for index,phase in enumerate(phases) if not index or phase!=phases[index-1]]==['order_list','order_details','analyzing']
    assert next(p['shopping_progress'] for p in progress if p['shopping_progress']['phase']=='order_details')['current']==2

@pytest.mark.asyncio
async def test_cold_history_document_is_reobserved_before_layout_failure():
    page=Page([{'cards':0,'empty':False,'text_length':0}, {'cards':0,'empty':True,'items':[]}])
    page.wait_stable=AsyncMock()
    result=await execute(page,{'shopping_action':'history','pages':1})
    assert result['outcome']=='success'
    assert page.wait_stable.await_count==2

@pytest.mark.asyncio
async def test_history_blank_document_preserves_readiness_diagnostics():
    page=Page([{'cards':0,'empty':False,'text_length':0}]*2)
    page.wait_stable=AsyncMock()
    result=await execute(page,{'shopping_action':'history','pages':1})
    assert result['evidence']['reason']=='amazon_history_document_not_ready'
    assert result['evidence']['text_length']==0

@pytest.mark.parametrize('has_submit,expected',[(True,True),(False,False)])
def test_visible_fresh_wrapper_requires_submit_and_local_store_badge(has_submit,expected):
    from ai2apps.browser.shopping import CONTROLS_SCRIPT,CHANNEL_HELPER,SHOPPING_DOM_HELPER
    script=r'''
const ai2appsDOMVisible=e=>!!e&&e.visible!==false;
const badge={visible:true,getAttribute:k=>k==='alt'?'Amazon Fresh':null};
const box={querySelectorAll:s=>s==='img,[role=img]'?[badge]:[],querySelector:()=>null};
const candidate={textContent:'Add to cart',visible:true,parentElement:box,matches:s=>s==='.a-button',getAttribute:()=>null,closest:()=>null,querySelector:s=>HAS_SUBMIT?{}:null,getBoundingClientRect:()=>({x:1,y:2,width:100,height:30})};
const document={body:{},title:'Banana',getElementById:()=>null,querySelector:()=>null,querySelectorAll:s=>s.includes('.a-button-text')?[candidate]:[]};
const location={pathname:'/dp/B000123456'};
'''.replace('HAS_SUBMIT','true' if has_submit else 'false')+CHANNEL_HELPER+SHOPPING_DOM_HELPER+'console.log(JSON.stringify(('+CONTROLS_SCRIPT+')()));'
    result=json.loads(subprocess.check_output(['node','-e',script],text=True))
    assert result['grocery_add'] is expected
    if expected:assert result['channel']=='fresh' and result['add']['width']==100
    else:assert result['add'] is None

@pytest.mark.asyncio
async def test_unverified_cart_explains_observation_and_next_steps():
    page=Page([{'recognized':True,'items':[{'id':ASIN,'quantity':1}]}])
    result=await execute(page,{'shopping_action':'cart_item','item':{'id':ASIN,'url':URL,'title':'Observed yogurt','quantity':2}})
    evidence=result['evidence']
    assert result['outcome']=='needs_user'
    assert evidence['reason']=='amazon_cart_add_unverified'
    message=evidence['assistance_message']
    for text in ['Observed yogurt','目标数量 2','读取数量 1','前往页面处理','不要重复点击加购','已处理，继续']:
        assert text in message
    assert '页面显示登录' not in message
    page.pointer_to.assert_not_called()

@pytest.mark.parametrize('labels,expected', [(['2. Click to change quantity'],2),(['Current quantity 2'],2),(['Qty: 2'],2),(['Current quantity 0'],0),(['Qty: 2','Current quantity 1'],0)])
def test_cart_prefers_visible_quantity_and_rejects_conflicts(labels,expected):
    from ai2apps.browser.shopping import CART_SCRIPT
    # Evaluate the actual production quantity-reading block against scoped controls.
    quantity_source=CART_SCRIPT[CART_SCRIPT.index(' const visibleQuantities='):CART_SCRIPT.index(' return {id:c.dataset.asin')]
    script="const labels="+json.dumps(labels)+r''';
const ai2appsDOMVisible=e=>!e.hidden;
const shoppingQuery=()=>labels.map(label=>({hidden:false,getAttribute:()=>label}));
const c={dataset:{quantity:'1'},querySelector:()=>({value:'1'})};
const label='';
'''+quantity_source+'console.log(JSON.stringify(quantity));'
    quantity=json.loads(subprocess.check_output(['node','-e',script],text=True))
    assert quantity==expected
