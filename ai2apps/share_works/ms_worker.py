from urllib.parse import urlsplit
"""Fixed isolated ModelScope SDK worker. Never reads or outputs credential files.

Run with the interpreter belonging to the user's already installed MS CLI.
No App runtime/SDK dependency injection, login, install or SDK upload retry loop.
"""
import base64
import contextlib
import hashlib
import io
import json
from pathlib import Path
import re
import sys


class WorkerError(ValueError):pass


def clients(api):
    # Version-checked official SDK transports: effectful requests must not retry
    # on an uncertain response. No access to headers, tokens or Cookie values.
    legacy=api.legacy;openapi=api.openapi
    if not hasattr(legacy,'_session') or not hasattr(openapi,'_max_retries'):
        raise WorkerError('ms_sdk_incompatible')
    from requests.adapters import HTTPAdapter
    legacy._session.mount('https://',HTTPAdapter(max_retries=0))
    legacy._session.mount('http://',HTTPAdapter(max_retries=0))
    openapi._max_retries=1  # SDK counts total attempts, not additional retries.
    return legacy,openapi


def inspect(api,repo):
    account=api.whoami().username
    if not isinstance(account,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',account):raise WorkerError('cli_identity_unrecognized')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',repo):raise WorkerError('invalid_space_id')
    owner,name=repo.split('/')
    if owner!=account:raise WorkerError('space_account_mismatch')
    _,openapi=clients(api)
    raw=openapi.get_studio(owner,name)
    if not isinstance(raw,dict):raise WorkerError('ms_sdk_incompatible')
    for key in ('data','Data'):
        if isinstance(raw.get(key),dict):raw=raw[key]
    sdk=raw.get('sdk_type') or raw.get('sdkType') or raw.get('SdkType')
    visibility=raw.get('visibility',raw.get('Visibility'))
    if sdk!='static' or visibility not in ('public',5,'5') or raw.get('private') is True:
        raise WorkerError('space_must_be_public_static')
    result={'provider':'ms','account':account,'repo':repo,'transport':'official-sdk-existing-login'}
    for key in ('app_url','appUrl','access_url','accessUrl','domain','host'):
        value=raw.get(key)
        if isinstance(value,str) and value.startswith('https://') and urlsplit(value).hostname and urlsplit(value).hostname.endswith('.ms.show'):
            result['application_url']=value;break
    return result


def upload(api,body):
    inspect(api,body['repo'])
    prefix=body['remote_path']
    if not re.fullmatch(r'shares/[0-9a-f]{32}',prefix):raise WorkerError('invalid_upload_target')
    root=Path(body['directory']).resolve()
    manifest_path=Path(body['manifest_path'])
    if manifest_path.resolve()!=root.parent/(root.name+'.manifest.json'):raise WorkerError('snapshot_changed')
    manifest=json.loads(manifest_path.read_text())
    if not isinstance(manifest,dict) or not 1<=len(manifest)<=2000:raise WorkerError('snapshot_changed')
    # Check the entire immutable snapshot before sending any file.
    blobs=[]
    for name,digest in manifest.items():
        path=root/name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):raise WorkerError('snapshot_changed')
        content=path.read_bytes()
        if len(content)>16*1024*1024:raise WorkerError('ms_inline_file_limit')
        if hashlib.sha256(content).hexdigest()!=digest:raise WorkerError('snapshot_changed')
        blobs.append((name,content))
    legacy,_=clients(api)
    batch=[];size=0;commits=0
    def commit():
        nonlocal commits
        if batch:
            legacy.create_commit(body['repo'],'studio',batch,'AI2Apps snapshot '+body['request_id'],revision='master')
            commits+=1
    for name,content in blobs:
        if batch and size+len(content)>16*1024*1024:
            commit();batch=[];size=0
        batch.append({'action':'create','path':prefix+'/'+name,'type':'normal','size':len(content),
                      'sha256':'','content':base64.b64encode(content).decode(),'encoding':'base64'})
        size+=len(content)
    commit()
    return {'commits':commits,'files':len(blobs)}


def execute(action,body,api):
    if action=='account':return {'account':api.whoami().username}
    if action=='inspect':return inspect(api,body['repo'])
    if action=='upload':return upload(api,body)
    if action=='deploy':
        inspect(api,body['repo']);clients(api);api.deploy_repo(body['repo'],'studio');return {'requested':True}
    raise WorkerError('unsupported_sdk_action')


def main():
    try:
        action=sys.argv[1];body=json.loads(sys.argv[2])
        # SDK owns credential loading and network auth. Its ordinary diagnostics
        # are suppressed: only selected safe fields cross the worker boundary.
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            from modelscope_hub import HubApi
            result=execute(action,body,HubApi())
        output={'value':result}
    except WorkerError as e:output={'error':str(e)}
    except ImportError:output={'error':'ms_sdk_missing'}
    except Exception as e:
        kind=type(e).__name__
        code={'AuthenticationError':'cli_not_logged_in','PermissionDeniedError':'cli_permission_denied','NotExistError':'space_not_found'}.get(kind,'ms_sdk_failed')
        output={'error':code}
    print(json.dumps(output))

if __name__=='__main__':main()
