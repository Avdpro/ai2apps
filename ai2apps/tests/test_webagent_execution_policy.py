"""Cross-provider policy tests use real compiler/executor and a fixture BiDi page."""
import json
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from ai2apps.agent_builder.execution_policy import resolve_policy, inherit_policy, verified_state
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.browser.visual_recovery import VisualControlRecovery
from ai2apps.browser.background_executor import BackgroundExecutor
from ai2apps.tests.test_webagent_visual_recovery import setup, Page

@pytest.mark.parametrize('provider',['owner.alpha','package.beta'])
def test_owner_floor_survives_task_and_nested_policy(provider):
    source={'name':provider,'agent_type':'web','execution_policy':{'visual_review':'off'},
            'minimum_execution_policy':{'visual_review':'always'},
            'steps':[{'name':'inspect','operation':'inspect','on':{'success':'done','failed':'failed'}}]}
    compiled=compile_source(source)
    assert compiled.valid
    assert compiled.ir['execution_policy']['visual_review']=='always'
    assert inherit_policy(compiled.ir['execution_policy'],{'visual_review':'off'})['visual_review']=='always'
    assert compiled.ir['minimum_execution_policy']=={'visual_review':'always'}

@pytest.mark.parametrize('bad',[{'readback':False},{'visual_review':'sometimes'},{'visual_locating':1},{'provider_override':'yes'}])
def test_invalid_policy_rejected_by_compiler(bad):
    result=compile_source({'agent_type':'web','execution_policy':bad,'steps':[{'name':'x','operation':'inspect'}]})
    assert not result.valid
    assert any(e['code']=='invalid_execution_policy' for e in result.report['errors'])

@pytest.mark.asyncio
async def test_direct_dom_control_always_reviewed_without_visual_locating():
    runtime,run,payloads=setup([{'confirmed':True},{'confirmed':True}]);page=Page()
    page.find_target=AsyncMock(return_value={**page.rows[0],'name':'Increase widget X',
        'rect':{'x':20,'y':20,'width':40,'height':20}})
    page.related_windows=AsyncMock(return_value=[]);page.pointer_to.return_value={'x':40,'y':30}
    result=await BackgroundExecutor(runtime).execute(page,{'step':{'operation':'click','target':{'intent':'Increase widget X'},'arguments':{}},
        'site_scope':['https://arbitrary.test/**'],'execution_policy':{'visual_locating':False,'visual_review':'always'}},run)
    assert result['outcome']=='success'
    assert [e['phase'] for e in result['evidence']['result']['visual_recovery']]==['review','after']
    assert len(payloads)==2
    page.pointer_to.assert_awaited_once()

@pytest.mark.asyncio
async def test_article_off_no_screenshots_but_real_readback_kept():
    runtime,run,payloads=setup();page=Page()
    page.read_page=AsyncMock(return_value={'outcome':'success','url':'https://arbitrary.test/article','text':'Actual fixture article'})
    result=await BackgroundExecutor(runtime).execute(page,{'step':{'operation':'read_page','arguments':{'url':'https://arbitrary.test/article'}},
        'site_scope':['https://arbitrary.test/**'],'execution_policy':{'visual_locating':False,'visual_review':'off'}},run)
    assert result['outcome']=='success' and result['evidence']['result']['text']=='Actual fixture article'
    assert 'after' in result['evidence']
    page.read_page.assert_awaited_once();page.connection.command.assert_not_called();assert not payloads

@pytest.mark.asyncio
@pytest.mark.parametrize('allowed',[True,False])
@pytest.mark.parametrize('verdict',[True,False,None])
async def test_visual_resolves_only_unknown_owner_evidence(allowed,verdict):
    runtime,run,payloads=setup([{'confirmed':True}]);page=Page()
    policy={'allow_visual_state_confirmation':allowed,'visual_review':'always'}
    result=await VisualControlRecovery(runtime,run,['https://arbitrary.test/**'],policy=policy).verify(page,'Observe requested state',{'verified':verdict})
    assert result['state_verified'] is (verdict if verdict is not None else allowed)
    page.pointer_to.assert_not_called();assert len(payloads)==1

@pytest.mark.asyncio
async def test_off_verify_reacquires_dom_without_model():
    runtime,run,payloads=setup();page=Page();page.snapshot=AsyncMock(wraps=page.snapshot)
    result=await VisualControlRecovery(runtime,run,['https://arbitrary.test/**'],policy={'visual_review':'off'}).verify(page,'Read only',{'verified':True})
    assert result['state_verified'] and result['visually_verified'] is None
    page.snapshot.assert_awaited_once();page.connection.command.assert_not_called();assert not payloads


def test_live_owner_source_declarations():
    from ai2apps.browser.shopping import cart_source
    assert compile_source(cart_source({},[])).ir['execution_policy']['visual_review']=='always'
    root=Path(__file__).resolve().parents[2]
    document=json.loads((root/'packages/ai2apps-web-reader/app.yaml').read_text())
    for entry in document['mini_apps'][0]['web_agent']['capabilities']:
        policy=compile_source(entry['source']).ir['execution_policy']
        assert policy['visual_review']==('on_recovery' if entry['id']=='article' else 'off')
        assert policy['visual_locating'] is (entry['id']=='article') and policy['readback']

@pytest.mark.asyncio
async def test_observed_offscreen_ref_scrolls_then_recaptures():
    runtime,run,_=setup();page=Page();page.rows[0]['rect'][1]=140
    async def scroll(delta):
        page.rows[0]['rect'][1]=20
        page.viewport['scroll_y']+=delta
    page.scroll=AsyncMock(side_effect=scroll)
    result=await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(page,'One observed control',allowed_refs={'e1'})
    assert result['performed']
    page.scroll.assert_awaited_once();page.pointer_to.assert_awaited_once()

@pytest.mark.asyncio
async def test_raw_owner_rect_matches_only_snapshot_precision_then_dom_ref():
    runtime,run,_=setup([{'confirmed':True},{'confirmed':True}]);page=Page()
    page.rows[0]['rect']=[20.1,20.2,40.3,20.4]
    recovery=VisualControlRecovery(runtime,run,['https://arbitrary.test/**'],policy={'visual_review':'always'})
    target=await recovery.review_target(page,{'rect':{'x':20.123456,'y':20.234567,'width':40.345678,'height':20.412345}},'One control')
    assert target['ref']=='e1' and target['rect']=={'x':20.1,'y':20.2,'width':40.3,'height':20.4}
    result=await recovery.click(page,'One control',target=target,readback=AsyncMock(return_value={'verified':True}))
    assert result['state_verified'];page.pointer_to.assert_awaited_once()

@pytest.mark.asyncio
async def test_snapshot_precision_does_not_authorize_ambiguous_or_other_rect():
    runtime,run,_=setup();page=Page()
    recovery=VisualControlRecovery(runtime,run,['https://arbitrary.test/**'],policy={'visual_review':'always'})
    from ai2apps.browser.visual_recovery import VisualRecoveryUnavailable
    with pytest.raises(VisualRecoveryUnavailable):
        await recovery.review_target(page,{'rect':{'x':20.16,'y':20,'width':40,'height':20}},'One control')
    page.rows.append({**page.rows[0],'ref':'e3'})
    with pytest.raises(VisualRecoveryUnavailable):
        await recovery.review_target(page,{'rect':{'x':20.01,'y':20,'width':40,'height':20}},'One control')
    page.pointer_to.assert_not_called();page.connection.command.assert_not_called()
