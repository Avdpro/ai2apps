"""Create an immutable source snapshot and family-isolated ~20k-row plan."""
import hashlib
import json
import shutil
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path('artifacts/dsv41-l2-v2-20260916')


def replace_once(path, before, after):
    text = path.read_text()
    assert text.count(before) == 1, (path, before)
    path.write_text(text.replace(before, after))


def main():
    ROOT.mkdir(exist_ok=False)
    source = ROOT / 'source'
    for name in ['dsv41_mlx', 'dsv41_reference']:
        shutil.copytree(Path('experiments') / name, source / 'experiments' / name,
                        ignore=shutil.ignore_patterns('__pycache__'))
    (source / 'artifacts').symlink_to(Path('artifacts').resolve(), target_is_directory=True)
    model = source / 'experiments/dsv41_mlx/model.py'
    replace_once(model, '        ids=mx.argsort(scores+bias,axis=-1)',
        "        router_rank=scores+bias\n        self.emit(f'layers.{l}.l2_rank',router_rank)\n        ids=mx.argsort(router_rank,axis=-1)")
    replace_once(model, "        h=self.s.embedding('embed',ids)",
        "        h=self.s.embedding('embed',ids)\n        self.emit('l2_embedding',h)")
    replace_once(model, '        logits=h[:,-1].astype(mx.float32)',
        "        self.emit('l2_final',h[:,-1])\n        logits=h[:,-1].astype(mx.float32)")
    runner = source / 'experiments/dsv41_mlx/run.py'
    replace_once(runner, 'mx.eval(logits,model.cache_counters,*model.ages.values())',
        'mx.eval(logits,model.cache_counters,*model.ages.values(),*model.collection_roots())')
    replace_once(runner, "            if args.logits_mode=='all':", "            model.collection_complete()\n            if args.logits_mode=='all':")
    shutil.copy2(Path(__file__).with_name('collector.py'), runner.with_name('collector.py'))
    (ROOT / 'source-hashes.json').write_text(json.dumps({str(p.relative_to(source)):
        hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*.py')}, indent=2))
    dataset = json.loads(Path('artifacts/dsv41-l1-shape-20260915/dataset/dataset-manifest.json').read_text())
    groups = defaultdict(lambda: defaultdict(list))
    for row in dataset['samples']:
        groups[(row['split'], row['scope'], row['language'])][row['kind']].append(row)
    selected = []
    # Round-robin strata instead of selecting the first 20k rows from a sorted file.
    for split, budget in [('train', 12000), ('validation', 4000), ('test', 4000)]:
        used = 0; wave = 0
        while used < budget:
            added = False
            for key in sorted(k for k in groups if k[0] == split):
                kinds = groups[key]; available = [k for k in kinds if kinds[k]]
                if not available: continue
                kind = 'scope' if wave == 0 else ('long' if wave % 2 else 'scope')
                if kind not in available:
                    kind = next((k for k in available if k != 'scope'), available[0]) if wave % 2 else available[0]
                row = kinds[kind].pop(0)
                selected.append(row); used += row['decode_steps']; added = True
                if wave > 0 and used >= budget: break
            if not added: break
            wave += 1
    families = defaultdict(set)
    for row in selected: families[row['family_id']].add(row['split'])
    assert all(len(s) == 1 for s in families.values()), 'family split leakage'
    plan = dict(schema='dsv41.l2-supervision/v2', samples=selected,
        maximum_rows=sum(r['decode_steps'] for r in selected),
        split_counts=dict(Counter(r['split'] for r in selected)),
        alignment='previous post-final-norm hidden + current input token embedding -> current 40-layer Top6',
        sampling='greedy, stop at EOS; rows may be fewer than planned maximum',
        executor='frozen legacy exact Top6; not a speed benchmark',
        limitations=dataset['limitations'])
    (ROOT / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    print(json.dumps({k:v for k,v in plan.items() if k != 'samples'}, ensure_ascii=False))


if __name__ == '__main__': main()
