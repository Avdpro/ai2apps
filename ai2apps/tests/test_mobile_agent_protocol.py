import asyncio,base64,json,time
from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import uuid4
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec,ed25519
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from ai2apps.remote.mobile_agent_crypto import public_key,verify_proof,verify_lease,local_input,PROTOCOL,AUDIENCE
from ai2apps.remote.mobile_agent import MobileAgent
from ai2apps.remote.security import RemoteTokenError
from ai2apps.storage import PlatformDatabase
from ai2apps.identity import IdentityRepository,OrganizationType

b64=lambda b:base64.urlsafe_b64encode(b).rstrip(b'=').decode()
stamp=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat().replace('+00:00','Z')
def sign(key,message):
 r,s=decode_dss_signature(key.sign(message.encode(),ec.ECDSA(hashes.SHA256())))
 return b64(r.to_bytes(32,'big')+s.to_bytes(32,'big'))

def test_cloud_public_vectors_interoperate():
 path=Path(__file__).parent/'fixtures/mobile-agent-proof-vectors-v1.json'
 data=json.loads(path.read_text());assert public_key(data['publicKey'])[1]==data['jkt']
 for v in data['vectors']:
  assert v['input'].encode().hex()==v['utf8Hex'];verify_proof(data['publicKey'],v['input'],v['signature'])
  with pytest.raises(RemoteTokenError):verify_proof(data['publicKey'],v['input']+'\n',v['signature'])

@pytest.fixture
def env(tmp_path):
 db=PlatformDatabase(tmp_path/'test.sqlite');db.initialize();identities=IdentityRepository(db)
 owner,deviceid,install,org=[str(uuid4()) for _ in range(4)]
 identities.bind_installation(installation_id=install,cloud_device_id=deviceid,organization_id=org,organization_type=OrganizationType.HOUSEHOLD,core_user_id=owner,billing_account_id=str(uuid4()),access_epoch=1)
 device=NS(device_id=deviceid,enabled=True,status='active',credential_version=1,access_epoch=1)
 server=NS(generation=0,instance=None,active=None,pending=None,views={},fail_ack=False,calls=[])
 signing=ed25519.Ed25519PrivateKey.generate();jwks={'keys':[dict(kid='test',kty='OKP',crv='Ed25519',alg='EdDSA',use='sig',x=b64(signing.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)))]}
 key=ec.generate_private_key(ec.SECP256R1());raw=key.public_key().public_bytes(Encoding.X962,PublicFormat.UncompressedPoint);jwk=dict(crv='P-256',kty='EC',x=b64(raw[1:33]),y=b64(raw[33:]));jkt=public_key(jwk)[1]
 session=str(uuid4())
 def token(cid,changes=None):
  now=int(time.time());c=dict(iss='ai2apps-cloud',aud=AUDIENCE,protocol=PROTOCOL,scope='agent:invoke',sub=owner,actor_user_id=owner,owner_user_id=owner,device_id=deviceid,installation_id=install,organization_id=org,organization_type='household',role='core',membership_epoch=1,access_epoch=1,credential_version=1,local_session_epoch=1,account_session_epoch=1,organization_authorization_version=1,organization_policy_version=1,mobile_connection_id=cid,session_id=session,authorization_generation=server.generation,enforcer_instance_id=server.instance,client_jkt=jkt,cnf={'jkt':jkt},iat=now,nbf=now,exp=now+60,jti=str(uuid4()))
  c.update(changes or {});head=b64(json.dumps({'alg':'EdDSA','kid':'test'}).encode());body=b64(json.dumps(c).encode());return head+'.'+body+'.'+b64(signing.sign((head+'.'+body).encode()))
 async def request(method,path,**kwargs):
  server.calls.append((method,path));body=kwargs.get('json',{})
  if path=='/v1/remote/jwks.json':return jwks
  if path.endswith('/device'):
   if method=='PUT':
    if server.instance!=body['enforcerInstanceId']:server.generation+=1;server.active=None;server.pending=None
    server.instance=body['enforcerInstanceId'];return dict(protocol=PROTOCOL,enforcerInstanceId=server.instance,generation=server.generation)
   return dict(protocol=PROTOCOL,enforcerInstanceId=server.instance,generation=server.generation,activeConnectionId=server.active,pendingConnectionId=server.pending)
  if path.endswith('/device/revoke'):server.generation+=1;server.active=None;return {'generation':server.generation}
  if path.endswith('/pairings'):
   cid=str(uuid4());server.views[cid]=dict(protocol=PROTOCOL,connectionId=cid,deviceId=deviceid,status='pending',generation=server.generation,enforcerInstanceId=server.instance,displayDeadline=stamp(time.time()+30),approvalDeadline=stamp(time.time()+35))
   return dict(connectionId=cid,protocol=PROTOCOL,generation=server.generation,pairingUrl='https://device-test.ai2apps.com/mobile/home#agent_pair=fixture')
  cid=path.split('/pairings/')[1].split('/')[0];v=server.views[cid]
  if path.endswith('/decision'):
   if body['decision']!='agent':v['status']='chat' if body['decision']=='chat' else 'denied';return dict(v)
   server.generation+=1;server.active=None;server.pending=cid;v.update(status='awaiting_ack',generation=server.generation);return dict(v)
  if path.endswith('/ack'):
   if server.fail_ack:raise OSError('ACK response lost')
   server.active=cid;server.pending=None;v.update(status='active',agent=True);return dict(v)
  if path.endswith('/proof-challenges'):return {'nonce':'a'*43,'clientKeyThumbprint':jkt}
  if path.endswith('/lease'):return {'leaseToken':token(cid),'leaseExpiresAt':stamp(time.time()+59),'generation':server.generation}
  if path.endswith('/revoke'):server.generation+=1;server.active=None;return {'generation':server.generation}
  return dict(v)
 async def timed_request(method,path,**kwargs):
  result=await request(method,path,**kwargs);return {**result,'_server_time':time.time()}
 manager=NS(repository=NS(database=db,list=lambda:[device]),_request=timed_request,require_device=lambda _:device,space=NS(installation=lambda _:identities.get_installation(),running=lambda _:True))
 service=MobileAgent(manager)
 return NS(service=service,manager=manager,server=server,device=deviceid,key=key,jwk=jwk,jkt=jkt,token=token,jwks=jwks)

