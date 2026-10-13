import json
from pathlib import Path
from datetime import date
from unittest.mock import AsyncMock
from types import SimpleNamespace
import pytest
from ai2apps.browser.gifts import gift_source,gift_inputs,screen_gifts
from ai2apps.browser.shopping import execute,product_rows
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.browser.mini_apps import validate_web_agent

A='B000123456';B='B000123457'
def product(key=A,price='$19.99'):
 return {'id':key,'title':'Observed gift','url':'https://www.amazon.com/dp/'+key,'price':price,'image_url':'https://m.media-amazon.com/images/I/example.jpg'}

def test_gift_sources_compile_and_default_to_normal_with_optional_privacy():
 root=Path(__file__).resolve().parents[2]
 mini=json.loads((root/'packages/ai2apps-shopping-pro/app.yaml').read_text())['mini_apps'][0]
 entries=validate_web_agent(mini)
 gifts=[e for e in entries if e['id'].startswith('gift_')]
 assert len(gifts)==3 and all(e['model_profile']=='normal' for e in gifts)
 assert mini['web_agent']['model_profile']=='privacy'
 assert 'model_profile' not in gift_inputs()['required']
 for revise in [False,True]:
  source=gift_source(gift_inputs(revise));assert compile_source(source).valid
  assert all(s['ai']['tier']=='standard' for s in source['steps'] if 'ai' in s)
  assert source['steps'][1]['arguments']['shopping_action']=='gift_search'
  assert 'purchase history' in source['steps'][0]['ai']['instruction']
  assert 'private names' in source['steps'][0]['ai']['instruction']

def test_verified_gifts_exclude_over_budget_and_never_accept_fabricated_metadata():
 plan={'items':[{'id':A,'score':95,'reason':'Good fit','price':'$0.01','url':'https://evil.test'},
                {'id':B,'score':90,'reason':'Too costly'}],'message':'Observed recommendations'}
 result=screen_gifts(plan,[product(),product(B,'$99.99')],5000)
 assert len(result['items'])==1
 assert result['items'][0]['price']=='$19.99' and result['items'][0]['unit_price_minor']==1999
 assert result['items'][0]['url']=='https://www.amazon.com/dp/'+A
 assert 'last_purchase' not in result['items'][0]

@pytest.mark.parametrize('ids',[[A,A],['B999999999']])
def test_gift_model_cannot_add_unobserved_or_duplicate_products(ids):
 with pytest.raises(ValueError):screen_gifts({'items':[{'id':i,'score':80,'reason':'x'} for i in ids]},[product()],5000)

def test_unknown_prices_remain_unverified_and_gift_report_provenance_is_observed():
 p=product(price='');result=screen_gifts({'items':[{'id':A,'score':80,'reason':'Price unverified'}]},[p],5000)
 assert 'unit_price_minor' not in result['items'][0]
 report={'assigned':{'gift_report':{'products':[p],'recommendations':result}}}
 assert product_rows(report)==[p]

@pytest.mark.asyncio
async def test_gift_read_deduplicates_searches_and_stops_for_login():
 page=SimpleNamespace(navigate=AsyncMock(),pause=AsyncMock(),snapshot=AsyncMock(return_value={'url':'https://www.amazon.com/s'}),call_json=AsyncMock(side_effect=[{'items':[product()]},{'items':[product()]}]))
 result=await execute(page,{'shopping_action':'gift_search','queries':['gift one','gift two']})
 assert len(result['evidence']['result']['items'])==1
 assert page.pause.await_count==2
 page.call_json=AsyncMock(return_value={'blocked':True})
 result=await execute(page,{'shopping_action':'gift_search','queries':['gift one','gift two']})
 assert result['outcome']=='needs_user'
 assert page.call_json.await_count==1

@pytest.mark.parametrize('message,expected',[
    ('No electronics',5000),('Budget $30',3000),('预算改为 30 美元',3000),
    ('予算30ドル',3000),('30 cm size',5000),
])
def test_budget_changes_require_an_explicit_amount(message,expected):
    result=screen_gifts({'items':[]},[],3000,original_budget=5000,message=message)
    assert result['budget_minor']==expected

@pytest.mark.asyncio
@pytest.mark.parametrize('capability,action,profile,allowed',[
 ('gift_recommend','gift_search','normal',True),
 ('gift_revise','screen_gifts','normal',True),
 ('gift_prepare_cart','cart_item','normal',True),
 ('history','gift_search','normal',False),
 ('gift_recommend','history','normal',False),
 ('history','history','privacy',True),
])
async def test_executor_limits_normal_shopping_to_gift_tasks(monkeypatch,capability,action,profile,allowed):
 from ai2apps.browser.background_executor import BackgroundExecutor
 from ai2apps.browser.tasks import BrowserTaskRepository
 monkeypatch.setattr(BrowserTaskRepository,'get',lambda *args:{'capability':capability,'browser_context':{'model_profile':profile}})
 fake=AsyncMock(return_value={'outcome':'success'})
 monkeypatch.setattr('ai2apps.browser.shopping.execute',fake)
 page=SimpleNamespace(context_id='page',validate_context=AsyncMock())
 run=SimpleNamespace(input={'parameters':{'model_profile':profile,'owner_user_id':'owner','browser_task_id':'task','caller_app_id':'mini:ai2apps.shopping-pro'}})
 result=await BackgroundExecutor(SimpleNamespace(database=None)).execute(page,{'step':{'operation':'inspect','arguments':{'shopping_action':action}}},run)
 assert result['outcome']==('success' if allowed else 'restricted')
 assert fake.await_count==int(allowed)
