"""Collect attention-independent FFN residual estimates as causal same-layer features."""
import hashlib,json,shutil
from pathlib import Path
root=Path('artifacts/dsv41-l2-preattn-v4-20260916');root.mkdir(exist_ok=False)
source=root/'source';shutil.copytree('artifacts/dsv41-l2-state-v3-20260916/source',source,symlinks=True)
model=source/'experiments/dsv41_mlx/model.py';s=model.read_text();needle="            residual=h;attn_pre,attn_post,attn_comb=self.hc_mixes(p,h,'attn')";assert s.count(needle)==1
s=s.replace(needle,needle+"\n            estimate=self.hc_post(mx.zeros((1,1,c.dim),dtype=h.dtype),h[:,-1:],attn_post[:,-1:],attn_comb[:,-1:])\n            self.emit(p+'.l2_preattn',self.norm(p+'.ffn_norm',self.hc_pre(estimate,attn_pre[:,-1:]))[0,0])")
model.write_text(s)
p=source/'experiments/dsv41_mlx/collector.py';s=p.read_text();s=s.replace("        if name.endswith('.l2_ffn'):","        if name.endswith('.l2_preattn'):\n            self.pending[('preattn', int(name.split('.')[1]))] = value.astype(mx.float32)\n        elif name.endswith('.l2_ffn'):")
s=s.replace("        self.export_arrays += [self.pending[('ffn', l)] for l in range(40)]","        self.export_arrays += [self.pending[('ffn', l)] for l in range(40)]\n        self.export_arrays += [self.pending[('preattn', l)] for l in range(40)]")
s=s.replace("        current_ffn = np.stack([np.array(self.pending[('ffn', l)]) for l in range(40)])","        current_ffn = np.stack([np.array(self.pending[('ffn', l)]) for l in range(40)])\n        current_preattn = np.stack([np.array(self.pending[('preattn', l)]) for l in range(40)])")
s=s.replace('dict(previous_ffn=self.previous_ffn,','dict(actual_ffn=current_ffn,preattn=current_preattn,');p.write_text(s)
(root/'source-hashes.json').write_text(json.dumps({str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*.py')},indent=2))
plan=json.loads(Path('artifacts/dsv41-l2-state-v3-20260916/plan.json').read_text());plan['schema']='dsv41.l2-supervision/v4';plan['samples']=plan['pilot_samples'];plan['maximum_rows']=sum(r['decode_steps'] for r in plan['samples']);plan['extra_feature']='Current layer pre-attention residual-only FFN input estimate; actual_ffn is target only';plan['limitations']+=['Same-layer prefetch has only attention computation as lead time; offline coverage cannot prove SSD readiness']
(root/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2));shutil.copy2(p,Path(__file__).with_name('collector_preattn.py'));print('preattn pilot prepared')
