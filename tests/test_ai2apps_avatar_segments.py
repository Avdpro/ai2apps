import hashlib
import json
from pathlib import Path
import zipfile
import pytest
from ai2apps.avatar.segments import job_digest, read_packet, write_packet

@pytest.fixture
def bundle(tmp_path):
    video=tmp_path/'source.mp4';video.write_bytes(b'video payload')
    state=tmp_path/'source.npy';state.write_bytes(b'opaque model state')
    packet=tmp_path/'segment.zip'
    expected=dict(identity=job_digest({'image':'sha-a','audio':'sha-b','model':'pin-1'}),index=0,start_frame=0,end_frame=187,fps=24,previous_state=None)
    receipt=write_packet(packet,video,state,**expected)
    return packet,expected,receipt

def test_atomic_verified_segment_and_predecessor(tmp_path,bundle):
    packet,expected,receipt=bundle
    destination=tmp_path/'verified'
    assert read_packet(packet,destination=destination,**expected)==receipt
    assert (destination/'video.mp4').read_bytes()==b'video payload'
    next_packet=tmp_path/'next.zip'
    follow={**expected,'index':1,'start_frame':187,'end_frame':340,'previous_state':receipt['state_sha256']}
    write_packet(next_packet,destination/'video.mp4',destination/'state.npy',**follow)
    assert read_packet(next_packet,**follow)['end_frame']==340
    with pytest.raises(ValueError,match='predecessor'):
        read_packet(next_packet,**{**follow,'previous_state':'0'*64})

@pytest.mark.parametrize('field,value', [('identity','0'*64),('index',1),('start_frame',1),('end_frame',188),('fps',25)])
def test_reject_reordered_changed_or_cross_job_packet(tmp_path,bundle,field,value):
    packet,expected,_=bundle
    with pytest.raises(ValueError):read_packet(packet,destination=tmp_path/'accepted',**{**expected,field:value})
    assert not (tmp_path/'accepted').exists()
    assert not list(tmp_path.glob('.avatar-segment-*'))

@pytest.mark.parametrize('member,data', [('video.mp4',b'corrupt'),('state.npy',b'wrong context')])
def test_corrupt_payload_never_accepted(tmp_path,bundle,member,data):
    packet,expected,_=bundle
    with zipfile.ZipFile(packet) as z:files={n:z.read(n) for n in z.namelist()}
    files[member]=data
    with zipfile.ZipFile(packet,'w') as z:
        for n,d in files.items():z.writestr(n,d)
    with pytest.raises(ValueError,match='digest'):read_packet(packet,**expected)

@pytest.mark.parametrize('kind', ['traversal','duplicate','compressed','large_receipt'])
def test_reject_unsafe_archive(tmp_path,bundle,kind):
    packet,expected,_=bundle
    with zipfile.ZipFile(packet) as z:files={n:z.read(n) for n in z.namelist()}
    with zipfile.ZipFile(packet,'w',compression=zipfile.ZIP_DEFLATED if kind=='compressed' else zipfile.ZIP_STORED) as z:
        for n,d in files.items():
            if kind=='traversal' and n=='state.npy':n='../state.npy'
            if kind=='large_receipt' and n=='receipt.json':d=b' '*20000
            z.writestr(n,d)
        if kind=='duplicate':
            with pytest.warns(UserWarning):z.writestr('state.npy',b'duplicate')
    with pytest.raises(ValueError):read_packet(packet,**expected)


def test_job_identity_changes_with_pins_and_parameters():
    original={'checkpoint':'rev1','package':'sha1','seed':42,'input_sha':'a'}
    assert job_digest(original)==job_digest(dict(reversed(list(original.items()))))
    for key,value in [('checkpoint','rev2'),('package','sha2'),('seed',43),('input_sha','b')]:
        assert job_digest(original)!=job_digest({**original,key:value})

@pytest.mark.parametrize('samples,rate', [(1,22050),(60*22050,22050),(601*44100+7,44100),(3600*16000,16000)])
def test_long_plan_exact_coverage(samples,rate):
    from ai2apps.avatar.segment_jobs import h3_segments
    plan=h3_segments(samples,rate)
    assert plan[0].start_frame==0
    assert plan[-1].end_frame==(samples*24+rate-1)//rate
    assert all(a.end_frame==b.start_frame for a,b in zip(plan,plan[1:]))
    assert all(s.generate_frames<=192 for s in plan)

@pytest.mark.asyncio
async def test_cancel_resume_and_corrupt_successor_recovery(tmp_path):
    import asyncio
    from ai2apps.avatar.segment_jobs import h3_segments,run_segments
    plan=h3_segments(20*16000,16000);identity=job_digest({'model':'pinned','audio':'full-track'})
    calls=[];cancel=[False]
    async def invoke(segment,prior,previous,target):
        if segment.index:assert prior.read_bytes()==f'state-{segment.index-1}'.encode()
        video=tmp_path/'video';state=tmp_path/'state'
        video.write_bytes(f'clip-{segment.index}'.encode());state.write_bytes(f'state-{segment.index}'.encode())
        write_packet(target,video,state,identity=identity,index=segment.index,start_frame=segment.start_frame,end_frame=segment.end_frame,fps=24,previous_state=previous)
        calls.append(segment.index)
    def progress(done,total):
        if done==1:cancel[0]=True
    root=tmp_path/'job'
    with pytest.raises(asyncio.CancelledError):
        await run_segments(root,identity,plan,invoke=invoke,cancelled=lambda:cancel[0],progress=progress)
    assert calls==[0]
    cancel[0]=False
    paths=await run_segments(root,identity,plan,invoke=invoke)
    assert calls==list(range(len(plan)))
    assert len(paths)==len(plan)
    (root/'000001.zip').write_bytes(b'broken')
    calls.clear()
    await run_segments(root,identity,plan,invoke=invoke)
    assert calls==list(range(1,len(plan)))
    calls.clear()
    (root/'000000/state.npy').write_bytes(b'tampered extracted context')
    await run_segments(root,identity,plan,invoke=invoke)
    assert calls==[]
    assert (root/'000000/state.npy').read_bytes()==b'state-0'
    with pytest.raises(ValueError,match='identity'):
        await run_segments(root,job_digest({'different':'inputs'}),plan,invoke=invoke)
