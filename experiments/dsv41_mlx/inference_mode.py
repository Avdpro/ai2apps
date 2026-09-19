"""Select the default text executor before allocating model/output resources.

The patched backend must be loaded by a fresh process. Imported benchmark runners
keep their explicitly injected Model; only the standalone CLI uses this selector.
"""
import json,os,sys
from pathlib import Path


def select(args):
    requested=args.inference_mode
    if requested=='legacy':return {'requested':requested,'selected':'legacy','reason':'explicit'}
    if requested=='window' and args.burst_top not in (2,4):raise ValueError('native windows require --burst-top 2 or 4')
    reasons=[]
    for enabled,reason in [
        (args.image or args.messages_json,'vision/chat input'),
        (args.trace or args.layer_progress or args.collect_routes,'per-layer diagnostics'),
        (args.static_l1 or args.l1_policy!='eviction_dual','alternate L1 policy'),
        (args.l1_shape or args.main_slots!=40,'alternate L1 capacity'),
        (args.burst_tail!='zero','alternate Burst tail'),
        (args.prefill_top is not None,'Burst Prefill'),
        (args.shared_dispatch or args.fused_gate_up or args.decode_dispatch!='legacy','experimental expert dispatch'),
        (args.attention_chunk!=64,'alternate attention chunk'),
    ]:
        if enabled:reasons.append(reason)
    if reasons:
        reason=', '.join(reasons)
        if requested in ('guarded','window'):raise ValueError(f'{requested} windows are not supported for {reason}; use packet or auto')
        return {'requested':requested,'selected':'packet','reason':reason+'; preserve forward with native packet boundary'}
    if requested=='auto':
        return {
            'requested':requested,
            'selected':'packet',
            'reason':'standard L1=40/L0=8 eviction_dual engine with one native GPU-to-CPU packet per layer',
        }
    return {'requested':requested,'selected':requested,'reason':'explicit validated text Decode'}


def launch(args,argv,parser):
    try:choice=select(args)
    except ValueError as e:parser.error(str(e))
    if choice['selected']=='legacy':
        print('DS4.1F inference mode: legacy ('+choice['reason']+')',flush=True)
        return choice
    root=Path(__file__).resolve().parents[2]
    build=root/'artifacts/dsv41-miss-resume-mlx-build'
    native=root/'artifacts/dsv41-miss-resume-native-build'
    if not (build/'libmlx.dylib').is_file() or not list(native.glob('_miss_resume*.so')):
        parser.error('New Decode backend is not built. Run .venv/bin/python experiments/dsv41_analysis/miss_resume/build.py, or select --inference-mode legacy.')
    forwarded=[];i=0
    # Strip selector/Burst flags consumed here; preserve all other user arguments.
    while i<len(argv):
        key=argv[i].split('=')[0]
        if key in ('--inference-mode','--resume-block'):
            i+=1 if '=' in argv[i] else 2
        else:forwarded.append(argv[i]);i+=1
    cmd=[sys.executable,str(root/'experiments/dsv41_analysis/miss_resume/launch.py'),
         '--resume-mode',choice['selected'],'--resume-block',str(args.block_layers if args.block_layers>1 else args.resume_block)]
    cmd+=forwarded
    env=os.environ.copy();env['DSV41_DEFAULT_ENTRY']=json.dumps(choice)
    print('DS4.1F inference mode: '+choice['selected']+' ('+choice['reason']+')',flush=True)
    os.execve(sys.executable,cmd,env)