async def approved(e):
 s=e.service;await s.configure(e.device,True);p=await s.create(e.device);await s.decision(e.device,p['connectionId'],'agent',s.row(e.device)['generation']);cid=p['connectionId'];await s.challenge(e.device,cid,'lease');await s.proof(e.device,cid,'lease',{'nonce':'a'*43,'signature':sign(e.key,'\n'.join(('ai2apps-mobile-agent-proof-v1','lease',cid,'a'*43,e.jkt))),'publicKey':e.jwk});return cid

@pytest.mark.asyncio
async def test_default_closed_switch_fences_old_valid_jwt_and_chat_keeps_active(env):
 e=env;s=e.service
 with pytest.raises(RemoteTokenError):s.require(e.device)
 cid=await approved(e);old=s.leases[cid]['claims'];qr=await s.create(e.device)
 await s.decision(e.device,qr['connectionId'],'chat',s.row(e.device)['generation']);assert s.lease(cid)
 qr=await s.create(e.device);await s.decision(e.device,qr['connectionId'],'agent',s.row(e.device)['generation'])
 assert old['exp']>time.time()
 with pytest.raises(RemoteTokenError):s.lease(cid)

@pytest.mark.asyncio
async def test_method_path_body_nonce_and_concurrent_replay(env):
 e=env;cid=await approved(e);s=e.service
 def proof(n,method='POST',path='/v1/mobile/agent/chat/threads',body=b'{}'):
  return sign(e.key,local_input(cid,n['jti'],method,path,body,n['nonce']))
 n=s.nonce(cid);sig=proof(n);actor=s.authorize(cid,n['nonce'],sig,'POST','/v1/mobile/agent/chat/threads',b'{}');assert actor.authentication_type=='desktop_approved_agent'
 with pytest.raises(RemoteTokenError):s.authorize(cid,n['nonce'],sig,'POST','/v1/mobile/agent/chat/threads',b'{}')
 for method,path,body in [('GET','/v1/mobile/agent/chat/threads',b'{}'),('POST','/v1/mobile/agent/agent-runs/other/cancel',b'{}'),('POST','/v1/mobile/agent/chat/threads',b'{"changed":true}')]:
  n=s.nonce(cid)
  with pytest.raises(RemoteTokenError):s.authorize(cid,n['nonce'],proof(n),method,path,body)

