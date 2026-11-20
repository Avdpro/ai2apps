"""Bot character authoring and single-definition handoff; no model calls."""
from io import BytesIO
import pytest
from PIL import Image
from test_app_interactions import runtime
from test_material_handoff import execution_session
from ai2apps.identity import IdentityRepository,OrganizationType
from ai2apps.gallery.repository import GalleryRepository
from ai2apps.gallery.characters import Characters,CharacterInput

@pytest.mark.asyncio
async def test_bot_character_authoring_and_handoff(runtime):
    IdentityRepository(runtime.database).bind_installation(installation_id='local',cloud_device_id='local-device',organization_id='local',organization_type=OrganizationType.HOUSEHOLD,core_user_id='local',billing_account_id='local',access_epoch=1)
    session=execution_session(runtime,'local','ai2apps.messager')
    scope=runtime.tools.context_for_session(caller_id='character-tools-test',session_id=session)
    async def invoke(tool,**args):return (await runtime.tools.execute(tool,args,context=scope)).output
    c=(await invoke('character.create',name='Panda',aliases=['Panpan']))['character']
    c=(await invoke('character.appearance.create',character_id=c['id'],revision=c['revision'],appearance={'name':'Hero','summary':'Panda with a blue cape'}))['character']
    aid=c['appearances'][0]['id']
    with pytest.raises(Exception,match='changed'):
        await invoke('character.update',character_id=c['id'],revision=1,changes={'name':'Changed'})
    with pytest.raises(Exception,match='definition image'):
        await invoke('character.appearance.update',character_id=c['id'],revision=c['revision'],appearance_id=aid,changes={'approved':True})
    repo=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery')
    stream=BytesIO();Image.new('RGB',(16,16),'blue').save(stream,'PNG');stream.seek(0)
    asset,_=repo.import_stream('local',stream,name='hero.png',media_type='image/png')
    c=(await invoke('character.appearance.update',character_id=c['id'],revision=c['revision'],appearance_id=aid,changes={'definition_image_id':asset['id']}))['character']
    c=(await invoke('character.appearance.update',character_id=c['id'],revision=c['revision'],appearance_id=aid,changes={'approved':True}))['character']
    assert c['appearances'][0]['approved']
    values=(await invoke('character.list',query='Panpan',finalized_only=False))['items']
    assert values[0]['id']==c['id'] and 'summary' not in values[0]['appearances'][0]
    assert (await invoke('character.list',query='Panpan',finalized_only=True))['items'][0]['id']==c['id']
    result=await invoke('character.use',character_id=c['id'],revision=c['revision'],appearance_id=aid)
    assert result['summary']=='Panda with a blue cape' and len(result['materials'])==1
    assert result['definition_image_id']==asset['id']
    other=Characters(repo,'other').save(CharacterInput(name='Private'))
    with pytest.raises(Exception):await invoke('character.get',character_id=other['id'])
    assert all(x['id']!=other['id'] for x in (await invoke('character.list'))['items'])
    c=(await invoke('character.update',character_id=c['id'],revision=c['revision'],changes={'aliases':['Hero panda']}))['character']
    assert (await invoke('character.get',character_id=c['id']))['character']['aliases']==['Hero panda']
