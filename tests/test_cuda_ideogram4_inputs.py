import hashlib
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
import cuda_ideogram4_inputs as module

@pytest.mark.parametrize('mutation',['size','digest','cancel','none'])
def test_pinned_inputs_fail_closed(tmp_path,monkeypatch,mutation):
    source=tmp_path/'weight';source.write_bytes(b'fixed')
    lock={'checkpoint':[{'path':'weight','bytes':5,'sha256':hashlib.sha256(b'fixed').hexdigest()}],'tokenizer':[]}
    (tmp_path/'ideogram4-inputs.lock.json').write_text(json.dumps(lock))
    monkeypatch.setattr(module,'__file__',str(tmp_path/'verifier.py'))
    if mutation=='size':source.write_bytes(b'longer')
    if mutation=='digest':source.write_bytes(b'wrong')
    calls=0
    def check():
        nonlocal calls
        calls+=1
        if mutation=='cancel' and calls==2:raise RuntimeError('cancel hashing')
    if mutation=='none':module.verify_inputs(tmp_path,tmp_path,check=check)
    else:
        with pytest.raises((ValueError,RuntimeError)):module.verify_inputs(tmp_path,tmp_path,check=check)
