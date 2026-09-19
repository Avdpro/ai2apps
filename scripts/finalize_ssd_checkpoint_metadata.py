#!/usr/bin/env python3
"""Add deployment/model-card metadata to an unpublished SSD snapshot candidate."""
import argparse,hashlib,json,shutil
from pathlib import Path

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def finalize(root, license_slug=None):
    p=root/'ssd-checkpoint.json';m=json.loads(p.read_text())
    if m.get('metadata_finalizer_sha256'):raise ValueError('metadata already finalized; do not rewrite candidate')
    upstream=root/'README.upstream.md'
    if upstream.exists():raise FileExistsError(upstream)
    if (root/'README.md').exists():shutil.copyfile(root/'README.md',upstream)
    source=m['source'];frontmatter=(f"---\nlicense: {license_slug}\nlibrary_name: mlx\n---\n\n" if license_slug else "")
    text=frontmatter+f'''# AI2Apps SSD-ready checkpoint

This is a byte-preserving storage-layout conversion of
`{source['repo_id']}` at immutable revision `{source['revision']}`.
Original tensor values and quantization are retained. Original routed experts
are externalized into the `experts/` directory rather than duplicated in the
backbone safetensors.

**Requires an AI2Apps Runtime with explicit `{m['layout']}` support.**
This candidate is not a drop-in checkpoint for unmodified Transformers,
mlx-lm or mlx-vlm. Do not use the backbone safetensors alone.
The corresponding Runtime and model Package have not yet completed release
acceptance. Full/Cached engine compatibility is recorded separately in the
Runtime release receipt; the presence of a reversible tensor map alone is
not an end-to-end engine guarantee.

- `ssd-checkpoint.json`: format, provenance and file digests.
- `external-tensors.json`: original tensor names and external byte locations.
- `source-tensor-sha256.json`: original tensor payload digests verified during export.
- `model.safetensors.index.json`: ordinary/vision/other retained tensor index.
- `experts/`: complete routed expert payloads, with no re-quantization.

See `LICENSE` and `README.upstream.md` for upstream terms and attribution.
This storage format changes installation space and data access; it is not a
new model training or a claim of improved model accuracy.
'''
    (root/'README.md').write_text(text)
    (root/'.gitattributes').write_text('*.safetensors filter=lfs diff=lfs merge=lfs -text\n*.moe filter=lfs diff=lfs merge=lfs -text\n*.bin filter=lfs diff=lfs merge=lfs -text\n')
    for name in ['README.md','README.upstream.md','.gitattributes']:
        f=root/name
        if f.is_file():m['files'][name]={'size':f.stat().st_size,'sha256':digest(f)}
    m['metadata_finalizer_sha256']=digest(Path(__file__));tmp=root/'ssd-checkpoint.json.partial';tmp.write_text(json.dumps(m,indent=2));tmp.replace(p)
    return {'path':str(root),'manifest_sha256':digest(p),'files':len(m['files']),'total_bytes':sum(f['size'] for f in m['files'].values())+p.stat().st_size}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('checkpoint',type=Path);ap.add_argument('--license');a=ap.parse_args();print(json.dumps(finalize(a.checkpoint,a.license),indent=2))
