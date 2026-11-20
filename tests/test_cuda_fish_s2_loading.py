"""Pinned checkpoint integrity must fail before any model/CUDA loading."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest


def loader():
    path=Path(__file__).resolve().parents[1]/'spark/cuda_fish_s2_loading.py'
    spec=importlib.util.spec_from_file_location('fish_loading_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('failure',['missing','size','digest','escape','quantized_path'])
def test_checkpoint_rejects_untrusted_inputs(tmp_path,monkeypatch,failure):
    module=loader();folder=tmp_path/('int4-model' if failure=='quantized_path' else 'model');folder.mkdir()
    path=folder/'weights.bin';path.write_bytes(b'original')
    name='weights.bin'
    if failure=='missing':path.unlink()
    if failure=='size':path.write_bytes(b'x')
    if failure=='digest':path.write_bytes(b'changed!')
    if failure=='escape':
        (tmp_path/'outside').write_bytes(b'original');path.unlink();path.symlink_to(tmp_path/'outside')
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'revision':'fixed','files':[{'path':name,'size':8,'sha256':hashlib.sha256(b'original').hexdigest()}]}))
    monkeypatch.setattr(module,'_CHECKPOINT',manifest)
    with pytest.raises(ValueError):module.verify_checkpoint(folder)


def test_checkpoint_accepts_only_matching_bytes(tmp_path,monkeypatch):
    module=loader();folder=tmp_path/'model';folder.mkdir();(folder/'weights.bin').write_bytes(b'original')
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'revision':'fixed','files':[{'path':'weights.bin','size':8,'sha256':hashlib.sha256(b'original').hexdigest()}]}))
    monkeypatch.setattr(module,'_CHECKPOINT',manifest)
    verified,receipt=module.verify_checkpoint(folder)
    assert verified==folder.resolve() and receipt['revision']=='fixed'
