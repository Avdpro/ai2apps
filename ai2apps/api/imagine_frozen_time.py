"""Frozen Time endpoints, scoped to the host-owned Imagine Studio Run."""
from __future__ import annotations
import asyncio
from contextlib import suppress
from io import BytesIO
from pathlib import Path
import shutil
import tempfile
from random import SystemRandom
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from ai2apps.model_invocation import ModelInvocationContext
from ai2apps.studio import StudioRepositoryError
from ai2apps.studio.frozen_time import FRAME_COUNTS
from ai2apps.studio.frozen_time_editor import parse_frame_plan
from ai2apps.studio.frozen_time_pipeline import DEPTH_MODELS, MERIDIAN, generate
from ai2apps.studio.live_photo import exporter_path
from ai2apps.api.frozen_preview import normalize_upload, register_preview
from ai2apps.studio.frozen_time_conversion import CACHE_FILES, convert_saved

MINI_APP_ID = "ai2apps.imagine.frozen-time"
FILES = {"output.mp4": "video/mp4", "output.html": "text/html", "live-photo.zip": "application/zip", 'LivePhoto.pvt.zip':'application/zip', "poster.jpg": "image/jpeg", 'LivePhoto.jpg':'image/jpeg','LivePhoto.mov':'video/quicktime'}


async def normalize_soundtrack(audio: UploadFile | None, output: str) -> bytes | None:
    if audio is None:
        return None
    if output != 'mp4':
        raise HTTPException(422, 'A soundtrack is only supported for MP4 output')
    if not (audio.content_type or '').startswith('audio/'):
        raise HTTPException(422, 'Choose an audio file')
    data = await audio.read(100 * 1024 * 1024 + 1)
    if not data or len(data) > 100 * 1024 * 1024:
        raise HTTPException(413, 'Soundtrack exceeds 100 MiB or is empty')
    def validate():
        import av
        with av.open(BytesIO(data)) as container:
            if not container.streams.audio or next(container.decode(audio=0), None) is None:
                raise ValueError('No decodable audio track')
    try:
        await asyncio.to_thread(validate)
    except Exception as error:
        raise HTTPException(422, 'Invalid soundtrack') from error
    return data


