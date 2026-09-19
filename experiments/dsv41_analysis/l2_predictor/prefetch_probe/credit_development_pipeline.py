"""Freeze a short-probe winner, then evaluate all existing scope-validation families."""
import hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
here=Path(__file__).parent
root=Path('artifacts/dsv41-l2-prefetch-credit-development-20260916');root.mkdir(exist_ok=True)
policy=Path('artifacts/dsv41-l2-prefetch-startup-20260916')
child=None
signal.signal(signal.SIGTERM,lambda *a:(_ for _ in ()).throw(SystemExit('interrupted')))
def status(**kw):
 (root/'status.json').write_text(json.dumps(dict(pid=os.getpid(),updated_at=time.time(),**kw),indent=2))
try:
 status(phase='waiting_for_policy_report')
 while not (policy/'report.json').exists():
  if (policy/'status.json').exists() and json.loads((policy/'status.json').read_text())['phase']=='failed':raise RuntimeError('Policy probe failed; inspect before resuming')
  time.sleep(20)
 report=json.loads((policy/'report.json').read_text());assert report['exact_primary_parity']
 candidates={k:v for k,v in report['results'].items() if 'timely_coverage' in v and v['peak_bytes']<=65_000_000_000 and v.get('route_boundaries_candidate',10**9)<=v.get('route_boundaries_baseline',0)}
 assert candidates,'No candidate under memory budget'
 winner=max(candidates,key=lambda k:candidates[k]['timely_coverage']);_,mode,_=winner.split('-');tail='zero'
 plan=json.loads(Path('artifacts/dsv41-l2-state-v3-20260916/plan.json').read_text())
 rows=[r for r in plan['samples'] if r['split']=='validation' and r['kind']=='scope']
 assert rows and len({(r['scope'],r['language']) for r in rows})==len(rows)
 frozen=dict(candidate=winner,mode=mode,tail=tail,notice_mode='credit',notice_group=2,startup=True,read_cap=64,staging_slots_per_layer=8,decode=128,expert_no_cache=True,rows=rows,independent_acceptance=False,selection='Highest timely coverage on preceding development probe subject to exact parity and 65GB footprint. Broader results are validation, not final test.')
 (root/'plan.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2))
 for row in rows:
  fixture=Path(row['fixture']);assert hashlib.sha256(fixture.read_bytes()).hexdigest()==row['fixture_sha256']
  case=root/row['id'];case.mkdir(exist_ok=True)
  for label,current_mode,current_tail,enabled in [('baseline','baseline','zero','0'),('candidate',mode,tail,'1')]:
   out=case/label
   if (out/'manifest.json').exists() and json.loads((out/'manifest.json').read_text()).get('status')=='complete':continue
   assert not out.exists(),f'Inspect incomplete run: {out}'
   status(phase='running',case=row['id'],variant=label)
   env=dict(os.environ,DYLD_LIBRARY_PATH=str(Path('artifacts/dsv41-miss-resume-mlx-build').resolve()),L2_PROBE_MODE=current_mode,L2_PROBE_TAIL=current_tail,L2_NOTICE_MODE='credit',L2_NOTICE_GROUP='2',L2_CREDIT_STARTUP='1',L2_PROBE_CANONICAL='1',L2_PREFETCH=enabled,L2_PROBE_OUTPUT=str(out))
   with (case/f'{label}.log').open('w') as log:
    child=subprocess.Popen([sys.executable,str(here/'entry.py'),'--output',str(out),'--prompt-json',str(fixture),'--decode','128','--prefill-slots','64','--logits-mode','hash','--inference-mode','legacy','--expert-no-cache'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    if child.wait():raise RuntimeError(f'{row["id"]}/{label} failed')
  (case/'complete.json').write_text(json.dumps(dict(complete=True)))
  with (case/'report.log').open('w') as log:subprocess.run([sys.executable,str(here/'report.py'),'--root',str(case)],check=True,stdout=log)
  d=json.loads((case/'report.json').read_text());assert d['exact_primary_parity']
  assert all(r['peak_bytes']<=65_000_000_000 for r in d['results'].values()),'Footprint gate failed'
 # Sum original misses, never average percentages across cases.
 results={row['id']:json.loads((root/row['id']/'report.json').read_text())['results'] for row in rows}
 total={k:sum(r['candidate'][k] for r in results.values()) for k in ['base_misses','timely','late','foreground','prefetch_reads','unused_reads']}
 total['timely_coverage']=total['timely']/total['base_misses'];total['wasted_MB_per_token']=total['unused_reads']*18.800640/(128*len(rows))
 total['total_decode_read_change_fraction']=(total['prefetch_reads']+total['foreground'])/total['base_misses']-1
 (root/'report.json').write_text(json.dumps(dict(candidate=winner,totals=total,cases=results,independent_acceptance=False,goal_complete=False,route_boundaries_baseline=sum(r['candidate']['route_boundaries_baseline'] for r in results.values()),route_boundaries_candidate=sum(r['candidate']['route_boundaries_candidate'] for r in results.values())),indent=2))
 status(phase='complete',goal_complete=False)
except BaseException as error:
 status(phase='failed',error=str(error));raise
finally:
 if child is not None and child.poll() is None:os.killpg(child.pid,signal.SIGTERM);child.wait()