@pytest.mark.asyncio
async def test_process_restart_rejects_cached_authorization_before_sync(env):
 e=env;cid=await approved(e);old=e.service.instance;restarted=MobileAgent(e.manager)
 assert restarted.instance!=old
 with pytest.raises(RemoteTokenError):restarted.require(e.device)
 await restarted.startup();assert restarted.status(e.device)['activeConnectionId'] is None
 with pytest.raises(RemoteTokenError):restarted.lease(cid)

@pytest.mark.asyncio
async def test_lost_ack_blocks_old_and_retries_only_same_pending(env):
 e=env;cid=await approved(e);p=await e.service.create(e.device);e.server.fail_ack=True
 with pytest.raises(OSError):await e.service.decision(e.device,p['connectionId'],'agent',e.server.generation)
 with pytest.raises(RemoteTokenError):e.service.lease(cid)
 generation=e.server.generation;e.server.fail_ack=False
 await e.service.ack(e.device,p['connectionId']);assert e.server.generation==generation

@pytest.mark.asyncio
async def test_ui_30s_and_ack_35s_boundaries(env):
 e=env;await e.service.configure(e.device,True);p=await e.service.create(e.device);v=e.server.views[p['connectionId']];v['displayDeadline']=stamp(time.time()-1)
 with pytest.raises(RemoteTokenError):await e.service.decision(e.device,p['connectionId'],'agent',e.server.generation)
 assert not any(path.endswith('/decision') for _,path in e.server.calls)

@pytest.mark.asyncio
async def test_jwt_wrong_audience_binding_and_epoch_rejected(env):
 e=env;cid=await approved(e)
 for changes in ({'aud':'owner-home'},{'exp':int(time.time())+61,'iat':int(time.time())},{'cnf':{'jkt':'x'*43}},{'scope':'notifications'}):
  with pytest.raises(RemoteTokenError):verify_lease(e.token(cid,changes),e.jwks,time.time())
 e.manager.require_device(e.device).access_epoch=2
 with pytest.raises(RemoteTokenError):e.service.lease(cid)

@pytest.mark.asyncio
async def test_expired_nonce_never_reaches_business(env):
 e=env;cid=await approved(e);n=e.service.nonce(cid)
 digest=__import__('hashlib').sha256(n['nonce'].encode()).digest();e.service.nonces[digest]=(cid,n['jti'],time.monotonic()-1)
 with pytest.raises(RemoteTokenError):e.service.authorize(cid,n['nonce'],sign(e.key,local_input(cid,n['jti'],'GET','/v1/mobile/agent/agents',b'',n['nonce'])),'GET','/v1/mobile/agent/agents',b'')

@pytest.mark.asyncio
async def test_expired_ack_cannot_activate(env):
 e=env;await e.service.configure(e.device,True);p=await e.service.create(e.device);e.server.fail_ack=True
 with pytest.raises(OSError):await e.service.decision(e.device,p['connectionId'],'agent',e.server.generation)
 e.server.views[p['connectionId']]['approvalDeadline']=stamp(time.time()-1);e.server.fail_ack=False
 with pytest.raises(RemoteTokenError):await e.service.ack(e.device,p['connectionId'])
 assert e.service.row(e.device)['active'] is None

@pytest.mark.asyncio
async def test_cloud_failure_does_not_reactivate_old_connection(env):
 e=env;cid=await approved(e);p=await e.service.create(e.device);original=e.manager._request
 async def failed(method,path,**kwargs):
  if path.endswith('/decision'):raise OSError('offline')
  return await original(method,path,**kwargs)
 e.manager._request=failed
 with pytest.raises(OSError):await e.service.decision(e.device,p['connectionId'],'agent',e.server.generation)
 with pytest.raises(RemoteTokenError):e.service.lease(cid)
 assert e.service.row(e.device)['active'] is None

