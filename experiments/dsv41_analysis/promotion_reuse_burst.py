"""Small regression for Burst's shared pre-transaction promotion path."""
import json,os,signal
from promotion_reuse import DATA,ROOT,run,parity,pause_uploads

def main():
    row=next(r for r in json.loads(DATA.read_text())['samples'] if r['id']=='general-zh-train-20').copy();row['decode_steps']=32
    paused=pause_uploads();results=[]
    try:
        for burst in [(2,1),(4,4)]:
            a=run(row,'reread',burst=burst);b=run(row,'reuse',burst=burst);parity(a,b)
            assert a['burst']==b['burst']
            results.append({'top':burst[0],'block':burst[1],'decode_steps':32,'exact':True,'copied_experts':b['adaptive_l1']['promotion_reuse']['copied_experts'],'saved_ssd_bytes':a['expert_total_read_bytes']-b['expert_total_read_bytes']})
        (ROOT/'burst-check.json').write_text(json.dumps(results,indent=2));print(results)
    finally:
        for pid in paused:
            try:os.kill(pid,signal.SIGCONT)
            except ProcessLookupError:pass

if __name__=='__main__':main()
