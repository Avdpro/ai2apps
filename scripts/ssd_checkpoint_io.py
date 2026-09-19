"""Bounded raw tensor copy helpers for SSD snapshot exporters."""
import hashlib,json,os,shutil,struct,subprocess,sys
from pathlib import Path

CHUNK = 8 * 1024 * 1024

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
    _, original_header = header(source)
    if '__metadata__' in original_header: result['__metadata__'] = original_header['__metadata__']
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
            if k == '__metadata__': continue
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
