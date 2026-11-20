"""Offline detached Contract v1 verification never claims Registry publication."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util,json,shutil,zipfile
import pytest
from ai2apps.packages.contract_v1 import build_package,generate_publisher_key,create_signature_envelope
from ai2apps.packages.manager import ServicePackageManager
from ai2apps.packages.models import TrustStatus,PackageError


def fixture(tmp_path):
    path=Path(__file__).resolve().parents[2]/'tests/test_ai2apps_package_contract_v1.py'
    spec=importlib.util.spec_from_file_location('contract_fixture',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    source=m._model_worker_source(tmp_path)
    built=build_package(source,tmp_path/'candidate.ai2service')
    private,public,_=generate_publisher_key()
    envelope=create_signature_envelope(built,private,publisher_id='arbitrary-publisher',publisher_key_id='key-one')
    root=tmp_path/'installed';root.mkdir()
    with zipfile.ZipFile(built.archive_path) as z:z.extractall(root)
    shutil.copy2(built.archive_path,root/'package.ai2service')
    publisher=SimpleNamespace(trust_status=TrustStatus.TRUSTED,key_id='key-one',public_key=public)
    record=SimpleNamespace(store_path=str(root),package_digest='sha256:'+built.sha256,publisher_key='registry.arbitrary-publisher.key-one',verification={'signature':{'trust':'publisher-signed-contract-v1','envelope':envelope}})
    manager=object.__new__(ServicePackageManager);manager._require_isolated_runtime=lambda _:None
    manager.packages=SimpleNamespace(get_publisher=lambda _:publisher,files=lambda _:[{'path':f.path,'content_hash':'sha256:'+f.sha256,'size_bytes':f.size} for f in built.files])
    return manager,record,publisher,root


def test_signed_candidate_checks_real_signature_and_file_index(tmp_path):
    manager,record,_,root=fixture(tmp_path);manager._validate_installed(record)
    assert record.verification['signature']['trust']!='ai2apps-cloud-registry-v1'
    (root/'src/worker_adapter.py').write_text('tampered')
    with pytest.raises(PackageError,match='changed'):manager._validate_installed(record)


def test_signed_candidate_rejects_revoked_key(tmp_path):
    manager,record,publisher,_=fixture(tmp_path);publisher.trust_status=TrustStatus.REVOKED
    with pytest.raises(PackageError,match='trust or key'):manager._validate_installed(record)


def test_signed_candidate_rejects_invalid_envelope(tmp_path):
    manager,record,_,_=fixture(tmp_path)
    record.verification['signature']['envelope']['payload']['package']['version']='9.9.9'
    with pytest.raises(Exception,match='signature|Signature'):manager._validate_installed(record)


def test_signed_candidate_rejects_other_publisher_identity(tmp_path):
    manager,record,_,_=fixture(tmp_path);record.publisher_key='registry.someone-else.key-one'
    with pytest.raises(PackageError,match='trust or key'):manager._validate_installed(record)
