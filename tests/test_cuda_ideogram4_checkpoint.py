import importlib.util
import json
from pathlib import Path
import pytest
import torch
spec=importlib.util.spec_from_file_location('ideogram_checkpoint',Path(__file__).resolve().parents[1]/'spark/cuda_ideogram4_checkpoint.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
def fixture():
 return {'layer.weight':torch.tensor([[1.,2.],[3.,4.]]).to(torch.float8_e4m3fn),'layer.weight_scale':torch.tensor(.25),'layer.comfy_quant':torch.tensor(list(json.dumps({'format':'float8_e4m3fn','full_precision_matrix_mult':False}).encode()),dtype=torch.uint8)}
def test_scalar_to_row_preserves_dequantized_weight_and_source():
 s=fixture();r=module.official_fp8_state(s)
 assert r['layer.weight'] is s['layer.weight']
 assert torch.equal(r['layer.weight'].float()*r['layer.weight_scale'][:,None],s['layer.weight'].float()*s['layer.weight_scale'])
 assert s['layer.weight_scale'].ndim==0 and 'layer.comfy_quant' in s
@pytest.mark.parametrize('bad',[float('nan'),float('inf'),0.,-1.])
def test_reject_invalid_scale(bad):
 s=fixture();s['layer.weight_scale']=torch.tensor(bad)
 with pytest.raises(ValueError):module.official_fp8_state(s)
def test_reject_orphan_and_unknown_descriptor():
 s=fixture();s['unknown.weight_scale']=torch.tensor(1.)
 with pytest.raises(ValueError,match='Orphan'):module.official_fp8_state(s)
 s=fixture();s['layer.comfy_quant']=torch.tensor(list(b'{"format":"nf4"}'),dtype=torch.uint8)
 with pytest.raises(ValueError,match='Unsupported'):module.official_fp8_state(s)
def test_text_mapping_explicit_head_and_collision():
 s={'model.embed_tokens.weight':torch.ones(2,2),'lm_head.weight':torch.ones(2,2)}
 assert set(module.official_fp8_state(s,text_encoder=True))=={'language_model.embed_tokens.weight'}
 s['language_model.embed_tokens.weight']=torch.ones(2,2)
 with pytest.raises(ValueError,match='collision'):module.official_fp8_state(s,text_encoder=True)

def test_visual_namespace_is_separate_from_language_encoder():
 assert module.official_text_key("model.visual.blocks.0.norm1.weight")=="visual.blocks.0.norm1.weight"
