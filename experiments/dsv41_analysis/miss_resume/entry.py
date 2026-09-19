"""Isolated experimental runner; never imported by the default Runtime."""
import importlib.util,sys,os,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'experiments/dsv41_mlx'))
spec=importlib.util.spec_from_file_location('miss_resume_model',Path(__file__).with_name('model.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
sys.path.insert(0,str(Path(__file__).parent))
from packet import PacketMixin
from route_packet import RoutePacketMixin
from stress import AllMissStress
class HybridModel(PacketMixin,module.MissResumeModel):pass
import run
import mlx.core as mx
from adaptive import AdaptiveModel
from burst import BurstModel
receipt={}
eager=os.environ.get('DSV41_RESUME_EAGER')=='1'
burst=int(os.environ.get('DSV41_RESUME_BURST','0'))
class ReceiptMixin:
    def __call__(self,ids,start=0):
        y=super().__call__(ids,start)
        dump=os.environ.get('DSV41_RESUME_STATE_DUMP')
        if dump:
            tensors={}
            def walk(v,path):
                if isinstance(v,mx.array):tensors[path]=v
                elif isinstance(v,dict):
                    for k,x in v.items():walk(x,path+'.'+str(k))
            walk(self.states,'states');walk(self.shared,'shared');walk(getattr(self,'fast',{}),'fast');walk(getattr(self,'slow',{}),'slow');walk(self.ages,'ages')
            tensors['cache_counters']=self.cache_counters;tensors['logits']=y
            p=Path(dump);p.mkdir(parents=True,exist_ok=True)
            mx.save_safetensors(str(p/f'start-{start}.safetensors'),tensors)
        return y
    def close(self):
        if not eager:
            receipt.update(self.resume_stats);print('MISS_RESUME_STATS',self.resume_stats,flush=True)
        super().close()
settings={}
def model_factory(args):
    top=args.burst_top or burst
    mode=os.environ.get('DSV41_RESUME_MODE','packet')
    if mode=='window':
        if top not in (2,4):raise ValueError('native windows require Burst Top2/Top4')
        os.environ['DSV41_NATIVE_WINDOW']='1'
        os.environ.setdefault('DSV41_LOCAL_ROOTS','1')
        os.environ.setdefault('DSV41_DEFER_COUNTERS','1')
        os.environ.setdefault('DSV41_DEFER_ROUTE_STATS','1')
    if args.trace or args.layer_progress or args.collect_routes or args.image or args.messages_json or args.static_l1 or args.l1_policy!='eviction_dual' or args.l1_shape or args.main_slots!=40 or args.burst_tail!='zero' or args.prefill_top or args.shared_dispatch or args.fused_gate_up or args.decode_dispatch!='legacy' or args.attention_chunk!=64:
        if mode in ('guarded','window') and not eager:raise ValueError('This configuration requires packet execution, not guarded windows')
        mode='packet'
    settings.update(mode=mode,top=top,output=args.output,requested_block_layers=args.block_layers)
    if eager or mode=='packet':
        base=BurstModel if top else run.StaticModel if args.static_l1 else AdaptiveModel
        bases=(ReceiptMixin,AllMissStress,base) if eager else (ReceiptMixin,AllMissStress,RoutePacketMixin,base)
        extra=dict(burst_top=top,block_layers=args.block_layers if eager else 1,tail_policy=args.burst_tail) if top else {}
    else:
        bases=(ReceiptMixin,AllMissStress,HybridModel)
        extra=dict(resume_block=int(os.environ.get('DSV41_RESUME_BLOCK','4')),resume_burst=top,resume_mode=mode)
    return type('ConfiguredMissResume',bases,{}),extra

# Compatibility with the experiment launcher; ordinary CLI Burst flags are kept.
if burst and not any(a.split('=')[0]=='--burst-top' for a in sys.argv[1:]):sys.argv+=['--burst-top',str(burst)]
run.model_factory=model_factory
run.main()
output=settings['output']/'manifest.json'
burst=settings['top']
data=json.loads(output.read_text());data['miss_resume']={'enabled':not eager,'auto_guarded_enabled':False,'window_admission':'forced' if os.environ.get('DSV41_WINDOW_FORCE')=='1' else 'previous_token_at_most_two_required_miss_layers','async_window':os.environ.get('DSV41_ASYNC_WINDOW')=='1','native_window':os.environ.get('DSV41_NATIVE_WINDOW')=='1','local_roots':os.environ.get('DSV41_LOCAL_ROOTS')=='1','defer_route_stats':os.environ.get('DSV41_DEFER_ROUTE_STATS')=='1','defer_counters':os.environ.get('DSV41_DEFER_COUNTERS')=='1','adaptive_windows':os.environ.get('DSV41_ADAPTIVE_WINDOWS')=='1','native_prefix':os.environ.get('DSV41_NATIVE_PREFIX','1')=='1','local_checkpoints':os.environ.get('DSV41_LOCAL_CHECKPOINTS','1')=='1','mode':settings['mode'],'packet_adapter':settings['mode']=='packet','requested_block_layers':settings['requested_block_layers'],'burst_top':burst,'block':int(os.environ.get('DSV41_RESUME_BLOCK','4')),'stats':receipt,'experimental':True,'stress_all_miss':os.environ.get('DSV41_RESUME_STRESS_ALL_MISS')=='1','source':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*') if p.is_file()},'state_dump':os.environ.get('DSV41_RESUME_STATE_DUMP')}
if burst:
    data['burst_top']=burst;data['scope']+='; approximate Burst Top'+str(burst)+', tail policy '+data['burst_tail']
output.write_text(json.dumps(data,indent=2))
