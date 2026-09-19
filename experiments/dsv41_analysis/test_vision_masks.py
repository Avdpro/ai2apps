"""Check image boundaries cannot leak into text n-grams, including following Decode."""
import sys,json
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import mlx.core as mx
import numpy as np
from tokenizers import Tokenizer
from engram import HashState
root=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD');c=SimpleNamespace(**json.load(open(root/'inference/config.json')))
h=HashState(c,Tokenizer.from_file(str(root/'tokenizer.json')),64)
ids=[15,16,c.image_token_id,c.image_token_id,17,18,c.image_token_id,19];mask=[True,True,False,False,True,True,False,True]
a=h(mx.array([ids],dtype=mx.int32),0,mx.array([mask]));b=h(mx.array([[20]],dtype=mx.int32),len(ids));mx.eval(a,b)
cache=np.array(h.cache).tolist();m=np.array(h.mult).reshape(h.layers,h.ngram,2);pr=np.array(h.primes);off=np.array(h.offsets)
expected=np.zeros((1,len(ids)+1,h.layers,h.cols),dtype=np.int32)
for pos in range(len(ids)+1):
 for layer in range(h.layers):
  for col in range(h.cols):
   rolling=0;blocked=False
   for j in range(col//h.heads+2):
    blocked=blocked or pos<j or cache[pos-j]==-1
    token=h.pad if blocked else cache[pos-j];mult=int(m[layer,j,0])|(int(m[layer,j,1])<<32)
    rolling^=token*mult
   expected[0,pos,layer,col]=rolling%int(pr[layer,col])+int(off[layer,col])
actual=np.concatenate([np.array(a),np.array(b)],axis=1);assert np.array_equal(actual,expected)
print('Image-mask n-gram Prefill and Decode checks passed')
