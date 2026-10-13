"""Resolve only explicitly declared checkpoints owned by locked model Packages."""
from .models import PackageError


def checkpoint_manifest(package, repository):
    manifest = package.manifest
    own = list(manifest.get('models', []))
    requested = [(model, dep) for model in own
                 for dep in _dependencies(model)]
    if not requested:
        return manifest
    if package.protocol != 'ai2apps-model-worker/v1':
        raise PackageError('invalid_checkpoint_dependency', 'Checkpoint dependencies require a Model Worker')
    requirements = {x['id']: x for x in manifest.get('requires', {}).get('services', [])}
    locks = {x.dependency_key: x for x in repository.locks(package.package_digest)}
    own_ids = {x['id'] for x in own}
    added = {}
    for consumer, dep in requested:
        if not isinstance(dep, dict) or set(dep) != {'service_id', 'model_id'}:
            raise PackageError('invalid_checkpoint_dependency', 'Only service_id and model_id may select a dependency checkpoint')
        service_id, model_id = dep['service_id'], dep['model_id']
        if (not isinstance(service_id, str) or not isinstance(model_id, str)
                or not model_id.startswith(service_id + '/') or model_id in own_ids
                or service_id == manifest['id']):
            raise PackageError('invalid_checkpoint_dependency', 'Invalid checkpoint owner or model identity')
        if model_id not in consumer.get('metadata', {}).get('required_model_ids', []):
            raise PackageError('invalid_checkpoint_dependency', 'Checkpoint dependency must also be a required model')
        requirement, lock = requirements.get(service_id), locks.get(service_id)
        provider = repository.active(service_id)
        if (not requirement or requirement.get('optional', False) or lock is None or lock.optional
                or provider is None or provider.package_digest != lock.dependency_digest
                or provider.package_version != lock.dependency_version
                or provider.service_key != service_id or provider.manifest.get('id') != service_id
                or provider.protocol != 'ai2apps-model-worker/v1'):
            raise PackageError('checkpoint_dependency_unavailable', 'Checkpoint provider must be an active digest-locked required Model Package')
        candidates = [x for x in provider.manifest.get('models', []) if x.get('id') == model_id]
        if len(candidates) != 1 or not isinstance(candidates[0].get('weights'), dict):
            raise PackageError('invalid_checkpoint_dependency', 'Dependency Package does not own this checkpoint')
        selected = candidates[0]
        if selected.get('metadata', {}).get('required_model_ids') or _dependencies(selected):
            raise PackageError('invalid_checkpoint_dependency', 'Transitive checkpoint dependencies are not supported')
        if model_id in added and added[model_id] != selected:
            raise PackageError('invalid_checkpoint_dependency', 'Conflicting checkpoint declaration')
        added[model_id] = selected
    # Only the checkpoint resolver receives these declarations. They do not
    # become public models or accepted invocation IDs of the consumer Worker.
    return {**manifest, 'models': own + list(added.values())}


def _dependencies(model):
    value = model.get('metadata', {}).get('checkpoint_dependencies', [])
    if not isinstance(value, list) or len(value) > 16:
        raise PackageError('invalid_checkpoint_dependency', 'Invalid checkpoint dependency list')
    return value
