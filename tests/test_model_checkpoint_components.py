"""Internal model dependencies cannot advertise independent inference capabilities."""
import pytest
from ai2apps.model_providers import validate_package_models, ModelProviderContractError


def validate(model):
    return validate_package_models('example.media', [model], runtime_mode='managed_process',
                                   protocol='ai2apps-model-worker/v1')


def test_internal_checkpoint_component_is_accepted_without_fake_inference_contract():
    result = validate({'id':'example.media/vae', 'model_type':'component',
                       'metadata':{'internal':True}})
    assert result[0]['model_type'] == 'component'
    assert tuple(result[0]['capabilities']) == ('checkpoint_component',)
    assert result[0]['metadata']['internal'] is True


@pytest.mark.parametrize('extra', [
    {}, {'metadata':{'internal':False}}, {'metadata':{'internal':'true'}},
    {'metadata':{'internal':True},'capabilities':['image_generation']},
    {'metadata':{'internal':True},'capabilities':['checkpoint_component','conversation']},
])
def test_component_must_be_internal_and_not_advertise_callable_operations(extra):
    with pytest.raises(ModelProviderContractError, match='component requires'):
        validate({'id':'example.media/vae','model_type':'component',**extra})


def test_catalog_readiness_tracks_helper_activation_and_hides_components(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.services import ServiceRuntimeMode, ServiceInstanceStatus
    from ai2apps.model_providers import list_package_models
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    weights = {'provider':'huggingface','repo_id':'example/weights','revision':'a'*40}
    models = validate_package_models('example.media', [
        {'id':'example.media/main','model_type':'image_generation','weights':weights,
         'metadata':{'required_model_ids':['example.media/vae']}},
        {'id':'example.media/vae','model_type':'component','weights':weights,
         'metadata':{'internal':True}}], runtime_mode='external', protocol='ai2apps-model-worker/v1')
    service = runtime.services.ensure_service(service_key='example.media',package_id='example.media',
        package_version='1.0.0',display_name='Media',runtime_mode=ServiceRuntimeMode.EXTERNAL,
        source='installed',config={'models':list(models)})
    runtime.services.ensure_instance(service_id=service.id,provider_key='package:example.media',
        status=ServiceInstanceStatus.RUNNING,endpoint='http://127.0.0.1:9876')
    snapshots = [{'model_id':'example.media/main','path':str(tmp_path/'main')},
                 {'model_id':'example.media/vae','path':None}]
    supervisor = SimpleNamespace(internal_headers=lambda _:None,model_root=tmp_path,
        _huggingface_hub_cache=lambda:tmp_path,
        _model_worker_checkpoints=lambda *_:(snapshots,()))
    monkeypatch.setattr(runtime,'package_manager',SimpleNamespace(supervisor=supervisor))
    catalog = {m.id:m for m in list_package_models(runtime)}
    assert not catalog['example.media/main'].checkpoint_ready
    assert catalog['example.media/main'].public_catalog_entry()['is_hidden']
    snapshots[1]['path'] = str(tmp_path/'vae')
    catalog = {m.id:m for m in list_package_models(runtime)}
    assert catalog['example.media/main'].checkpoint_ready
    assert not catalog['example.media/main'].public_catalog_entry()['is_hidden']
    assert catalog['example.media/vae'].checkpoint_ready
    assert catalog['example.media/vae'].public_catalog_entry()['is_hidden']
    snapshots.pop()
    assert not list_package_models(runtime)[0].checkpoint_ready


def test_dependency_readiness_rejects_cycles_and_missing_declarations():
    from ai2apps.model_providers import _package_model_checkpoints_ready
    models = {'a':{'metadata':{'required_model_ids':['b']}},
              'b':{'metadata':{'required_model_ids':['a']}}}
    assert not _package_model_checkpoints_ready('a',models,{})
    models['b']['metadata']['required_model_ids'] = ['missing']
    assert not _package_model_checkpoints_ready('a',models,{})
