"""Freeze v3 collection with causal previous-layer FFN inputs; no future features."""
import importlib.util,json,hashlib,shutil
from pathlib import Path
spec=importlib.util.spec_from_file_location('prepare',Path(__file__).with_name('prepare.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
root=Path('artifacts/dsv41-l2-state-v3-20260916');module.ROOT=root;module.main()
model=root/'source/experiments/dsv41_mlx/model.py'
module.replace_once(model,"        scores=(flat.astype(mx.float32)@self.w(p+'.weight',mx.float32).T)/c.gate_temp", "        self.emit(f'layers.{l}.l2_ffn',flat[-1])\n        scores=(flat.astype(mx.float32)@self.w(p+'.weight',mx.float32).T)/c.gate_temp")
collector=root/'source/experiments/dsv41_mlx/collector.py'
s=collector.read_text().replace('        self.previous = None','        self.previous = None\n        self.previous_ffn = None')
s=s.replace("        if name.endswith('.l2_rank'):","        if name.endswith('.l2_ffn'):\n            self.pending[('ffn', int(name.split('.')[1]))] = value.astype(mx.float32)\n        elif name.endswith('.l2_rank'):")
s=s.replace('        self.export_arrays = [self.hidden, self.embedding]',"        self.export_arrays = [self.hidden, self.embedding]\n        self.export_arrays += [self.pending[('ffn', l)] for l in range(40)]")
s=s.replace('        if self.start:\n            rank =',"        current_ffn = np.stack([np.array(self.pending[('ffn', l)]) for l in range(40)])\n        if self.start:\n            rank =")
s=s.replace('self.rows.append(dict(hidden=self.previous, embedding=embedding,','self.rows.append(dict(previous_ffn=self.previous_ffn, hidden=self.previous, embedding=embedding,')
s=s.replace('        self.previous = hidden','        self.previous_ffn = current_ffn\n        self.previous = hidden');collector.write_text(s)
(root/'source-hashes.json').write_text(json.dumps({str(p.relative_to(root/'source')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'source').rglob('*.py')},indent=2))
plan=json.loads((root/'plan.json').read_text());plan['schema']='dsv41.l2-supervision/v3';plan['extra_feature']='previous forward normalized FFN input per layer [40,5120], causal before next token forward';plan['pilot_samples']=[next(r for r in plan['samples'] if r['split']=='train'),next(r for r in plan['samples'] if r['split']=='validation')];plan['samples']=[r for r in plan['samples'] if r['split']!='test'];plan['maximum_rows']=sum(r['decode_steps'] for r in plan['samples']);plan['split_counts']={s:sum(r['split']==s for r in plan['samples']) for s in ['train','validation']};plan['test_policy']='No historical test recollection; new families reserved for later frozen-candidate acceptance';(root/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
shutil.copy2(collector,Path(__file__).with_name('collector_state.py'))
print('v3 ready',plan['maximum_rows'],plan['split_counts'])
