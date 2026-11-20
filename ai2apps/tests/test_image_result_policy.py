"""Image-owner settlement guards: pure results, no model calls or replays."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from ai2apps.images.capabilities import MINI_APP_CAPABILITIES, STICKER_GENERATE_CAPABILITY, COMIC_TRANSLATION_CAPABILITY
from ai2apps.images.result_policy import CAPABILITIES, completion_check, comic_completion_check

PRODUCERS=(*MINI_APP_CAPABILITIES.values(),STICKER_GENERATE_CAPABILITY)

def step(cap,status='completed',*,error=None,output=None):
    return SimpleNamespace(kind='tool',tool_name=cap,status=SimpleNamespace(value=status),error=error,output=output)

@pytest.mark.parametrize('cap',PRODUCERS)
@pytest.mark.parametrize('status',['failed','uncertain'])
def test_every_image_producer_blocks_failed_or_unknown_settlement(cap,status):
    error={'code':'provider_timeout','details':{'provider':'same-provider','phase':'execute','submitted':True,
            'outcome_uncertain':status=='uncertain','studio_run_id':'run_original','studio_job_id':'job_original'}}
    output={'studio_run_id':'run_original','studio_job_id':'job_original'}
    item=step(cap,status,error=error,output=output);before=deepcopy((error,output))
    assert completion_check([item],[])['code']=='image_result_unavailable'
    assert (error,output)==before

@pytest.mark.parametrize('cap',PRODUCERS)
def test_success_and_corrected_unsubmitted_parameters_allow_completion(cap):
    assert completion_check([step(cap)],[]) is None
    rejected=step(cap,'failed',error={'code':'provider_incompatible','phase':'prepare','submitted':False})
    assert completion_check([rejected,step(cap)],[]) is None
    assert rejected.error['submitted'] is False
    assert completion_check([step(cap,'failed',error={'code':'tool_declaration_required'})],[]) is None

@pytest.mark.parametrize('failed_cap',['image.try_on','image.product_photo'])
def test_multistage_failure_keeps_prior_outputs_and_original_receipts(failed_cap):
    artifact={'artifact_id':'verified_item','url':'/v1/platform/sessions/one/artifacts/verified_item/download'}
    prior=step('image.extract_items',output={'artifact':artifact,'studio_run_id':'extract_run'})
    failed=step(failed_cap,'uncertain',error={'code':'provider_timeout','submitted':True,'studio_job_id':'failed_job'})
    artifacts=[artifact];before=deepcopy(artifacts)
    assert completion_check([prior,failed],artifacts)['code']=='image_result_unavailable'
    assert artifacts==before and prior.output['studio_run_id']=='extract_run'
    assert failed.error['submitted'] is True and failed.error['studio_job_id']=='failed_job'

@pytest.mark.parametrize('status',['failed','uncertain'])
def test_comic_translation_has_its_own_deliverable_failure(status):
    assert comic_completion_check([step(COMIC_TRANSLATION_CAPABILITY,status)],[])['code']=='comic_result_unavailable'
    assert comic_completion_check([step(COMIC_TRANSLATION_CAPABILITY,status),step(COMIC_TRANSLATION_CAPABILITY)],[]) is None
    assert completion_check([step(COMIC_TRANSLATION_CAPABILITY,status)],[]) is None


def test_queries_and_other_owners_do_not_activate_image_failure_guard():
    for cap in ('sticker.lookup','capability.describe','artifact.preview','unrelated.render'):
        assert completion_check([step(cap,'failed')],[]) is None
        assert comic_completion_check([step(cap,'failed')],[]) is None
    assert set(CAPABILITIES)==set(PRODUCERS)


def test_runtime_registers_all_image_producers_with_the_guard(runtime):
    policy=runtime.app_capability_router.result_policies['imagine-delivery']
    for provider in runtime.app_capability_router.providers.values():
        if provider.app_id in ('ai2apps.images','ai2apps.imagine-studio') and provider.capability.startswith('image.'):
            assert provider.capability in policy.capabilities
    assert STICKER_GENERATE_CAPABILITY in policy.capabilities
    assert runtime.app_capability_router.result_policies['comic-delivery'].capabilities==(COMIC_TRANSLATION_CAPABILITY,)

from test_app_interactions import runtime

@pytest.mark.parametrize('failed_cap',['image.try_on','image.product_photo'])
@pytest.mark.parametrize('failure_status',['failed','uncertain'])
def test_agent_settlement_retains_verified_prior_image(runtime,tmp_path,failed_cap,failure_status):
    from PIL import Image
    from ai2apps.chat import ChatRepository
    from ai2apps.agents.general import GeneralAgentExecutor
    from ai2apps.agents.models import RunStepStatus, FailAction
    session=ChatRepository(runtime.database,runtime.events).create_thread(title='Partial image settlement')[0].session.id
    path=tmp_path/'verified.png';Image.new('RGB',(8,8),'yellow').save(path)
    a=runtime.workspace.import_artifact(session,path,name='verified.png',media_type='image/png')
    artifact={'id':a.id,'name':a.name,'media_type':'image/png','download_url':f'/v1/platform/sessions/{session}/artifacts/{a.id}/download'}
    prior=step('image.extract_items',output={'artifact':artifact,'studio_run_id':'verified_run','studio_job_id':'verified_job'})
    prior.status=RunStepStatus.COMPLETED
    failed=step(failed_cap,failure_status,error={'code':'provider_timeout','submitted':True,'outcome_uncertain':failure_status=='uncertain','studio_run_id':'original_run','studio_job_id':'original_job'})
    model=SimpleNamespace(kind='model',status=RunStepStatus.COMPLETED,output={},input={})
    context=SimpleNamespace(steps=[prior,failed,model],run=SimpleNamespace(session_id=session,parent_run_id='fixture-parent'))
    executor=GeneralAgentExecutor.__new__(GeneralAgentExecutor)
    executor.capability_router=runtime.app_capability_router;executor.workspace=runtime.workspace
    result=executor._complete(context,{'content':'Prior image retained. Later requested work remains incomplete.'},'stop')
    assert isinstance(result,FailAction) and result.code=='image_result_unavailable'
    assert [item['artifact_id'] for item in result.output['artifacts']]==[a.id]
    assert runtime.workspace.artifact_path(a).is_file()
    assert prior.output['studio_job_id']=='verified_job'
    assert failed.error['submitted'] is True and failed.error['studio_job_id']=='original_job'
