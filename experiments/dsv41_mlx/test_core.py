"""Semantic regression tests; CPU reference is imported only in this test process."""
import ast,functools,json,math
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import torch
import mlx.core as mx
from tokenizers import Tokenizer
from kernels import rope_freq
from engram import HashState
from model import Model

root=Path('artifacts/dsv41-download/DeepSeek-V4.1-Flash');config=json.loads((root/'inference/config.json').read_text())
old=torch.get_default_dtype();torch.set_default_dtype(torch.bfloat16)
try:
    tree=ast.parse((root/'inference/model.py').read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='precompute_freqs_cis']
    ns={'torch':torch,'math':math,'lru_cache':functools.lru_cache};exec(compile(ast.Module(body=nodes,type_ignores=[]),'official-rope','exec'),ns)
    a=ns['precompute_freqs_cis'](64,2048,65536,160000,16,32,1)
    cos,sin=rope_freq(64,2048,65536,160000,16,32,1);mx.eval(cos,sin)
    error=max(np.max(np.abs(np.array(cos)-a.real.float().numpy())),np.max(np.abs(np.array(sin)-a.imag.float().numpy())))
    print('YaRN cos/sin max_abs',float(error));assert error<.0002
finally:torch.set_default_dtype(old)

m=Model.__new__(Model);res=mx.arange(24).reshape(1,2,4,3).astype(mx.bfloat16);x=mx.zeros((1,2,3),dtype=mx.bfloat16)
comb=mx.zeros((1,2,4,4),dtype=mx.float32)
for i in range(4):comb[:,:,i,(i+1)%4]=1
out=m.hc_post(x,res,mx.zeros((1,2,4),dtype=mx.float32),comb);mx.eval(out)
assert np.array_equal(np.array(out.astype(mx.float32)),np.array(res[:,:,[3,0,1,2],:].astype(mx.float32)))
print('mHC source/destination orientation passed')

ref=Path('artifacts/dsv41-native-sdpa-profile2048-20260913');r=json.loads((ref/'manifest.json').read_text())
h=HashState(SimpleNamespace(**config),Tokenizer.from_file(str(root/'tokenizer.json')),2081);ids=r['input_ids'];start=0
for step in range(3):
    result=h(mx.array([ids],dtype=mx.int32),start);mx.eval(result);actual=np.array(result)
    for j,l in enumerate([1,14]):
        expected,_=torch.load(ref/f'{step:02d}_layers.{l}.engram.embed_rows.pt',weights_only=True)
        assert np.array_equal(actual[:,:,j],expected.numpy())
    start+=len(ids);ids=[r['generated_ids'][step]]
print('2048+2-step GPU Engram hash exact against saved reference')
