from ai2apps.tests.test_intelligence_api import client
from ai2apps.identity import RequestPrincipal
from ai2apps.intelligence.models import ChannelInput


def test_backup_endpoints(client):
    owner=RequestPrincipal.legacy_local().actor_user_id
    store=client.app.state.runtime.intelligence_collector.store
    c=store.save_channel(owner,ChannelInput(name='Backup API',interests='test').model_dump())
    response=client.get('/intelligence/backup',params={'channel_id':c['id']})
    assert response.status_code==200
    assert response.headers['content-type']=='application/zip'
    assert response.headers['cache-control']=='no-store'
    payload=response.content
    preview=client.post('/intelligence/backup/preview',files={'file':('backup.zip',payload,'application/zip')})
    assert preview.status_code==200,preview.text
    result=client.post('/intelligence/backup/import',files={'file':('backup.zip',payload,'application/zip')},data={'expected':preview.json()['expected']})
    assert result.status_code==200,result.text
    assert result.json()['create']==0
    assert len(client.get('/intelligence').json()['channels'])==1
    assert client.get('/intelligence/backup?channel_id=missing').status_code==404


def test_invalid_backup_returns_owner_error(client):
    r=client.post('/intelligence/backup/preview',files={'file':('bad.zip',b'not a zip','application/zip')})
    assert r.status_code==409