def create_frozen_router(runtime_provider, principal_dependency, studio, scoped_kwargs, studio_error):
    router = APIRouter()
    active = set()

    def ready(runtime, model_id, capability):
        model = runtime.model_invocations.model(model_id)
        return model is not None and model.checkpoint_ready and capability in model.capabilities

    def require_mount(mount_id, principal):
        from ai2apps.studio.capability_broker import StudioCapabilityBroker, StudioCapabilityError
        try:
            mounted = StudioCapabilityBroker(runtime_provider()).mounted_mini_app('ai2apps.imagine-studio', mount_id, principal=principal)
            if mounted.declaration.get('id') != MINI_APP_ID or not {'image.frozen_time.da', 'image.frozen_time.vggt'} <= mounted.capabilities:
                raise HTTPException(403, 'Frozen Time mount is not allowed')
        except StudioCapabilityError as error:
            raise HTTPException(error.status_code, str(error)) from error
        return mounted

    previews = register_preview(router,runtime_provider,principal_dependency,studio,scoped_kwargs,require_mount,ready)

    @router.post('/frozen-time/mounts/{mount_id}/runs/{run_id}/save-live-photo')
    @router.post('/runs/{run_id}/save-live-photo')
    async def save_live_photo(run_id: str, mount_id: str | None = None,
                             app_instance_id: str = Header(alias='X-AI2Apps-App-Instance'), principal=principal_dependency):
        # Only the authenticated native Shell may select the destination.
        if mount_id is not None:
            require_mount(mount_id,principal)
        repo=studio(principal,app_instance_id)
        try:
            run=repo.get_run(run_id,**scoped_kwargs(principal,app_instance_id))
        except StudioRepositoryError as error:
            return studio_error(error)
        if run['miniAppId']!=MINI_APP_ID or run['status']!='succeeded':
            raise HTTPException(404,'Completed Live Photo not found')
        source=runtime_provider().config.paths.artifacts_path/'imagine-frozen-time'/run_id
        if not all((source/name).is_file() for name in ('LivePhoto.jpg','LivePhoto.mov')):
            raise HTTPException(409,'Convert to Live Photo first')
        from ai2apps.native_export import native_export_broker
        try:
            identifier = native_export_broker.enqueue(source)
            return await asyncio.to_thread(native_export_broker.wait, identifier)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @router.post('/frozen-time/mounts/{mount_id}/runs', status_code=201)
    async def mounted_run(mount_id: str, app_instance_id: str = Header(alias='X-AI2Apps-App-Instance'), principal=principal_dependency):
        mounted = require_mount(mount_id,principal)
        return studio(principal, app_instance_id).create_run(mini_app_id=MINI_APP_ID,
            mini_app_version=mounted.declaration['version'], placement='ai2apps.imagine-studio',
            title='Frozen Time / 静止时间', input_data={}, **scoped_kwargs(principal, app_instance_id))

    @router.get("/frozen-time/models")
    async def models(app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"), principal=principal_dependency):
        studio(principal, app_instance_id)
        runtime = runtime_provider()
        model=runtime.model_invocations.model(MERIDIAN)
        counts=getattr(model,'metadata',{}).get('frame_counts',[73]) if model else [73]
        return {"depth": {key: ready(runtime, value, "depth_estimation") for key, value in DEPTH_MODELS.items()},
                "meridian": ready(runtime, MERIDIAN, "video_generation"), "livePhoto": exporter_path() is not None,
                "frameCounts": [n for n in FRAME_COUNTS if n in counts]}

    @router.get('/runs/{run_id}')
    async def run_status(run_id: str, app_instance_id: str = Header(alias='X-AI2Apps-App-Instance'), principal=principal_dependency):
        try:
            run = studio(principal, app_instance_id).get_run(run_id, **scoped_kwargs(principal, app_instance_id))
            if run['miniAppId'] != MINI_APP_ID:
                raise HTTPException(404, 'Frozen Time Run not found')
            return run
        except StudioRepositoryError as error:
            return studio_error(error)

    @router.get("/runs/{run_id}/frozen-content/{filename}")
    async def content(run_id: str, filename: str, app_instance_id: str = Query(alias="appInstanceId"),
                      download: bool = False, principal=principal_dependency):
        repo = studio(principal, app_instance_id)
        try:
            run = repo.get_run(run_id, **scoped_kwargs(principal, app_instance_id))
        except StudioRepositoryError as error:
            return studio_error(error)
        if run["miniAppId"] != MINI_APP_ID or run["status"] != "succeeded" or filename not in FILES:
            raise HTTPException(404, "Frozen Time output not found")
        path = runtime_provider().config.paths.artifacts_path / "imagine-frozen-time" / run["id"] / filename
        if not path.is_file():
            raise HTTPException(404, "Frozen Time output not found")
        return FileResponse(path, media_type=FILES[filename], filename=filename if download else None,
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
                     "Content-Security-Policy": "sandbox allow-scripts; default-src 'none'; media-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'"} if filename.endswith("html") else {"Cache-Control": "private, no-store"})

    @router.post("/runs/{run_id}/frozen-time", status_code=202)
    async def start(run_id: str, background_tasks: BackgroundTasks, image: UploadFile | None = File(None), audio: UploadFile | None = File(None),
                    depth: str = Form("vggt"), output: str = Form("live-photo"),
                    long_edge: int = Form(768), reference_speedup: bool = Form(True), seed: int = Form(-1, ge=-1, le=4294967295),
                    preview_id: str = Form(''), trajectory: str = Form(''),
                    app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"), principal=principal_dependency):
        runtime = runtime_provider()
        try:
            trajectory=parse_frame_plan(trajectory)
        except (ValueError,TypeError) as error:
            raise HTTPException(422,str(error)) from error
        repo = studio(principal, app_instance_id)
        scope = scoped_kwargs(principal, app_instance_id)
        try:
            run = repo.get_run(run_id, **scope)
        except StudioRepositoryError as error:
            return studio_error(error)
        if run["miniAppId"] != MINI_APP_ID or run["status"] != "queued":
            raise HTTPException(409, "Frozen Time Run is not queued")
        if depth not in DEPTH_MODELS or output not in {"html", "mp4", "live-photo"} or long_edge not in {512, 768}:
            raise HTTPException(422, "Invalid Frozen Time settings")
        if output == "live-photo" and exporter_path() is None:
            raise HTTPException(409, "Update Desktop to enable Live Photo export")
        if not ready(runtime, DEPTH_MODELS[depth], "depth_estimation") or not ready(runtime, MERIDIAN, "video_generation"):
            raise HTTPException(409, "Configure the required Frozen Time models first")
        model=runtime.model_invocations.model(MERIDIAN)
        if len(trajectory['frames']) not in getattr(model,'metadata',{}).get('frame_counts',[73]):
            raise HTTPException(409,'Update Meridian Package to enable this frame count')
        cached = None
        if preview_id:
            cached = previews.get(preview_id,scope)
            if cached['status'] != 'succeeded' or cached['settings'] != dict(depth=depth,output=output,long_edge=long_edge,trajectory=trajectory,reference_speedup=reference_speedup):
                raise HTTPException(409,'Preview is stale; preview the current settings first')
            data = (cached['directory']/'input.png').read_bytes()
        elif image is not None:
            data = await normalize_upload(image)
        else:
            raise HTTPException(422,'An image or completed preview is required')
        soundtrack_data = await normalize_soundtrack(audio, output)
        # The upload yielded: re-check before reserving to prevent duplicate runs.
        if repo.get_run(run_id, **scope)["status"] != "queued":
            raise HTTPException(409, "Run already started")
        if cached is not None:
            cached['status'] = 'rendering'
        requested_seed = seed
        seed = SystemRandom().randrange(4294967296) if seed == -1 else seed
        if getattr(runtime,'studio_jobs',None):
            from ai2apps.studio.extended_jobs import submit
            from dataclasses import asdict
            files={'input.png':data}
            prepared=None
            if soundtrack_data is not None:files['soundtrack.audio']=soundtrack_data
            if cached is not None:
                for name in ('model-input.png','reference.mp4'):files[name]=(cached['directory']/name).read_bytes()
                w,h,plan=cached['prepared'];prepared=[w,h,[asdict(frame) for frame in plan]]
            submit(runtime,principal,app_instance_id,'ai2apps.imagine-studio',MINI_APP_ID,'frozen-time',
                {'operation':'generate','settings':dict(depth=depth,output=output,long_edge=long_edge,reference_speedup=reference_speedup,trajectory=trajectory,seed=seed),
                 'prepared':prepared,'metadata':{'depthModel':DEPTH_MODELS[depth],'modelId':MERIDIAN,'output':output,'seed':seed,'requestedSeed':requested_seed}},files=files,run_id=run_id)
            if cached is not None:previews.discard(preview_id)
            return repo.get_run(run_id,**scope)
        repo.update_run(run_id, status="running", progress=0, detail=f"Preparing Frozen Time · Seed {seed}", **scope)
        active.add(run_id)
        context = ModelInvocationContext.from_principal(principal, session_id=f"imagine:{run_id}", app_instance_id=app_instance_id, consumer_app_id="ai2apps.imagine-studio")

        async def work():
            def cancelled():
                try:
                    return repo.get_run(run_id, **scope)["status"] != "running"
                except StudioRepositoryError:
                    return True
            def progress(value, detail):
                if not cancelled():
                    repo.update_run(run_id, status="running", progress=value, detail=detail, **scope)
            destination = runtime.config.paths.artifacts_path / "imagine-frozen-time" / run_id
            try:
                with tempfile.TemporaryDirectory(prefix="imagine-frozen-") as temporary:
                    directory = Path(temporary)
                    source = directory / "input.png"
                    source.write_bytes(data)
                    soundtrack = None
                    if soundtrack_data is not None:
                        soundtrack = directory / 'soundtrack.audio'
                        soundtrack.write_bytes(soundtrack_data)
                    extra = {}
                    if cached is not None:
                        for filename in ('model-input.png','reference.mp4'):
                            shutil.copyfile(cached['directory']/filename,directory/filename)
                        extra['prepared'] = cached['prepared']
                        previews.discard(preview_id)
                    artifacts = await generate(runtime, source, directory, depth=depth, output=output,
                        long_edge=long_edge, reference_speedup=reference_speedup, trajectory=trajectory, seed=seed, context=context, request_id=f"frozen-{run_id}", cancelled=cancelled, progress=progress, soundtrack=soundtrack, **extra)
                    if cancelled() or artifacts is None:
                        return
                    destination.mkdir(parents=True, exist_ok=True)
                    for filename in ["poster.jpg"] + [item[0] for item in artifacts] + [name for name in CACHE_FILES if (directory/name).is_file()]:
                        await asyncio.to_thread(shutil.copyfile, directory/filename, destination/filename)
                    if cancelled():
                        shutil.rmtree(destination)
                        return
                    base = f"/v1/platform/imagine-studio/runs/{quote(run_id, safe='')}/frozen-content/"
                    query = "?appInstanceId=" + quote(app_instance_id, safe="")
                    for filename, kind, media_type in artifacts:
                        preview = "output.mp4" if kind == "archive" else filename
                        repo.create_artifact(run_id, kind=kind, name=filename, media_type=media_type,
                            preview_url=base+preview+query, download_url=base+filename+query+"&download=true", source_id=run_id+":"+filename,
                            metadata={"miniAppId": MINI_APP_ID, "depthModel": DEPTH_MODELS[depth], "modelId": MERIDIAN,
                                      "posterUrl": base+"poster.jpg"+query, "output": output,
                                      "seed": seed, "requestedSeed": requested_seed}, **scope)
                    repo.update_run(run_id, status="succeeded", progress=100, detail=f"Completed · Seed {seed}", **scope)
            except Exception as error:
                if not cancelled():
                    with suppress(StudioRepositoryError):
                        repo.update_run(run_id, status="failed", progress=100, detail="Failed",
                            error={"code": "frozen_time_failed", "message": str(error)[:1000]}, **scope)
            finally:
                active.discard(run_id)
        background_tasks.add_task(work)
        return repo.get_run(run_id, **scope)
    @router.post('/frozen-time/mounts/{mount_id}/runs/{source_id}/convert',status_code=202)
    async def convert(mount_id: str, source_id: str, background_tasks: BackgroundTasks,
                      output: str=Form(), audio: UploadFile | None = File(None), app_instance_id: str=Header(alias='X-AI2Apps-App-Instance'),
                      principal=principal_dependency):
        mounted=require_mount(mount_id,principal)
        repo=studio(principal,app_instance_id)
        scope=scoped_kwargs(principal,app_instance_id)
        try:
            source_run=repo.get_run(source_id,**scope)
        except StudioRepositoryError as error:
            return studio_error(error)
        if source_run['miniAppId']!=MINI_APP_ID or source_run['status']!='succeeded':
            raise HTTPException(409,'Select a completed Frozen Time result')
        if output not in {'html','mp4','live-photo'}:
            raise HTTPException(422,'Invalid output format')
        soundtrack_data = await normalize_soundtrack(audio, output)
        runtime=runtime_provider()
        source_dir=runtime.config.paths.artifacts_path/'imagine-frozen-time'/source_id
        if not (source_dir/'output.mp4').is_file():
            raise HTTPException(404,'Source video is no longer available')
        original_output=next((a.get('metadata',{}).get('output') for a in source_run['artifacts'] if a.get('metadata',{}).get('output')), 'mp4')
        if not (source_dir/'conversion.json').is_file() and original_output=='html' and output!='html':
            raise HTTPException(409,'Older HTML result has no saved camera path for returning to center')
        result=repo.create_run(mini_app_id=MINI_APP_ID,mini_app_version=mounted.declaration['version'],
            placement='ai2apps.imagine-studio',title='Convert Frozen Time / 静止时间转存',
            input_data={'sourceRunId':source_id,'output':output},**scope)
        run_id=result['id']
        if getattr(runtime,'studio_jobs',None):
            from ai2apps.studio.extended_jobs import submit
            files={name:(source_dir/name).read_bytes() for name in set(CACHE_FILES+tuple(FILES)) if (source_dir/name).is_file()}
            if soundtrack_data is not None:files['soundtrack.audio']=soundtrack_data
            submit(runtime,principal,app_instance_id,'ai2apps.imagine-studio',MINI_APP_ID,'frozen-time',
                {'operation':'convert','output':output,'original_output':original_output,'metadata':{'sourceRunId':source_id,'output':output}},files=files,run_id=run_id)
            return repo.get_run(run_id,**scope)
        repo.update_run(run_id,status='running',progress=5,detail='Converting locally / 本地转存',**scope)
        active.add(run_id)
        async def work():
            def cancelled():
                try:
                    return repo.get_run(run_id,**scope)['status']!='running'
                except StudioRepositoryError:
                    return True
            destination=runtime.config.paths.artifacts_path/'imagine-frozen-time'/run_id
            try:
                with tempfile.TemporaryDirectory(prefix='frozen-convert-') as temporary:
                    directory=Path(temporary)
                    soundtrack=None
                    if soundtrack_data is not None:
                        soundtrack=directory/'soundtrack.audio'
                        soundtrack.write_bytes(soundtrack_data)
                    extra={'soundtrack':soundtrack} if soundtrack is not None else {}
                    artifacts=await convert_saved(source_dir,directory,output,original_output,cancelled,**extra)
                    if cancelled() or artifacts is None:
                        return
                    destination.mkdir(parents=True,exist_ok=True)
                    for name in ['poster.jpg']+[a[0] for a in artifacts]+[n for n in CACHE_FILES if (directory/n).is_file()]:
                        await asyncio.to_thread(shutil.copyfile,directory/name,destination/name)
                    if cancelled():
                        shutil.rmtree(destination)
                        return
                    base=f'/v1/platform/imagine-studio/runs/{quote(run_id,safe="")}/frozen-content/'
                    query='?appInstanceId='+quote(app_instance_id,safe='')
                    for name,kind,media in artifacts:
                        repo.create_artifact(run_id,kind=kind,name=name,media_type=media,
                            preview_url=base+('output.mp4' if kind=='archive' else name)+query,
                            download_url=base+name+query+'&download=true',source_id=run_id+':'+name,
                            metadata={'miniAppId':MINI_APP_ID,'sourceRunId':source_id,'output':output,'posterUrl':base+'poster.jpg'+query},**scope)
                    repo.update_run(run_id,status='succeeded',progress=100,detail='Converted / 转存完成',**scope)
            except Exception as error:
                if not cancelled():
                    repo.update_run(run_id,status='failed',progress=100,detail='Conversion failed',
                        error={'code':'frozen_conversion_failed','message':str(error)[:1000]},**scope)
            finally:
                active.discard(run_id)
        background_tasks.add_task(work)
        return repo.get_run(run_id,**scope)
    return router, active
