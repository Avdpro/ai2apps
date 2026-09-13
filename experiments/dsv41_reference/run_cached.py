#!/usr/bin/env python3
"""Run unchanged reference harness with bounded SSD storage caches."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import run_reference
from cached_store import CachedStore


def main():
    p=argparse.ArgumentParser(add_help=False)
    p.add_argument('--experts-per-layer',type=int,default=8)
    p.add_argument('--dense-cache-mib',type=int,default=2048)
    p.add_argument('--row-cache-mib',type=int,default=8)
    options,remaining=p.parse_known_args()
    if min(vars(options).values())<0: p.error('cache budgets must be nonnegative')
    output=Path(remaining[remaining.index('--output')+1])
    instance=[]
    def factory(root):
        store=CachedStore(root,options.experts_per_layer,options.dense_cache_mib*2**20,options.row_cache_mib*2**20)
        instance.append(store); return store
    run_reference.Store=factory
    sys.argv=[sys.argv[0],*remaining]
    try: run_reference.main()
    finally:
        manifest=output/'manifest.json'
        if manifest.exists() and instance:
            data=json.loads(manifest.read_text())
            data['storage_optimization']={'kind':'per-layer-complete-expert-LRU+dense-admission+row-LRU',
                'statistics':instance[0].summary(),'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [Path(__file__),Path(__file__).with_name('cached_store.py')]}}
            manifest.write_text(json.dumps(data,indent=2,ensure_ascii=False))
            print(json.dumps(data['storage_optimization']),flush=True)

if __name__=='__main__': main()
