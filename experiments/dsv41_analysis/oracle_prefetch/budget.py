import hashlib,json,os,subprocess,sys
from pathlib import Path
r=Path('artifacts/dsv41-oracle-prefetch-20260915');assert (r/'complete.json').exists()
s=Path('experiments/dsv41_analysis/oracle_prefetch/entry.py').read_text();s=s.replace('self.step=step;self.layer=0;',"self.step=step;self.remaining=int(os.environ['ORACLE_BUDGET']);self.layer=0;")
s=s.replace('if not self.busy and not self.foreground and available:', 'if not self.busy and not self.foreground and available and self.remaining>0:')
s=s.replace('j=available[0];self.busy=True;break','j=available[0];self.limit=min(self.batch,self.remaining);self.remaining-=min(self.limit,len(j[\'ids\'])-j[\'pos\']);self.busy=True;break')
s=s.replace("j['pos']+self.batch","j['pos']+self.limit")
p=r/'source/experiments/dsv41_mlx/budget_entry.py';p.write_text(s)
case='coding-en-train-18';base=r/f'{case}-baseline1';b=json.loads((base/'manifest.json').read_text());bst=json.loads((base/'oracle-stats.json').read_text());rows=[]
for cap in [8,16,32]:
 out=r/f'{case}-budget{cap}';cmd=[sys.executable,str(p),'--prompt-json',f'artifacts/dsv41-l1-shape-20260915/dataset/{case}.json','--decode','128','--prefill-slots','64','--logits-mode','hash','--output',str(out)]
 env=dict(os.environ,ORACLE_MODE='oracle',ORACLE_BATCH='2',ORACLE_PLAN=str(base/'oracle-plan.json'),ORACLE_OUTPUT=str(out),ORACLE_BUDGET=str(cap))
 with out.with_suffix('.log').open('w') as h:subprocess.run(cmd,env=env,stdout=h,stderr=subprocess.STDOUT,check=True)
 m=json.loads((out/'manifest.json').read_text());assert m['status']=='complete'
 for k in ['input_ids','generated_ids','logits_sha256','cache_stats','expert_total_read_bytes']:assert m[k]==b[k]
 st=json.loads((out/'oracle-stats.json').read_text());assert st['bank_fences']==bst['bank_fences'];ev=st['events'];counts={i:sum(e['experts'] for e in ev if e['background'] and e['step']==i) for i in range(1,129)};assert max(counts.values())<=cap
 t=m['step_seconds'];x=dict(cap=cap,tps=128/sum(t[1:]),tail_tps=112/sum(t[17:]),background_per_token=sum(counts.values())/128,ready_layers=sum(x['ready'] for x in st['fulfilled']),miss_layers=len(st['fulfilled']),peak_gb=m['sampled_physical_footprint_peak_bytes']/1e9);assert x['peak_gb']<65;rows.append(x);(r/'budget-results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(x),flush=True)
(r/'budget-verification.json').write_text(json.dumps({'runs':3,'logits_cache_bytes_fences_exact':True,'per_token_budget_respected':True,'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()},indent=2))
