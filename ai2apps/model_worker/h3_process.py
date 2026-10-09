# SPDX-License-Identifier: Apache-2.0
"""Private Comfy child lifecycle for a single sandboxed H3 Worker.

The caller supplies paths from the trusted Runtime, never a Package command or
remote endpoint. Each Worker must have its own network namespace and queue.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import signal
import socket
import tempfile

import httpx

from .protocol import ModelWorkerError


class H3Process:
    def __init__(self, runtime: Path, checkpoint: Path, data_root: Path, *, lora_checkpoint: Path | None = None):
        self.runtime = runtime.resolve(strict=True)
        self.checkpoint = checkpoint.resolve(strict=True)
        # Optional overlay location comes from a Host-resolved checkpoint, never
        # from an inference request or a remote URL.
        self.lora_checkpoint = None
        if lora_checkpoint is not None:
            overlay = lora_checkpoint.resolve(strict=True)
            if not overlay.is_dir():
                raise ValueError('H3 LoRA checkpoint must be a directory')
            self.lora_checkpoint = overlay
        self.root = Path(tempfile.mkdtemp(prefix='h3-worker-', dir=data_root))
        self.process = None
        self.client = None
        self.log = None
        self.lock = asyncio.Lock()

    def trusted_file(self, relative):
        path = (self.runtime / relative).resolve(strict=True)
        if not path.is_relative_to(self.runtime) or not path.is_file():
            raise RuntimeError('H3 executable/source escapes trusted Runtime')
        return path

    async def start(self):
        if self.process is not None:
            if self.process.returncode is None:
                return
            await self.stop()
        python = self.trusted_file('Python/bin/python3.12')
        main = self.trusted_file('h3/ComfyUI/main.py')
        for name in ('input', 'output', 'temp', 'user'):
            (self.root/name).mkdir(exist_ok=True)
        paths = self.root/'model-paths.json'
        model_paths = {'h3': {'base_path': str(self.checkpoint),
            'diffusion_models': 'diffusion_models', 'text_encoders': 'text_encoders', 'vae': 'vae'}}
        if self.lora_checkpoint is not None:
            model_paths['h3_lora'] = {'base_path': str(self.lora_checkpoint), 'loras': 'loras'}
        paths.write_text(json.dumps(model_paths))
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1',0))
            port=reservation.getsockname()[1]
        # -I excludes cwd and PYTHONPATH. Only Runtime-owned source and the
        # exported H3 dependency closure are admitted explicitly.
        profile=(self.runtime/'profiles/h3/site-packages').resolve(strict=True)
        if not profile.is_relative_to(self.runtime) or not profile.is_dir():
            raise RuntimeError('H3 dependency profile escapes trusted Runtime')
        bootstrap=('import sys,runpy; from pathlib import Path; '
            'profile=sys.argv.pop(1); core=sys.argv.pop(1); sys.argv=sys.argv[1:]; '
            'sys.path.insert(0,str(Path(sys.argv[0]).parent)); '
            'sys.path.extend((core,profile)); runpy.run_path(sys.argv[0],run_name="__main__")')
        core=(self.runtime/'Python/lib/python3.12/site-packages').resolve(strict=True)
        if not core.is_relative_to(self.runtime) or not core.is_dir():
            raise RuntimeError('H3 core framework escapes trusted Runtime')
        command=[str(python),'-I','-c',bootstrap,str(profile),str(core),str(main),'--listen','127.0.0.1','--port',str(port),
            '--disable-auto-launch','--disable-all-custom-nodes','--disable-api-nodes',
            '--preview-method','none','--use-pytorch-cross-attention',
            '--extra-model-paths-config',str(paths)]
        for name in ('input','output','temp','user'):
            command.extend((f'--{name}-directory',str(self.root/name)))
        self.log=(self.root/'comfy.log').open('ab')
        include=self.runtime/'h3/build-include'
        env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
            'CPATH':os.pathsep.join(str(include/p) for p in ('python3.12','aarch64-linux-gnu','.'))}
        env['CC']=str(self.trusted_file('h3/toolchain/bin/cc'))
        self.client=httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}',timeout=10,trust_env=False)
        try:
            self.process=await asyncio.create_subprocess_exec(*command,env=env,
                stdout=self.log,stderr=self.log,start_new_session=True)
            async with asyncio.timeout(90):
                while True:
                    self.check_alive()
                    try:
                        response=await self.client.get('/system_stats')
                        response.raise_for_status()
                        response.json()
                        break
                    except (httpx.HTTPError,ValueError):
                        await asyncio.sleep(.2)
        except BaseException:
            await self.stop()
            raise

    def check_alive(self):
        if self.process is None or self.process.returncode is not None:
            raise ModelWorkerError('Private H3 process exited; inspect Worker log',
                code='model_process_exited',status_code=503)

    async def stop(self):
        process,self.process=self.process,None
        if process is not None and process.returncode is None:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:
                await asyncio.wait_for(process.wait(),20)
            except TimeoutError:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                await process.wait()
        if self.client is not None:
            await self.client.aclose()
            self.client=None
        if self.log is not None:
            self.log.close()
            self.log=None

    async def interrupt_and_wait(self, prompt_id):
        """Do not release the request lock until the child acknowledges idle."""
        try:
            self.check_alive()
            response=await self.client.post('/interrupt',json={})
            response.raise_for_status()  # A successful interrupt has no JSON body.
            async with asyncio.timeout(30):
                while True:
                    self.check_alive()
                    response=await self.client.get('/queue')
                    response.raise_for_status()
                    queue=response.json()
                    pending=queue.get('queue_running',[])+queue.get('queue_pending',[])
                    if not any(entry[1]==prompt_id for entry in pending):
                        return
                    await asyncio.sleep(.1)
        except BaseException:
            # A hung child must not retain GPU work when the next request starts.
            await self.stop()
            raise

    async def run(self, graph, cancelled: asyncio.Event, timeout=1800):
        async with self.lock:
            if cancelled.is_set():
                raise ModelWorkerError('Video request cancelled',code='request_cancelled',status_code=499)
            await self.start()
            prompt_id=None
            try:
                response=await self.client.post('/prompt',json={'prompt':graph})
                response.raise_for_status()
                prompt_id=response.json()['prompt_id']
                async with asyncio.timeout(timeout):
                    while True:
                        self.check_alive()
                        if cancelled.is_set():
                            raise asyncio.CancelledError
                        response=await self.client.get('/history/'+prompt_id)
                        response.raise_for_status()
                        history=response.json().get(prompt_id)
                        if history:
                            status=history.get('status',{}).get('status_str')
                            if status=='success':
                                return history['outputs']
                            if status=='error':
                                raise ModelWorkerError('H3 generation failed; inspect Worker log',code='generation_failed',status_code=500)
                        await asyncio.sleep(.2)
            except (asyncio.CancelledError,TimeoutError):
                cleanup=asyncio.create_task(self.interrupt_and_wait(prompt_id) if prompt_id else self.stop())
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    await cleanup
                raise
            except BaseException:
                # An HTTP failure may hide a successfully submitted request.
                # Reset our private process rather than leave unknown GPU work.
                await self.stop()
                raise

    def output_path(self, filename, subfolder=''):
        root=(self.root/'output').resolve(strict=True)
        path=(root/subfolder/filename).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower()!='.mp4':
            raise ModelWorkerError('Invalid H3 output path',code='invalid_artifact',status_code=500)
        return path
