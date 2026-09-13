#!/usr/bin/env python3
"""Standalone pure-MLX text runner. No PyTorch imports or CPU tensor arithmetic."""
import argparse,ctypes,hashlib,json,os,subprocess,sys,threading,time
from pathlib import Path
import mlx.core as mx
from tokenizers import Tokenizer
from storage import Storage
from model import Model as StaticModel
from adaptive import AdaptiveModel as Model

class Usage(ctypes.Structure):
    _fields_=[('uuid',ctypes.c_uint8*16)]+[(str(i),ctypes.c_uint64) for i in range(18)]
class Budget:
    def __init__(self,limit=65_000_000_000):
        self.limit=limit;self.peak=0;self.error=None;self.samples=0;self.stop=threading.Event();self.lib=ctypes.CDLL('/usr/lib/libproc.dylib',use_errno=True)
        self.lib.proc_pid_rusage.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_void_p];self.lib.proc_pid_rusage.restype=ctypes.c_int
        self.sample();self.worker=threading.Thread(target=self.poll,daemon=True);self.worker.start()
    def sample(self):
        u=Usage()
        if self.lib.proc_pid_rusage(os.getpid(),2,ctypes.byref(u))!=0:self.error='physical footprint sampling failed';return
        self.peak=max(self.peak,getattr(u,'7'));self.samples+=1
    def poll(self):
        while not self.stop.wait(.02):self.sample()
    def check(self):
        if self.error:raise RuntimeError(self.error)
        if self.peak>self.limit:raise MemoryError('65 GB physical-footprint budget exceeded')
    def close(self):self.stop.set();self.worker.join();self.sample();self.check()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--checkpoint',type=Path,default=Path('artifacts/dsv41-download/DeepSeek-V4.1-Flash'));ap.add_argument('--expert-store',type=Path,default=Path('artifacts/dsv41-full-expert-store'));ap.add_argument('--output',type=Path,required=True);ap.add_argument('--prompt',default='The capital of France is');ap.add_argument('--prompt-json',type=Path);ap.add_argument('--decode',type=int,default=3);ap.add_argument('--main-slots',type=int,default=40,choices=[24,32,40,48]);ap.add_argument('--trace',action='store_true');ap.add_argument('--gather-only',action='store_true');ap.add_argument('--static-l1',action='store_true',help='Disable default dynamic L1 promotion for comparison');ap.add_argument('--burst-top',type=int,choices=[2,4],help='Opt-in approximate Decode: guarantee native Top-N');ap.add_argument('--block-layers',type=int,choices=[1,2,4],default=1,help='Burst transaction size; 1 is sequential control');ap.add_argument('--burst-tail',choices=['zero','zero-renorm','fixed-top','renorm'],default='zero');ap.add_argument('--prefill-slots',type=int,choices=[0,32,64,96],default=0);ap.add_argument('--prefill-top',type=int,choices=[2,4]);ap.add_argument('--shared-dispatch',action='store_true');ap.add_argument('--fused-gate-up',action='store_true');args=ap.parse_args()
    if args.prefill_top and not args.prefill_slots:ap.error('--prefill-top requires --prefill-slots')
    if args.burst_tail!='zero' and (args.burst_top is None or args.block_layers!=1):ap.error('experimental tail weighting requires Burst and Block1')
    if args.burst_top is None and args.block_layers!=1:ap.error('--block-layers requires --burst-top')
    if args.burst_top is not None and args.static_l1:ap.error('Burst currently requires default dynamic L1')
    if args.decode<0:raise ValueError('decode count')
    args.output.mkdir(parents=True,exist_ok=False)
    prompt=json.loads(args.prompt_json.read_text())['prompt'] if args.prompt_json else args.prompt
    tokenizer=Tokenizer.from_file(str(args.checkpoint/'tokenizer.json'));ids=tokenizer.encode(prompt).ids
    if not ids:raise ValueError('empty input')
    if args.prompt_json:
        fixture=json.loads(args.prompt_json.read_text())
        if 'input_ids' in fixture and fixture['input_ids']!=ids:raise ValueError('tokenizer input mismatch')
    config=json.loads((args.checkpoint/'inference/config.json').read_text());config.update(vision_n_layers=0,dspark_block_size=0,max_batch_size=1,temperature=0,max_seq_len=max(256,len(ids)+args.decode+1))
    budget=Budget();mx.set_cache_limit(2*2**30);mx.set_memory_limit(60_000_000_000);step=0
    receipt={'status':'running','backend':'pure-mlx','prompt':prompt,'input_ids':ids,'config':config,'decode_forwards':args.decode,'main_slots':args.main_slots,'hot_slots':8,'matrix_prefill':not args.gather_only,'l1_policy':'static' if args.static_l1 else 'dynamic','burst_top':args.burst_top,'burst_tail':args.burst_tail,'block_layers':args.block_layers,'prefill_slots':args.prefill_slots,'prefill_top':args.prefill_top,'shared_dispatch':args.shared_dispatch or args.fused_gate_up,'fused_gate_up':args.fused_gate_up,'gate_up_pack':'used-prefix-v2' if args.fused_gate_up else None,'checkpoint_index_sha256':hashlib.sha256((args.checkpoint/'model.safetensors.index.json').read_bytes()).hexdigest(),'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},'official_source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.checkpoint/'inference').glob('*.py')},'scope':'single sequence, text, greedy; original checkpoint; MLX tensor forward, host SSD address metadata; no MTP or vision'}
    receipt['source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    ref=Path(__file__).resolve().parents[1]/'dsv41_reference'
    receipt['cache_source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ref/'metal_bank.py',ref/'lru_metal_bank.py',Path('omlx/custom_kernels/glm_moe_dsa/csrc/expert_loader.cpp')]}
    (args.output/'manifest.json').write_text(json.dumps(receipt,indent=2))
    store=None;model=None;started=time.perf_counter()
    def trace(name,x):
        if args.trace:mx.save_safetensors(str(args.output/f'{step:02d}_{name}.safetensors'),{'value':x})
        if len(name.split('.'))==2:
            mx.eval(x);budget.check();print(json.dumps({'step':step,'layer':name,'elapsed':time.perf_counter()-started}),flush=True)
    try:
        store=Storage(args.checkpoint);model_type=StaticModel if args.static_l1 else Model;extra={}
        if args.burst_top is not None:
            from burst import BurstModel
            model_type=BurstModel;extra=dict(burst_top=args.burst_top,block_layers=args.block_layers,tail_policy=args.burst_tail)
        model=model_type(config,store,tokenizer,args.expert_store,config['max_seq_len'],args.main_slots,trace=trace,matrix_prefill=not args.gather_only,prefill_slots=args.prefill_slots,prefill_top=args.prefill_top,shared_dispatch=args.shared_dispatch,fused_gate_up=args.fused_gate_up,**extra)
        if 'torch' in sys.modules:raise RuntimeError('PyTorch imported in pure MLX process')
        print('Pure MLX model initialized',flush=True);generated=[];times=[];memory=[];x=mx.array([ids],dtype=mx.int32);pos=0
        for step in range(args.decode+1):
            t=time.perf_counter();logits=model(x,pos);mx.eval(logits,model.cache_counters,*model.ages.values())
            if not bool(mx.all(mx.isfinite(logits)).item()):raise FloatingPointError('nonfinite logits')
            token=int(mx.argmax(logits,axis=-1).item());times.append(time.perf_counter()-t)
            if step==0 and model.prefill_executor is not None:model.prefill_executor.release()
            mx.save_safetensors(str(args.output/f'{step:02d}_logits.safetensors'),{'logits':logits})
            generated.append(token);pos+=x.shape[1];x=mx.array([[token]],dtype=mx.int32)
            memory.append({'active':mx.get_active_memory(),'cache':mx.get_cache_memory(),'peak':mx.get_peak_memory()});budget.check()
        if 'torch' in sys.modules:raise RuntimeError('PyTorch imported during forward')
        counts=mx.sum(model.cache_counters,axis=0).tolist();model.stats.update(l1_hits=counts[0],l0_hits=counts[1],misses=counts[2])
        receipt.update(status='complete',generated_ids=generated,generated_text=tokenizer.decode(generated,skip_special_tokens=False),step_seconds=times,allocator_steps=memory,torch_imported=False,cache_stats=model.stats)
    except BaseException as e:
        receipt.update(status='failed',error=repr(e));raise
    finally:
        try:
            if model is not None:model.close()
            elif store is not None:store.close()
        except BaseException as e:receipt.update(status='failed',error='cleanup: '+repr(e))
        try:budget.close()
        except BaseException as e:receipt.update(status='failed',error=repr(e))
        receipt.update(total_seconds=time.perf_counter()-started,sampled_physical_footprint_peak_bytes=budget.peak,memory_budget_bytes=budget.limit,memory_samples=budget.samples)
        if store is not None:receipt.update(read_bytes=store.read_bytes,read_calls=store.read_calls,weight_payload_bytes=store.payload_bytes)
        if model is not None and model.prefill_executor is not None:
            receipt['prefill_report']=model.prefill_executor.report
            model.prefill_executor.release()
        if model is not None:receipt['expert_read_bytes']=sum(b.bytes for b in model.banks.values());receipt['expert_io_seconds']=sum(b.io_seconds for b in model.banks.values())
        if model is not None:
            scratch=receipt.get('prefill_report',{})
            receipt['expert_total_read_bytes']=receipt['expert_read_bytes']+scratch.get('read_bytes',0)
            receipt['expert_total_io_seconds']=receipt['expert_io_seconds']+scratch.get('io_seconds',0)
        if model is not None and hasattr(model,'adaptive_report'):
            receipt['adaptive_l1']=model.adaptive_report
            (args.output/'adaptive-l1.json').write_text(json.dumps(model.adaptive_report,indent=2))
        if model is not None and hasattr(model,'burst_report'):
            receipt['burst']=model.burst_report
            (args.output/'burst.json').write_text(json.dumps(model.burst_report,indent=2))
        receipt['trace_files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.glob('*.safetensors')}
        (args.output/'manifest.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({k:receipt.get(k) for k in ['status','error','step_seconds','generated_text','sampled_physical_footprint_peak_bytes','torch_imported']}),flush=True)
if __name__=='__main__':main()
