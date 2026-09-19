import sys,importlib.util,json,struct
from pathlib import Path
import pytest
ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_qwen_next_ssd_checkpoint as exporter

def fixture(tmp):
 src=tmp/'source';src.mkdir();store=tmp/'store';store.mkdir();raw=b'';h={};rows={}
 (src/'config.json').write_text(json.dumps({'model_type':'qwen4_exp'}))
 for pi,p in enumerate(['gate_proj','up_proj','down_proj']):
  for ci,c in enumerate(['weight','scales','biases']):
   k=f'language_model.model.layers.0.mlp.switch_mlp.{p}.{c}';b=bytes([pi*3+ci])*4+bytes([pi*3+ci+20])*4
   h[k]={'dtype':'I8','shape':[2,4],'data_offsets':[len(raw),len(raw)+8]};raw+=b;rows[p+'.'+c]=[b[:4],b[4:]]
 h['ordinary.weight']={'dtype':'I8','shape':[3],'data_offsets':[len(raw),len(raw)+3]};raw+=b'xyz'
 enc=json.dumps(h).encode();(src/'model.safetensors').write_bytes(struct.pack('<Q',len(enc))+enc+raw)
 (src/'model.safetensors.index.json').write_text(json.dumps({'weight_map':{k:'model.safetensors' for k in h}}))
 tensors=[];cursor=0;records=[bytearray(4096),bytearray(4096)]
 for p in ['gate_up_proj','down_proj']:
  for c in ['weight','scales','biases']:
   parts=['gate_proj','up_proj'] if p=='gate_up_proj' else ['down_proj'];n=4*len(parts)
   tensors.append({'name':p+'.'+c,'shape':[n],'nbytes':n,'offset':cursor,'dtype':'I8'})
   for e in range(2):records[e][cursor:cursor+n]=b''.join(rows[q+'.'+c][e] for q in parts)
   cursor+=n
 m={'variant':exporter.VARIANT,'layer':0,'num_experts':2,'data_offset':4096,'record_bytes':4096,'tensors':tensors};enc=json.dumps(m).encode()
 (store/'layer-000.moe').write_bytes(struct.pack('<Q',len(enc))+enc+b'\0'*(4088-len(enc))+b''.join(records))
 return src,store

def test_fused_export_and_full_tensor_reconstruction(tmp_path):
 src,store=fixture(tmp_path);out=tmp_path/'out';m=exporter.build(src,store,out,'owner/model','a'*40,layers=1,experts=2)
 assert m['tensor_count']==10
 locs=json.loads((out/'external-tensors.json').read_text());assert len(locs)==9
 base,h=exporter.header(src/'model.safetensors');original=(src/'model.safetensors').read_bytes()
 for k,v in locs.items():
  b=(out/v['file']).read_bytes();actual=b''.join(b[v['offset']+i*v['stride']:v['offset']+i*v['stride']+v['row_bytes']] for i in range(v['count']))
  lo,hi=h[k]['data_offsets'];assert actual==original[base+lo:base+hi]
 assert m['backbone_payload_bytes']==3

def test_wrong_fused_bytes_rejected(tmp_path):
 src,store=fixture(tmp_path);p=store/'layer-000.moe';b=bytearray(p.read_bytes());b[4096]=255;p.write_bytes(b)
 with pytest.raises(ValueError,match='bytes mismatch'):exporter.build(src,store,tmp_path/'out','owner/model','a'*40,layers=1,experts=2)
 assert not (tmp_path/'out').exists()

def test_runtime_reader_reconstructs_full_weights_and_rejects_escape(tmp_path):
 from omlx.ssd_checkpoint import ExternalTensorReader
 src,store=fixture(tmp_path);out=tmp_path/'out';exporter.build(src,store,out,'owner/model','a'*40,layers=1,experts=2)
 reader=ExternalTensorReader(out);base,h=exporter.header(src/'model.safetensors');b=(src/'model.safetensors').read_bytes()
 for key in reader.tensors:
  lo,hi=h[key]['data_offsets'];assert reader.read(key)==b[base+lo:base+hi]
 with pytest.raises(ValueError):reader.path('../secret')
 key=next(iter(reader.tensors));reader.tensors[key]['offset']=10**20
 with pytest.raises(ValueError,match='range'):reader.read(key)

def test_backbone_preserves_mlx_metadata(tmp_path):
 from ssd_checkpoint_io import subset,header
 p=tmp_path/'in.safetensors';meta={'__metadata__':{'format':'mlx'},'x':{'dtype':'I8','shape':[3],'data_offsets':[0,3]}}
 raw=json.dumps(meta).encode();p.write_bytes(struct.pack('<Q',len(raw))+raw+b'abc')
 subset(p,tmp_path/'out.safetensors',{'x':meta['x']},8+len(raw))
 _,h=header(tmp_path/'out.safetensors');assert h['__metadata__']=={'format':'mlx'}

def test_full_loader_hook_restores_external_weights_and_is_scoped(tmp_path, monkeypatch):
 import mlx.core as mx
 import mlx_vlm.utils as utils
 import omlx.patches.mlx_vlm_qwen4_exp_compat as compat
 from omlx.patches.qwen38_next_cache.runtime import qwen4_dynamic_safetensors_on_load
 src,store=fixture(tmp_path);out=tmp_path/'out'
 exporter.build(src,store,out,'owner/model','a'*40,layers=1,experts=2)
 (out/'config.json').write_text(json.dumps({'model_type':'qwen4_exp'}))
 monkeypatch.delenv('OMLX_QWEN4_DYNAMIC_STORE',raising=False)
 monkeypatch.setattr(compat,'configure_qwen4_exp_runtime',lambda *a,**k:None)
 original=utils._load_safetensors
 shard=next(out.glob('*.safetensors'))
 with qwen4_dynamic_safetensors_on_load(out):
  # Loading an unrelated model must not consume this model's expert injection.
  other=utils._load_safetensors(str(src/'model.safetensors'))
  restored=utils._load_safetensors(str(shard))
  assert set(restored)==set(other)
  assert all(mx.array_equal(restored[k],v).item() for k,v in other.items())
 assert utils._load_safetensors is original

def test_cached_ssd_slots_do_not_read_external_payloads():
 import mlx.core as mx
 from types import SimpleNamespace
 from omlx.patches.qwen38_next_cache.runtime import _ssd_expert_weights
 key='language_model.model.layers.0.mlp.switch_mlp.gate_proj.weight'
 def forbidden():raise AssertionError('Cached bootstrap must not read Full experts')
 reader=SimpleNamespace(tensors={key:{'shape':[512,4,8],'dtype':'U32'}},iter_mlx_weights=forbidden)
 weights=dict(_ssd_expert_weights(reader,slots=10))
 assert weights[key].shape==(10,4,8)
 assert weights[key].dtype==mx.uint32
 assert not mx.any(weights[key]).item()