@pytest.mark.asyncio
async def test_mobile_revoke_blocks_immediately_even_when_cloud_unreachable(env):
 e=env;cid=await approved(e);original=e.manager._request
 async def failed(method,path,**kwargs):
  if path.endswith('/revoke'):raise OSError('offline')
  return await original(method,path,**kwargs)
 e.manager._request=failed
 await e.service.challenge(e.device,cid,'revoke')
 with pytest.raises(OSError):await e.service.proof(e.device,cid,'revoke',{'nonce':'a'*43,'signature':sign(e.key,'\n'.join(('ai2apps-mobile-agent-proof-v1','revoke',cid,'a'*43,e.jkt))),'publicKey':e.jwk})
 with pytest.raises(RemoteTokenError):e.service.lease(cid)
 assert e.device in e.service.revocations

@pytest.mark.asyncio
async def test_wrong_key_cannot_bind_a_valid_cloud_lease(env):
 e=env;cid=await approved(e);wrong=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(Encoding.X962,PublicFormat.UncompressedPoint)
 jwk=dict(crv='P-256',kty='EC',x=b64(wrong[1:33]),y=b64(wrong[33:]))
 with pytest.raises(RemoteTokenError):await e.service.proof(e.device,cid,'lease',{'nonce':'a'*43,'signature':'fixture','publicKey':jwk})

@pytest.mark.asyncio
async def test_invalid_mobile_revoke_proof_cannot_disable_real_connection(env):
 e=env;cid=await approved(e);await e.service.challenge(e.device,cid,'revoke')
 with pytest.raises(RemoteTokenError):await e.service.proof(e.device,cid,'revoke',{'nonce':'a'*43,'signature':'wrong','publicKey':e.jwk})
 assert e.service.lease(cid)
 assert e.device not in e.service.revocations

@pytest.mark.asyncio
async def test_renew_preserves_identity_and_local_logout_stays_closed(env):
 e=env;cid=await approved(e);first=e.service.leases[cid]['claims']
 await e.service.challenge(e.device,cid,'lease')
 await e.service.proof(e.device,cid,'lease',{'nonce':'a'*43,'signature':sign(e.key,'\n'.join(('ai2apps-mobile-agent-proof-v1','lease',cid,'a'*43,e.jkt))),'publicKey':e.jwk})
 assert e.service.leases[cid]['claims']['session_id']==first['session_id']
 e.service.block_owner()
 with pytest.raises(RemoteTokenError):e.service.lease(cid)
 with pytest.raises(RemoteTokenError):await e.service.sync(e.device)
 assert not e.service.status(e.device)['enabled']


@pytest.mark.asyncio
async def test_app_handoff_requested_only_after_exact_cloud_negotiation(env):
 from ai2apps.remote.owner_home import APP_HANDOFF_PROTOCOL
 e=env;await e.service.configure(e.device,True)
 original=e.service.call;seen=[];supported=False
 async def call(device,method,path,body=None):
  if path=='/pairings':seen.append(body)
  value=await original(device,method,path,body)
  if method=='GET' and path=='/device' and supported:value['appHandoffProtocol']=APP_HANDOFF_PROTOCOL
  return value
 e.service.call=call
 await e.service.create(e.device);assert seen==[{}]
 supported=True
 await e.service.create(e.device);assert seen[-1]=={'appHandoffProtocol':APP_HANDOFF_PROTOCOL}


@pytest.mark.asyncio
async def test_combined_pending_generation_never_restores_old_committed_agent(env):
 e=env;s=e.service;old=await approved(e);p=await s.create(e.device);new=p['connectionId'];committed=e.server.generation
 original=s.call
 async def call(device,method,path,body=None):
  if path.endswith('/decision'):
   view=e.server.views[new];view.update(status='awaiting_ack',generation=committed+1,appHandoffProtocol='desktop-mobile-app-handoff-v1')
   return dict(view)
  if path.endswith('/ack'):
   assert s.row(e.device)['generation']==committed+1 and s.row(e.device)['pending']==new
   raise OSError('ACK uncertain')
  return await original(device,method,path,body)
 s.call=call
 with pytest.raises(OSError):await s.decision(e.device,new,'agent',committed)
 assert e.server.active==old and e.server.generation==committed
 await s.sync(e.device)
 assert s.row(e.device)['generation']==committed+1 and s.row(e.device)['active'] is None
 with pytest.raises(RemoteTokenError):s.lease(old)
 assert (await s.pairing(e.device,new))['status']=='awaiting_ack'
 assert s.row(e.device)['pending']==new
