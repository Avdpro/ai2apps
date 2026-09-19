"""Rank-128 route head; validation-only selection and held-out cache-aware evaluation."""
import argparse, hashlib, json, time
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten

ROOT=Path('artifacts/dsv41-l2-v2-20260916')

class Predictor(nn.Module):
    def __init__(self):
        super().__init__()
        self.down=nn.Linear(10240,128)
        self.up=nn.Linear(128,40*384)
    def __call__(self,x):
        x=x.reshape(-1,2,5120)
        x=x*mx.rsqrt(mx.mean(x*x,axis=-1,keepdims=True)+1e-6)
        return self.up(nn.gelu(self.down(x.reshape(-1,10240)))).reshape(-1,40,384)

def loss(model,x,y):
    logits=model(x)
    return mx.mean(mx.logsumexp(logits,axis=-1)-mx.mean(mx.take_along_axis(logits,y,axis=-1),axis=-1))

def load(plan,split):
    parts=[]
    for row in plan['samples']:
        if row['split']!=split:continue
        path=ROOT/'data'/row['id']; receipt=json.loads((path/'verified.json').read_text())
        if not receipt['rows']:continue
        with np.load(path/'supervision.npz') as z:
            parts.append((np.concatenate([z['hidden'],z['embedding']],axis=-1),z['top6'].astype(np.int32),z['previous_top6'].astype(np.int32),z['resident']))
    return tuple(np.concatenate([p[i] for p in parts]) for i in range(4))

def validation(model,data):
    x,y,_,_=data; total=0
    for i in range(0,len(x),64):
        n=len(x[i:i+64]);v=loss(model,mx.array(x[i:i+64]),mx.array(y[i:i+64]));total+=v.item()*n
    return total/len(x)

