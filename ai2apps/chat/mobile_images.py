"""Mobile projection of owned inline images; model inputs and stored originals stay intact."""
import base64,hashlib,json,re
from copy import deepcopy
from urllib.parse import urlencode
from fastapi import HTTPException
from starlette.responses import Response
from ai2apps.chat import ChatRepository
from ai2apps.core import RepositoryError

_ID=r'[A-Za-z0-9_-]{1,256}'
_CONTENT=re.compile(r'/chat/threads/('+_ID+r')/content$')
_TURN=re.compile(r'/chat/threads/('+_ID+r')/turns$')
MAX_RESTORED_BYTES=21*1024*1024
_DATA=re.compile(r'^data:(image/(?:png|jpeg|webp|avif|gif));base64,([A-Za-z0-9+/=\s]+)$')


def _repository(runtime,principal):return ChatRepository(runtime.database,runtime.events,principal=principal)


def _source(runtime,principal,thread,ref):
    if not isinstance(ref,dict) or set(ref)!={'thread_id','message_id','part_index','digest'} or ref['thread_id']!=thread:
        raise HTTPException(409,'Image reference changed; reload this conversation')
    if type(ref['part_index']) is not int or not 0<=ref['part_index']<1024 or not isinstance(ref['digest'],str) or not re.fullmatch(r'[a-f0-9]{64}',ref['digest']):raise HTTPException(422,'Invalid image reference')
    try:record=_repository(runtime,principal).get_content(thread)
    except RepositoryError as error:raise HTTPException(404,'Chat image unavailable') from error
    for message in record.messages:
        if message.metadata.get('id')!=ref['message_id'] or not isinstance(message.content,list) or ref['part_index']>=len(message.content):continue
        part=message.content[ref['part_index']]
        value=part.get('image_url') if isinstance(part,dict) else None
        url=value.get('url') if isinstance(value,dict) else None
        if isinstance(url,str) and hashlib.sha256(url.encode()).hexdigest()==ref['digest'] and _DATA.fullmatch(url):return value
    raise HTTPException(404,'Chat image is no longer present')


def prepare_request(runtime,principal,method,path,payload):
    match=_CONTENT.fullmatch(path) if method=='PUT' else _TURN.fullmatch(path) if method=='POST' else None
    if not match or not isinstance(payload,dict):return payload
    rows=payload.get('messages') if method=='PUT' else (payload.get('request') or {}).get('messages')
    if not isinstance(rows,list):return payload
    restored_size=len(json.dumps(payload).encode())
    if restored_size>MAX_RESTORED_BYTES:raise HTTPException(413,'Mobile Chat input exceeds media limit')
    for message in rows:
        parts=message.get('content') if isinstance(message,dict) else None
        if not isinstance(parts,list):continue
        for part in parts:
            if not isinstance(part,dict) or part.get('type')!='image_url' or not isinstance(part.get('image_url'),dict):continue
            image=part['image_url']
            if 'mobile_image_ref' in image:
                original=_source(runtime,principal,match[1],image['mobile_image_ref'])
                restored_size+=len(json.dumps(original).encode())-len(json.dumps(image).encode())
                if restored_size>MAX_RESTORED_BYTES:raise HTTPException(413,'Restored Chat images exceed Mobile input limit')
                part['image_url']=deepcopy(original)
    return payload


def project_response(path,status,content):
    match=_CONTENT.fullmatch(path)
    if not match or status!=200:return content
    try:value=json.loads(content)
    except (ValueError,TypeError):return content
    for message in value.get('messages',[]):
        mid=(message.get('metadata') or {}).get('id')
        if not isinstance(mid,str) or not re.fullmatch(_ID,mid):continue
        parts=message.get('content')
        if not isinstance(parts,list):continue
        for index,part in enumerate(parts):
            if not isinstance(part,dict) or part.get('type')!='image_url' or not isinstance(part.get('image_url'),dict):continue
            image=part['image_url'];url=image.get('url')
            if not isinstance(url,str) or not _DATA.fullmatch(url):continue
            digest=hashlib.sha256(url.encode()).hexdigest()
            full=f'/v1/mobile/chat/threads/{match[1]}/images/{mid}/{index}?'+urlencode({'digest':digest})
            image.update(url=full+'&preview=mobile',mobile_original_url=full,
                mobile_image_ref={'thread_id':match[1],'message_id':mid,'part_index':index,'digest':digest})
    return json.dumps(value,ensure_ascii=False).encode()


async def image_response(runtime,principal,thread,message,index,digest,*,preview=False):
    from ai2apps.web.mobile_image_preview import MAX_SOURCE,preview_bytes,response
    value=_source(runtime,principal,thread,{'thread_id':thread,'message_id':message,'part_index':index,'digest':digest})
    match=_DATA.fullmatch(value['url'])
    if len(match[2])>MAX_SOURCE*4//3+16:raise HTTPException(413,'Image exceeds Mobile media limit')
    try:content=base64.b64decode(re.sub(r'\s+','',match[2]),validate=True)
    except ValueError as error:raise HTTPException(422,'Invalid stored image') from error
    if len(content)>MAX_SOURCE:raise HTTPException(413,'Image exceeds Mobile media limit')
    if preview:return response(await preview_bytes(content))
    return Response(content,media_type=match[1],headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
