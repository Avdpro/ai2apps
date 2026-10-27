"""Actual reference/Composer/queue integration; upscaling model calls are fixtures."""
import asyncio
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace as NS
import json
import pytest
import av
import numpy as np
from ai2apps.chat import ChatRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.services import ToolCallContext
from ai2apps.studio import video_aaat as owner
from test_app_interactions import runtime


def video(path,color=64):
    with av.open(str(path),'w') as container:
        stream=container.add_stream('mpeg4',rate=10);stream.width=64;stream.height=64;stream.pix_fmt='yuv420p'
        for i in range(10):
            frame=av.VideoFrame.from_ndarray(np.full((64,64,3),color,dtype=np.uint8),format='rgb24')
            frame.pts=i
            for packet in stream.encode(frame):container.mux(packet)
        for packet in stream.encode():container.mux(packet)


def setup(runtime,tmp_path):
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='video')
    ctx=replace(ToolCallContext.from_principal(RequestPrincipal.legacy_local(),caller_id='test',session_id=thread.session.id),invocation_id='edit')
    items=[]
    for n in range(2):
        path=tmp_path/f'input{n}.mp4';video(path,64+n*32)
        items.append(runtime.documents.create_reference(ctx.session_id,path,media_type='video/mp4'))
    return ctx,items


@pytest.mark.asyncio
@pytest.mark.parametrize('operation',['trim','join'])
async def test_basic_edits_actual_render_publish_and_exact_replay(runtime,tmp_path,operation):
    ctx,items=setup(runtime,tmp_path)
    args={'operation':operation,'media_ids':[i.id for i in items] if operation=='join' else [items[0].id]}
    if operation=='trim':args.update(start_seconds=.2,end_seconds=.7)
    await runtime.studio_jobs.startup()
    try:
        result=await runtime.app_capability_router.invoke('video.process',args,ctx)
        repeated=await runtime.app_capability_router.invoke('video.process',args,ctx)
        assert repeated['studio_job_id']==result['studio_job_id']
        job=runtime.studio_jobs.get(result['studio_job_id'],RequestPrincipal.legacy_local())
        with runtime.database.transaction() as db:payload=json.loads(db.execute('SELECT request_json FROM studio_background_jobs WHERE id=?',(job['id'],)).fetchone()[0])
        assert all('reference' in s for s in payload['sources'].values())
        out=runtime.workspace.get_artifact(ctx.session_id,result['files'][0]['artifact_id'])
        with av.open(str(runtime.workspace.artifact_path(out))) as media:
            frames=list(media.decode(video=0))
            assert len(frames)==(15 if operation=='trim' else 60)
        if operation=='join':
            assert float(frames[0].to_ndarray(format='rgb24').mean())<float(frames[-1].to_ndarray(format='rgb24').mean())
        assert result['aaat_context']['scope']['studio_mini_app_id']==owner.COMPOSER
        with pytest.raises(Exception):await runtime.app_capability_router.invoke('video.process',{**args,'operation':'extract_audio'},ctx)
    finally:await runtime.studio_jobs.shutdown()


@pytest.mark.asyncio
async def test_basic_preflight_rejects_ownership_bounds_missing_audio_and_ignored_arguments(runtime,tmp_path):
    ctx,items=setup(runtime,tmp_path)
    for args in [
        {'operation':'trim','media_ids':[items[0].id],'end_seconds':2},
        {'operation':'trim','media_ids':[items[0].id],'start_seconds':.8,'end_seconds':.5},
        {'operation':'join','media_ids':[items[0].id]},
        {'operation':'join','media_ids':[i.id for i in items],'end_seconds':1},
        {'operation':'extract_audio','media_ids':[items[0].id]},
    ]:
        with pytest.raises(Exception):await runtime.app_capability_router.invoke('video.process',args,ctx)
    foreign,_=ChatRepository(runtime.database,runtime.events).create_thread(title='other')
    with pytest.raises(Exception):await runtime.app_capability_router.invoke('video.process',{'operation':'trim','media_ids':[items[0].id],'end_seconds':.5},replace(ctx,session_id=foreign.session.id))
    with runtime.database.transaction() as db:assert db.execute('SELECT COUNT(*) FROM studio_background_jobs').fetchone()[0]==0


@pytest.mark.asyncio
async def test_upscale_original_reference_missing_models_idempotence_and_output(runtime,tmp_path,monkeypatch):
    from ai2apps.studio import upscaling
    ctx,items=setup(runtime,tmp_path)
    model=NS(id='fixture.declared.upscaler',model_type='video_upscaling',capabilities=['video_upscaling'],metadata={},display_name='Fixture',video_upscaling_capabilities={'maximum_frames':30,'maximum_seconds':2})
    monkeypatch.setattr(upscaling,'_models',lambda _:[model])
    monkeypatch.setattr(upscaling,'_model_ready',lambda *a:False)
    d=await owner.upscale_descriptor(runtime,RequestPrincipal.legacy_local())
    assert d['configuration_required'] and d['install']['capability']=='video.upscaling'
    monkeypatch.setattr(upscaling,'_model_ready',lambda *a:True)
    async def infer(model_id,operation,body,destination,**kw):
        source=kw['files']['video'][1]
        assert source==tmp_path/'input0.mp4'
        import shutil
        shutil.copyfile(source,destination)
    monkeypatch.setattr(runtime.model_invocations,'invoke_background_to_file',infer)
    monkeypatch.setattr(upscaling,'inspect_source',lambda *a,**kw:NS(frames=10,fps=Fraction(10)))
    args={'video_id':items[0].id,'model_id':model.id,'seed':4}
    await runtime.studio_jobs.startup()
    try:
        result=await runtime.app_capability_router.invoke('video.upscale',args,ctx)
        again=await runtime.app_capability_router.invoke('video.upscale',args,ctx)
        assert result['studio_job_id']==again['studio_job_id']
        assert result['files'][0]['media_type']=='video/mp4'
        assert (tmp_path/'input0.mp4').exists()
        # Existing successful job is not regenerated when observed again.
        with pytest.raises(Exception):await runtime.app_capability_router.invoke('video.upscale',{**args,'seed':9},ctx)
    finally:await runtime.studio_jobs.shutdown()
