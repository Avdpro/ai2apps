"""Aggregate all cases, task-family bootstrap, fixed adoption gates."""
import json,hashlib
from collections import defaultdict
from pathlib import Path
import numpy as np
from batch import ROOT,DATA

def measure(m):
    t=m['step_seconds'];n=len(t)-1;tail_count=min(128,max(1,n//2));cold_count=min(n,16)
    return dict(decode=n/sum(t[1:]),tail=tail_count/sum(t[-tail_count:]),cold_decode=cold_count/sum(t[1:cold_count+1]),prefill=len(m['input_ids'])/t[0],ttft=t[0],cold_ttft=m.get('cold_ttft_seconds',t[0]),nonforward_wall=m['total_seconds']-sum(t),peak=m['sampled_physical_footprint_peak_bytes']/1e9,hit_pct=100*(1-m['cache_stats']['misses']/(40*6*n)),all_hit_pct=100*m['cache_stats']['all_hit_steps']/(40*n),promotion_loads=sum(len(p['pairs']) for p in m['adaptive_l1']['promotions']),miss=m['cache_stats']['misses'],all_hit=m['cache_stats']['all_hit_steps'],kernel_decode_read_gb=m.get('kernel_decode_disk_read_bytes',float('nan'))/1e9,io=sum(m['adaptive_l1']['decode_io_seconds'].values()))

def main():
    data=json.loads(DATA.read_text());rows=[r for r in data['samples'] if r['split']=='test'];case=[]
    for row in rows:
        variants={}
        for v in ['main40','shape']:
            paths=sorted((ROOT/('test-'+v)).glob(row['id']+'-r*/manifest.json'))
            assert len(paths)>=2
            measures=[measure(json.loads(p.read_text())) for p in paths]
            variants[v]={k:float(np.mean([x[k] for x in measures])) for k in measures[0]}
            variants[v]['peak']=max(x['peak'] for x in measures)
        case.append({**row,'results':variants,'decode_gain':variants['shape']['decode']/variants['main40']['decode']-1,'prefill_gain':variants['shape']['prefill']/variants['main40']['prefill']-1})
    families=defaultdict(list)
    for c in case:families[(c['scope'],c['family_id'])].append(c)
    paired=np.array([[np.mean([c['results'][v]['decode'] for c in cs]) for v in ['main40','shape']] for cs in families.values()])
    rng=np.random.default_rng(20260915)
    boots=[]
    for _ in range(10000):
        sample=paired[rng.integers(len(paired),size=len(paired))].mean(axis=0);boots.append(sample[1]/sample[0]-1)
    ci=np.quantile(boots,[.025,.975]).tolist()
    groups={s:float(np.mean([c['results']['shape']['decode'] for c in case if c['scope']==s])/np.mean([c['results']['main40']['decode'] for c in case if c['scope']==s])-1) for s in sorted({r['scope'] for r in rows})}
    means=paired.mean(axis=0);gain=float(means[1]/means[0]-1)
    prefill=float(np.mean([c['results']['shape']['prefill'] for c in case])/np.mean([c['results']['main40']['prefill'] for c in case])-1)
    peak=max(c['results']['shape']['peak'] for c in case)
    passed=gain>=.03 and prefill>=-.03 and min(groups.values())>=-.05 and ci[0]>0 and peak<=65
    result={'adopt':passed,'default':'Main40 remains unchanged pending explicit review','decode_macro_tps':{'main40':float(means[0]),'shape':float(means[1])},'macro_metrics':{v:{k:float(np.mean([c['results'][v][k] for c in case])) for k in ['tail','cold_decode','prefill','ttft','cold_ttft','hit_pct','all_hit_pct','promotion_loads','miss','all_hit','kernel_decode_read_gb','io']} for v in ['main40','shape']},'decode_gain':gain,'prefill_gain':prefill,'family_bootstrap95':ci,'task_decode_gain':groups,'peak_gb':peak,'cases':case,'regressions_over5pct':[c['id'] for c in case if c['decode_gain']<-.05]}
    long_rows=[r for r in rows if r['decode_steps']==512]
    segments={}
    for variant in ['main40','shape']:
        first=[];later=[]
        for row in long_rows:
            timings=[json.loads(p.read_text())['step_seconds'][1:] for p in (ROOT/('test-'+variant)).glob(row['id']+'-r*/manifest.json')]
            assert all(len(t)==512 for t in timings)
            first.append(np.mean([128/sum(t[:128]) for t in timings]))
            later.append(np.mean([384/sum(t[128:]) for t in timings]))
        segments[variant]={'first128_tps':float(np.mean(first)),'later384_tps':float(np.mean(later)),'cases':len(long_rows)}
    result['long_decode_segments']=segments
    result['length_groups']={}
    for name,subset in [('short',[c for c in case if c['kind']!='synthetic_evidence_long']),('approximately_2048',[c for c in case if c['kind']=='synthetic_evidence_long'])]:
        result['length_groups'][name]={'cases':len(subset)}
        for variant in ['main40','shape']:
            result['length_groups'][name][variant]={k:float(np.mean([c['results'][variant][k] for c in subset])) for k in ['decode','prefill','tail','hit_pct','all_hit_pct']}
    (ROOT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
