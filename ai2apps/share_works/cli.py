"""Fixed CLI grammar. Credentials are consumed only by the user's CLI process."""
import asyncio
import json
import os
import re
import shutil
import signal
from pathlib import Path


class PublishError(ValueError):
    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(code + (': ' + detail if detail else ''))


IDENTITY = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$')
REPO = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$')


class CLI:
    def __init__(self, provider, *, search_path=None):
        if provider not in ('hf','ms'): raise PublishError('invalid_provider')
        self.provider = provider
        if search_path is None:
            from ai2apps.coder.environment import cli_search_path
            search_path = cli_search_path(Path.home()/'.local')
            # The fixed development checkout has an existing Terminal tool
            # environment. Discover that one known environment, never scan
            # arbitrary projects or import its SDK into the App runtime.
            checkout=Path(__file__).resolve().parents[2]
            known=[Path.home()/'.local/bin']
            if os.environ.get('VIRTUAL_ENV') and Path(os.environ['VIRTUAL_ENV']).is_absolute():
                known.append(Path(os.environ['VIRTUAL_ENV'])/'bin')
            if (checkout/'.git').exists():known.append(checkout/'.venv/bin')
            search_path=os.pathsep.join([search_path,*map(str,known)])
        names = ('hf',) if provider == 'hf' else ('ms-hub','ms','modelscope-hub')
        self.exe = next((shutil.which(n, path=search_path) for n in names if shutil.which(n, path=search_path)), None)
        if not self.exe: raise PublishError('cli_missing', 'hf' if provider=='hf' else 'ms-hub')
        self.exe = str(Path(self.exe).resolve())
        self.env = {k:v for k,v in os.environ.items() if k in {
            'HOME','USER','LOGNAME','SHELL','TMPDIR','LANG','LC_ALL','HF_HOME','HF_TOKEN_PATH',
            'MODELSCOPE_HOME','MODELSCOPE_CACHE','XDG_CACHE_HOME','XDG_CONFIG_HOME',
            'SSL_CERT_FILE','REQUESTS_CA_BUNDLE','HTTPS_PROXY','HTTP_PROXY','NO_PROXY'}}
        from .environment import external_environment
        self.env=external_environment(self.env)
        self.env.update(PATH=search_path, NO_COLOR='1', TERM='dumb', CI='1', HF_HUB_DISABLE_PROGRESS_BARS='1')

    async def run(self, args, *, timeout=30, cwd=None):
        # All args originate in this module; no shell, token or interactive input.
        proc = await asyncio.create_subprocess_exec(self.exe,*args,stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
            env=self.env,cwd=cwd or str(Path.home()),start_new_session=True)
        async def bounded(stream):
            data=bytearray()
            while True:
                chunk=await stream.read(8192)
                if not chunk: break
                data.extend(chunk)
                if len(data)>256*1024: raise PublishError('cli_output_limit')
            return data.decode('utf-8',errors='replace')
        try:
            out,err=await asyncio.wait_for(asyncio.gather(bounded(proc.stdout),bounded(proc.stderr)),timeout)
            await asyncio.wait_for(proc.wait(),5)
        except BaseException:
            if proc.returncode is None:
                try: os.killpg(proc.pid,signal.SIGTERM)
                except ProcessLookupError: pass
                try: await asyncio.wait_for(proc.wait(),2)
                except asyncio.TimeoutError:
                    try: os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                    await proc.wait()
            raise
        if proc.returncode:
            raw=(out+'\n'+err).lower()
            code='cli_failed'
            if any(x in raw for x in ['not logged','not authenticated','invalid token','401','token expired']): code='cli_not_logged_in'
            elif any(x in raw for x in ['permission denied','403','forbidden']): code='cli_permission_denied'
            elif any(x in raw for x in ['unrecognized arguments','invalid choice','no such command']): code='cli_incompatible'
            elif '404' in raw or 'not found' in raw: code='space_not_found'
            # Never expose raw stderr: CLI errors can contain tokens/headers.
            raise PublishError(code)
        return out

    async def account(self):
        args=['auth','whoami'] if self.provider=='hf' else ['whoami']
        text=await self.run(args)
        if 'not logged in' in text.lower():raise PublishError('cli_not_logged_in')
        try:
            value=json.loads(text)
            name=value.get('name') or value.get('username') or value.get('user_name')
        except (ValueError,AttributeError):
            lines=[line.strip() for line in text.splitlines() if line.strip()]
            name=next((m.group(1) for line in lines if (m:=re.fullmatch(r'(?:username|user|name)\s*:\s*([\w.-]+)',line,re.I))),None)
            if name is None and lines and IDENTITY.fullmatch(lines[0]): name=lines[0]
        if not isinstance(name,str) or not IDENTITY.fullmatch(name): raise PublishError('cli_identity_unrecognized')
        return name

    async def inspect(self, repo):
        if not REPO.fullmatch(repo): raise PublishError('invalid_space_id')
        account=await self.account()
        if repo.split('/')[0]!=account: raise PublishError('space_account_mismatch')
        if self.provider=='hf':
            raw=await self.run(['spaces','info',repo,'--format','json'])
            try: info=json.loads(raw)
            except ValueError: raise PublishError('cli_incompatible')
            sdk=info.get('sdk') or (info.get('cardData') or info.get('card_data') or {}).get('sdk')
            if sdk!='static' or info.get('private') is not False: raise PublishError('space_must_be_public_static')
        else:
            help_text=await self.run(['upload','--help'])
            if not re.search(r'--repo-type[^\n]*studio',help_text):
                raise PublishError('cli_studio_upload_unsupported')
            raw=await self.run(['studio','list','--owner',account,'--status','all','--page-size','50'])
            # Exact row, no fuzzy matching or guessing another account.
            rows=[line for line in raw.splitlines() if repo in line.split() or repo in [s.strip() for s in line.split('|')]]
            if len(rows)!=1 or not re.search(r'\bstatic\b',rows[0]) or not re.search(r'\b(public)\b',rows[0]):
                raise PublishError('space_must_be_public_static')
        return {'provider':self.provider,'account':account,'repo':repo,**({'application_url':info.get('host')} if self.provider=='hf' and info.get('host') else {})}

    async def upload(self, repo, directory, remote_path, request_id):
        if not REPO.fullmatch(repo) or not re.fullmatch(r'shares/[0-9a-f]{32}',remote_path):raise PublishError('invalid_upload_target')
        args=['upload',repo,str(directory),remote_path,'--repo-type','space' if self.provider=='hf' else 'studio',
              '--commit-message','AI2Apps snapshot '+request_id]
        return await self.run(args,timeout=600,cwd=str(directory))

    async def deploy(self, repo):
        if self.provider=='ms': return await self.run(['studio','deploy',repo],timeout=120)
        return ''  # HF static Space deploys from the committed files.
