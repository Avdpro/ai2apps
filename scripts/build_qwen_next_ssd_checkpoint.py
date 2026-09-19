#!/usr/bin/env python3
"""Export Qwen Next's existing fused-v1 records plus compact original backbone."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from ssd_checkpoint_io import CHUNK,header,safe_file,sha,clone,subset

PATTERN=re.compile(r'^language_model\.model\.layers\.(\d+)\.mlp\.switch_mlp\.(gate_proj|up_proj|down_proj)\.(weight|scales|biases)$')
VARIANT='qwen4-exp-affine-q4-gate-up-fused-v1'

def build(source,store,output,repo,revision,layers=48,experts=512):
    if output.exists():raise FileExistsError(output)
    stage=output.with_name(output.name+'.partial');stage.mkdir(parents=True,exist_ok=False);(stage/'experts').mkdir()
    index=json.loads((source/'model.safetensors.index.json').read_text());wm=index['weight_map'];entries={};headers={}
    for name in sorted(set(wm.values())):
        p=safe_file(source,name);base,h=header(p);headers[name]=(base,h)
        for k,v in h.items():
            if k=='__metadata__':continue
            if wm.get(k)!=name or k in entries:raise ValueError('source index mismatch')
            entries[k]=(p,base,v)
    if set(entries)!=set(wm):raise ValueError('missing tensor')
    external={k for k in entries if PATTERN.fullmatch(k)}
    expected={f'language_model.model.layers.{l}.mlp.switch_mlp.{p}.{c}' for l in range(layers) for p in ['gate_proj','up_proj','down_proj'] for c in ['weight','scales','biases']}
    if external!=expected:raise ValueError('incomplete Qwen expert coverage')
    locations={};hashes={};files={};expert_bytes=0;layer_manifest={}
    for l in range(layers):
        name=f'layer-{l:03d}.moe';p=store/name
        with p.open('rb') as f:
            n=int.from_bytes(f.read(8),'little')
            if not 0<n<=4088:raise ValueError('bad store header')
            m=json.loads(f.read(n))
        if (m.get('variant')!=VARIANT or m.get('layer')!=l or m.get('num_experts')!=experts
            or m.get('data_offset')!=4096 or p.stat().st_size!=4096+experts*m['record_bytes']):raise ValueError('store layout/coverage mismatch')
        tensors={t['name']:t for t in m['tensors']};target=stage/'experts'/name;clone(p,target)
        m['source']=repo;m['source_revision']=revision
        encoded=json.dumps(m,separators=(',',':'),sort_keys=True).encode()
        if len(encoded)>4088:raise ValueError('export store header overflow')
        with target.open('r+b') as f:f.write(len(encoded).to_bytes(8,'little')+encoded+bytes(4088-len(encoded)))
        with target.open('rb') as packed:
            for proj in ['gate_proj','up_proj','down_proj']:
                for comp in ['weight','scales','biases']:
                    key=f'language_model.model.layers.{l}.mlp.switch_mlp.{proj}.{comp}';src,base,v=entries[key]
                    lo,hi=v['data_offsets']
                    if v['shape'][0]!=experts or (hi-lo)%experts:raise ValueError('stacked shape mismatch')
                    row=(hi-lo)//experts;t=tensors[('gate_up_proj' if proj!='down_proj' else proj)+'.'+comp]
                    shape=list(v['shape'][1:]);shape[0]*=2 if proj!='down_proj' else 1
                    if t['dtype']!=v['dtype'] or t['shape']!=shape or t['nbytes']!=row*(2 if proj!='down_proj' else 1):raise ValueError('fused segment mismatch')
                    offset=4096+t['offset']+(row if proj=='up_proj' else 0)
                    if t['offset']<0 or t['offset']+t['nbytes']>m['record_bytes']:raise ValueError('segment outside record')
                    digest=hashlib.sha256()
                    with src.open('rb') as f:
                        f.seek(base+lo)
                        for e in range(experts):
                            packed.seek(offset+e*m['record_bytes']);left=row
                            while left:
                                a=f.read(min(CHUNK,left));b=packed.read(len(a))
                                if not a or a!=b:raise ValueError('expert bytes mismatch: '+key)
                                digest.update(a);left-=len(a)
                    hashes[key]=digest.hexdigest()
                    locations[key]={'file':'experts/'+name,'offset':offset,'count':experts,'stride':m['record_bytes'],'row_bytes':row,'dtype':v['dtype'],'shape':v['shape']}
        files['experts/'+name]={'size':target.stat().st_size,'sha256':sha(target)};expert_bytes+=target.stat().st_size
        layer_manifest[str(l)]={'file':name,'file_bytes':target.stat().st_size,'num_experts':experts,'record_bytes':m['record_bytes']}
        print(json.dumps({'phase':'verified_experts','layer':l}),flush=True)
    (stage/'experts/manifest.json').write_text(json.dumps({'format':'omlx-moe-expert-major-set','version':1,'variant':VARIANT,'layers':layer_manifest},indent=2))
    new_map={};backbone_bytes=0
    for name,(base,h) in headers.items():
        selected={k:v for k,v in h.items() if k!='__metadata__' and k not in external}
        if not selected:continue
        target=safe_file(stage,name);target.parent.mkdir(parents=True,exist_ok=True)
        size,ds=subset(safe_file(source,name),target,selected,base);hashes.update(ds);backbone_bytes+=size;new_map.update({k:name for k in selected})
        print(json.dumps({'phase':'verified_backbone','shard':name}),flush=True)
    (stage/'model.safetensors.index.json').write_text(json.dumps({'metadata':{'total_size':backbone_bytes},'weight_map':new_map},indent=2))
    for name in ['LICENSE','README.md','config.json','generation_config.json','preprocessor_config.json','tokenizer.json','tokenizer_config.json','chat_template.jinja','merges.txt','vocab.json']:
        p=source/name
        if p.is_file():shutil.copyfile(p,stage/name)
    (stage/'external-tensors.json').write_text(json.dumps(locations,sort_keys=True));(stage/'source-tensor-sha256.json').write_text(json.dumps(hashes,sort_keys=True))
    for p in sorted(stage.rglob('*')):
        k=p.relative_to(stage).as_posix()
        if p.is_file() and k not in files:files[k]={'size':p.stat().st_size,'sha256':sha(p)}
    m={'schema':'ai2apps.ssd-checkpoint/v1','family':'qwen4_exp','layout':VARIANT,'source':{'repo_id':repo,'revision':revision,'index_sha256':sha(source/'model.safetensors.index.json')},'index_sha256':sha(stage/'model.safetensors.index.json'),'expert_store':'experts','tensor_count':len(entries),'verification':'all_tensor_payloads_equal','backbone_payload_bytes':backbone_bytes,'expert_file_bytes':expert_bytes,'files':files,'builder_sha256':sha(Path(__file__)),'io_helper_sha256':sha(Path(__file__).with_name('ssd_checkpoint_io.py'))}
    (stage/'ssd-checkpoint.json').write_text(json.dumps(m,indent=2));stage.rename(output);return m

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--expert-store',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--source-repo',required=True);ap.add_argument('--source-revision',required=True);a=ap.parse_args()
    if not re.fullmatch('[0-9a-f]{40}',a.source_revision):ap.error('immutable revision required')
    build(a.source.resolve(),a.expert_store.resolve(),a.output.resolve(),a.source_repo,a.source_revision)
