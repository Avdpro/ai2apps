#!/usr/bin/env python3
"""Resume official Hub SDK uploads of a frozen SSD checkpoint candidate.

Only candidate manifest files are eligible. SDK caches and partial files are
never uploaded. A complete upload still requires remote digest verification
and signed distribution publication before any model Package points at it.
"""
import argparse,hashlib,json,os,time
from pathlib import Path

def write(path, data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2));tmp.replace(path)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--hub',choices=['hf','ms'],required=True);ap.add_argument('--repo',required=True);ap.add_argument('--checkpoint',type=Path,required=True);ap.add_argument('--state',type=Path,required=True);ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    expected_owner='Avdpro' if a.hub=='hf' else 'ai2apps'
    if a.repo.split('/')[0]!=expected_owner:raise ValueError('repository namespace differs from confirmed release context')
    root=a.checkpoint.resolve();marker=root/'ssd-checkpoint.json';m=json.loads(marker.read_text());digest=hashlib.sha256(marker.read_bytes()).hexdigest()
    if m.get('verification')!='all_tensor_payloads_equal':raise ValueError('candidate lacks full payload validation')
    allowed=sorted(m['files'])+['ssd-checkpoint.json'];total=marker.stat().st_size
    for name,v in m['files'].items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts:raise ValueError('unsafe candidate path')
        f=root/p;f.resolve().relative_to(root)
        if not f.is_file() or f.stat().st_size!=v['size']:raise ValueError('candidate size mismatch: '+name)
        if f.stat().st_size<16*1024*1024 and hashlib.sha256(f.read_bytes()).hexdigest()!=v['sha256']:raise ValueError('candidate metadata mismatch: '+name)
        total+=f.stat().st_size
    if a.state.exists():
        old=json.loads(a.state.read_text())
        if old['repo']!=a.repo or old['manifest_sha256']!=digest or old['hub']!=a.hub:raise ValueError('resume identity mismatch')
        if old.get('status')=='uploaded':raise ValueError('upload already completed; perform remote verification')
    s={'hub':a.hub,'repo':a.repo,'checkpoint':str(root),'manifest_sha256':digest,'files':len(allowed),'bytes':total,'pid':os.getpid(),'started':time.time(),'status':'uploading'}
    a.state.parent.mkdir(parents=True,exist_ok=True);write(a.state,s);print(json.dumps(s),flush=True)
    try:
        if a.hub=='hf':
            from huggingface_hub import HfApi
            api=HfApi();api.upload_large_folder(a.repo,root,repo_type='model',allow_patterns=allowed,num_workers=a.workers,print_report=True,print_report_every=30)
            s['revision']=api.model_info(a.repo).sha
        else:
            from modelscope_hub import HubApi
            api=HubApi();api.upload_folder(a.repo,repo_type='model',folder_path=root,allow_patterns=allowed,max_workers=a.workers,use_cache=True,sync_remote_repo=False,commit_message='Upload verified byte-preserving SSD checkpoint candidate')
            # Resolve immutable commit separately after the SDK reports completion.
        s.update(status='uploaded',finished=time.time());write(a.state,s);print(json.dumps(s),flush=True)
    except Exception as e:
        s.update(status='failed',error_type=type(e).__name__,finished=time.time());write(a.state,s)
        print(json.dumps({'status':'failed','error_type':type(e).__name__}),flush=True)
        raise SystemExit(1)
if __name__=='__main__':main()
