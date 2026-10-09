from types import SimpleNamespace as NS
import pytest
from ai2apps.intelligence import entity_categories as categories, service
from ai2apps.intelligence.store import IntelligenceStore

@pytest.mark.asyncio
async def test_ai_plan_supports_custom_names_order_and_duplicate_rejection(monkeypatch):
    async def model(*args):
        validate=args[-1]
        with pytest.raises(ValueError):validate({'categories':[{'name':'Club','description':'a'},{'name':'Club','description':'b'}]})
        return validate({'categories':[{'name':'俱乐部','description':'足球俱乐部'},{'name':'球员','description':'职业球员'}]})
    monkeypatch.setattr(service,'model_json',model)
    result=await categories.plan(None,None,None,{'name':'足球'})
    assert [c['name'] for c in result['categories']]==['俱乐部','球员']
    assert result['default_id']==result['categories'][0]['id']

@pytest.mark.asyncio
async def test_channel_owned_assignment_and_cas(tmp_path,monkeypatch):
    store=IntelligenceStore(tmp_path);channel=store.save_channel('a',{'name':'Football','interests':'Clubs','interval_hours':0})
    async def model(*args):
        validate=args[-1]
        if 'categories' in args[-2]:
            cat=args[-2]['categories'][0]['id']
            with pytest.raises(ValueError):validate({'assignments':[{'entity_id':'foreign','category_id':cat}]})
            return validate({'assignments':[{'entity_id':'shared','category_id':cat}]})
        return validate({'categories':[{'name':'俱乐部','description':'football clubs'}]})
    monkeypatch.setattr(service,'model_json',model)
    monkeypatch.setattr(categories.Repository,'snapshot',lambda self,owner:{'entities':[{'id':'shared','name':'Club','kind':'organization','aliases':[],'facts':[],'channel_ids':[channel['id']]}]})
    result=await categories.organize(None,None,NS(actor_user_id='a'),store,channel['id'])
    assert result['assignments']['shared']==result['default_id']
    with pytest.raises(ValueError):categories.persist(store,'a',channel['id'],None,result)
    with pytest.raises(KeyError):categories.persist(store,'other',channel['id'],None,result)
