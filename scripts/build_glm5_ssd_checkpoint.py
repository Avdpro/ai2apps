#!/usr/bin/env python3
"""Verify fused-v2 GLM expert records and export a byte-preserving snapshot."""
import argparse
import json
import re
import shutil
from pathlib import Path

from ssd_checkpoint_io import CHUNK, clone, header, safe_file, sha, subset

VARIANT = 'glm5-next-affine-q4-gate-up-fused-v2'
PATTERN = re.compile(r'^model\.language_model\.layers\.(\d+)\.mlp\.experts\.(\d+)\.(gate_proj|up_proj|down_proj)\.(weight|scales|biases)$')


def build(source, store, output, repo, revision):
    import hashlib
    if output.exists():
        raise FileExistsError(output)
    config = json.loads((source / 'config.json').read_text())
    if config['model_type'] != 'glm5_next':
        raise ValueError('expected glm5_next')
    text = config['text_config']
    layers = range(text.get('first_k_dense_replace', 0), text['num_hidden_layers'])
    experts = text['n_routed_experts']
    stage = output.with_name(output.name + '.partial')
    stage.mkdir(parents=True, exist_ok=False)
    (stage / 'experts').mkdir()
    weight_map = json.loads((source / 'model.safetensors.index.json').read_text())['weight_map']
    entries = {}; headers = {}
    for name in sorted(set(weight_map.values())):
        p = safe_file(source, name)
        base, h = header(p); headers[name] = (base, h)
        for key, value in h.items():
            if key == '__metadata__':
                continue
            if weight_map.get(key) != name or key in entries:
                raise ValueError('source index mismatch')
            entries[key] = (p, base, value)
    if set(entries) != set(weight_map):
        raise ValueError('missing source tensors')
    # The checkpoint also contains MTP experts at layer num_hidden_layers.
    # Keep them in the backbone, just like the other auxiliary tensors.
    external = {key for key in entries
                if (match := PATTERN.fullmatch(key)) and int(match.group(1)) in layers}
    expected = {f'model.language_model.layers.{l}.mlp.experts.{e}.{p}.{c}'
                for l in layers for e in range(experts)
                for p in ('gate_proj', 'up_proj', 'down_proj')
                for c in ('weight', 'scales', 'biases')}
    if external != expected:
        raise ValueError('incomplete GLM expert coverage')
    locations = {}; hashes = {}; files = {}; layer_map = {}
    for layer in layers:
        name = f'layer-{layer:03d}.moe'
        p = store / name
        with p.open('rb') as f:
            n = int.from_bytes(f.read(8), 'little')
            if not 0 < n <= 4088:
                raise ValueError('bad store header')
            m = json.loads(f.read(n))
        if (m.get('variant') != VARIANT or m.get('layer') != layer
                or m.get('num_experts') != experts or m.get('data_offset') != 4096
                or p.stat().st_size != 4096 + experts * m['record_bytes']):
            raise ValueError('store geometry mismatch')
        target = stage / 'experts' / name
        clone(p, target)
        m['source'] = repo; m['source_revision'] = revision
        encoded = json.dumps(m, separators=(',', ':'), sort_keys=True).encode()
        if len(encoded) > 4088:
            raise ValueError('store header overflow')
        with target.open('r+b') as f:
            f.write(len(encoded).to_bytes(8, 'little') + encoded + bytes(4088-len(encoded)))
        tensors = {t['name']: t for t in m['tensors']}
        with target.open('rb') as packed:
            for expert in range(experts):
                for projection in ('gate_proj', 'up_proj', 'down_proj'):
                    for component in ('weight', 'scales', 'biases'):
                        key = f'model.language_model.layers.{layer}.mlp.experts.{expert}.{projection}.{component}'
                        src, base, v = entries[key]; lo, hi = v['data_offsets']; size = hi-lo
                        fused = projection != 'down_proj'
                        t = tensors[('gate_up_proj' if fused else projection) + '.' + component]
                        shape = list(v['shape']); shape[0] *= 2 if fused else 1
                        if (t['shape'] != shape or t['dtype'] != v['dtype']
                                or t['nbytes'] != size*(2 if fused else 1)
                                or t['offset'] < 0 or t['offset']+t['nbytes'] > m['record_bytes']):
                            raise ValueError('fused tensor geometry mismatch')
                        offset = 4096 + expert*m['record_bytes'] + t['offset'] + (size if projection == 'up_proj' else 0)
                        digest = hashlib.sha256(); packed.seek(offset)
                        with src.open('rb') as f:
                            f.seek(base+lo); left = size
                            while left:
                                a = f.read(min(CHUNK, left)); b = packed.read(len(a))
                                if not a or a != b:
                                    raise ValueError('expert bytes mismatch: ' + key)
                                digest.update(a); left -= len(a)
                        hashes[key] = digest.hexdigest()
                        locations[key] = dict(file='experts/'+name, offset=offset, nbytes=size,
                                              dtype=v['dtype'], shape=v['shape'])
        files['experts/'+name] = dict(size=target.stat().st_size, sha256=sha(target))
        layer_map[str(layer)] = dict(file=name, num_experts=experts, record_bytes=m['record_bytes'], file_bytes=target.stat().st_size)
        print(json.dumps({'phase': 'verified_experts', 'layer': layer}), flush=True)
    (stage/'experts/manifest.json').write_text(json.dumps(dict(format='omlx-moe-expert-major-set',version=1,variant=VARIANT,source=dict(repo_id=repo,revision=revision),layers=layer_map),indent=2))
    new_map = {}; backbone_bytes = 0
    for name, (base, h) in headers.items():
        keep = {k: v for k, v in h.items() if k != '__metadata__' and k not in external}
        if not keep:
            continue
        size, digests = subset(source/name, stage/name, keep, base)
        backbone_bytes += size; hashes.update(digests)
        new_map.update({k: name for k in keep})
    (stage/'model.safetensors.index.json').write_text(json.dumps(dict(metadata=dict(total_size=backbone_bytes),weight_map=new_map),indent=2))
    for name in ('LICENSE','README.md','config.json','generation_config.json','processor_config.json','preprocessor_config.json','tokenizer.json','tokenizer_config.json','chat_template.jinja','merges.txt','vocab.json'):
        if (source/name).is_file():
            shutil.copyfile(source/name,stage/name)
    (stage/'external-tensors.json').write_text(json.dumps(locations,sort_keys=True))
    (stage/'source-tensor-sha256.json').write_text(json.dumps(hashes,sort_keys=True))
    for p in stage.rglob('*'):
        name = p.relative_to(stage).as_posix()
        if p.is_file() and name not in files:
            files[name] = dict(size=p.stat().st_size,sha256=sha(p))
    m = dict(schema='ai2apps.ssd-checkpoint/v1',family='glm5_next',layout=VARIANT,
             source=dict(repo_id=repo,revision=revision,index_sha256=sha(source/'model.safetensors.index.json')),
             index_sha256=sha(stage/'model.safetensors.index.json'),expert_store='experts',
             tensor_count=len(entries),verification='all_tensor_payloads_equal',
             backbone_payload_bytes=backbone_bytes,files=files,builder_sha256=sha(Path(__file__)),
             io_helper_sha256=sha(Path(__file__).with_name('ssd_checkpoint_io.py')))
    (stage/'ssd-checkpoint.json').write_text(json.dumps(m,indent=2))
    stage.rename(output)
    return m


if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    for name in ('source','expert-store','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--source-repo',required=True); ap.add_argument('--source-revision',required=True)
    a=ap.parse_args()
    if not re.fullmatch('[0-9a-f]{40}',a.source_revision):
        ap.error('immutable revision required')
    build(a.source.resolve(),a.expert_store.resolve(),a.output.resolve(),a.source_repo,a.source_revision)
