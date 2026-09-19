"""Resumable serialized GPU experiment runner; pauses only identified own uploads."""
import argparse,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path('artifacts/dsv41-l1-shape-20260915')
DATA=ROOT/'dataset/dataset-manifest.json'

def run_sample(row,label,capacity=40,shape=None,capture=True,repeat=0,decode=None,no_cache=False,full_logits=False):
    if hashlib.sha256(Path(row['fixture']).read_bytes()).hexdigest()!=row['fixture_sha256']:raise RuntimeError('frozen fixture changed: '+row['id'])
    out=ROOT/label/(row['id']+f'-r{repeat}');out.parent.mkdir(parents=True,exist_ok=True)
    manifest=out/'manifest.json'
    if manifest.exists():
        prior=json.loads(manifest.read_text())
        if prior['status']=='complete':
            expected=json.loads(Path(shape).read_text())['capacities'] if shape else [capacity]*40
            if prior.get('main_capacities')!=expected or prior.get('decode_forwards')!=(decode or row['decode_steps']) or bool(prior.get('collect_routes'))!=capture or bool(prior.get('expert_no_cache'))!=no_cache:raise RuntimeError('run configuration changed: '+str(out))
            if full_logits and len(prior.get('trace_files',{}))!=(decode or row['decode_steps'])+1:raise RuntimeError('full logits missing: '+str(out))
            return prior
        raise RuntimeError(f'incomplete output requires explicit diagnosis: {out}')
    cmd=[sys.executable,'experiments/dsv41_mlx/run.py','--prompt-json',row['fixture'],'--output',str(out),'--decode',str(decode or row['decode_steps']),'--prefill-slots','64','--logits-mode','all' if full_logits else 'hash']
    cmd+=['--l1-shape',str(shape)] if shape else ['--main-slots',str(capacity)]
    if no_cache:cmd+=['--expert-no-cache']
    if capture:cmd+=['--collect-routes']
    with out.with_suffix('.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    result=json.loads(manifest.read_text())
    if result['status']!='complete':raise RuntimeError(str(out))
    print(json.dumps({'sample':row['id'],'label':label,'decode_tps':(len(result['step_seconds'])-1)/sum(result['step_seconds'][1:]),'peak_gb':result['sampled_physical_footprint_peak_bytes']/1e9,'total_seconds':result['total_seconds']}),flush=True)
    return result

def pause_uploads():
    paused=[]
    for p in Path('artifacts/chat-checkpoint-migration-20260914').glob('*upload.json'):
        try:
            a=json.loads(p.read_text());pid=a.get('pid')
            if a.get('status')!='uploading' or not pid:continue
            command=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
            if 'upload_ssd_checkpoint.py' not in command:continue
            os.kill(pid,signal.SIGSTOP);paused.append(pid)
        except (ValueError,ProcessLookupError):pass
    return paused

def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['pilot','calibrate','collect']);args=ap.parse_args()
    data=json.loads(DATA.read_text());samples=data['samples'];paused=pause_uploads() if args.phase!='collect' else []
    try:
        if args.phase=='pilot':
            for row in samples:
                if row['id'] in data['pilot_ids']:run_sample(row,'trace40')
        elif args.phase=='calibrate':
            from replay import verify
            results=[]
            for row in samples:
                if row['id'] not in data['calibration_ids']:continue
                refs=[]
                for cap in [40,32,48]:
                    r=run_sample(row,f'trace{cap}',capacity=cap);refs.append(r)
                    parity=verify(ROOT/f'trace{cap}'/(row['id']+'-r0'),cap)
                    results.append({'id':row['id'],'capacity':cap,**parity})
                assert all(r['generated_ids']==refs[0]['generated_ids'] and r['logits_sha256']==refs[0]['logits_sha256'] for r in refs),('numerical parity',row['id'])
                (ROOT/'calibration.json').write_text(json.dumps(results,indent=2))
        else:
            assert len(json.loads((ROOT/'calibration.json').read_text()))==60
            import numpy as np
            parity=[]
            for row in samples:
                if row['id'] not in data['calibration_ids']:continue
                arrays=[np.load(ROOT/f'trace{cap}'/(row['id']+'-r0')/'routes.npz',allow_pickle=False) for cap in [32,40,48]]
                try:
                    assert all(np.array_equal(a[k],arrays[0][k]) for a in arrays[1:] for k in ['prefill','decode']),('cross-capacity route mismatch',row['id'])
                    parity.append({'id':row['id'],'prefill_and_decode_routes_equal':True})
                finally:
                    for a in arrays:a.close()
            (ROOT/'calibration-routing.json').write_text(json.dumps(parity,indent=2))
            for row in samples:run_sample(row,'trace40')
    finally:
        for pid in paused:
            try:os.kill(pid,signal.SIGCONT)
            except ProcessLookupError:pass
if __name__=='__main__':main()
