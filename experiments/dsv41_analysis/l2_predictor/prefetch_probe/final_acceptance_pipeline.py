"""One frozen candidate, every reserved unseen conversation, no test-time tuning."""
import hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
import numpy as np
root=Path('artifacts/dsv41-l2-final-credit-v1-20260916')
receipt=json.loads((root/'frozen-candidate.json').read_text())
reservation=Path('artifacts/dsv41-l2-new-conversation-holdout-20260916/reservation.json')
plan=json.loads(reservation.read_text());rows=plan['samples'];assert len(rows)==24 and len({x['family_id'] for x in rows})==12
training=json.loads(Path('artifacts/dsv41-l2-state-v3-20260916/plan.json').read_text())
assert not {x['family_id'] for x in rows}&{x['family_id'] for x in training['samples']}
entry=root/'source/prefetch_probe/entry.py';reporter=root/'source/prefetch_probe/report.py';child=None
signal.signal(signal.SIGTERM,lambda *a:(_ for _ in ()).throw(SystemExit('interrupted')))
def status(**kw):
 (root/'status.json').write_text(json.dumps(dict(pid=os.getpid(),updated_at=time.time(),**kw),indent=2))
def verify_sources():
 for name,sha in receipt['source_hashes'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha,name
 for name,sha in receipt['base_source_hashes'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==sha,name
try:
 verify_sources()
 (root/'evaluation-plan.json').write_text(json.dumps(dict(reservation_sha256=hashlib.sha256(reservation.read_bytes()).hexdigest(),samples=rows,stop_at_eos=True,selection='All24 pre-reserved cases, no exclusions',candidate=receipt['candidate']),indent=2))
 results={};token_total=0
 for index,row in enumerate(rows):
  verify_sources();fixture=Path(row['fixture']);assert hashlib.sha256(fixture.read_bytes()).hexdigest()==row['fixture_sha256']
  case=root/row['id'];case.mkdir(exist_ok=True)
  for label in ('baseline','candidate'):
   out=case/label
   if (out/'manifest.json').exists() and json.loads((out/'manifest.json').read_text()).get('status')=='complete':continue
   assert not out.exists(),f'Inspect incomplete output before resuming: {out}'
   status(phase='running',case=row['id'],index=index,variant=label)
   env=dict(os.environ,DYLD_LIBRARY_PATH=str(Path('artifacts/dsv41-miss-resume-mlx-build').resolve()),L2_PROBE_MODE='block6' if label=='candidate' else 'baseline',L2_PROBE_TAIL='zero',L2_NOTICE_MODE='credit',L2_NOTICE_GROUP='2',L2_CREDIT_STARTUP='1',L2_PROBE_CANONICAL='1',L2_RECYCLE_CANCELLED='1',L2_PREFETCH='1' if label=='candidate' else '0',L2_PROBE_OUTPUT=str(out))
   with (case/f'{label}.log').open('w') as log:
    child=subprocess.Popen([sys.executable,str(entry),'--output',str(out),'--prompt-json',str(fixture),'--decode',str(row['decode_steps']),'--stop-at-eos','--prefill-slots','64','--logits-mode','hash','--inference-mode','legacy','--expert-no-cache'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    if child.wait():raise RuntimeError(f'{row["id"]}/{label} failed')
  (case/'complete.json').write_text(json.dumps(dict(complete=True)))
  with (case/'report.log').open('w') as log:subprocess.run([sys.executable,str(reporter),'--root',str(case)],check=True,stdout=log)
  d=json.loads((case/'report.json').read_text());assert d['exact_primary_parity']
  assert all(v['peak_bytes']<=65_000_000_000 for v in d['results'].values())
  d['test_opened']=True;d['scope']='Independent reserved conversation, frozen candidate, exact paired baseline, EOS stopping enabled'
  (case/'report.json').write_text(json.dumps(d,indent=2));results[row['id']]=d['results']
  with np.load(case/'candidate/routing.npz') as z:tokens=len(z['actual'])
  results[row['id']]['decode_tokens']=tokens;results[row['id']]['family_id']=row['family_id'];token_total+=tokens
 total={k:sum(v['candidate'][k] for v in results.values()) for k in ('base_misses','timely','late','foreground','prefetch_reads','unused_reads','route_boundaries_baseline','route_boundaries_candidate')}
 total.update(decode_tokens=token_total,timely_coverage=total['timely']/total['base_misses'],wasted_MB_per_token=total['unused_reads']*18.800640/token_total,total_decode_read_change_fraction=(total['prefetch_reads']+total['foreground'])/total['base_misses']-1)
 (root/'report.json').write_text(json.dumps(dict(candidate=receipt['candidate'],totals=total,cases=results,independent_acceptance=True,threshold_met=total['timely_coverage']>=.70,goal_complete=False,limitations=plan['limitations']),indent=2))
 status(phase='complete',threshold_met=total['timely_coverage']>=.70,goal_complete=False)
except BaseException as error:
 status(phase='failed',error=str(error));raise
finally:
 if child is not None and child.poll() is None:os.killpg(child.pid,signal.SIGTERM);child.wait()
