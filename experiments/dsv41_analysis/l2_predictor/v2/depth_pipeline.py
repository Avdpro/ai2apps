"""Serial depth ablation; one GPU training process at a time."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path('artifacts/dsv41-l2-depth-v1-20260916')
root.mkdir(exist_ok=False)
source = Path(__file__).with_name('train_depth.py')
for name in ('train_depth.py', 'train_state.py'):
    (root / name).write_bytes(source.with_name(name).read_bytes())
(root / 'plan.json').write_text(json.dumps(dict(blocks=[0, 1, 3], seeds=[17, 29],
    epochs=15, selection='validation cap64; cap48 secondary',
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), test_opened=False), indent=2))
results = {}
try:
    for seed in (17, 29):
        for blocks in (0, 1, 3):
            name = f'blocks{blocks}-seed{seed}'
            (root / 'status.json').write_text(json.dumps(dict(pid=os.getpid(), phase='running', case=name, time=time.time())))
            with (root / f'{name}.log').open('w') as log:
                subprocess.run([sys.executable, str(root / 'train_depth.py'), '--output', str(root / name),
                                '--seed', str(seed), '--blocks', str(blocks)], check=True, stdout=log, stderr=subprocess.STDOUT)
            results[name] = json.loads((root / name / 'result.json').read_text())
    (root / 'report.json').write_text(json.dumps(results, indent=2))
    (root / 'status.json').write_text(json.dumps(dict(phase='complete', time=time.time())))
except BaseException as error:
    (root / 'status.json').write_text(json.dumps(dict(phase='failed', error=str(error), time=time.time())))
    raise
