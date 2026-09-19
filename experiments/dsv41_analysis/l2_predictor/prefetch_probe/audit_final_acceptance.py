"""Audit a completed frozen evaluation; never select or modify its candidate."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def read(path):
    return json.loads(path.read_text())


def audit(root):
    assert read(root / 'status.json')['phase'] == 'complete'
    report = read(root / 'report.json')
    receipt = read(root / 'frozen-candidate.json')
    plan = read(root / 'evaluation-plan.json')
    for name, sha in receipt['source_hashes'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == sha, name
    for name, sha in receipt['base_source_hashes'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == sha, name
    rows = plan['samples']
    assert len(rows) == 24 and len({r['family_id'] for r in rows}) == 12
    assert set(report['cases']) == {r['id'] for r in rows}
    training = read(Path('artifacts/dsv41-l2-state-v3-20260916/plan.json'))
    assert not {r['family_id'] for r in rows} & {r['family_id'] for r in training['samples']}
    timed_tokens = {'baseline': 0, 'candidate': 0}
    timed_seconds = {'baseline': 0.0, 'candidate': 0.0}
    families = {}
    peak = 0
    for row in rows:
        assert hashlib.sha256(Path(row['fixture']).read_bytes()).hexdigest() == row['fixture_sha256']
        case = root / row['id']
        results = read(case / 'report.json')
        assert results['exact_primary_parity'] and results['test_opened']
        baseline = read(case / 'baseline/manifest.json')
        candidate = read(case / 'candidate/manifest.json')
        for key in ('input_ids', 'generated_ids', 'logits_sha256', 'cache_stats'):
            assert baseline[key] == candidate[key], (row['id'], key)
        for variant, manifest in (('baseline', baseline), ('candidate', candidate)):
            assert manifest['status'] == 'complete' and manifest['expert_no_cache']
            assert manifest['main_slots'] == 40 and manifest['hot_slots'] == 8
            assert manifest['l1_policy'] == 'eviction_dual' and manifest['burst_top'] is None
            assert manifest['stop_at_eos'] and manifest['memory_budget_bytes'] == 65_000_000_000
            peak = max(peak, manifest['sampled_physical_footprint_peak_bytes'])
            times = read(case / variant / 'timing.json')['step_seconds'][5:]
            timed_tokens[variant] += len(times)
            timed_seconds[variant] += sum(times)
        f = read(case / 'candidate/prefetch.json')
        with np.load(case / 'baseline/routing.npz') as b, np.load(case / 'candidate/routing.npz') as c:
            assert np.array_equal(b['actual'], c['actual'])
            assert np.array_equal(b['resident'], c['resident'])
            actual = c['actual'].astype(int)
            assert actual.shape[1:] == (40, 6)
            actual_misses = int((~np.take_along_axis(c['resident'], actual, axis=-1)).sum())
            predicted_first = np.argsort(c['predictions'][:, 0], axis=-1)[:, -6:]
            assert np.array_equal(np.sort(predicted_first, axis=-1), np.sort(actual[:, 0], axis=-1))
        assert len(f['tokens']) == len(f['credit_rows']) == len(actual)
        assert sum(x['requested'] for x in f['records']) == actual_misses
        assert sum(x['timely'] + x['late'] + x['foreground'] for x in f['records']) == actual_misses
        assert all(t['completed_reads'] <= 64 and t['reserved_reads'] <= 64 for t in f['tokens'])
        assert all(t['candidate_route_boundaries'] <= t['baseline_route_boundaries'] for t in f['credit_rows'])
        metrics = results['results']['candidate']
        assert metrics['staging_slots_total'] == 320
        total = families.setdefault(row['family_id'], np.zeros(2, dtype=np.int64))
        total += [metrics['timely'], metrics['base_misses']]
    assert peak <= 65_000_000_000
    pairs = np.array(list(families.values()))
    total = pairs.sum(axis=0)
    assert list(total) == [report['totals']['timely'], report['totals']['base_misses']]
    rng = np.random.default_rng(20260916)
    resamples = pairs[rng.integers(0, len(pairs), size=(10000, len(pairs)))].sum(axis=1)
    interval = np.quantile(resamples[:, 0] / resamples[:, 1], [.025, .975])
    tps = {v: timed_tokens[v] / timed_seconds[v] for v in timed_tokens}
    return dict(
        audit_passed=True, candidate=receipt['candidate'], cases=len(rows), families=len(families),
        timely_coverage=float(total[0] / total[1]),
        family_bootstrap_95_percent_interval=interval.tolist(),
        uncertainty_note='Descriptive family-cluster bootstrap, not an additional acceptance threshold.',
        pooled_end_to_end_after4_tps=tps, timed_tokens=timed_tokens,
        relative_tps_change=tps['candidate'] / tps['baseline'] - 1,
        peak_decimal_GB=peak / 1e9, totals=report['totals'],
        scope='24 authored bilingual conversation histories; exact paired main inference; counted route readbacks and notifications audited, not a hardware-wide GPU event trace.',
        goal_complete=False,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root)
    (args.root / 'audit.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
