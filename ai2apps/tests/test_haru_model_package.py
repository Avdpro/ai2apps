"""Owner declaration: truthfulness, resource permissions and Runtime dependency."""
import json
from pathlib import Path

import yaml
import pytest
from types import SimpleNamespace

from ai2apps.model_providers import validate_package_models
from ai2apps.packages.archive import ServicePackageArchive
from ai2apps.packages.registry import RegistryPackageManager
from ai2apps.packages.manager import HOST_PACKAGE_FEATURES, ServicePackageManager
from ai2apps.packages.models import CompatibilityContext, PackageError

ROOT = Path(__file__).resolve().parents[2] / 'packages/ai2apps-model-haru-4b-mlx'


def test_haru_package_has_explicit_native_duplex_and_honest_limits():
    service = yaml.safe_load((ROOT / 'service.yaml').read_text())
    ServicePackageArchive._manifest(service)
    models = validate_package_models(service['id'], service['models'],
        runtime_mode='managed_process', protocol='ai2apps-model-worker/v1')
    model, = models
    assert model['model_type'] == 'audio_realtime'
    assert model['capabilities'] == ['speech_duplex']
    assert model['metadata']['haru_precision'] == '8'
    audio = model['audio_capabilities']
    assert audio['operations'] == ['audio_realtime']
    duplex = audio['duplex']
    assert duplex['mode'] == 'native'
    assert (duplex['sample_rate'], duplex['frame_samples']) == (24000, 3200)
    assert duplex['text_output'] and duplex['voice_reference']
    for unsupported in ('text_input', 'async_result_injection', 'response_cancel'):
        assert duplex[unsupported] is False
    assert service['permissions']['network']['outbound'] is False
    assert service['permissions']['accelerator']['metal'] is True
    dependency, = service['requires']['services']
    assert dependency['version'] == '>=1.8.18,<2.0.0'
    assert 'audio-duplex-v1' in dependency['capabilities']
    assert service['compatibility']['features'] == ['model.audio-realtime.v1']


def test_haru_package_catalog_and_pinned_distribution_agree():
    manifest = json.loads((ROOT / 'ai2apps.json').read_text())
    service = yaml.safe_load((ROOT / 'service.yaml').read_text())
    spec = json.loads((ROOT / 'META/checkpoint-distribution.json').read_text())
    RegistryPackageManager._check_compatibility(manifest['compatibility'])
    assert manifest['package']['id'] == 'ai2apps/model-haru-4b-mlx'
    assert manifest['package']['version'] == service['version'] == '0.1.0'
    assert manifest['discovery'] == {'kind': 'model', 'categories': ['speech'],
        'tasks': ['audio-realtime', 'speech-duplex']}
    model, = service['models']
    assert manifest['modelInstall']['models'][0]['id'] == model['id'] == spec['modelId']
    weights = model['weights']
    assert weights['revision'] == spec['revision']
    assert weights['distribution_id'] == spec['distributionId']
    assert {x['type'] for x in spec['sourceRepositories']} == {'huggingface', 'modelscope'}
    assert all(len(x['revision']) == 40 for x in spec['sourceRepositories'])
    assert spec['quantization'] == 'bf16'  # Download precision != runtime backbone quantization.
    assert set(spec['includePatterns']) == {'config.json', 'model.safetensors',
        'tokenizer.json', 'tokenizer_config.json'}


def test_realtime_package_fails_closed_on_host_without_catalog_support():
    manager = object.__new__(ServicePackageManager)
    package = SimpleNamespace(manifest=SimpleNamespace(raw={}))
    requirement = {'features': ['model.audio-realtime.v1']}
    manager.compatibility = CompatibilityContext(os_name='darwin',
        architecture='arm64', python_version='3.11.0')
    with pytest.raises(PackageError) as error:
        manager._check_requirements(requirement, package)
    assert error.value.code == 'platform_feature_missing'
    manager.compatibility = CompatibilityContext(os_name='darwin',
        architecture='arm64', python_version='3.11.0', features=HOST_PACKAGE_FEATURES)
    manager._check_requirements(requirement, package)
