from types import SimpleNamespace

from ai2apps.model_providers import list_package_models
from ai2apps.services.models import ServiceStatus


def test_unrelated_models_skip_instance_and_checkpoint_work():
    services = [SimpleNamespace(source='installed', status=ServiceStatus.ENABLED,
        config={'models': [{'model_type': kind}]})
        for kind in ('llm', 'image_generation', 'speech', 'video_generation')]

    def forbidden(*args):
        raise AssertionError('Unrelated model must not resolve an instance')

    runtime = SimpleNamespace(services=SimpleNamespace(
        list_services=lambda: services, get_instance_for_service=forbidden))
    assert list_package_models(runtime, model_type='audio_generation') == ()


def test_filter_is_not_audio_specific():
    service = SimpleNamespace(source='installed', status=ServiceStatus.ENABLED,
        config={'models': [{'model_type': 'audio_generation'}]})
    def forbidden(*args):
        raise AssertionError('Unrelated model must not resolve an instance')
    runtime = SimpleNamespace(services=SimpleNamespace(
        list_services=lambda: [service], get_instance_for_service=forbidden))
    assert list_package_models(runtime, model_type='image_generation') == ()
