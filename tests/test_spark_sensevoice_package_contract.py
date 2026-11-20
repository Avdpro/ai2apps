"""Host dependency wiring for the CUDA SenseVoice source Package."""
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from ai2apps.model_providers import (
    ModelProviderContractError,
    installed_model_preparation_recipes,
    validate_package_models,
)
from ai2apps.model_worker.protocol import ModelWorkerCheckpoint, ModelWorkerContext
from ai2apps.packages.supervisor import ManagedServiceSupervisor

ROOT = Path(__file__).resolve().parents[1] / 'packages/ai2apps-model-sensevoice-small-cuda'


def source():
    return yaml.safe_load((ROOT / 'service.yaml').read_text())


def test_sensevoice_helper_survives_host_recipe_and_worker_boundaries(tmp_path, monkeypatch):
    manifest = source()
    manifest['models'] = validate_package_models(
        manifest['id'], manifest['models'], runtime_mode='managed_process',
        protocol=manifest['runtime']['protocol'],
    )
    monkeypatch.setattr(ManagedServiceSupervisor, '_huggingface_hub_cache', staticmethod(lambda: tmp_path))
    package = SimpleNamespace(status='active', manifest=manifest, store_path=ROOT, service_key=manifest['id'])
    runtime = SimpleNamespace(package_repository=SimpleNamespace(installed=lambda: [package]))
    recipes = {r['id']: r for r in installed_model_preparation_recipes(runtime)}
    asr = recipes[manifest['id'] + '/default']
    helper_id, = asr['required_model_ids']
    assert recipes[helper_id]['internal'] is True
    assert recipes[helper_id]['recipe'] == 'native'
    rows, _ = ManagedServiceSupervisor._model_worker_checkpoints(manifest, tmp_path)
    checkpoints = tuple(ModelWorkerCheckpoint(
        model_id=row['model_id'], upstream_id=row['upstream_id'], provider=row['provider'],
        repo_id=row['repo_id'], revision=row['revision'], path=None, preparation=row['preparation'],
    ) for row in rows)
    context = ModelWorkerContext(manifest['id'], ROOT, tmp_path, manifest['models'], checkpoints)
    assert context.checkpoint_for('funasr/fsmn-vad').model_id == helper_id
    assert context.checkpoint_for('funasr/fsmn-vad').revision == 'df20e6b30c653645fa4ff125cacfcabd1020a669'


def test_old_cross_service_fixture_identity_is_not_installable():
    manifest = source()
    manifest['models'][1]['id'] = 'ai2apps.model.fsmn-vad/default'
    with pytest.raises(ModelProviderContractError, match='must start with'):
        validate_package_models(manifest['id'], manifest['models'], runtime_mode='managed_process',
                                protocol=manifest['runtime']['protocol'])
