"""Same 32-slot budget: current-prefill Main24 plus recent Hot8."""
import argparse,hashlib,json,sys
from pathlib import Path
from collections import Counter
import batched_routed,run_metal_cpu_order,run_native_owned
from lru_metal_bank import LRUMetalBank

banks=[]
MAIN_SLOTS=24
class ContextBank(LRUMetalBank):
    def __init__(self,path,l1_ids,**kw):
        super().__init__(path,[],l0_slots=MAIN_SLOTS+8,io_workers=kw.get('io_workers',4))
        self.l0_slots=8;self.context_main=None;self.phase_stats=[];banks.append(self)
    def prime_context(self,indices):
        if self.context_main is not None:raise RuntimeError('one prefill per benchmark')
        counts=Counter(indices.flatten().tolist())
        selected=[e for e,_ in sorted(counts.items(),key=lambda p:(-p[1],p[0]))[:MAIN_SLOTS]]
        selected += [e for e in sorted(self.records) if e not in selected][:MAIN_SLOTS-len(selected)]
        self._load(selected,list(range(MAIN_SLOTS)))
        self.main=dict(zip(selected,range(MAIN_SLOTS)));self.hot.clear();self.context_main=selected
    def prepare(self,ids):
        if self.context_main is None:raise ValueError("context Main prototype requires a multi-token prefill")
        ids=list(dict.fromkeys(ids));l1=sum(e in self.main for e in ids);l0=sum(e in self.hot for e in ids)
        out=super().prepare(ids)
        self.phase_stats.append(dict(requests=len(ids),l1=l1,l0=l0,miss=len(ids)-l1-l0))
        return out

def main():
    global MAIN_SLOTS
    parser=argparse.ArgumentParser(add_help=False);parser.add_argument("--main-slots",type=int,default=24,choices=[24,32,40,48])
    args,remaining=parser.parse_known_args();sys.argv=[sys.argv[0],*remaining];MAIN_SLOTS=args.main_slots
    output=Path(sys.argv[sys.argv.index('--output')+1]);original=batched_routed.forward
    def prefill(x,weights,indices,bank):
        bank.prime_context(indices)
        result=original(x,weights,indices,bank)
        bank.prefill_calls=len(bank.phase_stats)
        return result
    batched_routed.forward=prefill;run_metal_cpu_order.LRUMetalBank=ContextBank
    try:run_native_owned.main()
    finally:
        path=output/'manifest.json'
        if path.exists():
            r=json.loads(path.read_text());r['metal_moe'].update(l1_experts_per_layer=MAIN_SLOTS,l0_slots_per_layer=8,l1_selection='current prefill route frequency, no decode lookahead')
            r['cpu_order_fp8']['l0_slots']=8
            phases=[]
            decode_count=max((len(b.phase_stats)-getattr(b,'prefill_calls',0) for b in banks),default=0)
            for phase in ['prefill',*[f'decode{i}' for i in range(1,decode_count+1)]]:
                counts=Counter()
                for b in banks:
                    n=getattr(b,'prefill_calls',0)
                    rows=b.phase_stats[:n] if phase=='prefill' else b.phase_stats[n+int(phase.removeprefix('decode'))-1:n+int(phase.removeprefix('decode'))]
                    for row in rows:counts.update(row)
                phases.append(dict(phase=phase,**counts))
            r['context_main']={'main':MAIN_SLOTS,'hot':8,'statistics':phases,'priming_experts':sum(len(b.main) for b in banks),'selection':'current prefill frequency, ascending expert ID tie break; unused IDs pad tiny prompts','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
            path.write_text(json.dumps(r,indent=2))
if __name__=='__main__':main()
