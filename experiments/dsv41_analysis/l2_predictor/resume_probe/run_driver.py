#!/usr/bin/env python3
"""Standalone pure-MLX text runner. No PyTorch imports or CPU tensor arithmetic."""
import argparse,ctypes,hashlib,json,os,subprocess,sys,threading,time
from pathlib import Path
import mlx.core as mx
from tokenizers import Tokenizer
from storage import Storage
from model import Model as StaticModel
from adaptive import AdaptiveModel as Model
model_factory=None

class Usage(ctypes.Structure):
    _fields_=[('uuid',ctypes.c_uint8*16)]+[(str(i),ctypes.c_uint64) for i in range(18)]
class Budget:
    def __init__(self,limit=65_000_000_000):
        self.limit=limit;self.peak=0;self.error=None;self.samples=0;self.stop=threading.Event();self.lib=ctypes.CDLL('/usr/lib/libproc.dylib',use_errno=True)
        self.lib.proc_pid_rusage.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_void_p];self.lib.proc_pid_rusage.restype=ctypes.c_int
        self.sample();self.disk_start=getattr(self,'disk_read_bytes',None);self.worker=threading.Thread(target=self.poll,daemon=True);self.worker.start()
    def sample(self):
        u=Usage()
        if self.lib.proc_pid_rusage(os.getpid(),2,ctypes.byref(u))!=0:self.error='physical footprint sampling failed';return
        self.disk_read_bytes=getattr(u,'16')
        self.current=getattr(u,'7');self.peak=max(self.peak,self.current);self.samples+=1
    def poll(self):
        while not self.stop.wait(.02):self.sample()
    def check(self):
        if self.error:raise RuntimeError(self.error)
        if self.peak>self.limit:raise MemoryError('65 GB physical-footprint budget exceeded')
    def close(self):self.stop.set();self.worker.join();self.sample();self.check()

