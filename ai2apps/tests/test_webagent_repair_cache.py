"""Persistent cache reuse and invalidation across unrelated WebAgent owners/sites."""
from copy import deepcopy
from unittest.mock import AsyncMock
import json
import pytest
from ai2apps.browser.control_recovery import ControlRuleRecovery
from ai2apps.browser.visual_recovery import VisualControlRecovery,VisualActionUncertain
from ai2apps.browser.repair_cache import RepairCache,settle
from ai2apps.tests.test_webagent_visual_recovery import Page,setup
from ai2apps.tests.test_browser_background import JournalDatabase


def context(tmp_path,host='alpha.test',tag='span'):
    runtime,run,payloads=setup([{'ref':'e1'},{'confirmed':True},{'confirmed':True},{'confirmed':True},{'confirmed':True}])
    runtime.database=JournalDatabase(tmp_path/'cache.sqlite')
    run.input['parameters'].update(caller_app_id='arbitrary.owner',ir={'name':'Example Web Task','source_digest':'original-v1'})
    page=Page();page.rows[0]['tag']=tag
    for i,row in enumerate(page.rows):row['structure']=f'HTML/BODY/SECTION/{tag}:{i}'
    original=page.snapshot
    async def snapshot(**kwargs):
        result=await original(**kwargs);result['url']=f'https://{host}/work';return result
    page.snapshot=snapshot
    scopes=[f'https://{host}/**'];step={'id':'one','operation':'click','target':{'intent':'old label'},'arguments':{}}
    def visual():return VisualControlRecovery(runtime,run,scopes)
    return runtime,run,page,payloads,step,visual

@pytest.mark.asyncio
@pytest.mark.parametrize('host,tag',[('alpha.test','span'),('beta.test','div')])
async def test_second_run_rebinds_new_refs_without_generating_rule(tmp_path,host,tag):
    runtime,run,page,payloads,step,visual=context(tmp_path,host,tag)
    first=visual();target=await ControlRuleRecovery(first).resolve(page,'one',step=step)
    cache=RepairCache.for_step(first,page,step,'one',(await page.snapshot())['url'])
    assert not cache.exists()
    result=await first.click(page,'one',target=target,readback=AsyncMock(return_value={'verified':True}))
    assert result['performed'] and cache.exists()
    assert [e['phase'] for e in first.evidence].count('repair')==1
    page.rows[0]['ref']='e101';page.rows[1]['ref']='e102';page.rows[0]['rect'][0]+=5
    run.id='second-run'
    second=visual();target=await ControlRuleRecovery(second).resolve(page,'one',step=step)
    assert target['ref']=='e101'
    assert {'phase':'repair_cache','status':'hit'} in second.evidence
    assert not any(e['phase'] in ('repair','select') for e in second.evidence)
    await second.click(page,'one',target=target,readback=AsyncMock(return_value={'verified':True}))
    assert len(payloads)==5
    assert page.pointer_to.await_count==2
    encoded=json.dumps(cache.read())
    assert 'e101' not in encoded and 'e1"' not in encoded and 'old label' not in encoded

@pytest.mark.asyncio
@pytest.mark.parametrize('change',['structure','label','disabled','scope','source','generation','arguments','owner','profile','url','ambiguous'])
async def test_invalidated_or_isolated_cache_never_supplies_old_target(tmp_path,change):
    runtime,run,page,payloads,step,visual=context(tmp_path)
    initial=visual();target=await ControlRuleRecovery(initial).resolve(page,'one',step=step)
    settle(target,{'readback':{'verified':True}},runtime.database)
    snapshot=await page.snapshot();candidates=initial.candidates(snapshot,{**page.viewport,'context':'owned'},None)
    cache=RepairCache.for_step(initial,page,step,'one',snapshot['url']);assert cache.exists()
    if change=='structure':snapshot['items'][0]['structure']+='wrapper'
    elif change=='label':snapshot['items'][0]['text']='Different action'
    elif change=='disabled':snapshot['items'][0]['disabled']=True
    elif change=='scope':candidates=candidates[1:]
    elif change=='source':run.input['parameters']['ir']['source_digest']='v2'
    elif change=='generation':run.input['parameters']['generation_id']='another-generation'
    elif change=='arguments':step['arguments']['value']='different'
    elif change=='owner':run.input['parameters']['owner_user_id']='another-owner'
    elif change=='profile':page.profile_key='another-profile'
    elif change=='url':snapshot['url']='https://alpha.test/other'
    elif change=='ambiguous':snapshot['items'].append({**deepcopy(snapshot['items'][0]),'ref':'e999'})
    if change!='scope':candidates=initial.candidates(snapshot,{**page.viewport,'context':'owned'},None)
    other=RepairCache.for_step(initial,page,step,'one',snapshot['url'])
    result,status=other.lookup(snapshot,candidates)
    assert result is None and status!='hit'
    page.pointer_to.assert_not_called()

