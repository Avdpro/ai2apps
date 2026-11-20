"""One owner service for Desktop/Mobile, backed by existing System Tasks."""
import asyncio
import hashlib
import io
import ssl
import socket
import json
import re
import threading
import time
import uuid
from urllib.parse import urlsplit, urljoin, quote
from PIL import Image
from .artifacts import normalize, MAX_INPUT
from .cli import CLI, PublishError, REPO
from .store import Store

HOST='ai2apps.ai-browser'
MINI='ai2apps.share-works'
KIND='share-works.publish'


class ShareWorks:
    def __init__(self,runtime):
        self.runtime=runtime
        self.store=Store(runtime.config.paths.artifacts_path/'share-works')
        self.lock=threading.RLock()
        from .ms_adapter import ModelScope
        self.cli_factory=lambda provider: ModelScope() if provider=='ms' else CLI(provider)
        import logging
        logging.getLogger(__name__).info('Share Works social publishing loaded from %s', __file__)

    def authorize(self,owner):
        # Terminal credentials belong to the installation's OS owner. A family
        # member's App access does not grant use of that account's CLI secrets.
        if self.runtime.legacy_api_key_principal().actor_user_id!=owner:
            raise PermissionError('Desktop owner required for Terminal CLI access')

    async def check(self,owner,provider,repo):
        self.authorize(owner)
        client=self.cli_factory(provider)
        if not repo:return {'provider':provider,'account':await client.account(),'repo':''}
        result=await client.inspect(repo)
        previous=self.preferences(owner)['targets'].get(provider,{})
        candidate=result.get('application_url') or (previous.get('application_url') if previous.get('repo')==repo else '')
        if candidate:result['application_url']=self.base_url(provider,candidate)
        self.store.save('preferences',owner,provider,{'provider':provider,'repo':repo,'application_url':result.get('application_url',''),'updated_at':time.time()})
        return result

    def preferences(self,owner):
        self.authorize(owner)
        targets={}
        for provider in ('hf','ms'):
            try:value=self.store.get('preferences',owner,provider)
            except KeyError:value={}
            if not value.get('application_url'):
                old=self.store.latest_target(owner,provider)
                if old and (not value or value.get('repo')==old.get('repo')):value={**old,**value,'application_url':old['application_url']}
            if value:targets[provider]={k:value.get(k,'') for k in ('provider','repo','application_url')}
        return {'targets':targets}


    @staticmethod
    def base_url(provider, value):
        u=urlsplit(value)
        suffix='.hf.space' if provider=='hf' else '.ms.show'
        if (u.scheme!='https' or not u.hostname or not u.hostname.endswith(suffix)
            or u.username or u.password or u.port or u.query or u.fragment or u.path not in ('','/')):
            raise PublishError('invalid_application_url','Use the direct HTTPS static application URL')
        return value.rstrip('/')+'/'

    async def export_input(self,owner,export_id):
        self.authorize(owner)
        from ai2apps.intelligence.export_jobs import file_path
        task=self.runtime.system_tasks.get(owner,export_id)
        if task['app_id']!='ai2apps.intelligence' or task['kind']!='intelligence.export' or task['status']!='completed' or task['result'].get('format')!='html':raise KeyError('export_not_available')
        path=file_path(self.runtime.intelligence_collector.store,owner,export_id,'html')
        data=await asyncio.to_thread(path.read_bytes)
        if len(data)>MAX_INPUT or hashlib.sha256(data).hexdigest()!=task['result']['sha256']:raise ValueError('export_not_available')
        return data,'intelligence.html'

    async def prepare(self,owner,data,filename,title,provider,repo,application_url):
        self.authorize(owner)
        account=await self.check(owner,provider,repo)
        base=self.base_url(provider,application_url)
        id=uuid.uuid4().hex
        files,manifest,digest=await asyncio.to_thread(normalize,data,filename,id,public_base=base)
        if provider=='ms' and any(len(content)>16*1024*1024 for content in files.values()):raise PublishError('ms_inline_file_limit')
        folder=self.store.path(owner,id);folder.mkdir(parents=True,mode=0o700)
        for name,content in files.items():
            path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
        manifest_file=folder.parent/(id+'.manifest.json')
        manifest_file.write_text(json.dumps(manifest,sort_keys=True))
        manifest_file.chmod(0o600)
        # Only immutable per-publication directories are touched. No repository
        # root, settings or existing file is overwritten by this implementation.
        value={'id':id,'title':title[:160],'provider':provider,'repo':repo,'account':account['account'],
            'application_url':base,'remote_path':'shares/'+id,'digest':digest,'manifest':manifest,
            'files':len(files),'size':sum(map(len,files.values())),'created_at':time.time(),'expires_at':time.time()+86400}
        self.store.save('snapshots',owner,id,value)
        self.store.save('preferences',owner,provider,{'provider':provider,'repo':repo,'application_url':base,'updated_at':time.time()})
        return self.public_snapshot(value)

    @staticmethod
    def public_snapshot(value):
        return {k:v for k,v in value.items() if k!='manifest'}

    def snapshot(self,owner,id):
        self.authorize(owner)
        value=self.store.get('snapshots',owner,id)
        folder=self.store.path(owner,id)
        for name,digest in value['manifest'].items():
            path=folder/name
            if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                raise PublishError('snapshot_changed')
        return value

    def publish(self,owner,id,request_id,confirmed):
        self.authorize(owner)
        if not confirmed:raise PublishError('public_confirmation_required')
        if not re.fullmatch(r'[A-Za-z0-9_-]{16,80}',request_id):raise PublishError('invalid_request_id')
        with self.lock:
            try:
                existing=self.store.get('publications',owner,request_id)
                if existing['snapshot_id']!=id:raise PublishError('request_id_conflict')
                return self._enqueue(owner,existing) if not existing.get('task_id') else self.status(owner,request_id)
            except KeyError:pass
            snap=self.snapshot(owner,id)
            if snap['expires_at']<time.time():raise PublishError('preparation_expired')
            # Persist intent before queue submission. On a crash in between,
            # querying the queue binds the original task, never a new upload.
            record={'request_id':request_id,'snapshot_id':id,'title':snap['title'],'provider':snap['provider'],
                'repo':snap['repo'],'account':snap['account'],'digest':snap['digest'],'created_at':time.time(),'task_id':'','dispatched':False}
            self.store.save('publications',owner,request_id,record)
            return self._enqueue(owner,record)

    def _enqueue(self,owner,record):
        tasks=self.runtime.system_tasks
        with self.runtime.database.transaction() as db:
            row=db.execute('SELECT id FROM system_tasks WHERE owner=? AND app_id=? AND kind=? AND dedup_key=? ORDER BY created_at LIMIT 1',
                (owner,HOST,KIND,'share:'+record['request_id'])).fetchone()
        if row:record['task_id']=row['id']
        elif not record.get('dispatched'):
            task=tasks.submit(owner,HOST,KIND,record['title'],{'request_id':record['request_id']},dedup_key='share:'+record['request_id'])
            record['task_id']=task['id']
        self.store.save('publications',owner,record['request_id'],record)
        return self.status(owner,record['request_id'])

    def status(self,owner,request_id):
        self.authorize(owner)
        record=self.store.get('publications',owner,request_id)
        if not record.get('task_id'):return {**record,'status':'pending_reconciliation'}
        try:
            task=self.runtime.system_tasks.get(owner,record['task_id'])
            return {**record,'status':task['status'],'message':task['message'],'progress':task['progress'],
                'result':self.reader_result(record,record.get('verified') or task.get('result') or {})}
        except KeyError:return {**record,'status':'history','result':self.reader_result(record,record.get('verified') or {})}

    @staticmethod
    def reader_result(record,result):
        # MS serves file fetches but redirects top-level navigation to its www
        # wrapper. The canonical public reader on the main domain was verified
        # in an anonymous browser; use it directly and preserve file evidence.
        if record.get('provider')!='ms' or not result.get('anonymous'):return result
        repo=record.get('repo','');snapshot_id=record.get('snapshot_id','')
        if not REPO.fullmatch(repo) or not re.fullmatch(r'[0-9a-f]{32}',snapshot_id):raise PublishError('invalid_upload_target')
        path='/shares/'+snapshot_id+'/index.html'
        reader='https://modelscope.cn/studios/'+repo+'?mode=full&app_path='+quote(path,safe='')
        return {**result,'content_url':result.get('content_url') or result.get('url'),'url':reader,'reader_route':'modelscope-canonical-studio'}

    async def verify(self,owner,record,report=lambda **kw:None):
        self.authorize(owner)
        snap=self.snapshot(owner,record['snapshot_id'])
        from ai2apps.research.provider import SafeHttpClient
        class PublicFiles(SafeHttpClient):
            ALLOWED_TYPES=SafeHttpClient.ALLOWED_TYPES|frozenset({'image/png','image/jpeg','image/gif','image/webp','image/x-icon',
                'text/css','text/javascript','application/javascript','application/octet-stream','font/woff','font/woff2',
                'application/pdf','video/mp4','video/webm','audio/mpeg','font/ttf'})
        client=PublicFiles(timeout_seconds=10,max_bytes=128*1024*1024,max_redirects=3)
        base=snap['application_url']+snap['remote_path']+'/'
        html_metadata_added=False
        public_html_sha256=''
        resource_origins=set()
        async def one(name,digest):
            nonlocal html_metadata_added,public_html_sha256
            try:response=await asyncio.to_thread(client.get,urljoin(base,quote(name,safe='/')))
            except Exception as error:
                if snap['provider']=='ms' and ms_deployment_pending(error):raise PublishError('deployment_pending') from error
                raise
            same_snapshot=response.url.startswith(base)
            if not same_snapshot and snap['provider']=='hf':
                from .hf_public import is_static_cdn_url
                same_snapshot=is_static_cdn_url(response.url)
                if same_snapshot:resource_origins.add(urlsplit(response.url).netloc)
            if not same_snapshot or response.truncated:
                record['verification_observation']={'expected_origin':urlsplit(base).netloc,'response_origin':urlsplit(response.url).netloc,
                    'snapshot_prefix_match':response.url.startswith(base),'truncated':bool(response.truncated)}
                self.store.save('publications',owner,record['request_id'],record)
                raise PublishError('public_file_truncated' if response.truncated else 'public_redirect_outside_snapshot')
            actual=hashlib.sha256(response.body).hexdigest()
            if name=='index.html':public_html_sha256=actual
            if actual!=digest:
                accepted=False
                if snap['provider']=='hf' and name=='index.html':
                    from .hf_public import matches_static_html
                    accepted,html_metadata_added=matches_static_html((self.store.path(owner,snap['id'])/name).read_bytes(),response.body)
                if not accepted:raise PublishError('public_content_mismatch')
            if name.lower().endswith(('.jpg','.jpeg','.png','.gif','.webp')):
                with Image.open(io.BytesIO(response.body)) as image:image.load()
        async def all_files():
            report(message='Verifying public files',progress={'stage':'verify','done':0,'total':snap['files']})
            await one('index.html',snap['manifest']['index.html'])
            done=1
            limit=asyncio.Semaphore(4)
            async def resource(name,digest):
                nonlocal done
                async with limit:
                    await one(name,digest)
                    done+=1
                    report(message='Verifying public files',progress={'stage':'verify','done':done,'total':snap['files']})
            jobs=[asyncio.create_task(resource(name,digest)) for name,digest in snap['manifest'].items() if name!='index.html']
            try:await asyncio.gather(*jobs)
            finally:
                for job in jobs:
                    if not job.done():job.cancel()
                await asyncio.gather(*jobs,return_exceptions=True)
        await asyncio.wait_for(all_files(),90)
        result={'url':base+'index.html','verified_at':time.time(),'digest':snap['digest'],'verified_files':snap['files'],
            'images_decoded':sum(name.endswith(('.png','.jpg','.jpeg','.gif','.webp')) for name in snap['manifest']),
            'repo':snap['repo'],'snapshot_id':snap['id'],'anonymous':True,
            'html_platform_metadata_added':html_metadata_added,'public_html_sha256':public_html_sha256,
            'resource_origins':sorted(resource_origins)}
        result=self.reader_result(record,result)
        record['verified']=result;self.store.save('publications',owner,record['request_id'],record)
        return result

    async def execute(self,ctx):
        async with asyncio.timeout(900):
            return await self._execute(ctx)

    async def _execute(self,ctx):
        self.authorize(ctx.owner)
        record=self.store.get('publications',ctx.owner,ctx.payload['request_id'])
        snap=self.snapshot(ctx.owner,record['snapshot_id'])
        if record.get('verified'):return record['verified']
        if record.get('dispatched'):
            # Generic queue Retry or restart can only reconcile this intent.
            return await self.verify(ctx.owner,record,ctx.report)
        ctx.report(message='Checking Terminal CLI account',progress={'stage':'account'})
        cli=self.cli_factory(snap['provider'])
        identity=await cli.inspect(snap['repo'])
        if identity['account']!=snap['account']:raise PublishError('cli_account_changed')
        record['dispatched']=True;record['task_id']=ctx.id
        self.store.save('publications',ctx.owner,record['request_id'],record)
        ctx.report(message='Uploading snapshot; cancellation cannot retract uploaded files',
            checkpoint={'snapshot_id':snap['id'],'dispatch':'possible'},progress={'stage':'upload'})
        await cli.upload(snap['repo'],self.store.path(ctx.owner,snap['id']),snap['remote_path'],record['request_id'])
        ctx.report(message='Waiting for static deployment',progress={'stage':'deploy'})
        await cli.deploy(snap['repo'])
        # Platform propagation/cold start is read-only waiting. Never reupload.
        deadline=time.monotonic()+600
        attempt=0
        while True:
            try:return await self.verify(ctx.owner,record,ctx.report)
            except asyncio.CancelledError:raise
            except Exception as error:
                reason,retryable=verification_failure(error)
                attempt+=1
                record['last_verification_error']=reason
                self.store.save('publications',ctx.owner,record['request_id'],record)
                if not retryable:raise PublishError(reason) from error
                if time.monotonic()>=deadline:raise PublishError('deployment_unverified','Use Verify; do not resubmit') from error
                ctx.report(message='Waiting for public deployment: '+reason,
                    progress={'stage':'waiting_deployment','reason':reason,'attempt':attempt})
                await asyncio.sleep(10)


