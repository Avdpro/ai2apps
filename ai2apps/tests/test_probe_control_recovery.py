"""Cross-site fixtures: recovery changes bindings, never operations or authority."""
from copy import deepcopy
from unittest.mock import AsyncMock
import pytest
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.agent_builder.probe_contract import coverage
from ai2apps.browser.control_recovery import ControlRuleRecovery
from ai2apps.browser.visual_recovery import VisualControlRecovery, VisualRecoveryUnavailable, VisualActionUncertain
from ai2apps.tests.test_webagent_visual_recovery import Page, setup


def source(ref='e1',operation='click'):
    return {'agent_type':'web','site_scope':['https://fixture.test/**'],'steps':[{
        'name':'one','operation':operation,'target':{'ref':ref},'arguments':{},
        'execution':{'mode':'compiled'},'on':{'success':'done','failed':'failed'}}]}

@pytest.mark.parametrize('tag',['button','span','div'])
def test_compiler_accepts_all_observed_control_tags(tag):
    probe={'items':[{'ref':'e1','tag':tag,'role':'button'}]}
    result=compile_source(source(),probe=probe)
    assert result.valid,result.report
    assert result.report['probe_coverage']['count']==1
    assert coverage(probe)['custom_controls']==int(tag!='button')

@pytest.mark.parametrize('row',[{'ref':'e2'},{'ref':'e1','disabled':True},{'ref':'e1','sensitive':True}])
def test_compiler_rejects_absent_or_unavailable_probe_ref(row):
    assert not compile_source(source(),probe={'items':[row]}).valid

def test_compiler_cannot_type_into_custom_button():
    assert not compile_source(source(operation='input'),probe={'items':[{'ref':'e1','tag':'span','role':'button'}]}).valid

@pytest.mark.asyncio
@pytest.mark.parametrize('host,tag',[('store.fixture.test','span'),('workspace.fixture.test','div')])
async def test_refresh_then_target_repair_then_review_with_immutable_operation(host,tag):
    runtime,run,payloads=setup([{'ref':'e1'},{'confirmed':True}]);page=Page()
    page.rows[0]['tag']=tag;page.rows[0]['text']='+';page.wait_stable=AsyncMock()
    original=page.snapshot
    async def snapshot(**kwargs):
        result=await original(**kwargs);result['url']=f'https://{host}/controls';return result
    page.snapshot=snapshot
    visual=VisualControlRecovery(runtime,run,[f'https://{host}/**'])
    target=await ControlRuleRecovery(visual).resolve(page,'Increase selected item once',step={'operation':'click','arguments':{'unchanged':1}},lookup=AsyncMock(return_value=None),allowed_refs={'e1'})
    assert target['ref']=='e1' and target['_visual']
    assert [e['phase'] for e in visual.evidence]==['reobserve','repair','rule_validated','review']
    assert visual.evidence[2]['target_tag']==tag
    assert len(payloads[0]['messages'][1]['content'])==1 # DOM repair uses no image
    assert len(payloads[1]['messages'][1]['content'])==2 # marked review after validation
    page.pointer_to.assert_not_called();page.wait_stable.assert_awaited_once()

@pytest.mark.asyncio
async def test_original_locator_recovers_without_target_generation():
    runtime,run,payloads=setup([{'confirmed':True}]);page=Page()
    visual=VisualControlRecovery(runtime,run,['https://arbitrary.test/**'])
    result=await ControlRuleRecovery(visual).resolve(page,'one',lookup=AsyncMock(return_value={'ref':'e1'}))
    assert result['ref']=='e1'
    assert [e['phase'] for e in visual.evidence]==['reobserve','rule_validated','review']
    assert len(payloads)==1

@pytest.mark.asyncio
async def test_changed_document_after_generated_rule_never_dispatches():
    runtime,run,_=setup([{'ref':'e1'}]);page=Page();original=page.snapshot;reads=0
    async def snapshot(**kwargs):
        nonlocal reads
        reads+=1
        if reads>1:page.viewport['document_token']='replacement'
        return await original(**kwargs)
    page.snapshot=snapshot
    visual=VisualControlRecovery(runtime,run,['https://arbitrary.test/**'])
    with pytest.raises(VisualRecoveryUnavailable,match='Probe changed'):
        await ControlRuleRecovery(visual).resolve(page,'one',lookup=AsyncMock(return_value=None))
    page.pointer_to.assert_not_called()

@pytest.mark.asyncio
async def test_unobserved_model_ref_cannot_dispatch_when_visual_locating_disabled():
    runtime,run,_=setup([{'ref':'e999'}]);page=Page()
    visual=VisualControlRecovery(runtime,run,['https://arbitrary.test/**'],policy={'visual_locating':False})
    with pytest.raises(VisualRecoveryUnavailable):await ControlRuleRecovery(visual).resolve(page,'one')
    page.pointer_to.assert_not_called()

