#!/usr/bin/env python3
"""Build an independent DS4.1 SSD snapshot, preserving every tensor payload.

This is a data-layout exporter, not a Package/distribution signing entry point.
Output is staged and only renamed after all source/store comparisons pass.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, struct, subprocess, sys
from pathlib import Path

CHUNK = 8 * 1024 * 1024
EXPERT = re.compile(r'^layers\.(\d+)\.ffn\.experts\.(\d+)\.(w[123])\.(weight|scale)$')
PARTS = [(w, p) for w in ('w1', 'w2', 'w3') for p in ('weight', 'scale')]

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(CHUNK), b''): h.update(b)
    return h.hexdigest()

def header(path):
    with path.open('rb') as f:
        raw = f.read(8)
        if len(raw) != 8: raise ValueError(f'truncated header: {path}')
        n = struct.unpack('<Q', raw)[0]
        if n > 128 * 1024 * 1024: raise ValueError('oversize header')
        h = json.loads(f.read(n))
    for key, v in h.items():
        if key == '__metadata__': continue
        lo, hi = v['data_offsets']
        if not 0 <= lo <= hi <= path.stat().st_size - 8 - n: raise ValueError(f'bad range: {key}')
    return 8 + n, h

def safe_file(root, name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts: raise ValueError(f'unsafe file name: {name}')
    # HF symlink blobs are allowed as inputs, never copied as links to outputs.
    return root / p

def copy_range(src, dst, offset, length):
    src.seek(offset)
    h = hashlib.sha256()
    while length:
        b = src.read(min(CHUNK, length))
        if not b: raise EOFError('truncated tensor')
        dst.write(b); h.update(b); length -= len(b)
    return h.hexdigest()

def subset(source, target, selected, offset):
    result = {}; cursor = 0
    for k, v in selected.items():
        size = v['data_offsets'][1] - v['data_offsets'][0]
        result[k] = dict(dtype=v['dtype'], shape=v['shape'], data_offsets=[cursor, cursor + size]); cursor += size
    raw = json.dumps(result, separators=(',', ':')).encode(); raw += b' ' * (-len(raw) % 8)
    digests = {}
    with source.open('rb') as src, target.open('xb') as dst:
        dst.write(struct.pack('<Q', len(raw))); dst.write(raw)
        for k, v in selected.items():
            lo, hi = v['data_offsets']; digests[k] = copy_range(src, dst, offset + lo, hi - lo)
        dst.flush(); os.fsync(dst.fileno())
    # Independently reread produced tensor bytes, not merely the write buffer.
    base, check = header(target)
    with target.open('rb') as f:
        for k, v in check.items():
            lo, hi = v['data_offsets']; f.seek(base + lo); h = hashlib.sha256(); left = hi - lo
            while left:
                b = f.read(min(CHUNK, left))
                if not b: raise EOFError('truncated output')
                h.update(b); left -= len(b)
            if h.hexdigest() != digests[k]: raise ValueError(f'output digest mismatch: {k}')
    return cursor, digests

def clone(source, target):
    # APFS copy-on-write is independent of the source; never hard-link model bytes.
    if sys.platform == 'darwin':
        r = subprocess.run(['/bin/cp', '-c', str(source), str(target)], capture_output=True)
        if r.returncode == 0: return
        target.unlink(missing_ok=True)
    shutil.copyfile(source, target)

def build(source, store, output, repo, revision, layers=40, experts=384):
    if output.exists(): raise FileExistsError(output)
    stage = output.with_name(output.name + '.partial')
    stage.mkdir(parents=True, exist_ok=False)
    index_path = source / 'model.safetensors.index.json'; original_hash = sha(index_path)
    index = json.loads(index_path.read_text()); weight_map = index['weight_map']; entries = {}; headers = {}
    try:
        for name in sorted(set(weight_map.values())):
            p = safe_file(source, name); base, h = header(p); headers[name] = (base, h)
            for k, v in h.items():
                if k == '__metadata__': continue
                if weight_map.get(k) != name: raise ValueError(f'index mismatch: {k}')
                if k in entries: raise ValueError(f'duplicate tensor: {k}')
                entries[k] = (p, base, v)
        if set(entries) != set(weight_map): raise ValueError('incomplete index')
        external = {k for k in entries if (m := EXPERT.fullmatch(k)) and int(m[1]) < layers}
        expected = {f'layers.{l}.ffn.experts.{e}.{w}.{part}' for l in range(layers) for e in range(experts) for w, part in PARTS}
        if external != expected: raise ValueError('incomplete or extra routed tensors')
        (stage / 'experts').mkdir(); tensor_hashes = {}; locations = {}; files = {}; total_external = 0
        for l in range(layers):
            p = store / f'layer-{l}.bin'; meta_path = Path(str(p) + '.json'); m = json.loads(meta_path.read_text())
            records = {int(k): int(v) for k, v in m['expert_to_record'].items()}
            if (m.get('checkpoint_index_sha256') != original_hash or set(records) != set(range(experts))
                    or set(records.values()) != set(range(experts)) or m.get('layer') != l
                    or p.stat().st_size != experts * m['record_bytes']): raise ValueError('store identity/coverage mismatch')
            # Copy then validate the actual export bytes against every original tensor.
            target = stage / 'experts' / p.name; clone(p, target)
            with target.open('rb') as packed:
                handles = {}
                try:
                    for e in range(experts):
                        cursor = records[e] * m['record_bytes']
                        for part_idx, (w, part) in enumerate(PARTS):
                            k = f'layers.{l}.ffn.experts.{e}.{w}.{part}'; src, base, v = entries[k]; lo, hi = v['data_offsets']
                            if v['shape'] != m['shapes'][part_idx]: raise ValueError(f'shape mismatch: {k}')
                            if src not in handles: handles[src] = src.open('rb')
                            f = handles[src]
                            locations[k] = {'file': 'experts/' + p.name, 'offset': cursor, 'nbytes': hi - lo, 'dtype': v['dtype'], 'shape': v['shape']}
                            f.seek(base + lo); packed.seek(cursor); left = hi - lo; h = hashlib.sha256()
                            while left:
                                a = f.read(min(CHUNK, left)); b = packed.read(len(a))
                                if not a or a != b: raise ValueError(f'expert payload mismatch: {k}')
                                h.update(a); left -= len(a)
                            tensor_hashes[k] = h.hexdigest(); cursor += hi - lo
                        if cursor != (records[e] + 1) * m['record_bytes']: raise ValueError('record layout mismatch')
                finally:
                    for f in handles.values(): f.close()
            digest = sha(target)
            if digest != m['sha256']: raise ValueError('store digest mismatch')
            files['experts/' + p.name] = {'size': target.stat().st_size, 'sha256': digest}
            shutil.copyfile(meta_path, stage / 'experts' / meta_path.name)
            total_external += target.stat().st_size
            print(json.dumps({'phase': 'verified_experts', 'layer': l, 'bytes': target.stat().st_size}), flush=True)
        shutil.copyfile(store / 'manifest.json', stage / 'experts' / 'manifest.json')
        new_map = {}; backbone_bytes = 0
        for name, (base, h) in headers.items():
            selected = {k: v for k, v in h.items() if k != '__metadata__' and k not in external}
            if not selected: continue
            target = safe_file(stage, name); target.parent.mkdir(parents=True, exist_ok=True)
            size, hashes = subset(safe_file(source, name), target, selected, base)
            tensor_hashes.update(hashes); backbone_bytes += size; new_map.update({k: name for k in selected})
            print(json.dumps({'phase': 'verified_backbone', 'shard': name, 'bytes': size}), flush=True)
        (stage / 'model.safetensors.index.json').write_text(json.dumps({'metadata': {'total_size': backbone_bytes}, 'weight_map': new_map}, indent=2))
        # Preserve upstream metadata, preprocessing/encoding sources and attribution.
        for name in ['config.json', 'configuration.json', 'tokenizer.json', 'tokenizer_config.json', 'generation_config.json', 'preprocessor_config.json', 'LICENSE', 'README.md', 'assets', 'DeepSeek_V41_Tech_Report.pdf', 'encoding', 'inference']:
            p = source / name
            if p.is_dir(): shutil.copytree(p, stage / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            elif p.is_file(): shutil.copyfile(p, stage / name)
        (stage / 'external-tensors.json').write_text(json.dumps(locations, sort_keys=True))
        (stage / 'source-tensor-sha256.json').write_text(json.dumps(tensor_hashes, sort_keys=True))
        for p in sorted(stage.rglob('*')):
            if p.is_file() and p.relative_to(stage).as_posix() not in files: files[p.relative_to(stage).as_posix()] = {'size': p.stat().st_size, 'sha256': sha(p)}
        manifest = {'schema': 'ai2apps.ssd-checkpoint/v1', 'family': 'deepseek_v41', 'layout': 'dsv41-original-fp4-six-segment-v1',
                    'source': {'repo_id': repo, 'revision': revision, 'index_sha256': original_hash},
                    'index_sha256': sha(stage / 'model.safetensors.index.json'), 'expert_store': 'experts',
                    'layers': layers, 'experts_per_layer': experts, 'tensor_count': len(entries),
                    'backbone_payload_bytes': backbone_bytes, 'expert_payload_bytes': total_external,
                    'verification': 'all_tensor_payloads_equal', 'files': files,
                    'builder_sha256': sha(Path(__file__))}
        (stage / 'ssd-checkpoint.json').write_text(json.dumps(manifest, indent=2))
        stage.rename(output)
        return manifest
    except Exception:
        # Keep explicit incomplete stage for diagnosis; never publish it as complete.
        raise

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--source', type=Path, required=True); ap.add_argument('--expert-store', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True); ap.add_argument('--source-repo', required=True); ap.add_argument('--source-revision', required=True)
    a = ap.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', a.source_revision): ap.error('source revision must be immutable 40-hex commit')
    m = build(a.source.resolve(), a.expert_store.resolve(), a.output.resolve(), a.source_repo, a.source_revision)
    print(json.dumps({k: v for k, v in m.items() if k != 'files'}, indent=2))
if __name__ == '__main__': main()