def ms_deployment_pending(error):
    """Recognize only the hosting platform's explicit bounded pending reply."""
    from urllib.error import HTTPError
    seen=set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error,HTTPError) and error.code==412:
            host=urlsplit(error.geturl()).hostname or ''
            if not host.endswith('.ms.show'):return False
            try:
                raw=error.read(4097)
                if len(raw)>4096:return False
                value=json.loads(raw)
                return value.get('Code')=='PreconditionFailed' and value.get('Message')=='function is pending state, please try later'
            except (ValueError,OSError,AttributeError):return False
            finally:error.close()
        error=error.__cause__
    return False


def verification_failure(error):
    if isinstance(error,PublishError):return error.code,error.code=='deployment_pending'
    seen=set();current=error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current,ssl.SSLCertVerificationError):return 'public_tls_error',False
        if isinstance(current,socket.gaierror):return 'public_dns_error',True
        if isinstance(current,(TimeoutError,asyncio.TimeoutError)):return 'public_timeout',True
        reason=getattr(current,'reason',None)
        current=reason if isinstance(reason,BaseException) else current.__cause__
    match=re.search(r'HTTP (\d{3})',str(error))
    if match:
        status=int(match[1]);return 'public_http_'+str(status),status in (404,409,425,429,500,502,503,504)
    return 'public_verification_failed',False


def register(runtime):
    from ai2apps.system_tasks import TaskHandler
    service=runtime.share_works=ShareWorks(runtime)
    async def cancel(ctx,force):
        # SystemTaskService cancels execute and waits for completion; CLI.run kills its own
        # process group on cancellation. No deployment deletion is attempted.
        return True
    runtime.system_tasks.register(KIND,TaskHandler(HOST,service.execute,cancel,
        lambda owner,payload:service.authorize(owner),resumable=False))

    from .social import KIND as SOCIAL_KIND, SocialWorks
    service.social = SocialWorks(service)
    runtime.system_tasks.register(SOCIAL_KIND, TaskHandler(HOST, service.social.execute_x, cancel,
        lambda owner, payload: service.authorize(owner), resumable=False))
