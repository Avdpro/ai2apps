"""Strict, checkpoint-bound fixed per-layer capacities (opt-in)."""
import hashlib
import json
from pathlib import Path

SCHEMA = 'dsv41.l1-shape/v1'
POLICY = 'dynamic-16-4-decay0.5-hysteresis2-v1'

def validate_shape(data, checkpoint_index_sha256, layers=40, checkpoint_manifest_sha256=None):
    growth = data.get('schema') == 'dsv41.l1-shape/growth-v1'
    if data.get('schema') not in (SCHEMA, 'dsv41.l1-shape/growth-v1') or data.get('family') != 'deepseek_v41':
        raise ValueError('unsupported L1 shape schema/family')
    if data.get('checkpoint_index_sha256') != checkpoint_index_sha256:
        raise ValueError('L1 shape checkpoint mismatch')
    if checkpoint_manifest_sha256 is not None and data.get('checkpoint_manifest_sha256') != checkpoint_manifest_sha256:
        raise ValueError('L1 shape SSD manifest mismatch')
    caps = data.get('capacities')
    if not isinstance(caps, list) or len(caps) != layers:
        raise ValueError('L1 shape requires exactly 40 capacities')
    if any(type(c) is not int or c not in (32,36,40,44,48) for c in caps):
        raise ValueError('L1 capacities must be integers in 32/36/40/44/48')
    if growth and (any(c not in (40,48) for c in caps) or caps.count(48)!=8):
        raise ValueError('growth shape requires baseline40 and exactly eight layers at48')
    if sum(caps) != (1664 if growth else 1600) or data.get('hot_slots') != 8 or data.get('policy') != POLICY:
        raise ValueError('L1 shape budget/Hot/policy mismatch')
    return tuple(caps)

def load_shape(path, checkpoint):
    digest = hashlib.sha256((Path(checkpoint)/'model.safetensors.index.json').read_bytes()).hexdigest()
    data = json.loads(Path(path).read_text())
    marker_digest=hashlib.sha256((Path(checkpoint)/'ssd-checkpoint.json').read_bytes()).hexdigest()
    return validate_shape(data, digest, checkpoint_manifest_sha256=marker_digest), data