def evaluate(model,data,frequency):
    x,y,prev,resident=data
    methods=['predictor','train_frequency','previous_only','previous_plus_frequency']
    stats={name:{k:dict(useful=0,reads=0) for k in [8,16,32,48]} for name in methods}
    total_misses=0;route_hits=0;layer_hits=np.zeros(40,dtype=np.int64)
    for i in range(0,len(x),64):
        xx=x[i:i+64]; yy=y[i:i+64]; pp=prev[i:i+64]; rr=resident[i:i+64]; n=len(xx)
        logits=model(mx.array(xx));prob=np.array(mx.softmax(logits,axis=-1))
        top=np.argsort(prob,axis=-1)[...,-6:]
        hits=(top[...,None]==yy[...,None,:]).any(axis=-2)
        route_hits+=hits.sum();layer_hits+=hits.sum(axis=(0,2))
        truth=np.zeros((n,40,384),dtype=bool);np.put_along_axis(truth,yy,True,axis=-1)
        previous=np.zeros_like(truth);np.put_along_axis(previous,pp,True,axis=-1)
        eligible=rr==0;eligible[:,:5]=False
        total_misses+=(truth&eligible).sum()
        scores={'predictor':prob,'train_frequency':np.broadcast_to(frequency,prob.shape),
                'previous_only':previous.astype(np.float32)+frequency[None]*1e-3,
                'previous_plus_frequency':previous.astype(np.float32)+frequency[None]}
        for name,score in scores.items():
            allowed=eligible&previous if name=='previous_only' else eligible
            masked=np.where(allowed,score,-np.inf).reshape(n,-1)
            # One global budget across layers 5..39, not N experts per layer.
            order=np.argsort(masked,axis=-1)[:,-48:][:,::-1]
            selected=np.take_along_axis(truth.reshape(n,-1),order,axis=-1)
            valid=np.take_along_axis(allowed.reshape(n,-1),order,axis=-1)
            for k in stats[name]:
                stats[name][k]['useful']+=int((selected[:,:k]&valid[:,:k]).sum())
                stats[name][k]['reads']+=int(valid[:,:k].sum())
    for budgets in stats.values():
        for v in budgets.values():
            v.update(useful_per_token=v['useful']/len(x),reads_per_token=v['reads']/len(x),
                     miss_coverage=v['useful']/max(1,int(total_misses)),precision=v['useful']/max(1,v['reads']),
                     wasted_MB_per_token=(v['reads']-v['useful'])*18800640/len(x)/1e6)
    return dict(rows=len(x),eligible_misses_per_token=int(total_misses)/len(x),
                route_recall6=float(route_hits)/(len(x)*40*6),per_layer_recall6=(layer_hits/(len(x)*6)).tolist(),
                budgets=stats,scope='layers 5..39; global per-token budget; availability oracle at token start, no deadline simulation')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--epochs',type=int,default=10);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    assert json.loads((ROOT/'collection-audit.json').read_text())['status']=='passed'
    plan=json.loads((ROOT/'plan.json').read_text());args.output.mkdir(parents=True,exist_ok=False)
    groups={split:{r['family_id'] for r in plan['samples'] if r['split']==split} for split in ['train','validation','test']}
    assert not groups['train']&groups['validation'] and not groups['train']&groups['test'] and not groups['validation']&groups['test']
    (args.output/'manifest.json').write_text(json.dumps(dict(rank=128,seed=20260916,epochs=args.epochs,selection='minimum validation loss',plan_sha256=hashlib.sha256((ROOT/'plan.json').read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),families={k:sorted(v) for k,v in groups.items()}),indent=2))
    train=load(plan,'train');val=load(plan,'validation')
    mx.random.seed(20260916);rng=np.random.default_rng(20260916);model=Predictor();opt=optim.AdamW(learning_rate=3e-4,weight_decay=1e-3);vg=nn.value_and_grad(model,loss)
    best=float('inf');history=[];start=time.time()
    for epoch in range(args.epochs):
        indices=rng.permutation(len(train[0]));total=0
        for i in range(0,len(indices),32):
            idx=indices[i:i+32];v,g=vg(model,mx.array(train[0][idx]),mx.array(train[1][idx]));opt.update(model,g);mx.eval(model.parameters(),opt.state,v);total+=v.item()*len(idx)
        vl=validation(model,val);row=dict(epoch=epoch+1,train_loss=total/len(indices),validation_loss=vl,elapsed_s=time.time()-start);history.append(row)
        if vl<best:
            best=vl;best_epoch=epoch+1;model.save_weights(str(args.output/'model.safetensors'))
        (args.output/'history.json').write_text(json.dumps(history,indent=2));print(json.dumps(row),flush=True)
    model.load_weights(str(args.output/'model.safetensors'))
    counts=np.stack([np.bincount(train[1][:,l].ravel(),minlength=384) for l in range(40)])
    frequency=(counts/counts.sum(axis=-1,keepdims=True)).astype(np.float32)
    val_result=evaluate(model,val,frequency)
    # Test data is first opened after model selection is complete.
    test=load(plan,'test');test_result=evaluate(model,test,frequency)
    probe=mx.array(test[0][:1]);mx.eval(model(probe));timings=[]
    for _ in range(100):
        begin=time.perf_counter();mx.eval(model(probe));timings.append(time.perf_counter()-begin)
    result=dict(best_epoch=best_epoch,epochs=args.epochs,seconds=time.time()-start,
                parameters=sum(v.size for _,v in tree_flatten(model.parameters())),
                matrix_shapes={k:list(v.shape) for k,v in tree_flatten(model.parameters())},
                predictor_single_token_median_ms=float(np.median(timings))*1000,
                peak_mlx_bytes=mx.get_peak_memory(),validation=val_result,test=test_result,
                limitations=['FP32 isolated head latency, not overlapped inference latency','No SSD deadlines, staging, prefetch competition or TPS measurement','Synthetic corpus and shared instruction templates; real multi-turn holdout remains absent'])
    (args.output/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('validation','test')}),flush=True)
if __name__=='__main__':main()
