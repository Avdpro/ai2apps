"""Validate rollback snapshot handles and alias preservation under MLX mutation."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
import mlx.core as mx
from burst import snapshot_tree
x=mx.arange(16).reshape(4,4)
state=({'kv':x},{'shared':x})
saved=snapshot_tree(state)
assert saved[0]['kv'] is saved[1]['shared']
assert saved[0]['kv'] is not x
x[0,0]=99
mx.eval(x,saved[0]['kv'])
assert x[0,0].item()==99 and saved[0]['kv'][0,0].item()==0
saved[0]['kv'][1,1]=-7
mx.eval(x,saved[1]['shared'])
assert x[1,1].item()==5 and saved[1]['shared'][1,1].item()==-7
print('Rollback snapshot preserves values and shared aliases across MLX updates')
