import importlib.util
from pathlib import Path
import zipfile
import pytest

spec=importlib.util.spec_from_file_location('upgrade_contract',Path(__file__).resolve().parents[1]/'spark/host_upgrade_contract.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

@pytest.mark.parametrize('value',[81,87])
def test_schema_is_read_from_candidate_without_importing_it(tmp_path,value):
    path=tmp_path/'candidate.whl'
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr('ai2apps/config.py',f'raise RuntimeError("must not execute")\nPLATFORM_DATABASE_SCHEMA_VERSION = {value}\n')
    assert module.expected_schema_version(path)==value

@pytest.mark.parametrize('source',['','PLATFORM_DATABASE_SCHEMA_VERSION=True','PLATFORM_DATABASE_SCHEMA_VERSION=87\nPLATFORM_DATABASE_SCHEMA_VERSION=81','PLATFORM_DATABASE_SCHEMA_VERSION=calculate()'])
def test_ambiguous_or_dynamic_schema_rejected(tmp_path,source):
    path=tmp_path/'candidate.whl'
    with zipfile.ZipFile(path,'w') as archive:archive.writestr('ai2apps/config.py',source)
    with pytest.raises((ValueError,TypeError)):module.expected_schema_version(path)

def test_health_requires_exact_actual_and_target_schema():
    health={'status':'ok','database':{'status':'ready','schema_version':87,'target_schema_version':87}}
    module.validate_schema_health(health,87)
    for key,value in [('schema_version',81),('target_schema_version',88),('schema_version','87')]:
        changed={**health,'database':{**health['database'],key:value}}
        with pytest.raises(ValueError):module.validate_schema_health(changed,87)
