"""Managed Cloud structured-output v1; format validation grants no business authority."""
import json
import httpx
from fastapi import HTTPException

CONTRACT = 'ai2apps.structured-output.v1'
MAX_BYTES = 1048576


def reject(code, message, *, status=400, details=None):
    raise HTTPException(status, {'code':code,'message':message,'retryable':False,
                                 **({'details':details} if details else {})})


def requested_format(request):
    raw = getattr(request, 'response_format', None)
    if raw is None:
        return None
    value = raw.model_dump(mode='json', exclude_none=True) if hasattr(raw,'model_dump') else raw
    if not isinstance(value,dict) or set(value)!={'type'}:
        reject('INVALID_AI_RESPONSE_FORMAT','Response format must contain only type.')
    if value['type'] not in ('text','json_object'):
        reject('AI_RESPONSE_FORMAT_UNSUPPORTED','Selected response format is not supported by managed Cloud.')
    if value['type']=='json_object':
        if getattr(request,'tools',None):
            reject('AI_RESPONSE_FORMAT_TOOLS_UNSUPPORTED','JSON object output cannot be combined with tools.')
        if any(str(m.role)=='developer' for m in request.messages):
            reject('AI_INSTRUCTION_ROLE_UNSUPPORTED','Structured output cannot preserve a separate developer role on this Cloud contract.')
    return value


async def check_capability(client, body, headers):
    if body.get('responseFormat',{}).get('type')!='json_object':
        return None
    try:
        response = await client.request('GET','/v1/ai/models',headers=headers or {})
    except httpx.HTTPError:
        reject('AI_STRUCTURED_OUTPUT_CAPABILITY_UNAVAILABLE','Cannot verify structured-output capability.',status=503)
    try:
        if response.status_code!=200:
            reject('AI_STRUCTURED_OUTPUT_CAPABILITY_UNAVAILABLE','Cannot verify the selected model\'s structured-output capability.',status=503)
        try:
            payload=response.json()
        except ValueError:
            reject('AI_STRUCTURED_OUTPUT_CAPABILITY_UNAVAILABLE','Cloud model capabilities were invalid.',status=502)
    finally:
        await response.aclose()
    items=payload.get('items',[]) if isinstance(payload,dict) else []
    for model in items if isinstance(items,list) else []:
        if not isinstance(model,dict) or model.get('id')!=body['model']:
            continue
        caps=model.get('capabilities');cap=caps.get('structuredOutput') if isinstance(caps,dict) else None
        if (isinstance(cap,dict) and cap.get('contract')==CONTRACT and
                isinstance(cap.get('modes'),list) and 'json_object' in cap['modes'] and
                cap.get('buffered') is True and type(cap.get('maxOutputBytes')) is int and
                0<cap['maxOutputBytes']<=MAX_BYTES):
            return cap['maxOutputBytes']
        break
    reject('AI_RESPONSE_FORMAT_UNSUPPORTED','The selected model does not advertise structured JSON object output. No request was submitted.')


def validate_complete(payload, text, limit):
    # Keep billing facts separate from validation. Missing markers never imply a refund.
    details={k:payload[k] for k in ('requestId','points','usage','stopReason') if k in payload} if isinstance(payload,dict) else {}
    if (not isinstance(payload,dict) or payload.get('responseFormat')!={'type':'json_object'} or
            not isinstance(payload.get('structuredOutput'),dict) or
            payload['structuredOutput'].get('valid') is not True or
            payload['structuredOutput'].get('type')!='json_object' or
            payload.get('stopReason')!='stop' or payload.get('status') not in (None,'completed') or
            not isinstance(payload.get('output',[]),list) or
            any(isinstance(x,dict) and x.get('type')=='tool_call' for x in payload.get('output',[]))):
        reject('AI_STRUCTURED_OUTPUT_INCOMPLETE','Cloud did not confirm a successful structured-output result. No action was executed.',status=502,details=details)
    if len(text.encode('utf-8'))>limit:
        reject('AI_STRUCTURED_OUTPUT_TOO_LARGE','Structured output exceeded the declared size limit.',status=502,details=details)
    try:
        value=json.loads(text,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
        if not isinstance(value,dict):
            raise ValueError()
    except (ValueError,TypeError):
        reject('AI_STRUCTURED_OUTPUT_INVALID','Model output did not satisfy the JSON object contract. No action was executed.',status=502,details=details)
    return value
