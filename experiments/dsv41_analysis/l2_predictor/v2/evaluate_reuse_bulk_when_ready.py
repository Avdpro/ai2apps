"""Evaluate completed v5 cohort without using held-out test conversations."""
import json,subprocess,sys,time
from pathlib import Path
root=Path('artifacts/dsv41-l2-attn-reuse-v5-20260916');here=Path(__file__).parent
while not (root/'bulk-complete.json').exists():
 state=root/'serial-bulk-state.json'
 if state.exists() and json.loads(state.read_text())['phase']=='original_collector_resumed':raise RuntimeError('bulk collector ended without completion')
 time.sleep(15)
for scale in [0.,1.]:
 out=root/f'priority-full-mean{scale}'
 subprocess.run([sys.executable,str(here/'evaluate_early_budget.py'),'--root',str(root),'--feature','attention_reuse','--mean-scale',str(scale),'--output',str(out),'--export-proposals'],check=True)
 subprocess.run([sys.executable,str(here/'evaluate_priority.py'),'--cohort',str(out)],check=True)
