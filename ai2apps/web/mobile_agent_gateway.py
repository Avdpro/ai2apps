"""Exact Mobile Agent ingress, independent of Owner cookies and Local admin auth."""
import json
import re
from urllib.parse import urlsplit
import httpx
from fastapi import FastAPI,HTTPException,Request
from starlette.responses import JSONResponse,Response,HTMLResponse
from ai2apps.remote.security import RemoteTokenError
from ai2apps.web.mobile_agent_transport import allowed_control

PREFIX='/v1/mobile/agent'
_ID=r'[A-Za-z0-9_-]{1,256}'

def business_target(method,path):
    if method=='POST' and re.fullmatch(r'/chat/threads/'+_ID+r'/manage',path):return path
    if method in ('PATCH','DELETE') and re.fullmatch(r'/chat/threads/'+_ID,path):return path
    if method=='POST' and re.fullmatch(r'/chat/threads/'+_ID+r'/speech',path):return path
    if path=='/chat/notification-target' and method=='POST':return '/notifications/resolve-target'
    if path=='/agents' and method=='GET':return '/agents'
    if path=='/chat/state' and method=='GET':return '/chat'
    if path=='/chat/threads' and method in ('GET','POST'):return '/chat/threads'
    m=re.fullmatch(r'/chat/threads/('+_ID+r')/(content|agent-runs)',path)
    if m:
        thread,kind=m.groups()
        if kind=='content' and method=='GET':return f'/chat/threads/{thread}/content'
        if kind=='agent-runs' and method in ('GET','POST'):return f'/sessions/{thread}/agent-runs'
    upload=re.fullmatch(r'/chat/threads/('+_ID+r')/uploads(?:/([0-9a-f]{32})(?:/(complete|cancel))?)?',path)
    if upload:
        thread,identifier,action=upload.groups()
        if (identifier is None and method=='POST') or (identifier and action is None and method=='PUT') or (identifier and action and method=='POST'):
            return '/sessions/'+thread+'/attachments/uploads'+('/'+identifier if identifier else '')+('/'+action if action else '')
    m=re.fullmatch(r'/agent-runs/('+_ID+r')(?:/(.*))?',path)
    if m:
        rid,tail=m.groups()
        if tail is None and method=='GET':return f'/agent-runs/{rid}'
        if tail and allowed_control(method,tail):return f'/agent-runs/{rid}/{tail}'
    return None

def public_path(method,path):
    if method=='GET' and path in ('/mobile/home','/mobile/agent-chat'):return True
    if path==PREFIX+'/bootstrap' and method=='GET':return True
    if re.fullmatch(PREFIX+r'/connections/[0-9a-f-]{36}/(?:challenge|lease|revoke|nonce)',path) and method=='POST':return True
    if path.startswith(PREFIX+'/') and (business_target(method,path[len(PREFIX):]) or path==PREFIX+'/models' and method=='GET' or re.fullmatch(PREFIX+r'/(?:assets/'+_ID+r'/\d+/\d+|(?:artifacts|files)/'+_ID+r'/'+_ID+r')',path) and method=='GET'):return True
    return False

async def dispatch(runtime,principal,method,path,body,headers,query=''):
    if path=='/notifications/resolve-target':
        try:
            data=json.loads(body)
            if data.get('target',{}).get('app_id')!='ai2apps.general-chat':raise ValueError()
        except (ValueError,AttributeError):
            raise HTTPException(403,'Only Chat notification targets are allowed') from None
    from ai2apps.api import create_ai2apps_router
    app=FastAPI(openapi_url=None,docs_url=None,redoc_url=None)
    app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:principal))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://agent.internal',timeout=None) as client:
        result=await client.request(method,'/v1/platform'+path+('?' +query if query else ''),content=body,headers=headers)
    return Response(result.content,status_code=result.status_code,media_type=result.headers.get('content-type','application/json'),headers={'Cache-Control':'no-store'})

