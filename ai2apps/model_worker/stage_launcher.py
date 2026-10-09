"""Isolated subprocess entry for Runtime-declared model stages (invoke with -I)."""
from __future__ import annotations
import argparse
from pathlib import Path
import runpy
import sys


def main():
    if not sys.flags.isolated:
        raise RuntimeError('Runtime stage launcher requires isolated Python (-I)')
    root=Path(__file__).resolve().parents[3]
    app=root/'app'
    sys.path.insert(0,str(app))
    from ai2apps.model_worker.runtime_profiles import (
        framework_profile_for_stage, framework_stage_entrypoint,
    )
    parser=argparse.ArgumentParser()
    parser.add_argument('--service-id',required=True)
    parser.add_argument('--stage',required=True)
    parser.add_argument('--job',required=True)
    parser.add_argument('--result',required=True)
    args=parser.parse_args()
    profile=framework_profile_for_stage(root,args.service_id,args.stage)
    entry=framework_stage_entrypoint(root,args.service_id,args.stage)
    # Both paths come from signed Runtime metadata, never job contents.
    core=root/'Python/lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'
    core=core.resolve(strict=True)
    if not core.is_relative_to(root) or not core.is_dir():
        raise RuntimeError('Runtime core framework layer is missing or escapes Runtime')
    sys.path[1:1]=[str(profile),str(core)]
    sys.argv=[str(entry),'--job',args.job,'--result',args.result]
    runpy.run_path(str(entry),run_name='__main__')


if __name__=='__main__':
    main()
