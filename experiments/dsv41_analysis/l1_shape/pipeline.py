"""Bounded sequential study; durable state and commands, never marks failures complete."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
from batch import ROOT

def main():
    state={'status':'running','started':time.time(),'stages':[],'analysis_source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}}
    try:
        for module,args in [('batch',['pilot']),('batch',['calibrate']),('batch',['collect']),('fit',[]),('qualify',[]),('evaluate',[]),('report',[]),('retest',[]),('report',[]),('write_report',[])]:
            command=[sys.executable,f'experiments/dsv41_analysis/l1_shape/{module}.py',*args]
            state['active']=command;(ROOT/'pipeline.json').write_text(json.dumps(state,indent=2))
            began=time.time();subprocess.run(command,check=True)
            state['stages'].append({'command':command,'seconds':time.time()-began,'module_sha256':hashlib.sha256(Path(command[1]).read_bytes()).hexdigest()})
        state['status']='complete'
    except BaseException as e:state.update(status='failed',error=repr(e));raise
    finally:
        state['updated']=time.time();(ROOT/'pipeline.json').write_text(json.dumps(state,indent=2))
if __name__=='__main__':main()
