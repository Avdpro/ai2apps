"""One-time byte-preserving expert-major layout for arbitrary DS4.1 text routes."""
import argparse,hashlib,json,os,shutil,time
from pathlib import Path
from run_reference import Store

def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,default=Path('artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()

    if a.output.resolve()==(a.checkpoint/'experts').resolve():raise ValueError('Refusing to overwrite checkpoint experts; choose a separate output directory')
    a.output.mkdir(parents=True,exist_ok=True);source=Store(a.checkpoint)
    source_hash=source.source_index_sha256
    started=time.time();completed=[]
    for layer in range(40):
        path=a.output/f'layer-{layer}.bin';meta=Path(str(path)+'.json')
        if path.exists() and meta.exists():
            old=json.loads(meta.read_text())
            if old.get('checkpoint_index_sha256')!=source_hash or path.stat().st_size!=384*old['record_bytes']:raise ValueError('existing layer identity/size mismatch')
            completed.append(layer);continue
        if path.exists() or meta.exists():raise ValueError('incomplete published layer; inspect before resuming')
        if shutil.disk_usage(a.output).free<7*2**30:raise OSError('insufficient disk space for next layer')
        partial=Path(str(path)+'.partial');digest=hashlib.sha256();shapes=[];record_bytes=None;total=0
        with partial.open('wb') as f:
            for expert in range(384):
                size=0
                for idx,(projection,part) in enumerate((w,s) for w in ('w1','w2','w3') for s in ('weight','scale')):
                    name=f'layers.{layer}.ffn.experts.{expert}.{projection}.{part}'
                    fd,base,entry=source.entries[name];lo,hi=entry['data_offsets']
                    if entry['dtype']!=('I8' if part=='weight' else 'F8_E8M0'):raise ValueError(name)
                    if expert==0:shapes.append(entry['shape'])
                    elif shapes[idx]!=entry['shape']:raise ValueError('shape mismatch')
                    raw=os.pread(fd,hi-lo,base+lo)
                    if len(raw)!=hi-lo:raise IOError('short source read')
                    f.write(raw);digest.update(raw);size+=len(raw)
                if record_bytes is None:record_bytes=size
                if record_bytes!=size:raise ValueError('record size mismatch')
                total+=size
            f.flush();os.fsync(f.fileno())
        info={'layer':layer,'expert_to_record':{i:i for i in range(384)},'record_bytes':record_bytes,'shapes':shapes,'sha256':digest.hexdigest(),
              'checkpoint_index_sha256':source_hash,'complete_experts':384,'byte_preserving':True}
        os.replace(partial,path)
        tmp=Path(str(meta)+'.partial');tmp.write_text(json.dumps(info,indent=2));os.replace(tmp,meta)
        completed.append(layer)
        receipt={'status':'complete' if len(completed)==40 else 'running','layers':completed,'checkpoint_index_sha256':source_hash,'elapsed_seconds':time.time()-started,'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        (a.output/'manifest.json').write_text(json.dumps(receipt,indent=2))
        print(json.dumps({'layer':layer,'bytes':total,'elapsed':time.time()-started}),flush=True)
    source.close()
if __name__=='__main__':main()