@pytest.mark.asyncio
@pytest.mark.parametrize('unknown',[False,True])
async def test_contradiction_or_uncertain_dispatch_never_promotes(tmp_path,unknown):
    runtime,run,page,payloads,step,visual=context(tmp_path)
    initial=visual();target=await ControlRuleRecovery(initial).resolve(page,'one',step=step)
    cache=RepairCache.for_step(initial,page,step,'one',(await page.snapshot())['url'])
    if unknown:
        page.pointer_to.side_effect=TimeoutError('lost acknowledgement')
        with pytest.raises(VisualActionUncertain):await initial.click(page,'one',target=target,readback=AsyncMock(return_value={'verified':True}))
        page.pointer_to.assert_awaited_once()
    else:await initial.click(page,'one',target=target,readback=AsyncMock(return_value={'verified':False}))
    assert not cache.exists()

@pytest.mark.asyncio
async def test_truncated_probe_cannot_promote_partial_structure(tmp_path):
    runtime,run,page,payloads,step,visual=context(tmp_path)
    initial=visual();snapshot=await page.snapshot();snapshot['controls_truncated']=True
    cache=RepairCache.for_step(initial,page,step,'one',snapshot['url'])
    assert cache.ticket(snapshot,snapshot['items'],snapshot['items'][0]) is None

@pytest.mark.asyncio
async def test_executor_prefers_cache_without_calling_broken_original_locator(tmp_path):
    from ai2apps.browser.background_executor import BackgroundExecutor
    runtime,run,page,payloads,step,visual=context(tmp_path)
    page.find_target=AsyncMock(return_value=None);page.related_windows=AsyncMock(return_value=[])
    page.pointer_to.return_value={'x':40,'y':30}
    request={'step':step,'site_scope':['https://alpha.test/**']}
    first=await BackgroundExecutor(runtime).execute(page,request,run)
    assert first['outcome']=='success'
    page.find_target=AsyncMock(side_effect=AssertionError('Cache should be preferred'))
    second=await BackgroundExecutor(runtime).execute(page,request,run)
    assert second['outcome']=='success'
    assert {'phase':'repair_cache','status':'hit'} in second['evidence']['result']['visual_recovery']


@pytest.mark.asyncio
async def test_cached_target_rejected_by_marked_review_is_invalidated(tmp_path):
    from ai2apps.browser.visual_recovery import VisualRecoveryUnavailable
    runtime,run,page,payloads,step,visual=context(tmp_path)
    first=visual();target=await ControlRuleRecovery(first).resolve(page,'one',step=step)
    settle(target,{'readback':{'verified':True}},runtime.database)
    second=visual();second.decide=AsyncMock(return_value=False)
    with pytest.raises(VisualRecoveryUnavailable):await ControlRuleRecovery(second).resolve(page,'one',step=step)
    assert {'phase':'repair_cache','status':'invalidated_review'} in second.evidence
    cache=RepairCache.for_step(second,page,step,'one',(await page.snapshot())['url'])
    assert not cache.exists();page.pointer_to.assert_not_called()

@pytest.mark.asyncio
async def test_uncertain_action_after_cache_hit_invalidates_without_replay(tmp_path):
    runtime,run,page,payloads,step,visual=context(tmp_path)
    first=visual();target=await ControlRuleRecovery(first).resolve(page,'one',step=step)
    settle(target,{'readback':{'verified':True}},runtime.database)
    second=visual();target=await ControlRuleRecovery(second).resolve(page,'one',step=step)
    assert {'phase':'repair_cache','status':'hit'} in second.evidence
    page.pointer_to.side_effect=TimeoutError('lost acknowledgement')
    with pytest.raises(VisualActionUncertain):await second.click(page,'one',target=target,readback=AsyncMock(return_value={'verified':True}))
    cache=RepairCache.for_step(second,page,step,'one',(await page.snapshot())['url'])
    assert not cache.exists();page.pointer_to.assert_awaited_once()


@pytest.mark.asyncio
async def test_optional_cache_write_failure_does_not_hide_verified_action(tmp_path,monkeypatch):
    import sqlite3
    runtime,run,page,payloads,step,visual=context(tmp_path)
    first=visual();target=await ControlRuleRecovery(first).resolve(page,'one',step=step)
    def busy(*args):raise sqlite3.OperationalError('database is locked')
    monkeypatch.setattr(RepairCache,'save',busy)
    result=await first.click(page,'one',target=target,readback=AsyncMock(return_value={'verified':True}))
    assert result['performed'] and result['readback']['verified']
    assert {'phase':'repair_cache_commit','status':'unavailable'} in result['evidence']
    page.pointer_to.assert_awaited_once()