@pytest.mark.asyncio
@pytest.mark.parametrize('verified',[True,False])
async def test_native_ack_failure_always_reads_owner_state_without_replay(verified):
    runtime,run,_=setup();page=Page();page.pointer_to.side_effect=TimeoutError('lost acknowledgement')
    readback=AsyncMock(return_value={'verified':verified,'observed_quantity':2 if verified else 1})
    visual=VisualControlRecovery(runtime,run,['https://arbitrary.test/**'])
    with pytest.raises(VisualActionUncertain) as caught:
        await visual.click(page,'one',allowed_refs={'e1'},readback=readback)
    page.pointer_to.assert_awaited_once();readback.assert_awaited_once()
    assert caught.value.evidence['readback']['verified'] is verified
    assert caught.value.evidence['automatic_replay_allowed'] is False

@pytest.mark.asyncio
async def test_crash_readback_never_creates_unbound_recovery_context():
    from types import SimpleNamespace as NS
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    runner=object.__new__(BackgroundBrowserRunner);runner.page_for=AsyncMock()
    result=await runner.uncertain_readback(NS(input={'parameters':{}}))
    assert result['reason']=='original_context_not_bound';runner.page_for.assert_not_called()

@pytest.mark.asyncio
async def test_crash_readback_observes_only_original_bound_context():
    from types import SimpleNamespace as NS
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    runner=object.__new__(BackgroundBrowserRunner);page=Page();runner.page_for=AsyncMock(return_value=page)
    run=NS(input={'parameters':{'browser_context':{'bidi_context':'owned'}}})
    result=await runner.uncertain_readback(run)
    assert result['status']=='observed' and result['verified_effect'] is False
    runner.page_for.assert_awaited_once_with(run);page.pointer_to.assert_not_called()

@pytest.mark.asyncio
async def test_offscreen_probe_control_is_scrolled_then_revalidated():
    runtime,run,_=setup([{'ref':'e1'},{'confirmed':True}]);page=Page();page.rows[0]['rect'][1]=400
    async def scroll(delta):
        page.rows[0]['rect'][1]-=delta;page.viewport['scroll_y']+=delta
    page.scroll=AsyncMock(side_effect=scroll)
    visual=VisualControlRecovery(runtime,run,['https://arbitrary.test/**'])
    result=await ControlRuleRecovery(visual).resolve(page,'Increase widget X',allowed_refs={'e1'})
    assert result['ref']=='e1';page.scroll.assert_awaited_once()
    assert [e['phase'] for e in visual.evidence]==['reobserve','repair','scroll_reobserve','rule_validated','review']
    page.pointer_to.assert_not_called()

@pytest.mark.asyncio
async def test_native_scroll_waits_for_actual_geometry_feedback():
    from types import SimpleNamespace as NS
    from ai2apps.browser.background_page import BackgroundPage
    page=BackgroundPage(NS(command=AsyncMock()),'owned',interaction_mode=lambda url:'natural')
    page.mode=AsyncMock(return_value='natural');page.pause=AsyncMock();page.activate_for_input=AsyncMock()
    page.call_json=AsyncMock(side_effect=[{'x':100,'y':50},[[0,0]],[[0,0]],[[0,600]],[[0,600]],[[0,600]]])
    result=await page.scroll(600)
    assert result=={'settled':True,'changed':True}
    page.activate_for_input.assert_awaited_once()
    args=page.connection.command.call_args.args[1]
    action=args['actions'][0]['actions'][0]
    assert action['duration']==0 and action['deltaY']==600
    page.connection.command.assert_awaited_once()

@pytest.mark.asyncio
@pytest.mark.parametrize('host,tag',[('store.fixture.test','span'),('workspace.fixture.test','div')])
async def test_dom_ambiguity_escalates_to_visual_selection_and_binding_before_any_action(host,tag):
    runtime,run,payloads=setup([{'ref':None},{'ref':'e1'},{'confirmed':True},{'confirmed':True}]);page=Page()
    page.rows[0]['tag']=tag
    original=page.snapshot
    async def snapshot(**kwargs):
        result=await original(**kwargs);result['url']=f'https://{host}/controls';return result
    page.snapshot=snapshot
    visual=VisualControlRecovery(runtime,run,[f'https://{host}/**'],policy={'visual_locating':True,'visual_review':'on_recovery'})
    target=await ControlRuleRecovery(visual).resolve(page,'Increase selected widget',step={'operation':'click','arguments':{}},lookup=AsyncMock(return_value=None))
    assert target['ref']=='e1'
    assert [v['phase'] for v in visual.evidence]==['reobserve','repair','select','review','rule_validated','review']
    assert len(payloads[1]['messages'][1]['content'])==2
    page.pointer_to.assert_not_called()


def test_unresolved_guidance_uses_owner_step_without_raw_internal_error_or_business_identity():
    from ai2apps.browser.background_executor import recovery_assistance
    for label in ('调整所选项目数量','选择文档目标文件夹'):
        message=recovery_assistance({'arguments':{'assistance_label':label,'locale':'zh'}},[{'phase':'select'}],'DOM repair did not select a unique observed target')
        assert label in message and '视觉复核' in message and '关闭弹窗' in message
        assert 'DOM repair' not in message and '尚未执行' in message
    message=recovery_assistance({'arguments':{'assistance_label':'Select widget','locale':'en'}},[],'Current task model has no declared image-input capability')
    assert 'Select widget' in message and 'configure a vision-capable' in message