async def result_image(runtime,principal,path):
    from ai2apps.api.ownership import authorize_agent_run
    from ai2apps.remote.mobile_apps import app_enabled
    from ai2apps.web.mobile_app_gateway import api_response
    m=re.fullmatch(r'/assets/('+_ID+r')/(\d+)/(\d+)',path)
    if not m:raise HTTPException(404)
    rid,vi,ii=m.groups();authorize_agent_run(runtime,principal,rid)
    run=runtime.agents.get_run(rid)
    try:
        record=run.output['aaat_views'][int(vi)];item=record['view']['items'][int(ii)];url=item['image']['url']
        provider=runtime.app_capability_router.providers[record['provider']]
    except (KeyError,TypeError,IndexError):raise HTTPException(404,'Result image unavailable')
    with runtime.database.transaction() as db:
        row=db.execute("SELECT manifest_json FROM app_definitions WHERE source='builtin' AND status='enabled' AND json_extract(manifest_json,'$.id')=?",(provider.app_id,)).fetchone()
    manifest=json.loads(row['manifest_json']) if row else {};mobile=manifest.get('mobile',{});spec=mobile.get('gateway')
    if not spec or not mobile.get('ready') or not app_enabled(runtime,principal,provider.app_id):raise HTTPException(403,'Result owner is not Mobile-enabled')
    parsed=urlsplit(url)
    if parsed.scheme or parsed.netloc or not url.startswith('/v1/platform/') or parsed.fragment:raise HTTPException(403,'Result image requires an owner resource adapter')
    response=await api_response(runtime,principal,spec,{'verb':'GET','path':url,'body':'','headers':{}})
    if not response.headers.get('content-type','').split(';')[0] in ('image/jpeg','image/png','image/webp','image/avif','image/gif'):raise HTTPException(422,'Owner resource is not a raster image')
    return Response(response.content,status_code=response.status_code,media_type=response.headers.get('content-type'),headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


async def generated_file(runtime, principal, path):
    """Only an artifact explicitly recorded by a successful Tool in this Run."""
    from ai2apps.api.ownership import authorize_agent_run, authorize_session
    from starlette.responses import FileResponse
    match=re.fullmatch(r'/files/('+_ID+r')/('+_ID+r')',path)
    if not match:raise HTTPException(404)
    rid,aid=match.groups();authorize_agent_run(runtime,principal,rid)
    run=runtime.agents.get_run(rid);authorize_session(runtime,principal,run.session_id)
    files=[]
    for step in runtime.agents.list_steps(rid):
        if step.status.value!='completed':continue
        output=step.output or {}
        if isinstance(output,dict):files.extend(output.get('files',[]) if isinstance(output.get('files'),list) else [])
    expected=f'/v1/platform/sessions/{run.session_id}/artifacts/{aid}/download'
    if not any(isinstance(f,dict) and f.get('artifact_id')==aid and f.get('url')==expected for f in files):
        raise HTTPException(404,'File is not a recorded output of this Run')
    artifact=runtime.workspace.get_artifact(run.session_id,aid)
    return FileResponse(runtime.workspace.artifact_path(artifact),filename=artifact.name,
        media_type=artifact.media_type,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


async def generated_image(runtime,principal,path):
    from ai2apps.api.ownership import authorize_agent_run
    m=re.fullmatch(r'/artifacts/('+_ID+r')/('+_ID+r')',path)
    if not m:raise HTTPException(404)
    rid,aid=m.groups();authorize_agent_run(runtime,principal,rid)
    run=runtime.agents.get_run(rid)
    expected=f'/v1/platform/sessions/{run.session_id}/artifacts/{aid}/download'
    parts=(run.output or {}).get('content',[])
    if not isinstance(parts,list) or not any(isinstance(p,dict) and p.get('type')=='image_url' and isinstance(p.get('image_url'),dict) and p['image_url'].get('artifact_id')==aid and p['image_url'].get('url')==expected for p in parts):
        raise HTTPException(404,'Image is not a recorded output of this Run')
    response=await dispatch(runtime,principal,'GET',expected.removeprefix('/v1/platform'),b'',{})
    if response.status_code!=200:return response
    if response.headers.get('content-type','').split(';')[0] not in ('image/png','image/jpeg','image/webp','image/avif','image/gif'):
        raise HTTPException(422,'Artifact is not a raster image')
    return Response(response.body,media_type=response.headers['content-type'],headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

async def application(scope,receive,send,runtime,device):
    """Called only for an exact known Device Host by PublicDeviceBoundary."""
    request=Request(scope,receive=receive);path=scope['path'];method=scope['method'];service=runtime.remote.mobile_agent
    async def execute():
        if method=='GET' and path in ('/mobile/home','/mobile/agent-chat'):
            from omlx.admin.routes import templates
            if path=='/mobile/home':
                return templates.TemplateResponse(request,'mobile_agent_pair.html',{},headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"})
            return templates.TemplateResponse(request,'mobile_chat.html',{'owner_home':False,'mobile_agent_ready':True,'mobile_agent_signed':True},headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; img-src 'self' blob:; style-src 'self' 'unsafe-inline'; frame-ancestors 'self'; object-src 'none'; base-uri 'none'; form-action 'none'"})
        if path==PREFIX+'/bootstrap':
            return JSONResponse({'protocol':'desktop-mobile-agent-v1','enabled':service.status(device)['ready'],'origin':runtime.remote.require_device(device).public_origin},headers={'Cache-Control':'no-store'})
        if request.headers.get('origin')!=runtime.remote.require_device(device).public_origin and method!='GET':raise HTTPException(403,'Agent Origin mismatch')
        length=int(request.headers.get('content-length','0'))
        if length>21*1024*1024:raise HTTPException(413)
        service.rate((device,request.client.host if request.client else '',path.split('/')[-1]),240)
        body=await request.body()
        if len(body)>21*1024*1024:raise HTTPException(413)
        m=re.fullmatch(PREFIX+r'/connections/([0-9a-f-]{36})/(challenge|lease|revoke|nonce)',path)
        if m:
            connection,action=m.groups();data=json.loads(body or b'{}')
            if action=='challenge':return JSONResponse(await service.challenge(device,connection,data.get('action','lease')))
            if action=='lease' or action=='revoke':return JSONResponse(await service.proof(device,connection,action,data))
            async with service.lock:
                record=service.lease(connection)
                if record['claims']['device_id']!=device:raise HTTPException(403,'Wrong Agent Device')
                return JSONResponse(service.nonce(connection))
        # Reject encoded/normalized aliases before checking the signed target.
        raw=scope.get('raw_path',path.encode())
        if raw!=path.encode('ascii') or b'%' in raw or '..' in path or '\\' in path:raise HTTPException(403,'Noncanonical Agent path')
        target=path+('?' +scope.get('query_string',b'').decode('ascii') if scope.get('query_string') else '')
        async with service.lock:
            connection=request.headers.get('x-ai2apps-agent-connection','')
            record=service.lease(connection)
            if record['claims']['device_id']!=device:raise HTTPException(403,'Wrong Agent Device')
            principal=service.authorize(connection,request.headers.get('x-ai2apps-agent-nonce',''),request.headers.get('x-ai2apps-agent-signature',''),method,target,body)
            relative=path[len(PREFIX):]
            if relative=='/models':
                from ai2apps.web.owner_home_gateway import _models
                if _models is None:raise HTTPException(503,'Model catalog unavailable')
                result=await _models(principal)
                return JSONResponse(result.model_dump(mode='json') if hasattr(result,'model_dump') else result)
            if relative.startswith('/files/'):return await generated_file(runtime,principal,relative)
            if relative.startswith('/artifacts/'):return await generated_image(runtime,principal,relative)
            if relative.startswith('/assets/'):return await result_image(runtime,principal,relative)
            routed=business_target(method,relative)
            if routed is None:raise HTTPException(403,'Agent route denied')
            headers={k:request.headers[k] for k in ('content-type','idempotency-key') if k in request.headers}
            return await dispatch(runtime,principal,method,routed,body,headers,scope.get('query_string',b'').decode('ascii'))
    try:response=await execute()
    except RemoteTokenError as error:response=JSONResponse({'detail':str(error)},status_code=403)
    except HTTPException as error:response=JSONResponse({'detail':error.detail},status_code=error.status_code)
    except (ValueError,KeyError,TypeError):response=JSONResponse({'detail':'Invalid Mobile Agent request'},status_code=422)
    except Exception:
        # Never serialize Cloud response/token/QR or silently fall back to Owner auth.
        response=JSONResponse({'detail':'Mobile Agent service unavailable'},status_code=503)
    await response(scope,receive,send)
