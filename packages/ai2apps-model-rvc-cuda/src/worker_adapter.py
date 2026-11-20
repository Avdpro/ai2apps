"""RVC CUDA service adapter: serialized conversion/training and request cancellation."""
import asyncio,gc,hashlib,inspect,json,math,threading,zipfile,stat,tempfile
from pathlib import Path
from ai2apps.model_worker import ModelWorkerArtifact,ModelWorkerError
MODEL_ID='ai2apps.model.rvc-cuda/serena-e70'
CHECKPOINT=('Avdpro/MLX-RVC-Serena-E70','738acad9f58c074d9f817eeac8c7dac9e2eafa1f')

def invalid(message,code='invalid_request',status=400):
    raise ModelWorkerError(message,code=code,status_code=status)

def number(payload,key,default,kind=float):
    value=payload.get(key,default)
    if isinstance(value,bool):invalid(key+' must be numeric')
    try:
        result=float(value)
        if not math.isfinite(result) or (kind is int and result!=int(result)):raise ValueError()
        return kind(result)
    except (TypeError,ValueError,OverflowError):invalid('invalid '+key)

MAX_VOICE_BUNDLE_BYTES = 512 * 1024**2

def extract_voice_bundle(source, destination, check):
    if Path(source).stat().st_size > MAX_VOICE_BUNDLE_BYTES:
        raise ValueError('trained voice ZIP exceeds size limit')
    required = {'model.json', 'index.json', 'model.safetensors', 'index.safetensors'}
    allowed = required | {'training-report.json'}
    with zipfile.ZipFile(source) as archive:
        members = archive.infolist()
        names = [item.filename for item in members]
        if len(names) != len(set(names)) or not required <= set(names) <= allowed:
            raise ValueError('invalid trained voice bundle files')
        if sum(item.file_size for item in members) > MAX_VOICE_BUNDLE_BYTES:
            raise ValueError('trained voice bundle exceeds expanded size limit')
        for item in members:
            kind = stat.S_IFMT(item.external_attr >> 16)
            if item.is_dir() or kind not in (0, stat.S_IFREG) or item.flag_bits & 1:
                raise ValueError('unsupported trained voice bundle entry')
            if item.filename.endswith('.json') and item.file_size > 1024**2:
                raise ValueError('trained voice manifest too large')
        destination.mkdir(exist_ok=False)
        total = 0
        for item in members:
            check()
            with archive.open(item) as reader, (destination/item.filename).open('xb') as writer:
                while data := reader.read(1024**2):
                    check(); total += len(data)
                    if total > MAX_VOICE_BUNDLE_BYTES:
                        raise ValueError('trained voice bundle exceeds expanded size limit')
                    writer.write(data)
    return destination

