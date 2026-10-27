from pathlib import Path
import sqlite3,json,hashlib,sys
import av,numpy as np
from ai2apps.studio.media_workflows import _read_audio
r=Path.home()/'Library/Application Support/AI2Apps/instances/app-dev'
c=sqlite3.connect('file:'+str(r/'data/platform/ai2apps-platform.sqlite3')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
row=c.execute("select * from studio_background_jobs where id=?",(sys.argv[1],)).fetchone()
payload=json.loads(row['request_json']);result=json.loads(row['result_json'] or '{}')
print('JOB',row['id'],row['status'],row['error_json'])
if row['status']!='succeeded':sys.exit(2)
artid=result['downloadUrl'].split('/')[-2]
a=c.execute('select storage_key,media_type from artifacts where id=?',(artid,)).fetchone();out=r/'data/platform/artifacts'/a['storage_key']
source=Path(payload['source_reference']['resolved'])
def frames(path):
 with av.open(str(path)) as v:return [(float(f.time or 0),hashlib.sha256(f.to_ndarray(format='rgb24').tobytes()).hexdigest()) for f in v.decode(video=0)]
def metrics(x,y):
 x=np.asarray(x,dtype=np.float64).flatten();y=np.asarray(y,dtype=np.float64).flatten();diff=y-x
 rms=lambda a:float(np.sqrt(np.mean(a*a)))
 return {'samples':len(x),'correlation':float(np.corrcoef(x,y)[0,1]),'snr_db':float(20*np.log10(max(rms(x),1e-12)/max(rms(diff),1e-12))),'rms_difference':rms(diff),'gain_db':float(20*np.log10(max(abs(float(x@y/(x@x))),1e-12)))}
x,rate=_read_audio(source.read_bytes());y,_=_read_audio(out.read_bytes());n=min(len(x),len(y));x=x[:n];y=y[:n]
def window(start,end):return metrics(x[round(start*rate):round(end*rate)],y[round(start*rate):round(end*rate)])
report={'job_id':row['id'],'studio_run_id':row['run_id'],'output_artifact_id':artid,'output_path':str(out),'output_size':out.stat().st_size,
 'video_frames':len(frames(source)),'frame_and_timestamp_parity':frames(source)==frames(out),'source_audio_seconds':len(x)/rate,'output_audio_seconds':len(y)/rate,
 'source_reference':True,'reference_reference':bool(payload.get('reference_reference')),'source_staged':(Path(payload['root'])/'source').exists(),'reference_staged':(Path(payload['root'])/'reference').exists(),
 'target_A_first':window(2.2,7.2),'target_A_last':window(16.9,21.8),'non_target_B':window(9,15.2),
 'background_intro':window(.3,1.5),'background_tail':window(22.8,24),
 'continuous_stereo_background':metrics((x[:,0]-x[:,1])/2,(y[:,0]-y[:,1])/2)}
assert report['frame_and_timestamp_parity'] and report['video_frames']==243
assert report['non_target_B']['correlation']>.995 and abs(report['non_target_B']['gain_db'])<.1
assert report['background_intro']['correlation']>.999 and report['background_tail']['correlation']>.999
assert report['continuous_stereo_background']['correlation']>.95
assert report['target_A_first']['correlation']<.2 and report['target_A_last']['correlation']<.2
assert not report['source_staged'] and not report['reference_staged']
Path('/tmp/speaker-preservation-live-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
