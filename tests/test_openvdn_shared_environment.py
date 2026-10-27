import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('openvdn_entry',Path(__file__).parents[1]/'spark/openvdn_process_entry.py')
entry=importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)

def test_legacy_environment_stays_isolated(tmp_path):
    process=tmp_path/'processes/openvdn'
    roots,_,_,version=entry.environment_for_role(tmp_path,process,'inference')
    assert version=='2.13.0+cu129'
    assert tmp_path/'Python/lib/python3.12/site-packages' not in roots
    assert entry.environment_for_role(tmp_path,process,'encoder')[3]=='2.10.0+cu130'

def test_explicit_shared_contract_retains_profile_precedence(tmp_path):
    (tmp_path/'META').mkdir()
    (tmp_path/'META/openvdn-processes.json').write_text(json.dumps({'sharedCore':{'schemaVersion':1,'torchVersion':'2.13.0+cu130'}}))
    process=tmp_path/'processes/openvdn'
    roots,_,_,version=entry.environment_for_role(tmp_path,process,'inference')
    assert roots[:2]==[process/'site-packages',tmp_path/'Python/lib/python3.12/site-packages']
    assert version==entry.environment_for_role(tmp_path,process,'encoder')[3]=='2.13.0+cu130'

@pytest.mark.parametrize('contract',[True,{}, {'schemaVersion':True,'torchVersion':'2.13.0+cu130'}, {'schemaVersion':1,'torchVersion':'2.13.0+cu129'}, {'schemaVersion':2,'torchVersion':'2.13.0+cu130'}])
def test_unknown_shared_contract_rejected(tmp_path,contract):
    (tmp_path/'META').mkdir()
    (tmp_path/'META/openvdn-processes.json').write_text(json.dumps({'sharedCore':contract}))
    with pytest.raises(RuntimeError,match='shared-core'):
        entry.environment_for_role(tmp_path,tmp_path/'processes/openvdn','inference')
