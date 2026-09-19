import importlib.util
import json
import hashlib
import struct
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('ssd_export', Path(__file__).parents[1] / 'scripts/build_dsv41_ssd_checkpoint.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def fixture(tmp):
    src=tmp/'source'; src.mkdir(); store=tmp/'store'; store.mkdir(); raw=b''; h={}; shapes=[]
    for e in range(2):
        for i,(w,p) in enumerate(mod.PARTS):
            k=f'layers.0.ffn.experts.{e}.{w}.{p}'; b=bytes([e*6+i])*4
            h[k]={'dtype':'I8','shape':[4],'data_offsets':[len(raw),len(raw)+4]};raw+=b
            if e==0:shapes.append([4])
    expert_raw=raw
    # Preserve tensors from MTP and ordinary layers, not just the main backbone.
    for k in ['embed.weight','layers.40.ffn.experts.0.w1.weight']:
        h[k]={'dtype':'I8','shape':[3],'data_offsets':[len(raw),len(raw)+3]};raw+=b'abc'
    enc=json.dumps(h).encode();(src/'model.safetensors').write_bytes(struct.pack('<Q',len(enc))+enc+raw)
    (src/'model.safetensors.index.json').write_text(json.dumps({'weight_map':{k:'model.safetensors' for k in h}}))
    idx=mod.sha(src/'model.safetensors.index.json');(store/'layer-0.bin').write_bytes(expert_raw)
    meta={'layer':0,'checkpoint_index_sha256':idx,'expert_to_record':{'0':0,'1':1},'record_bytes':24,'shapes':shapes,'sha256':hashlib.sha256(expert_raw).hexdigest()}
    (store/'layer-0.bin.json').write_text(json.dumps(meta));(store/'manifest.json').write_text('{}')
    return src,store

def test_export_preserves_every_payload(tmp_path):
    src,store=fixture(tmp_path);out=tmp_path/'out'
    m=mod.build(src,store,out,'owner/model','a'*40,layers=1,experts=2)
    assert m['tensor_count']==14
    assert m['backbone_payload_bytes']==6
    assert m['expert_payload_bytes']==48
    assert set(json.loads((out/'model.safetensors.index.json').read_text())['weight_map'])=={'embed.weight','layers.40.ffn.experts.0.w1.weight'}
    assert len(json.loads((out/'source-tensor-sha256.json').read_text()))==14
    assert not (tmp_path/'out.partial').exists()
    assert (src/'model.safetensors').exists()
    with pytest.raises(FileExistsError):mod.build(src,store,out,'owner/model','a'*40,layers=1,experts=2)

def test_store_corruption_never_publishes(tmp_path):
    src,store=fixture(tmp_path);(store/'layer-0.bin').write_bytes(b'X'*48)
    with pytest.raises(ValueError,match='payload mismatch'):mod.build(src,store,tmp_path/'out','owner/model','a'*40,layers=1,experts=2)
    assert not (tmp_path/'out').exists()

def test_duplicate_record_rejected(tmp_path):
    src,store=fixture(tmp_path);p=store/'layer-0.bin.json';m=json.loads(p.read_text());m['expert_to_record']['1']=0;p.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='coverage'):mod.build(src,store,tmp_path/'out','owner/model','a'*40,layers=1,experts=2)


def test_unsafe_index_path_rejected(tmp_path):
    with pytest.raises(ValueError):mod.safe_file(tmp_path,'../outside')
