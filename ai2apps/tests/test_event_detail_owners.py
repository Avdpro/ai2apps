"""Owner data projections through the actual AaAT Gateway; synthetic video only."""
import json
from types import SimpleNamespace
import pytest
from ai2apps.events.builtin import CHANNEL,VIDEO,VOICE
from ai2apps.system_tasks.sessions import execution_session
from test_app_interactions import runtime
from test_app_chat_durable import bind_identity

async def read(r,event,tool):
 ctx=r.tools.context_for_session(caller_id='owner-detail-test',session_id=execution_session(r,'local','ai2apps.intelligence'))
 return (await r.tools.execute(tool,{'event_id':event['id']},context=ctx)).output

@pytest.mark.asyncio
async def test_channel_detail_membership_missing_and_current_content(runtime):
 from ai2apps.intelligence.store import IntelligenceStore
 r=runtime;s=IntelligenceStore(r.config.paths.artifacts_path/'intelligence')
 with s.connect() as db:
  db.execute('INSERT INTO channels VALUES(?,?,?)',('c','local','{}'))
  db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',('r','local','c','running',0,json.dumps({'pending_status':'completed','result_message':'done','new_article_ids':['a','missing']})))
  db.execute('INSERT INTO articles VALUES(?,?,?,?)',('a','local','c',json.dumps({'title':'Original','summary':'summary','body':'private full body'})))
 s.complete_pending('local','r');s.flush_business_events(r.events.business_publishers[CHANNEL])
 event=r.business_events.list('local',event_type=CHANNEL)['items'][0]
 with s.connect() as db:db.execute('UPDATE articles SET data=? WHERE id=?',(json.dumps({'title':'Edited current title','summary':'summary','body':'private full body','primary_source_url':'https://example.com/original','sources':[{'url':'https://example.com/original','source_name':'Original owner source'}]}),'a'))
 result=await read(r,event,'intelligence.event_details')
 assert result['detail_mode']=='current' and not result['historical_snapshot']
 assert result['articles'][0]['title']=='Edited current title' and result['missing_ids']==['missing']
 assert 'private full body' not in str(result)
 assert result['articles'][0]['url']=='https://example.com/original' and result['articles'][0]['sources'][0]['source_name']=='Original owner source'

@pytest.mark.asyncio
async def test_generated_video_detail_uses_owned_artifact(runtime,tmp_path,monkeypatch):
 from ai2apps.core import utc_now_text
 from test_video_processing_aaat import video
 r=runtime;output=tmp_path/'render.mp4';video(output);now=utc_now_text();task='event-details-video'
 with r.database.transaction(write=True) as db:
  db.execute("INSERT INTO video_generation_tasks(id,actor_id,model_id,model_revision,status,request_json,request_hash,created_at,updated_at) VALUES(?,?,?,?,'running','{}','hash',?,?)",(task,'local','fixture','1',now,now))
 def owned_model(identifier,actor):
  assert identifier=='fixture' and actor=='local'
  return SimpleNamespace(service_key='fixture.video',id='fixture')
 monkeypatch.setattr(r.video_tasks,'_model',owned_model)
 async def invoke(*_):return output
 monkeypatch.setattr(r.video_tasks,'_invoke',invoke);await r.video_tasks._run(task)
 event=r.business_events.list('local',event_type=VIDEO)['items'][0]
 result=await read(r,event,'video.event_details');assert result['output']['artifact_id']==event['subject']['id']
 assert 'download_url' not in str(result) and str(tmp_path) not in str(result)

@pytest.mark.asyncio
async def test_voice_detail_and_cross_type_access_rejected(runtime):
 from ai2apps.readaloud.repository import ReadAloudRepository
 r=runtime;repo=ReadAloudRepository(r.database,r.events)
 profile=repo.create_voice_profile('local',name='Owned profile',source_type='synthetic_designed',model_id=None,provider_voice_id=None,reference_transcript='private reference text',rights_scope={})
 event=r.business_events.list('local',event_type=VOICE)['items'][0]
 result=await read(r,event,'voice.event_details');assert result['profile']['name']=='Owned profile' and 'private reference' not in str(result)
 with pytest.raises(Exception):await read(r,event,'video.event_details')
 repo.delete_voice_profile('local',profile['id'])
 with pytest.raises(Exception):await read(r,event,'voice.event_details')
