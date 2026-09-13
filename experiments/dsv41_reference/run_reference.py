#!/usr/bin/env python3
"""SSD reference using unedited official model.py and explicit CPU kernel translation."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import struct
import sys
import time
import types
import resource
import subprocess
import torch

DTYPES = {'F32': torch.float32, 'BF16': torch.bfloat16, 'F8_E4M3': torch.float8_e4m3fn,
          'F8_E8M0': torch.float8_e8m0fnu, 'I8': torch.int8, 'I64': torch.int64, 'I32': torch.int32}

class Store:
    def __init__(self, root):
        self.entries, self.fds = {}, {}
        self.bytes = self.reads = 0
        for path in sorted(root.glob('*.safetensors')):
            fd = os.open(path, os.O_RDONLY)
            self.fds[path.name] = fd
            size = struct.unpack('<Q', os.pread(fd, 8, 0))[0]
            header = json.loads(os.pread(fd, size, 8))
            for name, entry in header.items():
                if name == '__metadata__': continue
                if name in self.entries: raise ValueError(f'duplicate {name}')
                self.entries[name] = (fd, size+8, entry)
    def read(self, name, rows=None):
        fd, base, e = self.entries[name]
        lo, hi = e['data_offsets']
        shape = e['shape']
        def get(offset, length):
            raw = os.pread(fd, length, offset)
            if len(raw) != length: raise IOError(f'short read {name}')
            self.bytes += length; self.reads += 1
            return torch.frombuffer(bytearray(raw), dtype=DTYPES[e['dtype']])
        if rows is None:
            return get(base+lo, hi-lo).reshape(shape)
        stride = (hi-lo)//shape[0]
        ids = rows.flatten().tolist()
        if any(i < 0 or i >= shape[0] for i in ids): raise IndexError(name)
        # Byte-wise stack works with shell float8 dtypes on CPU.
        vals = [get(base+lo+i*stride, stride).view(torch.uint8) for i in ids]
        return torch.stack(vals).view(DTYPES[e['dtype']]).reshape(*rows.shape, *shape[1:])
    def close(self):
        for fd in self.fds.values(): os.close(fd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--checkpoint', type=Path, default=Path('artifacts/dsv41-download/DeepSeek-V4.1-Flash'))
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--prompt', default='The capital of France is')
    ap.add_argument('--decode', type=int, default=3, help='number of one-token decode forwards after prefill')
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--backend', choices=['cpu', 'cuda'], default='cpu')
    args = ap.parse_args()
    if args.decode < 0: ap.error('--decode must be nonnegative')
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(args.threads)
    torch.set_default_dtype(torch.bfloat16)
    torch.manual_seed(33377335)
    if args.backend == 'cpu':
        import cpu_kernel
        sys.modules['kernel'] = cpu_kernel
    elif not torch.cuda.is_available():
        raise RuntimeError('Official TileLang backend requires CUDA')
    device = args.backend
    sys.path.insert(0, str(args.checkpoint.resolve()/'inference'))
    model = importlib.import_module('model')
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint, local_files_only=True)
    config = json.loads((args.checkpoint/'inference/config.json').read_text())
    input_ids = tokenizer.encode(args.prompt)
    config.update(max_batch_size=1, max_seq_len=max(256, len(input_ids)+args.decode+1), temperature=0,
                  vision_n_layers=0, dspark_block_size=0)
    # Only parameter-heavy leaf construction uses meta; official runtime buffers/hash stay real.
    for cls in [model.Linear, model.ParallelEmbedding, model.ParallelEngramEmbedding, model.ParallelHead]:
        original = cls.__init__
        def init(self, *a, _original=original, **kw):
            with torch.device('meta'): _original(self, *a, **kw)
        cls.__init__ = init
    print('Building official model with meta weight placeholders', flush=True)
    with torch.device(device): net = model.Transformer(model.ModelArgs(**config), tokenizer)
    net.eval()
    store = Store(args.checkpoint)
    names = dict(net.named_modules())
    templates = {n: {k: torch.empty(p.shape, dtype=p.dtype, device='meta') for k,p in m.named_parameters(recurse=False)}
                 for n,m in names.items()}
    # Fail before inference if any active parameter cannot be resolved.
    missing = [f'{n}.{k}'.lstrip('.') for n, ps in templates.items() for k in ps
               if f'{n}.{k}'.lstrip('.') not in store.entries]
    if missing: raise ValueError(f'Missing weights: {missing}')
    step = [0]
    def save(label, value):
        def cpu(v):
            if isinstance(v, torch.Tensor):
                if v.is_floating_point() and not torch.isfinite(v.float()).all():
                    raise FloatingPointError(f'nonfinite trace {label}')
                return v.detach().cpu().clone()
            if isinstance(v, (tuple,list)): return tuple(cpu(x) for x in v)
            return v
        torch.save(cpu(value), args.output/f'{step[0]:02d}_{label}.pt')
    def load_module(n, m):
        for k, template in templates[n].items():
            key = f'{n}.{k}'.lstrip('.')
            x = store.read(key)
            if key.endswith('wo_a.weight'):
                scale = store.read(key.replace('.weight', '.scale')).float()
                x = (x.float().unflatten(0, (-1,32)).unflatten(-1,(-1,32)) * scale[:,None,:,None]).flatten(2,3).flatten(0,1).bfloat16()
            elif template.dtype == torch.float4_e2m1fn_x2:
                x = x.view(template.dtype)
            else:
                x = x.to(template.dtype)
            if tuple(x.shape) != tuple(template.shape): raise ValueError((key,x.shape,template.shape))
            m._parameters[k] = torch.nn.Parameter(x.to(device), requires_grad=False)
        if 'scale' in templates[n] and 'weight' in templates[n]: m.weight.scale = m.scale
    def release(n,m):
        for k,t in templates[n].items(): m._parameters[k] = torch.nn.Parameter(t, requires_grad=False)
    # Sparse embeddings differ only in storage access, never hash/dequant semantics.
    for n,m in names.items():
        if isinstance(m, (model.ParallelEngramEmbedding, model.ParallelEmbedding)):
            def lookup(self, ids, _n=n):
                if isinstance(self, model.ParallelEngramEmbedding):
                    values = store.read(_n+'.weight', ids).float().unflatten(-1,(-1,self.block_size))
                    scales = store.read(_n+'.scale', ids).float()
                    result = (values*scales[...,None]).flatten(-2).bfloat16().to(device)
                    save(_n+'_rows', (ids,result))
                    return result
                return store.read(_n+'.weight',ids).to(device)
            m.forward = types.MethodType(lookup,m)
            continue
        if n.endswith('.wo_a'): continue # official attention reads this weight directly
        if templates[n]:
            m.register_forward_pre_hook(lambda m,a,_n=n: load_module(_n,m))
            m.register_forward_hook(lambda m,a,o,_n=n: release(_n,m), always_call=True)
        if isinstance(m, model.Attention):
            m.register_forward_pre_hook(lambda m,a,_n=n: load_module(_n+'.wo_a',m.wo_a))
            m.register_forward_hook(lambda m,a,o,_n=n: release(_n+'.wo_a',m.wo_a), always_call=True)
        if isinstance(m, (model.Block, model.Attention, model.MoE, model.Gate, model.Engram)):
            m.register_forward_hook(lambda m,a,o,_n=n: save(_n,o))
        if isinstance(m,model.Block):
            m.register_forward_pre_hook(lambda m,a,_n=n: save(_n+'_input',a))
            def progress(m,a,o,_n=n):
                print(json.dumps({'step':step[0],'layer':_n,'seconds':round(time.time()-started,2),'read_GiB':round(store.bytes/2**30,3)}),flush=True)
            m.register_forward_hook(progress)
    receipt = {'status':'running','backend':args.backend,'reference_class':'official-model-cpu-kernel-translation' if device=='cpu' else 'official-model-tilelang',
               'cuda_parity_validated':False,'prompt':args.prompt,'input_ids':input_ids,'decode_forwards':args.decode,
               'config':config,'torch':torch.__version__,'threads':args.threads,
               'source_sha256':{str(p.relative_to(args.checkpoint)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.checkpoint/'inference').glob('*.py')},
               'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'kernel_sha256':hashlib.sha256((Path(__file__).parent/'cpu_kernel.py').read_bytes()).hexdigest()}
    receipt['source_commit'] = subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    receipt['checkpoint'] = str(args.checkpoint.resolve())
    receipt['checkpoint_index_sha256'] = hashlib.sha256((args.checkpoint/'model.safetensors.index.json').read_bytes()).hexdigest()
    receipt['sampling'] = 'greedy; prefill yields first output token, each decode forward yields one more'
    (args.output/'manifest.json').write_text(json.dumps(receipt,indent=2))
    started=time.time(); generated=[]; timings=[]; pos=0
    try:
        x = torch.tensor([input_ids],dtype=torch.long,device=device)
        with torch.inference_mode():
            for i in range(args.decode+1):
                step[0]=i; t=time.time()
                y,logits,_ = net(x,pos)
                save('logits',logits)
                top = logits.float().topk(10,dim=-1)
                save('top10',(top.indices,top.values))
                torch.save({k:v.detach().cpu().clone() if isinstance(v,torch.Tensor) else v
                            for k,v in vars(model.shared_attn).items()},args.output/f'{i:02d}_shared_attention.pt')
                # Runtime buffers and cross-layer owner state for rollback/cache comparisons.
                torch.save({n:b.detach().cpu().clone() for n,b in net.named_buffers()}, args.output/f'{i:02d}_buffers.pt')
                token=int(y.item()); generated.append(token)
                timings.append(time.time()-t)
                pos += x.shape[1]; x=y.reshape(1,1)
        receipt.update(status='complete',generated_ids=generated,generated_text=tokenizer.decode(generated),step_seconds=timings,
                       total_seconds=time.time()-started,read_bytes=store.bytes,read_calls=store.reads,
                       max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        receipt['trace_files'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.output.glob('*.pt'))}
        print(json.dumps(receipt,ensure_ascii=False),flush=True)
    except BaseException as e:
        receipt.update(status='failed',error=repr(e),total_seconds=time.time()-started)
        raise
    finally:
        (args.output/'manifest.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False))
        store.close()

if __name__ == '__main__': main()
