"""Resumable per-sequence collection, with exact pilot and structural data gates."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import numpy as np

ROOT = Path(os.environ.get('L2_DATA_ROOT', 'artifacts/dsv41-l2-v2-20260916'))


def verify(out, row):
    m = json.loads((out / 'manifest.json').read_text())
    assert m['status'] == 'complete'
    if ROOT.name in ('dsv41-l2-state-v3-20260916', 'dsv41-l2-preattn-v4-20260916', 'dsv41-l2-attn-reuse-v5-20260916'):
        prior = Path('artifacts/dsv41-l2-v2-20260916/data') / row['id'] / 'manifest.json'
        if prior.exists():
            reference = json.loads(prior.read_text())
            for key in ['input_ids', 'generated_ids', 'logits_sha256', 'expert_read_bytes', 'expert_total_read_bytes']:
                assert m[key] == reference[key], ('v3 versus v2', row['id'], key)
            for key in ['per_layer_counts', 'promotions', 'bank_fence_calls']:
                assert m['adaptive_l1'][key] == reference['adaptive_l1'][key], ('v3 versus v2', row['id'], key)
    n = m['decode_forwards']
    if not n:
        return dict(id=row['id'], split=row['split'], family_id=row['family_id'],
                    rows=0, excluded='EOS at prefill; no next forward to supervise')
    with np.load(out / 'supervision.npz') as z:
        assert z['hidden'].shape == (n, 5120)
        assert z['embedding'].shape == (n, 5120)
        assert z['router_rank'].shape == (n, 40, 384)
        assert z['top6'].shape == (n, 40, 6)
        assert z['resident'].shape == (n, 40, 384)
        assert np.isfinite(z['hidden']).all() and np.isfinite(z['embedding']).all()
        assert np.isfinite(z['router_rank']).all()
        if 'previous_ffn' in z:
            assert z['previous_ffn'].shape == (n, 40, 5120)
            assert np.isfinite(z['previous_ffn']).all()
        if 'preattn' in z:
            assert z['preattn'].shape == (n, 40, 5120) and z['actual_ffn'].shape == (n, 40, 5120)
            assert np.isfinite(z['preattn']).all() and np.isfinite(z['actual_ffn']).all()
        if 'attention_reuse' in z:
            assert z['attention_reuse'].shape == (n, 40, 5120) and np.isfinite(z['attention_reuse']).all()
        if 'previous_attention' in z:
            assert z['previous_attention'].shape == (n, 40, 5120) and np.isfinite(z['previous_attention']).all()
        ids = z['top6'].astype(int)
        assert ((ids >= 0) & (ids < 384)).all() and (np.diff(ids, axis=-1) > 0).all()
        # MLX and NumPy can select different expert IDs at an exactly tied
        # boundary. Preserve actual MLX IDs; verify the selected score multiset.
        expected = np.sort(z['router_rank'], axis=-1)[..., -6:]
        actual = np.sort(np.take_along_axis(z['router_rank'], ids, axis=-1), axis=-1)
        assert np.array_equal(expected, actual), 'router rank/Top6 mismatch'
        assert np.array_equal(z['top6'][:-1], z['previous_top6'][1:]), 'one-token alignment'
        assert z['position'].tolist() == list(range(len(m['input_ids']), len(m['input_ids']) + n))
        assert np.isin(z['resident'], [0, 1, 2]).all()
        misses = (np.take_along_axis(z['resident'], z['top6'].astype(int), axis=-1) == 0).sum()
        assert int(misses) == m['cache_stats']['misses'], 'cache snapshot/miss counter mismatch'
    # Token IDs are exact runner IDs, paired with each current forward's embedding.
    (out / 'alignment.json').write_text(json.dumps(dict(token_ids=m['generated_ids'][:-1],
        input_ids=m['input_ids'], split=row['split'], family_id=row['family_id']), indent=2))
    return dict(id=row['id'], split=row['split'], family_id=row['family_id'], rows=n,
        misses=int(misses), peak_bytes=m['sampled_physical_footprint_peak_bytes'],
        sha256=hashlib.sha256((out / 'supervision.npz').read_bytes()).hexdigest())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args()
    plan = json.loads((ROOT / 'plan.json').read_text())
    for name, digest in json.loads((ROOT / 'source-hashes.json').read_text()).items():
        assert hashlib.sha256((ROOT / 'source' / name).read_bytes()).hexdigest() == digest
    rows = plan.get('pilot_samples', plan['samples'][:2]) if args.pilot else plan['samples']
    if not args.pilot: assert (ROOT / 'pilot-verified.json').exists()
    records = []
    for row in rows:
        out = ROOT / 'data' / row['id']
        out.parent.mkdir(exist_ok=True)
        if not (out / 'verified.json').exists():
            if out.exists():
                assert (out / 'manifest.json').exists(), f'Incomplete run requires inspection: {out}'
                assert json.loads((out / 'manifest.json').read_text())['status'] == 'complete'
            assert hashlib.sha256(Path(row['fixture']).read_bytes()).hexdigest() == row['fixture_sha256']
            common = ['--prompt-json', row['fixture'], '--decode', str(row['decode_steps']),
                      '--prefill-slots', '64', '--logits-mode', 'hash', '--inference-mode', 'legacy', '--stop-at-eos']
            cmd = [sys.executable, str(ROOT / 'source/experiments/dsv41_mlx/collector.py'), *common, '--output', str(out)]
            if not out.exists():
                with out.with_suffix('.log').open('w') as log:
                    subprocess.run(cmd, env=dict(os.environ, L2_COLLECT_OUTPUT=str(out)), stdout=log, stderr=subprocess.STDOUT, check=True)
            record = verify(out, row)
            if args.pilot:
                ref = ROOT / 'reference' / row['id']
                ref.parent.mkdir(exist_ok=True)
                with ref.with_suffix('.log').open('w') as log:
                    subprocess.run([sys.executable, 'experiments/dsv41_mlx/run.py', *common,
                                    '--output', str(ref)], stdout=log, stderr=subprocess.STDOUT, check=True)
                a = json.loads((out / 'manifest.json').read_text())
                b = json.loads((ref / 'manifest.json').read_text())
                for key in ['input_ids', 'generated_ids', 'logits_sha256', 'expert_read_bytes', 'expert_total_read_bytes']:
                    assert a[key] == b[key], key
                for key in ['per_layer_counts', 'promotions', 'bank_fence_calls']:
                    assert a['adaptive_l1'][key] == b['adaptive_l1'][key], key
                record['exact_reference'] = True
            (out / 'verified.json').write_text(json.dumps(record, indent=2))
        records.append(json.loads((out / 'verified.json').read_text()))
        status = dict(phase='collecting', verified_sequences=len(records),
                      rows=sum(r['rows'] for r in records), updated_at=time.time(), records=records)
        temporary = ROOT / 'status.tmp'
        temporary.write_text(json.dumps(status, indent=2)); temporary.replace(ROOT / 'status.json')
        print(json.dumps(records[-1]), flush=True)
    status['phase'] = 'pilot_verified' if args.pilot else 'collection_complete'
    (ROOT / 'status.json').write_text(json.dumps(status, indent=2))
    if args.pilot: (ROOT / 'pilot-verified.json').write_text(json.dumps(records, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        path = ROOT / 'status.json'
        status = json.loads(path.read_text()) if path.exists() else {}
        status.update(phase='failed', error=repr(error), updated_at=time.time())
        path.write_text(json.dumps(status, indent=2))
        raise
