"""Validation tuning of a causal reserve policy; total reads never exceed64."""
import argparse,json,sys
from pathlib import Path
import numpy as np
import mlx.core as mx
from train_router_lookahead import Correction,PerLayerCorrection,RoutedCorrection,ROOT
sys.path.insert(0,str(Path('experiments/dsv41_mlx').resolve()))
from storage import Storage
ap=argparse.ArgumentParser();ap.add_argument('--innovation',type=float);ap.add_argument('--affine',type=Path);ap.add_argument('--model',type=Path);ap.add_argument('--output',type=Path);args=ap.parse_args()
affine=None
if args.affine:
 with np.load(args.affine) as z:affine={k:mx.array(z[k]) for k in z.files}
out=args.model or ROOT/'router-lookahead-d1-correction-pilot';meta=json.loads((out/'manifest.json').read_text());model=(RoutedCorrection if meta.get('route_features') else PerLayerCorrection)(39,meta['per_layer_rank']) if meta.get('per_layer_rank',0) else Correction(39);model.load_weights(str(out/'model.safetensors'));s=Storage('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD');w=mx.stack([s.weight(f'layers.{l}.ffn.gate.weight',mx.float32) for l in range(1,40)]).transpose(0,2,1);b=mx.stack([s.weight(f'layers.{l}.ffn.gate.bias',mx.float32) for l in range(1,40)]);norm=mx.stack([s.weight(f'layers.{l}.ffn_norm.weight',mx.float32) for l in range(40)]);ratio=norm[1:]/mx.where(mx.abs(norm[:-1])>1e-6,norm[:-1],mx.ones_like(norm[:-1]));mx.eval(w,b,ratio);s.close()
def predict(x,e,h,ratio,ids):return model(x,e,h,ratio,ids) if meta.get('route_features') else model(x,e,h,ratio)
def gather(names):
 arrays=[];miss=0;counts=[]
 for name in names:
  with np.load(ROOT/'data'/name/'supervision.npz') as z:
   states=z['previous_ffn'];source_ids=z['top6'][:-1,:-1].astype(np.int32);x=states[1:,:-1];previous=states[:-1];e=z['embedding'][:-1];h=z['hidden'][:-1];r=z['resident'][:-1,1:];truth=np.zeros(r.shape,bool);np.put_along_axis(truth,z['top6'][:-1,1:].astype(int),True,axis=-1);nm=(np.take_along_axis(z['resident'][:-1],z['top6'][:-1].astype(int),axis=-1)==0).sum((1,2));counts.append(nm);miss+=int(nm.sum())
   for i in range(0,len(x),32):
    pred=(predict(mx.array(x[i:i+32]),mx.array(e[i:i+32]),mx.array(h[i:i+32]),ratio,mx.array(source_ids[i:i+32])) if args.innovation is None else mx.array(x[i:i+32])*ratio+args.innovation*(mx.array(previous[i:i+32,1:])-mx.array(previous[i:i+32,:-1])*ratio))
    if affine is not None:
     base=mx.array(x[i:i+32])*ratio;residual=mx.array(previous[i:i+32,1:])-mx.array(previous[i:i+32,:-1])*ratio;pred=base*(1+affine['a'])+residual*affine['b']+affine['c']
    raw=mx.matmul(pred.transpose(1,0,2),w).transpose(1,0,2);scores=np.array(mx.sqrt(mx.maximum(mx.logaddexp(raw,0),1e-20))+b);ix=np.argsort(scores,axis=-1)[...,-12:][...,::-1];rank=np.take_along_axis(scores,ix,axis=-1);eligible=np.take_along_axis(r[i:i+32],ix,axis=-1)==0;correct=np.take_along_axis(truth[i:i+32],ix,axis=-1);arrays.append((rank,eligible,correct,ix.astype(np.int16)))
 return tuple(np.pad(np.concatenate([a[i] for a in arrays]),((0,0),(1,0),(0,0))) for i in range(4)),np.concatenate(counts)

output=ROOT/('lookahead-priority-cohort' if args.innovation is None else f'lookahead-innovation-{args.innovation}');output=(ROOT/f'lookahead-affine-{args.affine.stem}') if args.affine else output;output=(args.model/'priority') if args.model else output;output=args.output or output;output.mkdir(exist_ok=False)
for split,key in [('train','train_sequences'),('validation','validation_sequences')]:
 values,misses=gather(meta[key]);np.savez_compressed(output/f'{split}-proposals.npz',scores=values[0],eligible=values[1],correct=values[2],ids=values[3],misses=misses)
(output/'manifest.json').write_text(json.dumps(dict(source_manifest=meta,previous_token_residual_coefficient=args.innovation,affine_file=str(args.affine) if args.affine else None,test_opened=False,causality='Predict target layer L from current FFN input of L-1; layer0 excluded from proposals but all40 included in miss denominator'),indent=2))