class CudaRVCAdapter:
    def __init__(self,context):
        self.context=context;self.lock=asyncio.Lock();self.events={};self.pipeline=None;self.path=None;self.stopped=False

    async def start(self):self.stopped=False

    def cancel(self,request_id):
        if request_id in self.events:self.events[request_id].set()

    async def stop(self):
        self.stopped=True
        for event in self.events.values():event.set()
        async with self.lock:
            self.pipeline=None;self.path=None
            gc.collect()
            import torch
            torch.cuda.empty_cache()

    async def invoke(self,request):
        if self.stopped:invalid('RVC Worker stopped','model_unavailable',503)
        if request.request_id in self.events:invalid('Duplicate active request id','request_conflict',409)
        if request.operation not in ('audio_process','audio_voice_training'):invalid('Unsupported operation','operation_not_supported')
        payload=dict(request.payload)
        if payload.get('model') not in {MODEL_ID,CHECKPOINT[0]}:invalid('Unsupported RVC model','model_not_found',404)
        checkpoint=self.context.checkpoint_for(MODEL_ID)
        if checkpoint is None or checkpoint.path is None:invalid('Checkpoint not installed','model_unavailable',503)
        if (checkpoint.repo_id,checkpoint.revision)!=CHECKPOINT:invalid('Unsupported checkpoint','model_not_supported')
        if request.output_root is None:invalid('Controlled output root required','runtime_protocol_error')
        output=Path(request.output_root);output.mkdir(parents=True,exist_ok=True)
        if request.operation=='audio_process':
            if payload.get('task','voice_conversion')!='voice_conversion':invalid('Unsupported audio task')
            from cuda_rvc_pipeline import ConversionOptions
            options=ConversionOptions(speaker_id=number(payload,'speaker_id',0,int),semitones=number(payload,'semitones',0),retrieval_rate=number(payload,'retrieval_rate',.75),protect=number(payload,'protect',.33),seed=number(payload,'seed',0,int))
            try:options.validate()
            except ValueError as exc:invalid(str(exc))
            source=request.part('file').path
        else:
            from cuda_rvc_trainer import TrainingConfig
            config=TrainingConfig(epochs=number(payload,'epochs',30,int),batch_size=number(payload,'batch_size',4,int),precision=str(payload.get('precision') or 'float16'))
            try:config.validate()
            except ValueError as exc:invalid(str(exc))
            source=request.part('dataset').path
        voice_part = (getattr(request, 'parts', None) or {}).get('voice')
        if voice_part is not None and request.operation != 'audio_process':
            invalid('voice bundle is only valid for conversion')
        event=threading.Event();self.events[request.request_id]=event
        loop=asyncio.get_running_loop()
        def check():
            if event.is_set() or self.stopped:raise InterruptedError('RVC request cancelled')
        async def report_async(value):
            if request.progress:
                result=request.progress(value)
                if inspect.isawaitable(result):await result
        def report(value):
            check();asyncio.run_coroutine_threadsafe(report_async(value),loop).result()
        def run_impl():
            import numpy as np
            import soundfile as sf
            import cuda_rvc_pipeline as implementation
            check()
            if self.pipeline is None or self.path!=checkpoint.path:
                self.pipeline=implementation.CudaRVCPipeline(checkpoint.path,Path(implementation.__file__).with_name('cuda_rvc_weights.lock.json'))
                self.path=checkpoint.path
            check()
            if request.operation=='audio_process':
                if voice_part is not None:
                    with tempfile.TemporaryDirectory(prefix='rvc-voice-', dir=output) as folder:
                        voice_root = extract_voice_bundle(voice_part.path, Path(folder)/'voice', check)
                        check()
                        try:
                            self.pipeline.load_trained_voice(voice_root)
                        except (KeyError, TypeError) as exc:
                            raise ValueError('invalid trained voice manifest') from exc
                        check()
                audio,rate=sf.read(source,dtype='float32')
                if audio.ndim==2:audio=audio.mean(axis=1)
                if rate!=16000:
                    from scipy.signal import resample_poly
                    divisor=math.gcd(rate,16000);audio=resample_poly(audio,16000//divisor,rate//divisor).astype(np.float32)
                wave=self.pipeline.convert_long_16khz(audio,options=options,check=check)
                target=output/'rvc-output.wav'
                try:
                    with target.open('xb') as stream:sf.write(stream,wave,48000,format='WAV',subtype='PCM_16')
                    check()
                except FileExistsError:raise
                except BaseException:
                    target.unlink(missing_ok=True);raise
                return ModelWorkerArtifact(target,'audio/wav',target.name,{'sample_rate':48000,'samples':len(wave)})
            from cuda_rvc_preprocess import prepare
            from cuda_rvc_trainer import CudaRVCTrainer
            from cuda_rvc_voice_export import export_voice
            from safetensors.torch import load_file
            dataset=output/'dataset';dataset.mkdir()
            files=[];total=0
            with zipfile.ZipFile(source) as archive:
                members=[m for m in archive.infolist() if not m.is_dir()]
                if not 1<=len(members)<=500:raise ValueError('dataset ZIP must contain 1 to 500 WAV files')
                for index,member in enumerate(members):
                    check()
                    if Path(member.filename).suffix.lower()!='.wav':raise ValueError('dataset ZIP may contain WAV files only')
                    if total+member.file_size>2*1024**3:raise ValueError('expanded dataset too large')
                    target=dataset/f'{index:05d}.wav'
                    with archive.open(member) as reader,target.open('xb') as writer:
                        while data:=reader.read(1024*1024):
                            check();total+=len(data)
                            if total>2*1024**3:raise ValueError('expanded dataset too large')
                            writer.write(data)
                    files.append(target)
            cache=output/'cache';prepare(self.pipeline,files,cache,progress=report,check=check)
            lock=json.loads(Path(implementation.__file__).with_name('cuda_rvc_weights.lock.json').read_text())
            hashes={item['name']:item['sha256'] for item in lock['files']};states=[]
            for name in ('training/generator.safetensors','training/discriminator.safetensors'):
                path=Path(checkpoint.path)/name
                with path.open('rb') as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=hashes[name]:raise ValueError('training checkpoint digest mismatch')
                states.append(load_file(str(path)))
            training=output/'training'
            CudaRVCTrainer(*states).fit(cache,training,config,progress=report,check=check)
            check();voice=output/'voice'
            metadata=export_voice(training/f'epoch-{config.epochs:04d}',cache,voice)
            check();target=output/'rvc-voice.zip'
            try:
                with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_STORED) as archive:
                    for path in sorted(voice.iterdir()):
                        check();archive.write(path,path.name)
                    archive.write(training/'training-report.json','training-report.json')
                check()
            except FileExistsError:raise
            except BaseException:
                target.unlink(missing_ok=True);raise
            return ModelWorkerArtifact(target,'application/zip',target.name,metadata)
        def run():
            try:
                return run_impl()
            finally:
                if voice_part is not None:
                    # Uploaded voice state must never survive into the next request.
                    self.pipeline = None; self.path = None
                    gc.collect()
                    import torch
                    torch.cuda.empty_cache()
        try:
            async with self.lock:
                check()
                task=asyncio.create_task(asyncio.to_thread(run))
                try:return await asyncio.shield(task)
                except asyncio.CancelledError:
                    event.set()
                    while not task.done():
                        try:await asyncio.shield(task)
                        except asyncio.CancelledError:continue
                        except Exception:break
                    if not task.cancelled():task.exception()
                    raise
        except InterruptedError as exc:invalid(str(exc),'request_cancelled',499)
        except (ValueError,OSError,zipfile.BadZipFile) as exc:invalid(str(exc),'audio_processing_failed',422)
        finally:self.events.pop(request.request_id,None)

def create_adapter(context):return CudaRVCAdapter(context)
