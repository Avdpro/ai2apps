import json
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import build_glm5_ssd_checkpoint as exporter
from test_qwen_next_ssd_checkpoint_export import fixture


def glm_fixture(tmp):
    source, store = fixture(tmp)
    p = source/'model.safetensors'
    base, original = exporter.header(p); raw = p.read_bytes()[base:]
    h = {}
    for key, value in original.items():
        if key == 'ordinary.weight':
            h[key] = value
            continue
        component = key.split('.switch_mlp.')[1]
        for expert in range(2):
            offset = value['data_offsets'][0] + expert*4
            h[f'model.language_model.layers.3.mlp.experts.{expert}.{component}'] = dict(dtype='I8',shape=[4],data_offsets=[offset,offset+4])
    # Preserve an unrelated MTP tensor as ordinary payload.
    h['model.language_model.layers.4.mlp.experts.0.gate_proj.weight'] = h.pop('ordinary.weight')
    enc=json.dumps(h).encode();p.write_bytes(struct.pack('<Q',len(enc))+enc+raw)
    (source/'model.safetensors.index.json').write_text(json.dumps({'weight_map':{k:p.name for k in h}}))
    (source/'config.json').write_text(json.dumps({'model_type':'glm5_next','text_config':{'first_k_dense_replace':3,'num_hidden_layers':4,'n_routed_experts':2}}))
    p=store/'layer-000.moe';b=p.read_bytes();m=json.loads(b[8:8+int.from_bytes(b[:8],'little')])
    m.update(layer=3,variant=exporter.VARIANT);enc=json.dumps(m).encode()
    (store/'layer-003.moe').write_bytes(struct.pack('<Q',len(enc))+enc+bytes(4088-len(enc))+b[4096:])
    return source,store


def test_glm_fused_export_preserves_experts_and_mtp(tmp_path):
    source,store=glm_fixture(tmp_path);out=tmp_path/'out'
    result=exporter.build(source,store,out,'owner/model','a'*40)
    assert result['tensor_count']==19
    assert result['backbone_payload_bytes']==3
    wm=json.loads((out/'model.safetensors.index.json').read_text())['weight_map']
    assert list(wm)==['model.language_model.layers.4.mlp.experts.0.gate_proj.weight']
    locations=json.loads((out/'external-tensors.json').read_text())
    assert len(locations)==18
    base,h=exporter.header(source/'model.safetensors');raw=(source/'model.safetensors').read_bytes()
    for key,t in locations.items():
        data=(out/t['file']).read_bytes();lo,hi=h[key]['data_offsets']
        assert data[t['offset']:t['offset']+t['nbytes']]==raw[base+lo:base+hi]


def test_glm_corrupt_fused_record_is_not_published(tmp_path):
    source,store=glm_fixture(tmp_path);p=store/'layer-003.moe'
    b=bytearray(p.read_bytes());b[4096]^=1;p.write_bytes(b)
    with pytest.raises(ValueError,match='expert bytes mismatch'):
        exporter.build(source,store,tmp_path/'out','owner/model','a'*40)
    assert not (tmp_path/'out').exists()
