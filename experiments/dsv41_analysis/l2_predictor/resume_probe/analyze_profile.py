"""Host deadlines and observed (not exhaustive) command-buffer GPU intervals."""
import collections
import json
from pathlib import Path

root=Path('artifacts/dsv41-l2-window-profile-v1-20260917')
assert json.loads((root/'status.json').read_text())['phase']=='complete'
def union(intervals):
    merged=[]
    for a,b in sorted(set(intervals)):
        if not merged or a>merged[-1][1]:merged.append([a,b])
        else:merged[-1][1]=max(merged[-1][1],b)
    return merged

def intersection(a,b):
    i=j=0;total=0.
    while i<len(a) and j<len(b):
        total+=max(0.,min(a[i][1],b[j][1])-max(a[i][0],b[j][0]))
        if a[i][1]<b[j][1]:i+=1
        else:j+=1
    return total

results={}
for predictor in ('state','lookahead','block6'):
    d=json.loads((root/predictor/'l2-window.json').read_text())
    snapshots=[e for e in d['events'] if e['kind']=='ready_snapshot'];windows=d['gpu_windows']
    assert len(snapshots)==len(windows)
    deadlines={};gpu=[]
    for snapshot,w in zip(snapshots,windows):
        assert (snapshot['step'],snapshot['first'],snapshot['end'])==(w['step'],w['first'],w['end'])
        for layer in range(w['first'],w['end'] if w['failed']<0 else w['failed']+1):deadlines[w['step'],layer]=(snapshot['time'],w['host_finished'])
        times=w['gpu_times'];assert len(times)%2==0
        for a,b in zip(times[::2],times[1::2]):
            assert a>0 and a<=b<=w['host_finished']+.01
            gpu.append((a,b))
    bins=collections.Counter()
    for read in d['reads']:
        snapshot,finished=deadlines[read['step'],read['layer']]
        bins['ready_before_snapshot_marker' if read['end']<=snapshot else 'after_snapshot_before_host_return' if read['end']<=finished else 'after_host_return']+=1
    io=union([(r['begin'],r['end']) for r in d['reads']]);gpu=union(gpu)
    io_seconds=sum(b-a for a,b in io);overlap=intersection(io,gpu)
    results[predictor]=dict(reads=len(d['reads']),deadline_bins=dict(bins),
        used=sum(t['used'] for t in d['tokens']),unused=sum(t['unused'] for t in d['tokens']),
        events=dict(collections.Counter(e['kind'] for e in d['events'])),
        background_busy_seconds=io_seconds,foreground_lock_wait_seconds=sum(e['wait'] for e in d['events'] if e['kind']=='foreground_acquired'),
        observed_gpu_busy_seconds=sum(b-a for a,b in gpu),background_overlap_with_observed_gpu_seconds=overlap,
        observed_overlap_fraction=overlap/io_seconds if io_seconds else 0.)
report=dict(results=results,limitations=[
    'GPU timestamps cover command buffers observed by the Gate/proposal bridge, not every command buffer. Overlap is a lower-bound observation, not complete GPU utilization.',
    'Snapshot marker is after host lookup construction; before-marker completion alone does not prove that expert was published or selected.',
    'After-snapshot completion cannot enter that already-built lookup. Host-return deadline is later than the actual GPU gate; late bins are conservative.',
    'No extra completed handlers or CPU waits were added for timestamps; profiling wall time is excluded from performance comparisons.',
    'Deadline bins concern all background reads, including prediction errors, not only actual routed misses.'])
(root/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
