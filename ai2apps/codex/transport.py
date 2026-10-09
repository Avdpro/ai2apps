"""Local Codex App Server transport; never reads Desktop private databases."""
import asyncio
import json
import os
import shutil
from pathlib import Path


class CodexDesktop:
    @staticmethod
    def executable():
        candidates = [Path('/Applications/Codex.app/Contents/Resources/codex'),
                      Path('/Applications/ChatGPT.app/Contents/Resources/codex'),
                      Path.home()/'.local/bin/codex', Path('/usr/local/bin/codex')]
        return next((str(p) for p in candidates if p.is_file() and os.access(p, os.X_OK)), shutil.which('codex'))

    @staticmethod
    def environment():
        env = {k:v for k,v in os.environ.items() if not k.startswith(('AI2APPS_', 'OMLX_')) and k not in ('PYTHONPATH','PYTHONHOME','CODEX_THREAD_ID','CODEX_TURN_ID')}
        env['PATH'] = os.pathsep.join([str(Path.home()/'.local/bin'), '/opt/homebrew/bin', '/usr/local/bin', env.get('PATH','/usr/bin:/bin')])
        return env

    def __init__(self):
        self.proc = None
        self.pending = {}
        self.events = asyncio.Queue(maxsize=2048)
        self.serial = 0
        self.reader = None

    async def __aenter__(self):
        binary = self.executable()
        if not binary:
            raise ValueError('Install Codex CLI or Desktop first')
        env = self.environment()
        self.proc = await asyncio.create_subprocess_exec(binary, 'app-server', '--listen', 'stdio://',
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            env=env, limit=8*1024*1024)
        self.reader = asyncio.create_task(self._read())
        try:
            await self.call('initialize', {'clientInfo':{'name':'ai2apps','version':'0.2.0'}, 'capabilities':{'experimentalApi':True}})
            await self.send({'method':'initialized','params':{}})
        except BaseException:
            await self.__aexit__(None,None,None)
            raise
        return self

    async def _read(self):
        try:
            while raw := await self.proc.stdout.readline():
                msg = json.loads(raw)
                if 'method' not in msg:
                    future = self.pending.get(msg.get('id'))
                    if future is not None and not future.done(): future.set_result(msg)
                else:
                    self.events.put_nowait(msg)
        except (ValueError, asyncio.QueueFull):
            pass
        finally:
            for future in self.pending.values():
                if not future.done(): future.set_exception(ValueError('Codex connection closed'))
            if not self.events.full(): self.events.put_nowait({'method':'connection/closed'})

    async def send(self, message):
        self.proc.stdin.write((json.dumps(message)+'\n').encode())
        await self.proc.stdin.drain()

    async def call(self, method, params, timeout=30):
        self.serial += 1
        id = self.serial
        future = asyncio.get_running_loop().create_future()
        self.pending[id] = future
        try:
            await self.send({'id':id,'method':method,'params':params})
            message = await asyncio.wait_for(future, timeout)
            if 'error' in message: raise ValueError(message['error'].get('message','Codex request failed'))
            return message.get('result',{})
        finally:
            self.pending.pop(id,None)

    async def __aexit__(self, *_):
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try: await asyncio.wait_for(self.proc.wait(),5)
            except TimeoutError:
                self.proc.kill()
                await self.proc.wait()
        if self.reader:
            self.reader.cancel()
            await asyncio.gather(self.reader, return_exceptions=True)

    async def threads(self, cwd=None, cursor=None):
        params={'limit':50,'sortKey':'updated_at','sortDirection':'desc','useStateDbOnly':True,'sourceKinds':['cli','vscode','appServer']}
        if cwd: params['cwd']=cwd
        if cursor: params['cursor']=cursor
        page=await self.call('thread/list',params)
        return {'data':[{k:t.get(k) for k in ('id','name','cwd','updatedAt')} for t in page.get('data',[])], 'nextCursor':page.get('nextCursor')}
