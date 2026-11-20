"""ModelScope official SDK in the user's existing signed-in CLI environment."""
import json
from pathlib import Path
from .cli import CLI,PublishError


class ModelScope:
    def __init__(self):
        source=CLI('ms')
        python=next((p for name in ('python3','python') if (p:=Path(source.exe).parent/name).is_file()),None)
        if python is None:raise PublishError('ms_sdk_environment_missing')
        # CLI.run supplies bounded pipes, timeout and process-group cancellation.
        # The selected interpreter is beside the known installed CLI; no SDK is
        # imported from that environment into Local or installed automatically.
        self.runner=source;self.runner.exe=str(python)
        self.worker=str(Path(__file__).with_name('ms_worker.py'))

    async def request(self,action,body,timeout=30):
        raw=await self.runner.run([self.worker,action,json.dumps(body)],timeout=timeout)
        try:result=json.loads(raw)
        except ValueError:raise PublishError('ms_sdk_invalid_reply')
        if result.get('error'):raise PublishError(result['error'])
        if not isinstance(result.get('value'),dict):raise PublishError('ms_sdk_invalid_reply')
        return result['value']

    async def inspect(self,repo):return await self.request('inspect',{'repo':repo})
    async def account(self):return (await self.request('account',{}))['account']
    async def upload(self,repo,directory,remote_path,request_id):
        manifest_path=directory.parent/(directory.name+'.manifest.json')
        return await self.request('upload',{'repo':repo,'directory':str(directory),'remote_path':remote_path,'request_id':request_id,'manifest_path':str(manifest_path)},600)
    async def deploy(self,repo):return await self.request('deploy',{'repo':repo},120)