def main():
    ap=argparse.ArgumentParser(allow_abbrev=False);ap.add_argument('--force-input-tokens',type=Path);ap.add_argument('--checkpoint',type=Path,default=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD'));ap.add_argument('--expert-store',type=Path,default=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/experts'));ap.add_argument('--output',type=Path,required=True);ap.add_argument('--prompt',default='The capital of France is');ap.add_argument('--prompt-json',type=Path);ap.add_argument('--decode',type=int,default=3);ap.add_argument('--main-slots',type=int,default=40,choices=[24,32,36,40,44,48]);ap.add_argument('--trace',action='store_true');ap.add_argument('--layer-progress',action='store_true',help='Synchronize and report every layer (diagnostic; also enabled by --trace)');ap.add_argument('--gather-only',action='store_true');ap.add_argument('--static-l1',action='store_true',help='Disable default dynamic L1 promotion for comparison');ap.add_argument('--burst-top',type=int,choices=[2,4],help='Opt-in approximate Decode: guarantee native Top-N');ap.add_argument('--block-layers',type=int,choices=[1,2,4],default=1,help='Burst transaction size; 1 is sequential control');ap.add_argument('--burst-tail',choices=['zero','zero-renorm','fixed-top','renorm'],default='zero');ap.add_argument('--prefill-slots',type=int,choices=[0,32,64,96],default=0);ap.add_argument('--prefill-top',type=int,choices=[2,4]);ap.add_argument('--attention-chunk',type=int,choices=[64,128,256],default=64);ap.add_argument('--decode-dispatch',choices=['legacy','shared','unsorted'],default='legacy');ap.add_argument('--shared-dispatch',action='store_true');ap.add_argument('--fused-gate-up',action='store_true');ap.add_argument('--prefill-hot-reread',action='store_true',help='Legacy double-buffer Hot handoff control');ap.add_argument('--image',type=Path,action='append',default=[]);ap.add_argument('--vision-max-tokens',type=int,choices=[256,512,1024],default=1024);ap.add_argument('--messages-json',type=Path);ap.add_argument('--stop-at-eos',action='store_true');ap.add_argument('--expert-no-cache',action='store_true');ap.add_argument('--l1-shape',type=Path);ap.add_argument('--collect-routes',action='store_true');ap.add_argument('--logits-mode',choices=['all','hash'],default='all');ap.add_argument('--promotion-reread',action='store_true',help='Diagnostic legacy SSD reread for Hot promotions');ap.add_argument('--l1-policy',choices=['baseline','dual_fast75','probation32_8','eviction_dual'],default='eviction_dual');ap.add_argument('--promotion-copy',action='store_true',help='Diagnostic eviction_dual control: copy payload instead of swapping slot roles');ap.add_argument('--inference-mode',choices=['auto','legacy','packet','guarded','window'],default='auto',help='Default text Decode executor; legacy retains the original path');ap.add_argument('--resume-block',type=int,choices=[1,2,4,40],default=4,help='Window size for guarded/window execution');args=ap.parse_args()
    inference_selection=None
    if __name__=='__main__':
        from inference_mode import launch
        inference_selection=launch(args,sys.argv[1:],ap)
    if args.l1_policy=='eviction_dual' and args.promotion_reread:ap.error('eviction_dual requires Hot memory reuse; use --l1-policy baseline for the legacy reread control')
    main_shape=None;shape_metadata=None
    if args.l1_shape:
        if any(a=='--main-slots' or a.startswith('--main-slots=') for a in sys.argv[1:]):ap.error('--l1-shape and --main-slots are mutually exclusive')
        if args.static_l1 or args.burst_top or args.prefill_top or args.image:ap.error('L1 shape requires dynamic full Top6 text mode')
        from l1_shape import load_shape
        main_shape,shape_metadata=load_shape(args.l1_shape,args.checkpoint)
    if args.messages_json and (args.image or args.prompt_json):ap.error('--messages-json cannot be combined with --image or --prompt-json')
    if args.image and (args.burst_top or args.prefill_top):ap.error('Initial vision integration requires full Top6; Burst is not validated')
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
    config=json.loads((args.checkpoint/'inference/config.json').read_text());config.update(dspark_block_size=0,max_batch_size=1,temperature=0)
    vision_images=[];vision_types=None
    if args.messages_json:
        from types import SimpleNamespace
        from chat import prepare_chat
        messages=json.loads(args.messages_json.read_text())
        if not isinstance(messages,list):raise ValueError('messages must be a list')
        config['vision_max_n_token']=args.vision_max_tokens
        prompt,ids,vision_types,vision_images,args.image=prepare_chat(messages,args.checkpoint,tokenizer,SimpleNamespace(**config))
        if not args.image:config['vision_n_layers']=0;vision_types=None
        if args.image and (args.burst_top or args.prefill_top or args.l1_shape):ap.error('Vision chat requires full Top6 and no experimental L1 shape')
    elif args.image:
        from types import SimpleNamespace
        from vision import prepare_images
        config['vision_max_n_token']=args.vision_max_tokens
        vision_images,image_ids,types=prepare_images(args.image,SimpleNamespace(**config))
        import importlib.util
        encoding_path=args.checkpoint/'encoding/encoding.py'
        spec=importlib.util.spec_from_file_location('dsv41_official_encoding',encoding_path);encoding=importlib.util.module_from_spec(spec);spec.loader.exec_module(encoding)
        content=[{'type':'image_url','image_url':{'url':str(path)}} for path in args.image]+[{'type':'text','text':prompt}]
        prompt=encoding.encode_messages([{'role':'user','content':content}],thinking_mode='chat')
        expanded=[];vision_types=[];image_iter=iter(vision_images)
        for token in tokenizer.encode(prompt).ids:
            if token==config['image_token_id']:
                img=next(image_iter);img.start=len(expanded)
                expanded += [token]*len(img.types);vision_types+=img.types
            else:expanded.append(token);vision_types.append(-1)
        if sum(t==0 for t in vision_types)!=len(vision_images):raise ValueError('Image placeholder/tokenizer mismatch')
        ids=expanded
    else:config['vision_n_layers']=0
    config['max_seq_len']=max(256,len(ids)+args.decode+1)
    budget=Budget();mx.set_cache_limit(2*2**30);mx.set_memory_limit(60_000_000_000);step=0
    receipt={'status':'running','backend':'pure-mlx','prompt':prompt,'input_ids':ids,'config':config,'decode_forwards':args.decode,'requested_decode_forwards':args.decode,'stop_at_eos':args.stop_at_eos,'messages_file':str(args.messages_json) if args.messages_json else None,'main_slots':args.main_slots,'hot_slots':8,'matrix_prefill':not args.gather_only,'l1_policy':'static' if args.static_l1 else 'dynamic','burst_top':args.burst_top,'burst_tail':args.burst_tail,'block_layers':args.block_layers,'prefill_slots':args.prefill_slots,'prefill_hot_direct':not args.prefill_hot_reread,'prefill_top':args.prefill_top,'shared_dispatch':args.shared_dispatch or args.fused_gate_up,'fused_gate_up':args.fused_gate_up,'gate_up_pack':'used-prefix-v2' if args.fused_gate_up else None,'checkpoint_index_sha256':hashlib.sha256((args.checkpoint/'model.safetensors.index.json').read_bytes()).hexdigest(),'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},'official_source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.checkpoint/'inference').glob('*.py')},'images':[str(p) for p in args.image],'checkpoint':str(args.checkpoint.resolve()),'expert_store':str(args.expert_store.resolve()),'scope':'single sequence, greedy; SSD checkpoint; MLX tensor forward, host SSD address metadata; no MTP; '+('dense vision, official chat encoding' if args.image else 'text-only')}
    import importlib.metadata
    receipt['inference_selection']=inference_selection or json.loads(os.environ.get('DSV41_DEFAULT_ENTRY','null'))
    receipt['python_version']=sys.version
    receipt['command_line']=[sys.executable,*sys.argv]
    receipt['working_directory']=os.getcwd()
    receipt['mlx_version']=importlib.metadata.version('mlx')
    marker=args.checkpoint/'ssd-checkpoint.json'
    receipt['ssd_checkpoint_manifest_sha256']=hashlib.sha256(marker.read_bytes()).hexdigest() if marker.exists() else None
    from metal_bank import native
    receipt['native_sha256']=hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest()
    receipt['expert_no_cache']=args.expert_no_cache
    receipt['l1_shape']=shape_metadata
    receipt['main_capacities']=list(main_shape or (args.main_slots,)*40)
    receipt['collect_routes']=args.collect_routes
    receipt['logits_sha256']=[]
    receipt['attention_chunk']=args.attention_chunk
    receipt['decode_dispatch']=args.decode_dispatch
    receipt['layer_progress']=bool(args.layer_progress or args.trace)
    receipt['trace_enabled']=args.trace
    receipt['source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    ref=Path('experiments/dsv41_reference').resolve()
    receipt['cache_source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ref/'metal_bank.py',ref/'lru_metal_bank.py',Path('omlx/custom_kernels/glm_moe_dsa/csrc/expert_loader.cpp')]}
    (args.output/'manifest.json').write_text(json.dumps(receipt,indent=2))
    store=None;model=None;started=time.perf_counter()
    def trace(name,x):
        if args.trace:mx.save_safetensors(str(args.output/f'{step:02d}_{name}.safetensors'),{'value':x})
        if (args.layer_progress or args.trace) and len(name.split('.'))==2:
            mx.eval(x);budget.check();print(json.dumps({'step':step,'layer':name,'elapsed':time.perf_counter()-started}),flush=True)
    try:
        store=Storage(args.checkpoint)
        receipt['source_checkpoint_index_sha256']=store.source_index_sha256
        if model_factory is not None:
            model_type,extra=model_factory(args)
        else:
            model_type=StaticModel if args.static_l1 else Model;extra={}
            if args.burst_top is not None:
                from burst import BurstModel
                model_type=BurstModel;extra=dict(burst_top=args.burst_top,block_layers=args.block_layers,tail_policy=args.burst_tail)
        if args.collect_routes:
            from route_capture import captured_model
            model_type=captured_model(model_type,args.output)
        model=model_type(config,store,tokenizer,args.expert_store,config['max_seq_len'],args.main_slots,trace=trace,matrix_prefill=not args.gather_only,prefill_slots=args.prefill_slots,prefill_top=args.prefill_top,shared_dispatch=args.shared_dispatch,fused_gate_up=args.fused_gate_up,prefill_hot_direct=not args.prefill_hot_reread,decode_dispatch=args.decode_dispatch,attention_chunk=args.attention_chunk,main_shape=main_shape,expert_no_cache=args.expert_no_cache,**extra)
        if hasattr(model,'reuse_hot_promotions'):model.reuse_hot_promotions=not args.promotion_reread
        if hasattr(model,'l1_policy'):model.l1_policy=args.l1_policy
        receipt['l1_policy']=args.l1_policy
        if hasattr(model,'slot_swap_promotions'):model.slot_swap_promotions=not args.promotion_copy
        receipt['promotion_slot_swap']=args.l1_policy=='eviction_dual' and not args.promotion_copy
        receipt['promotion_reuse']=not args.promotion_reread
        if args.image:
            from vision import Vision
            model.vision=Vision(store,model.c);model.vision_images=vision_images;model.vision_types=mx.array([vision_types],dtype=mx.int32)
            receipt['vision_stages']=[]
            def stage(name):
                mx.synchronize();budget.sample();budget.check()
                receipt['vision_stages'].append(dict(stage=name,footprint_bytes=budget.current,active_bytes=mx.get_active_memory(),peak_bytes=budget.peak))
            model.vision_stage=stage;stage('before_vision_weights')
            receipt['vision_weight_bytes']=model.vision.load();stage('vision_weights_resident')
            receipt['image_inputs']=[dict(path=i.path,sha256=hashlib.sha256(Path(i.path).read_bytes()).hexdigest(),vit_grid=[i.n_vit_h,i.n_vit_w],span_tokens=len(i.types)) for i in vision_images]
        if 'torch' in sys.modules:raise RuntimeError('PyTorch imported in pure MLX process')
        receipt['model_init_seconds']=time.perf_counter()-started
        forced=json.loads(args.force_input_tokens.read_text()) if args.force_input_tokens else None
        if forced is not None:assert len(forced)>=args.decode
        receipt['forced_input_tokens']=str(args.force_input_tokens) if args.force_input_tokens else None
        print('Pure MLX model initialized',flush=True);generated=[];times=[];memory=[];x=mx.array([ids],dtype=mx.int32);pos=0
        for step in range(args.decode+1):
            t=time.perf_counter();logits=model(x,pos)
            from guarded_model import arrays
            mx.eval(logits,model.cache_counters,*model.ages.values(),*arrays((model.states,model.shared)))
            if not bool(mx.all(mx.isfinite(logits)).item()):raise FloatingPointError('nonfinite logits')
            token=int(mx.argmax(logits,axis=-1).item());times.append(time.perf_counter()-t)
            if step==0 and model.prefill_executor is not None:model.prefill_executor.release()
            if step==0:
                budget.sample();receipt['kernel_after_prefill_read_bytes']=budget.disk_read_bytes
            import numpy as np
            receipt['logits_sha256'].append(hashlib.sha256(np.array(logits.astype(mx.float32)).tobytes()).hexdigest())
            if os.environ.get('L2_AUDIT_STATE')=='1':
                tensors={};metadata={}
                def walk(v,path):
                    if isinstance(v,mx.array):tensors[path]=v
                    elif isinstance(v,dict):
                        for k,xv in v.items():walk(xv,path+'.'+str(k))
                    elif isinstance(v,(list,tuple)):
                        for k,xv in enumerate(v):walk(xv,path+'.'+str(k))
                    elif v is None or isinstance(v,(int,float,str,bool)):metadata[path]=v
                for name in ('states','shared','fast','slow','frequency','ages','ticks','cache_counters'):
                    walk(getattr(model,name),name)
                walk(model.hash.cache,'engram_hash')
                mx.save_safetensors(str(args.output/f'state-{step:02d}.safetensors'),tensors)
                (args.output/f'state-{step:02d}.json').write_text(json.dumps(metadata,sort_keys=True))

            if args.logits_mode=='all':mx.save_safetensors(str(args.output/f'{step:02d}_logits.safetensors'),{'logits':logits})
            if args.image:stage('prefill_done' if step==0 else 'decode_'+str(step))
            generated.append(token);pos+=x.shape[1];x=mx.array([[forced[step] if forced is not None and step<len(forced) else token]],dtype=mx.int32)
            memory.append({'active':mx.get_active_memory(),'cache':mx.get_cache_memory(),'peak':mx.get_peak_memory()});budget.check()
            if forced is None and args.stop_at_eos and token==tokenizer.token_to_id('<｜end▁of▁sentence｜>'):break
        if 'torch' in sys.modules:raise RuntimeError('PyTorch imported during forward')
        receipt['cold_ttft_seconds']=receipt['model_init_seconds']+times[0]
        counts=mx.sum(model.cache_counters,axis=0).tolist();model.stats.update(l1_hits=counts[0],l0_hits=counts[1],misses=counts[2])
        receipt.update(status='complete',decode_forwards=len(times)-1,generated_ids=generated,generated_text=tokenizer.decode(generated,skip_special_tokens=False),step_seconds=times,allocator_steps=memory,torch_imported=False,cache_stats=model.stats)
    except BaseException as e:
        receipt.update(status='failed',error=repr(e));raise
    finally:
        try:
            if model is not None:model.close()
            elif store is not None:store.close()
        except BaseException as e:receipt.update(status='failed',error='cleanup: '+repr(e))
        try:budget.close()
        except BaseException as e:receipt.update(status='failed',error=repr(e))
        if budget.disk_start is not None:
            receipt['kernel_disk_read_bytes']=max(0,budget.disk_read_bytes-budget.disk_start)
            receipt['kernel_decode_disk_read_bytes']=max(0,budget.disk_read_bytes-receipt.get('kernel_after_prefill_read_bytes',budget.disk_read_bytes))
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
        if args.collect_routes:receipt['route_files_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.glob('routes.*')}
        receipt['trace_files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.glob('*.safetensors')}
        (args.output/'manifest.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({k:receipt.get(k) for k in ['status','error','step_seconds','generated_text','sampled_physical_footprint_peak_bytes','torch_imported']}),flush=True)
if __name__=='__main__':main()
