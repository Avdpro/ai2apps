from pathlib import Path
import pytest
from ai2apps.native_export import NativeExportBroker


def broker_source(tmp_path):
    source=tmp_path/'source';source.mkdir()
    (source/'LivePhoto.jpg').write_bytes(b'jpeg')
    (source/'LivePhoto.mov').write_bytes(b'mov')
    broker=NativeExportBroker();broker.claim_next()
    return broker,source


def test_native_picker_cancel_does_not_save(tmp_path):
    broker,source=broker_source(tmp_path)
    identifier=broker.enqueue(source)
    assert broker.claim_next()==dict(id=identifier,name='LivePhoto.pvt',extension='pvt')
    assert broker.claim_next() is None
    broker.finish(identifier)
    assert broker.wait(identifier)=={'cancelled':True}
    assert sorted(p.name for p in tmp_path.iterdir())==['source']


def test_existing_package_is_preserved(tmp_path):
    broker,source=broker_source(tmp_path)
    destination=tmp_path/'Keep.pvt';destination.mkdir()
    (destination/'original').write_text('keep')
    identifier=broker.enqueue(source);broker.claim_next()
    broker.finish(identifier,path=str(destination))
    with pytest.raises(ValueError): broker.wait(identifier)
    assert (destination/'original').read_text()=='keep'
    assert not (destination/'LivePhoto.jpg').exists()


@pytest.mark.parametrize('path',['relative.pvt','/tmp/not-pvt.zip','/'])
def test_reject_invalid_native_destination(tmp_path,path):
    broker,source=broker_source(tmp_path)
    identifier=broker.enqueue(source);broker.claim_next()
    with pytest.raises(ValueError): broker.finish(identifier,path=path)
    broker.finish(identifier)
    broker.wait(identifier)


def test_expired_request_cannot_save(tmp_path):
    broker,source=broker_source(tmp_path)
    identifier=broker.enqueue(source);broker.claim_next()
    with pytest.raises(ValueError,match='timed out'): broker.wait(identifier,timeout=0)
    with pytest.raises(ValueError,match='no longer active'):
        broker.finish(identifier,path=str(tmp_path/'Late.pvt'))
    assert not (tmp_path/'Late.pvt').exists()


def test_old_shell_fails_without_saving_to_downloads(tmp_path):
    broker=NativeExportBroker()
    with pytest.raises(ValueError,match='updated Desktop Shell'): broker.enqueue(tmp_path)


def test_picker_completion_is_native_authenticated():
    source=(Path(__file__).parents[1]/'api/client.py').read_text()
    section=source.split("@router.get('/client/native-export/next'")[1].split('@router.get("/client/shell-browser-window/next"')[0]
    assert section.count('_require_helper_authorization(request)')==2
    assert 'native_export_broker.finish' in section


def test_native_routes_reject_web_content_and_complete_picker(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.client import create_client_router
    broker,source=broker_source(tmp_path)
    monkeypatch.setenv('AI2APPS_HELPER_TOKEN','a'*64)
    monkeypatch.setattr('ai2apps.api.client.native_export_broker',broker)
    app=FastAPI();app.include_router(create_client_router())
    client=TestClient(app)
    headers={'Authorization':'Bearer '+'a'*64}
    identifier=broker.enqueue(source)
    assert client.get('/client/native-export/next').status_code==401
    assert client.get('/client/native-export/next',headers={**headers,'Origin':'http://localhost'}).status_code==401
    assert client.get('/client/native-export/next',headers=headers).json()['id']==identifier
    url=f'/client/native-export/{identifier}/complete'
    assert client.post(url,json={'path':str(tmp_path/'Invalid.pvt')}).status_code==401
    assert client.post(url,headers=headers,json={'source':'untrusted'}).status_code==422
    assert client.post(url,headers=headers,content='not-json').status_code==422
    destination=tmp_path/'Selected.pvt'
    assert client.post(url,headers=headers,json={'path':str(destination)}).status_code==200
    assert broker.wait(identifier)['path']==str(destination)
    assert (destination/'LivePhoto.mov').read_bytes()==b'mov'
