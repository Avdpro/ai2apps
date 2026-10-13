from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from ai2apps.packages.checkpoint_dependencies import checkpoint_manifest
from ai2apps.packages.models import PackageError


def fixture():
    checkpoint={'id':'h3/base','weights':{'repo_id':'owner/base','revision':'a'*40,'distribution_id':'dist_base'},'metadata':{}}
    provider=NS(service_key='h3',package_digest='locked',package_version='0.11.0',protocol='ai2apps-model-worker/v1',
        manifest={'id':'h3','models':[checkpoint,{'id':'h3/unrelated','weights':{'repo_id':'private/unrelated'}}]})
    consumer=NS(package_digest='consumer',protocol='ai2apps-model-worker/v1',manifest={
        'id':'meridian','requires':{'services':[{'id':'h3','optional':False}]},
        'models':[{'id':'meridian/main','metadata':{'required_model_ids':['h3/base'],
            'checkpoint_dependencies':[{'service_id':'h3','model_id':'h3/base'}]}}]})
    lock=NS(dependency_key='h3',dependency_digest='locked',dependency_version='0.11.0',optional=False)
    repository=NS(locks=lambda _: [lock],active=lambda _:provider)
    return consumer,provider,lock,repository


def test_only_selected_checkpoint_is_exposed_without_mutation():
    consumer,provider,lock,repo=fixture()
    original=deepcopy(consumer.manifest)
    resolved=checkpoint_manifest(consumer,repo)
    assert [x['id'] for x in resolved['models']]==['meridian/main','h3/base']
    assert resolved['models'][1]['weights']==provider.manifest['models'][0]['weights']
    assert consumer.manifest==original


def test_legacy_worker_unchanged():
    package=NS(manifest={'models':[{'id':'legacy'}]})
    assert checkpoint_manifest(package,None) is package.manifest


def test_readiness_requires_both_owned_and_dependency_checkpoints():
    from ai2apps.model_providers import _package_model_checkpoints_ready
    consumer, _, _, repo = fixture()
    resolved = checkpoint_manifest(consumer, repo)
    models = {row['id']: row for row in resolved['models']}
    models['meridian/main']['weights'] = {'repo_id': 'owner/adapters'}
    ready = _package_model_checkpoints_ready
    own = {'meridian/main': {'path': '/adapters'}}
    assert not ready('meridian/main', models, own)
    assert not ready('meridian/main', models, {**own, 'h3/base': {'path': None}})
    assert ready('meridian/main', models, {**own, 'h3/base': {'path': '/h3'}})
    assert not ready('meridian/main', models, {'h3/base': {'path': '/h3'}})


def test_host_advertises_checkpoint_dependency_feature():
    from ai2apps.packages.manager import HOST_PACKAGE_FEATURES, ServicePackageManager
    from ai2apps.packages.models import CompatibilityContext
    assert 'model.checkpoint-dependencies.v1' in HOST_PACKAGE_FEATURES
    manager = object.__new__(ServicePackageManager)
    package = NS(manifest=NS(raw={}))
    requirement = {'features': ['model.checkpoint-dependencies.v1']}
    manager.compatibility = CompatibilityContext(os_name='darwin', architecture='arm64', python_version='3.11.0')
    with pytest.raises(PackageError) as error:
        manager._check_requirements(requirement, package)
    assert error.value.code == 'platform_feature_missing'
    manager.compatibility = CompatibilityContext(os_name='darwin', architecture='arm64', python_version='3.11.0', features=HOST_PACKAGE_FEATURES)
    manager._check_requirements(requirement, package)


@pytest.mark.parametrize('change',[
    'unlocked','changed_digest','changed_version','optional_lock','optional_requirement',
    'undeclared','missing_provider','wrong_protocol','wrong_owner','wrong_model_owner',
    'path_injection','missing_model','duplicate_model','missing_weights','transitive',
    'not_required','consumer_protocol',
])
def test_reject_unauthorized_dependency(change):
    c,p,l,r=fixture()
    metadata=c.manifest['models'][0]['metadata']
    dep=metadata['checkpoint_dependencies'][0]
    if change=='unlocked': r.locks=lambda _:[]
    elif change=='changed_digest': p.package_digest='other'
    elif change=='changed_version': p.package_version='0.12.0'
    elif change=='optional_lock': l.optional=True
    elif change=='optional_requirement': c.manifest['requires']['services'][0]['optional']=True
    elif change=='undeclared': c.manifest['requires']['services']=[]
    elif change=='missing_provider': r.active=lambda _:None
    elif change=='wrong_protocol': p.protocol='http-json'
    elif change=='wrong_owner': p.manifest['id']='other'
    elif change=='wrong_model_owner': dep['model_id']='other/base'
    elif change=='path_injection': dep['path']='/private/secret'
    elif change=='missing_model': p.manifest['models']=[]
    elif change=='duplicate_model': p.manifest['models'].append(p.manifest['models'][0])
    elif change=='missing_weights': p.manifest['models'][0].pop('weights')
    elif change=='transitive': p.manifest['models'][0]['metadata']['required_model_ids']=['other/secret']
    elif change=='not_required': metadata['required_model_ids']=[]
    elif change=='consumer_protocol': c.protocol='http-json'
    with pytest.raises(PackageError): checkpoint_manifest(c,r)
