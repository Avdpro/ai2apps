"""Read-only final artifact audit; no fitting or performance retuning."""
import hashlib
import json
import math
from pathlib import Path

from batch import DATA, ROOT


def main():
    data = json.loads(DATA.read_text())
    frozen = ROOT / 'candidate/frozen.json'
    shape = json.loads(frozen.read_text())
    selection = json.loads((ROOT / 'candidate/selection.json').read_text())
    assert hashlib.sha256(frozen.read_bytes()).hexdigest() == selection['frozen_sha256']
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == shape['dataset_manifest_sha256']
    assert len(shape['capacities']) == 40 and sum(shape['capacities']) == 1600
    captures = []
    early_eos = []
    for row in data['samples']:
        path = ROOT / 'trace40' / (row['id'] + '-r0') / 'manifest.json'
        record = json.loads(path.read_text())
        assert record['status'] == 'complete', str(path)
        assert len(record['step_seconds']) == row['decode_steps'] + 1, str(path)
        captures.append(record)
        if 1 in record['generated_ids'][:-1]:
            early_eos.append({'id': row['id'], 'split': row['split'], 'position': record['generated_ids'].index(1)})
    runs = 0
    peaks = []
    for row in (r for r in data['samples'] if r['split'] == 'test'):
        variants = {}
        for variant, expected in [('main40', [40] * 40), ('shape', shape['capacities'])]:
            paths = sorted((ROOT / ('test-' + variant)).glob(row['id'] + '-r*/manifest.json'))
            assert len(paths) in (2, 4), (row['id'], len(paths))
            variants[variant] = []
            for path in paths:
                record = json.loads(path.read_text())
                assert record['status'] == 'complete', str(path)
                assert record['main_capacities'] == expected, str(path)
                assert not record['collect_routes'], str(path)
                assert record['sampled_physical_footprint_peak_bytes'] <= 65_000_000_000, str(path)
                assert len(record['logits_sha256']) == row['decode_steps'] + 1, str(path)
                variants[variant].append(record)
                peaks.append(record['sampled_physical_footprint_peak_bytes'])
                runs += 1
        assert len(variants['main40']) == len(variants['shape']), row['id']
        baseline = variants['main40'][0]
        for record in variants['main40'] + variants['shape']:
            for key in ['input_ids', 'generated_ids', 'logits_sha256']:
                assert record[key] == baseline[key], (row['id'], key)
    results = json.loads((ROOT / 'results.json').read_text())
    for metrics in results['macro_metrics'].values():
        assert all(math.isfinite(v) for v in metrics.values())
    receipt = {'status': 'passed', 'route_captures': len(captures), 'heldout_runs_including_retests': runs,
               'heldout_peak_bytes_both_variants': max(peaks), 'early_eos_captures': early_eos,
               'candidate_sha256': selection['frozen_sha256'],
               'note': 'Early EOS is reported separately; fixed-step generation does not stop at EOS.'}
    (ROOT / 'final-audit.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
