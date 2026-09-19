"""Wait for serialized pilot parity before evaluating causal attention reuse."""
import json
import subprocess
import sys
import time
from pathlib import Path
root = Path('artifacts/dsv41-l2-attn-reuse-v5-20260916')
while not (root / 'pilot-verified.json').exists():
    status = root / 'status.json'
    if status.exists() and json.loads(status.read_text()).get('phase') == 'failed':
        raise RuntimeError('Pilot collection failed; no evaluation permitted')
    time.sleep(15)
subprocess.run([sys.executable, str(Path(__file__).with_name('evaluate_attention_reuse.py'))], check=True)
