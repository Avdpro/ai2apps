from pathlib import Path
import io,json,math,wave
import av,numpy as np
from ai2apps.studio.media_workflows import _read_audio,_wav,replace_video_audio
rate=48000
voices=[]
for key in ['a','b']:
 audio,sr=_read_audio(Path('/tmp/speaker-preservation-'+key+'.aiff').read_bytes())
 assert sr==rate
 voices.append(audio.mean(axis=1)*.65)
a,b=voices
windows=[];offset=rate*2
for speaker,values in [('A',a),('B',b),('A',a)]:
 windows.append({'speaker':speaker,'start':offset/rate,'end':(offset+len(values))/rate})
 offset+=len(values)+rate
frames=math.ceil((offset+rate)/rate*10);n=round(frames/10*rate)
t=np.arange(n,dtype=np.float64)/rate
# Quiet, continuous test music with distinct left/right harmonics and modulation.
bg=np.stack([.025*np.sin(2*np.pi*220*t)*(1+.2*np.sin(2*np.pi*.7*t)),.025*np.sin(2*np.pi*330*t)*(1+.2*np.sin(2*np.pi*.9*t))],axis=1).astype(np.float32)
dialogue=np.zeros_like(bg)
for w,values in zip(windows,[a,b,a]):
 st=round(w['start']*rate);dialogue[st:st+len(values)]+=values[:,None]
mixed=bg+dialogue
Path('/tmp/speaker-preservation-source.wav').write_bytes(_wav(mixed,rate))
np.savez('/tmp/speaker-preservation-groundtruth.npz',background=bg,dialogue=dialogue,mix=mixed,rate=rate)
with av.open('/tmp/speaker-preservation-frames.mp4','w') as c:
 s=c.add_stream('mpeg4',rate=10);s.width=320;s.height=180;s.pix_fmt='yuv420p'
 for i in range(frames):
  arr=np.zeros((180,320,3),np.uint8);arr[:]=[30+i%100,55,90];arr[:,(i*5)%300:(i*5)%300+20,1]=220
  f=av.VideoFrame.from_ndarray(arr,format='rgb24');f.pts=i
  for p in s.encode(f):c.mux(p)
 for p in s.encode():c.mux(p)
Path('/tmp/speaker-preservation-test.mp4').write_bytes(replace_video_audio(Path('/tmp/speaker-preservation-frames.mp4'),_wav(mixed,rate)))
info={'windows':windows,'duration':frames/10,'frames':frames,'source':'/tmp/speaker-preservation-test.mp4','reference':'/tmp/speaker-preservation-ref.aiff'}
Path('/tmp/speaker-preservation-fixture.json').write_text(json.dumps(info,indent=2));print(json.dumps(info))
